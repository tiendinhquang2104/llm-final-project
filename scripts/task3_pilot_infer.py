#!/usr/bin/env python3
"""One-pass paired pilot inference. Imports never load models or evaluation inputs.

Only the frozen safe model-input artifact enters prompts. This module never reads
references or ledgers. CLI execution requires an explicit --start flag.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from src.task3.dataset import write_json
from src.task3.inference import HFBackend
from src.task3.round15_runner import run_records
from src.task3.pilot_training import _digest
from src.task3.round15 import parse_response

# Resolve lazily so the runner remains importable before protocol preparation.
protocol = None
REVISION = 'c03e6d358207e414f1eca0bb1891e29f1db0e242'
LOCKED = dict(model_id='Qwen/Qwen2.5-Coder-7B-Instruct', revision=REVISION,
              seed=42, load_in_4bit=True, do_sample=False, context_limit=16384,
              diagnosis_max_tokens=2048, max_new_tokens=1024, level4_max_tokens=1536,
              max_time=60, max_attempts=3, prompt_variant='zero_shot')
TASK_KEYS = {'statement', 'problems', 'grading_policy', 'student_code', 'compiler_evidence', 'allowed_labels'}
ROW_KEYS = {'request_id', 'sample_id', 'kind', 'requested_level', 'task'}
STATUSES = ('completed', 'unresolved', 'runtime_error', 'schema_error')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _append(path, value):
    path = Path(path)
    with path.open('a', encoding='utf-8') as stream:
        os.chmod(path, 0o600)
        stream.write(json.dumps(value, ensure_ascii=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def _locked(config):
    if any(config.get(key) != value for key, value in LOCKED.items()):
        raise ValueError('locked pilot generation settings differ')
    if config.get('bad_words_ids') or config.get('few_shot_k', 0):
        raise ValueError('locked pilot forbids generation filters/examples')


def normalize_inference_config(frozen):
    """Translate only the sealed preparation key names into backend options."""
    raw = dict(frozen['inference'])
    if raw.get('model_id', frozen['model_id']) != frozen['model_id'] or raw.get('revision', frozen['revision']) != frozen['revision']:
        raise ValueError('locked model identity differs inside inference config')
    raw['model_id'], raw['revision'] = frozen['model_id'], frozen['revision']
    raw['diagnosis_max_tokens'] = raw.pop('diagnosis_max_new_tokens')
    raw['max_time'] = raw.pop('generation_max_time_s')
    raw.setdefault('max_attempts', 3)
    raw.setdefault('prompt_variant', 'zero_shot')
    _locked(raw)
    return raw


def _validate_rows(rows, expected_requests=None):
    seen, sources = set(), {}
    for row in rows:
        if set(row) != ROW_KEYS or set(row.get('task', {})) != TASK_KEYS:
            raise ValueError('unsafe model input keys')
        if not all(isinstance(row[key], str) and row[key] for key in ('request_id', 'sample_id')):
            raise ValueError('invalid model input ID')
        if row['request_id'] in seen:
            raise ValueError('duplicate request ID')
        seen.add(row['request_id'])
        if type(row['requested_level']) is not int or row['requested_level'] not in (1, 2, 3, 4):
            raise ValueError('invalid requested Level')
        if row['kind'] not in ('primary', 'counterfactual'):
            raise ValueError('invalid request kind')
        if not isinstance(row['task']['student_code'], str):
            raise ValueError('model input full source must be text')
        task_hash = digest(row['task'])
        if row['sample_id'] in sources and sources[row['sample_id']] != task_hash:
            raise ValueError('same source ID has differing tasks')
        sources[row['sample_id']] = task_hash
    actual = [dict(request_id=r['request_id'], sample_id=r['sample_id'], level=r['requested_level'], kind=r['kind']) for r in rows]
    if expected_requests is not None and actual != expected_requests:
        raise ValueError('manifest request order/identity mismatch')


def _start(out, arm, config, rows):
    out.mkdir(parents=True, exist_ok=True)
    marker = out/'started.json'
    # Exclusive creation is intentional: interrupted runs cannot silently resume.
    with marker.open('x', encoding='utf-8') as stream:
        os.chmod(marker, 0o600)
        json.dump(dict(arm=arm, config=config, config_sha256=digest(config), inputs_sha256=digest(rows),
                       total_requests=len(rows), started_unix=time.time(), resume_allowed=False), stream)
        stream.flush()
        os.fsync(stream.fileno())


def _capture(backend, messages, config, out, *, request_id, stage, key):
    started = time.perf_counter()
    phase = 'context'
    row = dict(request_id=request_id, stage=stage, generation_key=key, prompt_messages=messages,
               prompt_sha256=digest(messages), config_sha256=digest(config), generation_config=dict(config), raw_text=None, raw_sha256=None,
               output_tokens=0, input_tokens=None, finish_reason=None, eos_reached=None, error=None, error_status=None)
    try:
        row['input_tokens'] = len(backend.tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True))
        if row['input_tokens'] + config['max_new_tokens'] > config['context_limit']:
            raise ValueError('full source exceeds context budget; source never truncated')
        phase = 'generation'
        generated = backend.generate(messages, config)
        row.update(raw_text=generated.text, output_tokens=generated.output_tokens, latency_s=generated.latency_s,
                   finish_reason=generated.finish_reason, eos_reached=generated.eos_reached)
    except Exception as exc:
        row.update(error=f'{type(exc).__name__}: {exc}', token_count_unknown=True,
                   error_status='runtime_error' if phase=='generation' else 'unresolved')
    except BaseException as exc:
        row.update(error=f'{type(exc).__name__}: interrupted', token_count_unknown=True,
                   elapsed_s=time.perf_counter()-started)
        _append(out/'generations.jsonl', row)
        raise
    row['elapsed_s'] = time.perf_counter()-started
    if row['raw_text'] is not None:
        row['raw_sha256'] = hashlib.sha256(row['raw_text'].encode()).hexdigest()
    # Always persist raw text before parsing or disclosure checks.
    _append(out/'generations.jsonl', row)
    return row


def _record(row):
    task = row['task']
    compiler = task['compiler_evidence']
    # Frozen R15's public query projection is reused unchanged.
    return SimpleNamespace(sample_id=row['request_id'], statement=task['statement'], problems=task['problems'],
                           grading_policy=task['grading_policy'], code=task['student_code'],
                           target_feedback_level=f"Level {row['requested_level']}",
                           provenance={'_task3_compile_check': compiler})


def _legacy_error_status(entry):
    attempts = entry.get('trace', {}).get('attempts', [])
    if not attempts:
        return 'unresolved'
    if attempts[-1].get('runtime_error'):
        return 'runtime_error'
    try:
        parse_response(attempts[-1].get('raw_text'))
    except (ValueError, TypeError, KeyError):
        return 'schema_error'
    return 'unresolved'


def run_arm(rows, backend, config, output_dir, *, arm, expected_requests=None, _started=False):
    """Run all ordered requests once; unresolved rows remain explicit errors."""
    global protocol
    if arm not in ('A', 'B', 'C'):
        raise ValueError('unknown pilot arm')
    _locked(config)
    _validate_rows(rows, expected_requests)
    out = Path(output_dir)
    if not _started:
        _start(out, arm, config, rows)
    predictions, cache = [], {}
    def snapshot(complete=False, error=None):
        write_json(out/'predictions.partial.json', predictions)
        write_json(out/'status.json', dict(arm=arm, complete=complete, processed_requests=len(predictions),
                   expected_requests=len(rows), unresolved=sum(r['status']!='completed' for r in predictions),
                   statuses={status:sum(r['status']==status for r in predictions) for status in STATUSES},
                   diagnosis_schema_valid_sources=sum(d.get('schema_valid', False) for d in cache.values()),
                   diagnosis_resolved_sources=sum(d.get('resolved', False) for d in cache.values()), error=error))
    snapshot()
    try:
        if arm == 'A':
            # All bounded retries, guards and epistemic fallbacks are original R15.
            result = run_records([_record(row) for row in rows], backend, config, out/'legacy', examples=())
            success = {row['sample_id']: row['output'] for row in result['predictions']}
            for row in rows:
                rid = row['request_id']
                if rid in success:
                    predictions.append(dict(request_id=rid, status='completed', output=success[rid]))
                else:
                    predictions.append(dict(request_id=rid, status=_legacy_error_status(result['errors'][rid]), error=result['errors'][rid]['reason']))
                snapshot()
        else:
            if protocol is None:
                from src.task3 import pilot_protocol
                protocol = pilot_protocol
            for row in rows:
                rid, sid, task = row['request_id'], row['sample_id'], row['task']
                diagnosis_key = digest(dict(arm=arm, source_id=sid, task=task, stage='diagnosis'))
                cache_hit = diagnosis_key in cache
                if not cache_hit:
                    diagnostic = dict(diagnosis=None, raw=None, error=None, schema_valid=False, resolved=False, error_status='schema_error')
                    try:
                        value = protocol.task_from_model_input(task)
                        captured = _capture(backend, protocol.diagnosis_messages(value),
                            {**config, 'max_new_tokens':config['diagnosis_max_tokens']}, out,
                            request_id=rid, stage='diagnosis', key=diagnosis_key)
                        diagnostic.update(raw=captured['raw_text'], error=captured['error'])
                        if captured['error'] is not None:
                            diagnostic['error_status'] = captured['error_status']
                        if diagnostic['error'] is None:
                            diagnostic['diagnosis'] = protocol.parse_diagnosis(captured['raw_text'], value)
                            diagnostic['schema_valid'] = True
                            diagnostic['resolved'] = diagnostic['diagnosis']['status'] in ('clean', 'defective')
                            if not diagnostic['resolved']:
                                diagnostic['error'] = 'diagnosis_uncertain_unresolved'
                                diagnostic['error_status'] = 'unresolved'
                    except Exception as exc:
                        diagnostic['error'] = f'{type(exc).__name__}: {exc}'
                        diagnostic['error_status'] = 'schema_error'
                    cache[diagnosis_key] = diagnostic
                    _append(out/'diagnoses.jsonl', dict(source_id=sid, diagnosis_key=diagnosis_key, **diagnostic))
                diagnostic = cache[diagnosis_key]
                feedback_key = digest(dict(diagnosis_key=diagnosis_key, request_id=rid, level=row['requested_level']))
                decision = dict(request_id=rid, source_id=sid, diagnosis_key=diagnosis_key,
                    feedback_key=feedback_key, diagnosis_cache_hit=cache_hit, diagnosis_raw=diagnostic['raw'],
                    diagnosis=diagnostic['diagnosis'], diagnosis_schema_valid=diagnostic['schema_valid'],
                    diagnosis_resolved=diagnostic['resolved'], feedback_raw=None, error=diagnostic['error'],
                    status=diagnostic['error_status'] if diagnostic['error'] else 'unresolved')
                prediction = dict(request_id=rid, status=decision['status'])
                if not decision['error']:
                    try:
                        value = protocol.task_from_model_input(task)
                        messages = protocol.feedback_messages(value, diagnostic['diagnosis'], row['requested_level'])
                        cap = config['level4_max_tokens'] if row['requested_level']==4 else config['max_new_tokens']
                        captured = _capture(backend, messages, {**config, 'max_new_tokens':cap}, out,
                            request_id=rid, stage='feedback', key=feedback_key)
                        decision.update(feedback_raw=captured['raw_text'], error=captured['error'])
                        if captured['error'] is not None:
                            decision['status'] = captured['error_status']
                        if decision['error'] is None:
                            output = protocol.parse_feedback(captured['raw_text'], diagnostic['diagnosis'])
                            # The feedback stage cannot revise diagnosis taxonomy.
                            output['taxonomy_error'] = list(diagnostic['diagnosis']['taxonomy_error'])
                            prediction = dict(request_id=rid, status='completed', output=output)
                    except Exception as exc:
                        decision['error'] = f'{type(exc).__name__}: {exc}'
                        decision['status'] = 'schema_error'
                if prediction['status'] != 'completed':
                    prediction['status'] = decision['status']
                    prediction['error'] = decision['error'] or 'unresolved'
                decision['status'] = prediction['status']
                _append(out/'decisions.jsonl', decision)
                predictions.append(prediction)
                snapshot()
                print(json.dumps(dict(arm=arm, processed_requests=len(predictions), total_requests=len(rows))), flush=True)
        write_json(out/'predictions.json', predictions)
        snapshot(complete=True)
    except BaseException as exc:
        snapshot(error=f'{type(exc).__name__}: {exc}')
        raise
    return dict(predictions=predictions, complete=True)


def load_backend(config, *, adapter=None):
    """Reuse HF loader; attach PEFT after its base-only precision audit."""
    import torch
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError('locked pilot requires NF4 BF16 compute; no precision fallback')
    base = dict(config)
    base.pop('adapter', None)
    backend = HFBackend(base)
    if not hasattr(backend.model.generation_config, 'max_time'):
        raise RuntimeError('installed transformers cannot honor locked max_time')
    backend.model.generation_config.max_time = config['max_time']
    if adapter is not None:
        from peft import PeftModel
        backend.model = PeftModel.from_pretrained(backend.model, str(adapter), is_trainable=False)
        backend.model.eval()
    from bitsandbytes.nn import Linear4bit
    quantized = [module for module in backend.model.modules() if isinstance(module, Linear4bit)]
    if not quantized or any(module.compute_dtype != torch.bfloat16 for module in quantized):
        raise RuntimeError('actual NF4 modules do not all use locked BF16 compute')
    backend.precision_audit['pilot_quantized_compute_dtypes'] = sorted({str(module.compute_dtype) for module in quantized})
    return backend


def prepared_settings(frozen, arm, *, prepared_manifest, adapter_override=None):
    """Require the single complete training result and its exact selected files."""
    config = normalize_inference_config(frozen)
    work = Path(frozen['work_dir'])
    if not work.is_absolute():
        work = REPO/work
    result_path = work/'training'/'training-result.json'
    if not result_path.is_file():
        raise ValueError('complete training result required before any arm')
    result = json.loads(result_path.read_text())
    if result.get('status') != 'complete':
        raise ValueError('complete training result required before any arm')
    if result.get('config_sha256') != _digest(frozen) or result.get('config') != frozen:
        raise ValueError('training config binding differs from current frozen pilot')
    if result.get('manifest_sha256') != _digest(prepared_manifest):
        raise ValueError('training manifest binding differs from current verified pilot')
    adapter = work/'training'/'adapter'
    if adapter_override is not None and Path(adapter_override).resolve() != adapter.resolve():
        raise ValueError('adapter override differs from selected pilot adapter')
    tensor = adapter/'adapter_model.safetensors'
    if not tensor.is_file() or hashlib.sha256(tensor.read_bytes()).hexdigest() != result.get('selected_adapter_sha256'):
        raise ValueError('selected adapter tensor hash differs')
    actual = {str(path.relative_to(adapter)):hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted(adapter.rglob('*')) if path.is_file()}
    if actual != result.get('selected_adapter_files_sha256'):
        raise ValueError('selected adapter file map differs')
    return config, work, adapter if arm=='C' else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arm', choices=('A', 'B', 'C'), required=True)
    ap.add_argument('--config', type=Path, help='Optional exact copy of verified frozen config.json')
    ap.add_argument('--output', type=Path, help='Default: frozen work_dir/inference/arm-X')
    ap.add_argument('--adapter', type=Path, help='Must equal the selected training/adapter')
    ap.add_argument('--start', action='store_true', help='Explicitly begin the one authorized inference pass')
    args = ap.parse_args(argv)
    if not args.start:
        ap.error('--start is required; import/help never reads evaluation sources or loads models')
    from scripts.task3_pilot_prepare import verify_pilot
    from scripts.task3_freeze_eval_v2 import verify
    prepared, frozen, *_ = verify_pilot()
    if args.config is not None and json.loads(args.config.read_text()) != frozen:
        raise ValueError('requested config differs from frozen pilot config')
    if args.arm != 'C' and args.adapter is not None:
        raise ValueError('only arm C may attach an adapter')
    config, work, adapter = prepared_settings(frozen, args.arm, prepared_manifest=prepared, adapter_override=args.adapter)
    manifest = verify()
    input_path = Path(manifest['private_root'])/'model-inputs.private.json'
    declared_input = Path(frozen['eval_inputs'])
    if not declared_input.is_absolute():
        declared_input = REPO/declared_input
    if declared_input.resolve() != input_path.resolve():
        raise ValueError('frozen safe evaluation input path mismatch')
    # This is the only evaluation source read. No reference or ledger is opened.
    safe_bytes = input_path.read_bytes()
    if hashlib.sha256(safe_bytes).hexdigest() != manifest['private_files_sha256']['model-inputs.private.json']:
        raise ValueError('safe model input hash differs from frozen manifest')
    rows = json.loads(safe_bytes)
    _validate_rows(rows, manifest['requests'])
    if len(rows) != 96 or sum(r['kind']=='primary' for r in rows) != 60:
        raise ValueError('locked paired evaluation requires all96 requests/60primary')
    canonical = work/'inference'/f'arm-{args.arm}'
    output = args.output or canonical
    # The canonical marker also guards a caller-specified output directory.
    _start(canonical, args.arm, config, rows)
    if output.resolve() != canonical.resolve():
        _start(output, args.arm, config, rows)
    try:
        backend = load_backend(config, adapter=adapter)
        write_json(output/'runtime.before.json', backend.runtime_metadata())
        result = run_arm(rows, backend, config, output, arm=args.arm,
                         expected_requests=manifest['requests'], _started=True)
        write_json(output/'runtime.after.json', backend.runtime_metadata())
        print(json.dumps(dict(arm=args.arm, complete=result['complete'], requests=len(result['predictions']))))
    except BaseException as exc:
        if not (output/'status.json').exists():
            write_json(output/'status.json', dict(arm=args.arm, complete=False, processed_requests=0,
                       expected_requests=len(rows), error=f'{type(exc).__name__}: {exc}'))
        raise


if __name__ == '__main__':
    main()
