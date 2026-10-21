"""Artificial boundary tests: never load competition/private sources."""
import json
from dataclasses import replace
import pytest
from src.task3.inference import Generation, MockTokenizer
from src.task3.schema import Task3Record
from src.task3 import requirement_evidence as subject


def record(**kw):
    values=dict(source='synthetic',sample_id='TEST-1',original_submission_id='TEST-1',
      exam_id='TEST',exam_type='single_problem',statement='Read x and print x.',
      grading_policy='',code_path='test.cpp',code='int main(){ int x; cin >> x; cout << 0; }',
      target_feedback_level='Level 2 - Chẩn đoán',split='synthetic-train',
      gold_taxonomy=['Lỗi style'],gold_feedback='SECRET TEACHER')
    return Task3Record(**(values|kw))


def diag(status='có lỗi',quote='cout << 0;',pid='P1'):
    return {'requirements':[{'pid':pid,'status':status,'quote':quote,
       'requirement':'Print the input x.','behavior':'Prints zero.',
       'reason':'Input 7 gives 0 instead of 7.','counterexample':'7 -> 7'}]}


class SequenceBackend:
    tokenizer=MockTokenizer()
    def __init__(self,items):self.items=iter(items);self.calls=[]
    def generate(self,messages,config):
        self.calls.append(messages)
        return Generation(json.dumps(next(self.items),ensure_ascii=False),10,.01,'test',True)


def test_gold_and_teacher_never_reach_either_stage():
    r=record();d=diag()
    for messages in [subject.diagnosis_messages(r),subject.render_messages(r,d)]:
        s=json.dumps(messages,ensure_ascii=False)
        assert 'SECRET TEACHER' not in s
        assert 'Lỗi style' not in json.dumps(messages[-1],ensure_ascii=False)
        assert 'gold_' not in s
    assert 'requested_level' not in subject.diagnosis_messages(r)[-1]['content']


def test_quote_linkage_does_not_certify_semantics():
    kept,audit=subject.check_diagnosis(record(),diag())
    assert kept['requirements'][0]['status']=='có lỗi'
    assert audit['semantic_verification']=='not_performed'
    assert audit['counterexamples'][0]['status']=='unverified_not_executed'
    with pytest.raises(ValueError,match='quote'):
        subject.check_diagnosis(record(),diag(quote='invented line'))


def test_uncertain_never_renders_empty_or_praise():
    backend=SequenceBackend([diag(status='chưa đủ căn cứ')]*2)
    result=subject.run_candidate(record(),backend,{'max_new_tokens':1024,'context_limit':16384},
       {'taxonomy_error':['Lỗi logic'],'feedback':'BASE unchanged'})
    assert result['fallback_used'] and result['uncertain']
    assert result['output']=={'taxonomy_error':['Lỗi logic'],'feedback':'BASE unchanged'}
    assert len(backend.calls)==2
    assert len(result['attempts'])==2


def test_no_r15_completion_stays_error():
    backend=SequenceBackend([{'oops':1}]*2)
    result=subject.run_candidate(record(),backend,{'max_new_tokens':1024,'context_limit':16384},None)
    assert result['output'] is None and result['status']=='error' and result['fallback_used']


def test_defect_cannot_render_empty_taxonomy():
    backend=SequenceBackend([diag(),{'taxonomy_error':[],'feedback':'Tốt.'},
       {'taxonomy_error':['Lỗi logic','Lỗi nhập/xuất'],'feedback':'Ở cout, chương trình in 0 bất kể số vừa đọc.'}])
    result=subject.run_candidate(record(),backend,{'max_new_tokens':1024,'context_limit':16384},None)
    assert result['output']['taxonomy_error']==['Lỗi logic','Lỗi nhập/xuất']
    assert not result['fallback_used'] and len(result['attempts'])==3


def test_original_metric_accounts_for_missing_completion_and_all_ten_labels():
    refs=[{'sample_id':'a','labels':['Lỗi logic']},{'sample_id':'b','labels':[]}]
    out={'a':None,'b':None}
    m=subject.annotation_metrics(refs,out)
    assert m['exact_match']==0 and m['completed']==0 and m['requested']==2
    assert m['per_label']['Lỗi logic']['fn']==1
    assert len(m['per_label'])==10
    assert m['per_label']['Lỗi style']['support']==0


def test_each_requirement_must_be_accounted_for():
    r=record(exam_type='multi_problem',problems=[{'pid':'P1'},{'pid':'P2'}])
    with pytest.raises(ValueError,match='requirements'):
        subject.check_diagnosis(r,diag())
