import json
import unittest
from pathlib import Path

from src.synth import quota
from src.synth.compliance import check
from src.synth.labeler import SINGLE_POINTS, round_half_down
from src.synth.problems import load_problems
from src.synth.taxonomy import DEFECTS

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "src" / "synth" / "problems"


class TestQuota(unittest.TestCase):
    def test_totals_match_plan(self):
        self.assertEqual(quota.TOTAL_SINGLE, 300)
        self.assertEqual(quota.TOTAL_MULTI, 200)
        self.assertEqual(len(quota.single_slots()), 300)
        self.assertEqual(len(quota.multi_slots()), 200)

    def test_single_buckets_follow_plan_table(self):
        got = {}
        for rule, count, _ in quota.SINGLE_BUCKETS:
            got[rule] = got.get(rule, 0) + count
        self.assertEqual(got, {"S6": 45, "S5": 20, "S11": 20, "S12": 20, "S10": 25, "S4": 50, "S9": 15,
                               "S8": 20, "S7": 20, "S3": 15, "S2": 20, "S1": 25, "S0": 5})

    def test_slot_defects_exist(self):
        for _, _, combos in quota.SINGLE_BUCKETS:
            for combo in combos:
                for d in combo:
                    self.assertTrue(d in DEFECTS or d == "D14b", d)

    def test_multi_total_three_is_unreachable(self):
        # P1 alone = 2.5 -> 2; the smallest sum above 2.5 is 2.5 + 1.25 = 3.75 -> 4
        sums = {round_half_down(2.5 + a + b + c) for a in SINGLE_POINTS.values()
                for b in SINGLE_POINTS.values() for c in SINGLE_POINTS.values()}
        self.assertNotIn(3, sums)
        self.assertNotIn(3, dict(quota.MULTI_BUCKETS))

    def test_state_plans_round_to_their_total(self):
        for total, plans in quota.MULTI_STATE_PLANS.items():
            for states in plans:
                points = 2.5 + sum(SINGLE_POINTS[s] for s in states)
                self.assertEqual(round_half_down(points), total, (total, states))

    def test_levels_cycle_all_four(self):
        self.assertEqual(len(set(quota.LEVEL_CYCLE)), 4)

    def test_bank_shape_matches_plan(self):
        problems = load_problems(BANK)
        train = [p for p in problems.values() if not p.heldout]
        self.assertEqual(sum(1 for p in train if p.exam_type == "single_problem"), 18)
        self.assertEqual(sum(1 for p in train if p.exam_type == "multi_problem"), 10)
        self.assertEqual(sum(1 for p in problems.values() if p.heldout), 4)


class TestGeneratedFeedback(unittest.TestCase):
    def test_all_task3_feedback_compliant(self):
        r = ROOT / "data" / "synth" / "v1" / "task3_feedback.json"
        if not r.exists():
            self.skipTest("run scripts/build_synth_dataset.py --count first")
        samples = json.loads(r.read_text(encoding="utf-8"))["samples"]
        bad = [(s["sample_id"], check(s["output"]["feedback"], s["input"]["target_feedback_level"]).violations)
               for s in samples if not check(s["output"]["feedback"], s["input"]["target_feedback_level"]).ok]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
