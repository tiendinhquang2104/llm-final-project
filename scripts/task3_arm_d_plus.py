#!/usr/bin/env python3
"""Run a frozen D+ method on the existing internal30 or the complete public release.

Local artifacts contain private student data. No upload/push/submission capability.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.task3 import arm_d_plus as plus
from src.task3.dataset import load_task3, read_json, write_json
from src.task3.grounded_metrics import taxonomy_metrics
from src.task3.inference import load_tokenizer, tokenizer_metadata
from src.task3.language_precision_ablation import AuditedBackend
from src.task3.level_blind import digest, sha
from src.task3.public_contract import verify_public_contract
from src.task3.submission import validate_submission
from src.task3.two_pass import append
from src.synth.feedback import FEEDBACK_LEVELS

BASE = Path('/workspace/llm-final-project')
HISTORY = Path('/workspace/llm-final-project-ablation/outputs/task3/language-precision-ablation-20261024')
CONFIG = ROOT/'configs/task3/arm_d_plus_v1.json'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def code_hashes():
    paths = sorted((ROOT/'src').rglob('*.py'))
    paths += [Path(__file__), CONFIG]
    return {str(p.relative_to(ROOT)): sha(p) for p in paths}


def verify_method(root, freeze_path, config):
    frozen = read_json(freeze_path)
    require(frozen['config'] == config, 'frozen config drift')
    for name, h in frozen['code_sha256'].items():
        require((Path(root)/name).is_file() and sha(Path(root)/name) == h, 'frozen implementation drift: '+name)
    return frozen


def freeze_method(out, config, space, tok, supplied=None):
    if supplied:
        frozen = verify_method(ROOT, supplied, config)
        require(frozen['label_space'] == space, 'frozen label-space drift')
        require(frozen['tokenizer'] == tokenizer_metadata(tok), 'frozen tokenizer drift')
    else:
        frozen = {'version': plus.VERSION, 'config': config, 'code_sha256': code_hashes(),
                  'label_space': space, 'tokenizer': tokenizer_metadata(tok),
                  'method_identity': plus.method_identity(config, space['taxonomy_error'], space['feedback_level'], tok),
                  'source_HEAD': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  'prompts': {'findings': plus.FINDINGS_SYSTEM, 'feedback': plus.FEEDBACK_SYSTEM,
                              'guidance': plus.GUIDANCE, 'resolver': plus.RESOLVER_SYSTEM},
                  'mapping': {'version': plus.MAPPING_VERSION, 'resolver': plus.RESOLVER_VERSION,
                              'aliases': plus.ALIASES, 'definitions': plus.DEFINITIONS}}
    path = out/'method-freeze.json'
    if path.exists():
        require(read_json(path) == frozen, 'method freeze changed on resume')
    else:
        write_json(path, frozen)
        for name in frozen['code_sha256']:
            target = out/'frozen-code'/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/name, target)
    return frozen


def archive_binding(root, records, source):
    """Compare loader inputs against original archive bytes; do not alter datasets."""
    outer = BASE/'data-20261017T044357Z-1-001.zip'
    with zipfile.ZipFile(outer) as z:
        if source == 'public':
            middle_bytes = z.read('data/public-test-cham-diem-phan-hoi-files.zip')
            with zipfile.ZipFile(io.BytesIO(middle_bytes)) as middle:
                nested_bytes = middle.read('public_test_release.zip')
            prefix = 'public_test_release/'
        else:
            nested_bytes = z.read('data/generate-dataset.zip')
            prefix = 'generate-dataset/'
    with zipfile.ZipFile(io.BytesIO(nested_bytes)) as nested:
        for name in ('exams.json', 'label_space.json', 'task3_feedback.json'):
            require(nested.read(prefix+name) == (root/name).read_bytes(), 'archive metadata mismatch: '+name)
        codes = {}
        for r in records:
            path = Path(r.code_path)
            relative = path.relative_to(root).as_posix()
            require(nested.read(prefix+relative) == path.read_bytes(), 'archive code mismatch: '+r.sample_id)
            codes[r.sample_id] = sha(path)
    return {'outer_sha256': sha(outer), 'dataset_archive_sha256': hashlib.sha256(nested_bytes).hexdigest(),
            'metadata_sha256': {n: sha(root/n) for n in ('exams.json', 'label_space.json', 'task3_feedback.json')},
            'code_sha256': codes, 'records': len(records), 'archive_metadata_and_code_match': True}


def prepare_inputs(args, out):
    if args.phase == 'public':
        root = args.public_root.resolve()
        contract = verify_public_contract(root)
        requested = contract['requested_levels']
        requested_path = out/'requested-levels.private.json'
        if not requested_path.exists():
            write_json(requested_path, requested)
        else:
            require(read_json(requested_path) == requested, 'requested Level input drift')
        records = load_task3(root, 'public', requested_path)
        by_id = {r.sample_id: r for r in records}
        require(set(by_id) == set(requested), 'public ID mismatch')
        records = [by_id[sid] for sid in requested]
        require(all(r.gold_taxonomy is None and r.gold_feedback is None for r in records), 'public gold forbidden')
        write_json(out/'public-contract.json', contract)
    else:
        root = args.internal_root.resolve()
        old_units = read_json(args.history/'units.private.json')
        require(len(old_units) == 30 and len({u['sample_id'] for u in old_units}) == 30, 'existing internal30 required')
        available = {r.sample_id: r for r in load_task3(root, 'synthetic')}
        records = [available[u['sample_id']] for u in old_units]
        for old, r in zip(old_units, records):
            require(old['level'] == FEEDBACK_LEVELS.index(r.target_feedback_level)+1, 'internal historical Level drift')
            require(all(old['task'][k] == getattr(r, k) for k in ('statement', 'code', 'problems', 'grading_policy', 'exam_type')),
                    'internal source/history mismatch')
        requested = {r.sample_id: r.target_feedback_level for r in records}
        historical_gold = {g['sample_id']: g['taxonomy_error'] for g in read_json(args.history/'gold.private.json')}
        require(all(r.gold_taxonomy == historical_gold[r.sample_id] for r in records), 'historical gold drift')
        write_json(out/'gold.private.json', [{'sample_id': r.sample_id, 'taxonomy_error': r.gold_taxonomy} for r in records])
        write_json(out/'requested-levels.private.json', requested)
        contract = None
    space = read_json(root/'label_space.json')
    units = [plus.record_unit(r) for r in records]
    binding = archive_binding(root, records, args.phase)
    binding.update(phase=args.phase, input_units_sha256=digest(units), requested_levels_sha256=digest(requested))
    if (out/'input-binding.private.json').exists():
        require(read_json(out/'input-binding.private.json') == binding, 'run input identity drift')
    else:
        write_json(out/'input-binding.private.json', binding)
        write_json(out/'units.private.json', units)
        write_json(out/'label-space.private.json', space)
    return units, space, requested


def preflight(units, tok, config, space):
    lengths = []
    for u in units:
        messages = plus.messages_findings(u, space['taxonomy_error'])
        count = len(tok.apply_chat_template(messages, tokenize=True, add_generation_prompt=True))
        require(count+config['findings_max_new_tokens'] <= config['context_limit'],
                'detector full input plus output exceeds context: '+u['sample_id'])
        minimal_feedback = plus.messages_feedback(u, [], space['taxonomy_error'], space['feedback_level'])
        feedback_count = len(tok.apply_chat_template(minimal_feedback, tokenize=True, add_generation_prompt=True))
        require(feedback_count+config['max_new_tokens'] <= config['context_limit'],
                'feedback full input plus output exceeds context: '+u['sample_id'])
        lengths.append({'sample_id': u['sample_id'], 'detector_input_tokens': count,
                        'detector_output_allowance': config['findings_max_new_tokens'],
                        'minimum_renderer_input_tokens': feedback_count,
                        'renderer_output_allowance': config['max_new_tokens']})
    return {'records': len(lengths), 'context_limit': config['context_limit'],
            'max_detector_input': max(r['detector_input_tokens'] for r in lengths),
            'per_call_full_source_preflight': True, 'cases': lengths,
            'resolver_code_token_ids': plus.choice_token_ids(tok)}


class DPlusBackend(AuditedBackend):
    def generate(self, messages, config):
        result = super().generate(messages, config)
        if result.finish_reason != 'eos' and result.latency_s >= config['generation_max_time_s']:
            result.finish_reason = 'timeout'
        return result

    def choose(self, messages, labels):
        return plus.constrained_choice(self, messages, labels)


def validate_export(out, requested, labels):
    """The final submission name only becomes visible after all checks pass."""
    out = Path(out)
    path = out/'partial.predictions.json'
    rows = read_json(path)
    ids = [r.get('sample_id') for r in rows if isinstance(r, dict)]
    counts = Counter(ids)
    validation = {'expected': len(requested), 'completed': len(rows),
                  'missing': len(set(requested)-set(ids)), 'extra': len(set(ids)-set(requested)),
                  'duplicate': sum(n-1 for n in counts.values()), 'passed': False}
    try:
        official_result = validate_submission(path, requested)
        for row in rows:
            tax = row['output']['taxonomy_error']
            require(tax == [label for label in labels if label in tax], 'official taxonomy ordering required')
        validation.update(passed=True, validator='src.task3.submission.validate_submission', **official_result)
    except (ValueError, KeyError, TypeError) as exc:
        validation['error'] = str(exc)
        write_json(out/'validation.json', validation)
        raise
    write_json(out/'predictions.json', rows)
    validate_submission(out/'predictions.json', requested)
    validation['predictions_sha256'] = sha(out/'predictions.json')
    write_json(out/'validation.json', validation)
    return validation


def summarize(out, results, expected, runtime, wall_time, phase, history):
    rows = [json.loads(line) for line in (out/'attempts.jsonl').read_text().splitlines()] if (out/'attempts.jsonl').exists() else []
    reservations = [json.loads(line) for line in (out/'reservations.jsonl').read_text().splitlines()] if (out/'reservations.jsonl').exists() else []
    mappings = [a for r in results for a in r.get('mapping_audit', [])]
    failures = [dict(sample_id=r['sample_id'], **r['failure']) for r in results if r['failure']]
    summary = {'method': plus.VERSION, 'phase': phase, 'expected': expected,
               'completed': sum(r['status']=='resolved' for r in results), 'unresolved': len(failures),
               'failures': failures, 'mapping_counts': dict(Counter(a['mapping_method'] for a in mappings)),
               'normal_calls': sum(r['kind']=='normal' for r in rows),
               'repair_calls': sum(r['kind']=='repair' for r in rows),
               'resolver_calls': sum(r['kind']=='resolver' for r in rows),
               'resolver_forward_passes': sum(r.get('forward_passes',0) for r in rows if r['kind']=='resolver'),
               'json_generations': sum(r['kind']!='resolver' for r in rows),
               'total_calls': len(rows), 'reservations': len(reservations),
               'interrupted_reservations': len(reservations)-len(rows),
               'input_tokens': sum(r['input_tokens'] for r in rows),
               'generated_output_tokens': sum(r.get('output_tokens') or 0 for r in rows),
               'resolver_input_tokens': sum(r['input_tokens'] for r in rows if r['kind']=='resolver'),
               'resolver_decision_tokens': sum(r.get('decision_tokens',0) for r in rows),
               'generation_and_resolver_latency_s': sum(r['latency_s'] for r in rows),
               'resolver_latency_s': sum(r['latency_s'] for r in rows if r['kind']=='resolver'),
               'last_invocation_wall_time_s': wall_time, 'runtime': runtime,
               'branch': subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
               'HEAD': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
               'feedback_language_check': 'Vietnamese requested; structural validator checks nonempty text, not semantic language or factual correctness.',
               'semantic_review': {'false_diagnosis':'not_evaluated', 'unsupported_diagnosis':'not_evaluated',
                                   'Level_compliance':'not_evaluated', 'placeholder_variants':'not_evaluated',
                                   'reason':'No compatible content review of the new D+ outputs; historical reviews rate different outputs.'},
               'limitations': ['Enum/schema validity does not verify diagnostic correctness.',
                               'Combined method change, not a single-component enum ablation.',
                               'Original Word binary unavailable; checked-in .docx.md conversion read. Public release contract governs.']}
    if phase == 'internal':
        gold = read_json(out/'gold.private.json')
        historical = {r['sample_id']:r for r in read_json(history/'D/results.private.json')}
        def tax(row):
            return row['output']['taxonomy_error'] if row['status']=='resolved' else None
        summary['taxonomy_metrics'] = {'D_plus': taxonomy_metrics([r['taxonomy_error'] for r in gold], [tax(r) for r in results]),
                                       'historical_D': taxonomy_metrics([r['taxonomy_error'] for r in gold], [tax(historical[r['sample_id']]) for r in results])}
        summary['comparison'] = 'Same30 IDs/source code/statements/problems/policy/requested Levels and unchanged gold; D+ enriches previously omitted metadata and changes prompts/mapping. Seen development, not heldout.'
    write_json(out/'run-summary.json', summary)
    return summary


def write_reproduction(args, out):
    py = Path(sys.executable).absolute()
    flags = ['--phase', args.phase, '--out', str(out), '--public-root', str(args.public_root.resolve()),
             '--internal-root', str(args.internal_root.resolve()), '--history', str(args.history.resolve())]
    flags += ['--method-freeze', str((args.method_freeze or out/'method-freeze.json').resolve())]
    base_cmd = [str(py), str(Path(__file__).resolve()), *flags]
    resume = shlex.join([*base_cmd, '--resume'])
    reproduce_flags = [str(out)+'-reproduce' if token == str(out) else token for token in flags]
    reproduce = shlex.join([str(py), str(Path(__file__).resolve()), *reproduce_flags])
    verify = shlex.join([*base_cmd, '--resume', '--verify-only'])
    write_json(out/'commands.json', {'reproduce': reproduce, 'resume': resume, 'verify_resume': verify})
    (out/'REPRODUCE.md').write_text('# D+ local reproduction\n\nRun from any directory with the existing local model cache and datasets.\n\n```bash\n'+reproduce+'\n```\n\nResume the same run:\n\n```bash\n'+resume+'\n```\n\nRead-only resume/input/freeze preflight:\n\n```bash\n'+verify+'\n```\n', encoding='utf-8')


def bundle(out):
    require(read_json(out/'validation.json')['passed'], 'cannot bundle invalid submission')
    main = ['predictions.json','validation.json','config.resolved.json','run-summary.json','method-freeze.json',
            'commands.json','REPRODUCE.md','REPORT.md','preflight.json','input-binding.private.json']
    submission_zip = out.parent/(out.name+'-submission.zip')
    with zipfile.ZipFile(submission_zip, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in main:
            if (out/name).is_file(): z.write(out/name, name)
    audit_zip = out.parent/(out.name+'-audit.private.zip')
    paths = sorted(p for p in out.rglob('*') if p.is_file())
    with zipfile.ZipFile(audit_zip, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in paths: z.write(p, p.relative_to(out).as_posix())
    for target in (submission_zip,audit_zip):
        target.chmod(0o600)
        with zipfile.ZipFile(target) as z: require(z.testzip() is None, 'bundle CRC failure')
    write_json(out/'bundles.json', {p.name:{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in (submission_zip,audit_zip)})


def report(out, summary):
    s=summary;runtime=s['runtime']
    metrics=''
    if 'taxonomy_metrics' in s:
        metrics='\nTaxonomy với gold giữ nguyên: '+json.dumps({k:{m:v[m] for m in ('micro_f1','macro_f1','exact_count')} for k,v in s['taxonomy_metrics'].items()},ensure_ascii=False)+'.\n'
    text=f'''# Task 3 {s['method']} — {s['phase']}

Hoàn tất {s['completed']}/{s['expected']}; unresolved {s['unresolved']}. Mapping: {json.dumps(s['mapping_counts'],ensure_ascii=False)}.
Normal calls {s['normal_calls']}; corrective retries {s['repair_calls']}; resolver calls/passes {s['resolver_calls']}/{s['resolver_forward_passes']}.
Input tokens {s['input_tokens']}; output sinh {s['generated_output_tokens']}; resolver input {s['resolver_input_tokens']}; thời gian calls {s['generation_and_resolver_latency_s']:.3f}s, resolver {s['resolver_latency_s']:.3f}s.
VRAM peak allocated/reserved: {runtime['peak_gpu_memory_allocated_bytes']/2**30:.3f}/{runtime['peak_gpu_memory_reserved_bytes']/2**30:.3f} GiB. Actual precision {runtime['actual_precision']}; không quantization/offload. Seed42, greedy; model/revision và resolved GenerationConfig trong config.resolved.json.
{metrics}
D+ tách parse, mapping nhãn và validate; alias chỉ đổi nhãn, unknown dùng logits trên đúng A–J của tokenizer thật, cùng model BF16. Hỗ trợ labels đa nhãn và label cũ; union theo label_space. Bảo toàn constraints/io_mode/ngôn ngữ/đề/code/compile_log/test_report bằng allowlist, giữ nguồn metadata; không coi log rỗng là pass. Prompt chỉ dẫn tiếng Anh, feedback tiếng Việt theo Level chính thức. Mỗi stage tối đa một corrective retry JSON/schema; renderer retry giữ nguyên findings.

Tài liệu .docx.md mô tả Task3 nhận nhãn cho sẵn; public thực tế không có nhãn input và yêu cầu taxonomy_error cùng feedback. Đã theo public release. Không có binary Word để đối chiếu trực tiếp. Không sửa gold, không dùng Task2/lịch sử để điền public. Không có đánh giá nội dung tương thích cho D+ mới: false/unsupported diagnosis, Level và placeholder chưa đánh giá. Enum/schema hợp lệ không chứng minh chẩn đoán hay feedback đúng.

predictions.json chỉ được tạo sau validator pass; validation.json ghi expected/missing/duplicate/extra và SHA256. Raw từng attempt, resolver scores, rendered prompts, findings chuẩn hóa, audit mapping và journal ở cùng thư mục/bundle audit riêng tư. Commands tái lập/resume ở REPRODUCE.md. Không upload leaderboard hoặc push dữ liệu.
'''
    (out/'REPORT.md').write_text(text, encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('internal','public'),required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--public-root',type=Path,default=BASE/'data/raw/public_test_release')
    parser.add_argument('--internal-root',type=Path,default=BASE/'data/synth/generate-dataset')
    parser.add_argument('--history',type=Path,default=HISTORY)
    parser.add_argument('--method-freeze',type=Path)
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args();out=args.out.resolve()
    if args.phase=='public': require(args.method_freeze is not None, 'public requires pre-public internal method freeze')
    if args.resume: require(out.is_dir(), 'resume directory missing')
    else: require(not out.exists(), 'existing directory requires --resume')
    out.mkdir(parents=True,exist_ok=True);out.chmod(0o700)
    config=read_json(CONFIG)
    require(not config['load_in_4bit'] and config['seed']==42 and config['do_sample'] is False and not config.get('adapter'), 'fixed BF16 greedy base model required')
    os.environ.update(HF_HOME=str(BASE/'outputs/task3/hf-cache'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    units,space,requested=prepare_inputs(args,out)
    tok=load_tokenizer(config)
    frozen=freeze_method(out,config,space,tok,args.method_freeze or (out/'method-freeze.json' if args.resume else None))
    write_json(out/'preflight.json',preflight(units,tok,config,space))
    write_reproduction(args,out)
    bound_config={**config,'implementation_sha256':frozen['code_sha256']}
    if args.verify_only:
        # Reconstruct the entire journal identity, including projected inputs.
        identity=digest([plus.method_identity(bound_config,space['taxonomy_error'],space['feedback_level'],tok),
                         [{'sample_id':u['sample_id'],'task':plus.task_payload(u),'level':u['level'],'provenance':u.get('provenance')} for u in units]])
        if (out/'identity.json').exists(): require(read_json(out/'identity.json')=={'identity':identity},'resume identity mismatch')
        print(json.dumps({'verified':True,'records':len(units),'method_freeze_sha256':sha(out/'method-freeze.json')}));return
    if (out/'run-summary.json').exists() and read_json(out/'run-summary.json')['completed']==len(units):
        validation=validate_export(out,requested,space['taxonomy_error'])
        print(json.dumps({'resume':'complete; no model loaded','validation':validation},ensure_ascii=False));return
    free=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip().splitlines()
    require(len(free)==1 and int(free[0])>=config['minimum_free_gpu_mib'],'GPU unavailable or another model active; no concurrent BF16 load')
    started=time.perf_counter()
    backend=DPlusBackend(config,tok,out)
    require(backend.model.generation_config.max_time==config['generation_max_time_s'],'generation timeout is not enforced')
    write_json(out/'runtime-before.json',backend.runtime_metadata())
    resolved={'requested':config,'tokenizer':tokenizer_metadata(tok),'choice_tokens':plus.choice_token_ids(tok),
              'runtime':backend.runtime_metadata(),'generation':{stage:read_json(out/f'generation-{stage}.json') for stage in ('taxonomy','feedback')},
              'packages':{p:importlib.metadata.version(p) for p in ('torch','transformers','tokenizers','accelerate')},
              'implementation_sha256':frozen['code_sha256'],'method_freeze_sha256':sha(out/'method-freeze.json')}
    write_json(out/'config.resolved.json',resolved)
    results=plus.run_units(units,backend,bound_config,out,space)
    runtime=backend.runtime_metadata();write_json(out/'runtime-after.json',runtime)
    invocation={'wall_time_s':time.perf_counter()-started,'runtime':runtime,'resume':args.resume,'timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    append(out/'invocations.jsonl',invocation)
    verify_method(ROOT,out/'method-freeze.json',config)
    summary=summarize(out,results,len(units),runtime,invocation['wall_time_s'],args.phase,args.history)
    report(out,summary)
    try:
        validation=validate_export(out,requested,space['taxonomy_error'])
    except ValueError:
        print(json.dumps({'complete':False,'completed':summary['completed'],'expected':len(units),'summary':str(out/'run-summary.json')},ensure_ascii=False));return 1
    bundle(out)
    print(json.dumps({'complete':True,'completed':summary['completed'],'expected':len(units),'validation':validation,
                      'mapping_counts':summary['mapping_counts'],'predictions':str(out/'predictions.json')},ensure_ascii=False))
    return 0


if __name__=='__main__':
    sys.exit(main())
