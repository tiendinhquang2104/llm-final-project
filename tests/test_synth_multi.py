import unittest

from src.synth.labeler import label_multi
from src.synth.multi import assemble, parse_statuses, run_multi
from src.synth.problems import Problem
from src.synth.verify import Runner, RunOutcome


class FakeRunner(Runner):
    runner_id = "fake"

    def __init__(self, stdout="", compiled=True, timed_out=False, log="clean"):
        self.stdout, self.compiled, self.timed_out, self.log = stdout, compiled, timed_out, log

    def run(self, code, stdin, timeout_s, exam_type="single_problem"):
        if not self.compiled:
            return RunOutcome(False, "student.cpp:1:1: error: nope", 1)
        return RunOutcome(True, self.log, 0, self.stdout, "", self.timed_out, 0.01)


PROBLEM = Problem(
    exam_id="SYN-GEN",
    exam_type="multi_problem",
    statement="...",
    problems=[{"pid": f"P{i}"} for i in range(1, 5)],
    harness="int main(){ return 0; }",
)


class TestAssembleParse(unittest.TestCase):
    def test_assemble_appends_harness(self):
        self.assertTrue(assemble("int f(){}", "int main(){}").rstrip().endswith("int main(){}"))

    def test_assemble_without_harness(self):
        self.assertEqual(assemble("int f(){}", ""), "int f(){}")

    def test_parse_statuses(self):
        statuses = parse_statuses("noise\nP1=ok P2=partial P3: crash P4=MISSING")
        self.assertEqual(statuses, {"P1": "ok", "P2": "partial", "P3": "crash", "P4": "missing"})


class TestRunMulti(unittest.TestCase):
    def test_all_ok(self):
        report = run_multi(FakeRunner("P1=ok P2=ok P3=ok P4=ok"), "code", PROBLEM)
        self.assertEqual(report.states, {"P1": "ok", "P2": "ok", "P3": "ok", "P4": "ok"})
        self.assertEqual(label_multi(report.signals).total, 10)

    def test_partial_maps_to_total_9(self):
        report = run_multi(FakeRunner("P1=ok P2=ok P3=partial P4=ok"), "code", PROBLEM)
        self.assertEqual(label_multi(report.signals).total, 9)

    def test_missing_question(self):
        report = run_multi(FakeRunner("P1=ok P2=ok P3=missing P4=ok"), "code", PROBLEM)
        self.assertEqual(report.states["P3"], "missing")

    def test_unprinted_question_defaults_to_missing(self):
        report = run_multi(FakeRunner("P1=ok P2=ok"), "code", PROBLEM)
        self.assertEqual(report.states["P3"], "missing")

    def test_compile_failure(self):
        report = run_multi(FakeRunner(compiled=False), "code", PROBLEM)
        self.assertFalse(report.compiles)
        self.assertFalse(report.signals.compiles)

    def test_timeout_marks_infinite_loop_and_m2(self):
        report = run_multi(FakeRunner("", timed_out=True), "code", PROBLEM)
        self.assertTrue(report.signals.infinite_loop_any)
        self.assertEqual(label_multi(report.signals).rule_id, "M2")


if __name__ == "__main__":
    unittest.main()
