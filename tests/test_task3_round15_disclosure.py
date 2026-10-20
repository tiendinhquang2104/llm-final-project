"""Artificial surface-disclosure cases; no code correctness or model assessment."""

import pytest

from src.task3.round15_disclosure import audit_flags, disclosure_violations

@pytest.mark.parametrize('text', [
    'Dòng 8 thiếu câu lệnh return nên hàm không trả về kết quả.',
    'Hàm `sum_values` thiếu `return total;` ở nhánh cuối.',
    'Biểu thức "cur = cur->next;" ở dòng 9 bỏ qua phần tử đầu.',
    'main.cpp:8:3: error: expected ; before return\n 8 | return total;\n   | ^~~~~~',
])
def test_level2_allows_location_cause_identifiers_and_quoted_source(text):
    assert disclosure_violations(text, 2) == []


@pytest.mark.parametrize('text', [
    'Thay `return 0;` bằng `return total;`.',
    'Hãy thêm câu lệnh `return total;` vào cuối hàm.',
    'Thêm `return total;` vào cuối hàm.',
    'Hãy thêm `return total;` vào cuối hàm.',
    'Add a return statement at the end of the function.',
    'Replace the current expression with `x + y`.',
    'Để sửa, dùng `return total;`.',
    '```cpp\nreturn total;\n```',
    'return total;',
    'int sum(int x, int y) { return x + y; }',
])
@pytest.mark.parametrize('level', [1, 2])
def test_low_levels_block_explicit_repairs_and_solution_code(text, level):
    assert disclosure_violations(text, level)


@pytest.mark.parametrize('text', [
    'Lỗi nằm ở dòng 8.',
    'Kết quả sai vì nhánh cuối thiếu return.',
    'The answer is wrong because the last branch does not return a value.',
    'Hàm `sum_values` không trả về kết quả.',
    'Biến total chưa được khởi tạo.',
    'The error is in function compute_total.',
    'main.cpp:8:3: error: expected ; before return',
])
def test_level1_blocks_explicit_position_cause_and_identifier_disclosure(text):
    assert disclosure_violations(text, 1)


@pytest.mark.parametrize('text', [
    'Bài làm chưa đáp ứng yêu cầu. Em hãy tiếp tục ôn luyện.',
    'Cần đọc kỹ đề và kiểm tra lại bài làm.',
    'Em đã có một khởi đầu tốt. 你好',
])
@pytest.mark.parametrize('level', [1, 2, 3, 4])
def test_general_advice_and_surface_language_or_praise_are_not_rejection_gates(text, level):
    assert disclosure_violations(text, level) == []


@pytest.mark.parametrize('text', [
    'Thêm return total vào cuối hàm.',
    'Add a return statement at the end of the function.',
    '```cpp\nint main() { return 0; }\n```',
    'Complete solution: int add(int a, int b) { return a + b; }',
    'Lỗi ở dòng 8 vì nhánh cuối thiếu return.',
    'Cần đọc kỹ đề và kiểm tra lại bài làm. Tốt lắm! 你好',
])
@pytest.mark.parametrize('level', [3, 4])
def test_high_levels_never_reject_based_on_content(text, level):
    assert disclosure_violations(text, level) == []


def test_level3_full_solution_and_generic_advice_have_only_audit_cues():
    flags = audit_flags('Complete solution: int main() { return 0; }', 3)
    assert 'complete_solution_cue' in flags
    assert 'generic_advice_cue' in audit_flags('Cần đọc kỹ đề và kiểm tra lại bài làm.', 3)


@pytest.mark.parametrize('level', [1, 2, 3, 4])
def test_cjk_and_praise_are_audit_cues_only(level):
    text = 'Tốt lắm! 你好'
    assert disclosure_violations(text, level) == []
    assert set(audit_flags(text, level)) == {'contains_cjk', 'praise_cue'}


@pytest.mark.parametrize('level', [0, 5, True, '2'])
def test_invalid_levels_are_rejected_as_api_arguments(level):
    with pytest.raises(ValueError):
        disclosure_violations('Bài làm chưa đạt.', level)
