import json
from dataclasses import replace
import pytest
from tests.test_task3_round14 import sample
from src.task3.inference import Generation,MockTokenizer


class Scripted:
    tokenizer=MockTokenizer()
    def __init__(self,answers,out):self.answers=list(answers);self.calls=0;self.out=out
    def generate(self,messages,config):
        self.calls+=1
        # Prior raw responses must already exist before requesting a retry.
        if self.calls>1:assert (self.out/'attempts.jsonl').exists()
        result=self.answers.pop(0)
        if isinstance(result,Exception):raise result
        return Generation(result,17,.01,'eos',True)


def cfg():return {'context_limit':20000,'max_new_tokens':512,'max_attempts':3,'prompt_variant':'zero_shot'}

def response(text='Chỗ sai ở phép tính; dùng tổng hai số làm kết quả.',labels=None):
    return json.dumps({'taxonomy_error':['Lỗi logic'] if labels is None else labels,'feedback':text},ensure_ascii=False)


def test_raw_saved_before_processing_and_level3_not_replaced(tmp_path):
    from src.task3.round15_runner import run_records
    backend=Scripted([response('Hàm main thiếu return. Thêm return x; cuối hàm.')],tmp_path)
    got=run_records([sample(3)],backend,cfg(),tmp_path)
    assert len(got['predictions'])==1
    assert got['predictions'][0]['output']['feedback']=='Hàm main thiếu return. Thêm return x; cuối hàm.'
    assert got['traces'][0]['first_raw_text']==response('Hàm main thiếu return. Thêm return x; cuối hàm.')
    rows=[json.loads(s) for s in (tmp_path/'attempts.jsonl').read_text().split('\n') if s]
    assert rows[0]['capture_stage']=='before_parse_and_guard'
    assert not got['traces'][0]['fallback_used']


def test_level2_repair_retry_keeps_useful_diagnosis(tmp_path):
    from src.task3.round15_runner import run_records
    backend=Scripted([response('Hàm main sai. Hãy thay x bằng 0.'),response('Trong main, giá trị x trả về khác yêu cầu đề.')],tmp_path)
    got=run_records([sample(2)],backend,cfg(),tmp_path)
    assert backend.calls==2
    assert got['predictions'][0]['output']['feedback']=='Trong main, giá trị x trả về khác yêu cầu đề.'
    assert got['traces'][0]['first_raw_schema_output']['feedback']=='Hàm main sai. Hãy thay x bằng 0.'
    assert got['traces'][0]['raw_to_final_changed']


def test_schema_failure_never_becomes_empty_and_budget_is_not_reset(tmp_path):
    from src.task3.round15_runner import run_records
    backend=Scripted(['bad']*3,tmp_path)
    got=run_records([sample(2)],backend,cfg(),tmp_path)
    assert got['errors'] and not got['predictions']
    again=run_records([sample(2)],backend,cfg(),tmp_path)
    assert backend.calls==3 and again['errors']
    assert not (tmp_path/'predictions.json').exists()


def test_persistent_level2_disclosure_has_flagged_fallback_but_preserves_model_labels(tmp_path):
    from src.task3.round15_runner import run_records
    backend=Scripted([response('Hãy thay x bằng 0.')]*3,tmp_path)
    got=run_records([sample(2)],backend,cfg(),tmp_path)
    assert got['predictions'][0]['output']['taxonomy_error']==['Lỗi logic']
    assert got['traces'][0]['fallback_used']
    assert got['traces'][0]['usefulness']=='not_established_epistemic_fallback'


def test_resume_keeps_completed_outputs_and_binds_source_examples(tmp_path):
    from src.task3.round15_runner import run_records
    backend=Scripted([response(labels=[])],tmp_path)
    r=sample(3);got=run_records([r],backend,cfg(),tmp_path)
    assert run_records([r],backend,cfg(),tmp_path)['predictions']==got['predictions'] and backend.calls==1
    with pytest.raises(ValueError,match='identity'):
        run_records([replace(r,code=r.code+'\n//modified')],backend,cfg(),tmp_path)
    with pytest.raises(ValueError,match='identity'):
        run_records([r],backend,dict(cfg(),example_bank_sha256='changed'),tmp_path)


