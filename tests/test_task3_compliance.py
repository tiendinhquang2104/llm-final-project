import pytest

from src.task3.compliance import check, fallback


@pytest.mark.parametrize(
    "level,text,ok",
    [
        (1, "Em kiểm tra lại bài làm nhé.", True),
        (1, "P2 sai vì vòng lặp bỏ phần tử cuối.", False),
        (1, "Vong lap sai do bo qua phan tu cuoi.", False),
        (1, "Em xem dòng 9.", False),
        (1, "```cpp\nreturn 4;\n```", False),
        (1, "Đáp án là 42.", False),
        (1, "Em xem lại nhé: `return 42;`.", False),
        (2, "Lỗi ở `cur = cur->next` gây mất liên kết.", True),
        (2, "Hàm abs(năm mất - năm sinh) chưa đúng.", True),
        (2, "Can thay dieu kien i < n thanh i <= n.", False),
        (2, "Dieu kien vong lap khong dung.", True),
        (2, "Thay `i < n` thành `i <= n` là cách khắc phục.", False),
        (2, "P3 lặp vô tận vì con trỏ không dịch chuyển.", True),
        (2, "Bạn thay bằng vòng lặp for.", False),
        (2, "Em cần cập nhật biến điều khiển.", False),
        (2, "Ban can dieu chinh bien dem de duyet du cac phan tu.", False),
        (2, "Hãy thay điều kiện i < n thành i <= n.", False),
        (2, "Compiler báo lỗi ở `cur->next`; con trỏ đang không hợp lệ.", True),
        (2, "Em cần dùng `return 0;` để kết thúc hàm.", False),
        (2, "return head;", False),
        (2, "```cpp\nint main(){}\n```", False),
        (3, "Em cần cập nhật con trỏ sang nút kế tiếp.", True),
        (3, "int main(){return 0;}", False),
        (4, "```cpp\nint main(){return 0;}\n```", True),
    ],
)
def test_disclosure_regressions(level, text, ok):
    assert check(text, level).ok is ok


def test_compiler_diagnostics_allowed_level2():
    text = "Lỗi biên dịch:\nTEST.cpp:5:10: error: not declared\n  5 | return x;\n    |        ^\n"
    assert check(text, 2).ok


@pytest.mark.parametrize("level", range(1, 5))
def test_fallback_and_empty(level):
    assert check(fallback(level), level).ok
    assert "empty_feedback" in check("", level).violations


def test_optional_local_structured_check_flags_irrelevant():
    result = check("TEST unrelated", 3, semantic_check=lambda text, lvl: ["irrelevant_feedback"])
    assert not result.ok
    assert "independent semantic assessment not measured" in result.semantic_status
    assert result.semantic_compliance == "not_measured"
    assert "irrelevant_feedback" in result.violations


def test_level1_rejects_compiler_diagnostic_location():
    text = "TEST.cpp:5:10: error: undeclared name\n  5 | return x;\n    |        ^\n"
    assert not check(text, 1).ok
    assert check(text, 2).ok


def test_level1_trailing_newline_is_not_a_diagnosis():
    assert check("Em kiểm tra lại bài nhé.\n", 1).ok


def test_fallback_does_not_claim_diagnosis_and_semantics_are_unmeasured():
    for level in range(1, 5):
        result = check(fallback(level), level)
        assert result.heuristic_compliance
        assert result.semantic_compliance == "not_measured"


@pytest.mark.parametrize(
    "text",
    [
        "Hôm nay có dự báo thời tiết.",
        "Hom nay xem bong da.",
        "Try this cooking recipe.",
    ],
)
def test_irrelevant_topic_guard_accents_and_unaccented(text):
    assert "irrelevant_feedback" in check(text, 3).violations
