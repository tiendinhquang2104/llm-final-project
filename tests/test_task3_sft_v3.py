"""Regression tests for scientific boundaries and official-contract evaluation."""
import importlib
from pathlib import Path
import pytest


def api():
    spec = importlib.util.find_spec('src.task3.sft_v3')
    assert spec is not None, 'v3 policy implementation missing'
    return importlib.import_module('src.task3.sft_v3')


def candidate(step, **kw):
    return dict(step=step, invalid=0, clean_false_alarms=0, faulty_misses_with_invalid=1,
                supported_faulty_diagnosis=50, faulty_l3_correct=12, level_compliant=70,
                balanced_joint=.8, oracle_joint=75, mean_loss=.5, **kw)


def test_select_rejects_surface_compliance_with_more_missed_defects():
    m=api(); v2=candidate(240); a=candidate(240); b=candidate(480)
    b.update(level_compliant=80,faulty_misses_with_invalid=2)
    chosen=m.select_checkpoint([a,b],v2)
    assert chosen['step']==240 and chosen['eligible_steps']==[240]
    assert chosen['eligibility_failures']['480']==['faulty_misses_with_invalid']


def test_fallback_is_diagnostic_and_never_claims_promotion():
    m=api(); v2=candidate(240); a=candidate(240); b=candidate(480)
    a.update(invalid=1,balanced_joint=.7); b.update(clean_false_alarms=1,balanced_joint=.9)
    chosen=m.select_checkpoint([a,b],v2)
    assert chosen['step']==480 and chosen['passes_preliminary_conditions'] is False


def test_joint_accepts_useful_l4_without_code_and_separates_wrong_l3_hint():
    m=api(); axes={k:'pass' for k in m.AXES}
    assert m.joint_success('valid',4,True,axes,'absent') is True
    assert m.joint_success('valid',4,True,axes,'fail') is False
    axes['l3_repair_direction']='fail'
    assert m.joint_success('valid',3,True,axes,'absent') is False
    assert axes['level_compliance']=='pass'


def test_faulty_praise_and_invalids_have_distinct_diagnostic_denominators():
    m=api(); axes={k:'pass' for k in m.AXES}
    axes['diagnosis_supported']='fail'
    rows=[dict(sample_id='d',level=1,faulty=True,status='valid',parsed={'taxonomy_error':[]},axes=axes,code_verdict='absent'),
          dict(sample_id='e',level=1,faulty=True,status='invalid_schema',parsed=None,axes=axes,code_verdict='absent'),
          dict(sample_id='c',level=1,faulty=False,status='valid',parsed={'taxonomy_error':['Lỗi logic']},axes=axes,code_verdict='absent')]
    result=m.summarize(rows)
    assert (result['targets'],result['sources'],result['faulty_misses'],result['faulty_invalids'],result['clean_false_alarms'])==(3,3,1,1,1)
    assert result['faulty_misses_with_invalid']==2 and result['joint_successful']==0


def test_journal_does_not_replay_unknown_and_keeps_smoke_separate(tmp_path):
    m=api(); journal=m.BudgetJournal(tmp_path/'journal.jsonl')
    journal.reserve('smoke-before/x');journal.reserve('smoke-after/x')
    with pytest.raises(ValueError):journal.reserve('smoke-extra/x')
    journal.reserve('base-dev/x')
    with pytest.raises(ValueError):journal.reserve('base-dev/x')
    assert len(journal.reserved())==3


def test_epoch_exposure_validation_requires_each_row_twice():
    m=api()
    assert m.validate_exposures(['a','b','b','a'],['a','b'],2)
    with pytest.raises(ValueError):m.validate_exposures(['a','b','a','a'],['a','b'],2)


def test_two_epoch_arguments_reuse_recipe_and_recompute_for_quarantine(tmp_path):
    import yaml
    m=api();cfg=yaml.safe_load(Path('configs/task3/sft_v1.yaml').read_text())
    cfg['training']['epochs']=2
    cfg['training']['sampling']='seeded_epoch_shuffle_without_replacement'
    args=m.main_training_arguments(cfg,tmp_path,956)
    assert args['num_train_epochs']==2 and args['save_steps']==239
    assert args['gradient_accumulation_steps']==4 and args['learning_rate']==2e-5
    assert args['remove_unused_columns'] is False
    assert cfg['training']['epochs']==2
    with pytest.raises(ValueError):m.main_training_arguments(cfg,tmp_path,955)


def test_oracle_wrapper_rejects_level_answers_and_keeps_e2e_unmodified():
    m=api();x=[{'role':'system','content':'contract'},{'role':'user','content':'source'}]
    packet={'faulty':True,'taxonomy':['Lỗi logic'],'location':[{'excerpt':'x++','lines':[7]}],
            'mechanism':'increments rather than decrements','essential_conditions':['n>0'],'repair_direction':'decrease remaining count'}
    wrapped=m.oracle_prompt(x,packet)
    assert x[1]['content']=='source' and wrapped[0]==x[0]
    assert 'reviewed' in wrapped[1]['content'].lower()
    packet['targets']={'1':{'feedback':'prewritten'}}
    with pytest.raises(ValueError):m.oracle_prompt(x,packet)