def test_infrastructure_failure_isolated_and_counts_toward_budget(tmp_path):
    from src.task3.round15_runner import run_records
    rows=[sample(3),replace(sample(3),sample_id='OTHER')]
    backend=Scripted([RuntimeError('GPU unavailable'),response()],tmp_path)
    got=run_records(rows,backend,cfg(),tmp_path)
    assert len(got['predictions'])==1 and got['errors']


def test_runtime_resume_consumes_remaining_budget_instead_of_sticking_on_old_failure(tmp_path):
    from src.task3.round15_runner import run_records
    backend=Scripted([RuntimeError('temporary GPU fault')],tmp_path)
    first=run_records([sample(3)],backend,cfg(),tmp_path)
    assert first['errors'] and backend.calls==1
    backend.answers.append(response())
    second=run_records([sample(3)],backend,cfg(),tmp_path)
    assert len(second['predictions'])==1 and backend.calls==2


def test_capture_reaches_disk_before_the_parser_is_called(tmp_path,monkeypatch):
    import src.task3.round15_runner as runner
    original=runner.parse_response
    def verify_capture(text):
        rows=[json.loads(line) for line in (tmp_path/'attempts.jsonl').read_text().split('\n') if line]
        assert rows[-1]['raw_text']==text
        return original(text)
    monkeypatch.setattr(runner,'parse_response',verify_capture)
    got=runner.run_records([sample(3)],Scripted([response()],tmp_path),cfg(),tmp_path)
    assert len(got['predictions'])==1


def test_round14_control_wrapper_captures_raw_before_legacy_postprocessing(tmp_path):
    from src.task3.round15_runner import RawCaptureBackend
    original=Scripted([response()],tmp_path)
    wrapped=RawCaptureBackend(original,tmp_path/'legacy-pre-guard.jsonl')
    generation=wrapped.generate([{'role':'user','content':'artificial'}],cfg())
    rows=[json.loads(s) for s in (tmp_path/'legacy-pre-guard.jsonl').read_text().split('\n') if s]
    assert rows[0]['raw_text']==generation.text and rows[0]['capture_stage']=='before_legacy_parser_and_guard'


def test_orphan_attempt_journal_cannot_be_rebound_to_new_inputs(tmp_path):
    from src.task3.round15_runner import run_records
    backend=Scripted(['bad']*3,tmp_path)
    run_records([sample(3)],backend,cfg(),tmp_path)
    (tmp_path/'progress.json').unlink()
    with pytest.raises(ValueError,match='unbound'):
        run_records([replace(sample(3),code='int main(){return 9;}')],backend,cfg(),tmp_path)


def test_resumed_journal_attempt_identity_and_prompt_hash_are_verified(tmp_path):
    from src.task3.round15_runner import run_records
    backend=Scripted(['bad']*3,tmp_path)
    run_records([sample(3)],backend,cfg(),tmp_path)
    journal=tmp_path/'attempts.jsonl';rows=[json.loads(s) for s in journal.read_text().split('\n') if s]
    rows[0]['prompt_messages']=[{'role':'user','content':'different task'}]
    journal.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    with pytest.raises(ValueError,match='journal'):
        run_records([sample(3)],backend,cfg(),tmp_path)


def test_resumed_completed_schema_and_disclosure_are_verified(tmp_path):
    from src.task3.round15_runner import run_records
    backend=Scripted([response('Em hãy đối chiếu bài làm với đề.',labels=[])],tmp_path)
    run_records([sample(1)],backend,cfg(),tmp_path)
    path=tmp_path/'progress.json';state=json.loads(path.read_text());key=next(iter(state['completed']))
    state['completed'][key]['output']['feedback']='Lỗi ở dòng 3 do biến x chưa khai báo.'
    path.write_text(json.dumps(state))
    with pytest.raises(ValueError,match='completed'):
        run_records([sample(1)],backend,cfg(),tmp_path)


def test_exhausted_runtime_errors_do_not_become_completed_only_on_resume(tmp_path):
    from src.task3.round15_runner import run_records
    backend=Scripted([response('Hãy thay x bằng 0.'),RuntimeError('fault'),RuntimeError('fault')],tmp_path)
    for _ in range(2):
        got=run_records([sample(2)],backend,cfg(),tmp_path)
        assert got['errors']
    third=run_records([sample(2)],backend,cfg(),tmp_path)
    assert third['errors'] and not third['predictions'] and backend.calls==3
