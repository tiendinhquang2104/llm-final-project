from src.task3.round24_metrics import summarize_review, research_gate

def test_unknown_claim_does_not_cover_defect_and_empty_is_not_precision_one():
 ref={'defects':[{'defect_id':'d','kind':'functional'}]}
 r={'claims':[{'verdict':'unknown','defect_ids':[]}],'level_compliant':False,'useful_feedback':False}
 v=summarize_review(r,ref,level=2,eligible=True);assert v['defects_found']==0 and v['claim_precision']==0
 r['claims']=[];assert summarize_review(r,ref,level=2,eligible=True)['claim_precision']is None

def test_level_one_does_not_get_mechanism_coverage_requirement():
 v=summarize_review({'claims':[],'level_compliant':True,'useful_feedback':True},{'defects':[{'defect_id':'d','kind':'functional'}]},level=1,eligible=True)
 assert v['defects_total']is None and v['defects_found']is None

def test_fallback_has_zero_substantive_credit():
 r={'claims':[{'verdict':'supported','defect_ids':['d']}],'level_compliant':True,'useful_feedback':True}
 v=summarize_review(r,{'defects':[{'defect_id':'d','kind':'functional'}]},level=3,eligible=False)
 assert v['defects_found']==0 and not v['useful_feedback'] and v['supported_claims']==0

def test_missing_taxonomy_reference_cannot_pass_research_gate():
 a={'false_accusations':2,'found_by_ID':{},'defects_found':0,'L1_disclosure':0,'L2_repair':0,'L3_useful':0,'original_micro_f1':.2,'agent_micro_f1':None,'invalid_fallback_unknown':0}
 b={**a,'false_accusations':1,'L3_useful':1}
 assert not research_gate(a,b)['passed']

def test_each_control_defect_must_be_retained_not_only_equal_total_recall():
 a={'false_accusations':2,'found_by_ID':{'id':['a']},'defects_found':1,'L1_disclosure':0,'L2_repair':0,'L3_useful':0,'original_micro_f1':.2,'agent_micro_f1':.1,'invalid_fallback_unknown':0}
 b={**a,'false_accusations':1,'found_by_ID':{'id':['b']},'L3_useful':1}
 assert not research_gate(a,b)['checks']['retain_each_control_defect']

def test_unknown_functional_reference_is_excluded_from_recall_denominator():
 ref={'functional_defect':None,'defects':[{'defect_id':'risk','kind':'functional'}]}
 r={'claims':[],'level_compliant':False,'useful_feedback':False}
 v=summarize_review(r,ref,level=2,eligible=True);assert v['defects_total']==0 and v['defects_found']==0
