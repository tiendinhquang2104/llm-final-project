"""End-to-end pipeline tests with a scripted fake LLM (no network)."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.data.loader import load_split, load_task1
from src.data.preprocess import make_split
from src.llm.api_client import Backend
from src.task1.experiment import run_experiment
from src.task1.pipeline import Task1Pipeline, to_submission
from src.task1.prompts import build_messages, select_demos
from src.utils.config import load_config
from tests._data import DATA, ROOT, require_data

require_data()
DS = load_task1(DATA)
SPLIT = load_split(ROOT / "data" / "splits")


class FakeLLM(Backend):
    """Returns P1=wrong + full marks; the code rules must turn EX01 into total 2."""

    name = "fake"

    def __init__(self, broken_first=False):
        self.calls = 0
        self.broken_first = broken_first

    def generate(self, requests, gen):
        self.calls += 1
        if self.broken_first and self.calls == 1:
            return [["sorry, no json"] for _ in requests]
        out = {"rationale": "x", "problems": [{"pid": "P1", "status": "wrong"}],
               "rubric": {"compilable": 1, "io_format": 1, "logic": 4, "edge_case": 2, "complexity": 1,
                          "code_quality": 1}}
        return [[json.dumps(out)] for _ in requests]


class TestData(unittest.TestCase):
    def test_load(self):
        self.assertEqual(len(DS.samples), 32)
        s = DS.by_id()["EX01-S101"]
        self.assertIn("prob1", s.code)
        self.assertEqual(s.gold_total, sum(s.gold_rubric.values()))

    def test_split_fixed_and_disjoint(self):
        train, val = make_split([s.sample_id for s in DS.samples], val_ratio=0.2, seed=42)
        self.assertEqual(SPLIT, {"train": train, "val": val})
        self.assertFalse(set(SPLIT["train"]) & set(SPLIT["val"]))
        self.assertEqual(len(SPLIT["train"]) + len(SPLIT["val"]), 32)
        self.assertEqual((len(SPLIT["train"]), len(SPLIT["val"])), (26, 6))
        self.assertEqual({i[:4] for i in SPLIT["train"]}, {"EX01", "EX02"})

    def test_committed_split_matches_generator(self):
        committed = load_split(ROOT / "data" / "splits")
        self.assertEqual(committed, {"train": SPLIT["train"], "val": SPLIT["val"]})
        old = load_split(ROOT / "data" / "splits" / "history_13_19")
        self.assertEqual((len(old["train"]), len(old["val"])), (13, 19))


class TestPrompts(unittest.TestCase):
    def test_no_feedback_leak_and_demos_exclude_target(self):
        by = DS.by_id()
        pool = [by[i] for i in SPLIT["train"]]
        s = by[SPLIT["val"][0]]
        demos = select_demos(pool, s, 3)
        self.assertEqual(len(demos), 3)
        self.assertTrue(all(d.exam_id == s.exam_id and d.sample_id != s.sample_id for d in demos))
        msgs = build_messages(DS.exams[s.exam_id], s, demos, {"template": "structured"})
        text = msgs[0]["content"] + msgs[1]["content"]
        fb = json.loads((DATA / "task3_feedback.json").read_text(encoding="utf-8"))
        feedback = {x["sample_id"]: x["output"]["feedback"] for x in fb["samples"]}
        for sid in [s.sample_id] + [d.sample_id for d in demos]:
            self.assertNotIn(feedback[sid], text)

    def test_policy_in_code_vs_prompt(self):
        s = DS.by_id()["EX01-S101"]
        in_code = build_messages(DS.exams["EX01"], s, [], {"template": "structured"})[1]["content"]
        in_prompt = build_messages(DS.exams["EX01"], s, [], {"template": "structured",
                                                              "policy_in_prompt": True})[1]["content"]
        self.assertIn("KHÔNG tự áp dụng", in_code)
        self.assertIn("BẮT BUỘC", in_prompt)


class TestPipeline(unittest.TestCase):
    def test_rules_applied_after_llm(self):
        by = DS.by_id()
        pipe = Task1Pipeline(DS, FakeLLM(), {"prompt": {}, "generation": {}}, [by[i] for i in SPLIT["train"]])
        _, preds = pipe.run([by["EX01-S101"], by["EX02-S201"]])
        p1, p2 = preds
        self.assertEqual(p1["total_llm"], 10)
        self.assertEqual(p1["total_score"], 2)  # prerequisite rule fired
        self.assertEqual(p2["total_score"], 10)  # single_problem: no prerequisite

    def test_retry_on_parse_failure(self):
        by = DS.by_id()
        llm = FakeLLM(broken_first=True)
        pipe = Task1Pipeline(DS, llm, {"prompt": {}, "generation": {}}, [])
        _, preds = pipe.run([by["EX02-S201"]])
        self.assertEqual(llm.calls, 2)
        self.assertTrue(preds[0]["parse_ok"])

    def test_invalid_output_has_no_fabricated_score(self):
        class Dead(Backend):
            def generate(self, requests, gen):
                return [["nope"] for _ in requests]

        by = DS.by_id()
        pipe = Task1Pipeline(DS, Dead(), {"prompt": {}, "generation": {}}, [by[i] for i in SPLIT["train"]])
        _, preds = pipe.run([by["EX02-S201"]])
        self.assertFalse(preds[0]["parse_ok"])
        self.assertIsNone(preds[0]["total_score"])
        self.assertEqual(to_submission(preds), [])

    def test_run_experiment_writes_artifacts(self):
        cfg = load_config(ROOT / "configs/task1/e3_few_shot_structured.yaml")
        with tempfile.TemporaryDirectory() as tmp:
            llm = FakeLLM()
            registry = Path(tmp) / "registry.csv"
            m = run_experiment(cfg, DS, SPLIT, llm, tmp, verbose=False, registry=registry)
            out = Path(tmp) / "e3_few_shot_structured"
            for f in ("config.json", "prompt.md", "raw_outputs.jsonl", "predictions.json", "metrics.json",
                      "error_analysis.md", "predictions_full.json"):
                self.assertTrue((out / f).exists(), f)
            self.assertNotIn(DS.by_id()[SPLIT["val"][0]].code, (out / "prompt.md").read_text(encoding="utf-8"))
            self.assertEqual(m["main"]["n"], len(SPLIT["val"]))
            self.assertIn("full", m["rule_ablation"])
            rows = list(csv.DictReader(open(registry, encoding="utf-8")))
            self.assertEqual([(r["experiment_id"], r["task"]) for r in rows], [("e3_few_shot_structured", "task1")])
            self.assertIn('"qwk"', rows[0]["metrics"])
            calls = llm.calls
            m2 = run_experiment(cfg, DS, SPLIT, llm, tmp, verbose=False, registry=None)  # cache hit: no new model call
            self.assertEqual(llm.calls, calls)
            self.assertEqual(m["main"]["qwk"], m2["main"]["qwk"])
            # provenance of the original inference survives a cache hit (model version + cost reporting)
            info = json.loads((out / "config.json").read_text(encoding="utf-8"))["model_info"]["inference"]
            self.assertIn("inferred_at", info)
            self.assertIn("from_cache", info)
            final = load_config(ROOT / "configs/task1/final.yaml")  # same prompt as e3 -> shared cache
            run_experiment(final, DS, SPLIT, llm, tmp, verbose=False, registry=None)
            self.assertEqual(llm.calls, calls)
            self.assertTrue((Path(tmp) / "task1_final" / "predictions.json").exists())

    def test_failed_requests_are_not_cached(self):
        class Flaky(FakeLLM):
            def generate(self, requests, gen):
                if self.calls < 2:  # first two calls fail (empty text)
                    self.calls += 1
                    return [[""] for _ in requests]
                return super().generate(requests, gen)

        cfg = load_config(ROOT / "configs/task1/e1_zero_shot_plain.yaml")
        cfg["data"]["sample_ids"] = ["EX02-S204"]
        with tempfile.TemporaryDirectory() as tmp:
            llm = Flaky()
            run_experiment(cfg, DS, SPLIT, llm, tmp, verbose=False, registry=None)  # call 1 fails, retry (call 2) fails
            run_experiment(cfg, DS, SPLIT, llm, tmp, verbose=False, registry=None)  # must call the model again
            self.assertEqual(llm.calls, 3)

    def test_quick_subset(self):
        cfg = load_config(ROOT / "configs/task1/e1_zero_shot_plain.yaml")
        cfg["data"]["sample_ids"] = ["EX01-S105", "EX02-S204"]
        with tempfile.TemporaryDirectory() as tmp:
            m = run_experiment(cfg, DS, SPLIT, FakeLLM(), tmp, verbose=False, registry=None)
        self.assertEqual(m["main"]["n"], 2)

    def test_smoke_sample_reused_in_full_run(self):
        cfg = load_config(ROOT / "configs/task1/e3_few_shot_structured.yaml")
        first, second = SPLIT["val"][:2]
        cfg["name"] += "_test"
        cfg["data"]["sample_ids"] = [first]
        seen = []

        class Recorder(FakeLLM):
            def generate(self, requests, gen):
                seen.extend(q["sample"].sample_id for q in requests)
                return super().generate(requests, gen)

        backend = Recorder()
        with tempfile.TemporaryDirectory() as tmp:
            run_experiment(cfg, DS, SPLIT, backend, tmp, verbose=False, registry=None)
            full = load_config(ROOT / "configs/task1/e3_few_shot_structured.yaml")
            full["data"]["sample_ids"] = [first, second]
            run_experiment(full, DS, SPLIT, backend, tmp, verbose=False, registry=None)
        self.assertEqual(seen, [first, second])

    def test_interrupted_run_resumes_from_checkpoint(self):
        class DiesAfterFirstChunk(FakeLLM):
            def generate(self, requests, gen):
                if self.calls >= 1:
                    raise KeyboardInterrupt
                return super().generate(requests, gen)

        cfg = load_config(ROOT / "configs/task1/e1_zero_shot_plain.yaml")
        cfg["checkpoint_every"] = 2
        cfg["data"]["sample_ids"] = ["EX01-S101", "EX01-S102", "EX02-S201", "EX02-S202"]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(KeyboardInterrupt):
                run_experiment(cfg, DS, SPLIT, DiesAfterFirstChunk(), tmp, verbose=False, registry=None)
            seen = []

            class Recorder(FakeLLM):
                def generate(self, requests, gen):
                    seen.extend(q["sample"].sample_id for q in requests)
                    return super().generate(requests, gen)

            m = run_experiment(cfg, DS, SPLIT, Recorder(), tmp, verbose=False, registry=None)
            self.assertEqual(seen, ["EX02-S201", "EX02-S202"])  # only the missing samples
            self.assertEqual(m["main"]["n"], 4)
            self.assertFalse((Path(tmp) / cfg["name"] / "raw_outputs.partial.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
