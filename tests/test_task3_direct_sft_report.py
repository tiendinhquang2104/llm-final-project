"""Synthetic decision fixtures; feedback and taxonomy must both improve."""
from scripts.task3_direct_sft_report import candidate_decision

def summary():
 return dict(semantic_pending=0,completed=60,reviewed=60,taxonomy=dict(annotation=dict(micro=.2,macro=.1),source=dict(micro=.2,macro=.1)),false_claim=10,l1_false_clean=2,l2_strict=dict(numerator=3,denominator=10),l3_useful=dict(numerator=1,denominator=4))

def test_f1_only_cannot_authorize_public():
 a=summary();b=summary();b['taxonomy']={k:dict(micro=.4,macro=.2) for k in ('annotation','source')}
 assert not candidate_decision(a,b)['eligible']

def test_pending_or_incomplete_blocks_candidate():
 a=summary();b=summary();b.update(completed=59,reviewed=59,false_claim=5,l2_strict=dict(numerator=6,denominator=10))
 b['taxonomy']={k:dict(micro=.4,macro=.2) for k in ('annotation','source')}
 assert not candidate_decision(a,b)['eligible']

def test_all_predeclared_conditions_required():
 a=summary();b=summary();b.update(false_claim=5,l2_strict=dict(numerator=6,denominator=10))
 b['taxonomy']={k:dict(micro=.4,macro=.2) for k in ('annotation','source')}
 assert candidate_decision(a,b)['eligible']
 b['l1_false_clean']=3
 assert not candidate_decision(a,b)['eligible']

def test_generation_report_reads_actual_native_trace_fields(tmp_path):
 import json
 from scripts.task3_direct_sft_report import generation_summary
 (tmp_path/'legacy').mkdir()
 calls=[dict(raw_text='{"taxonomy_error":[],"feedback":"x"}',input_tokens=5,output_tokens=2,latency_s=.1)]
 (tmp_path/'generations.jsonl').write_text('\n'.join(json.dumps(x) for x in calls))
 (tmp_path/'legacy/attempts.jsonl').write_text('\n'.join(json.dumps(dict(sample_id='fixture')) for _ in range(3)))
 (tmp_path/'legacy/decisions.jsonl').write_text(json.dumps(dict(disclosure_violations=['explicit_repair_disclosure'])))
 r=generation_summary(tmp_path,[dict(trace=dict(fallback_used=True))])
 assert r['fallback']==1 and r['extra_retry_calls']==2
 assert r['decision_reasons']=={'explicit_repair_disclosure':1}

def test_pending_relevant_semantics_block_even_if_false_claim_reviewed():
 a=summary();b=summary();b.update(false_claim=5,l2_strict=dict(numerator=1,denominator=1,pending=9))
 b['taxonomy']={k:dict(micro=.4,macro=.2) for k in ('annotation','source')}
 assert not candidate_decision(a,b)['eligible']
 b['l2_strict']=dict(numerator=6,denominator=10,pending=0)
 b['semantic_pending']=1
 assert not candidate_decision(a,b)['eligible']
