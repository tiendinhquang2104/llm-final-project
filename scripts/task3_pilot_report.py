#!/usr/bin/env python3
"""Offline immutable pilot summaries. References open only after all arms finish."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src.task3.frozen_eval import evaluate

ARMS = ('A', 'B', 'C')
STATUSES = {'completed', 'runtime_error', 'schema_error', 'unresolved', 'abstained'}
HAN = re.compile('[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002ffff\U00030000-\U000323af]')
KANA = re.compile('[\u3040-\u30ff\u31f0-\u31ff\uff66-\uff9f\U0001b000-\U0001b16f]')
HANGUL = re.compile('[\u1100-\u11ff\u3130-\u318f\ua960-\ua97f\uac00-\ud7af\ud7b0-\ud7ff]')


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _coverage(predictions, status, expected_ids=None):
    reasons = []
    if status.get('complete') is not True:
        reasons.append('arm status is not complete')
    if status.get('processed_requests') != 96 or status.get('expected_requests') != 96:
        reasons.append('arm did not process exactly all96 requests')
    ids = [p.get('request_id') for p in predictions]
    if len(ids) != 96 or len(set(ids)) != 96 or any(not isinstance(rid, str) or not rid for rid in ids):
        reasons.append('prediction request IDs are missing or duplicated')
    if expected_ids is not None and set(ids) != set(expected_ids):
        reasons.append('prediction request IDs differ from the frozen cohort')
    return reasons


def summarize_arms(snapshot, predictions_byarm, statuses_byarm, ledgers=None):
    """Score complete cohorts only; incomplete arms never receive prefix metrics."""
    requests = snapshot['requests']
    ids = [r['request_id'] for r in requests]
    primary = [r for r in requests if r['kind'] == 'primary']
    counterfactual = [r for r in requests if r['kind'] == 'counterfactual']
    triples = Counter(r['sample_id'] for r in counterfactual)
    levels = {sid: {r['level'] for r in counterfactual if r['sample_id'] == sid} for sid in triples}
    if (len(ids) != 96 or len(set(ids)) != 96 or len(primary) != 60 or
            len({r['sample_id'] for r in primary}) != 60 or len(counterfactual) != 36 or
            len(triples) != 12 or any(n != 3 for n in triples.values()) or
            any(value != {1, 2, 3} for value in levels.values())):
        raise ValueError('frozen cohort must have60 primary requests and36 counterfactual requests/12 triples')
    result = dict(status='complete', requested=96, primary_requested=60,
                  counterfactual_requested=36, counterfactual_triples=12, arms={})
    for arm in ARMS:
        predictions = predictions_byarm.get(arm, [])
        status = statuses_byarm.get(arm, {})
        reasons = _coverage(predictions, status, ids)
        report = dict(status='incomplete' if reasons else 'complete', processed_requests=len(predictions),
                      canonical_status_counts=dict(Counter(p.get('status', 'missing') for p in predictions)))
        if reasons:
            report['reasons'] = reasons
            result['status'] = 'incomplete'
        else:
            if any(p.get('status') not in STATUSES for p in predictions):
                raise ValueError('unknown prediction status; canonical scorer statuses are required')
            report['metrics'] = evaluate(snapshot, predictions, (ledgers or {}).get(arm))
        result['arms'][arm] = report
    return result


def _distribution(values):
    return dict(count=len(values), total=sum(values), min=min(values) if values else None,
                max=max(values) if values else None, mean=statistics.mean(values) if values else None,
                median=statistics.median(values) if values else None)


def _number(row, key):
    value = row.get(key)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def summarize_raw(predictions, *, generations=(), diagnoses=(), decisions=(), legacy_attempts=(),
                  legacy_decisions=(), legacy_traces=()):
    """Numeric journal diagnostics, without semantic review or output excerpts."""
    legacy = bool(legacy_attempts or legacy_decisions or legacy_traces)
    attempts = list(legacy_attempts if legacy else generations)
    keys = [(r.get('sample_id'), 'legacy') if legacy else (r.get('generation_key', r.get('request_id')), r.get('stage'))
            for r in attempts]
    known_input = [v for row in attempts if (v := _number(row, 'input_tokens')) is not None]
    known_output = [v for row in attempts if (v := _number(row, 'output_tokens')) is not None and not row.get('token_count_unknown')]
    latency = [v for row in attempts if (v := _number(row, 'latency_s')) is not None]
    elapsed = [v for row in attempts if (v := _number(row, 'elapsed_s')) is not None]
    parsed = []
    for prediction in predictions:
        if prediction.get('status') != 'completed':
            continue
        out = prediction.get('output')
        if out is None and isinstance(prediction.get('raw_text'), str):
            try: out = json.loads(prediction['raw_text'])
            except ValueError: continue
        if isinstance(out, dict) and isinstance(out.get('feedback'), str):
            parsed.append((prediction['request_id'], out['feedback']))
    diagnostic_ids = [row['source_id'] for row in diagnoses]
    if len(diagnostic_ids) != len(set(diagnostic_ids)):
        raise ValueError('diagnosis journal must contain each source exactly once')
    unicode_diagnostics = {name+'_request_ids': [rid for rid, text in parsed if expression.search(text)]
                           for name, expression in (('han', HAN), ('kana', KANA), ('hangul', HANGUL))}
    unicode_diagnostics.update(semantic_judgment=False,
        vietnamese_semantics='pending external hash-bound review ledger; Unicode is a diagnostic only')
    schema_rows = list(legacy_decisions) if legacy else list(diagnoses)
    schema_valid = sum(row.get('schema_valid') is True for row in schema_rows)
    feedback_attempts = [r for r in attempts if r.get('stage') == 'feedback'] if not legacy else attempts
    return dict(generation=dict(attempts=len(attempts), retries=len(attempts)-len(set(keys)),
                    input_tokens=int(sum(known_input)), input_tokens_known_attempts=len(known_input),
                    input_tokens_unknown_attempts=len(attempts)-len(known_input),
                    output_tokens=int(sum(known_output)), output_tokens_known_attempts=len(known_output),
                    output_tokens_unknown_attempts=len(attempts)-len(known_output),
                    latency_s=sum(latency), latency_known_attempts=len(latency),
                    elapsed_s=sum(elapsed), elapsed_known_attempts=len(elapsed),
                    by_stage=dict(Counter('legacy' if legacy else r.get('stage', 'unknown') for r in attempts)),
                    finish_reasons=dict(Counter(str(r.get('finish_reason', 'unknown')) for r in attempts))),
        diagnosis=dict(unique_sources=len(diagnostic_ids), schema_valid_sources=schema_valid if not legacy else None,
                       resolved_sources=sum(r.get('resolved') is True for r in diagnoses),
                       cache_hits=sum(r.get('diagnosis_cache_hit') is True for r in decisions),
                       denominator_unit='unique source; diagnosis is not repeated for cached requests'),
        feedback=dict(attempts=len(feedback_attempts), requested=len(predictions),
                      completed=sum(p.get('status') == 'completed' for p in predictions),
                      schema_valid_requests=(len(parsed) if legacy else sum(d.get('status') == 'completed' or
                        (d.get('error') is None and d.get('feedback_raw') is not None) for d in decisions))),
        schema_attempts=dict(assessed=len(schema_rows), valid=schema_valid,
                             scope='legacy combined attempts' if legacy else 'diagnosis sources'),
        fallback_requests=sum(row.get('fallback_used') is True for row in legacy_traces),
        feedback_length=dict(characters=_distribution([len(text) for _, text in parsed]),
                             words=_distribution([len(text.split()) for _, text in parsed]),
                             word_definition='Unicode whitespace-separated words'),
        unicode_diagnostics=unicode_diagnostics)


def _read(path):
    return json.loads(Path(path).read_text())


def _journal(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()] if Path(path).exists() else []


def _write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        os.chmod(path, 0o600)
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())


def run_report(work, *, verify_pilot, load_reference, ledgers=None):
    """Read reference callback only after every final arm artifact is complete."""
    work = Path(work)
    frozen = verify_pilot()
    training_path = work/'training'/'training-result.json'
    if not training_path.exists() or _read(training_path).get('status') != 'complete':
        raise ValueError('offline report requires complete frozen pilot training')
    states, predictions = {}, {}
    pending = dict(status='incomplete', arms={})
    for arm in ARMS:
        folder = work/'inference'/f'arm-{arm}'
        state_path, prediction_path = folder/'status.json', folder/'predictions.json'
        state = _read(state_path) if state_path.exists() else {}
        states[arm] = state
        reasons = []
        if state.get('complete') is not True or state.get('processed_requests') != 96 or state.get('expected_requests') != 96:
            reasons.append('all96 request processing is not complete')
        if not prediction_path.exists():
            reasons.append('final predictions artifact is absent')
        pending['arms'][arm] = dict(status='incomplete' if reasons else 'ready', reasons=reasons)
    if any(row['status'] != 'ready' for row in pending['arms'].values()):
        return pending
    for arm in ARMS:
        predictions[arm] = _read(work/'inference'/f'arm-{arm}'/'predictions.json')
        reasons = _coverage(predictions[arm], states[arm])
        if reasons:
            pending['arms'][arm] = dict(status='incomplete', reasons=reasons)
    if any(row['status'] != 'ready' for row in pending['arms'].values()):
        return pending
    output = work/'reports'
    paths = [output/f'arm-{arm}.summary.private.json' for arm in ARMS] + [output/'comparison.summary.private.json']
    if any(path.exists() for path in paths):
        raise FileExistsError('immutable pilot report already exists')
    snapshot = load_reference()
    result = summarize_arms(snapshot, predictions, states, ledgers)
    if result['status'] != 'complete':
        return result
    result['snapshot_sha256'] = _digest(snapshot)
    result['pilot_binding_sha256'] = _digest(frozen)
    for arm in ARMS:
        folder = work/'inference'/f'arm-{arm}'
        report = result['arms'][arm]
        report['raw_diagnostics'] = summarize_raw(predictions[arm],
            generations=_journal(folder/'generations.jsonl'), diagnoses=_journal(folder/'diagnoses.jsonl'),
            decisions=_journal(folder/'decisions.jsonl'), legacy_attempts=_journal(folder/'legacy'/'attempts.jsonl'),
            legacy_decisions=_journal(folder/'legacy'/'decisions.jsonl'),
            legacy_traces=_read(folder/'legacy'/'traces.json') if (folder/'legacy'/'traces.json').exists() else [])
        report['input_sha256'] = {str(path.relative_to(folder)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(folder.rglob('*')) if path.is_file()}
        report['training_result_sha256'] = hashlib.sha256(training_path.read_bytes()).hexdigest()
        report['review_ledger_sha256'] = _digest((ledgers or {}).get(arm, []))
        report['snapshot_sha256'] = result['snapshot_sha256']
        report['pilot_binding_sha256'] = result['pilot_binding_sha256']
    # Validate every journal and construct every summary before claiming any
    # immutable output name, so bad input cannot strand a partial report set.
    for arm in ARMS:
        _write_new(output/f'arm-{arm}.summary.private.json', result['arms'][arm])
    _write_new(output/'comparison.summary.private.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--score', action='store_true', help='explicitly permit reference scoring after all final arm outputs')
    parser.add_argument('--work', type=Path, default=REPO/'outputs/task3/pilot-v1-20261021')
    for arm in ARMS:
        parser.add_argument('--ledger-'+arm, type=Path)
    args = parser.parse_args(argv)
    if not args.score:
        parser.error('--score is required; importing/help never reads references or predictions')
    from scripts.task3_pilot_prepare import verify_pilot
    def load_reference():
        from scripts.task3_freeze_eval_v2 import verify
        manifest = verify()
        path = Path(manifest['private_root'])/'reference.private.json'
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest['private_files_sha256']['reference.private.json']:
            raise ValueError('frozen reference bytes changed')
        return json.loads(raw)
    ledger_paths = {arm:getattr(args, 'ledger_'+arm) for arm in ARMS}
    # Optional ledgers contain private reviews; they are read only on explicit scoring.
    ledgers = {arm:_read(path) for arm, path in ledger_paths.items() if path is not None}
    result = run_report(args.work, verify_pilot=verify_pilot, load_reference=load_reference, ledgers=ledgers)
    print(json.dumps(dict(status=result['status'], arms={arm:row['status'] for arm, row in result['arms'].items()})))
    return 0 if result['status'] == 'complete' else 2


if __name__ == '__main__':
    raise SystemExit(main())
