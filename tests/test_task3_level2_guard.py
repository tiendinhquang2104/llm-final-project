"""Bounded surface screen tests; passing is never semantic certification."""
import pytest
from tests.test_task3_level2_prompt import ALLOWED,FORBIDDEN
from src.task3.round15_disclosure import _normalized

EXTRA_ALLOWED=[
    'Việc xóa phần tử nhỏ nhất khiến `rbegin()` vẫn chỉ tới giá trị lớn nhất.',
    'Hàm này dùng phép chia nguyên nên phần thập phân bị mất.',
    'Không cần thay kiểu total vì biến đã là long long.',
    'Dòng này thiếu đối số sau dấu phẩy, nên compiler không phân tích được lời gọi.',
    'Khi cur không thay đổi, vòng lặp không kết thúc.',
    'Giá trị không được khởi tạo trước lần đọc đầu, nên kết quả không xác định.',
    'Đề yêu cầu số chẵn, trong khi `x%2!=0` chọn số lẻ.',
]

@pytest.mark.parametrize('text',ALLOWED+EXTRA_ALLOWED)
@pytest.mark.parametrize('normalize',[False,True])
def test_new_screen_keeps_diagnostic_language(text,normalize):
    from src.task3.level2_guard import disclosure_violations
    assert disclosure_violations(_normalized(text) if normalize else text,2)==[]

@pytest.mark.parametrize('text',FORBIDDEN+[
    'Cần sửa đổi điều kiện if trong vòng lặp for.',
    'Cần khởi tạo total bằng 0 và cộng tất cả các số.',
    'Bạn nên sử dụng phép chia lấy dư (a % b) thay vì phép chia (a / b).',
    'Biến total nên là kiểu int hoặc long long.',
    'Dùng phần tử lớn nhất còn lại làm kết quả.',
    '```cpp\ncur = cur->next;\n```',
])
@pytest.mark.parametrize('normalize',[False,True])
def test_new_screen_blocks_explicit_change_instructions(text,normalize):
    from src.task3.level2_guard import disclosure_violations
    assert disclosure_violations(_normalized(text) if normalize else text,2)

@pytest.mark.parametrize('level',[1,3,4])
@pytest.mark.parametrize('text',ALLOWED+FORBIDDEN)
def test_other_levels_identical_to_r15(text,level):
    from src.task3.level2_guard import disclosure_violations
    from src.task3.round15_disclosure import disclosure_violations as old
    assert disclosure_violations(text,level)==old(text,level)


def test_new_guard_retries_real_generation_path_and_retains_labels(tmp_path):
    from src.task3.level2_prompt import adapter
    from src.task3.round15_runner import run_records
    from tests.test_task3_round15_runner import Scripted,response,cfg
    from tests.test_task3_round14 import sample
    backend=Scripted([response(FORBIDDEN[5]),response(ALLOWED[3])],tmp_path)
    with adapter('D',guard='new'):
        result=run_records([sample(2)],backend,cfg(),tmp_path)
    assert backend.calls==2
    assert result['predictions'][0]['output']['feedback']==ALLOWED[3]
    assert result['traces'][0]['final_origin']=='qwen_retry'


def test_new_guard_exhaustion_is_flagged_diagnostic_failure(tmp_path):
    from src.task3.level2_prompt import adapter
    from src.task3.round15_runner import run_records
    from tests.test_task3_round15_runner import Scripted,response,cfg
    from tests.test_task3_round14 import sample
    with adapter('A',guard='new'):
        result=run_records([sample(2)],Scripted([response(FORBIDDEN[3])]*3,tmp_path),cfg(),tmp_path)
    assert result['traces'][0]['fallback_used']
    assert result['traces'][0]['usefulness']=='not_established_epistemic_fallback'
    assert result['predictions'][0]['output']['taxonomy_error']==['Lỗi logic']
