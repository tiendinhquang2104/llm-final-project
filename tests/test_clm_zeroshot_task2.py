import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from src.clm_zeroshot import guides
from src.clm_zeroshot.scoring import choice_probs, noul_candidates, noul_prob, question_states
from src.clm_zeroshot.task2 import decide, label_probs, prevalence_thresholds, run_task2_zeroshot
from src.task2.clm.encoder import CachedEncoder
from src.task2.clm.heads import NoulModel
from src.task2.data import load_task2
from src.task2.evaluator import validate_predictions
from src.task2.labels import LABELS
from tests._task2 import CharTokenizer, FakeEncoder, make_dataset, make_fake_heads

CFG = {"name": "task2_clm_test", "seed": 42, "data": {"public_per_exam": None},
       "text": {"max_tokens": 1200, "max_statement_tokens": 64}}
GOLD = [("G1", "EXA", ["Lỗi logic"]), ("G2", "EXA", []), ("G3", "EXB", ["Lỗi hàm", "Lỗi logic"]),
        ("G4", "EXB", ["Lỗi biên dịch"]), ("G5", "EXA", ["Lỗi logic"]), ("G6", "EXB", [])]


class TestScoring(unittest.TestCase):
    def test_candidates_follow_clm_format(self):
        f, t = noul_candidates("Q?")
        self.assertEqual(f, "false: No. This is false: Q?")
        self.assertEqual(t, "true: Yes. This is true: Q?")

    def test_choice_probs_rows_sum_to_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            heads = NoulModel.from_checkpoint(make_fake_heads(Path(tmp) / "h.pt"))
            rng = np.random.default_rng(0)
            S, C = rng.standard_normal((5, 16)), rng.standard_normal((3, 16))
            P = choice_probs(heads, S, C)
            self.assertEqual(P.shape, (5, 3))
            np.testing.assert_allclose(P.sum(1), 1.0, atol=1e-5)
            pt = noul_prob(heads, S, C[:2])
            np.testing.assert_allclose(pt, choice_probs(heads, S, C[:2])[:, 1])

    def test_context_cut_keeps_longest_question(self):
        tok = CharTokenizer()
        gold = load_task2(make_dataset(Path(tempfile.mkdtemp()) / "g", GOLD, code={"G1": "x = 1;\n" * 400}))
        s = next(x for x in gold.samples if x.sample_id == "G1")
        qs = ["short?", "a much longer question " * 5]
        out = question_states(gold.exams["EXA"], s, tok, qs, {"max_tokens": 600, "max_statement_tokens": 64})
        self.assertEqual(len(out), 2)
        for text, q in zip(out, qs):
            self.assertTrue(text.endswith("\n\n" + q))
            self.assertLessEqual(len(tok.encode(text)), 600)
        self.assertEqual(out[0].rsplit("\n\n", 1)[0], out[1].rsplit("\n\n", 1)[0])


class TestThresholds(unittest.TestCase):
    def test_predicted_rate_matches_prevalence(self):
        rng = np.random.default_rng(1)
        P = rng.random((100, 10))
        Y = np.zeros((100, 10), bool)
        Y[:20, 0] = True
        Y[:50, 1] = True
        thr = prevalence_thresholds(P, Y, floor=0.05)
        pred = P >= thr
        self.assertAlmostEqual(pred[:, 0].mean(), 0.20, delta=0.02)
        self.assertAlmostEqual(pred[:, 1].mean(), 0.50, delta=0.02)

    def test_zero_frequency_uses_floor(self):
        P = np.random.default_rng(2).random((100, 10))
        thr = prevalence_thresholds(P, np.zeros((100, 10), bool), floor=0.1)
        self.assertAlmostEqual((P[:, 3] >= thr[3]).mean(), 0.10, delta=0.02)

    def test_decide_overrides_compile_label(self):
        j = LABELS.index("Lỗi biên dịch")
        P = np.ones((3, 10))
        err = np.array([True, False, True])
        out = decide(P, np.full(10, 0.5), err)
        self.assertEqual(out[:, j].tolist(), err.tolist())
        self.assertTrue(out[:, j - 1].all())


class TestRun(unittest.TestCase):
    def test_label_probs_shape_and_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gold = load_task2(make_dataset(tmp / "g", GOLD))
            heads = make_fake_heads(tmp / "h.pt")
            P = label_probs(gold.samples, gold.exams, FakeEncoder(), heads, CFG["text"])
            self.assertEqual(P.shape, (6, 10))
            self.assertTrue(((P >= 0) & (P <= 1)).all())

    def test_end_to_end_no_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gold = load_task2(make_dataset(tmp / "g", GOLD))
            public = load_task2(make_dataset(tmp / "p", [("P1", "EXA", None), ("P2", "EXB", None)]))
            heads = make_fake_heads(tmp / "h.pt")
            before = {k: v.clone() for k, v in NoulModel.from_checkpoint(heads).state_dict().items()}
            with mock.patch("src.task2.clm.heads.train_noul", side_effect=AssertionError("trained")), \
                    mock.patch("src.task2.clm.experiment.train_noul", side_effect=AssertionError("trained")):
                m = run_task2_zeroshot(CFG, CachedEncoder(FakeEncoder(dim=16), tmp / "c"), heads, gold, public,
                                       tmp / "out", registry=None)
            self.assertEqual(m["mode"], "clm_zeroshot")
            self.assertAlmostEqual(m["floor"], 1 / 6)
            after = NoulModel.from_checkpoint(heads).state_dict()
            self.assertTrue(all(bool((before[k] == after[k]).all()) for k in before))
            self.assertIn("clm_zeroshot_prompts", m["systems"])
            self.assertEqual(set(m["thresholds"]), set(LABELS))
            sub = json.loads((tmp / "out" / "predictions.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_predictions(sub, ["P1", "P2"]), [])
            for f in ("predictions_full.json", "metrics.json", "resources.json", "config.json"):
                self.assertTrue((tmp / "out" / f).exists(), f)
            self.assertTrue(all(q.startswith("Bài nộp trên") for q in guides.LABEL_QUESTIONS.values()))


if __name__ == "__main__":
    unittest.main()
