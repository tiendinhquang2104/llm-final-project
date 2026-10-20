#!/usr/bin/env python3
"""Frozen train-only counterfactual and paired two-stage pilot orchestration."""
import argparse
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from src.task3.dataset import load_task3,load_prepared,write_json
from src.task3.schema import Task3Record,code_hash
from src.task3.compiler import check_cpp_syntax
from src.task3.round14 import sanitize
from src.task3.round14_runner import digest
from src.utils.config import load_config
ROOT=REPO/'outputs/task3/round18'
ZIP_SHA='6bda70c29254a3bce91933b65f4a311d73a052e72d181c97e977152e14602f9b'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def records(name):return [Task3Record(**r) for r in json.loads((ROOT/(name+'.private.json')).read_text())]
def metadata(r,expectation):
 return dict(sample_id=r.sample_id,family=r.exam_id,group=r.group_key or r.original_submission_id,source_sha256=hashlib.sha256(r.code.encode()).hexdigest(),code_identity=code_hash(r.code),renamed_identity=code_hash(r.code,renamed=True),annotation_v2=r.gold_taxonomy,**expectation)
def prepare():
 if (ROOT/'freeze.json').exists():raise ValueError('already frozen')
 assert sha(REPO/'generate-dataset_v2.zip')==ZIP_SHA
 pool=load_task3(REPO/'data/raw/round18-new','synthetic');by={r.sample_id:r for r in pool}
 spec=json.loads((REPO/'configs/task3/r18_source_expectations.json').read_text())
 old={r.sample_id:r for r in load_prepared(REPO/'data/processed/task3','synthetic-train')}
 protected=[]
 for split in ('real-val','synthetic-heldout'):
  protected.extend(load_prepared(REPO/'data/processed/task3',split))
 forbidden={code_hash(r.code,renamed=True) for r in protected}
 groups={r.original_submission_id for r in protected}
 sets={}
 for name in ('counterfactual','evaluation'):
  selected=[]
  for sid,ex in spec[name].items():
   r=by[sid]
   assert r.original_submission_id not in groups and code_hash(r.code,renamed=True) not in forbidden
   assert sid in old or int(sid.rsplit('-',1)[-1])>=int(spec['new_first_ids'][r.exam_id])
   e=check_cpp_syntax(r.code,compiler='/usr/bin/g++',standard='c++11',timeout_s=3);e.pop('latency_s',None)
   r=replace(r,split='synthetic-train',group_key=old[sid].group_key if sid in old else code_hash(r.code),provenance={'_task3_compile_check':e})
   if ex.get('compile_error'):assert e['status']=='compile_error'
   selected.append(r)
  assert len({code_hash(r.code,renamed=True) for r in selected})==len(selected)
  sets[name]=selected;write_json(ROOT/(name+'.private.json'),[asdict(r) for r in selected])
 assert not {r.exam_id for r in sets['counterfactual']}&{r.exam_id for r in sets['evaluation']}
 protected_files={str(p.relative_to(REPO)):sha(p) for p in (REPO/'outputs/task3/round15').rglob('*') if p.is_file()}
 protected_files['predictions.json']=sha(REPO/'predictions.json')
 for p in (REPO/'reports/task3').glob('*R15*'):protected_files[str(p.relative_to(REPO))]=sha(p)
 freeze={'zip_sha256':ZIP_SHA,'initial_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'branch':subprocess.check_output(['git','branch','--show-current'],text=True).strip(),'selection_rule':'source reviewed fixed IDs; two per diagnostic family; separate evaluation families; old fixed train membership plus new appended train IDs checked against heldout/real-val identities; no public selection',
 'sets':{n:[metadata(r,spec[n][r.sample_id]) for r in rr] for n,rr in sets.items()},'private_hashes':{n:sha(ROOT/(n+'.private.json')) for n in sets},'control_config':load_config(REPO/'configs/task3/r15_zero_shot.yaml'),'control_implementation':{p:sha(REPO/p) for p in ['src/task3/round15.py','src/task3/round15_runner.py','src/task3/round15_disclosure.py','src/task3/inference.py']},'protected_files':protected_files,'counterfactual_levels':[1,2,3],'level4_ids':[r.sample_id for r in sets['counterfactual'][:4]],'evaluation_levels':{r.sample_id:(i%4)+1 for i,r in enumerate(sets['evaluation'])},'pilot_policy':{'seed':42,'lora_r':16,'lora_alpha':32,'learning_rate':0.0001,'epochs':1,'gradient_accumulation_steps':4,'checkpoint':'final epoch only; no eval selection or sweep','training_family_exclusions':sorted({r.exam_id for rr in sets.values() for r in rr})},'exposure':'R16/R17 train development and six real-val/old heldout repeatedly observed; R13 corpus reviewed. This is a frozen paired development evaluation, NOT blind. New algorithm source appended in current ZIP; no family-generalization claim.'}
 write_json(ROOT/'freeze.json',freeze);write_json(REPO/'reports/task3/TASK3_ROUND18_FREEZE_20261020.json',freeze)
 print('frozen',sha(ROOT/'freeze.json'))
