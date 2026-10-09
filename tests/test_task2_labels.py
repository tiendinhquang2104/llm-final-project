import json
import unittest

from src.task2.labels import DESCRIPTIONS, LABELS, from_vector, normalize_label, normalize_labels, to_vector
from tests._data import ROOT


class TestLabels(unittest.TestCase):
    def test_order_matches_label_space(self):
        path = ROOT / "data" / "raw" / "public_test_release" / "label_space.json"
        if path.exists():
            self.assertEqual(list(LABELS), json.loads(path.read_text(encoding="utf-8"))["taxonomy_error"])
        self.assertEqual(len(LABELS), 10)
        self.assertEqual(set(DESCRIPTIONS), set(LABELS))

    def test_normalize(self):
        self.assertEqual(normalize_label("  lỗi   LOGIC "), "Lỗi logic")
        self.assertIsNone(normalize_label("Lỗi lạ"))
        self.assertIsNone(normalize_label(3))
        self.assertEqual(normalize_labels(["Lỗi style", "lỗi biên dịch", "Lỗi style", "x"]),
                         ["Lỗi biên dịch", "Lỗi style"])
        self.assertEqual(normalize_labels("Lỗi logic"), [])
        self.assertEqual(normalize_labels(None), [])

    def test_vector_roundtrip(self):
        v = to_vector(["Lỗi hàm", "Lỗi biên dịch"])
        self.assertEqual(len(v), 10)
        self.assertEqual(v[0], 1)
        self.assertEqual(from_vector(v), ["Lỗi biên dịch", "Lỗi hàm"])
