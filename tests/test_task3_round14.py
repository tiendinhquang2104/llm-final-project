"""Round14 artificial tests; no public or real-validation examples."""
import json
from dataclasses import replace
import pytest
from tests.test_task3_dataset import record
from src.synth.taxonomy import LABEL_SPACE


def sample(level=2):
    from src.task3.round14 import sanitize
    r=replace(record('ARTIFACT-FIXTURE'),code='int main(){int x=1;return x;}',
              target_feedback_level=f'Level {level} - '+{1:'Gợi ý nhẹ',2:'Chẩn đoán',3:'Gợi ý sửa',4:'Lời giải mẫu'}[level])
    return sanitize(r,{'status':'compiled','diagnostic':''})


def value(labels=None,feedback='Vấn đề nằm ở hàm main: kết quả trả về khác yêu cầu.'):
    labels=['Lỗi logic'] if labels is None else labels
    return {'taxonomy_error':labels,'rationales':[{'taxonomy_group':g,'source_quote':'return x;',
        'reason':'Giá trị trả về khác yêu cầu đề.','confidence':'medium'} for g in labels],
        'assessment':'Model best-effort assessment, not proof of correctness.','uncertain':True,'feedback':feedback}


def test_input_and_prompts_do_not_use_gold_teacher_or_id():
    from src.task3.round14 import build_messages,sanitize
    r=replace(record('SECRET-ID'),gold_taxonomy=['Lỗi style'],gold_feedback='SECRET TEACHER')
    s=sanitize(r,{'status':'compiled','diagnostic':''})
    text=json.dumps(build_messages(s,'direct'),ensure_ascii=False)
    assert 'SECRET TEACHER' not in text and 'SECRET-ID' not in text
    assert 'gold_taxonomy' not in text and 'gold_feedback' not in text
    assert s.gold_taxonomy is None and s.gold_feedback is None and s.test_report is None


def test_positive_labels_need_matching_rationales_and_failure_is_not_empty():
    from src.task3.round14 import parse_assessment
    r=sample();v=value();out=parse_assessment(json.dumps(v),r,direct=True)
    assert out['taxonomy_error']==['Lỗi logic']
    for bad in ['BROKEN',json.dumps(dict(v,rationales=[])),json.dumps(dict(v,taxonomy_error=['syntax_error']))]:
        with pytest.raises(ValueError):parse_assessment(bad,r,direct=True)
    clean=parse_assessment(json.dumps(value(labels=[])),r,direct=True)
    assert clean['taxonomy_error']==[] and clean['epistemic_status']=='model_predicted_clean_unverified'


def test_warning_is_not_compile_error_and_correct_quote_is_not_semantic_proof():
    from src.task3.round14 import parse_assessment,build_messages
    r=sample();v=value(labels=['Lỗi biên dịch'])
    with pytest.raises(ValueError,match='compiler'):parse_assessment(json.dumps(v),r,direct=True)
    v=value();v['rationales'][0]['reason']='Biến x chưa được khởi tạo.'
    with pytest.raises(ValueError,match='contradict'):parse_assessment(json.dumps(v),r,direct=True)
    text=json.dumps(build_messages(r,'classify'),ensure_ascii=False)
    assert 'warning' in text and 'không chứng minh' in text


def test_level1_projection_never_discloses_diagnosis_even_if_model_does():
    from src.task3.round14 import finish_feedback
    out=finish_feedback(sample(1),value(),value()['feedback'])
    assert out['origin']=='level1_projection'
    assert 'main' not in out['feedback'] and 'x' not in out['feedback']


def test_level2_rejects_repair_inline_code_and_cjk():
    from src.task3.round14 import feedback_errors
    for text in ['Hãy thay x bằng 3 ở hàm main.','Vấn đề ở hàm main. Sửa thành `return 3;`.','Hàm main sai vì 未初始化.']:
        assert feedback_errors(sample(),['Lỗi logic'],text)


def test_level3_generic_direction_not_considered_useful_and_full_solution_blocked():
    from src.task3.round14 import feedback_errors
    assert feedback_errors(sample(3),['Lỗi logic'],'Hàm main trả sai giá trị. Hướng sửa: Kiểm tra lại.')
    assert feedback_errors(sample(3),['Lỗi logic'],'Hàm main trả sai.\n```cpp\nint main(){return 2;}\n```')
    assert not feedback_errors(sample(3),['Lỗi logic'],'Vị trí: hàm main. Giá trị trả về khác yêu cầu. Hướng sửa: Thay giá trị trả về x bằng hằng 0 theo yêu cầu đề.')


def test_feedback_cannot_add_unpredicted_group_or_praise_without_verification():
    from src.task3.round14 import feedback_errors
    assert feedback_errors(sample(),['Lỗi logic'],'Lỗi biên dịch ở hàm main do thiếu dấu chấm phẩy.')
    assert feedback_errors(sample(),[],'Bài làm hoàn toàn chính xác.')


def test_budget_covers_retry_and_rejects_essential_context_overflow():
    from src.task3.round14 import fitted_messages
    from src.task3.inference import MockTokenizer
    with pytest.raises(ValueError,match='context'):
        fitted_messages(sample(),'direct',MockTokenizer(),{'context_limit':20,'max_new_tokens':10},retry='format')


