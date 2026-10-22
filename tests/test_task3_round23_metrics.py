import pytest
from src.task3.round23_metrics import gate_result,validate_rows, pair_counts, trustworthy_witness


def rows():
    result=[]
    for i in range(40):
        for role in ['base','mutant']:
            result.append({'pair_id':str(i),'sample_id':f'{i}-{role}','role':role,'split':'development'if i<24 else'evaluation','arms':{a:{'content_success':True,'strict_success':False}for a in ['R15','self','execution']}})
    return result


def test_pair_denominators_keep_every_id_and_failure():
    data=rows();validate_rows(data)
    assert pair_counts(data,'R15','content_success','evaluation')=={'pairs':16,'successes':16,'accuracy':1.0}
    assert pair_counts(data,'self','strict_success','evaluation')['successes']==0
    data[-1]['sample_id']=data[0]['sample_id']
    with pytest.raises(ValueError):validate_rows(data)


def test_gate_requires_witness_gain_and_no_extra_false_clean():
    cfg={'minimum_strict_pair_successes':8,'minimum_gain_over_R15_exact_taxonomy_pairs':2,'minimum_trustworthy_mutant_witnesses':12,'additional_mutant_false_clean_allowed':0}
    assert gate_result(cfg,3,8,12,1,1)['passed']
    assert not gate_result(cfg,3,8,11,1,1)['passed']
    assert not gate_result(cfg,7,8,12,1,1)['passed']
    assert not gate_result(cfg,3,8,12,2,1)['passed']


def test_numeric_witness_metric_is_separate_from_semantic_and_taxonomy_scores():
    assert trustworthy_witness({'input_valid':True,'actual_correct':True,'expected_correct':True,'distinguishes':True})
    assert not trustworthy_witness({'input_valid':True,'actual_correct':None,'expected_correct':True,'distinguishes':True})
