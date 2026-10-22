"""Isolated, one-pass train-only taxonomy experiment; never mutates R15.

No model imports at module load. Invalid predictions remain None. Private journals
are persisted before parsing, and a started directory cannot be resumed/replayed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

from src.task3.round24_review import taxonomy_metrics, validate_projection
from src.task3.schema import Task3Record, code_hash, validate_taxonomy
from src.task3.round15 import query_payload, parse_response

SYSTEM = ('Bạn đọc yêu cầu bài toán và mã C++ của sinh viên. Xác định những nhóm lỗi có bằng chứng '
          'từ mã nguồn so với yêu cầu bài toán. Chỉ trả về JSON có đúng một khóa `taxonomy_error`, '
          'là mảng không lặp các tên nhóm trong danh sách cho phép: `Lỗi biên dịch`, `Lỗi nhập/xuất`, '
          '`Lỗi logic`, `Lỗi vòng lặp`, `Lỗi mảng/chuỗi`, `Lỗi hàm`, `Lỗi edge case`, '
          '`Lỗi thuật toán`, `Lỗi hard-code`, `Lỗi style`. Có thể trả `[]` nếu không đủ căn cứ '
          'xác định lỗi. Không sinh feedback, giải thích, hướng sửa hoặc văn bản ngoài JSON. '
          'Không suy ra chương trình đúng chỉ từ việc biên dịch thành công.')
RETRY = 'JSON/schema không hợp lệ: {error}. Chỉ trả lại JSON đúng schema đã yêu cầu.'
PAYLOAD_KEYS = {'statement', 'problems', 'grading_policy', 'code', 'compiler'}
MODEL = 'Qwen/Qwen2.5-Coder-7B-Instruct'
REVISION = 'c03e6d358207e414f1eca0bb1891e29f1db0e242'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    path.chmod(0o600)


def append(path, value):
    with Path(path).open('a', encoding='utf-8') as f:
        f.write(json.dumps(value, ensure_ascii=False) + '\n')
        f.flush()
        os.fsync(f.fileno())
    Path(path).chmod(0o600)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(rows, key):
    result = {r[key]: r for r in rows}
    require(len(result) == len(rows), 'duplicate ' + key)
    return result


def validate_units(units):
    unique(units, 'source_id')
    ids = []
    for u in units:
        require(set(u['query_ids']) == {'1', '2', '3'}, 'three Level projections required')
        ids.extend(u['query_ids'].values())
        taxonomy_messages(u['payload'])
    require(len(ids) == len(set(ids)), 'duplicate projected query ID')


def taxonomy_messages(payload, error=None):
    require(set(payload) == PAYLOAD_KEYS, 'taxonomy payload allowlist mismatch')
    require(set(payload['compiler']) == {'status', 'diagnostic'}, 'compiler schema mismatch')
    require(all(set(p) <= {'pid', 'statement', 'prototype'} for p in payload['problems']),
            'unexpected problem fields')
    messages = [{'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}]
    if error is not None:
        messages.append({'role': 'user', 'content': RETRY.format(error=error[:500])})
    return messages


def _no_duplicates(pairs):
    result = {}
    for k, v in pairs:
        require(k not in result, 'duplicate JSON key')
        result[k] = v
    return result


def strict_object(text):
    require(isinstance(text, str), 'JSON text required')
    body = text.strip()
    if body.startswith('```'):
        match = re.fullmatch(r'```(?:json)?\s*([\s\S]*?)\s*```', body)
        require(match is not None, 'single JSON code fence required')
        body = match[1]
    try:
        value = json.loads(body, object_pairs_hook=_no_duplicates)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError('strict JSON object required') from exc
    require(isinstance(value, dict), 'JSON object required')
    return value


def parse_taxonomy(text):
    value = strict_object(text)
    require(set(value) == {'taxonomy_error'}, 'exact taxonomy_error key required')
    return validate_taxonomy(value['taxonomy_error'])


def run_taxonomy(units, backend, config, output_dir):
    validate_units(units)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    marker = out / 'started.json'
    # Exclusive creation is a one-pass interlock, including after interruption.
    try:
        with marker.open('x', encoding='utf-8') as f:
            json.dump({'units_sha256': digest(units), 'config_sha256': digest(config)}, f)
            f.flush()
            os.fsync(f.fileno())
    except FileExistsError as exc:
        raise ValueError('experiment already started; no automatic rerun') from exc
    results = []
    for u in units:
        labels = None
        error = None
        attempts = []
        for number in (1, 2):
            messages = taxonomy_messages(u['payload'], error)
            tokens = len(backend.tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True))
            require(tokens + config['max_new_tokens'] <= config['context_limit'], 'full query exceeds context')
            row = dict(source_id=u['source_id'], source_sha256=u['source_sha256'], attempt=number,
                       messages=messages, messages_sha256=digest(messages), input_tokens=tokens)
            start = time.perf_counter()
            try:
                generation = backend.generate(messages, config)
                row.update(raw_text=generation.text, output_tokens=generation.output_tokens,
                           latency_s=generation.latency_s, finish_reason=generation.finish_reason,
                           eos_reached=generation.eos_reached, runtime_error=None)
            except RuntimeError as exc:
                row.update(raw_text=None, output_tokens=None, latency_s=time.perf_counter()-start,
                           runtime_error=str(exc))
            append(out / 'attempts.jsonl', row)  # raw capture precedes parser
            attempts.append(row)
            if row['runtime_error']:
                error = row['runtime_error']
                break  # runtime failure is not eligible for a schema retry
            try:
                labels = parse_taxonomy(row['raw_text'])
                error = None
            except ValueError as exc:
                error = str(exc)
            append(out / 'decisions.jsonl', dict(source_id=u['source_id'], attempt=number,
                                               parse_error=error, accepted=error is None))
            if error is None:
                break  # never retry valid semantic predictions
        results.append(dict(source_id=u['source_id'], source_sha256=u['source_sha256'],
                            status='valid' if labels is not None else 'invalid', taxonomy_error=labels,
                            calls=len(attempts), retry=len(attempts)>1, error=error))
        write(out / 'results.private.json', results)
        print(json.dumps({'taxonomy_sources': len(results), 'total': len(units),
                          'valid': sum(r['status']=='valid' for r in results)}), flush=True)
    return results


def project_taxonomy(units, results):
    validate_units(units)
    by = unique(results, 'source_id')
    require(set(by) == {u['source_id'] for u in units}, 'result source mapping mismatch')
    projected = []
    for u in units:
        r = by[u['source_id']]
        require(r['source_sha256'] == u['source_sha256'], 'result code hash mismatch')
        if r['status'] == 'valid':
            validate_taxonomy(r['taxonomy_error'])
        else:
            require(r['status'] == 'invalid' and r['taxonomy_error'] is None, 'invalid is not []')
        for level, sid in u['query_ids'].items():
            projected.append(dict(sample_id=sid, source_id=u['source_id'], level=int(level),
                                  taxonomy_error=r['taxonomy_error'], status=r['status']))
    return projected


def numeric_gate(baseline, candidate):
    checks = dict(valid_20=candidate['n']==20 and candidate['invalid']==0,
                  strict_micro_f1=candidate['micro_f1'] is not None and baseline['micro_f1'] is not None
                  and candidate['micro_f1'] > baseline['micro_f1'],
                  exact_not_lower=candidate['exact'] >= baseline['exact'])
    return dict(passed=all(checks.values()), checks=checks)


def metrics_for(units, predictions, *, reference_key='gold'):
    rows = [dict(prediction=predictions[u['source_id']], reference=u[reference_key]) for u in units]
    result = taxonomy_metrics(rows)
    result.update({k: sum(c[k] for c in result['per_label'].values()) for k in ('TP', 'FP', 'FN')})
    result['empty_on_nonempty_gold'] = sum(predictions[u['source_id']] == [] and bool(u[reference_key]) for u in units)
    result['valid'] = result['n'] - result['invalid']
    return result


def audit_inputs(root):
    """Validate retained Round24 originals and journals, loading train data only."""
    root = Path(root)
    w = root / 'outputs/task3/round24-20261022'
    hashes = {}
    def load(rel):
        p = root / rel
        require(p.is_file(), 'missing artifact: ' + str(p))
        hashes[str(rel)] = sha(p)
        return read(p)
    freeze = load('outputs/task3/round24-20261022/selection-freeze.json')
    for p, expected in freeze['files'].items():
        path = Path(p)
        require(path.is_relative_to(root), 'freeze outside repository')
        require(path.is_file(), f'missing frozen artifact: {p}; expected {expected}')
        actual = sha(path)
        require(actual == expected, f'freeze hash mismatch: {p}; expected {expected}; actual {actual}')
        hashes[str(path.relative_to(root))] = actual
    prefix = 'outputs/task3/round24-20261022/'
    sources = load(prefix + 'sources.private.json')
    queries = load(prefix + 'model-inputs.private.json')
    baseline = unique(load(prefix + 'R15/predictions.json'), 'sample_id')
    traces = unique(load(prefix + 'R15/traces.json'), 'sample_id')
    progress = load(prefix + 'R15/progress.json')
    run = load(prefix + 'R15/run.json')
    require(run['config']['model_id'] == MODEL and run['config']['revision'] == REVISION, 'baseline model mismatch')
    require(run['requested'] == run['completed'] == 60 and not run['errors'], 'baseline incomplete')
    require(run['config']['input_sha256'] == sha(w/'model-inputs.private.json'), 'baseline input hash mismatch')
    require(progress['identity'] == run['identity'] and not progress['errors'], 'baseline run binding mismatch')
    attempts_path = w / 'R15/attempts.jsonl'
    hashes[str(attempts_path.relative_to(root))] = sha(attempts_path)
    attempts = [json.loads(l) for l in attempts_path.read_text().splitlines()]
    decisions_path = w / 'R15/decisions.jsonl'
    hashes[str(decisions_path.relative_to(root))] = sha(decisions_path)
    decisions = unique([json.loads(l) for l in decisions_path.read_text().splitlines()], 'attempt_id')
    validate_projection(queries, sources)
    require(len(sources)==20 and len(queries)==60, '20 sources and 60 queries required')
    require(len(unique(sources, 'source_sha256'))==20, 'duplicate source hash')
    for renamed in (False, True):
        require(len({code_hash(s['record']['code'], renamed=renamed) for s in sources})==20,
                'selected sources share canonical code identity')
    query_by = unique(queries, 'sample_id')
    require(set(baseline)==set(traces)==set(query_by)==set(progress['completed']), 'baseline query coverage mismatch')
    require(set(a['sample_id'] for a in attempts)==set(query_by), 'raw attempts coverage mismatch')
    original_refs = load(prefix + 'reference.private.json')
    review_refs = unique(load(prefix + 'reference-rulebook-v2.private.json'), 'original_id')
    human = load(prefix + 'human-decisions.private.json')
    require(not human and all(r.get('human_verified') is False for r in review_refs.values()),
            'unexpected human authority; protocol needs explicit revision')
    raw = {}
    for kind, directory in [('real','data/raw/sample_dataset'), ('synthetic','data/synth/generate-dataset')]:
        space = load(directory + '/label_space.json')
        from src.synth.taxonomy import LABEL_SPACE
        require(space['taxonomy_error'] == list(LABEL_SPACE), 'official labels differ')
        raw[kind] = unique(load(directory + '/task3_feedback.json')['samples'], 'sample_id')
    units = []
    for s in sources:
        r = s['record']
        sid = r['sample_id']
        require(r['split'] in ('real-train','synthetic-train'), sid + ': not train-only')
        origin = root / s['origin_file']
        require(origin.is_file() and sha(origin)==s['origin_file_sha256'], sid + ': origin hash mismatch')
        hashes[s['origin_file']] = sha(origin)
        matches = [json.loads(l)['record'] for l in origin.read_text().splitlines()
                   if json.loads(l)['record']['sample_id']==sid]
        require(matches == [r], sid + ': original record mismatch')
        code_path = Path(r['code_path'])
        require(code_path.is_relative_to(root) and code_path.is_file() and sha(code_path)==s['raw_source_sha256'], sid+': source bytes mismatch')
        hashes[str(code_path.relative_to(root))] = sha(code_path)
        require(hashlib.sha256(r['code'].encode()).hexdigest()==s['source_sha256'], sid+': code text hash mismatch')
        sample = raw[r['source']][sid]
        labels = sample['input']['taxonomy_error'] if r['source']=='real' else sample['output']['taxonomy_error']
        require(labels==r['gold_taxonomy'] and sample['output']['feedback']==r['gold_feedback'], sid+': original gold mismatch')
        ref = review_refs[sid]
        require(ref['source_sha256']==s['source_sha256'] and ref['original_gold_taxonomy']==labels, sid+': review binding mismatch')
        qs = [q for q in queries if q['original_submission_id']==sid]
        unit = dict(source_id=sid, source_sha256=s['source_sha256'], raw_source_sha256=s['raw_source_sha256'],
                    origin_file=s['origin_file'], origin_file_sha256=s['origin_file_sha256'],
                    source=r['source'], split=s['split'], family=s['family'], gold=labels,
                    review_status=ref['taxonomy_status'], provisional_reference=ref['reference_taxonomy'],
                    human_verified=False, query_ids={}, baseline={}, first_raw={}, baseline_trace={})
        for q in qs:
            qid = q['sample_id']
            require(all(q[k]==r[k] for k in ['statement','code','problems','grading_policy','exam_id','code_path']), qid+': projection mismatch')
            level = str(int(q['target_feedback_level'][6]))
            unit['query_ids'][level] = qid
            ats = [a for a in attempts if a['sample_id']==qid]
            trace = traces[qid]
            require(trace['attempts']==ats and ats and [a['attempt'] for a in ats]==list(range(1,len(ats)+1)), qid+': raw trace mismatch')
            require(progress['completed'][qid]['output']==baseline[qid]['output'] and progress['completed'][qid]['trace']==trace, qid+': progress mismatch')
            payload = json.loads(ats[0]['prompt_messages'][-1]['content'])
            require(payload == query_payload(Task3Record(**q)), qid+': rendered baseline payload differs')
            require(payload.pop('requested_level')==int(level), qid+': baseline Level differs')
            if 'payload' in unit:
                require(unit['payload']==payload, sid+': baseline task/compiler differs by Level')
            unit['payload'] = payload
            final = parse_response(json.dumps(baseline[qid]['output'], ensure_ascii=False))
            require(final == parse_response(ats[-1]['raw_text']) or trace['fallback_used'], qid+': final not bound to raw')
            unit['baseline'][level] = final['taxonomy_error']
            try:
                first = parse_response(ats[0]['raw_text'])['taxonomy_error']
            except ValueError:
                first = None
            unit['first_raw'][level] = first
            unit['baseline_trace'][level] = dict(calls=len(ats), retry=len(ats)>1, fallback=trace['fallback_used'])
            require(all(a['attempt_id'] in decisions for a in ats), qid+': missing decisions')
        units.append(unit)
    validate_units(units)
    require(set(review_refs)=={u['source_id'] for u in units} and len(original_refs)==20, 'review coverage mismatch')
    return dict(units=units, input_hashes=hashes, baseline_run=run,
                review_authority='agent review / user-provisional mapping; no human verification')
