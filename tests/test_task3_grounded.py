"""Artificial contracts, never examples for inference."""
import copy
import json
from types import SimpleNamespace
import pytest
from src.task3 import grounded as g
from src.task3.inference import Generation, MockTokenizer


def task():
    return dict(statement='Print the sum for n >= 0.',exam_type='single_problem',problems=[],
                grading_policy={},code='int main(){int n=0; int total=0; total=n-1;}',
                compiler={'status':'compiled','diagnostic':''},tests={'status':'not_run','cases':[]})


def diagnosis():
    return dict(status='confirmed_error',reason='Found a source-backed defect.',
                scope={'assessed':['whole'],'blocked':[]},findings=[dict(
        id='F1',subproblem='whole',quote='total=n-1;',requirement_ref='statement',
        condition='n = 0',observed='Tổng nhận giá trị -1.',
        conflict='Giá trị âm trái tổng yêu cầu bằng 0.',evidence_type='static',
        evidence_reference='source',confidence='high',labels=['Lỗi logic'],disputed=False,
        repair='Tính tổng theo miền dữ liệu của đề.')])


def accepted(): return g.parse_diagnosis(json.dumps(diagnosis()),task())


def test_missing_module_contract():
    assert callable(getattr(g,'level_view',None))


def test_input_projection_drops_gold_level_feedback_nested():
    t=task();t.update(gold_taxonomy=['Lỗi hàm'],feedback='ANSWER',target_feedback_level='L1')
    t['problems']=[dict(pid='P1',statement='Sum',prototype='int f();',feedback='ANSWER',gold=['x'])]
    payload=json.loads(g.diagnosis_messages(t)[1]['content'])
    assert set(payload)==g.TASK_KEYS
    assert set(payload['problems'][0])=={'pid','statement','prototype'}
    assert 'ANSWER' not in json.dumps(payload)


@pytest.mark.parametrize('bad',['{}','{"status":"clean"}','{"status":NaN}',
    '{"status":1,"status":2}','```cpp\n{}\n```'])
def test_parse_failures_never_clean(bad):
    with pytest.raises(ValueError): g.parse_diagnosis(bad,task())


def test_compiled_is_not_clean_and_optional_single_json_fence():
    d=g.parse_diagnosis('```json\n'+json.dumps(diagnosis())+'\n```',task())
    assert d['taxonomy_error']==['Lỗi logic']
    assert d['selected_findings'][0]['source_span']=={'start_line':1,'end_line':1}


def test_unknown_diagnosis_is_distinct_from_reasoned_empty():
    d=diagnosis();d.update(status='plausible_but_unverified',findings=[])
    x=g.parse_diagnosis(json.dumps(d),task())
    assert x['taxonomy_error'] is None and not x['publishable']
    d['status']='no_error_found_with_available_evidence'
    x=g.parse_diagnosis(json.dumps(d),task())
    assert x['taxonomy_error']==[] and x['publishable']
    d['reason']=''
    with pytest.raises(ValueError):g.parse_diagnosis(json.dumps(d),task())


@pytest.mark.parametrize('mutate',[
    lambda d:d['findings'][0].update(quote='total=123;'),
    lambda d:d['findings'][0].update(labels=['syntax_error']),
    lambda d:d['findings'][0].update(requirement_ref='P9'),
    lambda d:d['findings'][0].update(evidence_type='compiler',evidence_reference='made-up'),
    lambda d:d['findings'][0].update(evidence_type='trusted_test',evidence_reference='made-up'),
    lambda d:d['findings'][0].update(condition=''),
])
def test_source_requirement_and_evidence_fail_closed(mutate):
    d=diagnosis();mutate(d)
    with pytest.raises(ValueError):g.parse_diagnosis(json.dumps(d),task())


def test_comment_quote_and_uncertain_findings_cannot_support_labels():
    t=task();t['code']+=' // imaginary=5;'
    d=diagnosis();d['findings'][0]['quote']='imaginary=5;'
    with pytest.raises(ValueError):g.parse_diagnosis(json.dumps(d),t)
    d=diagnosis();d['findings'][0]['disputed']=True
    with pytest.raises(ValueError):g.parse_diagnosis(json.dumps(d),task())


def test_independent_multilabel_and_explicit_overlap():
    d=diagnosis();f=copy.deepcopy(d['findings'][0]);f.update(
        id='F2',labels=['Lỗi nhập/xuất'],quote=task()['code'],condition='Mọi đầu vào hợp lệ.',
        observed='Hàm main không xuất kết quả nào.',conflict='Đề yêu cầu in tổng nhưng không có thao tác xuất kết quả.')
    d['findings'].append(f)
    assert g.parse_diagnosis(json.dumps(d),task())['taxonomy_error']==['Lỗi nhập/xuất','Lỗi logic']
    d=diagnosis();d['findings'][0]['labels']+=['Lỗi vòng lặp']
    with pytest.raises(ValueError,match='one primary'):g.parse_diagnosis(json.dumps(d),task())


def test_l1_view_has_no_source_cause_labels_location_or_repair():
    v=g.level_view(accepted(),1)
    text=json.dumps(v,ensure_ascii=False)
    for forbidden in ['total','n = 0','Lỗi logic','F1','whole','-1','Tính tổng']:
        assert forbidden not in text
    assert set(v)=={'level','status','evidence_limit'}


