#!/usr/bin/env python3
"""New direct SFT protocol: source identities, assistant-only targets, no diagnosis."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import sys
from types import SimpleNamespace

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
WORK=REPO/'outputs/task3/direct-sft-v1-20261021'
FROZEN=WORK/'frozen'
CONFIG=REPO/'configs/task3/direct_sft_v1_20261021.json'
PUBLIC=REPO/'reports/task3/TASK3_DIRECT_SFT_V1_FREEZE_20261021.json'
from src.task3.round15 import build_messages,parse_response
from src.task3.eval_v2 import similarity as source_similarity


def read(path):return json.loads(Path(path).read_bytes())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def write_new(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('xb') as f:f.write((json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode())
 path.chmod(0o600)


def native_record(row,level):
 return SimpleNamespace(sample_id=row['sample_id'],statement=row['statement'],problems=row.get('problems',[]),grading_policy=row.get('grading_policy',{}),code=row['code'],target_feedback_level=f'Level {level}',provenance={'_task3_compile_check':{'status':'unavailable','diagnostic':''}})


def build_examples(sources,reviewed):
 by={r['sample_id']:r for r in reviewed}
 if len(by)!=len(reviewed) or set(by)!={r['sample_id'] for r in sources}:raise ValueError('source/target membership mismatch')
 result=[];ids=set()
 for source in sources:
  r=by[source['sample_id']];h=hashlib.sha256(source['code'].encode()).hexdigest()
  if source.get('source_sha256',h)!=r['source_sha256'] or source.get('source_text_sha256',h)!=h or r.get('source_reference') is None:raise ValueError('raw/decoded source target hash or unresolved reference')
  if r.get('review',{}).get('human_verified') is not False:raise ValueError('agent source review required')
  for target in r['targets']:
   level=target['level'];output=target['output']
   if type(level) is not int or level not in (1,2,3,4):raise ValueError('invalid target Level')
   completion=json.dumps(output,ensure_ascii=False)
   parsed=parse_response(completion)
   if set(parsed['taxonomy_error'])!=set(r['source_reference']):raise ValueError('target/reference taxonomy mismatch')
   eid=f"direct-v1:{source['sample_id']}@L{level}"
   if eid in ids:raise ValueError('duplicate direct example')
   ids.add(eid)
   result.append(dict(sample_id=source['sample_id'],source_sha256=h,example_id=eid,kind='direct',loss_weight=1.,messages=build_messages(native_record(source,level),()),completion=completion,requested_level=level))
 if not result:raise ValueError('empty direct targets')
 return result


def source_split(sources,*,similarity=source_similarity,seed=42):
 """Split source/group/near-connected components, never individual Level rows."""
 n=len(sources)
 if n<2:raise ValueError('need at least two sources')
 parents=list(range(n))
 def root(i):
  while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
  return i
 for i in range(n):
  for j in range(i):
   same_group=sources[i].get('group') and sources[i].get('group')==sources[j].get('group')
   if same_group or sources[i]['code']==sources[j]['code'] or similarity(sources[i],sources[j])>=.85:
    parents[root(i)]=root(j)
 groups={}
 for i,row in enumerate(sources):groups.setdefault(root(i),[]).append(row)
 components=sorted(groups.values(),key=lambda g:min(r['sample_id'] for r in g));random.Random(seed).shuffle(components)
 if len(components)<2:raise ValueError('all sources form one near-duplicate component')
 desired=max(1,round(n*.2));validation=[];train=[]
 for component in components:
  if len(validation)<desired and len(train)+sum(map(len,components))>len(component):validation.extend(component)
  else:train.extend(component)
 if not train:
  train=components[-1];validation=[r for g in components[:-1] for r in g]
 if not validation:raise ValueError('empty internal validation')
 return sorted(train,key=lambda r:r['sample_id']),sorted(validation,key=lambda r:r['sample_id'])


def verify_example_bindings(train_sources,val_sources,reviewed,train_examples,val_examples):
 ids=[r['sample_id'] for r in train_sources+val_sources]
 if len(ids)!=len(set(ids)):raise ValueError('training/internal validation source overlap')
 fresh=build_examples(train_sources+val_sources,reviewed)
 old=train_examples+val_examples
 def byid(rows):
  result={r['example_id']:r for r in rows}
  if len(result)!=len(rows):raise ValueError('duplicate frozen example ID')
  return result
 if byid(fresh)!=byid(old):raise ValueError('frozen source/context/target-to-example mismatch')
 train_ids={r['sample_id'] for r in train_sources};val_ids={r['sample_id'] for r in val_sources}
 if {r['sample_id'] for r in train_examples}!=train_ids or {r['sample_id'] for r in val_examples}!=val_ids:
  raise ValueError('example split/source mismatch')


def verify_hashes(mapping,*,root=REPO):
 for name,h in mapping.items():
  if sha(Path(root)/name)!=h:raise ValueError('bound file changed: '+name)


def verify_pilot():
 seal=read(FROZEN/'seal.json');manifest=read(FROZEN/'manifest.json')
 for name,h in seal['files_sha256'].items():
  if Path(name).name!=name or sha(FROZEN/name)!=h:raise ValueError('frozen direct artifact drift: '+name)
 verify_hashes(manifest['implementation_sha256'])
 verify_hashes(manifest['parent_files_sha256'])
 if sha(PUBLIC)!=manifest['public_manifest_sha256']:raise ValueError('public freeze metadata changed')
 from importlib.metadata import version
 if any(version(name)!=expected for name,expected in manifest['library_versions'].items()):raise ValueError('runtime library versions changed')
 quality=read(WORK/'review/pretrain-target-audit-v2.private.json')
 if quality.get('training_gate_pass') is not True or quality['targets_v2_sha256']!=sha(WORK/'targets/targets-reviewed-v2.private.json'):raise ValueError('target quality binding drift')
 config=read(FROZEN/'config.json')
 if config!=read(CONFIG):raise ValueError('config changed after freeze')
 sources=read(FROZEN/'train-sources.private.json');registry=read(FROZEN/'registry.private.json')
 from src.task3.direct_sft_data import require_direct_isolation
 val_sources=read(FROZEN/'validation-sources.private.json')
 require_direct_isolation(sources+val_sources,registry,stage='before_optimizer')
 examples=read(FROZEN/'train-examples.private.json');validation=read(FROZEN/'validation-examples.private.json')
 verify_example_bindings(sources,val_sources,read(WORK/'targets/targets-reviewed-v2.private.json'),examples,validation)
 return manifest,config,examples,validation,sources,registry


def prepare():
 if FROZEN.exists() or PUBLIC.exists():raise FileExistsError('direct protocol freeze exists')
 from src.task3.direct_sft_data import require_direct_isolation
 from scripts.task3_direct_sft_inventory import verify_inventory
 verify_inventory()
 config=read(CONFIG)
 from src.task3.direct_sft_training import validate_frozen_config
 validate_frozen_config(config)
 sources=read(WORK/'targets/approved-sources.private.json');reviewed=read(WORK/'targets/targets-reviewed-v2.private.json')
 registry=read(WORK/'data/registry-with-supplement.private.json')
 quality=read(WORK/'review/pretrain-target-audit-v2.private.json')
 if quality.get('training_gate_pass') is not True or quality['targets_v2_sha256']!=sha(WORK/'targets/targets-reviewed-v2.private.json'):raise ValueError('independent pretrain target quality gate not passed/bound')
 if any(set(r['source_reference'])!=set(s['taxonomy_annotation']) for s,r in zip(sources,reviewed)):raise ValueError('annotation/source target conflict')
 gate=require_direct_isolation(sources,registry,stage='before_targets')
 train,val=source_split(sources);all_examples=build_examples(sources,reviewed)
 train_ids={r['sample_id'] for r in train};val_ids={r['sample_id'] for r in val}
 if train_ids&val_ids:raise ValueError('source split overlap')
 examples=[r for r in all_examples if r['sample_id'] in train_ids];validation=[r for r in all_examples if r['sample_id'] in val_ids]
 # Read only the old sealed model-input projection, never evaluation references.
 evalroot=REPO/'outputs/task3/eval-freeze-v2-20261021/frozen'
 oldseal=read(evalroot/'seal.json')
 expected=oldseal.get('files_sha256',oldseal.get('private_files_sha256',{})).get('model-inputs.private.json')
 if expected is None:
  expected=read(REPO/'reports/task3/TASK3_EVAL_V2_FREEZE_20261021.json')['private_files_sha256']['model-inputs.private.json']
 if sha(evalroot/'model-inputs.private.json')!=expected:raise ValueError('safe development input hash mismatch')
 development=[r for r in read(evalroot/'model-inputs.private.json') if r['kind']=='primary']
 if len(development)!=60 or {r['sample_id'] for r in development}&(train_ids|val_ids):raise ValueError('development membership/leakage')
 from src.task3.inference import load_tokenizer,tokenizer_metadata
 from src.task3.direct_sft_training import encode_direct_examples
 tokenizer=load_tokenizer(config)
 _,train_audit=encode_direct_examples(tokenizer,examples,config['max_seq_length'])
 _,val_audit=encode_direct_examples(tokenizer,validation,config['max_seq_length'])
 files=['scripts/task3_direct_sft_prepare.py','scripts/task3_direct_sft_train.py','scripts/task3_direct_sft_infer.py','src/task3/direct_sft_training.py','src/task3/direct_sft_data.py','src/task3/eval_snapshot.py','src/task3/eval_v2.py','src/task3/pilot_training.py','src/task3/train.py','src/task3/round15.py','src/task3/round15_runner.py','src/task3/round15_disclosure.py','src/task3/round14.py','src/task3/round14_runner.py','src/task3/inference.py','src/task3/schema.py','src/task3/dataset.py','src/task3/runtime.py','scripts/task3_pilot_infer.py','scripts/task3_direct_sft_inventory.py']
 files=sorted(set(files)|{str(p.relative_to(REPO)) for package in ['src/task3','src/synth','src/utils'] for p in (REPO/package).glob('*.py')})
 parents=[CONFIG,REPO/'generate-dataset_v2.zip',REPO/'data/raw/round18-new/label_space.json',WORK/'review/pretrain-audit-selection.private.json',WORK/'review/pretrain-target-audit-v2.private.json',WORK/'data/registry-with-supplement.private.json',WORK/'data/inventory.private.json',WORK/'data/manifest.private.json',WORK/'data/supplement-manifest.private.json',WORK/'targets/approved-sources.private.json',WORK/'targets/targets-reviewed-v2.private.json',WORK/'targets/audit-v2.private.json',evalroot/'seal.json',evalroot/'model-inputs.private.json']
 def hist(rows):
  refs={r['sample_id']:r for r in reviewed}
  return dict(sources=len(rows),origin=dict(Counter(r['origin'] for r in rows)),clean_defect=dict(Counter(refs[r['sample_id']]['defect_status'] for r in rows)),labels=dict(Counter(label for r in rows for label in refs[r['sample_id']]['source_reference'])))
 from importlib.metadata import version
 protocol=dict(library_versions={name:version(name) for name in ('torch','transformers','peft','bitsandbytes','accelerate','datasets')},version='direct-sft-v1-20261021',head_before='709e5a2d02f8293690b7475b9dc293d8ba8d97fb',family_disjoint=False,evaluation_status='Evaluationv2 is development with prior exposure; shared family names allowed by this NEW source-level protocol; historical seals/gates unchanged.',training_signal='assistant direct final JSON only; no diagnosis/CoT/public predictions/score/public prompts',split_policy='seed42source/group/nearconnected components80/20; allLevels same source remain together',train=hist(train),validation=hist(val),examples=dict(train=len(examples),validation=len(validation)),levels=dict(train=dict(Counter(r['requested_level'] for r in examples)),validation=dict(Counter(r['requested_level'] for r in validation))),development=dict(primary=60,levels=dict(Counter(r['requested_level'] for r in development))),guard=gate,token_audit=dict(train=train_audit,validation=val_audit),tokenizer=tokenizer_metadata(tokenizer),implementation_sha256={n:sha(REPO/n) for n in files},parent_files_sha256={str(p.relative_to(REPO)):sha(p) for p in parents})
 public={k:v for k,v in protocol.items() if k not in ('tokenizer','parent_files_sha256')}
 write_new(PUBLIC,public);protocol['public_manifest_sha256']=sha(PUBLIC)
 FROZEN.mkdir()
 artifacts={'config.json':config,'train-sources.private.json':train,'validation-sources.private.json':val,'train-examples.private.json':examples,'validation-examples.private.json':validation,'registry.private.json':registry,'development-inputs.private.json':development,'protocol.json':protocol,'token-audit.json':protocol['token_audit'],'rubric.json':dict(reviewer='agent static source-grounded, not human-verified',primary='all60paired rows; missing feedback remains null',L1='no false-clean assurance on defects; disclosure tracked',L2='location+cause correct, false claim, concrete repair leak separately; strict intersection',L3='correctcause+feasible direction without complete solution',decision=dict(completion='SFT60of60 schemafinal completed; all60semanticreviews present',taxonomy='SFTmicro ANDmacro strictly higher thanBASE forBOTHannotation andsource refs',feedback='lower falseclaim countoverall; higher strictL2locationcause-without-falseclaim-or-repair rate ondefects; no greater L1falseclean; L3cause-feasiblerepair rate notlower and at leastone successfuldefectL3',failure='Anycondition fails or pending =>keepR15, no publiccandidate; no retuning'))}
 for name,value in artifacts.items():write_new(FROZEN/name,value)
 write_new(FROZEN/'manifest.json',protocol)
 write_new(FROZEN/'seal.json',dict(files_sha256={p.name:sha(p) for p in FROZEN.iterdir() if p.is_file()}))
 verify_pilot();print(json.dumps({k:protocol[k] for k in ('train','validation','examples','levels','token_audit')},ensure_ascii=False,indent=2))


def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['prepare','verify']);args=ap.parse_args()
 if args.command=='prepare':prepare()
 else:
  m,*_=verify_pilot();print(json.dumps(dict(verified=True,train=m['train'],validation=m['validation']),ensure_ascii=False))
if __name__=='__main__':main()
