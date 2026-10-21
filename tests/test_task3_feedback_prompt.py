"""Protocol regressions: leaks, source isolation, scoring and artifact binding."""
import copy
import json
from dataclasses import replace

import pytest

from tests.test_task3_round14 import sample


def api():
    from src.task3 import feedback_prompt
    return feedback_prompt


def test_nested_gold_teacher_and_reference_never_enter_prompt():
    m=api(); r=replace(sample(2), gold_feedback='SECRET_TEACHER', gold_taxonomy=['Lỗi logic'],
        provenance={'reference_finding':'SECRET_FINDING','_task3_compile_check':{'status':'unavailable','diagnostic':''}},
        problems=[{'pid':'P1','statement':'sum','teacher_feedback':'SECRET_NESTED'}])
    text=json.dumps(m.messages(r, [], 'B'), ensure_ascii=False)
    assert all(x not in text for x in ['SECRET_TEACHER','SECRET_FINDING','SECRET_NESTED','gold_taxonomy','reference_finding'])
    assert r.code in json.loads(m.messages(r, [], 'B')[-1]['content'])['code']


def test_examples_bound_to_train_source_and_isolated_from_query():
    m=api();r=replace(sample(2),split='synthetic-train',source='synthetic',sample_id='train-one',exam_id='TRAIN')
    ex={'sample_id':r.sample_id,'level':2,'code':r.code,'statement':r.statement,'family':r.exam_id,
        'provenance':{'partition':'synthetic-train','author':'agent-reviewed'},
        'output':{'taxonomy_error':['Lỗi logic'],'feedback':'Trong main, biểu thức tính tổng sai yêu cầu.'}}
    m.validate_bank([ex], {r.sample_id:r}, [])
    for altered in [dict(ex,code=r.code+'changed'),dict(ex,provenance={'partition':'public'})]:
        with pytest.raises(ValueError):m.validate_bank([altered],{r.sample_id:r},[])
    with pytest.raises(ValueError):m.validate_bank([ex],{r.sample_id:r},[r])


def test_proxy_disclosure_wrong_claim_unknown_and_generic_do_not_pass():
    m=api();v={'location_correct':True,'cause_correct':True,'feasible_repair':True,'status_correct':True}
    assert m.proxy_score(v,2,False)==1
    assert m.proxy_score(dict(v,repair_disclosure=True),2,False)==0
    assert m.proxy_score(dict(v,false_technical_claim=True),4,False)==0
    assert m.proxy_score(dict(v,unknown=True),3,False)==0
    assert m.proxy_score({'generic':True},2,False)==0
    assert m.proxy_score({'generic':True},1,False)==.5
    assert m.proxy_score(dict(v,feasible_repair=False),3,False)==.5
    assert m.proxy_score({'status_correct':True},1,False)==1


def test_manifest_binds_prompt_model_source_output_and_detects_tamper(tmp_path):
    m=api();p=tmp_path/'output.json';p.write_text('{}'); f=tmp_path/'seal.json'
    m.seal(f,[p],{'model_revision':'pin','prompt_sha256':'prompt','input_sha256':'input'})
    m.verify_seal(f)
    p.write_text('{"edited":true}')
    with pytest.raises(ValueError,match='hash'):m.verify_seal(f)


def test_full_query_never_silently_truncated_and_examples_drop_in_fixed_order():
    from src.task3.inference import MockTokenizer
    m=api();r=sample(3);t=MockTokenizer();cfg={'context_limit':1,'max_new_tokens':100}
    with pytest.raises(ValueError,match='never truncate'):m.fitted(r,[],t,cfg,arm='B')
    msg,info=m.fitted(r,[],t,dict(cfg,context_limit=20000),arm='B')
    assert json.loads(msg[-1]['content'])['code']==r.code


def test_same_level_max_two_distinct_families_no_evaluation_label_selection():
    m=api();r=sample(2)
    bank=[{'sample_id':str(i),'level':level,'family':'F'+str(i%3),'code':str(i)} for i,level in enumerate([2,2,2,2,1,3])]
    a=m.choose_examples(r,bank)
    b=m.choose_examples(replace(r,gold_taxonomy=['Lỗi logic'],gold_feedback='secret'),bank)
    assert a==b and len(a)==2 and len({x['family'] for x in a})==2 and all(x['level']==2 for x in a)


def test_near_duplicate_renames_detected_but_independent_algorithm_survives():
    m=api()
    a='int solve(int n){int s=0;while(n){s+=n%10;n/=10;}return s;}'
    b='int f(int x){int total=0;while(x){total+=x%10;x/=10;}return total;}'
    assert m.similarity(a,b)['renamed_identity']
    c='int solve(int n){return n<2?0:1;}'
    assert m.similarity(a,c)['structural_jaccard']<.75


def test_strict_schema_rejects_extra_keys_and_unofficial_taxonomy():
    from src.task3.round15 import parse_response
    with pytest.raises(ValueError):parse_response('{"taxonomy_error":[],"feedback":"ok","diagnosis":{}}')
    with pytest.raises(ValueError):parse_response('{"taxonomy_error":["other"],"feedback":"ok"}')
