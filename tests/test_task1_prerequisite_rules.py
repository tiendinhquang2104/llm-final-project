"""Unit tests for the prerequisite / compile-gate rules (independent of any prompt or model)."""
import json
import unittest

from src.data.loader import DIMENSIONS
from src.task1.prerequisite_rules import (
    ExamPolicy, RuleConfig, apply_rules, clamp_rubric, derive_logic, normalize_status, policy_from_exam,
)

from tests._data import DATA, require_data

require_data()
EXAMS = {e["exam_id"]: e for e in json.loads((DATA / "exams.json").read_text(encoding="utf-8"))["exams"]}
FULL = {"compilable": 1, "io_format": 1, "logic": 4, "edge_case": 2, "complexity": 1, "code_quality": 1}
OK4 = {"P1": "correct", "P2": "correct", "P3": "correct", "P4": "correct"}


class TestPolicyFromExam(unittest.TestCase):
    def test_multi_problem_prerequisite_parsed(self):
        pol = policy_from_exam(EXAMS["EX01"])
        self.assertEqual(pol.prerequisites, {"P1": ("P2", "P3", "P4")})
        self.assertEqual(set(pol.problem_weights), {"P1", "P2", "P3", "P4"})

    def test_ex01_statement_zeroes_everything_when_not_compilable(self):
        self.assertEqual(policy_from_exam(EXAMS["EX01"]).zero_on_not_compilable, tuple(DIMENSIONS))

    def test_single_problem_has_no_prerequisite_and_keeps_code_quality(self):
        pol = policy_from_exam(EXAMS["EX02"])
        self.assertEqual(pol.prerequisites, {})
        self.assertNotIn("code_quality", pol.zero_on_not_compilable)

    def test_overrides(self):
        pol = policy_from_exam(EXAMS["EX01"], {"zero_on_prereq_fail": ["logic"]})
        self.assertEqual(pol.zero_on_prereq_fail, ("logic",))


class TestPrerequisiteRule(unittest.TestCase):
    def setUp(self):
        self.pol = policy_from_exam(EXAMS["EX01"])

    def test_prereq_correct_keeps_scores(self):
        r, total, trace = apply_rules(FULL, OK4, self.pol)
        self.assertEqual(r, FULL)
        self.assertEqual(total, 10)
        self.assertEqual(trace, [])

    def test_prereq_wrong_zeroes_dependents(self):
        r, total, trace = apply_rules(FULL, {**OK4, "P1": "wrong"}, self.pol)
        # Matches the teacher pattern (e.g. EX01-S105..S107): only compilable + io_format survive.
        self.assertEqual(r, {"compilable": 1, "io_format": 1, "logic": 0, "edge_case": 0, "complexity": 0,
                             "code_quality": 0})
        self.assertEqual(total, 2)
        self.assertTrue(any(t.startswith("prereq:P1=wrong") for t in trace))

    def test_prereq_wrong_zeroes_fractional_dependents(self):
        scores = {**FULL, "logic": 3.75, "edge_case": 1.25}
        r, total, _ = apply_rules(scores, {**OK4, "P1": "wrong"}, self.pol)
        self.assertEqual((r["logic"], r["edge_case"], total), (0, 0, 2))

    def test_each_fail_status_triggers(self):
        for st in ("wrong", "runtime_error", "not_attempted"):
            with self.subTest(st=st):
                _, total, _ = apply_rules(FULL, {**OK4, "P1": st}, self.pol)
                self.assertEqual(total, 2)

    def test_partial_prereq_passes_by_default_but_fails_in_strict_mode(self):
        st = {**OK4, "P1": "partial"}
        self.assertEqual(apply_rules(FULL, st, self.pol)[1], 10)
        self.assertEqual(apply_rules(FULL, st, self.pol, RuleConfig(prereq_strict=True))[1], 2)

    def test_dependent_failure_does_not_trigger_rule(self):
        _, total, trace = apply_rules(FULL, {**OK4, "P2": "wrong"}, self.pol)
        self.assertEqual(total, 10)
        self.assertEqual(trace, [])

    def test_unknown_status_is_noop(self):
        r, _, trace = apply_rules(FULL, {}, self.pol)
        self.assertEqual(r, FULL)
        self.assertIn("prereq:P1:status_unknown->no_op", trace)

    def test_rule_can_be_disabled(self):
        _, total, _ = apply_rules(FULL, {**OK4, "P1": "wrong"}, self.pol, RuleConfig(prerequisite=False))
        self.assertEqual(total, 10)

    def test_single_problem_never_fires(self):
        pol = policy_from_exam(EXAMS["EX02"])
        _, total, _ = apply_rules(FULL, {"P1": "wrong"}, pol)
        self.assertEqual(total, 10)

    def test_generic_chain_policy(self):
        pol = ExamPolicy("X", "multi_problem", prerequisites={"P2": ("P3",)},
                         problem_weights={"P1": 1, "P2": 1, "P3": 1})
        r, _, trace = apply_rules(FULL, {"P1": "correct", "P2": "wrong", "P3": "correct"}, pol)
        self.assertEqual(r["logic"], 0)
        self.assertTrue(any("P3:not_graded" in t for t in trace))


