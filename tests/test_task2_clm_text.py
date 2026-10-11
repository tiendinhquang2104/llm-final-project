import unittest
from types import SimpleNamespace

from src.task2.clm.text import CUT, build_state_texts, candidate_texts, label_question, middle_truncate
from src.task2.labels import LABELS
from tests._task2 import EXAMS, CharTokenizer

TOK = CharTokenizer()
EXAM = {**EXAMS["exams"][0], "statement": "Đề " * 400}


class TestText(unittest.TestCase):
    def test_middle_truncate_budget(self):
        s = "a" * 50 + "b" * 50
        out = middle_truncate(s, 40, TOK)
        self.assertLessEqual(len(out), 40)
        self.assertTrue(out.startswith("a") and out.endswith("b") and CUT in out)
        self.assertEqual(middle_truncate("short", 40, TOK), "short")

    def test_state_texts_fit_and_end_with_question(self):
        sample = SimpleNamespace(code="int x;\n" * 1000, exam_id="EXA")
        st = build_state_texts(EXAM, sample, TOK, max_tokens=600, max_statement_tokens=100)
        self.assertLessEqual(len(st["context"]), 600)
        self.assertEqual(list(st["questions"]), list(LABELS))
        for lab, text in st["questions"].items():
            self.assertLessEqual(len(text), 600)
            self.assertTrue(text.endswith(label_question(lab)))
            self.assertIn("int x;", text)
        self.assertNotIn("feedback", st["context"].lower())

    def test_compile_log_block(self):
        log = "/tmp/tmpab/student.cpp:3:1: error: x"
        sample = SimpleNamespace(code="int x;\n" * 1000, exam_id="EXA", compile_log=log)
        st = build_state_texts(EXAM, sample, TOK, max_tokens=600, max_statement_tokens=100, use_compile_log=True)
        for text in [st["context"], *st["questions"].values()]:
            self.assertLessEqual(len(text), 600)
            self.assertIn("Kết quả biên dịch", text)
            self.assertIn("student.cpp:3:1: error: x", text)
            self.assertNotIn("/tmp/tmpab/", text)
            self.assertLess(text.index("Kết quả biên dịch"), text.index("int x;"))
        long = SimpleNamespace(code="int x;\n", exam_id="EXA", compile_log="e" * 5000)
        st = build_state_texts(EXAM, long, TOK, max_tokens=900, max_statement_tokens=100, use_compile_log=True,
                               max_compile_tokens=50)
        self.assertLessEqual(len(st["context"]), 900)
        self.assertLess(st["context"].count("e"), 200)

    def test_compile_log_empty_none_and_off(self):
        clean = SimpleNamespace(code="int x;", exam_id="EXA", compile_log="")
        st = build_state_texts(EXAM, clean, TOK, max_tokens=600, max_statement_tokens=100, use_compile_log=True)
        self.assertIn("không có lỗi hay cảnh báo", st["context"])
        off = build_state_texts(EXAM, clean, TOK, max_tokens=600, max_statement_tokens=100)
        self.assertNotIn("Kết quả biên dịch", off["context"])
        none = SimpleNamespace(code="int x;", exam_id="EXA", compile_log=None)  # no compiler: no block
        st = build_state_texts(EXAM, none, TOK, max_tokens=600, max_statement_tokens=100, use_compile_log=True)
        self.assertNotIn("Kết quả biên dịch", st["context"])

    def test_candidates(self):
        f, t = candidate_texts("Lỗi logic")
        self.assertTrue(f.startswith("false: No.") and t.startswith("true: Yes."))
        self.assertIn("Lỗi logic", t)


if __name__ == "__main__":
    unittest.main()
