import json
import math
import tempfile
import unittest
from pathlib import Path

from src.task2.evaluator import f1_scores, to_submission, validate_predictions, write_submission
from src.task2.labels import LABELS

L0, L2, L3 = LABELS[0], LABELS[2], LABELS[3]


class TestF1(unittest.TestCase):
    def test_hand_example(self):
        gold = {"a": [L0], "b": [L0, L2], "c": []}
        pred = {"a": [L0], "b": [L2, L3], "c": []}
        m = f1_scores(gold, pred)
        self.assertAlmostEqual(m["per_label"][L0]["f1"], 2 / 3)
        self.assertAlmostEqual(m["per_label"][L2]["f1"], 1.0)
        self.assertAlmostEqual(m["per_label"][L3]["f1"], 0.0)
        self.assertIsNone(m["per_label"][LABELS[9]]["f1"])
        self.assertAlmostEqual(m["macro_f1"], (2 / 3 + 1.0) / 10)
        self.assertAlmostEqual(m["macro_f1_skip_absent"], (2 / 3 + 1.0 + 0.0) / 3)
        self.assertAlmostEqual(m["micro_f1"], 4 / 6)
        self.assertAlmostEqual(m["exact_match"], 2 / 3)
        self.assertEqual(m["n"], 3)

    def test_missing_prediction_is_empty(self):
        m = f1_scores({"a": [L0]}, {})
        self.assertEqual(m["per_label"][L0]["f1"], 0.0)

    def test_all_empty(self):
        m = f1_scores({"a": []}, {"a": []})
        self.assertEqual(m["macro_f1"], 0.0)
        self.assertTrue(math.isnan(m["macro_f1_skip_absent"]))
        self.assertTrue(math.isnan(m["micro_f1"]))
        self.assertEqual(m["exact_match"], 1.0)


class TestValidate(unittest.TestCase):
    def test_valid_and_errors(self):
        ok = to_submission({"a": ["lỗi logic"], "b": []}, ["a", "b"])
        self.assertEqual(ok[0]["output"]["taxonomy_error"], ["Lỗi logic"])
        self.assertEqual(validate_predictions(ok, ["a", "b"]), [])
        bad = [{"sample_id": "a", "output": {"taxonomy_error": ["Lỗi lạ"]}},
               {"sample_id": "a", "output": {"taxonomy_error": []}},
               {"sample_id": "z", "output": {"taxonomy_error": "Lỗi logic"}},
               {"output": {}}]
        errs = "\n".join(validate_predictions(bad, ["a", "b"]))
        for needle in ("unknown label", "duplicate", "must be a list", "missing sample_id", "missing 1", "unexpected"):
            self.assertIn(needle, errs)

    def test_write_submission(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "predictions.json"
            write_submission(path, {"a": [L0]}, ["a", "b"])
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual([r["output"]["taxonomy_error"] for r in data], [[L0], []])
