from pathlib import Path
import pytest
from src.task3.sft_v4_training import validate_rows, main_training_arguments
from src.task3.sft_v4 import EvaluationJournal, choose_checkpoint, pair_success
from src.task3.prompt_crossover import call_state


def test_three_levels_once_no_fourth_level():
    rows=[dict(example_id=f's-L{l}',sample_id='s',level=l,loss_weight=1.) for l in [1,2,3]]
    validate_rows(rows,3)
    rows[-1]['level']=4
    with pytest.raises(ValueError):validate_rows(rows,3)


def test_single_attempt_resume_and_foreign_target(tmp_path):
    j=EvaluationJournal(tmp_path/'j',{'dev/base':['s-L1']})
    j.reserve('dev/base/s-L1')
    assert call_state(j,'dev/base/s-L1')[0]=='uncertain'
    with pytest.raises(ValueError):j.reserve('dev/base/s-L1')
    with pytest.raises(ValueError):j.reserve('test/base/s-L1')
    j.append(dict(type='generation_completed',key='dev/base/s-L1',result={'raw':'ok'}))
    assert call_state(j,'dev/base/s-L1')==('completed',{'raw':'ok'})


def test_selection_eligibility_precedes_ranking_and_fallback():
    v3=dict(clean_false_alarms=0,invalid=0,disclosure_failures=1)
    a=dict(step=48,pair_success=20,repair=10,diagnosis=20,clean_false_alarms=1,invalid=0,disclosure_failures=0)
    b=dict(step=96,pair_success=3,repair=2,diagnosis=5,clean_false_alarms=0,invalid=0,disclosure_failures=1)
    r=choose_checkpoint([a,b],v3)
    assert r['step']==96 and not r['fallback']
    b['invalid']=1
    r=choose_checkpoint([a,b],v3)
    assert r['step']==48 and r['fallback'] and not r['eligible_for_promotion']


def test_pair_needs_truthful_clean_and_actual_defect_not_only_labels():
    axes={k:'pass' for k in ['diagnosis_supported','coverage','factual_fidelity','location_and_condition']}
    clean=dict(status='valid',parsed={'taxonomy_error':[]},axes=axes)
    faulty=dict(status='valid',parsed={'taxonomy_error':['Lỗi logic']},axes=dict(axes))
    assert pair_success(clean,faulty) is True
    faulty['axes']['diagnosis_supported']='fail'
    assert pair_success(clean,faulty) is False
    faulty['axes']['diagnosis_supported']='uncertain'
    assert pair_success(clean,faulty) is None


def test_training_recipe_real_arguments_are_one_epoch_96_steps():
    import json,copy
    m=json.loads(Path('outputs/task3/base-pv3-control-20261027-run1/manifest.json').read_text())
    cfg=copy.deepcopy(m['runtime']['loader_manifest']['config'])
    cfg['training'].update(epochs=1,sampling='one_seeded_shuffle_of_train_rows_without_replacement',checkpoint_selection='diagnostic_pair_lexicographic_dev_only')
    a=main_training_arguments(cfg,Path('/tmp/not-run'),384)
    assert a['num_train_epochs']==1 and a['gradient_accumulation_steps']==4 and a['save_steps']==48
    assert a['learning_rate']==2e-5 and a['bf16'] and not a['fp16']
    assert a['optim']=='adamw_torch' and a['lr_scheduler_type']=='cosine' and a['warmup_ratio']==.03
    assert not a['remove_unused_columns'] and a['eval_strategy']=='no'
    assert a['save_only_model'] is False and not a['push_to_hub']


def test_neutral_clean_prose_is_not_confirmed_discrimination():
    axes={k:'pass' for k in ['diagnosis_supported','coverage','factual_fidelity','location_and_condition']}
    clean=dict(status='valid',parsed={'taxonomy_error':[]},axes=axes,correct_status='not_evaluable')
    faulty=dict(status='valid',parsed={'taxonomy_error':['Lỗi logic']},axes=dict(axes),correct_status='pass')
    assert pair_success(clean,faulty) is None


def test_auxiliary_status_pair_preserves_unknown_prose():
    from src.task3.sft_v4 import metrics
    from src.task3.prompt_crossover import AXES
    rr=[]
    for faulty,sid in [(False,'c'),(True,'f')]:
        for l in [1,2,3]:
            rr.append(dict(example_id=f'{sid}-L{l}',sample_id=sid,family_id='family',level=l,faulty=faulty,status='valid',
                raw='{"taxonomy_error": '+('["Lỗi logic"]' if faulty else '[]')+', "feedback": "nội dung"}',finish_reason='eos',
                parsed={'taxonomy_error':['Lỗi logic'] if faulty else [],'feedback':'nội dung'},gold_taxonomy=['Lỗi logic'] if faulty else [],
                axes={a:'pass' for a in AXES},correct_status='pass' if faulty else 'not_evaluable',code_verdict='absent',taxonomy_feedback_contradiction=False))
    m=metrics(rr)
    assert all(p['status_both_correct'] is None for p in m['diagnostic_pairs']['details'])


def test_unknown_disclosure_is_not_implicitly_promotion_ready():
    a=dict(step=48,pair_success=10,repair=5,diagnosis=10,clean_false_alarms=0,invalid=0,disclosure_failures=0,disclosure_unknown=3)
    b=dict(a,step=96,pair_success=0)
    ref=dict(clean_false_alarms=0,invalid=0,disclosure_failures=0,disclosure_unknown=0)
    r=choose_checkpoint([a,b],ref)
    assert not r['eligible_for_promotion']
    assert r['unresolved_disclosure']
