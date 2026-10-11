import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests._task2 import make_dataset

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("run_task2_api", ROOT / "scripts" / "run_task2_api.py")
SCRIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCRIPT)

VAL = json.loads((ROOT / "data/splits/val_ids.json").read_text(encoding="utf-8"))
TRAIN = json.loads((ROOT / "data/splits/train_ids.json").read_text(encoding="utf-8"))

RUN_CFG = """provider: openai
openai: {model: gpt-4o-mini, max_usd: 3.0, input_usd_per_million: 0.15, output_usd_per_million: 0.60}
gemini: {model: gemma-x}
run:
  experiments: []
  smoke_sample_ids: []
  predict: true
  predict_config: api_predict
"""


class TestPreflight(unittest.TestCase):
    def _run(self, pools=None):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            labels = [["Lỗi logic"], ["Lỗi hàm"], []]
            gold = make_dataset(tmp / "g", [(sid, "EXA" if k % 2 else "EXB", labels[k % 3])
                                            for k, sid in enumerate(TRAIN + VAL)])
            pub = make_dataset(tmp / "p", [("P1", "EXA", None), ("P2", "EXB", None)])
            (tmp / "run.yaml").write_text(RUN_CFG, encoding="utf-8")
            argv = ["x", "--preflight", "--run-config", str(tmp / "run.yaml"), "--gold-root", str(gold),
                    "--public-root", str(pub)]
            buf = io.StringIO()
            real = SCRIPT.Task2ApiPipeline

            def spy(dataset, backend, cfg, pool=()):
                if pools is not None:
                    pools.append([s.sample_id for s in pool])
                return real(dataset, backend, cfg, pool)

            with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(buf), \
                    mock.patch.object(SCRIPT, "Task2ApiPipeline", spy):
                SCRIPT.main()
            return json.loads(buf.getvalue())

    def test_predict_demos_exclude_gold_val_and_cost_scales_with_n(self):
        pools = []
        rep = self._run(pools)
        self.assertTrue(pools)
        for pool in pools:
            self.assertEqual(sorted(pool), sorted(TRAIN))
        (name, e), = rep["experiments"].items()
        self.assertIn("api_predict", name)
        demos = e["demos_first_sample"]
        self.assertTrue(demos)
        ids = [d["sample_id"] if isinstance(d, dict) else getattr(d, "sample_id", d) for d in demos]
        self.assertFalse(set(ids) & set(VAL), ids)
        self.assertEqual(e["requests"], 2 * 5)
        self.assertGreater(e["estimated_usd"], 0)
        self.assertEqual(e["approx_input_tokens"] % 5, 0)

    def test_estimated_usd_formula(self):
        class Pipe:
            def build_request(self, s):
                return {"messages": [{"content": "x" * 3000}], "demos": []}

        cfg = {"generation": {"n": 5, "max_new_tokens": 100}}
        settings = {"openai": {"input_usd_per_million": 1.0, "output_usd_per_million": 2.0}}
        e = SCRIPT.preflight_entry(Pipe(), [1, 2], cfg, "openai", settings)
        self.assertEqual(e["approx_input_tokens"], 1000 * 2 * 5)
        self.assertAlmostEqual(e["estimated_usd"], (10000 * 1.0 + 10 * 100 * 2.0) / 1e6)
        self.assertNotIn("estimated_usd", SCRIPT.preflight_entry(Pipe(), [1], cfg, "gemini", settings))


if __name__ == "__main__":
    unittest.main()
