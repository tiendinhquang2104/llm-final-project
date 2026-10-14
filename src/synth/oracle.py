"""Auto-oracle (synth_plan.md section "Cải tiến 3", implementation step 6).

The ``exec_report`` field is a model *input*. At inference a test submission has no hidden
testcases, so the report must come from information that also exists for a test exam; the
training records must use the *same* source, otherwise the model learns a signal it will never
see. Two modes:

* ``minimal`` (default, no LLM needed): compile result + the examples written in the statement
  (the problem's ``example`` tests). Statement examples exist for every exam, train or test.
* ``full``: ``minimal`` plus inputs whose expected output is a majority vote of K reference
  solutions written by an LLM (``solution_generator``). Needs the LLM; never uses the hand-written
  labeling tests.

The report never contains the injected defect, the rule, or anything derived from the labeling
tests (that would leak the label into the input).
"""

from __future__ import annotations

import random
import re
from collections import Counter
from dataclasses import dataclass

from src.synth.problems import Problem
from src.synth.verify import Runner, TestCase, compile_error

ORACLE_MODES = ("minimal", "full")
_LOG_LINE_RE = re.compile(r"^\S*?([\w.-]+\.(?:cpp|h)):(\d+):(\d+): (?:fatal )?error: (.*)$", re.MULTILINE)


def majority_vote(outputs: list[str], min_agree: int = 3) -> str | None:
    """Expected output agreed on by at least ``min_agree`` reference solutions (ties dropped)."""
    counts = Counter(o.rstrip("\n") for o in outputs)
    if not counts:
        return None
    value, n = counts.most_common(1)[0]
    return value if n >= min_agree else None


@dataclass
class OracleTest:
    stdin: str
    expected: str
    group: str = "example"
    timeout_s: float = 2.0

    def as_case(self) -> TestCase:
        return TestCase(input=self.stdin, expected=self.expected, group=self.group, timeout_s=self.timeout_s)


def statement_examples(problem: Problem) -> list[OracleTest]:
    """The examples printed in the statement (``example`` tests): available for any exam."""
    return [OracleTest(t.input, t.expected, "example") for t in problem.tests if t.group == "example"]


def first_compile_error(log: str) -> str:
    """One-line summary of the first compiler error (file path stripped)."""
    m = _LOG_LINE_RE.search(log or "")
    return f"line {m.group(2)}: {m.group(4).strip()[:120]}" if m else ""


class AutoOracle:
    def __init__(self, problem: Problem, runner: Runner, mode: str = "minimal", solution_generator=None,
                 n_references: int = 5, rng: random.Random | None = None):
        if mode not in ORACLE_MODES:
            raise ValueError(f"oracle mode must be one of {ORACLE_MODES}")
        if mode == "full" and solution_generator is None:
            raise ValueError("oracle mode 'full' needs an LLM solution_generator")
        self.problem = problem
        self.runner = runner
        self.mode = mode
        self.solution_generator = solution_generator
        self.n_references = n_references
        self.rng = rng or random.Random(0)
        self.tests = statement_examples(problem)
        if mode == "full":
            self.tests += self._generated_tests()

    def _generated_tests(self) -> list[OracleTest]:
        inputs = self.problem.metadata.get("oracle_inputs", [])
        expected = self.build_reference_expectations(inputs)
        return [OracleTest(i, expected[i], "generated") for i in inputs if i in expected]

    def build_reference_expectations(self, inputs: list[str]) -> dict[str, str]:
        """Majority vote of K LLM reference solutions for each input."""
        references = self.solution_generator(self.problem, self.n_references)
        expected: dict[str, str] = {}
        for stdin in inputs:
            outs = []
            for code in references:
                out = self.runner.run(code, stdin, 2.0, self.problem.exam_type)
                if out.compiled and not out.timed_out:
                    outs.append(out.stdout)
            vote = majority_vote(outs)
            if vote is not None:
                expected[stdin] = vote
        return expected

    def exec_report(self, code: str) -> str:
        """Report built only from compile + oracle tests. Never mentions defects or labels."""
        if not code.strip():
            return "compile: FAIL (g++ -std=c++11) | empty submission"
        if self.problem.exam_type == "multi_problem":
            return self._multi_report(code)
        lines = []
        cases = [t.as_case() for t in self.tests]
        outcomes = [self.runner.run(code, c.input, c.timeout_s, self.problem.exam_type) for c in cases[:1]]
        compiled = outcomes[0].compiled if outcomes else self._compiles(code)
        if not compiled:
            log = outcomes[0].compile_log if outcomes else ""
            err = first_compile_error(log)
            return "compile: FAIL (g++ -std=c++11)" + (f" | {err}" if err else "")
        lines.append("compile: OK (g++ -std=c++11)")
        if not cases:
            lines.append("statement_examples: none")
            return "\n".join(lines)
        outcomes += [self.runner.run(code, c.input, c.timeout_s, self.problem.exam_type) for c in cases[1:]]
        exact = norm = timeouts = crashes = 0
        for c, o in zip(cases, outcomes):
            if o.timed_out:
                timeouts += 1
                continue
            if o.returncode not in (0, None):
                crashes += 1
            out = (o.stdout or "").replace("\r\n", "\n").rstrip("\n")
            exact += out == c.expected.rstrip("\n")
            norm += " ".join(out.lower().split()) == " ".join(c.expected.lower().split())
        label = "statement_examples" if self.mode == "minimal" else "oracle_tests"
        lines.append(f"{label}: {len(cases)} | pass {norm}/{len(cases)} | strict {exact}/{len(cases)}"
                     f" | timeout {timeouts} | crash {crashes}")
        return "\n".join(lines)

    def _compiles(self, code: str) -> bool:
        return self.runner.run(code, "", 2.0, self.problem.exam_type).compiled

    def _multi_report(self, code: str) -> str:
        # functions only: syntax check by compiling with a stub main (no grading data at inference)
        probe = code.rstrip("\n") + "\n\nint main() { return 0; }\n"
        out = self.runner.run(probe, "", 2.0, "multi_problem")
        if not out.compiled:
            # the submission may define its own main; retry as-is before declaring failure
            alone = self.runner.run(code, "", 2.0, "multi_problem")
            if alone.compiled or not compile_error(out.compile_log):
                out = alone
        if not out.compiled:
            err = first_compile_error(out.compile_log)
            return "compile: FAIL (g++ -std=c++11 -fsyntax-only)" + (f" | {err}" if err else "")
        defined = [p["pid"] for p in self.problem.problems
                   if re.search(rf"\b{_proto_name(p)}\s*\([^;{{]*\)\s*\{{", code)]
        return ("compile: OK (g++ -std=c++11 -fsyntax-only)\n"
                f"functions_defined: {', '.join(defined) if defined else 'none'}")


def _proto_name(problem_entry: dict) -> str:
    m = re.search(r"(\w+)\s*\(", problem_entry.get("prototype", ""))
    return re.escape(m.group(1)) if m else re.escape(problem_entry.get("pid", "").lower())


def build_oracle(problem: Problem, runner: Runner | None, solution_generator=None, mode: str = "minimal",
                 rng: random.Random | None = None) -> AutoOracle:
    if runner is None:
        raise ValueError("the oracle needs a compiler runner (exec_report must come from real execution)")
    return AutoOracle(problem, runner, mode=mode, solution_generator=solution_generator, rng=rng)