def test_level4_allows_full_solution_instead_of_tiny_certificate_gate():
    from src.task3.round14 import feedback_errors
    text='Hàm main cần trả kết quả theo đề. Lời giải:\n```cpp\n#include <iostream>\nint main(){int a,b;std::cin>>a>>b;std::cout<<a+b;}\n```'
    assert not feedback_errors(sample(4),['Lỗi logic'],text)


@pytest.mark.parametrize('text',[
 'Hàm main trả sai giá trị. Bổ sung phép cộng hai số đầu vào trước khi trả kết quả.',
 'Tại hàm main, kết quả sai. Sử dụng tổng hai số đầu vào làm giá trị trả về.',
])
def test_level2_rejects_unprefixed_imperative_repairs(text):
    from src.task3.round14 import feedback_errors
    assert 'level2_imperative_repair' in feedback_errors(sample(2),['Lỗi logic'],text)


@pytest.mark.parametrize('direction',[
 'Đọc lại yêu cầu và kiểm tra cẩn thận từng bước của chương trình.',
 'Thêm phần xử lý thích hợp để chương trình đáp ứng đúng yêu cầu.'
])
def test_level3_long_generic_advice_lacks_source_bound_action(direction):
    from src.task3.round14 import feedback_errors
    assert 'level3_action_not_source_bound' in feedback_errors(sample(3),['Lỗi logic'],'Hàm main trả sai giá trị. Hướng sửa: '+direction)


def test_empty_taxonomy_does_not_allow_positive_error_diagnosis():
    from src.task3.round14 import feedback_errors
    assert 'empty_taxonomy_error_diagnosis' in feedback_errors(sample(2),[],'Hàm main trả sai kết quả vì không tính tổng hai số đầu vào.')
    assert 'empty_taxonomy_error_diagnosis' not in feedback_errors(sample(2),[],'Chưa xác định được lỗi cụ thể có căn cứ trong phần mã hiện có.')


def test_explicit_binary_classifier_decisions_are_not_exception_defaults():
    from src.task3.round14 import parse_assessment
    v=value(labels=[]);v.pop('feedback');v.pop('taxonomy_error')
    v['label_decisions']={g:False for g in LABEL_SPACE}
    parsed=parse_assessment(json.dumps(v),sample())
    assert parsed['taxonomy_error']==[]
    v['label_decisions']['Lỗi logic']=True;v['rationales']=value()['rationales']
    assert parse_assessment(json.dumps(v),sample())['taxonomy_error']==['Lỗi logic']
    del v['label_decisions']['Lỗi style']
    with pytest.raises(ValueError):parse_assessment(json.dumps(v),sample())


def test_level4_needs_solution_artifact_not_diagnosis_only():
    from src.task3.round14 import feedback_errors
    assert 'missing_level4_solution' in feedback_errors(sample(4),['Lỗi logic'],'Hàm main trả sai kết quả. Hãy dùng phép cộng hai số.')


def test_negative_label_rationale_does_not_invalidate_explicit_classifier_no_error_decision():
    from src.task3.round14 import parse_assessment
    v=value(labels=[]);v.pop('feedback')
    v['rationales']=[{'taxonomy_group':'Lỗi biên dịch','reason':'Không có lỗi biên dịch; compiler đã chạy qua.','source_quote':''}]
    out=parse_assessment(json.dumps(v),sample())
    assert out['taxonomy_error']==[] and out['rationales']==[]
    assert out['rejected_rationales'][0]['reason']=='group_not_predicted'
    assert out['epistemic_status']=='model_predicted_clean_unverified'


def test_nonexact_model_quote_is_rejected_support_not_a_default_label_decision():
    from src.task3.round14 import parse_assessment
    v=value();v['rationales'][0]['source_quote']='NONEXISTENT SOURCE'
    out=parse_assessment(json.dumps(v),sample(),direct=True)
    assert out['taxonomy_error']==['Lỗi logic']
    assert out['rationales'][0]['source_quote']==''
    assert out['rejected_rationales'][0]['reason']=='nonexact_source_quote'


@pytest.mark.parametrize('prefix',['Ở hàm main, ','Trong hàm main, ','Vị trí: hàm main; '])
def test_location_prefix_does_not_hide_level2_imperative(prefix):
    from src.task3.round14 import feedback_errors
    assert 'level2_imperative_repair' in feedback_errors(sample(2),['Lỗi logic'],prefix+'bổ sung phép cộng hai số đầu vào trước khi trả kết quả.')


def test_merely_naming_function_and_asking_correct_processing_is_not_specific():
    from src.task3.round14 import feedback_errors
    assert 'level3_action_not_source_bound' in feedback_errors(sample(3),['Lỗi logic'],
        'Hàm main trả sai giá trị. Hướng sửa: Sửa hàm main để tính toán đúng theo yêu cầu đề cho mọi đầu vào.')


def test_empty_taxonomy_cannot_request_a_concrete_repair_even_without_error_keyword():
    from src.task3.round14 import feedback_errors
    assert 'empty_taxonomy_repair' in feedback_errors(sample(3),[],
        'Ở hàm main, thay x thành 0 để phù hợp yêu cầu đề.')
