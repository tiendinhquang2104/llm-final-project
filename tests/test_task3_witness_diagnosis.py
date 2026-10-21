import json
from src.task3.inference import Generation,MockTokenizer
from src.task3.schema import Task3Record
from src.task3 import witness_diagnosis as wd


def rec():
    return Task3Record(source='synthetic',sample_id='opaque',original_submission_id='opaque',exam_id='TEST',exam_type='single_problem',statement='Read x, print it.',code_path='source.cpp',code='int main(){int x;cin>>x;cout<<0;}',grading_policy='',target_feedback_level='Level 2 - Chẩn đoán',gold_taxonomy=['Lỗi style'],gold_feedback='HIDDEN_TEACHER',provenance={'hidden_expected':'SECRET_ORACLE'})


def answer(status='defect'):
    return dict(status=status,pid='P1',quote='cout<<0;',requirement='Print x.',input={'stdin':'7','files':{}},predicted_actual={'termination':'ok','stdout':'0'},actual_reason='Literal zero is printed.',predicted_expected='7',expected_reason='Input x is seven.',mechanism='Constant output ignores x.',taxonomy_error=['Lỗi logic'])


def test_inference_projection_excludes_gold_oracle_and_level():
    messages=wd.messages(rec())
    text=json.dumps(messages,ensure_ascii=False)
    assert not any(k in text for k in ['HIDDEN_TEACHER','SECRET_ORACLE','gold_taxonomy','requested_level'])
    assert 'base_code' not in text and 'mutant' not in text


def test_uncertain_does_not_become_clean_fallback():
    class B:
        tokenizer=MockTokenizer()
        def generate(self,*a):return Generation(json.dumps({'status':'uncertain','taxonomy_error':[]}),5,.1,'test',True)
    rows=[];r=wd.run(rec(),B(),{'context_limit':16384,'max_new_tokens':1536},capture=rows.append)
    assert r['status']=='uncertain'and not r['fallback_used']and len(rows)==1


def test_invalid_quote_retries_bounded_and_retains_raw_errors():
    class B:
        tokenizer=MockTokenizer()
        def generate(self,*a):return Generation(json.dumps(answer()|{'quote':'not in code'}),5,.1,'test',True)
    r=wd.run(rec(),B(),{'context_limit':16384,'max_new_tokens':1536})
    assert r['status']=='schema_error'and len(r['attempts'])==2
    assert all(a['raw_text']for a in r['attempts'])


def test_valid_witness_is_a_prediction_not_a_certificate():
    class B:
        tokenizer=MockTokenizer()
        def generate(self,*a):return Generation(json.dumps(answer()),5,.1,'test',True)
    r=wd.run(rec(),B(),{'context_limit':16384,'max_new_tokens':1536})
    assert r['status']=='defect'and r['semantic_verification']=='not_performed_at_inference'
