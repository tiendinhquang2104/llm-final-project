#!/usr/bin/env python3
"""Only the sealed witness-mechanism study; no oracle/scorer import or renderer."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from src.task3.dataset import write_json
from src.task3.feedback_prompt import verify_seal,sha
from src.task3.schema import Task3Record
from src.task3.witness_diagnosis import run
ROOT=REPO/'outputs/task3/witness-behavior-20261022'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--verify-only',action='store_true');args=p.parse_args()
    verify_seal(ROOT/'pre-inference-freeze.json')
    records=[Task3Record(**r)for r in json.loads((ROOT/'model-inputs.private.json').read_text())]
    if len(records)!=48 or len({r.sample_id for r in records})!=48:raise ValueError('48 unique frozen IDs required')
    if any(r.source!='synthetic'or r.gold_taxonomy is not None or r.gold_feedback is not None or r.split not in ('witness-mechanism-development','witness-mechanism-evaluation')for r in records):raise ValueError('offline projections only')
    cfgs=json.loads((ROOT/'resolved-config.json').read_text());cfg=cfgs['R15'];candidate=cfgs['candidate']
    if cfg.get('adapter')or candidate['public_inference']or candidate['training']:raise ValueError('base Qwen offline only')
    if args.verify_only:print(json.dumps({'verified':True,'IDs':len(records),'freeze_sha256':sha(ROOT/'pre-inference-freeze.json')}));return 0
    with (ROOT/'model-started.json').open('x')as f:json.dump({'freeze_sha256':sha(ROOT/'pre-inference-freeze.json')},f)
    os.environ['HF_HOME']=str(REPO/'outputs/task3/hf-cache');os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    from src.task3.inference import HFBackend,load_tokenizer,tokenizer_metadata
    from src.task3.round15_runner import run_records
    tokenizer=load_tokenizer(cfg);metadata=tokenizer_metadata(tokenizer)
    if metadata['mock']or metadata['chat_template_sha256']!='cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f':raise ValueError('real pinned tokenizer required')
    backend=HFBackend(cfg,tokenizer);backend.model.generation_config.max_time=cfg['generation_max_time_s']
    write_json(ROOT/'runtime-before.json',{'runtime':backend.runtime_metadata(),'tokenizer':metadata,'config':cfgs,'packages':subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True).splitlines(),'replay':False})
    base=run_records(records,backend,cfg,ROOT/'R15',examples=())
    write_json(ROOT/'R15/run.json',{'config':cfg,'identity':base['identity'],'requested':48,'completed':len(base['predictions']),'errors':base['errors'],'tokenizer':metadata,'runtime':backend.runtime_metadata(),'replay':False})
    verify_seal(ROOT/'pre-inference-freeze.json')
    out=ROOT/'diagnosis';out.mkdir(exist_ok=True);results=[]
    def capture(row):
        with (out/'attempts.jsonl').open('a')as f:f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
    for record in records:
        result=run(record,backend,{**cfg,'max_new_tokens':candidate['candidate_max_new_tokens']},capture=capture)
        results.append(result);write_json(out/'results.private.json',results)
        print(json.dumps({'diagnosis_completed':len(results),'total':48,'status':result['status']}),flush=True)
    verify_seal(ROOT/'pre-inference-freeze.json')
    write_json(ROOT/'run.json',{'requested':48,'R15_completed':len(base['predictions']),'diagnosis_ids':len(results),'diagnosis_status_counts':{s:sum(r['status']==s for r in results)for s in ['defect','no_defect_in_scope','uncertain','schema_error']},'runtime':backend.runtime_metadata(),'tokenizer':metadata,'config':cfgs,'replay':False,'renderer_run':False,'freeze_sha256':sha(ROOT/'pre-inference-freeze.json')})
    return 0

if __name__=='__main__':raise SystemExit(main())
