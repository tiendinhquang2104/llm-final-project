"""Artificial fixtures only: compact contracts must preserve evidence failures."""
import copy
import importlib
import json

import pytest


@pytest.fixture
def c():
    class LazyContract:
        def __getattr__(self,name):
            try:return getattr(importlib.import_module('src.task3.compact'),name)
            except ModuleNotFoundError:pytest.fail('compact contract is not implemented')
    return LazyContract()


@pytest.fixture
def task():
    return dict(statement='Read n integers and print their sum.', exam_type='single_problem',
                problems=[], grading_policy={}, code='int sum=0; for(int i=0;i<=n;i++) sum += a[i];',
                compiler={'status':'unavailable','diagnostic':''}, tests={'status':'not_run','cases':[]})


def finding(**changes):
    return dict(scope='whole', quote='i<=n', observed='Đọc cả phần tử thứ n.',
                conflict='Miền dữ liệu chỉ có n phần tử.', when='n phần tử hợp lệ.',
                labels=['Lỗi vòng lặp'], **changes)


def raw(findings=None, verdict='error'):
    return json.dumps(dict(verdict=verdict, reason='Đã đối chiếu source với miền dữ liệu.',
                           findings=[finding()] if findings is None else findings), ensure_ascii=False)


def test_machine_fields_not_required_or_sent(c, task):
    result=c.parse(raw(),task,'whole')
    f=result['selected_findings'][0]
    assert f['id']=='F1' and f['source_span']=={'start_line':1,'end_line':1}
    assert f['evidence_type']=='static' and f['evidence_reference']['compiler_status']=='unavailable'
    payload=json.loads(c.diagnosis_messages({**task,'taxonomy_error':['gold'],'feedback':'teacher','level':4},'whole')[1]['content'])
    assert not {'taxonomy_error','feedback','level','confidence','evidence_reference','finding_id'}&set(payload)


def test_partial_valid_survives_bad_quote(c,task):
    bad={**finding(),'quote':'sum -= a[i]'}
    result=c.parse(raw([finding(),bad]),task,'whole')
    assert result['taxonomy_error']==['Lỗi vòng lặp']
    assert len(result['selected_findings'])==1 and len(result['rejected'])==1
    assert result['coverage']=='partial_model_assessment'


@pytest.mark.parametrize('quote',['i<n','sum -= a[i]','', 'not_in_source'])
def test_bad_quote_never_repaired_to_nearest(c,task,quote):
    result=c.parse(raw([{**finding(),'quote':quote}]),task,'whole')
    assert not result['publishable'] and result['taxonomy_error'] is None


def test_whitespace_normalization_preserves_tokens(c,task):
    result=c.parse(raw([{**finding(),'quote':'i <= n'}]),task,'whole')
    assert result['selected_findings'][0]['quote']=='i<=n'
    assert result['selected_findings'][0]['quote_normalization']=='token_whitespace'


def test_comment_quote_cannot_support_finding(c,task):
    task['code']='// i<=n\nint main() {}'
    assert not c.parse(raw(),task,'whole')['publishable']


def test_uncertainty_cannot_be_promoted_from_lexical_match(c,task):
    result=c.parse(raw(verdict='uncertain'),task,'whole')
    assert result['status']=='candidate_unverified' and result['taxonomy_error'] is None
    assert not result['publishable']


def test_clean_requires_explicit_reason_and_no_claims(c,task):
    assert c.parse(raw([],verdict='clean'),task,'whole')['taxonomy_error']==[]
    assert not c.parse(raw(verdict='clean'),task,'whole')['publishable']
    with pytest.raises(ValueError):c.parse('{"verdict":"clean","reason":"","findings":[]}',task,'whole')


def test_single_finding_multilabel_needs_overlap_reason(c,task):
    f={**finding(),'labels':['Lỗi vòng lặp','Lỗi mảng/chuỗi']}
    assert not c.parse(raw([f]),task,'whole')['publishable']
    f['overlap_reason']='Lỗi vòng lặp: miền lặp dư; Lỗi mảng/chuỗi: truy cập phần tử n ngoài mảng.'
    d=c.parse(raw([f]),task,'whole')
    assert d['taxonomy_error']==['Lỗi vòng lặp','Lỗi mảng/chuỗi']
    assert d['selected_findings'][0]['primary']=='Lỗi vòng lặp'
    assert d['selected_findings'][0]['secondary']==['Lỗi mảng/chuỗi']


