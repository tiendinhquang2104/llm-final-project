#!/usr/bin/env python3
"""Gated local preflight. No public inference or automatic evaluation expansion."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.task3 import compact as c,compact_runner as runner,grounded as g
from src.task3.dataset import write_json
from src.task3.grounded_runner import Journal
from src.task3.level_blind import read,sha,digest

OUT=ROOT/'outputs/task3/compact-20261023'
CONFIG=ROOT/'configs/task3/compact_20261023.json'
FILES=['src/task3/compact.py','src/task3/compact_runner.py','scripts/task3_compact.py',
       'configs/task3/compact_20261023.json','docs/task3_compact_rulebook.md',
       'src/task3/grounded.py','src/task3/grounded_runner.py','src/task3/inference.py',
       'src/task3/diagnosis_contract_v1.py','src/task3/round15.py','src/task3/round15_disclosure.py']


def environment():
    os.environ['HF_HOME']=str(ROOT/'outputs/task3/hf-cache')
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'


def gate_p1():
    runs=[p for p in OUT.glob('p1-v*/run.private.json')]
    return any(read(p)['diagnosis_completed']==8 for p in runs)


def freeze(phase,version):
    g.require(phase in {'p1','p2'},'preflight phases only')
    if phase=='p2':g.require(gate_p1(),'P1 gate failed: do not expand')
    if version==2:g.require((OUT/'p1-v1/run.private.json').exists(),'v1 must finish first')
    cfg=read(CONFIG);units=read(OUT/(phase+'-selection.private.json'))
    g.require(len(units)==(8 if phase=='p1' else 20),'exact selected ID count')
    d=OUT/f'{phase}-v{version}';g.require(not d.exists(),'exclusive freeze exists')
    d.mkdir();(d/'code').mkdir()
    for name in FILES:
        target=d/'code'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
    write_json(d/'units.private.json',units)
    m=dict(phase=phase,version=version,config=cfg,units_sha256=sha(d/'units.private.json'),
        implementation_sha256={name:sha(ROOT/name)for name in FILES},
        prompt_sha256=digest([c.SYSTEM if version==1 else c.SYSTEM_V2,c.VERIFY_SYSTEM,runner.FEEDBACK_SYSTEM,runner.GUARD_SYSTEM,runner.RESCUE_SUPPORT]),
        head_at_freeze=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        evidence='compiler executable present but no isolated compiler sandbox; unavailable, tests not_run',
        exposure='development; old60 already exposed; no new evaluation claim',
        oracle='offline experiment only; production entrypoint rejects oracle provenance')
    write_json(d/'freeze.json',m);(d/'freeze.sha256').write_text(sha(d/'freeze.json')+'\n')
    print(json.dumps({'frozen':str(d),'IDs':len(units),'prompt_sha256':m['prompt_sha256']}))


def verify(d):
    m=read(d/'freeze.json');g.require(sha(d/'freeze.json')==(d/'freeze.sha256').read_text().strip(),'freeze changed')
    g.require(sha(d/'units.private.json')==m['units_sha256'],'source changed')
    for name,h in m['implementation_sha256'].items():g.require(sha(ROOT/name)==h,'code/config drift:'+name)
    return m,read(d/'units.private.json')


def backend(config):
    environment()
    free=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip().splitlines()
    g.require(len(free)==1 and int(free[0])>=config['minimum_free_gpu_mib'],'insufficient free GPU; do not interfere with other process')
    from src.task3.inference import HFBackend,load_tokenizer
    b=HFBackend(config,load_tokenizer(config));b.model.generation_config.max_time=config['generation_max_time_s']
    return b


def run(phase,version):
    d=OUT/f'{phase}-v{version}';m,units=verify(d)
    if phase=='p2':g.require(gate_p1(),'P1 gate not passed')
    g.require(not (d/'run.private.json').exists(),'run complete; no resampling')
    b=backend(m['config']);write_json(d/'runtime-before.private.json',b.runtime_metadata())
    j=Journal(d/'candidate',b,m['config'],sha(d/'freeze.json'));results=[]
    for u in units:
        result=runner.run_unit(u,j,version);results.append(result);write_json(d/'results.private.json',results)
        print(json.dumps({'processed':len(results),'total':len(units),'diagnosis':result['diagnosis']['status'],
            'grounded':result['grounded']['status'],'final':result['final']['status'],'origin':result['final']['origin']}),flush=True)
    verify(d)
    summary=dict(diagnosis_completed=sum(r['diagnosis']['publishable']for r in results),
        grounded_completed=sum(r['grounded']['status']=='resolved'for r in results),
        final_completed=sum(r['final']['status']=='resolved'for r in results),
        rescue_completed=sum(r['final']['status']=='resolved'and r['final']['origin']=='rescue'for r in results),
        unresolved=[r['sample_id']for r in results if r['final']['status']!='resolved'],
        IDs=len(units),runtime=b.runtime_metadata(),freeze_sha256=sha(d/'freeze.json'),replay=False)
    write_json(d/'run.private.json',summary);print(json.dumps(summary),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['freeze','run','verify'])
    p.add_argument('--phase',choices=['p1','p2'],default='p1');p.add_argument('--version',choices=[1,2],type=int,default=1)
    a=p.parse_args()
    if a.action=='freeze':freeze(a.phase,a.version)
    elif a.action=='run':run(a.phase,a.version)
    else:m,u=verify(OUT/f'{a.phase}-v{a.version}');print(json.dumps({'verified':True,'IDs':len(u)}))
