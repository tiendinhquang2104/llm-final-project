import pytest
from src.task3.round24_review import taxonomy_metrics,validate_reference,validate_claim_review,public_decision

LABEL='Lỗi logic'
def test_empty_confirmed_subset_is_na_not_perfect():
 assert taxonomy_metrics([])['micro_f1'] is None

def test_invalid_empty_prediction_is_not_correct_clean():
 m=taxonomy_metrics([{'prediction':None,'reference':[]}]);assert m['exact']==0 and m['invalid']==1

def test_every_official_label_has_separate_confusion_counts():
 m=taxonomy_metrics([{'prediction':['Lỗi vòng lặp'],'reference':[LABEL]}]);assert len(m['per_label'])==10
 assert m['per_label'][LABEL]['FN']==1 and m['per_label']['Lỗi vòng lặp']['FP']==1

def test_original_and_confirmed_references_are_not_interchangeable():
 a=taxonomy_metrics([{'prediction':[LABEL],'reference':['Lỗi vòng lặp']}]);b=taxonomy_metrics([{'prediction':[LABEL],'reference':[LABEL]}]);assert a['exact']==0 and b['exact']==1

def test_disputed_reference_cannot_be_silently_confirmed():
 ref={'taxonomy_status':'disputed','reference_taxonomy':[LABEL],'functional_defect':True,'defects':[],'human_verified':False}
 with pytest.raises(ValueError):validate_reference(ref,'int x;')

def test_source_quote_must_exist():
 ref={'taxonomy_status':'confirmed','reference_taxonomy':[LABEL],'functional_defect':True,'defects':[{'defect_id':'d','source_quote':'not source','taxonomy_options':[[LABEL]]}],'human_verified':False}
 with pytest.raises(ValueError):validate_reference(ref,'int x;')

def test_claim_cannot_quote_invented_feedback_or_cover_unknown_defect():
 ref={'defects':[{'defect_id':'d'}]}; review={'claims':[{'feedback_quote':'invented','source_quote':'x','verdict':'supported','defect_ids':['d']}]}
 with pytest.raises(ValueError):validate_claim_review(review,{'feedback':'actual'},'int x;',ref)
 review['claims'][0]['feedback_quote']='actual';review['claims'][0]['defect_ids']=['unknown']
 with pytest.raises(ValueError):validate_claim_review(review,{'feedback':'actual'},'int x;',ref)

def test_agent_review_is_never_human_authority():
 result=public_decision(research_passed=True,independent_confirmation=False,human_decisions=[],unresolved_disputes=2)
 assert not result['select_public_candidate'] and result['production']=='R15'

def test_train_projection_rejects_gold_and_source_replacement():
 from src.task3.round24_review import validate_projection
 source={'record':{'sample_id':'S','source':'real','code':'int x;','exam_id':'E'},'split':'development'}
 record={'sample_id':'R-L1','original_submission_id':'S','source':'real','code':'int x;','exam_id':'E','gold_taxonomy':None,'gold_feedback':None,'split':'round24-development','target_feedback_level':'Level 1 - Gợi ý nhẹ'}
 validate_projection([record],[source],expected_levels=[1])
 record['gold_taxonomy']=[]
 with pytest.raises(ValueError):validate_projection([record],[source],expected_levels=[1])
 record['gold_taxonomy']=None;record['code']='other'
 with pytest.raises(ValueError):validate_projection([record],[source],expected_levels=[1])

def test_train_projection_clones_cannot_cross_family_split():
 from src.task3.round24_review import validate_projection
 source={'record':{'sample_id':'S','source':'real','code':'int x;','exam_id':'E'},'split':'development'}
 record={'sample_id':'R-L1','original_submission_id':'S','source':'real','code':'int x;','exam_id':'E','gold_taxonomy':None,'gold_feedback':None,'split':'round24-confirmation','target_feedback_level':'Level 1 - Gợi ý nhẹ'}
 with pytest.raises(ValueError):validate_projection([record],[source],expected_levels=[1])
