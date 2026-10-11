import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from src.task2.augment import augment, source_id
from src.task2.clm.encoder import CachedEncoder
from src.task2.clm.experiment import SYSTEMS, kfold_ids, run_clm
from src.task2.data import load_task2
from src.task2.evaluator import validate_predictions
from tests._task2 import FakeEncoder, make_dataset, make_fake_heads

CFG = {"name": "task2_clm_test", "seed": 42, "data": {"public_per_exam": None},
       "text": {"max_tokens": 512, "max_statement_tokens": 64},
       "train": {"epochs": 2, "lr": 1e-3, "batch_size": 16}, "probe": {"C": 1.0},
       "thresholds": {"min_rate": 0.0, "default": 0.5}, "cv": {"folds": 3}, "final_system": "clm_noul_aug"}
GOLD = [("G1", "EXA", ["Lỗi logic"]), ("G2", "EXA", []), ("G3", "EXB", ["Lỗi hàm", "Lỗi logic"]),
        ("G4", "EXB", ["Lỗi biên dịch"]), ("G5", "EXA", ["Lỗi logic"]), ("G6", "EXB", [])]


class TestKfold(unittest.TestCase):
    def test_disjoint_cover_deterministic(self):
        ids = [f"S{i}" for i in range(10)]
        folds = kfold_ids(ids, 4, 42)
        self.assertEqual(len(folds), 4)
        self.assertEqual(sorted(sum(folds, [])), sorted(ids))
        self.assertEqual(folds, kfold_ids(list(reversed(ids)), 4, 42))
        self.assertEqual(len(kfold_ids(ids[:2], 4, 42)), 2)


