#!/usr/bin/env python3
"""Sealed train-derived offline A/D inference; no public submission path."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src.task3.dataset import write_json
from src.task3.feedback_prompt import verify_seal, sha
from src.task3.level2_prompt import adapter, VERSION
from src.task3.schema import Task3Record

ROOT = REPO / 'outputs/task3/level2-diagnostic-20261021'
CONFIG = REPO / 'configs/task3/level2_diagnostic_20261021.json'


def offline_records(path):
    records = [Task3Record(**r) for r in json.loads(Path(path).read_text())]
    if not records or len({r.sample_id for r in records}) != len(records):
        raise ValueError('nonempty unique offline IDs required')
    for r in records:
        if (r.source == 'public' or r.gold_taxonomy is not None or r.gold_feedback is not None
                or r.split not in ('synthetic-train-derived-confirmation','exposed-offline-development')
                or int(r.target_feedback_level[6]) != 2):
            raise ValueError('only whitelisted offline Level2 inputs without gold are allowed')
    return records


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--phase', choices=['calibration','confirmation'], required=True)
    ap.add_argument('--guard', choices=['old','new'], default='old')
    args = ap.parse_args()
    verify_seal(ROOT / 'prompt-freeze.json')
    if args.guard == 'new':
        verify_seal(ROOT / 'guard-freeze.json')
    if args.phase == 'confirmation':
        verify_seal(ROOT / 'confirmation-freeze.json')
    cfg = json.loads(CONFIG.read_text())
    if cfg.get('adapter') or cfg.get('public_inference') is not False:
        raise ValueError('base model offline inference only')
    path = ROOT / f'{args.phase}-inputs.private.json'
    records = offline_records(path)
    from src.task3.inference import HFBackend, load_tokenizer, tokenizer_metadata
    from src.task3.round15_runner import run_records
    from src.task3.submission import validate_submission
    os.environ.setdefault('HF_HOME', str(REPO / 'outputs/task3/hf-cache'))
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    tokenizer = load_tokenizer(cfg)
    metadata = tokenizer_metadata(tokenizer)
    if metadata['chat_template_sha256'] != 'cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f':
        raise ValueError('R15 tokenizer template changed')
    backend = HFBackend(cfg, tokenizer)
    backend.model.generation_config.max_time = float(cfg['generation_max_time_s'])
    for arm in ('A','D'):
        out = ROOT / args.phase / args.guard / arm
        if (out / 'run.json').exists():
            raise ValueError('completed one-pass arm already exists')
        active = {**cfg, 'offline_arm':arm, 'offline_guard':args.guard,
                  'experiment_version':VERSION, 'prompt_variant':'zero_shot',
                  'input_sha256':sha(path), 'prompt_freeze_sha256':sha(ROOT/'prompt-freeze.json')}
        if args.guard == 'new':
            active['guard_freeze_sha256'] = sha(ROOT/'guard-freeze.json')
        with adapter(arm, guard=args.guard):
            result = run_records(records, backend, active, out)
        verify_seal(ROOT/'prompt-freeze.json')
        if args.guard == 'new':verify_seal(ROOT/'guard-freeze.json')
        if args.phase == 'confirmation':verify_seal(ROOT/'confirmation-freeze.json')
        validation = validate_submission(out/'predictions.json', {r.sample_id:r.target_feedback_level for r in records}) if not result['errors'] else {'status':'INCOMPLETE'}
        write_json(out/'run.json', {'arm':arm,'guard':args.guard,'phase':args.phase,
            'config':active,'records':len(records),'completed':len(result['predictions']),
            'errors':result['errors'],'identity':result['identity'],'runtime':backend.runtime_metadata(),
            'tokenizer':metadata,'validation':validation,'programs_executed':False,
            'attempts_sha256':sha(out/'attempts.jsonl'),
            'output_sha256':sha(out/'predictions.json') if (out/'predictions.json').exists() else None})
        print(json.dumps({'phase':args.phase,'guard':args.guard,'arm_done':arm,'completed':len(result['predictions'])}),flush=True)
    return 0

if __name__ == '__main__':raise SystemExit(main())
