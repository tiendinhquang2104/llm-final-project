import pytest
from src.task3 import grounded_metrics as m


def test_macro_uses_all_ten_labels_invalid_is_not_clean():
    refs=[['Lỗi logic'],[]]
    a=m.taxonomy_metrics(refs,[['Lỗi logic'],None])
    assert a['macro_f1']==pytest.approx(0.1)
    assert a['micro_f1']==1.0 and a['exact_match']==0.5
    assert a['invalid']==1 and a['empty_predictions']==0
    assert a['per_label']['Lỗi logic']['TP']==1


def test_false_clean_and_multilabel_counts():
    a=m.taxonomy_metrics([['Lỗi logic','Lỗi hàm'],[]],[[],['Lỗi vòng lặp']])
    assert a['false_clean']==1 and a['FN']==2 and a['FP']==1
    assert a['per_label']['Lỗi hàm']['support']==1


def test_joint_fails_disputed_level_and_unresolved():
    review=dict(finding_supported='yes',taxonomy_missing=[],taxonomy_extra=[],
                main_error_covered_in_feedback='yes',feedback_false_claim='no',
                feedback_taxonomy_consistent='yes',level_compliant='yes')
    assert m.joint_pass(review,True)
    assert not m.joint_pass({**review,'finding_supported':'disputed'},True)
    assert not m.joint_pass({**review,'level_compliant':'no'},True)
    assert not m.joint_pass(review,False)


def test_gate_cannot_choose_smooth_but_incomplete_candidate():
    base=dict(completed=60,joint_pass=5,serious_L1_L2_leaks=0,micro_f1=.2,false_claims=1,false_clean=3,rare_tp={'Lỗi style':1})
    cand={**base,'completed':59,'joint_pass':55}
    gate=dict(minimum_joint_gain_samples=3,maximum_micro_f1_drop=.02)
    assert not m.winner_gate(base,cand,gate)['passed']
    assert not m.winner_gate(base,{**base,'joint_pass':9,'rare_tp':{'Lỗi style':0}},gate)['passed']
