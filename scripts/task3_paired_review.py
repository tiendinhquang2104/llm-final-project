#!/usr/bin/env python3
"""Frozen development-only paired 7B study. No public reader or C++ execution."""
from pathlib import Path
import argparse,hashlib,json,os,sys,time,subprocess
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.task3.eval_snapshot import sha_file,sha_bytes,write_new,read_archive
from src.task3.paired_review import leakage_matches,blind_pairs
from src.task3.dataset import decode_code
from src.utils.config import load_config
W=ROOT/'outputs/task3/paired-review-20261022'
CONFIG=ROOT/'configs/task3/paired_review_20261022.json'
def read(p):return json.loads(Path(p).read_text())
def put(p,v):write_new(p,v)
def verify():
 m=read(W/'selection.private.json')
 for path,h in m['files_sha256'].items():
  if sha_file(ROOT/path)!=h:raise ValueError('frozen input/code drift: '+path)
 return m

def prepare():
 cfg=read(CONFIG);archive=read_archive(ROOT/'generate-dataset_v2.zip')
 syn={r['sample_id']:r for r in read(ROOT/'outputs/task3/eval-freeze-v2-20261021/frozen/reference.private.json')['records']}
 pool={};annotations={};inputs={}
 for line in (ROOT/'data/processed/task3/real-val.jsonl').read_text().splitlines():
  r=json.loads(line)['record'];raw=Path(r['code_path']).read_bytes()
  if decode_code(Path(r['code_path']))!=r['code']:raise ValueError('real source bytes mismatch')
  sid=r['sample_id'];pool[sid]=dict(sample_id=sid,source='real',family=r['exam_id'],statement=r['statement'],problems=r['problems'],grading_policy=r['grading_policy'],code=r['code'],source_sha256=sha_bytes(raw),source_text_sha256=sha_bytes(r['code'].encode()),original_level=r['target_feedback_level'],compiler_evidence={'status':'unknown','diagnostic':''})
  annotations[sid]=dict(taxonomy_error=r['gold_taxonomy'],teacher_feedback=r['gold_feedback'])
 for sid,r in syn.items():
  a=next(a for a in archive['records']if a['sample_id']==sid)
  if any(a[k]!=r[k]for k in ['code','statement','source_sha256']):raise ValueError('archive source/context mismatch')
  pool[sid]={k:r[k]for k in ['sample_id','family','statement','problems','grading_policy','code','source_sha256','source_text_sha256','compiler_evidence']}
  pool[sid].update(source='synthetic',original_level=r['original_level'])
  annotations[sid]=dict(taxonomy_error=r['annotation_v2'],teacher_feedback=None)
 training=[];files=[CONFIG,ROOT/'generate-dataset_v2.zip',ROOT/'data/processed/task3/real-val.jsonl',ROOT/'data/processed/task3/manifest.json',ROOT/'outputs/task3/eval-freeze-v2-20261021/frozen/reference.private.json',ROOT/'data/raw/round18-new/label_space.json',ROOT/'data/raw/sample_dataset/label_space.json']
 adapters={}
 for v in ['v1','v2']:
  d=ROOT/f'outputs/task3/direct-sft-{v}-20261021';t=read(d/'training/training-result.json')
  actual={str(p.relative_to(d/'training/adapter')):sha_file(p)for p in (d/'training/adapter').rglob('*')if p.is_file()}
  if t['status']!='complete'or actual!=t['selected_adapter_files_sha256']:raise ValueError('adapter unavailable/drift '+v)
  adapters[v]=dict(path=str(d/'training/adapter'),sha256=actual,selected_epoch=t['selected_epoch'])
  files += [d/'training/training-result.json']+list((d/'training/adapter').rglob('*'))
  for kind in ['train','validation']:
   f=d/f'frozen/{kind}-sources.private.json';files.append(f);training+=read(f)
 selected=[];exclusions=[];family_split={}
 for split in ['development','validation']:
  for index,sid in enumerate(cfg[split]):
   r=pool[sid];matches=leakage_matches(r,training+selected,cfg['near_threshold'])
   if matches:exclusions.append(dict(sample_id=sid,matches=matches));continue
   if r['family']in family_split and family_split[r['family']]!=split:raise ValueError('cross-split family')
   family_split[r['family']]=split;r=dict(r,split=split,requested_level=1+index%3)
   if sid in ['SYN-BASE2-0000','SYN-REVSTR-0001']:r['requested_level']=4
   selected.append(r)
 put(W/'sources.private.json',selected);put(W/'annotations.private.json',{r['sample_id']:annotations[r['sample_id']]for r in selected})
 put(W/'leakage.private.json',dict(protected_rows=len(training),exclusions=exclusions,selected=len(selected),threshold=cfg['near_threshold'],family_splits=family_split,limitations='SFT family overlap and prior research exposure remain; lexical screening cannot prove semantic independence.'))
 put(W/'requested-levels.private.json',{r['sample_id']:r['requested_level']for r in selected})
 for r in selected:
  inputs[r['sample_id']]=dict(kind='primary',request_id=r['sample_id'],sample_id=r['sample_id'],requested_level=r['requested_level'],task=dict(statement=r['statement'],problems=r['problems'],grading_policy=r['grading_policy'],student_code=r['code'],compiler_evidence=r['compiler_evidence'],allowed_labels=read(ROOT/'data/raw/round18-new/label_space.json')['taxonomy_error']))
 put(W/'model-inputs.private.json',list(inputs.values()))
 files += [ROOT/f for f in ['src/task3/paired_review.py','scripts/task3_paired_review.py','src/task3/round15.py','src/task3/round15_runner.py','src/task3/inference.py','src/task3/submission.py','configs/task3/r15_common.yaml','configs/task3/r15_zero_shot.yaml','configs/task3/r15_selected.yaml']]
 files += [W/f for f in ['sources.private.json','annotations.private.json','model-inputs.private.json','leakage.private.json','requested-levels.private.json']]
 put(W/'selection.private.json',dict(created_unix=time.time(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),config=cfg,adapters=adapters,files_sha256={str(p.relative_to(ROOT)):sha_file(p)for p in files if p.is_file()},selected=[{k:r[k]for k in ['sample_id','source_sha256','source_text_sha256','source','family','split','requested_level','original_level']}for r in selected],annotation_version=cfg['annotation_version']))
 print(json.dumps(dict(selected=len(selected),excluded=len(exclusions),selection_sha256=sha_file(W/'selection.private.json'))))