def test_invalid_label_is_not_synonym_normalized(c,task):
    assert not c.parse(raw([{**finding(),'labels':['off_by_one']}]),task,'whole')['publishable']


def test_unknown_scope_does_not_become_whole(c,task):
    assert not c.parse(raw([{**finding(),'scope':'P9'}]),task,'whole')['publishable']


def test_runner_supplies_scope_when_model_omits_it(c,task):
    f=finding();del f['scope']
    assert c.parse(raw([f]),task,'whole')['selected_findings'][0]['subproblem']=='whole'


def test_descriptive_location_is_not_scope_metadata(c,task):
    f={**finding(),'scope':'loop condition'}
    d=c.parse(raw([f]),task,'whole')
    assert d['selected_findings'][0]['subproblem']=='whole'
    assert d['selected_findings'][0]['model_location']=='loop condition'


@pytest.mark.parametrize('source,quote',[('int a;','inta;'),('x++;','x+ +;'),('s="a b";','s="ab";')])
def test_token_normalization_cannot_change_semantics(c,task,source,quote):
    task['code']=source
    assert not c.parse(raw([{**finding(),'quote':quote}]),task,'whole')['publishable']


@pytest.mark.parametrize('source,quote',[
    ('x=1e3;','x = 1 e3;'),('x=0x1p+2;','x = 0x1p + 2;'),
    ('x &= 1;','x & = 1;'),('x |= 1;','x | = 1;'),
    ('#define F(x) x','#define F (x) x'),('s="a"_tag;','s="a" _tag;'),
    ('obj.*ptr;','obj. *ptr;'),('??=define F(x) x','??=define F (x) x')])
def test_reviewed_lexical_whitespace_counterexamples(c,task,source,quote):
    task['code']=source
    assert not c.parse(raw([{**finding(),'quote':quote}]),task,'whole')['publishable']


def test_fence_only_repair_not_truncation(c,task):
    assert c.parse('```json\n'+raw()+'\n```',task,'whole')['publishable']
    with pytest.raises(ValueError):c.parse('```json\n'+raw()[:-2],task,'whole')


def test_l1_context_without_cause_or_identifier(c,task):
    d=c.parse(raw(),task,'whole');view=c.view(d,1,'tính tổng các số')
    text=json.dumps(view,ensure_ascii=False)
    assert 'tính tổng' in text
    assert all(secret not in text for secret in ['i<=n','source_span','conflict','F1','sum','whole'])


def test_l2_no_repair_l3_has_direction_instruction(c,task):
    d=c.parse(raw(),task,'whole');d['selected_findings'][0]['repair']='REPAIR_SECRET'
    assert 'REPAIR_SECRET' not in json.dumps(c.view(d,2,'tổng'))
    assert 'REPAIR_SECRET' in json.dumps(c.view(d,3,'tổng'))


def test_oracle_cannot_enter_production(c,task):
    d=c.parse(raw(),task,'whole');d['provenance']='offline_oracle'
    with pytest.raises(ValueError):c.require_production(d)


def test_semantic_rejection_preserves_other_findings(c,task):
    d=c.parse(raw([finding(),{**finding(),'quote':'sum += a[i]','labels':['Lỗi logic']}]),task,'whole')
    checked=c.apply_semantic(d,{'clean_supported':False,'findings':[{'id':'F1','supported':True},{'id':'F2','supported':False}]})
    assert checked['taxonomy_error']==['Lỗi vòng lặp'] and len(checked['selected_findings'])==1
    assert len(checked['semantic_rejected'])==1


def test_compiler_pass_does_not_override_logic(c,task):
    task['compiler']['status']='compiled'
    assert c.parse(raw(),task,'whole')['taxonomy_error']==['Lỗi vòng lặp']
