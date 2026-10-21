#!/usr/bin/env python3
"""Run only the sealed offline requirement-evidence study, never public data."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from src.task3.dataset import write_json
from src.task3.feedback_prompt import verify_seal,sha
from src.task3.requirement_evidence import run_candidate
from src.task3.schema import Task3Record

ROOT=REPO/'outputs/task3/requirement-evidence-20261021'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args()
    frozen=verify_seal(ROOT/'study-freeze.json')
    records=[Task3Record(**r)for r in json.loads((ROOT/'model-inputs.private.json').read_text())]
    selection=json.loads((ROOT/'frozen-selection.private.json').read_text())['records']
    if len({r.sample_id for r in records})!=len(records) or {r.sample_id for r in records}!={r['sample_id']for r in selection}:raise ValueError('IDs mismatch')
    for r in records:
        if r.source=='public' or r.gold_taxonomy is not None or r.gold_feedback is not None:
            raise ValueError('public/gold/teacher input denied')
        if r.split not in ('raw-training-archive-development','synthetic-train-derived-confirmation'):
            raise ValueError('input not in frozen offline origin allowlist')
    resolved=json.loads((ROOT/'resolved-config.json').read_text());cfg=resolved['r15'];candidate_cfg=resolved['candidate']
    if candidate_cfg.get('public_inference') is not False or candidate_cfg.get('training') is not False or cfg.get('adapter'):
        raise ValueError('offline pinned base only')
    if cfg['model_id']!=candidate_cfg['model_id'] or cfg['revision']!=candidate_cfg['revision']:raise ValueError('model mismatch')
    if args.verify_only:
        print(json.dumps({'verified':True,'records':len(records),'freeze_sha256':sha(ROOT/'study-freeze.json')}));return 0
    if (ROOT/'run.json').exists():raise ValueError('one-pass study already completed; do not overwrite')
    # Exclusive marker prevents an accidental concurrent second run. A crash is an
    # incomplete run to audit, never a reason to delete journals/select outputs.
    marker=ROOT/'inference-started.json'
    with marker.open('x')as stream:
        json.dump({'freeze_sha256':sha(ROOT/'study-freeze.json'),'pid':os.getpid()},stream)
    os.environ['HF_HOME']=str(REPO/'outputs/task3/hf-cache')
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    from src.task3.inference import HFBackend,load_tokenizer,tokenizer_metadata
    from src.task3.round15_runner import run_records
    tokenizer=load_tokenizer(cfg)
    meta=tokenizer_metadata(tokenizer)
    if meta['mock'] or meta['chat_template_sha256']!='cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f':raise ValueError('real pinned tokenizer required')
    backend=HFBackend(cfg,tokenizer)
    backend.model.generation_config.max_time=float(cfg['generation_max_time_s'])
    write_json(ROOT/'runtime-before.json',{'config':resolved,'tokenizer':meta,'runtime':backend.runtime_metadata(),'python':sys.version,'packages':subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True).splitlines(),'replay':False,'programs_compiled':False,'programs_executed':False})
    # Native production implementation: no adapters/patches/prompt overrides.
    baseline=run_records(records,backend,cfg,ROOT/'R15',examples=())
    base_by={p['sample_id']:p['output']for p in baseline['predictions']}
    write_json(ROOT/'R15/run.json',{'config':cfg,'records':len(records),'completed':len(base_by),'errors':baseline['errors'],'identity':baseline['identity'],'runtime':backend.runtime_metadata(),'tokenizer':meta,'replay':False})
    verify_seal(ROOT/'study-freeze.json')
    out=ROOT/'candidate';out.mkdir(exist_ok=True)
    calls=out/'attempts.jsonl';results=[]
    def capture(row):
        row={**row,'prompt_sha256':__import__('hashlib').sha256(json.dumps(row['prompt_messages'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()}
        with calls.open('a')as stream:
            stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush();os.fsync(stream.fileno())
    for r in records:
        result=run_candidate(r,backend,{**cfg,'diagnosis_max_new_tokens':candidate_cfg['diagnosis_max_new_tokens']},base_by.get(r.sample_id),capture=capture)
        results.append(result);write_json(out/'results.private.json',results)
        print(json.dumps({'candidate_completed':len(results),'total':len(records),'fallback':result['fallback_used'],'uncertain':result['uncertain']}),flush=True)
    finals=[{'sample_id':r['sample_id'],'status':r['status'],'output':r['output']}for r in results]
    write_json(out/'predictions.json',finals)
    verify_seal(ROOT/'study-freeze.json')
    write_json(ROOT/'run.json',{'requested':len(records),'R15_completed':len(base_by),'candidate_completed':sum(r['output']is not None for r in results),'candidate_fallback_ids':[r['sample_id']for r in results if r['fallback_used']],'candidate_uncertain_ids':[r['sample_id']for r in results if r['uncertain']],'model_config':resolved,'runtime':backend.runtime_metadata(),'tokenizer':meta,'replay':False,'freeze_sha256':sha(ROOT/'study-freeze.json'),'student_programs_compiled':False,'student_programs_executed':False})
    return 0

if __name__=='__main__':raise SystemExit(main())
