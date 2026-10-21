#!/usr/bin/env python3
"""One v2 direct pass; BASE and v1 outputs are immutable reused inputs. No diagnosis, no evaluation reference in model inputs."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from src.task3.round15 import query_payload,parse_response
from src.task3.round15_runner import run_records
from src.task3.dataset import write_json
from scripts.task3_pilot_infer import load_backend,_capture

LOCKED=dict(model_id='Qwen/Qwen2.5-Coder-7B-Instruct',revision='c03e6d358207e414f1eca0bb1891e29f1db0e242',seed=42,load_in_4bit=True,do_sample=False,context_limit=16384,max_new_tokens=1024,level4_max_tokens=1536,max_time=60,max_attempts=3,prompt_variant='zero_shot',few_shot_k=0,prompt_policy='round15-short-direct-v1',completion_policy='preserve_qwen_content_with_schema_and_explicit_l1_l2_only')
TASK_KEYS={'statement','problems','grading_policy','student_code','compiler_evidence','allowed_labels'}


def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def validate_rows(rows):
 ids=set();sources=set()
 if not isinstance(rows,list) or not rows:raise ValueError('nonempty paired rows required')
 for r in rows:
  if set(r)!={'request_id','sample_id','kind','requested_level','task'} or set(r['task'])!=TASK_KEYS:raise ValueError('unsafe model input keys')
  if r['request_id'] in ids or r['sample_id'] in sources:raise ValueError('unique primary sources required')
  if r['kind']!='primary' or type(r['requested_level']) is not int or r['requested_level'] not in (1,2,3,4):raise ValueError('invalid Level/request')
  ids.add(r['request_id']);sources.add(r['sample_id'])


def record(r):
 t=r['task'];return SimpleNamespace(sample_id=r['request_id'],statement=t['statement'],problems=t['problems'],grading_policy=t['grading_policy'],code=t['student_code'],target_feedback_level=f"Level {r['requested_level']}",provenance={'_task3_compile_check':t['compiler_evidence']})


def start(out,arm,config,rows):
 if arm != 'V2' or config != LOCKED:raise ValueError('only V2 with frozen settings may start')
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 with (out/'started.json').open('x') as f:
  os.chmod(f.name,0o600);json.dump(dict(arm=arm,config=config,config_sha256=digest(config),inputs_sha256=digest(rows),requests=len(rows),resume_allowed=False,started_unix=time.time()),f);f.flush();os.fsync(f.fileno())


class Capture:
 def __init__(self,backend,out,records):
  self.backend=backend;self.tokenizer=backend.tokenizer;self.out=out;self.index=0
  self.requests={digest(query_payload(r)):r.sample_id for r in records}
  if len(self.requests)!=len(records):raise ValueError('nonunique query payload')
 def generate(self,messages,config):
  self.index+=1
  rid=self.requests[digest(json.loads(messages[1]['content']))]
  captured=_capture(self.backend,messages,config,self.out,request_id=rid,stage='direct',key=self.index)
  if captured['error']:raise RuntimeError(captured['error'])
  return SimpleNamespace(text=captured['raw_text'],output_tokens=captured['output_tokens'],latency_s=captured['latency_s'],finish_reason=captured['finish_reason'],eos_reached=captured['eos_reached'])


def run_arm(rows,backend,config,out,*,arm,started=False):
 if arm != 'V2' or config!=LOCKED:raise ValueError('frozen direct paired settings required')
 validate_rows(rows);out=Path(out)
 if not started:start(out,arm,config,rows)
 records=[record(r) for r in rows];predictions=[]
 write_json(out/'status.json',dict(arm=arm,complete=False,requests=len(rows),processed=0))
 try:
  result=run_records(records,Capture(backend,out,records),config,out/'legacy',examples=())
  success={r['sample_id']:r['output'] for r in result['predictions']}
  trace={r['sample_id']:r for r in result['traces']}
  for row in rows:
   rid=row['request_id'];p=dict(request_id=rid,sample_id=row['sample_id'],status='unresolved')
   if rid in success:p.update(status='completed',output=success[rid],trace=trace[rid])
   else:
    error=result['errors'][rid];p['error']=error['reason'];attempts=error.get('trace',{}).get('attempts',[])
    if attempts and attempts[-1].get('runtime_error'):p['status']='runtime_error'
    elif attempts:
     try:parse_response(attempts[-1].get('raw_text'))
     except (ValueError,TypeError):p['status']='schema_error'
   predictions.append(p)
  write_json(out/'predictions.json',predictions)
  write_json(out/'status.json',dict(arm=arm,complete=True,requests=len(rows),processed=len(predictions),completed=sum(r['status']=='completed' for r in predictions)))
 except BaseException as exc:
  write_json(out/'status.json',dict(arm=arm,complete=False,requests=len(rows),processed=len(predictions),error=repr(exc)));raise
 return dict(predictions=predictions)


def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--arm',choices=['V2'],required=True);ap.add_argument('--start',action='store_true');args=ap.parse_args()
 if not args.start:ap.error('--start is required')
 from scripts.task3_direct_sft_v2_prepare import verify_pilot,WORK,FROZEN,read,sha
 manifest,config,*_=verify_pilot()
 if config['inference']!=LOCKED:raise ValueError('frozen inference config mismatch')
 trained=read(WORK/'training/training-result.json')
 if trained['status']!='complete' or trained['manifest_sha256']!=digest(manifest) or trained['config_sha256']!=digest(config):raise ValueError('complete internally-selected adapter required before paired inference')
 adapter=WORK/'training/adapter'
 actual={str(p.relative_to(adapter)):sha(p) for p in adapter.rglob('*') if p.is_file()}
 if actual!=trained['selected_adapter_files_sha256']:raise ValueError('adapter files differ from internal-validation selection')
 rows=read(FROZEN/'development-inputs.private.json');validate_rows(rows)
 if len(rows)!=60:raise ValueError('all60development primary records required')
 out=WORK/'inference'/f'arm-{args.arm}';start(out,args.arm,LOCKED,rows)
 os.environ.setdefault('HF_HOME',str(REPO/'outputs/task3/hf-cache'));os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
 backend=load_backend(LOCKED,adapter=adapter)
 write_json(out/'runtime.before.json',backend.runtime_metadata())
 run_arm(rows,backend,dict(LOCKED),out,arm=args.arm,started=True)
 write_json(out/'runtime.after.json',backend.runtime_metadata())
 print(json.dumps(dict(arm=args.arm,requests=len(rows),complete=True)))
if __name__=='__main__':main()
