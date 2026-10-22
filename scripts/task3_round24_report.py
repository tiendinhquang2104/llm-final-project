#!/usr/bin/env python3
"""Recompute Round24 metrics from sealed source and per-claim reviews; no model."""
from pathlib import Path
import json,sys,collections,csv
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R));W=R/'outputs/task3/round24-20261022'
from src.task3.feedback_prompt import verify_seal,digest,sha
from src.task3.round24_review import taxonomy_metrics,validate_reference,validate_claim_review,public_decision
from src.task3.round24_audit import validate_defect_links,audit_completion
from src.task3.round24_metrics import summarize_review,research_gate
from src.task3.dataset import write_json
read=lambda p:json.loads((W/p).read_text())

def main():
 for name in ['selection-freeze.json','review-freeze.json','baseline-review-freeze.json','rulebook-freeze.json','prompt-freeze.json','adjudication-freeze.json']:verify_seal(W/name)
 sources={s['record']['sample_id']:s for s in read('sources.private.json')};refs={r['original_id']:r for r in read('reference-rulebook-v2.private.json')};records=read('model-inputs.private.json');reviews=read('all-claims.private.json');reviewby={(r['sample_id'],r['arm']):r for r in reviews};human=read('human-decisions.private.json')
 assert len(reviewby)==len(reviews)==120
 outputs={a:{r['sample_id']:r['output']for r in read(a+'/completed.predictions.json')}for a in ['R15','C']};traces={a:{r['sample_id']:r for r in read(a+'/traces.json')}for a in ['R15','C']}
 for arm in ['R15','C']:audit_completion({r['sample_id']for r in records},outputs[arm],traces[arm],read(arm+'/run.json')['errors'])
 rows=[]
 for r in records:
  source=sources[r['original_submission_id']];ref=refs[r['original_submission_id']];validate_reference(ref,r['code']);ref={**ref,'functional_defect':ref.get('functional_status_for_scoring',ref['functional_defect'])};row={'sample_id':r['sample_id'],'original_id':r['original_submission_id'],'family':r['exam_id'],'split':source['split'],'level':int(r['target_feedback_level'][6]),'source_sha256':source['source_sha256'],'original_gold':source['record']['gold_taxonomy'],'reference_status':ref['taxonomy_status'],'functional_defect':ref['functional_defect'],'synthetic_mutant':source['record']['source']=='synthetic'and bool(set(source['record']['gold_taxonomy'])-{'Lỗi style'})and ref['functional_defect']is True,'arms':{}}
  for arm in ['R15','C']:
   output=outputs[arm].get(r['sample_id']);trace=traces[arm].get(r['sample_id']);rv=reviewby[r['sample_id'],arm]
   assert rv['output_sha256']==digest(output);validate_claim_review(rv,output or {'feedback':''},r['code'],ref);validate_defect_links(rv,ref,r['code'])
   eligible=output is not None and trace is not None and not trace['fallback_used']
   known_clean=ref['functional_defect']is False;labels=output['taxonomy_error']if eligible else None
   functional_label_claim=bool(labels and set(labels)-{'Lỗi style'})
   summary=summarize_review(rv,ref,level=row['level'],eligible=eligible)
   fa=bool(known_clean and eligible and (rv['false_functional_accusation']is True or functional_label_claim))
   a={'output':output,'eligible':eligible,'fallback':bool(trace and trace['fallback_used']),'labels_for_scoring':labels,'original_exact':labels is not None and set(labels)==set(source['record']['gold_taxonomy']),'agent_confirmed_exact':labels is not None and set(labels)==set(ref['reference_taxonomy'])if ref['taxonomy_status']=='confirmed'else None,'binary_defect_detected':bool(eligible and functional_label_claim),'false_accusation':fa,'false_clean':bool(eligible and ref['functional_defect']is True and rv['false_clean']),'review':rv,'summary':summary}
   row['arms'][arm]=a
  rows.append(row)
 result={}
 for split in ['all','development','confirmation']:
  subset=[r for r in rows if split=='all'or r['split']==split];result[split]={}
  for arm in ['R15','C']:
   values=[r['arms'][arm]for r in subset];original=[{'prediction':r['arms'][arm]['labels_for_scoring'],'reference':r['original_gold']}for r in subset];confirmed=[{'prediction':r['arms'][arm]['labels_for_scoring'],'reference':refs[r['original_id']]['reference_taxonomy']}for r in subset if r['reference_status']=='confirmed'];hs={r['original_id']:r for r in human if r.get('human_verified')is True and r.get('taxonomy_error')is not None};hp=[{'prediction':r['arms'][arm]['labels_for_scoring'],'reference':hs[r['original_id']]['taxonomy_error']}for r in subset if r['original_id']in hs]
   totals={k:sum(a['summary'][k]or 0 for a in values)for k in ['claims','supported_claims','false_claims','unsupported_claims','unknown_claims','defects_total','defects_found']}
   totals.update(claim_precision=totals['supported_claims']/totals['claims']if totals['claims']else None,defect_recall_L2_L3=totals['defects_found']/totals['defects_total']if totals['defects_total']else None)
   levels={}
   for lev in [1,2,3]:
    selected=[r['arms'][arm]for r in subset if r['level']==lev];levels[str(lev)]={'IDs':len(selected),'compliant':sum(a['summary']['level_compliant']for a in selected),'useful':sum(a['summary']['useful_feedback']for a in selected),'disclosure':sum(a['review']['Level1_disclosure']if lev==1 else a['review']['Level2_repair']if lev==2 else a['review']['Level3_missing_repair']for a in selected),'harmful_repair':sum(a['review']['harmful_repair']for a in selected)}
   result[split][arm]={'IDs':len(subset),'sources':len({r['original_id']for r in subset}),'original_taxonomy':taxonomy_metrics(original),'agent_confirmed_taxonomy':taxonomy_metrics(confirmed),'human_confirmed_taxonomy':taxonomy_metrics(hp),'disputed_taxonomy_IDs':sum(r['reference_status']=='disputed'for r in subset),'unknown_taxonomy_IDs':sum(r['reference_status']=='unknown'for r in subset),'binary_detection':{'known_defect_IDs':sum(r['functional_defect']is True for r in subset),'detected_known_defects':sum(r['functional_defect']is True and r['arms'][arm]['binary_defect_detected']for r in subset),'synthetic_mutant_IDs':sum(r['synthetic_mutant']for r in subset),'detected_synthetic_mutants':sum(r['synthetic_mutant']and r['arms'][arm]['binary_defect_detected']for r in subset)},'known_clean_IDs':sum(r['functional_defect']is False for r in subset),'unknown_functional_IDs':sum(r['functional_defect']is None for r in subset),'false_accusations':sum(a['false_accusation']for a in values),'false_clean':sum(a['false_clean']for a in values),'invalid':sum(a['output']is None for a in values),'fallback':sum(a['fallback']for a in values),'material_unknown':sum(a['review']['material_unknown']for a in values),'claims_and_coverage':totals,'levels':levels}
 def gate_input(arm):
  a=result['confirmation'][arm];return {'false_accusations':a['false_accusations'],'found_by_ID':{r['sample_id']:r['arms'][arm]['summary']['found_defect_ids']for r in rows if r['split']=='confirmation'and r['level']>=2},'defects_found':a['claims_and_coverage']['defects_found'],'L1_disclosure':a['levels']['1']['disclosure'],'L2_repair':a['levels']['2']['disclosure'],'L3_useful':a['levels']['3']['useful'],'original_micro_f1':a['original_taxonomy']['micro_f1'],'agent_micro_f1':a['agent_confirmed_taxonomy']['micro_f1'],'invalid_fallback_unknown':a['invalid']+a['fallback']+a['material_unknown']}
 gate=research_gate(gate_input('R15'),gate_input('C'));decision=public_decision(research_passed=gate['passed'],independent_confirmation=False,human_decisions=human,unresolved_disputes=sum(r['taxonomy_status']!='confirmed'for r in refs.values()))
 costs={}
 for arm in ['R15','C']:
  attempts=[json.loads(l)for l in (W/arm/'attempts.jsonl').read_text().splitlines()];costs[arm]={'calls':len(attempts),'input_tokens':sum(a['input_tokens']for a in attempts),'output_tokens':sum(a['output_tokens']for a in attempts),'generation_latency_s':sum(a['latency_s']for a in attempts)}
 report={'splits':result,'research_gate':gate,'decision':decision,'costs':costs,'authority':'independent agent review, not human-verified','human_confirmed_sources':len(human),'independent_confirmation':False,'program_execution':False,'training':False,'public_inference':False,'prompt_freeze_sha256':sha(W/'prompt-freeze.json'),'adjudication_freeze_sha256':sha(W/'adjudication-freeze.json')}
 write_json(W/'id-metrics.private.json',rows);write_json(W/'metrics.json',report);write_json(R/'reports/task3/TASK3_ROUND24_RESULTS_20261022.json',report)
 with (W/'id-metrics.private.csv').open('w')as f:
  fields=['sample_id','original_id','family','split','level','source_sha256','reference_status','functional_defect','arm','eligible','fallback','original_exact','agent_confirmed_exact','false_accusation','false_clean','claims','supported_claims','false_claims','unsupported_claims','unknown_claims','defects_total','defects_found','level_compliant','useful_feedback'];writer=csv.DictWriter(f,fields);writer.writeheader()
  for row in rows:
   for arm,a in row['arms'].items():
    v={k:row[k]for k in fields if k in row};v.update(arm=arm,**{k:a[k]for k in ['eligible','fallback','original_exact','agent_confirmed_exact','false_accusation','false_clean']});v.update({k:a['summary'][k]for k in ['claims','supported_claims','false_claims','unsupported_claims','unknown_claims','defects_total','defects_found','level_compliant','useful_feedback']});writer.writerow(v)
 print(json.dumps({'gate':gate,'decision':decision,'costs':costs},ensure_ascii=False))
 return 0
if __name__=='__main__':raise SystemExit(main())
