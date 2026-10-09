import json
import tempfile
import unittest
from pathlib import Path

from src.task2.benchmark import collect_rows, to_markdown


def _run(d: Path, systems: dict, res: dict) -> Path:
    d.mkdir(parents=True)
    (d / "metrics.json").write_text(json.dumps({"systems": systems}))
    (d / "resources.json").write_text(json.dumps(res))
    return d


class TestBenchmark(unittest.TestCase):
    def test_rows_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            f1 = {"n": 6, "macro_f1": 0.25, "micro_f1": 0.5}
            api = _run(tmp / "api", {"api": f1}, {"hardware": "API", "seconds_per_sample": 3.0, "tokens_in": 100,
                                                  "tokens_out": 10, "cost_usd": 0.01, "peak_memory_gb": None,
                                                  "train_seconds": None})
            clm = _run(tmp / "clm", {"clm_noul@tuned": f1, "probe@0.5": f1},
                       {"hardware": "M3", "seconds_per_sample": 9.5, "peak_memory_gb": 5.5, "train_seconds": 12.0,
                        "tokens_in": None, "tokens_out": None, "cost_usd": 0.0})
            rows = collect_rows([api, clm, tmp / "missing"])
            self.assertEqual([r["system"] for r in rows], ["api", "clm_noul@tuned", "probe@0.5"])
            md = to_markdown(rows)
            self.assertIn("| api | api |", md)
            self.assertIn("5.50", md)
            self.assertIn("0.250", md)