def infer(arm,split):
 m=verify();out=W/arm/split
 if (out/'started.json').exists():raise ValueError('refuse overwrite or replay of existing arm')
 os.environ['HF_HOME']=str(ROOT/'outputs/task3/hf-cache');os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
 from scripts.task3_direct_sft_infer import record,Capture
 from scripts.task3_pilot_infer import load_backend
 from src.task3.round15_runner import run_records
 from src.task3.dataset import write_json
 from src.task3.submission import validate_submission
 from src.synth.feedback import FEEDBACK_LEVELS
 cfg=load_config(ROOT/m['config']['baseline']);cfg['max_time']=cfg['generation_max_time_s']
 rows=[r for r in read(W/'model-inputs.private.json')if any(s['sample_id']==r['sample_id']and s['split']==split for s in m['selected'])]
 records=[record(r)for r in rows];adapter=None
 if arm in ['SFT1','SFT2']:adapter=m['adapters']['v1'if arm=='SFT1'else'v2']['path']
 if arm=='C1':
  from src.task3.paired_review_prompt import adapter as prompt_adapter
  freeze=read(W/'candidate-freeze.private.json')
  if freeze['prompt_sha256']!=sha_file(ROOT/'src/task3/paired_review_prompt.py'):raise ValueError('candidate prompt drift')
 out.mkdir(parents=True,exist_ok=True);put(out/'started.json',dict(arm=arm,split=split,config=cfg,adapter=adapter,selection_sha256=sha_file(W/'selection.private.json'),start_unix=time.time()))
 backend=load_backend(cfg,adapter=adapter);write_json(out/'runtime-before.json',backend.runtime_metadata())
 start=time.perf_counter()
 if arm=='C1':
  with prompt_adapter():result=run_records(records,Capture(backend,out,records),cfg,out,examples=())
 else:result=run_records(records,Capture(backend,out,records),cfg,out,examples=())
 status=dict(requested=len(records),completed=len(result['predictions']),errors=result['errors'],elapsed_s=time.perf_counter()-start,config=cfg,runtime=backend.runtime_metadata(),schema=None)
 if not result['errors']:status['schema']=validate_submission(out/'predictions.json',{r['request_id']:FEEDBACK_LEVELS[r['requested_level']-1]for r in rows})
 write_json(out/'run.json',status);verify();print(json.dumps(dict(arm=arm,split=split,completed=status['completed'],requested=status['requested'],elapsed_s=status['elapsed_s'])))

def blind(split,arms,name):
 verify();sources=[r for r in read(W/'sources.private.json')if r['split']==split];outputs={}
 for arm in arms:
  outputs[arm]={r['sample_id']:r['output']for r in read(W/arm/split/'completed.predictions.json')}
 packet,key=blind_pairs(sources,outputs,seed=42 if name=='baseline'else 71)
 put(W/f'{split}-{name}-pairs.private.json',packet);put(W/f'{split}-{name}-key.private.json',key)
 print(json.dumps(dict(split=split,rows=len(packet))))

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('phase',choices=['prepare','verify','infer','blind']);ap.add_argument('--arm',choices=['R15','SFT1','SFT2','C1']);ap.add_argument('--split',choices=['development','validation']);ap.add_argument('--arms',nargs='+');ap.add_argument('--name',default='baseline');a=ap.parse_args()
 if a.phase=='prepare':prepare()
 elif a.phase=='verify':verify();print('VERIFIED')
 elif a.phase=='infer':infer(a.arm,a.split)
 elif a.phase=='blind':blind(a.split,a.arms,a.name)
if __name__=='__main__':main()
