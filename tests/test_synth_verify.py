import unittest

from src.synth.verify import (
    Runner,
    RunOutcome,
    TestCase as VCase,
    build_multi_exec_report,
    classify_multi,
    compile_error,
    normalize,
    run_single,
)

TIMEOUT = object()


class FakeRunner(Runner):
    runner_id = "fake"

    def __init__(self, outputs, compiled=True, log="clean"):
        self.outputs, self.compiled, self.log = outputs, compiled, log

    def run(self, code, stdin, timeout_s, exam_type="single_problem"):
        if not self.compiled:
            return RunOutcome(False, "student.cpp:3:1: error: bad", 1)
        v = self.outputs.get(stdin, TIMEOUT)
        if v is TIMEOUT:
            return RunOutcome(True, self.log, 124, "", "", True, timeout_s)
        return RunOutcome(True, self.log, 0, v, "", False, 0.01)


def tc(expected, group="normal", stdin=None):
    return VCase(input=stdin or expected, expected=expected, group=group)

class TestHelpers(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize(" True \n"), "true")
        self.assertEqual(normalize("1  2"), "1 2")

    def test_compile_error(self):
        self.assertTrue(compile_error("/tmp/x/student.cpp:5:3: error: 'x' was not declared"))
        self.assertFalse(compile_error("(linker) undefined reference to main"))
        self.assertFalse(compile_error(None))


class TestSingle(unittest.TestCase):
    def test_all_pass(self):
        tests = [tc("1"), tc("2")]
        report = run_single(FakeRunner({"1": "1", "2": "2"}), "code", tests)
        self.assertEqual(report.signals, report.signals.__class__(has_code=True))
        self.assertIn("pass 2/2", report.exec_report)

    def test_extra_character_is_not_exact_but_normalized(self):
        tests = [tc("True")]
        report = run_single(FakeRunner({"True": " True"}), "code", tests)
        self.assertFalse(report.signals.token_exact)
        self.assertTrue(report.signals.token_normalized)

    def test_wrong_token(self):
        tests = [tc("True")]
        report = run_single(FakeRunner({"True": "TRUE"}), "code", tests)
        self.assertFalse(report.signals.token_normalized)  # TRUE is a format (IO) error, EX02-S206
        self.assertEqual(report.signals.normal_pass_ratio, 1.0)  # ...but the logic is right

    def test_wrong_value_is_not_a_format_error(self):
        tests = [tc("True"), tc("False", stdin="x")]
        report = run_single(FakeRunner({"True": "False", "x": "True"}), "code", tests)
        self.assertTrue(report.signals.token_normalized)
        self.assertEqual(report.signals.normal_pass_ratio, 0.0)
        self.assertFalse(report.signals.core_incomplete)  # it prints answers: S4, not S2

    def test_timeout_marks_non_termination(self):
        tests = [tc("1")]
        report = run_single(FakeRunner({}), "code", tests)
        self.assertFalse(report.signals.terminates)

    def test_compile_failure(self):
        report = run_single(FakeRunner({}, compiled=False), "code", [tc("1")])
        self.assertFalse(report.signals.compiles)

    def test_edge_groups_counted_not_tests(self):
        tests = [tc("a", "edge:min"), tc("b", "edge:min"), tc("c", "edge:max")]
        report = run_single(FakeRunner({"a": "a", "b": "X", "c": "c"}), "code", tests)
        self.assertEqual(report.signals.edge_groups_failed, 1)  # one group (min) failed, not 1 test... 2 tests in min

    def test_examples_only_pass_detects_hardcode(self):
        tests = [tc("5", "example", stdin="ex"), tc("7", "normal", stdin="n1"), tc("9", "normal", stdin="n2")]
        report = run_single(FakeRunner({"ex": "5", "n1": "0", "n2": "0"}), "code", tests)
        self.assertTrue(report.signals.examples_only_pass)

    def test_timeout_on_large_edge_is_tle_not_infinite_loop(self):
        tests = [tc("1"), tc("2", "edge:max")]
        report = run_single(FakeRunner({"1": "1"}), "code", tests)  # edge input times out
        self.assertTrue(report.signals.terminates)
        self.assertFalse(report.signals.perf_ok)
        self.assertEqual(report.signals.edge_groups_failed, 1)

    def test_perf_probe(self):
        tests = [tc("1", "perf")]
        report = run_single(FakeRunner({}), "code", tests)
        self.assertFalse(report.signals.perf_ok)
        self.assertIn("perf_probe: TIMEOUT", report.exec_report)


class TestExecReportAndMulti(unittest.TestCase):
    def test_exec_report_has_edge_and_run(self):
        tests = [tc("1"), tc("2", "edge:min"), tc("3", "perf")]
        report = run_single(FakeRunner({"1": "1", "2": "2", "3": "3"}), "code", tests)
        lines = report.exec_report.splitlines()
        self.assertTrue(any(l.startswith("compile: OK") for l in lines))
        self.assertTrue(any(l.startswith("edge_probe:") and "min=pass" in l for l in lines))
        self.assertTrue(any(l.startswith("perf_probe:") for l in lines))

    def test_classify_multi_orders_problems(self):
        m = classify_multi({"P2": "ok", "P1": "ok", "P4": "missing", "P3": "edge"}, compiles=True, infinite_loop=False)
        self.assertEqual(m.problem_states, ("ok", "ok", "edge", "missing"))
        self.assertTrue(m.p1_ok)

    def test_multi_exec_report(self):
        text = build_multi_exec_report({"P1": "ok", "P2": "ok", "P3": "TIMEOUT"}, "clean")
        self.assertIn("per_problem: P1=ok  P2=ok  P3=TIMEOUT", text)


if __name__ == "__main__":
    unittest.main()


class TestCachingRunner(unittest.TestCase):
    class Counting(Runner):
        runner_id = "counting"

        def __init__(self):
            self.calls = 0

        def run(self, code, stdin, timeout_s, exam_type="single_problem", files=None, args=None):
            self.calls += 1
            return RunOutcome(True, "", 0, f"out:{stdin}", "", False, 0.01)

    def test_identical_requests_hit_the_cache_across_instances(self):
        import tempfile
        from pathlib import Path
        from src.synth.verify import CachingRunner
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cache.sqlite"
            inner = self.Counting()
            first = CachingRunner(inner, path)
            a = first.run("code", "1", 2.0)
            b = first.run("code", "1", 2.0)
            first.run("code", "2", 2.0)                      # different stdin -> miss
            first.run("code", "1", 2.0, files={"d.csv": "x"}, args=["d.csv"])  # different files -> miss
            self.assertEqual(inner.calls, 3)
            self.assertEqual(a, b)
            first.close()
            again = CachingRunner(self.Counting(), path)     # reopened: still cached
            self.assertEqual(again.run("code", "1", 2.0).stdout, "out:1")
            self.assertEqual(again.inner.calls, 0)
            self.assertEqual(again.stats()["hits"], 1)
            again.close()
