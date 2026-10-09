import tempfile
import unittest
from pathlib import Path

from src.task2.data import load_task2
from tests._task2 import make_dataset


class TestLoadTask2(unittest.TestCase):
    def test_labelled_and_unlabelled(self):
        with tempfile.TemporaryDirectory() as tmp:
            gold = load_task2(make_dataset(Path(tmp) / "g", [("A1", "EXA", ["lỗi logic", "Lỗi hàm"]),
                                                             ("B1", "EXB", [])]))
            self.assertEqual(gold.by_id()["A1"].labels, ["Lỗi logic", "Lỗi hàm"])
            self.assertEqual(gold.by_id()["B1"].labels, [])
            self.assertTrue(gold.by_id()["B1"].has_gold)
            self.assertIn("int main", gold.by_id()["A1"].code)
            self.assertIsNone(gold.by_id()["A1"].compile_log)  # "" -> None
            pub = load_task2(make_dataset(Path(tmp) / "p", [("P1", "EXA", None)]))
            self.assertFalse(pub.samples[0].has_gold)
            self.assertEqual(set(pub.exams), {"EXA", "EXB"})

    def test_unknown_label_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp), [("A1", "EXA", ["Lỗi lạ"])])
            with self.assertRaises(ValueError):
                load_task2(root)
