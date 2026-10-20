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
    assert not feedback_errors(sample(3),['Lỗi logic'],'Vị trí: hàm main. Giá trị trả về khác yêu cầu. Hướng sửa: Thay giá trị trả về x bằng giá trị tính từ đầu vào theo yêu cầu đề.')


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
