"""Unit tests for Task 3 Pedagogical Guard, Prompts, and Compliance Metrics."""

from __future__ import annotations

import unittest

from src.evaluation.metrics import evaluate_task3_compliance
from src.task3.pedagogical_guard import (
    audit_feedback,
    detect_code_leakage,
    detect_location_leakage,
    sanitize_feedback,
)
from src.task3.prompts import build_task3_messages, build_user_prompt, format_numbered_code


class TestTask3Guard(unittest.TestCase):
    def test_detect_code_leakage(self):
        clean_text = "Em cần kiểm tra lại điều kiện dừng của vòng lặp để tránh tràn số."
        self.assertEqual(len(detect_code_leakage(clean_text)), 0)

        code_block = "Lỗi ở đây:\n```cpp\nfor(int i = 0; i < n; i++) {}\n```"
        self.assertGreater(len(detect_code_leakage(code_block)), 0)

        cpp_stmt = "Em nên viết return 0; ở cuối hàm main."
        self.assertGreater(len(detect_code_leakage(cpp_stmt)), 0)

    def test_detect_location_leakage(self):
        clean_text = "Bài làm có lỗi logic trong thuật toán tính tổng."
        self.assertEqual(len(detect_location_leakage(clean_text)), 0)

        location_violation = "Lỗi xảy ra ở dòng 15 khi gán biến."
        self.assertGreater(len(detect_location_leakage(location_violation)), 0)

        location_violation_en = "Bug at line 42 in loop."
        self.assertGreater(len(detect_location_leakage(location_violation_en)), 0)

    def test_audit_level1_compliance(self):
        # Compliant Level 1: General feedback, no location, no code
        ok_text = "Bài làm của em còn một số sai sót về mặt thuật toán, hãy đọc kỹ lại ràng buộc đề bài."
        rep = audit_feedback(ok_text, "Level 1 - Gợi ý nhẹ", ["Lỗi logic"])
        self.assertTrue(rep.is_compliant)
        self.assertEqual(len(rep.violations), 0)

        # Non-compliant Level 1: Mentions line number
        bad_loc = "Em xem lại dòng 25 xem bị sai cái gì."
        rep_loc = audit_feedback(bad_loc, "Level 1 - Gợi ý nhẹ", ["Lỗi logic"])
        self.assertFalse(rep_loc.is_compliant)

        # Non-compliant Level 1: Mentions code
        bad_code = "Em sửa thành: ```cpp\nint ans = 0;\n```"
        rep_code = audit_feedback(bad_code, "Level 1 - Gợi ý nhẹ", ["Lỗi logic"])
        self.assertFalse(rep_code.is_compliant)

    def test_audit_level2_compliance(self):
        # Compliant Level 2: Mentions location and root cause, but NO code
        ok_text = "P1 đúng; P2 sai ở dòng 45 do truy cập chỉ số âm trong mảng; P3 chưa làm."
        rep = audit_feedback(ok_text, "Level 2 - Chẩn đoán", ["Lỗi mảng/chuỗi"])
        self.assertTrue(rep.is_compliant)

        # Non-compliant Level 2: Includes C++ fix code
        bad_text = "Dòng 45 sai, hãy sửa thành ```cpp\nif (i >= 0) a[i] = 1;\n```"
        rep = audit_feedback(bad_text, "Level 2 - Chẩn đoán", ["Lỗi mảng/chuỗi"])
        self.assertFalse(rep.is_compliant)

    def test_audit_level4_compliance(self):
        # Level 4 allows code and full solutions
        code_text = "Em sửa lại toàn bộ như sau:\n```cpp\nint main() {\n    return 0;\n}\n```"
        rep = audit_feedback(code_text, "Level 4 - Lời giải mẫu", ["Lỗi logic"])
        self.assertTrue(rep.is_compliant)

    def test_audit_zero_error_empty_feedback(self):
        # When no errors, feedback MUST be empty string
        rep_ok = audit_feedback("", "Level 2 - Chẩn đoán", [])
        self.assertTrue(rep_ok.is_compliant)

        rep_bad = audit_feedback("Bài làm tốt lắm!", "Level 2 - Chẩn đoán", [])
        self.assertFalse(rep_bad.is_compliant)
        self.assertEqual(rep_bad.sanitized_feedback, "")

    def test_sanitize_strips_code_in_level1_and_2(self):
        raw = "Lỗi ở dòng 10. Em sửa lại như sau:\n```cpp\ncout << res;\n```\nChúc em học tốt."
        sanitized = sanitize_feedback(raw, "Level 2 - Chẩn đoán", ["Lỗi nhập/xuất"])
        self.assertNotIn("```", sanitized)
        self.assertNotIn("cout <<", sanitized)
        rep = audit_feedback(sanitized, "Level 2 - Chẩn đoán", ["Lỗi nhập/xuất"])
        self.assertTrue(rep.is_compliant)

    def test_sanitize_zero_error(self):
        sanitized = sanitize_feedback("Khen ngợi sinh viên", "Level 1", [])
        self.assertEqual(sanitized, "")

    def test_format_numbered_code(self):
        code = "int main() {\n    return 0;\n}"
        formatted = format_numbered_code(code)
        self.assertIn("1 | int main()", formatted)
        self.assertIn("2 |     return 0;", formatted)

    def test_build_task3_messages(self):
        msgs = build_task3_messages(
            exam_id="EX01",
            exam_type="multi_problem",
            exam_statement="Tính tổng số nguyên",
            code="int main() { return 0; }",
            target_level="Level 2 - Chẩn đoán",
            taxonomy_error=["Lỗi logic"],
        )
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "system")
        self.assertIn("QUY TẮC CỐT LÕI", msgs[0]["content"])
        self.assertEqual(msgs[1]["role"], "user")
        self.assertIn("EX01", msgs[1]["content"])
        self.assertIn("Level 2 - Chẩn đoán", msgs[1]["content"])

    def test_evaluate_task3_compliance(self):
        records = [
            {"feedback": "P1 đúng; P2 sai logic ở dòng 10.", "target_feedback_level": "Level 2", "taxonomy_error": ["Lỗi logic"]},
            {"feedback": "", "target_feedback_level": "Level 1", "taxonomy_error": []},
            {"feedback": "Xem code: ```cpp int a; ```", "target_feedback_level": "Level 1", "taxonomy_error": ["Lỗi logic"]},
            {"feedback": "Không có lỗi", "target_feedback_level": "Level 2", "taxonomy_error": []},
        ]
        res = evaluate_task3_compliance(records)
        self.assertEqual(res["total_samples"], 4.0)
        self.assertEqual(res["level_compliance_rate"], 0.5)
        self.assertEqual(res["empty_on_zero_error_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
