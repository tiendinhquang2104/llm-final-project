"""Execution oracle for Task 2: run every submission on the test suite of its exam (src/task2/test_gen.py).

The suites are generated at inference by the pipeline's local LLM from what each exam gives (statement,
constraints, prototypes, data file); nothing in this module or in test_gen.py is written for a particular exam, and
no label of a test sample is ever read.

- single_problem (stdin/stdout): one run per test, each gets a compare_output status (pass / whitespace / case /
  fail, or timeout / runtime_error).
- multi_problem (functions only): the submission is compiled with the suite's driver (the student's own main, if
  any, is renamed; a function the file does not define gets an empty stub); one run per case, so each problem is
  judged on its own. A problem whose body is empty is "missing". Cases of the first problem also run on resized
  copies of the data file.

Results are signals (per-test statuses, per-problem states, a few static code checks), turned into labels by
src/task2/exec_rules.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from src.task2.compile import RUN_TIMEOUT, compare_output, has_compile_error
from src.task2.prompts_cot import ALL_COMMENTED, strip_comments
from src.task2.test_gen import Suite, assemble, func_name, multi_header, prototypes


SEGFAULT = (139, -11)  # 128 + SIGSEGV from the Docker shell, -SIGSEGV from subprocess


# ---------------------------------------------------------------------------------------------- code analysis

def function_bodies(code: str, protos: dict[str, str]) -> dict[str, str]:
    """pid -> body text (comments removed) of the exam functions the code defines; absent functions have no key."""
    src = strip_comments(code)
    out = {}
    for pid, proto in protos.items():
        name = func_name(proto)
        m = name and re.search(rf"\b{re.escape(name)}\s*\([^;{{]*\)\s*\{{", src)
        if not m:
            continue
        depth, i = 1, m.end()
        while i < len(src) and depth:
            depth += {"{": 1, "}": -1}.get(src[i], 0)
            i += 1
        out[pid] = src[m.end():i - 1]
    return out


_TRIVIAL_RETURN = re.compile(r"^\s*(return\s*(NULL|nullptr|0|-1|false|true|\{\s*\}|\w+\s*\(\s*\)|\w+)?\s*;\s*)?$",
                             re.S)


def is_missing(body: str | None) -> bool:
    """Empty body, or only a trivial return / declaration of the result (the statements ask to leave the body of an
    unsolved function empty)."""
    if body is None:
        return True
    stmts = [s.strip() for s in body.split(";") if s.strip()]
    if not stmts:
        return True
    if len(stmts) == 1 and _TRIVIAL_RETURN.match(stmts[0] + ";"):
        return True
    if len(stmts) == 2 and re.match(r"^[\w<>:\*\s&]+\s+\w+(\s*=\s*[^;]+)?$", stmts[0]) and stmts[1].startswith("return"):
        return True
    return False


def hardcode_size(body: str, structs: list[str]) -> bool:
    """The file read sized by a constant: an array of an exam struct with a literal length, or `n = <2+ digits>;`."""
    alt = "|".join(re.escape(s) for s in structs)
    pats = [r"\bn\s*=\s*\d{2,}\s*;"]
    if alt:
        pats += [rf"new\s+({alt})\s*\[\s*\d+\s*\]", rf"\b({alt})\s+\w+\s*\[\s*\d+\s*\]"]
    return any(re.search(p, body) for p in pats)


def hardcode_file(body: str, data_file: str | None) -> bool:
    """A fixed file name instead of the `filename` parameter: a string literal naming a .csv / the data file."""
    names = [r"\.csv", r"filename"] + ([re.escape(Path(data_file).stem)] if data_file else [])
    return bool(re.search(rf"\"[^\"]*({'|'.join(names)})[^\"]*\"", body, re.I))


@dataclass
class ExecResult:
    sample_id: str
    kind: str | None                        # exam_type when the exam has a suite, else None
    compiles: bool
    all_commented: bool
    harness_ok: bool = True                 # multi: the driver built with the submission
    statuses: dict = field(default_factory=dict)   # test id -> status
    groups: dict = field(default_factory=dict)     # test id -> group (single) / pid (multi)
    states: dict = field(default_factory=dict)     # multi: pid -> ok/partial/fail/crash/timeout/missing
    prereq: dict = field(default_factory=dict)     # multi: pid -> pids it is a prerequisite for
    hardcode_size: bool = False
    hardcode_file: bool = False
    uses_stoi: bool = False
    p1_variant_fail: bool = False           # multi: first problem right on the exam file, wrong on a resized copy
    all_segfault: bool = False              # every run died of a memory fault (SIGSEGV): an index / pointer error
    probe: bool = False                     # multi, probe suite: "ok" of the first problem = right record count;
                                            # later problems are only "ran" / crash / timeout / missing

    def to_json(self) -> dict:
        return self.__dict__


def _multi_status(actual: str, test: dict, rc: int | None, timeout: bool) -> str:
    if timeout:
        return "timeout"
    if rc:
        return "crash"
    if "rows" in test:  # probe: the driver prints the record count first
        got = (actual.split("\n", 1) + [""])[1].split()
        return "pass" if got and got[0] == str(test["rows"]) else "fail"
    if test.get("expected") is None:
        return "ran"
    return "pass" if multi_header(actual) == multi_header(test["expected"]) else "fail"


def _problem_states(statuses: dict, groups: dict, missing: dict, pids: list[str]) -> tuple[dict, bool]:
    states = {}
    for pid in pids:
        st = [v for k, v in statuses.items() if groups.get(k) == pid]
        if missing.get(pid) or not st:
            states[pid] = "missing"
        elif all(s == "pass" for s in st):
            states[pid] = "ok"
        elif all(s == "ran" for s in st):
            states[pid] = "ran"
        elif "timeout" in st:
            states[pid] = "timeout"
        elif any(s == "pass" for s in st):
            states[pid] = "partial"
        elif "crash" in st:
            states[pid] = "crash"
        else:
            states[pid] = "fail"
    first = pids[0] if pids else None
    base = statuses.get(f"{first}A")
    variant_fail = bool(first) and base == "pass" and states.get(first) != "ok"
    return states, variant_fail


class Oracle:
    """Runs submissions with a Task 2 compiler (src/task2/compile.py) and caches the results on disk."""

    def __init__(self, compiler, cache_dir="outputs/task2/_exec_cache"):
        self.compiler = compiler
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)

    def _key(self, code: str, tests: list[str]) -> str:
        blob = json.dumps([self.compiler.compiler_id, code, tests, RUN_TIMEOUT])
        return hashlib.sha256(blob.encode()).hexdigest()[:32]

    @staticmethod
    def _jobs(sample, suite: Suite, exam: dict):
        stdin = [t["stdin"] for t in suite.tests]
        if suite.exam_type != "multi_problem":
            return sample.code, stdin
        return assemble(sample.code, suite, prototypes(exam)), stdin

    def run(self, samples, exams: dict, suites: dict[str, Suite | None]) -> dict[str, ExecResult]:
        results, todo = {}, []
        for s in samples:
            suite = suites.get(s.exam_id)
            commented = strip_comments(s.code) == ALL_COMMENTED
            r = ExecResult(s.sample_id, suite.exam_type if suite else None,
                           compiles=not has_compile_error(s.compile_log), all_commented=commented)
            results[s.sample_id] = r
            if suite is None or not suite.tests or not r.compiles or commented:
                continue
            code, stdin = self._jobs(s, suite, exams[s.exam_id])
            todo.append((s, suite, code, stdin, self._key(code, stdin)))
        fresh = [t for t in todo if not (self.cache / f"{t[4]}.json").exists()]
        if fresh:
            print(f"[exec] running {len(fresh)} submissions ({sum(len(t[3]) for t in fresh)} runs)", flush=True)
            for i in range(0, len(fresh), 40):
                chunk = fresh[i:i + 40]
                outs = self.compiler.run([(t[2], "single_problem", t[3]) for t in chunk])
                for t, (log, rc, runs) in zip(chunk, outs):
                    row = {"log": log[-2000:], "rc": rc, "runs": runs}
                    (self.cache / f"{t[4]}.json").write_text(json.dumps(row), encoding="utf-8")
        for s, suite, code, stdin, key in todo:
            row = json.loads((self.cache / f"{key}.json").read_text(encoding="utf-8"))
            self._fill(results[s.sample_id], s, suite, exams[s.exam_id], row)
        return results

    @staticmethod
    def _fill(r: ExecResult, s, suite: Suite, exam: dict, row: dict) -> None:
        runs = row.get("runs")
        src = strip_comments(s.code)
        r.uses_stoi = bool(re.search(r"\bsto(i|f|d|l|ll)\s*\(|\batoi\s*\(|\batof\s*\(", src))
        multi = suite.exam_type == "multi_problem"
        protos = prototypes(exam) if multi else {}
        bodies = function_bodies(s.code, protos) if multi else {}
        if multi and suite.pids:
            first = bodies.get(suite.pids[0], "")
            r.hardcode_size = hardcode_size(first, suite.struct_names)
            r.hardcode_file = hardcode_file(first, exam.get("data_file"))
            r.prereq = dict(suite.prereq)
            r.probe = suite.probe
        if runs is None:  # the driver (or the program) did not build: unknown, not the student's fault here
            r.harness_ok = False
            return
        r.all_segfault = bool(runs) and all(run.get("returncode") in SEGFAULT and not run.get("timeout") for run in runs)
        if not multi:
            for t, run in zip(suite.tests, runs):
                if run.get("timeout"):
                    st = "timeout"
                elif run.get("returncode"):
                    st = "runtime_error"
                else:
                    st = compare_output(run.get("actual", ""), t["expected"])
                r.statuses[t["id"]], r.groups[t["id"]] = st, t["group"]
            return
        for t, run in zip(suite.tests, runs):
            r.statuses[t["id"]] = _multi_status(run.get("actual", ""), t, run.get("returncode"), run.get("timeout"))
            r.groups[t["id"]] = t["pid"]
        missing = {pid: is_missing(bodies.get(pid)) for pid in suite.pids}
        r.states, r.p1_variant_fail = _problem_states(r.statuses, r.groups, missing, suite.pids)


def distrust_suites(results: dict[str, ExecResult], samples, min_runs: int = 5) -> list[str]:
    """Multi-problem exams whose suite no submission passes on the prerequisite problem, among at least `min_runs`
    submissions that ran: the generated references then most likely share a misreading of the statement, and a
    wrong suite would judge every submission wrong. Their results lose the execution signal (kind=None), so the
    labels fall back to the model. Uses run outcomes only, never a label."""
    by_exam: dict[str, list[ExecResult]] = {}
    for s in samples:
        r = results[s.sample_id]
        if r.states and r.harness_ok:
            by_exam.setdefault(s.exam_id, []).append(r)
    bad = []
    for eid, rs in by_exam.items():
        pre = [next((p for p in r.states if r.prereq.get(p)), next(iter(r.states))) for r in rs]
        ran = [(r, p) for r, p in zip(rs, pre) if r.states[p] != "missing"]
        if len(ran) >= min_runs and not any(r.states[p] == "ok" for r, p in ran):
            bad.append(eid)
            for r in rs:
                r.kind = None
    return bad


def run_with_probe_fallback(oracle: "Oracle", samples, exams: dict, suites: dict) -> tuple[dict, list[str]]:
    """oracle.run, then the multi-problem exams whose suite is not trusted (distrust_suites) are judged again on the
    probe version of their suite (Suite.as_probe: record counts, crashes, endless runs); the runs are cached, so
    nothing is executed twice. Returns the results and the exams that fell back."""
    res = oracle.run(samples, exams, suites)
    bad = distrust_suites(res, samples)
    if bad:
        probe = {e: suites[e].as_probe() for e in bad if suites.get(e) is not None and not suites[e].probe}
        again = [s for s in samples if s.exam_id in probe]
        if again:
            res.update(oracle.run(again, exams, probe))
    return res, bad


def write_results(results: dict[str, ExecResult], path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in results.values():
            f.write(json.dumps(r.to_json(), ensure_ascii=False) + "\n")


def env_compiler(ccfg: dict):
    from src.task2.compile import make_compiler
    return make_compiler(ccfg.get("backend", "auto"), ccfg.get("image", "gcc:13.3.0"),
                         os.path.join(ccfg.get("workdir", "outputs/task2/_compile_work") + "_exec"))
