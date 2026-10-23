#!/usr/bin/env python3
"""Freeze and run local paired C0/C1/C2; never trains or reads public attempts."""
from __future__ import annotations
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
import hashlib

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.task3 import grounded as g
from src.task3.dataset import write_json
from src.task3.level_blind import digest,sha,read
from src.task3.schema import Task3Record
from src.utils.config import load_config
from task3_grounded_inventory import DEFAULT,PARENT

FILES=['src/task3/grounded.py','src/task3/grounded_runner.py','scripts/task3_grounded_experiment.py',
       'configs/task3/grounded_20261023.json','docs/task3_grounded_rulebook.md',
       'src/task3/inference.py','src/task3/diagnosis_contract_v1.py','src/task3/round15.py',
       'src/task3/round15_runner.py','src/task3/round15_disclosure.py',
       'configs/task3/r15_selected.yaml','configs/task3/r15_zero_shot.yaml','configs/task3/r15_common.yaml']


def environment():
    os.environ['HF_HOME']=str(ROOT/'outputs/task3/hf-cache')
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'


def verify_selection(out):
    for name,h in read(out/'selection-seal.json').items():g.require(sha(out/name)==h,'selection hash drift: '+name)
    selected=read(out/'selection.private.json')
    g.require(sha(PARENT/'seal.json')==selected['parent_sha256'],'parent seal drift')
    seal=read(PARENT/'seal.json')
    for name,h in seal['hashes'].items():g.require(sha(PARENT/name)==h,'frozen parent artifact drift: '+name)
    manifest=read(ROOT/'reports/task3/TASK3_EVAL_V2_FREEZE_20261021.json')
    g.require(sha(ROOT/'reports/task3/TASK3_EVAL_V2_FREEZE_20261021.json')==selected['parent_manifest_sha256'],'parent manifest drift')
    g.require(sha(ROOT/'generate-dataset_v2.zip')==manifest['archive_sha256'],'archive bytes changed')
    with zipfile.ZipFile(ROOT/'generate-dataset_v2.zip') as archive:
        for name,h in manifest['archive_members_sha256'].items():
            g.require(hashlib.sha256(archive.read(name)).hexdigest()==h,'archive member drift: '+name)
        # Resolve selected source identity using archive metadata only, not source reviews/gold.
        samples=json.loads(archive.read('generate-dataset/task3_feedback.json'))['samples']
        members={s['sample_id']:'generate-dataset/'+s['input']['code_file'] for s in samples}
        inputs={r['sample_id']:r['task']['student_code']for r in read(PARENT/'model-inputs.private.json') if r['kind']=='primary'}
        inputs.update({r['sample_id']:r['code']for r in read(PARENT/'train-eligible.private.json')})
        expected={r['sample_id']:r['source_sha256']for r in manifest['evaluation_selection']+selected['development']}
        for sid,code in inputs.items():
            raw=archive.read(members[sid]);g.require(hashlib.sha256(raw).hexdigest()==expected[sid],'selected raw source drift')
            decoded=None
            for enc in ['utf-8-sig','cp1258','cp1252','latin-1']:
                try:decoded=raw.decode(enc);break
                except UnicodeDecodeError:pass
            g.require(decoded==code,'selected decoded source drift')
    return selected


