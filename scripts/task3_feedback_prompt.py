#!/usr/bin/env python3
"""Run only sealed offline Task3 inputs; no public inference entry point."""
from __future__ import annotations
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from src.task3.dataset import write_json
from src.task3.feedback_prompt import verify_seal,sha,prompt_adapter,VERSION
from src.task3.schema import Task3Record
from src.task3.inference import HFBackend,load_tokenizer,tokenizer_metadata
from src.task3.round15_runner import run_records
from src.task3.submission import validate_submission

ROOT=REPO/'outputs/task3/feedback-prompt-20261021'


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--phase',required=True,choices=['calibration','fresh'])
    args=ap.parse_args()
    frozen=verify_seal(ROOT/'prompt-freeze.json')
    cfg=json.loads((REPO/'configs/task3/feedback_prompt_20261021.json').read_text())
    if cfg.get('adapter') or cfg.get('public_inference') is not False:raise ValueError('offline base model only')
    if args.phase=='calibration':
        arms=['A','B','C'];input_path=ROOT/'calibration-inputs.private.json'
    else:
        verify_seal(ROOT/'fresh-freeze.json')
        selection=json.loads((ROOT/'selection.json').read_text())
        verify_seal(ROOT/'selection-freeze.json')
        if selection['candidate'] not in ('B','C'):raise ValueError('locked B/C selection required')
        arms=['A',selection['candidate']];input_path=ROOT/'fresh-inputs.private.json'
    records=[Task3Record(**r) for r in json.loads(input_path.read_text())]
    if any(r.source=='public' or r.gold_taxonomy is not None or r.gold_feedback is not None for r in records):
        raise ValueError('no public/gold/teacher inference inputs')
    bank=json.loads((ROOT/'bank.private.json').read_text())
    os.environ.setdefault('HF_HOME',str(REPO/'outputs/task3/hf-cache'))
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    tokenizer=load_tokenizer(cfg)
    if tokenizer_metadata(tokenizer)['chat_template_sha256']!='cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f':
        raise ValueError('R15 chat template mismatch')
    backend=HFBackend(cfg,tokenizer)
    backend.model.generation_config.max_time=float(cfg['generation_max_time_s'])
    for arm in arms:
        out=ROOT/args.phase/arm
        if (out/'run.json').exists():raise ValueError('completed one-pass arm already exists')
        active={**cfg,'offline_arm':arm,'prompt_variant':'few_shot' if arm=='C' else 'zero_shot',
            'few_shot_k':2 if arm=='C' else 0,'experiment_version':VERSION,
            'prompt_freeze_sha256':sha(ROOT/'prompt-freeze.json'),'input_sha256':sha(input_path)}
        with prompt_adapter(arm):result=run_records(records,backend,active,out,examples=bank if arm=='C' else ())
        verify_seal(ROOT/'prompt-freeze.json')
        if args.phase=='fresh':verify_seal(ROOT/'fresh-freeze.json');verify_seal(ROOT/'selection-freeze.json')
        validation=validate_submission(out/'predictions.json',{r.sample_id:r.target_feedback_level for r in records}) if len(result['predictions'])==len(records) else {'status':'INCOMPLETE'}
        write_json(out/'run.json',{'phase':args.phase,'arm':arm,'config':active,
            'records':len(records),'completed':len(result['predictions']),'errors':result['errors'],
            'identity':result['identity'],'runtime':backend.runtime_metadata(),'tokenizer':tokenizer_metadata(tokenizer),
            'output_sha256':sha(out/'predictions.json') if (out/'predictions.json').exists() else None,
            'attempts_sha256':sha(out/'attempts.jsonl'),'validation':validation,'programs_executed':False})
        print(json.dumps({'arm_done':arm,'phase':args.phase,'completed':len(result['predictions'])}),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
