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

    def test_candidates(self):
        f, t = candidate_texts("Lỗi logic")
        self.assertTrue(f.startswith("false: No.") and t.startswith("true: Yes."))
        self.assertIn("Lỗi logic", t)


if __name__ == "__main__":
    unittest.main()
