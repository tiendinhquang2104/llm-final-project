#!/usr/bin/env python3
"""Offline paired scoring; references are opened only after both direct arms finish."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from src.task3.frozen_eval import evaluate,output_digest
from src.task3.round15 import parse_response


def rate(value):
 return value['numerator']/value['denominator'] if value.get('denominator') else None


def candidate_decision(base,sft):
 checks=dict(semantic_complete=base.get('semantic_pending')==0 and sft.get('semantic_pending')==0 and all(not arm[key].get('pending',0) for arm in (base,sft) for key in ('l2_strict','l3_useful')),complete=sft['completed']==60,all_reviewed=base['reviewed']==60 and sft['reviewed']==60,
  taxonomy=all(sft['taxonomy'][ref][metric]>base['taxonomy'][ref][metric] for ref in ('annotation','source') for metric in ('micro','macro')),
  false_claim=sft['false_claim']<base['false_claim'],l1_false_clean=sft['l1_false_clean']<=base['l1_false_clean'],
  l2_strict=rate(sft['l2_strict']) is not None and rate(base['l2_strict']) is not None and rate(sft['l2_strict'])>rate(base['l2_strict']),
  l3_useful=rate(sft['l3_useful']) is not None and rate(base['l3_useful']) is not None and rate(sft['l3_useful'])>=rate(base['l3_useful']) and sft['l3_useful']['numerator']>=1)
 return dict(eligible=all(checks.values()),checks=checks,action='freeze method then exactly one328candidate; never submit' if all(checks.values()) else 'keepR15; no publiccandidate; no retuning')


def fraction(values):
 selected=[v for v in values if v is not None]
 return dict(numerator=sum(selected),denominator=len(selected),pending=len(values)-len(selected))


def feedback_summary(snapshot,predictions,ledger):
 byref={r['sample_id']:r for r in snapshot['records']};byreq={r['request_id']:r for r in snapshot['requests']};byreview={r['request_id']:r for r in ledger};rows=[]
 for p in predictions:
  req=byreq[p['request_id']];r=byref[req['sample_id']];review=byreview.get(p['request_id']);completed=p['status']=='completed'
  assessment=review['assessments'] if review else {}
  rows.append(dict(request_id=p['request_id'],sample_id=req['sample_id'],level=req['level'],defect=r['defect_status']=='defect',completed=completed,reviewed=completed and assessment.get('false_technical_claim') is not None,assessments=assessment))
 def summary(group):
  def values(key,select=lambda r:True):return [r['assessments'].get(key) for r in group if select(r)]
  l2=[r for r in group if r['level']==2 and r['defect']]
  strict=[]
  for r in l2:
   a=r['assessments'];keys=['l2_location_cause_useful','l2_repair_leak','false_technical_claim']
   strict.append(None if any(a.get(k) is None for k in keys) else a[keys[0]] and not a[keys[1]] and not a[keys[2]])
  def required(row):
   keys=['false_technical_claim','vietnamese','cjk']
   if row['defect']:keys+=['false_clean','missing_core_finding']
   if row['level']==1:keys+=['l1_disclosure']
   if row['level']==2:
    keys+=['l2_repair_leak']
    if row['defect']:keys+=['l2_location_cause_useful']
   if row['level']==3 and row['defect']:keys+=['l3_cause_feasible_repair']
   return keys
  semantic_pending=sum(r['assessments'].get(key) is None for r in group for key in required(r))
  return dict(semantic_pending=semantic_pending,requested=len(group),completed=sum(r['completed'] for r in group),reviewed=sum(r['reviewed'] for r in group),
   false_claim=fraction(values('false_technical_claim')),false_clean=fraction(values('false_clean',lambda r:r['defect'])),
   l1_false_clean=fraction(values('false_clean',lambda r:r['defect'] and r['level']==1)),
   missing_core=fraction(values('missing_core_finding',lambda r:r['defect'])),
   l1_disclosure=fraction(values('l1_disclosure',lambda r:r['level']==1)),
   l2_useful=fraction(values('l2_location_cause_useful',lambda r:r['level']==2 and r['defect'])),
   l2_repair_leak=fraction(values('l2_repair_leak',lambda r:r['level']==2)),l2_strict=fraction(strict),
   l3_useful=fraction(values('l3_cause_feasible_repair',lambda r:r['level']==3 and r['defect'])))
 result=summary(rows);result['by_level']={str(level):summary([r for r in rows if r['level']==level]) for level in (1,2,3,4)}
 return result


def generation_summary(folder,predictions):
 def journal(path):return [json.loads(l) for l in path.read_text().splitlines() if l] if path.exists() else []
 calls=journal(folder/'generations.jsonl');attempts=journal(folder/'legacy/attempts.jsonl');decisions=journal(folder/'legacy/decisions.jsonl')
 schema=sum(1 for c in calls if c.get('raw_text') and _valid(c['raw_text']))
 return dict(raw_calls=len(calls),schema_valid_calls=schema,input_tokens=sum(c.get('input_tokens') or 0 for c in calls),output_tokens=sum(c.get('output_tokens') or 0 for c in calls),generation_latency_s=sum(c.get('latency_s') or 0 for c in calls),extra_retry_calls=sum(max(0,n-1) for n in Counter(a['sample_id'] for a in attempts).values()),decision_reasons=dict(Counter(flag for d in decisions for flag in d.get('disclosure_violations',[]))),fallback=sum(bool(p.get('trace',{}).get('fallback_used')) for p in predictions),raw_sha256=[c.get('raw_sha256') for c in calls])


def _valid(raw):
 try:parse_response(raw);return True
 except (ValueError,TypeError):return False


def run():
 from scripts.task3_direct_sft_prepare import verify_pilot,WORK,FROZEN,read,sha,write_new
 verify_pilot()
 predictions={}
 for arm in ('BASE','SFT'):
  folder=WORK/'inference'/f'arm-{arm}';state=read(folder/'status.json')
  if state.get('complete') is not True or state.get('processed')!=60:raise ValueError('all60requests botharms required BEFORE anyreference access')
  predictions[arm]=read(folder/'predictions.json')
  if len(predictions[arm])!=60:raise ValueError('incomplete predictions')
 # Reference is retrospective only; old seal/hash remains authoritative.
 root=REPO/'outputs/task3/eval-freeze-v2-20261021/frozen';public=read(REPO/'reports/task3/TASK3_EVAL_V2_FREEZE_20261021.json')
 if sha(root/'reference.private.json')!=public['private_files_sha256']['reference.private.json']:raise ValueError('source reference drift')
 refs=read(root/'reference.private.json');inputs=read(FROZEN/'development-inputs.private.json')
 snapshot=dict(records=refs['records'],requests=[dict(request_id=r['request_id'],sample_id=r['sample_id'],level=r['requested_level'],kind='primary') for r in inputs])
 reports={};decisions={}
 for arm,preds in predictions.items():
  ledger=read(WORK/'review'/f'ledger-{arm}.private.json')
  metrics=evaluate(snapshot,preds,ledger);feedback=feedback_summary(snapshot,preds,ledger);tax=metrics['primary']
  reports[arm]=dict(metrics=metrics,feedback=feedback,generation=generation_summary(WORK/'inference'/f'arm-{arm}',preds),predictions_sha256=sha(WORK/'inference'/f'arm-{arm}'/'predictions.json'),ledger_sha256=sha(WORK/'review'/f'ledger-{arm}.private.json'),final_sha256={p['request_id']:output_digest(p['output']) if p['status']=='completed' else None for p in preds})
  decisions[arm]=dict(semantic_pending=feedback['semantic_pending'],completed=feedback['completed'],reviewed=feedback['reviewed'],taxonomy={ref:dict(micro=tax[key]['micro']['f1'],macro=tax[key]['macro']['f1']) for ref,key in [('annotation','annotation_v2'),('source','source_reference')]},false_claim=feedback['false_claim']['numerator'],l1_false_clean=feedback['l1_false_clean']['numerator'],l2_strict=feedback['l2_strict'],l3_useful=feedback['l3_useful'])
 result=dict(version='direct-sft-v1-20261021',reference_sha256=sha(root/'reference.private.json'),reports=reports,decision_inputs=decisions,decision=candidate_decision(decisions['BASE'],decisions['SFT']))
 write_new(WORK/'paired-results.private.json',result)
 print(json.dumps(dict(decision=result['decision'],summaries=decisions),ensure_ascii=False,indent=2))

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--score',action='store_true');args=parser.parse_args()
 if not args.score:parser.error('--score required')
 run()