def units_for(split,out):
    selected=verify_selection(out)
    if split=='development':
        rows=read(PARENT/'train-eligible.private.json');ids={x['sample_id']for x in selected['development']}
        units=[]
        for r in rows:
            g.require(r['sample_id'] in ids,'development selection drift')
            level=int(r['original_level'][6]) if isinstance(r['original_level'],str) else r['original_level']
            units.append(dict(sample_id=r['sample_id'],request_id=r['sample_id']+'@development',level=level,family=r['family'],
                task=g.task_payload(dict(statement=r['statement'],exam_type=r['exam_type'],problems=r['problems'],
                    grading_policy=r['grading_policy'],code=r['code'],compiler={'status':'unavailable','diagnostic':''},
                    tests={'status':'not_run','cases':[]}))))
        return units
    rows=[r for r in read(PARENT/'model-inputs.private.json')if r['kind']=='primary']
    g.require([r['request_id']for r in rows]==[r['request_id']for r in selected['evaluation']],'evaluation selection drift')
    with zipfile.ZipFile(ROOT/'generate-dataset_v2.zip') as archive:
        exams={e['exam_id']:e for e in json.loads(archive.read('generate-dataset/exams.json'))['exams']}
        samples=json.loads(archive.read('generate-dataset/task3_feedback.json'))['samples']
        exam_types={s['sample_id']:exams[s['input']['exam_id']]['exam_type']for s in samples}
    units=[]
    for r,bound in zip(rows,selected['evaluation']):
        t=r['task']
        g.require(__import__('hashlib').sha256(t['student_code'].encode()).hexdigest()==bound['source_text_sha256'],'evaluation source drift')
        compiler=dict(t['compiler_evidence']);compiler.setdefault('diagnostic','')
        if compiler['status']=='unknown':compiler['status']='unavailable'
        units.append(dict(sample_id=r['sample_id'],request_id=r['request_id'],level=r['requested_level'],
             family='-'.join(r['sample_id'].split('-')[:-1]),task=g.task_payload(dict(statement=t['statement'],
             exam_type=exam_types[r['sample_id']],problems=t['problems'],
             grading_policy=t['grading_policy'],code=t['student_code'],compiler=compiler,tests={'status':'not_run','cases':[]}))))
    return units


def freeze(out,split):
    verify_selection(out)
    destination=out/split;g.require(not destination.exists(),'split freeze already exists')
    units=units_for(split,out);cfg=read(ROOT/'configs/task3/grounded_20261023.json')
    c0=load_config(ROOT/'configs/task3/r15_selected.yaml')
    environment()
    from src.task3.inference import load_tokenizer,tokenizer_metadata
    from src.task3.round15 import fitted_messages
    tok=load_tokenizer(cfg);metadata=tokenizer_metadata(tok)
    budgets=[]
    for u in units:
        n=len(tok.apply_chat_template(g.diagnosis_messages(u['task'],'x'*400),tokenize=True,add_generation_prompt=True))
        g.require(n+cfg['max_new_tokens']<=cfg['context_limit'],'diagnosis context overflow')
        r=record(u,split);_,b=fitted_messages(r,[],tok,c0)
        budgets.append(dict(request_id=u['request_id'],diagnosis_retry_input_tokens=n,C0=b))
    destination.mkdir()
    write_json(destination/'units.private.json',units)
    manifest=dict(version=g.VERSION,split=split,at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
          initial_head=read(out/'inventory.private.json')['initial_head'],head_at_freeze=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          selection_sha256=sha(out/'selection.private.json'),config=cfg,C0_config=c0,tokenizer=metadata,
          source_sha256=sha(destination/'units.private.json'),implementation_sha256={name:sha(ROOT/name)for name in FILES},
          prompt_sha256=digest([g.DIAGNOSIS_SYSTEM,g.FEEDBACK_SYSTEM,g.GUARD_SYSTEM,g.RULES]),budgets=budgets,
          policy=dict(C0='native immutable R15, 1024 tokens/45s/3 attempts with original fallback',
                      C1='shared diagnosis + full task/findings; cited-sentence schema and legacy disclosure screen',
                      C2='same diagnosis + Level view only + Qwen semantic screen',
                      candidate_budget='1536 tokens/60s per call, diagnosis<=2; renderer<=2 plus one guard per valid C2 attempt',
                      compiler='supplied only, no compile or student execution',no_public_selection=True,
                      exposure='historically exposed controlled evaluation; method prospectively frozen; not blind',
                      selection='all 60 parent primary; all 8 parent eligible train; no sample-based changes',
                      exhaustion='unresolved, no placeholders or empty taxonomy fallback'))
    write_json(destination/'freeze.json',manifest)
    (destination/'freeze.sha256').write_text(sha(destination/'freeze.json')+'\n')
    print(json.dumps(dict(frozen=split,IDs=len(units),sha256=sha(destination/'freeze.json'),prompt_sha256=manifest['prompt_sha256'])))


