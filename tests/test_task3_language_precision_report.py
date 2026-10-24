import copy
import pytest
from scripts.task3_language_precision_report import validate_rating, compare_values


def rating():
    return {'output_id':'opaque','findings':[],'detected_reference_indices':[],'main_detected':True,'finding_prose_language':'none',**{k:True for k in ['factual','faithful','main_covered','level_ok','natural_role']},**{k:False for k in ['addresses_ban','self_reference','meta','generic_placeholder','disputed']},'l1_detail_leak':False,'l2_repair_leak':None,'l3_actionable':None,'inherited_false_claims':0,'new_false_claims':0,'new_diagnoses':0,'disputes':[],'reason':'bounded praise','evidence':[{'source_quote':'int x','feedback_quote':'Em','reason':'bounded'}]}


def test_rating_bound_to_exact_output_and_source():
    u={'level':1,'task':{'code':'int x;','statement':'Read x','grading_policy':''}}
    output={'output_id':'opaque','status':'resolved','stage1':{'findings':[],'taxonomy_error':[]},'output':{'feedback':'Em đọc x.'}}
    validate_rating(rating(),u,output,0)
    r=rating();r['evidence'][0]['feedback_quote']='edited'
    with pytest.raises(ValueError):validate_rating(r,u,output,0)
    r=rating();r['detected_reference_indices']=[0]
    with pytest.raises(ValueError):validate_rating(r,u,output,0)


def test_paired_lower_is_better_and_interaction():
    per={'A':[2,1],'B':[1,1],'C':[2,0],'D':[0,1]}
    result=compare_values(per,lower=True)
    assert result['B-A']['wins']==1 and result['B-A']['ties']==1
    assert result['D-C']['wins']==1 and result['D-C']['losses']==1
    assert result['interaction_sum']==0


def test_false_claim_and_new_diagnosis_cannot_receive_good_flags():
    u={'level':1,'task':{'code':'int x;','statement':'Read x','grading_policy':''}}
    o={'output_id':'opaque','status':'resolved','stage1':{'findings':[]},'output':{'feedback':'Em đọc x.'}}
    for field in ['inherited_false_claims','new_false_claims','new_diagnoses']:
        r=rating();r[field]=1
        with pytest.raises(ValueError):validate_rating(r,u,o,0)


def test_l3_with_supported_reference_requires_actionability_rating():
    u={'level':3,'task':{'code':'int x;','statement':'Read x','grading_policy':''}}
    o={'output_id':'opaque','status':'resolved','stage1':{'findings':[{}]},'output':{'feedback':'Em đọc x.'}}
    r=rating();r['l1_detail_leak']=None;r['findings']=[{'index':0,'verdict':'correct','label_correct':True,'reference_indices':[0],'reason':'read x','source_quote':'int x'}]
    with pytest.raises(ValueError):validate_rating(r,u,o,1)


def test_material_dispute_covers_secondary_source_and_finding():
    from scripts.task3_language_precision_report import material_dispute
    a={'source_disputed':False,'source_taxonomy':[],'disputes':[]}
    b={**a,'source_taxonomy':['Lỗi logic']}
    assert material_dispute(a,b,[])
    assert material_dispute(a,None,[{'disputed':False,'disputes':[],'findings':[{'verdict':'disputed'}]}])