def test_evaluator_persists_finite_teacher_loss_before_generation(tmp_path,monkeypatch):
    import json,math
    from contextlib import nullcontext
    from types import SimpleNamespace
    import torch
    import src.task3.sft_v3_runtime as runtime
    class Toy(torch.nn.Module):
        def forward(self,input_ids,attention_mask,use_cache=False):
            return SimpleNamespace(logits=torch.zeros((*input_ids.shape,16)))
    monkeypatch.setattr(torch.Tensor,'cuda',lambda self:self)
    monkeypatch.setattr(torch.cuda,'synchronize',lambda:None)
    monkeypatch.setattr(torch.cuda,'reset_peak_memory_stats',lambda:None)
    monkeypatch.setattr(runtime,'evaluating',lambda model:nullcontext())
    monkeypatch.setattr(runtime,'gpu_cost',lambda start:dict(wall_s=0,peak_allocated_bytes=0,peak_reserved_bytes=0))
    e=dict(example_id='x-L1',sample_id='x',level=1,prompt=[dict(role='system',content='s')],completion='{"taxonomy_error":[],"feedback":"Đúng."}')
    row=dict(example_id='x-L1',sample_id='x',level=1,input_ids=[1,2,3],attention_mask=[1,1,1],labels=[-100,2,3],loss_weight=1.)
    result=dict(example_id='x-L1',sample_id='x',level=1,status='valid',parsed={'taxonomy_error':[],'feedback':'Đúng.'},raw=e['completion'],wall_s=0,finish_reason='eos')
    monkeypatch.setattr(runtime,'generate',lambda *args:result)
    (tmp_path/'manifest.json').write_text('{}')
    manifest=dict(config={'revision':'test'},generation={},parser_policy={})
    value=runtime.evaluate(Toy(),SimpleNamespace(pad_token_id=0),[e],[row],tmp_path/'base-dev',manifest,api().BudgetJournal(tmp_path/'j.jsonl'),'base-dev')
    assert value['mean_loss']==pytest.approx(math.log(16))
    assert json.loads((tmp_path/'base-dev/losses.jsonl').read_text())['loss']==pytest.approx(math.log(16))


def test_context_preflight_accepts_four_levels_of_one_source():
    import src.task3.sft_v3_runtime as runtime
    class Tokens:
        def apply_chat_template(self,*a,**kw):return [1,2,3]
    rows=[dict(example_id='same-L'+str(level),sample_id='same',level=level,prompt=[]) for level in (1,2,3,4)]
    got=runtime.context_preflight(Tokens(),rows,{'max_new_tokens':{'1':10,'2':10,'3':10,'4':20}},32768)
    assert [r['sample_id'] for r in got]==['same-L1','same-L2','same-L3','same-L4']
    assert all(r['source_id']=='same' and r['status']=='evaluable' for r in got)
    assert rows[0]['sample_id']=='same'


def test_bounded_code_success_status_is_accepted():
    import scripts.task3_sft_v3_review as review
    assert hasattr(review,'executable_verdict'), 'bounded audit verdict adaptation missing'
    assert review.executable_verdict({'status':'all_authored_tests_passed'})=='pass'
    assert review.executable_verdict({'status':'authored_test_failure'})=='fail'
    assert review.executable_verdict({'status':'started_no_retry'})=='uncertain'


def test_review_expansion_cannot_join_different_payload_groups():
    import scripts.task3_sft_v3_review as review
    assert hasattr(review,'validate_review_ids'), 'exact duplicate adjudication binding missing'
    groups={'a':frozenset(['a','b']),'b':frozenset(['a','b']),'c':frozenset(['c'])}
    assert review.validate_review_ids(['b','a'],groups)
    with pytest.raises(ValueError):review.validate_review_ids(['a','c'],groups)
    with pytest.raises(ValueError):review.validate_review_ids(['a'],groups)


def test_supplied_uncertain_code_cannot_be_declared_absent():
    import scripts.task3_sft_v3_review as review
    assert hasattr(review,'resolved_code_verdict'), 'code evidence resolution validation missing'
    with pytest.raises(ValueError):review.resolved_code_verdict('uncertain',{'code_verdict':'absent'})
    with pytest.raises(ValueError):review.resolved_code_verdict('uncertain',{'code_verdict':'pass'})
    assert review.resolved_code_verdict('uncertain',{'code_verdict':'pass','code_resolution_evidence':'The local snippet updates only the accumulator and matches the reviewed invariant.'})=='pass'
    assert review.resolved_code_verdict('fail',{'code_verdict':'pass'})=='fail'


def test_oracle_fidelity_level_metric_is_separate_from_task_joint():
    import scripts.task3_sft_v3_review as review
    assert hasattr(review,'oracle_fidelity_level'), 'oracle fidelity plus Level metric missing'
    axes={k:'pass' for k in api().AXES};axes['l3_repair_direction']='fail'
    row=dict(status='valid',level=3,faulty=True,axes=axes,code_verdict='absent')
    assert review.oracle_fidelity_level(row)
    assert not api().joint_success('valid',3,True,axes,'absent')