def verify(out,split):
    verify_selection(out);d=out/split;m=read(d/'freeze.json')
    g.require(sha(d/'freeze.json')==(d/'freeze.sha256').read_text().strip(),'freeze seal drift')
    g.require(sha(d/'units.private.json')==m['source_sha256'],'frozen source drift')
    for name,h in m['implementation_sha256'].items():g.require(sha(ROOT/name)==h,'runtime drift: '+name)
    g.require(read(d/'units.private.json')==units_for(split,out),'parent projection drift')
    return m,read(d/'units.private.json')


def record(u,split):
    t=u['task']
    from src.synth.feedback import FEEDBACK_LEVELS
    return Task3Record(source='synthetic',sample_id=u['request_id'],original_submission_id=u['sample_id'],exam_id=u['family'],
          exam_type=t['exam_type'],statement=t['statement'],grading_policy=t['grading_policy'],code_path='PRIVATE_SOURCE',code=t['code'],
          target_feedback_level=FEEDBACK_LEVELS[u['level']-1],problems=t['problems'],split='grounded-'+split,
          provenance={'_task3_compile_check':t['compiler']})


def run(out,split):
    m,units=verify(out,split);d=out/split
    g.require(not (d/'run.private.json').exists(),'split already complete; do not resample')
    if split=='evaluation':
        g.require((out/'development/review-seal.json').is_file(),'independent development review must be sealed first')
    free=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip().splitlines()
    g.require(len(free)==1 and int(free[0])>=m['config']['minimum_free_gpu_mib'],'GPU unavailable')
    environment()
    from src.task3.inference import HFBackend,load_tokenizer,tokenizer_metadata
    from src.task3.round15_runner import run_records
    from src.task3.grounded_runner import Journal,run_candidates
    tok=load_tokenizer(m['config']);g.require(tokenizer_metadata(tok)==m['tokenizer'],'tokenizer drift')
    backend=HFBackend(m['config'],tok)
    write_json(d/'runtime-before.private.json',dict(runtime=backend.runtime_metadata(),tokenizer=m['tokenizer'],replay=False))
    backend.model.generation_config.max_time=m['C0_config']['generation_max_time_s']
    c0=run_records([record(u,split)for u in units],backend,m['C0_config'],d/'C0',examples=())
    backend.model.generation_config.max_time=m['config']['generation_max_time_s']
    journal=Journal(d/'candidate',backend,m['config'],sha(d/'freeze.json'))
    candidates=run_candidates(units,journal,d/'candidate')
    verify(out,split)
    write_json(d/'run.private.json',dict(freeze_sha256=sha(d/'freeze.json'),C0_completed=len(c0['predictions']),
                 C1_completed=sum(r['arms']['C1']['status']=='resolved'for r in candidates),
                 C2_completed=sum(r['arms']['C2']['status']=='resolved'for r in candidates),
                 runtime=backend.runtime_metadata(),replay=False,model_id=m['config']['model_id'],revision=m['config']['revision']))
    print(json.dumps(read(d/'run.private.json'),ensure_ascii=False))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['freeze','verify','run','all'])
    p.add_argument('--split',choices=['development','evaluation'],default='development');p.add_argument('--output',type=Path,default=DEFAULT)
    a=p.parse_args();out=a.output.resolve();g.require(out.is_relative_to(ROOT/'outputs/task3'),'private output path required')
    if a.phase in ['freeze','all']:freeze(out,a.split)
    if a.phase=='verify':m,u=verify(out,a.split);print(json.dumps({'verified':True,'IDs':len(u)}))
    if a.phase in ['run','all']:run(out,a.split)


if __name__=='__main__':main()
