#!/usr/bin/env python3
"""Read-only full-payload/native provenance and protected-byte verification."""
from pathlib import Path
import sys,json,argparse
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R));W=R/'outputs/task3/round24-20261022'
from src.task3.feedback_prompt import verify_seal,sha
from src.task3.round24_audit import audit_model_payload,audit_completion
from src.task3.schema import Task3Record
from src.task3.dataset import write_json
from src.task3.round24_prompt import messages
read=lambda p:json.loads((W/p).read_text())

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--phase',choices=['preC','final'],required=True);args=ap.parse_args()
 for seal in ['selection-freeze.json','review-freeze.json','rulebook-freeze.json','baseline-review-freeze.json']:verify_seal(W/seal)
 if args.phase=='final':verify_seal(W/'prompt-freeze.json')
 protected=read('protected-before.private.json');drift=[p for p,h in protected.items()if not (R/p).is_file()or sha(R/p)!=h]
 if drift:raise ValueError('protected bytes changed: '+str(drift))
 records={r['sample_id']:Task3Record(**r)for r in read('model-inputs.private.json')};sources={s['record']['sample_id']:Task3Record(**s['record'])for s in read('sources.private.json')};frozen={r['sample_id']:r for r in read('frozen-initial-prompts.private.json')}
 if len(records)!=60 or set(records)!=set(frozen):raise ValueError('query set mismatch')
 for sid,rec in records.items():
  for arm in ['R15','C']:
   expected=messages(rec,[],arm=arm)
   if expected!=frozen[sid][arm]:raise ValueError('initial prompt differs from frozen')
   audit_model_payload(json.loads(expected[1]['content']),sources[rec.original_submission_id],int(rec.target_feedback_level[6]))
 calls={}
 for arm in (['R15']if args.phase=='preC'else ['R15','C']):
  prediction_rows=read(arm+'/completed.predictions.json');trace_rows=read(arm+'/traces.json');outputs={r['sample_id']:r['output']for r in prediction_rows};traces={r['sample_id']:r for r in trace_rows};run=read(arm+'/run.json');audit_completion(records,outputs,traces,run['errors'])
  if len(prediction_rows)!=len(outputs)or len(trace_rows)!=len(traces):raise ValueError('duplicate native output/trace')
  journal=[json.loads(l)for l in (W/arm/'attempts.jsonl').read_text().splitlines()]
  for a in journal:
   sid=a['sample_id'];initial=frozen[sid][arm]
   if a['prompt_messages'][:2]!=initial or len(a['prompt_messages'])not in [2,3]:raise ValueError('native attempt prompt changed')
   if not 1<=a['attempt']<=3:raise ValueError('unbounded native retry')
   audit_model_payload(json.loads(a['prompt_messages'][1]['content']),sources[records[sid].original_submission_id],int(records[sid].target_feedback_level[6]))
  if sum(len(t['attempts'])for t in traces.values())+sum(len(e['trace']['attempts'])for e in run['errors'].values())!=len(journal):raise ValueError('journal/trace coverage mismatch')
  for sid,t in traces.items():
   if t['attempts']!=[a for a in journal if a['sample_id']==sid]:raise ValueError('trace differs from durable raw journal')
  rt=run['runtime'];cfg=run['config']
  if run['replay']or run['tokenizer']['mock']or cfg['model_id']!='Qwen/Qwen2.5-Coder-7B-Instruct'or cfg['revision']!='c03e6d358207e414f1eca0bb1891e29f1db0e242'or cfg.get('adapter'):raise ValueError('model identity')
  if rt['actual_precision']!='nf4'or not rt['is_loaded_in_4bit']or set(rt['parameter_storage_elements_by_device'])!={'cuda:0'}or rt['quantized_compute_dtypes']!=['torch.bfloat16']:raise ValueError('runtime precision/device drift')
  if run['program_execution']or run['training']or run['new_renderer']:raise ValueError('forbidden added intervention')
  calls[arm]=len(journal)
 if args.phase=='final':
  a=read('R15/run.json')['config'];b=read('C/run.json')['config']
  if {k:v for k,v in a.items()if k!='offline_arm'}!={k:v for k,v in b.items()if k!='offline_arm'}:raise ValueError('model generation config differs between arms')
  if (W/'adjudication-freeze.json').exists():verify_seal(W/'adjudication-freeze.json')
 report={'passed':True,'phase':args.phase,'query_IDs':60,'source_packets':20,'full_initial_payloads_verified':120,'actual_native_calls_verified':calls,'protected_files_unchanged':len(protected),'program_execution':False,'new_renderer':False,'training':False,'human_verification_claimed':False}
 write_json(W/('payload-audit-preC.private.json'if args.phase=='preC'else 'completion-audit.private.json'),report);print(json.dumps(report));return 0
if __name__=='__main__':raise SystemExit(main())
