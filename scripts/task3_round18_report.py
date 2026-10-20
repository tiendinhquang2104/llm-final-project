#!/usr/bin/env python3
"""Offline paired metrics and hash-bound source review. Does not call a model."""
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from scripts.task3_round18 import ROOT,verify,sha,records
from src.task3.dataset import write_json
from src.task3.round14 import object_json
from src.task3.round14_runner import digest
from src.task3.two_stage_eval import taxonomy_metrics
REPORT=REPO/'reports/task3'

def read(p):return json.loads(Path(p).read_text())
def rawsha(s):return hashlib.sha256(s.encode()).hexdigest() if s is not None else None
def log_rows(p):return [json.loads(s) for s in Path(p).read_text().splitlines()]
def two_stage(name,c):
 rr=read(ROOT/c/(name+'.private.json'));journal=log_rows(ROOT/c/(name+'.journal.jsonl'));out={}
 for r in rr:
  raw=[x for x in journal if x['sample_id']==r['sample_id'] and x['status']=='raw']
  out[r['sample_id']]={'diagnosis':r['diagnosis'],'levels':r['levels'],'errors':r['errors'],'raw':raw}
 return out

def main():
 freeze=verify();review=read(REPO/'configs/task3/r18_source_review.json');goldrecords=records('evaluation');gold={r.sample_id:r.gold_taxonomy for r in goldrecords}
 source={x['sample_id']:x['labels'] for x in freeze['sets']['evaluation']};source_notes={x['sample_id']:x['evidence'] for x in freeze['sets']['evaluation']}
 source_notes['SYN-FACT-0009']='Corrected before paired inference: n=5 rounded Stirling118 vs factorial120; original n=4 prose wrong. See data audit errata.'
 a=read(ROOT/'A-evaluation/progress.json');stages={'B':two_stage('evaluation','B'),'C':two_stage('evaluation','C')};tables=[];outputs={c:{} for c in 'ABC'};metrics={}
 for r in goldrecords:
  sid=r.sample_id;level=freeze['evaluation_levels'][sid];row={'sample_id':sid,'family':r.exam_id,'level':level,'source_sha256':hashlib.sha256(r.code.encode()).hexdigest(),'source_expected':source[sid],'source_evidence':source_notes[sid],'annotation_v2':gold[sid],'conditions':{}}
  for c in 'ABC':
   annotations=review['evaluation'][sid][c]
   if c=='A':
    entry=a['completed'].get(sid);out=entry['output'] if entry else None;trace=entry['trace'] if entry else a['errors'][sid]['trace'];raws=trace['attempts'];diag=None;errors=[];finalraw=raws[-1]['raw_text'];fallback=trace['fallback_used']
    tax=[]
    for x in raws:
     try:tax.append(object_json(x['raw_text']).get('taxonomy_error'))
     except ValueError:tax.append(None)
    transitions=sum(x is not None and y is not None and set(x)!=set(y) for x,y in zip(tax,tax[1:]))
   else:
    entry=stages[c][sid];diag=entry['diagnosis'];out=entry['levels'].get(str(level));raws=entry['raw'];errors=entry['errors'];finalraw=next((x['raw_text'] for x in raws if x['stage']=='feedback'),None);fallback=False;transitions=0
   outputs[c][sid]=out
   json_failures=0
   for x in raws:
    try:object_json(x['raw_text'])
    except ValueError:json_failures+=1
   condition={'final_taxonomy':out['taxonomy_error'] if out else None,'diagnostic_taxonomy':diag['taxonomy_error'] if diag else None,'completed':out is not None,'errors':errors,'fallback':fallback,'raw_hashes':[{'stage':x.get('stage','joint'),'raw_utf8_sha256':rawsha(x['raw_text']),'prompt_sha256':x.get('prompt_sha256')} for x in raws],'final_sha256':digest(out) if out else None,'diagnosis_sha256':digest(diag) if diag else None,'json_failed_attempts':json_failures,'attempts':len(raws),'retry_taxonomy_transitions':transitions,**annotations}
   row['conditions'][c]=condition
  tables.append(row)
 for c in 'ABC':
  rows=[t['conditions'][c] for t in tables]
  metrics[c]={'taxonomy_v2':taxonomy_metrics(gold,outputs[c]),'taxonomy_source_reference':taxonomy_metrics(source,outputs[c]),'raw_attempts':sum(r['attempts'] for r in rows),'json_failed_attempts':sum(r['json_failed_attempts'] for r in rows),'unresolved_records':sum(not r['completed'] for r in rows),'fallback':sum(r['fallback'] for r in rows),'retry_taxonomy_transitions':sum(r['retry_taxonomy_transitions'] for r in rows),'false_claim_first_joint_or_diagnosis':sum(bool(r.get('false_claim_first') or r.get('false_claim_diagnosis')) for r in rows),'false_claim_any_raw':sum(bool(r.get('false_claim_first') or r.get('false_claim_diagnosis') or r.get('false_claim_final') or r.get('false_claim_feedback_raw')) for r in rows),'false_claim_final':sum(bool(r.get('false_claim_final')) for r in rows),'false_clean_first_joint_or_diagnosis':sum(bool(r.get('false_clean_first') or r.get('false_clean_diagnosis')) for r in rows),'false_clean_final':sum(bool(r.get('false_clean_final')) for r in rows),'empty_on_confirmed_defect':sum(bool(t['source_expected']) and outputs[c][t['sample_id']] is not None and not outputs[c][t['sample_id']]['taxonomy_error'] for t in tables),'per_level':{}}
  for level in (1,2,3,4):
   selected=[t for t in tables if t['level']==level];denom=sum(bool(t['source_expected']) for t in selected);rr=[t['conditions'][c] for t in selected]
   metrics[c]['per_level'][level]={'requested':len(rr),'confirmed_defect_denominator':denom,'completed':sum(r['completed'] for r in rr),'empty_taxonomy':sum(r['completed'] and not r['final_taxonomy'] for r in rr),'false_claim_final':sum(bool(r.get('false_claim_final')) for r in rr),'false_clean_final':sum(bool(r.get('false_clean_final')) for r in rr),'l1_disclosure_final':sum(bool(r.get('l1_disclosure')) for r in rr) if level==1 else None,'l2_strict_useful':sum(bool(r.get('l2_useful')) for r in rr) if level==2 else None,'l2_repair_leak':sum(bool(r.get('l2_leak')) for r in rr) if level==2 else None,'l3_strict_useful':sum(bool(r.get('l3_useful')) for r in rr) if level==3 else None,'l3_conditional_useful':sum(bool(r.get('l3_conditional_useful')) for r in rr) if level==3 else None}
 # Counterfactual: full feedback and all raw attempts remain private; ledger
 # includes hashes, taxonomy, source-evidence pointer and human-readable review.
 old=read(ROOT/'A-results.private.json');new=two_stage('counterfactual','B');cf=[]
 for item in old['per_id']:
  sid=item['sample_id'];b=new[sid];judgment=review['counterfactual'][sid];entry={'sample_id':sid,'first_set_invariant_A':item['first_invariant'],'final_set_invariant_A':item['final_invariant'],'source_evidence':next(x['evidence'] for x in freeze['sets']['counterfactual'] if x['sample_id']==sid),'source_review':judgment,'A':[],'B':{'diagnosis_taxonomy':b['diagnosis']['taxonomy_error'] if b['diagnosis'] else None,'diagnosis_sha256':digest(b['diagnosis']) if b['diagnosis'] else None,'errors':b['errors'],'levels':{},'raw_hashes':[{'stage':x['stage'],'level':x['requested_level'],'raw_utf8_sha256':rawsha(x['raw_text'])} for x in b['raw']]}}
  state=read(ROOT/'A-counterfactual/progress.json')
  for levelrow in item['levels']:
   level=levelrow['level'];output=levelrow['final'];trace=state['completed'][sid+'@L'+str(level)]['trace']
   entry['A'].append({'level':level,'attempt_taxonomies':[x['output']['taxonomy_error'] if x['output'] else None for x in levelrow['attempts']],'final_taxonomy':output['taxonomy_error'] if output else None,'raw_utf8_sha256':[rawsha(x['raw_text']) for x in trace['attempts']],'final_sha256':digest(output),'origin':levelrow['origin'],'fallback':levelrow['fallback'],'false_claim_final':level in judgment.get('A_false_final',[]),'false_claim_any_raw':level in judgment.get('A_false_raw',[]),'false_clean_final':bool(next(x['labels'] for x in freeze['sets']['counterfactual'] if x['sample_id']==sid)) and not output['taxonomy_error']})
  for level,out in b['levels'].items():
   entry['B']['levels'][level]={'taxonomy':out['taxonomy_error'],'final_sha256':digest(out),'false_claim_final':int(level) in judgment.get('B_false_final',[])}
  entry['B']['complete_triple']=all(str(i) in b['levels'] for i in (1,2,3))
  entry['B']['invariant_complete_triple']=entry['B']['complete_triple'] and len({tuple(sorted(b['levels'][str(i)]['taxonomy_error'])) for i in (1,2,3)})==1
  cf.append(entry)
 cfs={'A':{k:v for k,v in old.items() if k!='per_id'},'B':{'diagnoses_accepted':sum(r['B']['diagnosis_taxonomy'] is not None for r in cf),'diagnoses_failed':sum(r['B']['diagnosis_taxonomy'] is None for r in cf),'completed_level_requests':sum(len(r['B']['levels']) for r in cf),'requested_level_requests':64,'complete_triples':sum(r['B']['complete_triple'] for r in cf),'invariant_complete_triples':sum(r['B']['invariant_complete_triple'] for r in cf),'taxonomy_copied_on_every_completed_output':all(v['taxonomy']==r['B']['diagnosis_taxonomy'] for r in cf for v in r['B']['levels'].values()),'empty_by_level':{l:sum(str(l) in r['B']['levels'] and not r['B']['levels'][str(l)]['taxonomy'] for r in cf) for l in (1,2,3,4)}}}
 result={'decision':'retain_R15_baseline_no_candidate','pilot_eligibility':'INVALID_HISTORICAL_EVALUATION_LEAKAGE','reviewer':review['reviewer'],'metric_policy':'10 labels fixed, zero_division0; unresolved decisions penalized as no positives for TP/FP/FN but never awarded clean exact set and never exported as[]; source reference is assistant reviewed and mapping-sensitive; primary official agreement uses unchanged v2','hash_policy':'raw_utf8_sha256 hashes exact text UTF8; final/diagnosis_sha256 uses repository digest sorted-key ensure_ascii=False JSON with default separators','review_scope':'A every first/retry/final; B/C every diagnosis raw, feedback raw and accepted final, including rejected schema. No inference reruns for content. Record-level material false claim, not atomic precision. Unsupported domain/checker assumptions distinguished from source-refuted claims. All manually assistant-reviewed, not human verified.','source_review_sha256':sha(REPO/'configs/task3/r18_source_review.json'),'counterfactual':cfs,'paired_metrics':metrics,'paired_per_id':tables,'counterfactual_per_id':cf}
 write_json(REPORT/'TASK3_ROUND18_RESULTS_20261020.json',result)
 write_json(ROOT/'results.json',result)
 print(json.dumps({'counterfactual':cfs,'paired':{c:{k:v for k,v in m.items() if not k.startswith('taxonomy') and k!='per_level'} for c,m in metrics.items()},'v2':{c:{k:m['taxonomy_v2'][k] for k in ('micro_f1','macro_f1','exact_set_count','completed')} for c,m in metrics.items()}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
