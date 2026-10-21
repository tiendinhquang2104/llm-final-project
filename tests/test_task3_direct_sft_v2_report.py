"""Artificial three-arm decision fixtures; no student/development content."""
from copy import deepcopy
import pytest


def arm():
    return dict(completed=60, reviewed=60, semantic_pending=0,
                taxonomy={ref: dict(micro=.2, macro=.1) for ref in ('annotation', 'source')},
                false_claim=30, l1_false_clean=5,
                l2_useful=dict(numerator=5, denominator=20, pending=0),
                l2_strict=dict(numerator=3, denominator=20, pending=0),
                l3_useful=dict(numerator=1, denominator=6, pending=0))


def arms():
    base=arm();v1=arm();v2=arm()
    v1.update(false_claim=15,l1_false_clean=0)
    v1['taxonomy']={ref:dict(micro=.5,macro=.4) for ref in ('annotation','source')}
    v1['l2_strict']['numerator']=4
    v1['l3_useful']['numerator']=0
    v2.update(false_claim=10,l1_false_clean=0)
    v2['taxonomy']=deepcopy(v1['taxonomy'])
    v2['l2_useful']['numerator']=8
    v2['l2_strict']['numerator']=6
    v2['l3_useful']['numerator']=2
    return base,v1,v2


def decide(values):
    from scripts.task3_direct_sft_v2_report import production_decision
    return production_decision(*values)


def test_conjunctive_rule_accepts_content_and_retained_taxonomy():
    assert decide(arms())['eligible']


@pytest.mark.parametrize('key', ['l2_useful','l2_strict','l3_useful'])
def test_taxonomy_gain_without_each_content_gain_fails(key):
    rows=arms(); rows[2][key]=deepcopy(rows[0][key])
    assert not decide(rows)['eligible']


def test_retention_is_fraction_of_gain_over_base_for_both_references():
    rows=arms();rows[2]['taxonomy']['source']['macro']=.369
    assert not decide(rows)['eligible']
    rows[2]['taxonomy']['source']['macro']=.37
    assert decide(rows)['eligible']


@pytest.mark.parametrize('arm_index',[0,1,2])
def test_unknown_flags_never_become_success(arm_index):
    rows=arms();rows[arm_index]['semantic_pending']=1
    assert not decide(rows)['eligible']


def test_completion_and_new_l1_false_clean_block_replacement():
    rows=arms();rows[2]['completed']=59
    assert not decide(rows)['eligible']
    rows=arms();rows[2]['l1_false_clean']=1
    assert not decide(rows)['eligible']


def test_missing_or_zero_defect_denominator_is_not_perfect():
    rows=arms();rows[2]['l3_useful']=dict(numerator=0,denominator=0,pending=0)
    assert not decide(rows)['eligible']


def test_new_decision_never_authorizes_public_generation():
    result=decide(arms())
    assert result['public_generation_authorized'] is False


def test_input_binding_rejects_missing_or_changed_predictions():
    from scripts.task3_direct_sft_v2_report import verify_reused_outputs
    expected={'BASE':{'predictions.json':'a'},'V1':{'predictions.json':'b'}}
    verify_reused_outputs(expected,deepcopy(expected))
    actual=deepcopy(expected);actual['V1']['predictions.json']='changed'
    with pytest.raises(ValueError,match='reused'):
        verify_reused_outputs(expected,actual)
