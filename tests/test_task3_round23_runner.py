import json
import subprocess
import hashlib
import pytest
from src.task3.inference import Generation,MockTokenizer
from src.task3.schema import Task3Record
from src.task3.round23_runner import run_shared, build_messages

SCOPE={'kind':'scalar','lo':0,'hi':10}
def rec():return Task3Record(source='synthetic',sample_id='opaque',original_submission_id='opaque',exam_id='TRAIN',exam_type='single_problem',statement='Read x,print x.',code_path='source.cpp',code='int main(){cout<<0;}',grading_policy='',target_feedback_level='Level 2 - Chẩn đoán',gold_taxonomy=['Lỗi style'],gold_feedback='SECRET_TEACHER',provenance={'hidden_oracle':'SECRET_EXPECTED','_task3_compile_check':{'status':'pass','diagnostic':''}})
def raw(input='2',actual='0'):return json.dumps(dict(status='defect',span='cout << 0;',input=input,actual=actual,expected='2',mechanism='Constant output ignores input.',taxonomy_error=['Lỗi logic']))
class Backend:
    tokenizer=MockTokenizer()
    def __init__(self,texts):self.texts=iter(texts);self.messages=[]
    def generate(self,messages,config):self.messages.append(messages);return Generation(next(self.texts),20,.1,'test',True)


def test_shared_initial_and_own_observation_only_with_raw_capture_before_parse():
    b=Backend([raw(),raw(actual='7')]);rows=[];executed=[]
    def execute(w):executed.append(w);return {'returncode':0,'stdout':'7','stderr':'','timeout':False,'executed':True}
    r=run_shared(rec(),SCOPE,b,{'max_new_tokens':768,'context_limit':16384},execute,capture=rows.append)
    assert len(b.messages)==2 and len(executed)==1 and len(rows)==2
    assert 'parse_status'not in rows[0] and rows[0]['raw_text']==raw()
    assert r['self']['output']['actual']=='0' and r['execution']['output']['actual']=='7'
    assert '7'in b.messages[1][-1]['content'] and 'SECRET_'not in json.dumps(b.messages)
    assert r['execution']['observed']['input']=={'stdin':'2','files':{}}


def test_invalid_input_never_executes_or_gets_a_repair_call():
    b=Backend([raw(input='99')])
    def forbidden(_):raise AssertionError('invalid cannot execute')
    r=run_shared(rec(),SCOPE,b,{'max_new_tokens':768,'context_limit':16384},forbidden)
    assert len(b.messages)==1 and r['execution']['status']=='invalid_input'
    assert not r['execution']['fallback_used']


def test_uncertain_and_schema_error_remain_failures_without_fallback():
    for text,status in [('not json','schema_error'),('{"status":"uncertain","taxonomy_error":[]}','uncertain')]:
        b=Backend([text]);r=run_shared(rec(),SCOPE,b,{'max_new_tokens':768,'context_limit':16384},lambda _:None)
        assert r['self']['status']==status and r['execution']['status']==status and len(b.messages)==1


def test_real_compile_diagnostic_reused_without_execution_or_extra_call():
    record=rec();record.provenance['_task3_compile_check']={'status':'error','diagnostic':'actual compiler error'}
    b=Backend([raw(actual='<compile_error>')])
    def forbidden(_):raise AssertionError('compile error cannot run')
    r=run_shared(record,SCOPE,b,{'max_new_tokens':768,'context_limit':16384},forbidden)
    assert len(b.messages)==1 and r['execution']['observed']['actual']['termination']=='compile_error'


def test_continuation_cannot_claim_observation_on_changed_input():
    b=Backend([raw(),raw(input='3')])
    r=run_shared(rec(),SCOPE,b,{'max_new_tokens':768,'context_limit':16384},lambda w:{'returncode':0,'stdout':'0','stderr':'','timeout':False,'executed':True})
    assert r['execution']['status']=='schema_error' and r['self']['status']=='defect'


def test_payload_never_projects_gold_or_requested_level():
    text=json.dumps(build_messages(rec(),SCOPE))
    assert not any(k in text for k in ['SECRET_','gold_taxonomy','requested_level','counterpart','mutation'])


def test_sandbox_setup_failure_is_unknown_infrastructure_not_program_failure():
    b=Backend([raw()])
    def broken(_):raise subprocess.SubprocessError('preexec failed')
    r=run_shared(rec(),SCOPE,b,{'max_new_tokens':768,'context_limit':16384},broken)
    assert r['execution']['status']=='execution_error'and r['execution']['output']is None and len(b.messages)==1


def test_preflight_failure_is_journaled_but_not_counted_as_model_call():
    b=Backend([]);journal=[]
    r=run_shared(rec(),SCOPE,b,{'max_new_tokens':768,'context_limit':1},lambda _:None,capture=journal.append)
    assert not b.messages and r['self']['status']=='schema_error'
    assert journal[0]['generation_attempted']is False


def test_model_source_and_compiler_bind_to_the_executed_submission(tmp_path):
    from scripts.task3_round23_infer import validate_executable_binding
    record=rec();work=tmp_path/'work';work.mkdir();(work/'source.cpp').write_text(record.code);(work/'program').write_bytes(b'trusted test artifact')
    entry={'jail':str(tmp_path),'source_sha256':hashlib.sha256(record.code.encode()).hexdigest(),'compiler':{'status':'pass','stderr':'','binary_sha256':hashlib.sha256((work/'program').read_bytes()).hexdigest()}}
    validate_executable_binding(record,entry)
    record.code+=' ';
    with pytest.raises(ValueError):validate_executable_binding(record,entry)


def test_continuation_preflight_records_zero_marginal_model_calls():
    b=Backend([raw()]);count=len(b.tokenizer.apply_chat_template(build_messages(rec(),SCOPE),tokenize=True,add_generation_prompt=True))
    r=run_shared(rec(),SCOPE,b,{'max_new_tokens':768,'context_limit':count+768},lambda w:{'returncode':0,'stdout':'0','stderr':'','timeout':False,'executed':True})
    assert len(b.messages)==1 and r['execution']['status']=='schema_error'and r['execution']['marginal_calls']==0
