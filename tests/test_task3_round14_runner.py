import json
from pathlib import Path
import pytest
from src.task3.inference import Generation,MockTokenizer
from tests.test_task3_round14 import sample,value


class Scripted:
    tokenizer=MockTokenizer()
    def __init__(self,answers):self.answers=list(answers);self.calls=0
    def generate(self,messages,config):
        self.calls+=1
        answer=self.answers.pop(0)
        if isinstance(answer,Exception):raise answer
        return Generation(answer,20,.01,'eos',True)


def config():return {'context_limit':30000,'max_new_tokens':768,'max_retries':1,'method':'direct','seed':42}


def test_resume_keeps_completed_id_and_rejects_changed_inputs(tmp_path):
    from src.task3.round14_runner import run_records
    backend=Scripted([json.dumps(value())]);r=sample()
    first=run_records([r],backend,config(),tmp_path)
    assert len(first['predictions'])==1 and backend.calls==1
    assert run_records([r],backend,config(),tmp_path)['predictions']==first['predictions']
    assert backend.calls==1
    from dataclasses import replace
    with pytest.raises(ValueError,match='identity'):run_records([replace(r,code=r.code+'\n//changed')],backend,config(),tmp_path)


def test_failure_does_not_lose_another_id_and_unknown_is_not_empty(tmp_path):
    from src.task3.round14_runner import run_records
    from dataclasses import replace
    backend=Scripted([RuntimeError('gpu fault')]*8+[json.dumps(value())])
    # A per-ID infrastructure error isolates immediately, without changing labels.
    backend=Scripted([RuntimeError('gpu fault'),json.dumps(value())])
    result=run_records([sample(),replace(sample(),sample_id='SECOND')],backend,config(),tmp_path)
    assert len(result['predictions'])==1 and result['errors']
    assert result['predictions'][0]['sample_id']=='SECOND'
    assert not (tmp_path/'predictions.json').exists()


def test_parse_failure_retries_then_uses_independent_classifier_not_empty(tmp_path):
    from src.task3.round14_runner import run_records
    classifier=value();classifier.pop('feedback')
    backend=Scripted(['bad','bad',json.dumps(classifier),json.dumps({'feedback':value()['feedback']})])
    out=run_records([sample()],backend,config(),tmp_path)
    assert out['predictions'][0]['output']['taxonomy_error']==['Lỗi logic']
    assert out['traces'][0]['classification_fallback']


def test_explicit_model_clean_survives_without_becoming_verified_clean(tmp_path):
    from src.task3.round14_runner import run_records
    backend=Scripted([json.dumps(value(labels=[]))])
    out=run_records([sample(1)],backend,config(),tmp_path)
    assert out['predictions'][0]['output']['taxonomy_error']==[]
    assert out['traces'][0]['assessment']['epistemic_status']=='model_predicted_clean_unverified'


def test_two_stage_labels_and_feedback_have_independent_calls(tmp_path):
    from src.task3.round14_runner import run_records
    cls=value();cls.pop('feedback')
    backend=Scripted([json.dumps(cls),json.dumps({'feedback':value()['feedback']})])
    cfg=dict(config(),method='two_stage')
    out=run_records([sample()],backend,cfg,tmp_path)
    assert backend.calls==2 and len(out['predictions'])==1


def test_oracle_diagnostic_reuses_assessment_and_changes_only_feedback_labels(tmp_path):
    from src.task3.round14_runner import run_records
    r=sample();a=value();a.pop('feedback')
    a.update(epistemic_status='model_predicted_errors_unverified')
    backend=Scripted([json.dumps({'feedback':'Chưa xác định được lỗi cụ thể có căn cứ trong phần mã hiện có.'})])
    out=run_records([r],backend,dict(config(),method='two_stage'),tmp_path,
                    oracle_labels={r.sample_id:[]},assessment_cache={r.sample_id:a})
    assert backend.calls==1 and out['predictions'][0]['output']['taxonomy_error']==[]
    assert out['traces'][0]['assessment']==a


@pytest.mark.parametrize('field,value',[('grading_policy','Different prerequisites.'),('level_definitions',[{'new':'definition'}])])
def test_resume_binds_every_prompt_input(field,value):
    from src.task3.round14_runner import identity
    from dataclasses import replace
    r=sample();backend=Scripted([])
    assert identity([r],backend,config())!=identity([replace(r,**{field:value})],backend,config())


def test_unbound_existing_final_artifact_is_rejected(tmp_path):
    from src.task3.round14_runner import run_records
    (tmp_path/'predictions.json').write_text('["STALE"]')
    with pytest.raises(ValueError,match='unbound'):
        run_records([sample()],Scripted([RuntimeError('fault')]),config(),tmp_path)
    assert (tmp_path/'predictions.json').read_text()=='["STALE"]'


def test_bound_incomplete_state_cannot_keep_a_final_artifact(tmp_path):
    from src.task3.round14_runner import run_records,identity
    backend=Scripted([RuntimeError('fault')]);r=sample()
    binding=identity([r],backend,dict(config(),oracle_labels=None,assessment_cache=None))
    (tmp_path/'progress.json').write_text(json.dumps({'identity':binding,'completed':{},'errors':{}}))
    (tmp_path/'predictions.json').write_text('["STALE"]')
    with pytest.raises(ValueError,match='incomplete'):
        run_records([r],backend,config(),tmp_path)


def test_journal_totals_include_failed_and_resumed_attempts(tmp_path):
    from src.task3.round14_runner import journal_totals
    p=tmp_path/'attempts.jsonl'
    row={'stage':'classify','output_tokens':20,'input_tokens':30,'latency_s':.1,'error':'bad'}
    p.write_text(json.dumps(row)+'\n'+json.dumps(row)+'\n'+json.dumps(dict(row,error=None))+'\n')
    assert journal_totals(p)['output_tokens']==60
    assert journal_totals(p)['attempts']==3


def test_interrupted_attempt_tail_is_preserved_before_resume_append(tmp_path):
    from src.task3.round14_runner import run_records,journal_totals
    journal=tmp_path/'attempts.jsonl';journal.write_bytes(b'{"incomplete":')
    out=run_records([sample()],Scripted([json.dumps(value())]),config(),tmp_path)
    assert len(out['predictions'])==1 and journal_totals(journal)['attempts']==1
    backups=list(tmp_path.glob('attempts.jsonl.interrupted-*.raw'))
    assert len(backups)==1 and backups[0].read_bytes()==b'{"incomplete":'
