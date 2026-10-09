import json
import tempfile
import unittest
from pathlib import Path

from src.task2.api_experiment import run_api
from src.task2.data import load_task2
from tests._task2 import FakeBackend, make_dataset

CFG = {"name": "task2_api_test", "seed": 42,
       "prompt": {"few_shot_k": 0, "max_code_chars": 4000, "use_aux_signals": False},
       "generation": {"temperature": 0.0, "n": 1, "max_new_tokens": 256}, "retry_on_parse_fail": 0,
       "checkpoint_every": 1}


def ans(*labels):
    return json.dumps({"rationale": "r", "taxonomy_error": list(labels)}, ensure_ascii=False)


class TestRunApi(unittest.TestCase):
    def test_outputs_metrics_and_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds = load_task2(make_dataset(Path(tmp) / "d", [("A1", "EXA", ["Lỗi logic"]), ("A2", "EXA", [])]))
            out = Path(tmp) / "out"
            m = run_api(CFG, ds, ds.samples, FakeBackend([ans("Lỗi logic"), ans()]), out, registry=None)
            self.assertAlmostEqual(m["systems"]["api"]["exact_match"], 1.0)
            for f in ("predictions.json", "predictions_full.json", "silver_labels.json", "metrics.json",
                      "resources.json", "config.json", "raw_outputs.jsonl"):
                self.assertTrue((out / f).exists(), f)
            silver = json.loads((out / "silver_labels.json").read_text(encoding="utf-8"))
            self.assertEqual(silver["A1"]["Lỗi logic"], 1.0)
            # second run: everything cached -> backend never called
            empty = FakeBackend([])
            run_api(CFG, ds, ds.samples, empty, out, registry=None)
            self.assertEqual(empty.calls, [])

    def test_unlabelled_has_no_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds = load_task2(make_dataset(Path(tmp) / "d", [("P1", "EXA", None)]))
            m = run_api(CFG, ds, ds.samples, FakeBackend(["rác"]), Path(tmp) / "o", registry=None)
            self.assertEqual(m["systems"], {})
            self.assertEqual(m["parse_failures"], 1)
            sub = json.loads((Path(tmp) / "o" / "predictions.json").read_text(encoding="utf-8"))
            self.assertEqual(sub, [{"sample_id": "P1", "output": {"taxonomy_error": []}}])


class UsageBackend(FakeBackend):
    """FakeBackend that reports token and cost counters, like a real API backend."""

    def __init__(self, texts):
        super().__init__(texts)
        self.usage = {"prompt_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

    def generate(self, requests, gen):
        for _ in requests:
            self.usage["prompt_tokens"] += 10
            self.usage["output_tokens"] += 5
            self.usage["cost_usd"] += 0.001
        return super().generate(requests, gen)

    def info(self):
        return {"backend": "fake", "model": "fake-1", "usage": dict(self.usage)}


class TestResumeSafety(unittest.TestCase):
    def test_truncated_cache_line_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds = load_task2(make_dataset(Path(tmp) / "d", [("A1", "EXA", ["Lỗi logic"]), ("A2", "EXA", [])]))
            out = Path(tmp) / "out"
            a1 = [ds.by_id()["A1"]]
            run_api(CFG, ds, a1, FakeBackend([ans("Lỗi logic")]), out, registry=None)
            with (out / "raw_outputs.jsonl").open("a", encoding="utf-8") as f:
                f.write('{"sample_id": "A2", "key": "x", "rec')  # run killed mid-append
            empty = FakeBackend([])
            m = run_api(CFG, ds, a1, empty, out, registry=None)  # must not crash, A1 must not be re-requested
            self.assertEqual(empty.calls, [])
            self.assertEqual(m["parse_failures"], 0)
            # A2 is requested now; its row must stay parseable after the truncated line
            run_api(CFG, ds, ds.samples, FakeBackend([ans()]), out, registry=None)
            final = FakeBackend([])
            run_api(CFG, ds, ds.samples, final, out, registry=None)
            self.assertEqual(final.calls, [])

    def test_resources_accumulate_and_survive_cached_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds = load_task2(make_dataset(Path(tmp) / "d", [("A1", "EXA", ["Lỗi logic"]), ("A2", "EXA", [])]))
            out = Path(tmp) / "out"
            run_api(CFG, ds, ds.samples, UsageBackend([ans("Lỗi logic"), ans()]), out, registry=None)
            res = json.loads((out / "resources.json").read_text(encoding="utf-8"))
            self.assertEqual(res["tokens_in"], 20)
            self.assertEqual(res["tokens_out"], 10)
            self.assertAlmostEqual(res["cost_usd"], 0.002)
            # fully cached rerun: nothing inferred, so the recorded cost must be kept
            run_api(CFG, ds, ds.samples, UsageBackend([]), out, registry=None)
            res = json.loads((out / "resources.json").read_text(encoding="utf-8"))
            self.assertEqual(res["tokens_in"], 20)
            self.assertAlmostEqual(res["cost_usd"], 0.002)
            # a new sample is inferred: its usage is added to the previous totals
            ds3 = load_task2(make_dataset(Path(tmp) / "d3", [("A1", "EXA", ["Lỗi logic"]), ("A2", "EXA", []),
                                                             ("A3", "EXA", ["Lỗi hàm"])]))
            run_api(CFG, ds3, ds3.samples, UsageBackend([ans("Lỗi hàm")]), out, registry=None)
            res = json.loads((out / "resources.json").read_text(encoding="utf-8"))
            self.assertEqual(res["tokens_in"], 30)
            self.assertAlmostEqual(res["cost_usd"], 0.003)