def verify():
 f=json.loads((ROOT/'freeze.json').read_text())
 for p,h in {**f['protected_files'],**f['control_implementation']}.items():assert sha(REPO/p)==h,p
 for n,h in f['private_hashes'].items():assert sha(ROOT/(n+'.private.json'))==h
 return f

def run_a():
 from src.task3.inference import HFBackend
 from src.task3.round15_runner import run_records
 f=verify();cfg=f['control_config'];inputs=[]
 for r in records('counterfactual'):
  for level in [1,2,3]+([4] if r.sample_id in f['level4_ids'] else []):
   inputs.append(replace(sanitize(r,r.provenance['_task3_compile_check']),sample_id=r.sample_id+'@L'+str(level),target_feedback_level='Level '+str(level)+{1:' - Gợi ý nhẹ',2:' - Chẩn đoán',3:' - Gợi ý sửa',4:' - Lời giải mẫu'}[level]))
 backend=HFBackend(cfg);backend.model.generation_config.max_time=cfg['generation_max_time_s']
 result=run_records(inputs,backend,cfg,ROOT/'A-counterfactual',examples=[])
 write_json(ROOT/'A-runtime.json',backend.runtime_metadata());summarize_a(f,result)
 verify()

def summarize_a(f,result):
 from src.task3.round15 import parse_response
 by={p['sample_id']:p['output'] for p in result['predictions']};traces={t['sample_id']:t for t in result['traces']}
 table=[]
 for r in records('counterfactual'):
  rows=[]
  for level in [1,2,3]+([4] if r.sample_id in f['level4_ids'] else []):
   sid=r.sample_id+'@L'+str(level);trace=traces.get(sid,result['errors'].get(sid,{}).get('trace',{}));attempts=[]
   for a in trace.get('attempts',[]):
    try:p=parse_response(a['raw_text'])
    except (ValueError,TypeError):p=None
    attempts.append({'raw_sha256':digest(a.get('raw_text')),'output':p})
   final=by.get(sid);last=next((a['output'] for a in reversed(attempts) if a['output'] is not None),None)
   rows.append({'level':level,'attempts':attempts,'final':final,'final_sha256':digest(final),'origin':trace.get('final_origin'),'fallback':trace.get('fallback_used'),'retry_taxonomy_changed':bool(attempts and attempts[0]['output'] and final and set(attempts[0]['output']['taxonomy_error'])!=set(final['taxonomy_error'])),'controller_taxonomy_changed':bool(last and final and last['taxonomy_error']!=final['taxonomy_error'])})
  first=[set(x['attempts'][0]['output']['taxonomy_error']) if x['attempts'] and x['attempts'][0]['output'] else None for x in rows[:3]];final=[set(x['final']['taxonomy_error']) if x['final'] else None for x in rows[:3]]
  table.append({'sample_id':r.sample_id,'first_invariant':None not in first and all(s==first[0] for s in first),'final_invariant':None not in final and all(s==final[0] for s in final),'levels':rows})
 summary={'codes':len(table),'runs':sum(len(x['levels']) for x in table),'completed':len(by),'first_exact_set_invariant':sum(x['first_invariant'] for x in table),'final_exact_set_invariant':sum(x['final_invariant'] for x in table),'retry_taxonomy_changes':sum(y['retry_taxonomy_changed'] for x in table for y in x['levels']),'controller_taxonomy_changes':sum(y['controller_taxonomy_changed'] for x in table for y in x['levels']),'empty_by_level':{l:sum(y['final'] is not None and not y['final']['taxonomy_error'] for x in table for y in x['levels'] if y['level']==l) for l in (1,2,3,4)},'per_id':table}
 write_json(ROOT/'A-results.private.json',summary);print(json.dumps({k:v for k,v in summary.items() if k!='per_id'},ensure_ascii=False))

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['prepare','A']);a=ap.parse_args()
 os.environ.setdefault('HF_HOME',str(REPO/'outputs/task3/hf-cache'));os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
 prepare() if a.phase=='prepare' else run_a()
