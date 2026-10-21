#!/usr/bin/env python3
"""Frozen base-Qwen paired pass on thirty prepared TRAIN sources.

Imports and --help perform no source reads or model loading. Only --start can
verify prepared artifacts and begin a canonical, non-resumable arm.
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
WORK = REPO / 'outputs/task3/diagnosis-contract-v1-20261021'
LOCKED = dict(model_id='Qwen/Qwen2.5-Coder-7B-Instruct',
              revision='c03e6d358207e414f1eca0bb1891e29f1db0e242', seed=42,
              load_in_4bit=True, do_sample=False, context_limit=16384,
              max_new_tokens=1024, diagnosis_max_tokens=1536, level4_max_tokens=1536,
              max_time=60, max_attempts=3, prompt_variant='zero_shot', few_shot_k=0,
              prompt_policy='round15-short-direct-v1',
              completion_policy='preserve_qwen_content_with_schema_and_explicit_l1_l2_only')
ROW_KEYS = {'request_id', 'sample_id', 'kind', 'requested_level', 'task'}
TASK_KEYS = {'statement', 'problems', 'grading_policy', 'code', 'compiler_evidence', 'domain'}
STATUSES = ('completed', 'abstained', 'runtime_error', 'schema_error', 'unresolved')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def _write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _append(path, value):
    with Path(path).open('a', encoding='utf-8') as stream:
        os.chmod(path, 0o600)
        stream.write(json.dumps(value, ensure_ascii=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def _locked(config):
    if config != LOCKED:
        raise ValueError('exact frozen base-model inference configuration required; no adapter or overrides')


def _validate_rows(rows):
    if not isinstance(rows, list) or len(rows) != 30:
        raise ValueError('all thirty TRAIN sources are required')
    request_ids, source_ids = set(), set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != ROW_KEYS or not isinstance(row['task'], dict) or set(row['task']) != TASK_KEYS:
            raise ValueError('unsafe model input keys')
        if any(not isinstance(row[k], str) or not row[k] for k in ('request_id', 'sample_id')):
            raise ValueError('invalid request/source identifier')
        if row['request_id'] in request_ids or row['sample_id'] in source_ids:
            raise ValueError('exactly one primary request per unique source required')
        request_ids.add(row['request_id']); source_ids.add(row['sample_id'])
        if row['kind'] != 'primary' or type(row['requested_level']) is not int or row['requested_level'] not in (1, 2, 3, 4):
            raise ValueError('primary request with integer Level1..4 required')
        if not isinstance(row['task']['code'], str) or not isinstance(row['task']['statement'], str):
            raise ValueError('full source and statement must be text')


def _start(out, arm, config, rows, manifest=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with (out/'started.json').open('x', encoding='utf-8') as stream:
        os.chmod(out/'started.json', 0o600)
        json.dump(dict(arm=arm, config=config, config_sha256=digest(config),
                       inputs_sha256=digest(rows), manifest_sha256=digest(manifest),
                       total_sources=30, started_unix=time.time(), resume_allowed=False), stream)
        stream.flush(); os.fsync(stream.fileno())
    descriptor = os.open(out, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    if any(path.name != 'started.json' for path in out.iterdir()):
        raise ValueError('refusing pre-existing unbound inference artifacts')


def _capture(backend, messages, config, out, *, request_id, stage, generation_index=None):
    started = time.perf_counter()
    capture = dict(request_id=request_id, stage=stage, capture_stage='before_parse_and_guard',
                   generation_index=generation_index,
                   prompt_messages=messages, prompt_sha256=digest(messages),
                   legacy_prompt_sha256=hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest() if stage == 'R15' else None,
                   generation_config=dict(config), config_sha256=digest(config),
                   raw_text=None, raw_sha256=None, input_tokens=None, output_tokens=0,
                   finish_reason=None, eos_reached=None, error=None, error_status=None)
    phase = 'context'
    try:
        capture['input_tokens'] = len(backend.tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True))
        if capture['input_tokens'] + config['max_new_tokens'] > config['context_limit']:
            raise ValueError('full source exceeds context budget; source never truncated')
        phase = 'generation'
        generated = backend.generate(messages, config)
        capture.update(raw_text=generated.text, output_tokens=generated.output_tokens,
                       latency_s=generated.latency_s, finish_reason=generated.finish_reason,
                       eos_reached=generated.eos_reached)
    except Exception as exc:
        capture.update(error=f'{type(exc).__name__}: {exc}', token_count_unknown=True,
                       error_status='runtime_error' if phase == 'generation' else 'unresolved')
    except BaseException as exc:
        capture.update(error=f'{type(exc).__name__}: interrupted', token_count_unknown=True,
                       elapsed_s=time.perf_counter()-started)
        _append(out/'generations.jsonl', capture)
        raise
    capture['elapsed_s'] = time.perf_counter()-started
    if capture['raw_text'] is not None:
        capture['raw_sha256'] = hashlib.sha256(capture['raw_text'].encode()).hexdigest()
    _append(out/'generations.jsonl', capture)
    return capture


def _record(row):
    task = row['task']
    return SimpleNamespace(sample_id=row['request_id'], statement=task['statement'], problems=task['problems'],
                           grading_policy=task['grading_policy'], code=task['code'],
                           target_feedback_level=f"Level {row['requested_level']}",
                           provenance={'_task3_compile_check': task['compiler_evidence']})


class CaptureBackend:
    """Preserve R15 generation results while journaling before its parser runs."""
    def __init__(self, backend, out):
        self.backend, self.out = backend, out
        self.generation_index = 0
        self.tokenizer = backend.tokenizer

    def generate(self, messages, config):
        self.generation_index += 1
        captured = _capture(self.backend, messages, config, self.out,
                            request_id=None, stage='R15', generation_index=self.generation_index)
        if captured['error']:
            raise RuntimeError(captured['error'])
        return SimpleNamespace(text=captured['raw_text'], output_tokens=captured['output_tokens'],
                               latency_s=captured['latency_s'], finish_reason=captured['finish_reason'],
                               eos_reached=captured['eos_reached'])


def _r15_prediction(row, result):
    from src.task3.round15 import parse_response
    successes = {p['sample_id']: p['output'] for p in result['predictions']}
    traces = {p['sample_id']: p for p in result['traces']}
    if row['request_id'] in successes:
        return dict(request_id=row['request_id'], sample_id=row['sample_id'], status='completed',
                    output=successes[row['request_id']], feedback_available=True,
                    trace=traces[row['request_id']])
    entry = result['errors'][row['request_id']]
    attempts = entry.get('trace', {}).get('attempts', [])
    status = 'unresolved'
    if attempts and attempts[-1].get('runtime_error'):
        status = 'runtime_error'
    elif attempts:
        try:
            parse_response(attempts[-1].get('raw_text'))
        except (ValueError, TypeError, KeyError):
            status = 'schema_error'
    return dict(request_id=row['request_id'], sample_id=row['sample_id'], status=status,
                feedback_available=False, error=entry['reason'], trace=entry.get('trace'))


def _short_prediction(row, backend, config, out):
    from src.task3 import diagnosis_contract_v1 as protocol
    rid, task = row['request_id'], row['task']
    prediction = dict(request_id=rid, sample_id=row['sample_id'], status='schema_error',
                      feedback_available=False, diagnosis_status=None)
    decision = dict(request_id=rid, source_id=row['sample_id'], diagnosis=None,
                    diagnosis_raw=None, feedback_raw=None, machine_audit=None, error=None)
    phase = 'diagnosis'
    try:
        captured = _capture(backend, protocol.diagnosis_messages(task),
                            {**config, 'max_new_tokens': config['diagnosis_max_tokens']}, out,
                            request_id=rid, stage='diagnosis')
        decision['diagnosis_raw'] = captured['raw_text']
        if captured['error']:
            prediction['status'] = captured['error_status']
            raise ValueError(captured['error'])
        parsed = protocol.parse_diagnosis(captured['raw_text'], task)
        diagnosis = parsed['diagnosis']
        decision.update(diagnosis=diagnosis, machine_audit=parsed['machine_audit'])
        if not parsed['machine_audit']['accepted']:
            raise ValueError('diagnosis_machine_audit_rejected')
        prediction['diagnosis_status'] = diagnosis['status']
        phase = 'feedback'
        cap = config['level4_max_tokens'] if row['requested_level'] == 4 else config['max_new_tokens']
        captured = _capture(backend, protocol.feedback_messages(task, diagnosis, row['requested_level']),
                            {**config, 'max_new_tokens': cap}, out, request_id=rid, stage='feedback')
        decision['feedback_raw'] = captured['raw_text']
        if captured['error']:
            prediction['status'] = captured['error_status']
            raise ValueError(captured['error'])
        output = protocol.parse_feedback(captured['raw_text'])
        output['taxonomy_error'] = list(diagnosis['taxonomy_error'])
        prediction.update(output=output, feedback_available=True,
                          status='abstained' if diagnosis['status'] == 'uncertain' else 'completed')
    except Exception as exc:
        prediction['error'] = decision['error'] = f'{phase}: {type(exc).__name__}: {exc}'
    decision.update(status=prediction['status'], feedback_available=prediction['feedback_available'],
                    diagnosis_status=prediction['diagnosis_status'])
    _append(out/'decisions.jsonl', decision)
    return prediction


def run_arm(rows, backend, config, output_dir, *, arm, _started=False):
    """Execute exactly thirty ordered sources; synthetic callers inject backends."""
    if arm not in ('R15', 'SHORT'):
        raise ValueError('unknown arm')
    _locked(config); _validate_rows(rows)
    out = Path(output_dir)
    if not _started:
        _start(out, arm, config, rows)
    predictions = []
    def snapshot(complete=False, error=None):
        _write(out/'predictions.partial.json', predictions)
        counts = {status: sum(p['status'] == status for p in predictions) for status in STATUSES}
        _write(out/'status.json', dict(arm=arm, complete=complete, processed_requests=len(predictions),
               expected_requests=30, feedback_available=sum(p.get('feedback_available', False) for p in predictions),
               statuses=counts, **counts, error=error))
    snapshot()
    try:
        legacy = None
        if arm == 'R15':
            from src.task3.round15_runner import run_records
            legacy = run_records([_record(row) for row in rows], CaptureBackend(backend, out),
                                 config, out/'legacy', examples=())
        for row in rows:
            prediction = (_r15_prediction(row, legacy) if arm == 'R15'
                          else _short_prediction(row, backend, config, out))
            predictions.append(prediction)
            if arm == 'R15':
                _append(out/'decisions.jsonl', prediction)
            snapshot()
            print(json.dumps(dict(arm=arm, processed_requests=len(predictions), total_requests=30)), flush=True)
        _write(out/'predictions.json', predictions)
        snapshot(complete=True)
    except BaseException as exc:
        snapshot(error=f'{type(exc).__name__}: {exc}')
        raise
    return dict(predictions=predictions, complete=True)


def assert_base_only(model):
    if getattr(model, '_hf_peft_config_loaded', False) or getattr(model, 'peft_config', None):
        raise RuntimeError('base-only pass forbids loaded PEFT adapters')
    if any(type(module).__module__.startswith('peft') for module in model.modules()):
        raise RuntimeError('base-only pass forbids loaded PEFT modules')


def load_backend(config):
    """Load only pinned base Qwen; audit actual NF4 double-quant BF16 modules."""
    _locked(config)
    import torch
    from bitsandbytes.nn import Linear4bit
    from src.task3.inference import HFBackend
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError('NF4 requires native BF16 compute; no precision fallback')
    backend = HFBackend(config)
    assert_base_only(backend.model)
    modules = list(backend.model.modules())
    quantized = [m for m in modules if isinstance(m, Linear4bit)]
    if not quantized or any(m.compute_dtype != torch.bfloat16 for m in quantized):
        raise RuntimeError('actual NF4 modules must all use BF16 compute')
    for module in quantized:
        if getattr(module.weight, 'quant_type', None) != 'nf4' or not getattr(module.weight, 'compress_statistics', False):
            raise RuntimeError('actual quantized weights must use NF4 double quantization')
    backend.model.generation_config.max_time = config['max_time']
    backend.precision_audit.update(adapter_loaded=False, quant_type='nf4', double_quant=True,
                                   actual_quantized_compute_dtypes=sorted({str(m.compute_dtype) for m in quantized}))
    return backend


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm', choices=('R15', 'SHORT'), required=True)
    parser.add_argument('--start', action='store_true')
    args = parser.parse_args(argv)
    if not args.start:
        parser.error('--start required to verify artifacts and begin the one authorized arm')
    from scripts.task3_contract_v1_prepare import verify
    manifest, config, rows = verify()
    _locked(config); _validate_rows(rows)
    out = WORK/'inference'/f'arm-{args.arm}'
    _start(out, args.arm, config, rows, manifest)
    try:
        backend = load_backend(config)
        _write(out/'runtime.before.json', backend.runtime_metadata())
        result = run_arm(rows, backend, config, out, arm=args.arm, _started=True)
        _write(out/'runtime.after.json', backend.runtime_metadata())
        print(json.dumps(dict(arm=args.arm, complete=result['complete'], requests=len(result['predictions']))))
    except BaseException as exc:
        if not (out/'status.json').exists():
            _write(out/'status.json', dict(arm=args.arm, complete=False, processed_requests=0,
                   expected_requests=30, error=f'{type(exc).__name__}: {exc}'))
        raise


if __name__ == '__main__':
    main()
