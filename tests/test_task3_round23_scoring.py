from src.task3.round23_scoring import score_prediction, strict_member_success
import subprocess


def test_actual_expected_independent_and_observed_actual_never_independent_prediction():
    p={'status':'defect','input_text':'2','actual':'2','expected':'2'}
    s=score_prediction(p,{'kind':'scalar','lo':0,'hi':10},{'status':'pass'},lambda t:'2',lambda w:{'returncode':0,'stdout':'0','timeout':False,'executed':True})
    assert s['input_valid'] and not s['actual_correct']and s['expected_correct']and s['distinguishes']


def test_strict_success_requires_canonical_taxonomy_mechanism_and_witness():
    s={'input_valid':True,'actual_correct':True,'expected_correct':True,'distinguishes':True}
    assert strict_member_success('defect',s,False,True,True)
    assert not strict_member_success('defect',s,False,True,False)
    assert not strict_member_success('no_defect_in_scope',s,True,True,True)
    assert not strict_member_success('uncertain',s,False,True,True)


def test_unavailable_execution_is_not_a_runtime_error_witness():
    p={'status':'defect','input_text':'2','actual':'<runtime_error>','expected':'2'}
    scope={'kind':'scalar','lo':0,'hi':10}
    def unavailable(_):return {'returncode':1,'stdout':'','timeout':False,'executed':False}
    s=score_prediction(p,scope,{'status':'pass'},lambda t:'2',unavailable)
    assert s['input_valid'] and s['actual_correct'] is None and not s['distinguishes']
    def forbidden(_):raise AssertionError('compiler unavailable cannot execute')
    s=score_prediction(p,scope,{'status':'unavailable'},lambda t:'2',forbidden)
    assert s['actual_correct'] is None
    def broken(_):raise subprocess.SubprocessError('preexec failed')
    s=score_prediction(p,scope,{'status':'pass'},lambda t:'2',broken)
    assert s['actual_correct'] is None and not s['distinguishes']