class TestRunClm(unittest.TestCase):
    def test_end_to_end_cv_with_mutants(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gold = load_task2(make_dataset(tmp / "g", GOLD))
            public = load_task2(make_dataset(tmp / "p", [("P1", "EXA", None), ("P2", "EXB", None)]))
            mutants = augment(gold.samples)
            self.assertGreater(len(mutants), 0)
            leaked = replace(mutants[0], sample_id="P1~strip_indentation")  # not from a gold source
            m = run_clm(CFG, CachedEncoder(FakeEncoder(dim=16), tmp / "c"), make_fake_heads(tmp / "h.pt"), gold,
                        public, tmp / "out", [*mutants, leaked], registry=None)
            for system in SYSTEMS:
                for suffix in ("@0.5", "@tuned"):
                    self.assertEqual(m["systems"][system + suffix]["n"], 6)
            self.assertEqual(m["n_gold"], 6)
            self.assertEqual(m["n_mutants"], len(mutants))  # the non-gold-source mutant was dropped
            self.assertEqual(m["cv_folds"], 3)
            self.assertEqual(len(m["history"]["folds"]), 3 * 2)  # (no-aug, aug) per fold
            sub = json.loads((tmp / "out" / "predictions.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_predictions(sub, ["P1", "P2"]), [])
            res = json.loads((tmp / "out" / "resources.json").read_text(encoding="utf-8"))
            self.assertEqual(res["n_samples"], 6 + len(mutants) + 2)
            for f in ("clm_noul_heads.pt", "clm_noul_aug_heads.pt", "thresholds.json", "metrics.json"):
                self.assertTrue((tmp / "out" / f).exists(), f)

    def test_augmented_fold_train_size_has_no_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gold = load_task2(make_dataset(tmp / "g", GOLD))
            mutants = augment(gold.samples)
            m = run_clm(CFG, CachedEncoder(FakeEncoder(dim=16), tmp / "c"), make_fake_heads(tmp / "h.pt"), gold,
                        None, tmp / "out", mutants, registry=None)
            conf = json.loads((tmp / "out" / "config.json").read_text(encoding="utf-8"))
            all_ids = sorted(s for fold in conf["folds"] for s in fold)
            self.assertEqual(len(m["history"]["folds"]), 3 * 2)
            for entry in m["history"]["folds"]:
                train = set(all_ids) - set(conf["folds"][entry["fold"]])
                n_mut = sum(source_id(i) in train for i in conf["mutant_ids"])
                self.assertEqual(entry["n_train"], len(train) + (n_mut if entry["augment"] else 0), entry)
                if entry["augment"]:
                    self.assertGreater(n_mut, 0)

    def test_lr_grid_selects_on_oof_and_records_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gold = load_task2(make_dataset(tmp / "g", GOLD))
            mutants = augment(gold.samples)
            grid = [1e-4, 1e-2]
            cfg = {**CFG, "train": {**CFG["train"], "lr_grid": grid}}
            m = run_clm(cfg, CachedEncoder(FakeEncoder(dim=16), tmp / "c"), make_fake_heads(tmp / "h.pt"), gold,
                        None, tmp / "out", mutants, registry=None)
            self.assertEqual(set(m["lr_selection"]), {"clm_noul", "clm_noul_aug"})
            for sel in m["lr_selection"].values():
                self.assertEqual(sel["grid"], grid)
                self.assertIn(sel["chosen"], grid)
                self.assertEqual(len(sel["oof_macro_f1_tuned"]), 2)
                best = max(sel["oof_macro_f1_tuned"].values())
                self.assertEqual(sel["oof_macro_f1_tuned"][str(sel["chosen"])], best)
            seen = {(e["lr"], e["fold"], e["augment"]) for e in m["history"]["folds"]}
            self.assertEqual(seen, {(lr, f, a) for lr in grid for f in range(3) for a in (False, True)})
            self.assertEqual(len(m["history"]["folds"]), 2 * 3 * 2)
            self.assertEqual(m["systems"]["clm_noul@tuned"]["n"], 6)

    def test_no_grid_has_no_lr_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gold = load_task2(make_dataset(tmp / "g", GOLD))
            m = run_clm(CFG, CachedEncoder(FakeEncoder(dim=16), tmp / "c"), make_fake_heads(tmp / "h.pt"), gold,
                        None, tmp / "out", (), registry=None)
            self.assertNotIn("lr_selection", m)
            self.assertTrue(all(e["lr"] == 1e-3 for e in m["history"]["folds"]))

    def test_missing_checkpoint_fails_before_embedding(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gold = load_task2(make_dataset(tmp / "g", GOLD))
            fake = FakeEncoder()
            with self.assertRaises(Exception):
                run_clm(CFG, CachedEncoder(fake, tmp / "c"), tmp / "missing.pt", gold, None, tmp / "o", (),
                        registry=None)
            self.assertEqual(fake.calls, 0)

    def test_unknown_final_system_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gold = load_task2(make_dataset(tmp / "g", GOLD))
            with self.assertRaises(ValueError):
                run_clm({**CFG, "final_system": "nope"}, CachedEncoder(FakeEncoder(), tmp / "c"),
                        make_fake_heads(tmp / "h.pt"), gold, None, tmp / "o", (), registry=None)

    def _with_logs(self, ds, bad_ids):
        ds.samples[:] = [replace(s, compile_log=("/tmp/tmpab/student.cpp:3:1: error: x" if s.sample_id in bad_ids else ""))
                         for s in ds.samples]
        return ds

    def test_compile_variant_probe_feature_and_final(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gold = self._with_logs(load_task2(make_dataset(tmp / "g", GOLD)), {"G4"})
            public = self._with_logs(load_task2(make_dataset(tmp / "p", [("P1", "EXA", None), ("P2", "EXB", None)])),
                                     {"P2"})
            cfg = {**CFG, "final_system": "probe_aug+cr", "probe": {"C": 1.0, "compile_feature": True},
                   "text": {**CFG["text"], "use_compile_log": True, "max_compile_tokens": 64},
                   "_compiler_id": "fake:g++ 13"}
            m = run_clm(cfg, CachedEncoder(FakeEncoder(dim=16), tmp / "c"), make_fake_heads(tmp / "h.pt"), gold,
                        public, tmp / "out", augment(gold.samples), registry=None)
            for system in SYSTEMS:
                for suffix in ("@0.5", "@tuned"):
                    self.assertEqual(m["systems"][f"{system}+cr{suffix}"]["n"], 6)
            for suffix in ("@0.5", "@tuned"):
                self.assertEqual(m["systems"]["probe_aug+cr" + suffix]["per_label"]["Lỗi biên dịch"]["f1"], 1.0)
            self.assertEqual(m["final_system"], "probe_aug+cr")
            self.assertEqual(m["compile"], {"enabled": True, "compiler_id": "fake:g++ 13"})
            raw = json.loads((tmp / "out" / "predictions.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_predictions(raw, ["P1", "P2"]), [])
            sub = {r["sample_id"]: r["output"]["taxonomy_error"] if "output" in r else r["labels"] for r in raw}
            self.assertIn("Lỗi biên dịch", sub["P2"])
            self.assertNotIn("Lỗi biên dịch", sub["P1"])

    def test_unknown_cr_final_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gold = load_task2(make_dataset(tmp / "g", GOLD))
            with self.assertRaises(ValueError):
                run_clm({**CFG, "final_system": "nope+cr"}, CachedEncoder(FakeEncoder(), tmp / "c"),
                        make_fake_heads(tmp / "h.pt"), gold, None, tmp / "o", (), registry=None)

    def test_public_per_exam_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gold = load_task2(make_dataset(tmp / "g", GOLD))
            public = load_task2(make_dataset(tmp / "p", [("P1", "EXA", None), ("P2", "EXA", None),
                                                         ("P3", "EXB", None)]))
            run_clm({**CFG, "data": {"public_per_exam": 1}}, CachedEncoder(FakeEncoder(), tmp / "c"),
                    make_fake_heads(tmp / "h.pt"), gold, public, tmp / "o", (), registry=None)
            ids = [r["sample_id"] for r in json.loads((tmp / "o" / "predictions.json").read_text(encoding="utf-8"))]
            self.assertEqual(ids, ["P1", "P3"])
