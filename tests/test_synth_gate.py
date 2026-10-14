import importlib.util
import sys
import unittest
from pathlib import Path

from tests import _data

_data.require_data()

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("check_labeler_gate", ROOT / "scripts" / "check_labeler_gate.py")
GATE = importlib.util.module_from_spec(SPEC)
sys.modules["check_labeler_gate"] = GATE
SPEC.loader.exec_module(GATE)


class TestLabelerGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = GATE.run_gate(_data.DATA)

    def test_observable_single_samples_all_match(self):
        self.assertGreaterEqual(self.result["n_counted"], 13)
        self.assertEqual(self.result["matched"], self.result["n_counted"])

    def test_known_noise_is_flagged(self):
        by_id = {r["sample_id"]: r for r in self.result["rows"]}
        self.assertEqual(by_id["EX02-S209"]["reason"], "data finding")
        self.assertIsNone(by_id["EX02-S210"]["reason"])


if __name__ == "__main__":
    unittest.main()
