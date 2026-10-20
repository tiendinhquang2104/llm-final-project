#!/usr/bin/env python3
"""One frozen two-stage base/adapter comparison; no public inference."""
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from scripts.task3_round18 import ROOT,records,verify,sha
from src.task3.dataset import write_json
from src.task3.round14 import sanitize
from src.task3.round14_runner import digest
from src.task3.two_stage import TwoStageRunner,StageFailure
from src.utils.config import load_config
from src.synth.feedback import FEEDBACK_LEVELS

def run_set(name,backend,cfg,condition):
 f=verify();directory=ROOT/condition;directory.mkdir(exist_ok=True);path=directory/(name+'.private.json')
 if path.exists():raise ValueError('single pass only: output exists '+str(path))
 runner=TwoStageRunner(backend,cfg,directory/(name+'.journal.jsonl'));result=[]
 for raw in records(name):
  r=sanitize(raw,raw.provenance['_task3_compile_check']);levels=[1,2,3]+([4] if r.sample_id in f['level4_ids'] else []) if name=='counterfactual' else [f['evaluation_levels'][r.sample_id]]
  row={'sample_id':r.sample_id,'levels':{},'errors':{},'diagnosis':None}
  try:row['diagnosis']=runner.diagnose(r)
  except StageFailure as exc:row['errors']['diagnose']=str(exc)
  if row['diagnosis'] is not None:
   for level in levels:
    try:row['levels'][str(level)]=runner.feedback(r,row['diagnosis'],level)
    except StageFailure as exc:row['errors'][str(level)]=str(exc)
  result.append(row);write_json(path,result)
  print(condition,name,r.sample_id,len(row['levels']),row['errors'],flush=True)
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('condition',choices=('B','C'));args=ap.parse_args()
 os.environ.setdefault('HF_HOME',str(REPO/'outputs/task3/hf-cache'));os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
 from src.task3.inference import HFBackend
 f=verify();cfg=load_config(REPO/'configs/task3/r18_two_stage.yaml')
 if args.condition=='C':
  manifest=json.loads((ROOT/'training-manifest.json').read_text());assert manifest['config']['revision']==cfg['revision']
  cfg['adapter']=str(REPO/'checkpoints/task3/r18-pilot/adapter')
 code={p:sha(REPO/p) for p in ('src/task3/two_stage.py','scripts/task3_round18_flow.py','configs/task3/r18_two_stage.yaml')}
 binding=ROOT/'two-stage-freeze.json'
 if args.condition=='B':
  if binding.exists():raise ValueError('base frozen run already started')
  write_json(binding,{'implementation':code,'config':cfg,'A_results_sha256':sha(ROOT/'A-results.private.json')})
 else:assert json.loads(binding.read_text())['implementation']==code,'flow changed after base evaluation'
 backend=HFBackend(cfg);backend.model.generation_config.max_time=cfg['generation_max_time_s']
 if args.condition=='B':
  from src.task3.round15_runner import run_records
  rr=[replace(sanitize(r,r.provenance['_task3_compile_check']),target_feedback_level=FEEDBACK_LEVELS[f['evaluation_levels'][r.sample_id]-1]) for r in records('evaluation')]
  run_records(rr,backend,f['control_config'],ROOT/'A-evaluation',examples=[])
  run_set('counterfactual',backend,cfg,'B')
 run_set('evaluation',backend,cfg,args.condition)
 write_json(ROOT/args.condition/'runtime.json',backend.runtime_metadata());verify()
if __name__=='__main__':main()
