import json
import tempfile
import unittest
from pathlib import Path

from src.task2.clm.encoder import CachedEncoder
from src.task2.clm.experiment import run_clm
from src.task2.data import load_task2
from src.task2.evaluator import validate_predictions
from tests._task2 import FakeEncoder, make_dataset, make_fake_heads

CFG = {"name": "task2_clm_test", "seed": 42, "data": {"public_per_exam": None},
       "text": {"max_tokens": 512, "max_statement_tokens": 64},
       "train": {"epochs": 2, "lr": 1e-3, "batch_size": 16}, "probe": {"C": 1.0},
       "thresholds": {"min_rate": 0.0, "default": 0.5}, "silver": {"holdout": 0.5},
       "final_system": "clm_noul"}


class TestRunClm(unittest.TestCase):
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gold = load_task2(make_dataset(tmp / "g", [
                ("T1", "EXA", ["Lỗi logic"]), ("T2", "EXA", []), ("T3", "EXB", ["Lỗi hàm", "Lỗi logic"]),
                ("T4", "EXB", ["Lỗi biên dịch"]), ("V1", "EXA", ["Lỗi logic"]), ("V2", "EXB", [])]))
            public = load_task2(make_dataset(tmp / "p", [("P1", "EXA", None), ("P2", "EXA", None),
                                                         ("P3", "EXB", None), ("P4", "EXB", None)]))
            split = {"train": ["T1", "T2", "T3", "T4"], "val": ["V1", "V2"]}
            silver = {"P1": {"Lỗi logic": 0.8}, "P3": {"Lỗi hàm": 1.0}}
            enc = CachedEncoder(FakeEncoder(dim=16), tmp / "cache")
            out = tmp / "out"
            m = run_clm(CFG, enc, make_fake_heads(tmp / "h.pt"), gold, public, split, out, silver, registry=None)
            for key in ("clm_zero_shot@0.5", "clm_noul@0.5", "clm_noul@tuned", "probe@0.5", "probe@tuned"):
                self.assertIn(key, m["systems"])
            self.assertEqual(m["n_val_gold"], 2)
            self.assertEqual(m["n_train"], 5)  # 4 gold + 1 silver (holdout 0.5 of 2)
            sub = json.loads((out / "predictions.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_predictions(sub, ["P1", "P2", "P3", "P4"]), [])
            res = json.loads((out / "resources.json").read_text(encoding="utf-8"))
            self.assertEqual(res["n_samples"], 10)
            self.assertTrue((out / "clm_noul_heads.pt").exists())

    def test_missing_checkpoint_fails_before_embedding(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gold = load_task2(make_dataset(tmp / "g", [("T1", "EXA", ["Lỗi logic"]), ("V1", "EXB", [])]))
            fake = FakeEncoder()
            with self.assertRaises(Exception):
                run_clm(CFG, CachedEncoder(fake, tmp / "c"), tmp / "missing.pt", gold, None,
                        {"train": ["T1"], "val": ["V1"]}, tmp / "o", None, registry=None)
            self.assertEqual(fake.calls, 0)

    def test_early_stopping_uses_silver_holdout_when_gold_val_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gold = load_task2(make_dataset(tmp / "g", [("T1", "EXA", ["Lỗi logic"]), ("T2", "EXB", [])]))
            public = load_task2(make_dataset(tmp / "p", [("P1", "EXA", None), ("P2", "EXA", None),
                                                         ("P3", "EXB", None), ("P4", "EXB", None)]))
            silver = {"P1": {"Lỗi logic": 1.0}, "P2": {}, "P3": {"Lỗi hàm": 1.0}, "P4": {"Lỗi logic": 0.9}}
            m = run_clm(CFG, CachedEncoder(FakeEncoder(), tmp / "c"), make_fake_heads(tmp / "h.pt"), gold, public,
                        {"train": ["T1", "T2"], "val": []}, tmp / "o", silver, registry=None)
            self.assertEqual(m["n_val_gold"], 0)
            self.assertEqual(len(m["history"]["eval"]), CFG["train"]["epochs"])
            self.assertIsNotNone(m["history"]["best_epoch"])
            self.assertEqual(m["systems"], {})  # reported metrics stay gold-val only

    def test_public_per_exam_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gold = load_task2(make_dataset(tmp / "g", [("T1", "EXA", ["Lỗi logic"]), ("T2", "EXB", [])]))
            public = load_task2(make_dataset(tmp / "p", [("P1", "EXA", None), ("P2", "EXA", None),
                                                         ("P3", "EXB", None)]))
            cfg = {**CFG, "data": {"public_per_exam": 1}}
            run_clm(cfg, CachedEncoder(FakeEncoder(), tmp / "c"), make_fake_heads(tmp / "h.pt"), gold, public,
                    {"train": ["T1", "T2"], "val": []}, tmp / "o", None, registry=None)
            ids = [r["sample_id"] for r in json.loads((tmp / "o" / "predictions.json").read_text(encoding="utf-8"))]
            self.assertEqual(ids, ["P1", "P3"])