class TestCompileGate(unittest.TestCase):
    def test_ex01_not_compilable_is_all_zero(self):
        _, total, _ = apply_rules({**FULL, "compilable": 0}, OK4, policy_from_exam(EXAMS["EX01"]))
        self.assertEqual(total, 0)

    def test_ex02_not_compilable_keeps_code_quality(self):
        # Teacher pattern on EX02 (S203, S212, S217): total 1 = code_quality only.
        r, total, _ = apply_rules({**FULL, "compilable": 0}, {"P1": "wrong"}, policy_from_exam(EXAMS["EX02"]))
        self.assertEqual(total, 1)
        self.assertEqual(r["code_quality"], 1)

    def test_gate_disabled(self):
        _, total, _ = apply_rules({**FULL, "compilable": 0}, OK4, policy_from_exam(EXAMS["EX01"]),
                                  RuleConfig(compile_gate=False))
        self.assertEqual(total, 9)


class TestClampAndDerive(unittest.TestCase):
    def test_clamp(self):
        r = clamp_rubric({"compilable": 1, "io_format": 0.01, "logic": 2.6, "edge_case": 0,
                          "complexity": 1, "code_quality": 0})
        self.assertEqual(r["logic"], 2.6)
        self.assertEqual(r["io_format"], 0.01)
        with self.assertRaises(ValueError):
            clamp_rubric({**r, "logic": 2.601})

    def test_total_is_sum_of_dims(self):
        _, total, _ = apply_rules({"compilable": 1, "io_format": 1, "logic": 3.75, "edge_case": 2, "complexity": 1,
                                   "code_quality": 1}, OK4, policy_from_exam(EXAMS["EX01"]))
        self.assertEqual(total, 9.75)

    def test_derive_logic_weighted(self):
        w = {"P1": 2.5, "P2": 2.5, "P3": 2.5, "P4": 2.5}
        self.assertEqual(derive_logic(OK4, w), 4)
        self.assertEqual(derive_logic({**OK4, "P3": "not_attempted", "P4": "runtime_error"}, w), 2)
        self.assertEqual(derive_logic({**OK4, "P3": "partial"}, w), 4)  # 3.5 rounds half up
        self.assertIsNone(derive_logic({"P1": "correct"}, w))

    def test_derive_logic_in_apply_rules(self):
        pol = policy_from_exam(EXAMS["EX01"])
        r, _, trace = apply_rules(FULL, {**OK4, "P3": "not_attempted", "P4": "wrong"}, pol,
                                  RuleConfig(derive_logic=True))
        self.assertEqual(r["logic"], 2)
        self.assertIn("derive_logic:4->2", trace)

    def test_normalize_status(self):
        self.assertEqual(normalize_status("Correct"), "correct")
        self.assertEqual(normalize_status("infinite loop"), "runtime_error")
        self.assertEqual(normalize_status("not attempted"), "not_attempted")
        self.assertIsNone(normalize_status("???"))


if __name__ == "__main__":
    unittest.main()
