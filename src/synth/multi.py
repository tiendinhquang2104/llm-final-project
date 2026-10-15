"""Multi-problem run harness (synth_plan.md implementation step 1, multi branch).

A multi_problem submission defines functions only (``prob1..prob4``); to exercise them the problem
bank ships a ``harness``: a C++ snippet with ``int main()`` that calls the functions and prints one
status per question, e.g. ``P1=ok P2=ok P3=partial P4=missing``. The runner concatenates submission
+ harness, runs once, and parses the statuses into ``MultiSignals`` for the labeler.

The harness is exam content (authored with the problem), so this module stays deterministic and is
unit-tested with a fake runner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.synth.labeler import MultiSignals
from src.synth.verify import Runner, build_multi_exec_report, classify_multi

STATUS_RE = re.compile(r"\bP([1-9])\s*[=:]\s*(ok|edge|partial|fail|crash|missing)\b", re.IGNORECASE)
VALID_STATES = ("ok", "edge", "partial", "fail", "crash", "missing")


@dataclass
class MultiRunReport:
    compiles: bool
    timed_out: bool
    states: dict[str, str]
    signals: MultiSignals
    exec_report: str
    compile_log: str = ""
    stdout: str = ""


def assemble(code: str, harness: str) -> str:
    """Submission functions followed by the exam harness (the harness may rely on their structs)."""
    return code.rstrip("\n") + "\n\n" + harness.strip() + "\n" if harness else code


def parse_statuses(stdout: str) -> dict[str, str]:
    """Map ``P1=ok``-style tokens to {"P1": "ok", ...}; later tokens win."""
    return {f"P{i}": state.lower() for i, state in STATUS_RE.findall(stdout or "")}


def run_multi(runner: Runner, code: str, problem, timeout_s: float = 5.0) -> MultiRunReport:
    order = [p["pid"] for p in problem.problems] or ["P1"]
    source = assemble(code, problem.harness)
    outcome = runner.run(source, "", timeout_s, "multi_problem")
    if not outcome.compiled:
        return MultiRunReport(False, False, {pid: "missing" for pid in order},
                              classify_multi({}, compiles=False, infinite_loop=False),
                              build_multi_exec_report({}, outcome.compile_log), outcome.compile_log, outcome.stdout)
    statuses = parse_statuses(outcome.stdout)
    states = {pid: statuses.get(pid, "missing") for pid in order}
    if outcome.timed_out:
        for pid in order:
            if pid not in statuses:
                states[pid] = "crash"
    signals = classify_multi(states, compiles=True, infinite_loop=outcome.timed_out)
    report = build_multi_exec_report(states, outcome.compile_log)
    return MultiRunReport(True, outcome.timed_out, states, signals, report, outcome.compile_log, outcome.stdout)


# --------------------------------------------------------------------------------------------
# Dataset harness for the shared "Rec{a,b}" multi_problem schema (prob1 reads a file of "a b"
# lines; prob2/prob3 return an int; prob4 prints). Each probK is run on 2 normal and 3 edge
# datasets and compared with the reference solution's output, which makes the per-question states
# observable: ok (all pass), edge (normal pass, an edge set fails), partial (some normal pass),
# fail (no normal pass), missing (empty body), crash (no output). Labels come from these
# observations, never from the defect that was intended.
# --------------------------------------------------------------------------------------------

import random as _random

REC_PROTOTYPES = ("prob1(string filename, int& n)", "prob2(Rec* arr, int n)", "prob3(Rec* arr, int n)",
                  "prob4(Rec* arr, int n)")
DATA_NAME = "input_data.csv"  # deliberately not the file name in the statement (hard-coding it fails)

REC_HARNESS = r'''
int main(int argc, char** argv) {
    int __n = 0;
    Rec* __a = prob1(argv[1], __n);
    std::cout << "\n@P1 " << __n;
    if (__a) for (int __i = 0; __i < __n && __i < 1000; __i++) std::cout << " " << __a[__i].a << "," << __a[__i].b;
    std::cout << std::endl;
    if (!__a || __n <= 0) return 0;
    std::cout << "\n@P2 " << prob2(__a, __n) << std::endl;
    std::cout << "\n@P3 " << prob3(__a, __n) << std::endl;
    std::cout << "\n@P4B" << std::endl;
    prob4(__a, __n);
    std::cout << "\n@P4E" << std::endl;
    return 0;
}
'''

_MARK_RE = re.compile(r"^@P([1-3]) ?(.*)$", re.MULTILINE)


def is_rec_schema(problem) -> bool:
    protos = " ".join(p.get("prototype", "") for p in problem.problems)
    return problem.exam_type == "multi_problem" and all(p.split("(")[0] in protos for p in REC_PROTOTYPES) \
        and "Rec*" in protos


def rec_datasets(exam_id: str) -> dict[str, str]:
    """Deterministic datasets per exam: normal1/normal2 (extremes in the middle), edge sets."""
    rng = _random.Random(f"rec-datasets:{exam_id}")

    def rows(k, lo, hi):
        return [(rng.randint(lo, hi), rng.randint(lo, hi)) for _ in range(k)]

    def middle_extremes(rs):
        rs = sorted(rs, key=lambda r: r[0])
        mid = [rs[-1], rs[0]]  # max a and min a go to the middle
        rest = rs[1:-1]
        return rest[: len(rest) // 2] + mid + rest[len(rest) // 2:]

    normal1 = middle_extremes(rows(7, 1, 40))
    normal2 = middle_extremes(rows(6, 1, 40))
    ends = sorted(rows(6, 1, 40), key=lambda r: -r[0])  # max a first, min a last
    ends[0], ends[-1] = (ends[0][0], min(r[1] for r in ends) - 1), (ends[-1][0], max(r[1] for r in ends) + 1)
    single = rows(1, 1, 40)
    negative = rows(5, -40, -1)
    fmt = lambda rs: "".join(f"{a} {b}\n" for a, b in rs)
    return {"normal1": fmt(normal1), "normal2": fmt(normal2),
            "edge:ends": fmt(ends), "edge:single": fmt(single), "edge:negative": fmt(negative)}


def parse_rec_output(stdout: str) -> dict[str, str]:
    out = {f"P{k}": v.strip() for k, v in _MARK_RE.findall(stdout or "")}
    if "@P4B" in (stdout or "") and "@P4E" in stdout:
        body = stdout.split("@P4B", 1)[1].split("@P4E", 1)[0]
        out["P4"] = " ".join(body.split())
    return out


def _function_body(code: str, name: str) -> str | None:
    m = re.search(rf"\b{name}\s*\([^)]*\)\s*\{{", code)
    if not m:
        return None
    depth, i = 1, m.end()
    while i < len(code) and depth:
        depth += (code[i] == "{") - (code[i] == "}")
        i += 1
    return code[m.end():i - 1]


def _is_missing(code: str, pid: str) -> bool:
    body = _function_body(code, f"prob{pid[1:]}")
    if body is None:
        return True
    stripped = re.sub(r"//[^\n]*|/\*.*?\*/|\s", "", body, flags=re.S)
    return stripped in ("", "return0;", "return;", "returnnullptr;", "returnNULL;")


@dataclass
class RecRunReport:
    compiles: bool
    timed_out: bool
    states: dict[str, str]
    signals: MultiSignals
    compile_log: str
    per_dataset: dict[str, dict[str, bool]]


def run_multi_datasets(runner, code: str, problem, reference_outputs: dict[str, dict[str, str]] | None = None,
                       timeout_s: float = 3.0) -> RecRunReport:
    """Run the Rec-schema harness on every dataset and derive per-question states."""
    pids = ["P1", "P2", "P3", "P4"]
    datasets = rec_datasets(problem.exam_id)
    if reference_outputs is None:
        reference_outputs = reference_rec_outputs(runner, problem)
    source = code.rstrip("\n") + "\n" + REC_HARNESS
    results: dict[str, dict[str, bool]] = {}
    timed_out = False
    compile_log = ""
    for name, content in datasets.items():
        out = runner.run(source, "", timeout_s, "multi_problem", files={DATA_NAME: content}, args=[DATA_NAME])
        compile_log = out.compile_log
        if not out.compiled:
            states = {pid: "missing" for pid in pids}
            return RecRunReport(False, False, states, classify_multi({}, compiles=False, infinite_loop=False),
                                compile_log, {})
        if out.timed_out:
            timed_out = True
        got = parse_rec_output(out.stdout)
        exp = reference_outputs[name]
        results[name] = {pid: (pid in got and got[pid] == exp.get(pid)) for pid in pids}
        for pid in pids:
            if pid not in got:
                results[name][pid + ":crash"] = True
    states = {}
    normal = [n for n in datasets if n.startswith("normal")]
    edge = [n for n in datasets if n.startswith("edge")]
    for pid in pids:
        if pid != "P1" and _is_missing(code, pid):
            states[pid] = "missing"
            continue
        n_ok = sum(results[n][pid] for n in normal)
        e_ok = all(results[n][pid] for n in edge)
        crashed = all(results[n].get(pid + ":crash") for n in normal)
        if n_ok == len(normal) and e_ok:
            states[pid] = "ok"
        elif n_ok == len(normal):
            states[pid] = "edge"
        elif crashed:
            states[pid] = "crash"
        elif n_ok > 0:
            states[pid] = "partial"
        else:
            states[pid] = "fail"
    signals = classify_multi(states, compiles=True, infinite_loop=timed_out)
    return RecRunReport(True, timed_out, states, signals, compile_log, results)


_REF_CACHE: dict[str, dict[str, dict[str, str]]] = {}


def reference_rec_outputs(runner, problem) -> dict[str, dict[str, str]]:
    """Expected per-dataset outputs = the reference solution's outputs (must cover every pid)."""
    if problem.exam_id in _REF_CACHE:
        return _REF_CACHE[problem.exam_id]
    source = problem.reference.rstrip("\n") + "\n" + REC_HARNESS
    outputs = {}
    for name, content in rec_datasets(problem.exam_id).items():
        out = runner.run(source, "", 5.0, "multi_problem", files={DATA_NAME: content}, args=[DATA_NAME])
        if not out.compiled or out.timed_out:
            raise ValueError(f"{problem.exam_id}: reference fails on dataset {name}: {out.compile_log[:300]}")
        got = parse_rec_output(out.stdout)
        if set(got) != {"P1", "P2", "P3", "P4"}:
            raise ValueError(f"{problem.exam_id}: reference output incomplete on {name}: {got}")
        outputs[name] = got
    _REF_CACHE[problem.exam_id] = outputs
    return outputs
