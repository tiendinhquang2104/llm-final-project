"""Artificial contracts for the prompt-only comparison; no real/public code."""
import json
from dataclasses import replace
import pytest
from tests.test_task3_round14 import sample
from src.task3.inference import MockTokenizer


def test_compact_prompt_has_only_required_fields_and_preserves_entire_query():
    from src.task3.round15 import build_messages
    r=replace(sample(3),code='// HEAD\n'+sample(3).code+'\n// TAIL')
    messages=build_messages(r,[])
    text=json.dumps(messages,ensure_ascii=False)
    assert r.code in json.loads(messages[-1]['content'])['code']
    payload=json.loads(messages[-1]['content'])
    assert payload['requested_level']==3
    assert 'taxonomy_error' in messages[0]['content'] and 'feedback' in messages[0]['content']
    assert 'rationales' not in text and 'assessment' not in text
    assert r.sample_id not in text and 'gold_taxonomy' not in text


def test_few_shot_changes_only_examples_with_same_system_and_query():
    from src.task3.round15 import build_messages
    ex={'level':3,'statement':'Return zero.','code':'int main(){return 1;}',
        'compiler':{'status':'compiled','diagnostic':''},'output':{'taxonomy_error':['Lỗi logic'],'feedback':'Hàm main trả 1 khác yêu cầu; đổi giá trị trả về thành 0.'}}
    zero=build_messages(sample(3),[]);few=build_messages(sample(3),[ex])
    assert zero[0]==few[0] and zero[-1]==few[-1]
    assert few[1]['role']=='user' and few[2]['role']=='assistant'
    assert json.loads(few[2]['content'])==ex['output']


def test_budget_drops_whole_examples_but_never_query_source():
    from src.task3.round15 import fitted_messages
    r=sample(2);ex={'level':2,'statement':'s'*1000,'code':'int main(){return 7;}',
        'compiler':{},'output':{'taxonomy_error':['Lỗi logic'],'feedback':'Hàm main trả khác yêu cầu.'}}
    base,meta=fitted_messages(r,[],MockTokenizer(),{'context_limit':10000,'max_new_tokens':50})
    cap=len(MockTokenizer().apply_chat_template(base,add_generation_prompt=True))+60
    msgs,meta=fitted_messages(r,[ex],MockTokenizer(),{'context_limit':cap,'max_new_tokens':50})
    assert meta['examples_used']==0 and meta['examples_dropped']==1
    assert json.loads(msgs[-1]['content'])['code']==r.code
    with pytest.raises(ValueError,match='context'):
        fitted_messages(r,[],MockTokenizer(),{'context_limit':20,'max_new_tokens':50})


def test_schema_preserves_explicit_model_empty_and_does_not_fabricate_parse_results():
    from src.task3.round15 import parse_response
    raw=json.dumps({'taxonomy_error':[],'feedback':'Em hãy đối chiếu bài với đề.'})
    assert parse_response(raw)['taxonomy_error']==[]
    assert parse_response('```json\n'+raw+'\n```')['taxonomy_error']==[]
    for text in ['broken',json.dumps({'feedback':'x'}),json.dumps({'taxonomy_error':['syntax_error'],'feedback':'x'})]:
        with pytest.raises(ValueError):parse_response(text)


def test_level3_valid_schema_is_not_rejected_for_action_keywords_fence_or_cjk():
    from src.task3.round15 import process_response
    texts=['Trong hàm main, giá trị trả sai; đặt kết quả về đúng tổng của hai đầu vào.',
           'Hàm main thiếu giá trị trả về. Thêm return x; cuối hàm.',
           'Chưa đủ thông tin để đưa ra hướng sửa hữu ích.',
           'Nhận xét 未初始化.']
    for text in texts:
        out=process_response(json.dumps({'taxonomy_error':['Lỗi logic'],'feedback':text}),3)
        assert out['feedback']==text


def test_level2_preserves_useful_diagnosis_but_rejects_explicit_repair():
    from src.task3.round15 import process_response
    text='Ở hàm main, giá trị trả về là x trong khi đề yêu cầu tổng hai đầu vào.'
    assert process_response(json.dumps({'taxonomy_error':['Lỗi logic'],'feedback':text}),2)['feedback']==text
    with pytest.raises(ValueError,match='disclosure'):
        process_response(json.dumps({'taxonomy_error':['Lỗi logic'],'feedback':'Ở main thiếu return; hãy thêm return x; cuối hàm.'}),2)


def test_example_validation_binds_train_source_and_records_level_override():
    from src.task3.round15 import validate_examples
    r=sample(2)
    ex={'sample_id':r.sample_id,'level':3,'original_level':r.target_feedback_level,
        'statement':r.statement,'code':r.code,'compiler':{},
        'output':{'taxonomy_error':['Lỗi logic'],'feedback':'Hàm main sai giá trị; đổi kết quả trả về.'},
        'provenance':{'source':r.split,'reference_source':'assistant_source_review_train_only_not_teacher','bank_only_level_override':True}}
    assert validate_examples([ex],[r])==[ex]
    with pytest.raises(ValueError,match='source'):
        validate_examples([{**ex,'code':r.code+' // changed'}],[r])
    with pytest.raises(ValueError,match='train'):
        validate_examples([{**ex,'provenance':{**ex['provenance'],'source':'public'}}],[r])


def test_configured_example_count_is_obeyed():
    from src.task3.round15 import fitted_messages
    ex={'level':2,'statement':'Return zero.','code':'int main(){return 1;}','compiler':{},
        'output':{'taxonomy_error':['Lỗi logic'],'feedback':'Hàm main trả sai giá trị.'}}
    _,meta=fitted_messages(sample(2),[ex]*3,MockTokenizer(),{'context_limit':20000,'max_new_tokens':50,'few_shot_k':2})
    assert meta['examples_used']==2


def test_example_supplied_problem_and_policy_metadata_must_match_source():
    from src.task3.round15 import validate_examples
    r=sample(2);ex={'sample_id':r.sample_id,'level':2,'original_level':r.target_feedback_level,
        'statement':r.statement,'code':r.code,'compiler':{},'problems':[{'prototype':'wrong function'}],
        'output':{'taxonomy_error':['Lỗi logic'],'feedback':'Hàm main trả sai giá trị.'},
        'provenance':{'source':r.split,'reference_source':'assistant_source_review_train_only_not_teacher','bank_only_level_override':False}}
    with pytest.raises(ValueError,match='metadata'):validate_examples([ex],[r])


def test_raw_metrics_use_the_same_strict_two_key_schema_as_new_prompts():
    from scripts.task3_round15 import parse_raw_candidate
    with pytest.raises(ValueError):parse_raw_candidate(json.dumps({'taxonomy_error':[],'feedback':'Đối chiếu lại đề.','extra':1}))