def test_l2_gets_diagnosis_without_repair_l3_gets_direction():
    d=accepted();v=g.level_view(d,2)
    assert 'repair' not in json.dumps(v)
    assert 'total=n-1;' not in json.dumps(v)
    assert 'conflict' in v['findings'][0]
    assert 'repair' in g.level_view(d,3)['findings'][0]


def test_single_problem_with_supplied_pid_accepts_whole_scope():
    t=task();t['problems']=[dict(pid='P1',statement=t['statement'])]
    assert g.parse_diagnosis(json.dumps(diagnosis()),t)['publishable']


def test_l2_view_has_source_bound_location_for_single_problem():
    assert g.level_view(accepted(),2)['findings'][0]['source_span']=={'start_line':1,'end_line':1}


def test_renderer_citations_bind_each_sentence_without_allowing_new_error():
    d=accepted()
    r=g.parse_feedback(json.dumps({'sentences':[{'text':'Phần tính tổng cho kết quả âm vì phép tính hiện tại giảm n đi một.','finding_ids':['F1']}]}),d,2)
    assert r['feedback'] and r['sentence_support'][0]['finding_ids']==['F1']
    with pytest.raises(ValueError):g.parse_feedback(json.dumps({'sentences':[{'text':'Sai.','finding_ids':['F99']}]}),d,2)
    with pytest.raises(ValueError):g.parse_feedback(json.dumps({'sentences':[{'text':'Đúng.','finding_ids':[]}]}),d,2)


def test_l1_internal_trace_binds_status_claim_without_exposing_ids_to_renderer():
    d=accepted()
    r=g.parse_feedback(json.dumps({'sentences':[{'text':'Bài làm còn có điểm chưa phù hợp với yêu cầu.','finding_ids':[]}]}),d,1)
    assert r['sentence_support'][0]['finding_ids']==['F1']
    assert 'F1' not in json.dumps(g.level_view(d,1))


def test_prerequisite_blocked_scope_not_silently_assessed():
    t=task();t.update(exam_type='multi_problem',problems=[dict(pid='P1',statement='A'),dict(pid='P2',statement='B')],grading_policy='Nếu P1 (đọc file) sai thì các câu P2–P4 không được chấm.')
    d=diagnosis();d['scope']={'assessed':['P1'],'blocked':['P2']};d['findings'][0].update(subproblem='P2',requirement_ref='P2')
    with pytest.raises(ValueError):g.parse_diagnosis(json.dumps(d),t)
    d['findings'][0].update(subproblem='P1',requirement_ref='P1')
    assert g.parse_diagnosis(json.dumps(d),t)['scope']['blocked']==['P2']


def test_partial_multi_clean_and_unbound_blocking_are_rejected():
    t=task();t.update(exam_type='multi_problem',problems=[dict(pid='P1',statement='A'),dict(pid='P2',statement='B')],grading_policy='Prefer concise code.')
    d=diagnosis();d.update(status='no_error_found_with_available_evidence',findings=[],scope={'assessed':['P1'],'blocked':[]})
    with pytest.raises(ValueError,match='scope coverage'):g.parse_diagnosis(json.dumps(d),t)
    d=diagnosis();d['scope']={'assessed':['P1'],'blocked':['P2']};d['findings'][0].update(subproblem='P1',requirement_ref='P1')
    with pytest.raises(ValueError,match='prerequisite'):g.parse_diagnosis(json.dumps(d),t)


def test_span_matches_active_occurrence_when_comment_has_same_quote():
    t=task();t['code']='// total=n-1;\n'+t['code']
    d=g.parse_diagnosis(json.dumps(diagnosis()),t)
    assert d['selected_findings'][0]['source_span']['start_line']==2


def test_missing_evidence_keeps_explicit_status():
    t=task();t.pop('compiler');t.pop('tests')
    p=g.task_payload(t)
    assert p['compiler']['status']=='unavailable' and p['tests']['status']=='not_run'
    assert g.parse_diagnosis(json.dumps(diagnosis()),p)['publishable']


def test_semantic_guard_detects_implicit_repair_without_regex_authority():
    bad={'supported':True,'level_compliant':False,'main_covered':True,'natural_vietnamese':True,'reason_codes':['L2_IMPLICIT_REPAIR']}
    assert not g.parse_guard(json.dumps(bad))['accepted']
    assert g.safe_retry_codes(['L2_IMPLICIT_REPAIR','secret total=0'])==['L2_IMPLICIT_REPAIR']
    good={**bad,'level_compliant':True,'reason_codes':[]}
    assert g.parse_guard(json.dumps(good))['accepted']
    with pytest.raises(ValueError):g.parse_guard('{"supported":true}')


def test_bound_journal_resume_does_not_resample_or_accept_changed_prompt(tmp_path):
    from src.task3.grounded_runner import Journal
    class Backend:
        tokenizer=MockTokenizer()
        def __init__(self):self.calls=0
        def generate(self,m,c):self.calls+=1;return Generation('{}',2,0.01,'eos',True)
    b=Backend();j=Journal(tmp_path,b,{'max_new_tokens':10,'context_limit':1000},'freezehash')
    m=[{'role':'user','content':'TEST-ONLY'}]
    assert j.call('one',m)['raw_text']=='{}'
    assert j.call('one',m)['raw_text']=='{}' and b.calls==1
    with pytest.raises(ValueError):j.call('one',[{'role':'user','content':'changed'}])
    with pytest.raises(ValueError):Journal(tmp_path,b,{},'different')
