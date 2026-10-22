#!/usr/bin/env python3
"""Sealed train-only Round23 inference. No oracle/scorer imports or renderer."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from src.task3.dataset import write_json
from src.task3.feedback_prompt import verify_seal,sha
from src.task3.schema import Task3Record
from src.task3.cpp_sandbox import CppSandbox
from src.task3.round23_runner import run_shared
ROOT=REPO/'outputs/task3/round23-20261022'


def validate_executable_binding(record,entry):
    jail=Path(entry['jail'])
    if hashlib.sha256(record.code.encode()).hexdigest()!=entry['source_sha256']:raise ValueError('record source differs from executable')
    if record.provenance.get('_task3_compile_check')!={'status':entry['compiler']['status'],'diagnostic':entry['compiler']['stderr']}:raise ValueError('compiler evidence mismatch')
    if sha(jail/'work/source.cpp')!=entry['source_sha256']:raise ValueError('source drift')
    if entry['compiler']['status']=='pass'and sha(jail/'work/program')!=entry['compiler']['binary_sha256']:raise ValueError('binary drift')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verify-only',action='store_true');args=parser.parse_args()
    verify_seal(ROOT/'pre-inference-freeze.json')
    records=[Task3Record(**r)for r in json.loads((ROOT/'model-inputs.private.json').read_text())]
    index=json.loads((ROOT/'execution-index.private.json').read_text());config=json.loads((ROOT/'resolved-config.json').read_text());cfg=config['R15'];candidate=config['candidate']
    if len(records)!=80 or len({r.sample_id for r in records})!=80 or set(index)!={r.sample_id for r in records}:raise ValueError('all80 IDs required')
    if any(r.source!='synthetic'or r.gold_taxonomy is not None or r.gold_feedback is not None for r in records):raise ValueError('only isolated synthetic train-statement projections')
    if cfg.get('adapter')or candidate['training']or candidate['public_inference']:raise ValueError('offline base-model inference only')
    for r in records:
        validate_executable_binding(r,index[r.sample_id])
    if args.verify_only:print(json.dumps({'verified':True,'IDs':80,'freeze_sha256':sha(ROOT/'pre-inference-freeze.json')}));return 0
    free_mib=int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip())
    if free_mib<candidate['minimum_free_gpu_mib']:
        state={'status':'waiting_for_gpu','free_gpu_mib':free_mib,'required_gpu_mib':candidate['minimum_free_gpu_mib'],'model_calls':0,'model_loaded':False}
        write_json(ROOT/'gpu-preflight.json',state);print(json.dumps(state));return 3
    with(ROOT/'model-started.json').open('x')as stream:json.dump({'freeze_sha256':sha(ROOT/'pre-inference-freeze.json')},stream)
    os.environ['HF_HOME']=str(REPO/'outputs/task3/hf-cache');os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    from src.task3.inference import HFBackend,load_tokenizer,tokenizer_metadata
    from src.task3.round15_runner import run_records
    tokenizer=load_tokenizer(cfg);metadata=tokenizer_metadata(tokenizer)
    if metadata['mock']or metadata['chat_template_sha256']!='cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f':raise ValueError('pinned real tokenizer required')
    backend=HFBackend(cfg,tokenizer);backend.model.generation_config.max_time=cfg['generation_max_time_s']
    write_json(ROOT/'runtime-before.json',{'runtime':backend.runtime_metadata(),'tokenizer':metadata,'config':config,'packages':subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True).splitlines(),'replay':False})
    baseline=run_records(records,backend,cfg,ROOT/'R15',examples=())
    write_json(ROOT/'R15/run.json',{'config':cfg,'identity':baseline['identity'],'requested':80,'completed':len(baseline['predictions']),'errors':baseline['errors'],'runtime':backend.runtime_metadata(),'tokenizer':metadata,'replay':False})
    verify_seal(ROOT/'pre-inference-freeze.json');sandbox=CppSandbox(Path(config['sandbox_root']));results=[]
    def capture(row):
        with(ROOT/'diagnosis-attempts.jsonl').open('a')as stream:stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush();os.fsync(stream.fileno())
    for record in records:
        entry=index[record.sample_id]
        def execute(witness):return sandbox.run(Path(entry['jail']),**witness)
        result=run_shared(record,entry['scope'],backend,{**cfg,'max_new_tokens':candidate['candidate_max_new_tokens']},execute,capture=capture)
        results.append(result);write_json(ROOT/'diagnosis-results.private.json',results)
        print(json.dumps({'completed':len(results),'IDs':80,'self':result['self']['status'],'execution':result['execution']['status']}),flush=True)
    verify_seal(ROOT/'pre-inference-freeze.json')
    write_json(ROOT/'run.json',{'requested':80,'R15_completed':len(baseline['predictions']),'diagnosis_ids':len(results),'runtime':backend.runtime_metadata(),'tokenizer':metadata,'config':config,'replay':False,'renderer_run':False,'freeze_sha256':sha(ROOT/'pre-inference-freeze.json')})
    return 0

if __name__=='__main__':raise SystemExit(main())
