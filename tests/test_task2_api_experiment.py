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
