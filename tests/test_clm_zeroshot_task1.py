import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from src.clm_zeroshot.guides import RUBRIC_QUESTIONS
from src.clm_zeroshot.task1 import assemble, dimension_scores, problem_status, run_task1_zeroshot
from src.data.loader import DIM_MAX, DIMENSIONS
from src.task1.clm_probe import load_rubrics
from src.task1.evaluator import validate_predictions
from src.task2.clm.encoder import CachedEncoder
from src.task2.clm.heads import NoulModel
from src.task2.data import load_task2
from tests._task2 import EXAMS, FakeEncoder, make_dataset, make_fake_heads

CFG = {"name": "task1_zeroshot_test", "text": {"max_tokens": 1200, "max_statement_tokens": 64}}
GOLD = [(f"G{i}", "EXA" if i % 2 else "EXB", []) for i in range(6)]
EXB = EXAMS["exams"][1]
EXA = EXAMS["exams"][0]


def _rub(i):
    return {"compilable": i % 2, "io_format": i % 2, "logic": i % 5, "edge_case": i % 3, "complexity": 1,
            "code_quality": 0}


def _write_t1(root, rows):
    samples = []
    for sid, eid, rub in rows:
        s = {"sample_id": sid, "input": {"exam_id": eid}}
        if rub:
            s["output"] = {"rubric": rub, "total_score": sum(rub.values())}
        samples.append(s)
    (root / "task1_grading.json").write_text(json.dumps({"samples": samples}), encoding="utf-8")


class TestPieces(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.gold = load_task2(make_dataset(self.tmp / "g", GOLD))
        self.heads = NoulModel.from_checkpoint(make_fake_heads(self.tmp / "h.pt"))

    def test_expectations_in_range(self):
        sc = dimension_scores(self.gold.samples, self.gold.exams, FakeEncoder(), self.heads, CFG["text"])
        self.assertEqual(set(sc), set(RUBRIC_QUESTIONS))
        for d, v in sc.items():
            self.assertEqual(v.shape, (6,))
            self.assertTrue(((v >= 0) & (v <= DIM_MAX[d])).all(), d)

    def test_status_only_for_multi_problem(self):
        st = problem_status(self.gold.samples, self.gold.exams, FakeEncoder(), self.heads, CFG["text"])
        for s, d in zip(self.gold.samples, st):
            if s.exam_id == "EXA":
                self.assertEqual(d, {})
            else:
                self.assertEqual(set(d), {"P1", "P2"})
                self.assertTrue(set(d.values()) <= {"correct", "wrong"})

    def test_assemble_compile_error(self):
        row = {"io_format": 1.2, "logic": 3.6, "edge_case": 1.4, "complexity": 0.9, "code_quality": 0.7}
        r, t, trace = assemble(row, True, {}, EXA)
        self.assertEqual(r["compilable"], 0)
        self.assertEqual((r["io_format"], r["logic"], r["edge_case"], r["complexity"]), (0, 0, 0, 0))
        self.assertTrue(any(x.startswith("compile_zero") for x in trace))
        r, t, _ = assemble(row, False, {}, EXA)
        self.assertEqual(r, {"compilable": 1, "io_format": 1, "logic": 4, "edge_case": 1, "complexity": 1,
                             "code_quality": 1})
        self.assertEqual(t, 9)
        self.assertTrue(all(type(v) is int for v in r.values()))

    def test_prereq_wrong_zeroes_dependents(self):
        row = {"io_format": 1, "logic": 3, "edge_case": 2, "complexity": 1, "code_quality": 1}
        r, t, trace = assemble(row, False, {"P1": "wrong", "P2": "correct"}, EXB)
        self.assertEqual((r["compilable"], r["io_format"]), (1, 1))
        self.assertEqual((r["logic"], r["edge_case"], r["complexity"], r["code_quality"]), (0, 0, 0, 0))
        self.assertEqual(t, 2)
        self.assertTrue(any(x.startswith("prereq_zero") for x in trace))
        r, t, _ = assemble(row, False, {"P1": "correct", "P2": "wrong"}, EXB)
        self.assertEqual(t, 9)


class TestRun(unittest.TestCase):
    def test_end_to_end_no_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            g = make_dataset(tmp / "g", GOLD)
            _write_t1(g, [(sid, e, _rub(i)) for i, (sid, e, _) in enumerate(GOLD)])
            gold = load_task2(g)
            rubrics = load_rubrics(g)
            public = load_task2(make_dataset(tmp / "p", [("P1", "EXA", None), ("P2", "EXB", None),
                                                         ("P3", "EXB", None)]))
            ids = ["P2", "P1", "P3"]
            heads = make_fake_heads(tmp / "h.pt")
            before = {k: v.clone() for k, v in NoulModel.from_checkpoint(heads).state_dict().items()}
            boom = AssertionError("trained")
            with mock.patch("src.task2.clm.heads.train_noul", side_effect=boom), \
                    mock.patch("src.task2.clm.experiment.train_noul", side_effect=boom), \
                    mock.patch("sklearn.linear_model.Ridge.fit", side_effect=boom):
                m = run_task1_zeroshot(CFG, CachedEncoder(FakeEncoder(dim=16), tmp / "c"), heads, gold, rubrics,
                                       public, ids, tmp / "out", registry=None)
            after = NoulModel.from_checkpoint(heads).state_dict()
            self.assertTrue(all(bool((before[k] == after[k]).all()) for k in before))
            self.assertEqual(m["mode"], "clm_zeroshot")
            self.assertIn("optimistic", m["evaluation"])
            self.assertEqual(m["systems"]["clm_zeroshot_prompts"]["n"], 6)
            preds = json.loads((tmp / "out" / "predictions.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_predictions(preds, set(ids)), [])
            self.assertEqual([p["sample_id"] for p in preds], ids)
            for p in preds:
                self.assertTrue(all(type(v) is int for v in p["output"]["rubric"].values()))
            full = json.loads((tmp / "out" / "predictions_full.json").read_text(encoding="utf-8"))
            self.assertEqual(set(full[0]), {"sample_id", "exam_id", "has_compile_error", "expected", "statuses",
                                            "rule_trace", "rubric", "total_score"})
            for f in ("metrics.json", "resources.json", "config.json"):
                self.assertTrue((tmp / "out" / f).exists(), f)


if __name__ == "__main__":
    unittest.main()
