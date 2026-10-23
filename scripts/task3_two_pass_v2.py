#!/usr/bin/env python3
"""Freeze C/D ablations and conditional E; no public inference or model retries."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.task3 import two_pass_v2 as v2
from src.task3.dataset import write_json
from src.task3.level_blind import read,sha,digest

OUT=ROOT/'outputs/task3/two-pass-v2-20261023';OLD=ROOT/'outputs/task3/two-pass-20261023'
FILES=['src/task3/two_pass_v2.py','scripts/task3_two_pass_v2.py','configs/task3/two_pass_v2_20261023.json',
       'scripts/task3_two_pass_v2_audit.py',
       'src/task3/two_pass.py','src/task3/inference.py','src/task3/grounded.py','src/task3/schema.py',
       'src/task3/level_blind.py','src/task3/dataset.py','src/task3/grounded_metrics.py','src/synth/taxonomy.py','src/synth/feedback.py']


def require(condition,message):
    if not condition:raise ValueError(message)


def freeze():
    d=OUT/'frozen'
    if d.exists():raise ValueError('one exclusive v2 prompt pair only')
    require((OUT/'boundary-trace.private.json').exists(),'trace first')
    from scripts.task3_two_pass import verify as verify_v1
    old=verify_v1();config=read(ROOT/'configs/task3/two_pass_v2_20261023.json')
    for k in ['model_id','revision','load_in_4bit','seed','do_sample','max_new_tokens','context_limit','generation_max_time_s']:
        require(config[k]==old['config'][k],k)
    labels=read(ROOT/'data/raw/sample_dataset/label_space.json')
    require(labels['taxonomy_error']==list(v2.LABEL_SPACE),'official labels')
    require(sha(OUT/'units.private.json')==sha(OLD/'units.private.json'),'old16 source mismatch')
    for name,h in read(OUT/'review/source-seal.json')['hashes'].items():require(sha(OUT/'review'/name)==h,name)
    d.mkdir();write_json(d/'level-definitions.json',labels['feedback_level'])
    for n in FILES:
        p=d/'code'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/n).read_bytes())
    inputs=[OUT/'units.private.json',OUT/'control.private.json',OUT/'selection.private.json',OUT/'control-runtime.private.json',
            OUT/'review/source-seal.json',OUT/'boundary-trace.private.json',OLD/'B/results.private.json',OLD/'B/predictions.json',
            ROOT/'outputs/task3/eval-freeze-v2-20261021/frozen/train-eligible.private.json',
            ROOT/'outputs/task3/eval-freeze-v2-20261021/frozen/reference.private.json']
    m={'version':v2.VERSION,'initial_HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
       'config':config,'tokenizer':old['tokenizer'],'code_sha256':{n:sha(ROOT/n)for n in FILES},
       'input_sha256':{str(p.relative_to(ROOT)):sha(p)for p in inputs},'definitions_sha256':sha(d/'level-definitions.json'),
       'prompt_sha256':{'stage1_v2':digest(v2.TAXONOMY_SYSTEM),'stage2_v2':digest([v2.FEEDBACK_SYSTEM,v2.LEVEL_GUIDANCE]),
                        'stage2_v1':digest([v2.v1.FEEDBACK_SYSTEM,v2.v1.LEVEL_GUIDANCE])}}
    write_json(d/'freeze.json',m);(d/'freeze.sha256').write_text(sha(d/'freeze.json')+'\n')
    print(json.dumps({'frozen':True,'SHA256':sha(d/'freeze.json'),'prompts':m['prompt_sha256']}))


def verify():
    d=OUT/'frozen';m=read(d/'freeze.json')
    require(sha(d/'freeze.json')==(d/'freeze.sha256').read_text().strip(),'freeze seal drift')
    for n,h in m['code_sha256'].items():require(sha(ROOT/n)==h,n)
    for n,h in m['input_sha256'].items():require(sha(ROOT/n)==h,n)
    require(sha(d/'level-definitions.json')==m['definitions_sha256'],'official definitions')
    for n,h in read(OUT/'review/source-seal.json')['hashes'].items():require(sha(OUT/'review'/n)==h,n)
    return m


def authorize_E():
    from scripts.task3_two_pass_v2_audit import verify_packet
    verify_packet('CD')
    gate=read(OUT/'E-gate.private.json');require(gate['allow_E'],'E stopped by preregistered offline gate')
    require(gate['freeze_sha256']==sha(OUT/'frozen/freeze.json'),'gate freeze binding')
    for n,h in gate['review_sha256'].items():require(sha(OUT/n)==h,n)
    for n,h in read(OUT/'review/paired-seal-CD.json').items():require(sha(OUT/'review'/n)==h,n)


def run(phase):
    m=verify();summary_path=OUT/('CD-run.private.json' if phase=='run-CD' else 'E-run.private.json')
    require(not summary_path.exists(),'completed run cannot be resampled')
    if phase=='run-E':authorize_E()
    config=m['config'];os.environ.update(HF_HOME=str(ROOT/'outputs/task3/hf-cache'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    free=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip().splitlines()
    require(len(free)==1 and int(free[0])>=config['minimum_free_gpu_mib'],'insufficient free GPU')
    from src.task3.inference import load_tokenizer,tokenizer_metadata,HFBackend
    tokenizer=load_tokenizer(config);require(tokenizer_metadata(tokenizer)==m['tokenizer'],'tokenizer drift')
    backend=HFBackend(config,tokenizer);backend.model.generation_config.max_time=config['generation_max_time_s']
    units=read(OUT/'units.private.json');definitions=read(OUT/'frozen/level-definitions.json')
    frozen={r['sample_id']:r['stage1']for r in read(OLD/'B/results.private.json')}
    summary={'freeze_sha256':sha(OUT/'frozen/freeze.json'),'arms':{},'model_loads':1,'replay':phase=='run-CD'}
    for arm in ['C','D'] if phase=='run-CD' else ['E']:
        rows=v2.run_arm(units,backend,config,OUT/arm,definitions,arm,frozen if arm=='C' else None)
        p=OUT/arm/'reservations.jsonl';reservations=[json.loads(x)for x in p.read_text().splitlines()] if p.exists() else []
        counts={sid:sum(r['sample_id']==sid for r in reservations)for sid in [u['sample_id']for u in units]}
        require(max(counts.values(),default=0)<= (1 if arm=='C' else 2),'model call cap')
        summary['arms'][arm]={'IDs':len(rows),'completed':sum(r['status']=='resolved'for r in rows),
            'unresolved':sum(r['status']!='resolved'for r in rows),'inconsistency':sum(r['inconsistency']for r in rows),
            'fallback':0,'calls':len(reservations),'maximum_calls_per_ID':max(counts.values(),default=0)}
    summary['runtime']=backend.runtime_metadata();verify();write_json(summary_path,summary)
    write_json(OUT/'requested-levels.private.json',{u['sample_id']:u['level']for u in units})
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['freeze','verify','run-CD','run-E']);a=p.parse_args()
    if a.phase=='freeze':freeze()
    elif a.phase=='verify':verify();print(json.dumps({'verified':True}))
    else:run(a.phase)
