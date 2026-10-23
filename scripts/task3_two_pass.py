#!/usr/bin/env python3
"""Frozen sequential two-prompt development experiment, never public inference."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.task3 import two_pass as t
from src.task3.dataset import write_json
from src.task3.level_blind import read,sha,digest
from src.utils.config import load_config

OUT=ROOT/'outputs/task3/two-pass-20261023'
FILES=['src/task3/two_pass.py','scripts/task3_two_pass.py','configs/task3/two_pass_20261023.json',
       'src/task3/inference.py','src/task3/grounded.py','src/task3/schema.py','src/task3/submission.py',
       'src/task3/round15.py','src/task3/round15_runner.py','configs/task3/r15_selected.yaml',
       'configs/task3/r15_zero_shot.yaml','configs/task3/r15_common.yaml']


def freeze():
    for n,h in read(OUT/'selection-seal.json').items():
        if sha(OUT/n)!=h:raise ValueError('selection drift:'+n)
    d=OUT/'frozen'
    if d.exists():raise ValueError('exclusive freeze exists; one prompt pair only')
    config=read(ROOT/'configs/task3/two_pass_20261023.json');control=load_config(ROOT/'configs/task3/r15_selected.yaml')
    for k in ['model_id','revision','load_in_4bit','seed','do_sample','max_new_tokens','context_limit','generation_max_time_s']:
        if config[k]!=control[k]:raise ValueError('R15 runtime mismatch:'+k)
    labels=read(ROOT/'data/raw/sample_dataset/label_space.json')
    if labels['taxonomy_error']!=list(t.LABEL_SPACE):raise ValueError('official label mismatch')
    d.mkdir();write_json(d/'level-definitions.json',labels['feedback_level'])
    for name in FILES:
        p=d/'code'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/name).read_bytes())
    manifest=dict(version=t.VERSION,initial_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        config=config,R15_config=control,source_sha256=sha(OUT/'units.private.json'),control_sha256=sha(OUT/'control.private.json'),
        selection_seal_sha256=sha(OUT/'selection-seal.json'),level_definitions_sha256=sha(d/'level-definitions.json'),
        code_sha256={n:sha(ROOT/n)for n in FILES},prompt_sha256=digest([t.TAXONOMY_SYSTEM,t.FEEDBACK_SYSTEM,t.LEVEL_GUIDANCE]),
        tokenizer=read(ROOT/'outputs/task3/grounded-20261023/evaluation/freeze.json')['tokenizer'],
        policy='two calls maximum per ID; no retries/semantic gate; sequential; one frozen pair; prior-exposed development; no public')
    write_json(d/'freeze.json',manifest);(d/'freeze.sha256').write_text(sha(d/'freeze.json')+'\n')
    print(json.dumps({'IDs':len(read(OUT/'units.private.json')),'freeze_sha256':sha(d/'freeze.json'),'prompt_sha256':manifest['prompt_sha256']}))


def verify():
    d=OUT/'frozen';m=read(d/'freeze.json')
    if sha(d/'freeze.json')!=(d/'freeze.sha256').read_text().strip():raise ValueError('freeze seal drift')
    for p,key in [(OUT/'units.private.json','source_sha256'),(OUT/'control.private.json','control_sha256'),
                  (OUT/'selection-seal.json','selection_seal_sha256'),(d/'level-definitions.json','level_definitions_sha256')]:
        if sha(p)!=m[key]:raise ValueError('frozen input drift:'+str(p))
    for n,h in read(OUT/'selection-seal.json').items():
        if sha(OUT/n)!=h:raise ValueError('selection artifact drift:'+n)
    for n,h in m['code_sha256'].items():
        if sha(ROOT/n)!=h:raise ValueError('runtime drift:'+n)
    return m


def run():
    m=verify()
    if (OUT/'run.private.json').exists():raise ValueError('run complete, no resampling')
    config=m['config'];os.environ['HF_HOME']=str(ROOT/'outputs/task3/hf-cache')
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    free=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip().splitlines()
    if len(free)!=1 or int(free[0])<config['minimum_free_gpu_mib']:raise ValueError('insufficient free GPU')
    from src.task3.inference import HFBackend,load_tokenizer,tokenizer_metadata
    tokenizer=load_tokenizer(config)
    if tokenizer_metadata(tokenizer)!=m['tokenizer']:raise ValueError('tokenizer drift')
    backend=HFBackend(config,tokenizer);backend.model.generation_config.max_time=config['generation_max_time_s']
    write_json(OUT/'runtime-before.private.json',backend.runtime_metadata())
    results=t.run_units(read(OUT/'units.private.json'),backend,config,OUT/'B',read(OUT/'frozen/level-definitions.json'))
    verify();completed=sum(r['status']=='resolved'for r in results)
    if completed<len(results):
        write_json(OUT/'development.hybrid.predictions.json',t.hybrid(results,read(OUT/'control.private.json')))
        write_json(OUT/'hybrid-origins.private.json',{r['sample_id']:'two_pass'if r['status']=='resolved'else'R15_whole_pair'for r in results})
    write_json(OUT/'requested-levels.private.json',{u['sample_id']:u['level']for u in read(OUT/'units.private.json')})
    path=OUT/'B/reservations.jsonl'
    reservations=[json.loads(x)for x in path.read_text().splitlines()]if path.exists()else[]
    counts={}
    for r in reservations:counts[r['sample_id']]=counts.get(r['sample_id'],0)+1
    if any(c>2 for c in counts.values()):raise ValueError('two-call cap broken')
    summary=dict(IDs=len(results),completed=completed,unresolved=len(results)-completed,
        R15_fallback=len(results)-completed,
        model_reservations=len(reservations),maximum_calls_per_ID=max(counts.values(),default=0),
        runtime=backend.runtime_metadata(),replay=False,freeze_sha256=sha(OUT/'frozen/freeze.json'))
    write_json(OUT/'run.private.json',summary);print(json.dumps(summary),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['freeze','verify','run']);a=p.parse_args()
    if a.phase=='freeze':freeze()
    elif a.phase=='run':run()
    else:verify();print(json.dumps({'verified':True}))
