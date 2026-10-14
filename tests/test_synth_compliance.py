import json
import unittest

from src.synth.compliance import check, level_of
from tests import _data

_data.require_data()


def _real_feedbacks():
    payload = json.loads((_data.DATA / "task3_feedback.json").read_text(encoding="utf-8"))
    for s in payload["samples"]:
        yield s["sample_id"], s["input"]["target_feedback_level"], s["output"]["feedback"]


class TestLevelOf(unittest.TestCase):
    def test_parses_all_forms(self):
        self.assertEqual(level_of("Level 1 - Gợi ý nhẹ"), 1)
        self.assertEqual(level_of("Level 4 - Lời giải mẫu"), 4)
        self.assertEqual(level_of(3), 3)
        with self.assertRaises(ValueError):
            level_of("nope")


class TestRealFeedbackGate(unittest.TestCase):
    def test_no_real_instructor_feedback_is_flagged(self):
        bad = []
        for sid, level, feedback in _real_feedbacks():
            res = check(feedback, level)
            if not res.ok:
                bad.append((sid, res.violations))
        self.assertEqual(bad, [], f"checker flagged real instructor feedback: {bad}")


class TestSyntheticViolations(unittest.TestCase):
    def test_level1_rejects_code(self):
        self.assertTrue(check("Em xem lại chỗ này nhé.", 1).ok)
        self.assertFalse(check("Em sửa thành `for (int i = 0; i < n; i++)` nhé.", 1))
        self.assertFalse(check("Em xem dòng 9.", 1))
        self.assertFalse(check("Em xem hàm isArm.", 1))

    def test_level2_rejects_blocks_and_imperatives(self):
        self.assertTrue(check("P3 lặp vô tận vì con trỏ không dịch chuyển.", 2).ok)
        self.assertFalse(check("Em thêm dòng `cur = cur->next;` vào cuối.", 2))
        self.assertFalse(check("Bạn thay bằng vòng lặp for.", 2))

    def test_level2_allows_inline_identifiers(self):
        self.assertTrue(check("P3 lặp vô tận vì thiếu cur = cur->next.", 2).ok)
        self.assertTrue(check("Hàm abs(năm mất - năm sinh) chưa đúng.", 2).ok)

    def test_level3_allows_direction_blocks_solution(self):
        self.assertTrue(check("Em cần cập nhật con trỏ sang node kế tiếp.", 3).ok)
        self.assertFalse(check("```cpp\ncur = cur->next;\nreturn head;\n```", 3))

    def test_level3_allows_single_line_code(self):
        self.assertTrue(check("Em thêm `cur = cur->next;` là được.", 3).ok)

    def test_level4_unrestricted(self):
        self.assertTrue(check("```cpp\nint main(){ return 0; }\n```", 4).ok)

    def test_compile_log_block_is_stripped(self):
        log = ("student.cpp:5:10: error: 'x' was not declared\n"
               "   5 |     return x;\n"
               "     |            ^\n")
        self.assertTrue(check(f"Lỗi biên dịch:\n{log}", 2).ok)


if __name__ == "__main__":
    unittest.main()
