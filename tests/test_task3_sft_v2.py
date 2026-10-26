import pytest
import json
from pathlib import Path

from src.task3.sft_v2 import BudgetJournal, select_checkpoint, cross_level_consistency, joint_success
from src.task3.sft_v2_runtime import compiler_view, pending_dev_evaluations, historical_payload


def candidate(step, fa=2, invalid=0, joint=10, repairs=3, loss=1.):
    return dict(step=step, clean_false_alarms=fa, invalid=invalid, joint_successful=joint,
                faulty_l3_correct=repairs, mean_loss=loss)


def test_selection_eligibility_precedes_quality_and_uses_all_ties():
    a, b = candidate(120), candidate(240, fa=4, joint=70)
    assert select_checkpoint([a,b],3,0)['step'] == 120
    assert select_checkpoint([a,dict(a,step=240)],3,0)['step'] == 120
    assert select_checkpoint([a,dict(a,step=240,mean_loss=.9)],3,0)['step'] == 240
    assert select_checkpoint([a,dict(a,step=240,faulty_l3_correct=4)],3,0)['step'] == 240
    assert select_checkpoint([a,dict(a,step=240,clean_false_alarms=1)],3,0)['step'] == 240


def test_failed_promotion_selects_diagnostic_candidate_and_invalid_is_disqualifying():
    a,b=candidate(120,fa=4,joint=9),candidate(240,fa=5,joint=70)
    result=select_checkpoint([a,b],3,0)
    assert result['step']==120 and not result['passes_preliminary_conditions']
    assert select_checkpoint([candidate(120,invalid=1),candidate(240)],3,0)['step']==240
    with pytest.raises(ValueError): select_checkpoint([a,dict(b,mean_loss=float('nan'))],3,0)


def test_joint_success_handles_uncertainty_applicability_and_separate_l4_axes():
    axes={x:'pass' for x in ('diagnosis_supported','location_and_condition','level_compliance',
                            'vietnamese_compliance','l3_repair_direction','l4_explanation_quality')}
    assert joint_success('valid',1,False,dict(axes,location_and_condition='not_applicable'),None)
    assert not joint_success('valid',2,True,dict(axes,location_and_condition='not_applicable'),None)
    assert not joint_success('valid',3,True,dict(axes,l3_repair_direction='uncertain'),None)
    assert joint_success('valid',3,False,dict(axes,l3_repair_direction='not_applicable'),None)
    assert not joint_success('valid',4,True,dict(axes,l4_explanation_quality='fail'),'pass')
    assert not joint_success('valid',4,True,axes,'not_evaluable')
    assert not joint_success('missing',1,False,axes,None)


def test_consistency_reports_invalid_and_incomplete_groups_without_counting_them_consistent():
    rows=[dict(sample_id='a',level=k,status='valid',parsed={'taxonomy_error':[]}) for k in range(1,5)]
    rows += [dict(sample_id='b',level=k,status='valid',parsed={'taxonomy_error':[] if k<4 else ['X']}) for k in range(1,5)]
    rows += [dict(sample_id='c',level=1,status='missing',parsed=None)]
    result=cross_level_consistency(rows)
    assert result['consistent_complete_valid_sources']==1
    assert result['inconsistent_complete_valid_sources']==1
    assert result['incomplete_sources']==1 and result['sources_with_invalid']==1


def test_budget_journal_global_and_per_request_caps(tmp_path):
    j=BudgetJournal(tmp_path/'j.jsonl')
    for i in range(3): j.reserve('ar15-dev/x/'+str(i),402)
    with pytest.raises(ValueError): j.reserve('ar15-dev/x/3',402)
    j.reserve('step-120-dev/x',402)
    with pytest.raises(ValueError): j.reserve('step-120-dev/x',402)
    for i in range(2): j.reserve('smoke-'+str(i)+'/x',402)
    with pytest.raises(ValueError): j.reserve('smoke-extra/x',402)


def test_compiler_warning_is_diagnostic_with_pass_status():
    assert compiler_view({'returncode':0,'stderr':'warning: unused variable'})==dict(status='pass',diagnostic='warning: unused variable')
    assert compiler_view({'returncode':1,'stderr':'error: missing semicolon'})['status']=='error'


def test_saved_checkpoint_dev_evaluations_are_recovered_before_resume():
    assert pending_dev_evaluations(120,set())==[120]
    assert pending_dev_evaluations(240,{240})==[120]
    assert pending_dev_evaluations(240,{120,240})==[]


def test_historical_prediction_preserves_controller_nested_output():
    output=dict(taxonomy_error=[],feedback='Phản hồi.')
    assert historical_payload(dict(sample_id='x',output=output))==output
    assert historical_payload(None) is None


def test_exported_private_targets_match_actual_model_targets():
    from src.task3.sft_v1 import read_jsonl
    root=Path(__file__).resolve().parents[1]/'data/raw/task3-sft-v2'
    if not root.exists():pytest.skip('private dataset not exported')
    cases={c['sample_id']:c for c in json.loads((root/'cases.private.json').read_text())}
    for split in ('train','dev','test','final'):
        for r in read_jsonl(root/f'{split}.records.jsonl'):
            assert cases[r['source_id']]['targets'][str(r['input']['target_feedback_level'])]==r['output']
