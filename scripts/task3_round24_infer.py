#!/usr/bin/env python3
"""Sealed train-only direct feedback comparison, native R15 controller, no execution."""
from pathlib import Path
import argparse,json,sys,os,subprocess
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.task3.dataset import write_json
from src.task3.feedback_prompt import verify_seal,sha
from src.task3.schema import Task3Record
from src.task3.round24_review import validate_projection
from src.utils.config import load_config
W=ROOT/'outputs/task3/round24-20261022'

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--arm',choices=['R15','C'],required=True);ap.add_argument('--verify-only',action='store_true');args=ap.parse_args()
 verify_seal(W/'selection-freeze.json');verify_seal(W/'review-freeze.json')
 if args.arm=='C':verify_seal(W/'prompt-freeze.json');verify_seal(W/'baseline-review-freeze.json')
 raw_records=json.loads((W/'model-inputs.private.json').read_text());validate_projection(raw_records,json.loads((W/'sources.private.json').read_text()))
 records=[Task3Record(**r)for r in raw_records]
 if len(records)!=60 or len({r.sample_id for r in records})!=60:raise ValueError('60 unique query IDs required')
 for r in records:
  if r.source not in ['real','synthetic']or not r.split.startswith('round24-')or r.gold_taxonomy is not None or r.gold_feedback is not None:raise ValueError('isolated train projection only')
 cfg=load_config(ROOT/'configs/task3/r15_selected.yaml');ex=json.loads((ROOT/'configs/task3/round24_20261022.json').read_text())
 if cfg['model_id']!=ex['model_id']or cfg['revision']!=ex['revision']or cfg.get('adapter'):raise ValueError('pinned base7B model only')
 cfg={**cfg,'offline_experiment':'round24','offline_arm':args.arm,'input_sha256':sha(W/'model-inputs.private.json')}
 if args.verify_only:print(json.dumps({'verified':True,'IDs':len(records),'arm':args.arm}));return 0
 out=W/args.arm
 if (out/'run.json').exists():raise ValueError('arm already completed; never replace observations')
 free=int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip())
 if free<ex['minimum_free_gpu_mib']:print(json.dumps({'waiting_gpu':True,'free_mib':free}));return 3
 os.environ['HF_HOME']=str(ROOT/'outputs/task3/hf-cache');os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
 from src.task3.inference import HFBackend,load_tokenizer,tokenizer_metadata
 from src.task3.round15_runner import run_records
 from src.task3.round15 import fitted_messages
 tok=load_tokenizer(cfg);metadata=tokenizer_metadata(tok)
 if metadata['mock']or metadata['chat_template_sha256']!='cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f':raise ValueError('pinned tokenizer required')
 if args.arm=='C':
  from src.task3.round24_prompt import fitted
  preflight=lambda r:fitted(r,[],tok,cfg,arm='C')
 else:preflight=lambda r:fitted_messages(r,[],tok,cfg)
 budgets=[{'sample_id':r.sample_id,**preflight(r)[1]}for r in records]
 out.mkdir(exist_ok=True);write_json(out/'preflight.json',budgets)
 backend=HFBackend(cfg,tok);backend.model.generation_config.max_time=cfg['generation_max_time_s']
 write_json(out/'runtime-before.json',{'config':cfg,'runtime':backend.runtime_metadata(),'tokenizer':metadata,'replay':False})
 if args.arm=='C':
  from src.task3.round24_prompt import adapter
  with adapter('C'):result=run_records(records,backend,cfg,out,examples=())
 else:result=run_records(records,backend,cfg,out,examples=())
 verify_seal(W/'review-freeze.json')
 if args.arm=='C':verify_seal(W/'prompt-freeze.json')
 write_json(out/'run.json',{'arm':args.arm,'config':cfg,'requested':60,'completed':len(result['predictions']),'errors':result['errors'],'runtime':backend.runtime_metadata(),'tokenizer':metadata,'identity':result['identity'],'replay':False,'program_execution':False,'training':False,'new_renderer':False})
 return 0 if not result['errors'] else 2
if __name__=='__main__':raise SystemExit(main())
