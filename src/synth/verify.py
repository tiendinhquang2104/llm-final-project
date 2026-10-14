"""Compile/run harness (synth_plan.md section "Cải tiến 3" and implementation step 1).

Compiles a submission and runs it against standard tests (stdin/stdout), edge groups and a
performance probe, with a timeout, and turns the raw outcomes into the ``SingleSignals`` /
``MultiSignals`` the labeler consumes plus the ``exec_report`` text that becomes a model input.

Execution backends mirror src/task2/compile.py: native g++ on Linux, Docker gcc on macOS. All
comparison and signal derivation is pure, so it is unit-tested with a fake runner (no compiler).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from src.synth.labeler import MultiSignals, SingleSignals

ERROR_RE = re.compile(r"^\S+:\d+:\d+: (?:fatal )?error:", re.MULTILINE)


@dataclass(frozen=True)
class TestCase:
    input: str
    expected: str
    group: str = "normal"  # normal | example | perf | edge:<name>
    timeout_s: float = 2.0
    name: str = ""

    @property
    def is_edge(self) -> bool:
        return self.group.startswith("edge")

    @property
    def is_perf(self) -> bool:
        return self.group == "perf"

    @property
    def is_example(self) -> bool:
        return self.group == "example"

    @property
    def edge_group(self) -> str:
        return self.group.split(":", 1)[1] if ":" in self.group else self.group


@dataclass
class RunOutcome:
    compiled: bool
    compile_log: str
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    duration_s: float = 0.0


@dataclass
class TestResult:
    case: TestCase
    exact: bool
    normalized: bool
    timed_out: bool
    returncode: int | None
    duration_s: float


@dataclass
class SingleRunReport:
    outcomes: list[RunOutcome]
    results: list[TestResult]
    compile_log: str
    signals: SingleSignals
    exec_report: str


@dataclass
class MultiRunReport:
    compile_log: str
    outputs: dict[str, str]
    signals: MultiSignals
    exec_report: str


def normalize(text: str) -> str:
    """Case-insensitive, whitespace-collapsed, trailing-newline-insensitive comparison key."""
    return " ".join((text or "").strip().lower().split())


def compile_error(log: str | None) -> bool:
    return bool(log) and bool(ERROR_RE.search(log))


class Runner:
    """Compile + run one program with stdin. Subclasses provide the sandbox."""

    runner_id = "base"

    def run(self, code: str, stdin: str, timeout_s: float, exam_type: str = "single_problem") -> RunOutcome:
        raise NotImplementedError


class LocalRunner(Runner):
    """Native compiler backend. Binaries are cached by source hash, so a submission is compiled
    once and then run against every test (the build runs thousands of tests)."""

    def __init__(self, cxx: str = "g++", workdir: str | None = None):
        self.cxx = cxx
        self.runner_id = "native:" + self._version()
        self.workdir = Path(tempfile.mkdtemp(prefix="synthrun", dir=workdir))
        self._bins: dict[str, tuple[bool, str, Path | None]] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()
        self._warm: set[str] = set()   # binaries that have run once (first exec can be slow)

    def _version(self) -> str:
        p = subprocess.run([self.cxx, "--version"], capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
        return (p.stdout or p.stderr).strip().splitlines()[0] if (p.stdout or p.stderr).strip() else "unknown"

    def compile(self, code: str) -> tuple[bool, str, Path | None]:
        key = hashlib.sha1(code.encode("utf-8")).hexdigest()
        if key in self._bins:
            return self._bins[key]
        with self._guard:
            lock = self._locks.setdefault(key, threading.Lock())
        with lock:
            if key in self._bins:
                return self._bins[key]
            d = self.workdir / key
            d.mkdir(parents=True, exist_ok=True)
            (d / "student.cpp").write_text(code, encoding="utf-8")
            comp = subprocess.run([self.cxx, "-std=c++11", "-w", "student.cpp", "-o", "student"],
                                  cwd=d, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL,
                                  env={**os.environ, "LC_ALL": "C"})
            log = (comp.stdout or "") + (comp.stderr or "")
            ok = comp.returncode == 0 and (d / "student").exists()
            self._bins[key] = (ok, log, d / "student" if ok else None)
        return self._bins[key]

    def run(self, code, stdin, timeout_s, exam_type="single_problem", files=None, args=None):
        ok, log, exe = self.compile(code)
        if not ok:
            return RunOutcome(False, log, 1)
        d = Path(tempfile.mkdtemp(prefix="case", dir=self.workdir))
        try:
            for name, content in (files or {}).items():
                (d / name).write_text(content, encoding="utf-8")
            # A timeout is confirmed once with a longer limit: the first exec of a fresh binary can be
            # slow (OS scan, CPU contention) and a false "infinite loop" would corrupt the label.
            key = exe.parent.name
            limits = (timeout_s,) if key in self._warm else (timeout_s, max(10.0, 4 * timeout_s))
            self._warm.add(key)
            for limit in limits:
                start = time.monotonic()
                try:
                    p = subprocess.run([str(exe), *(args or [])], cwd=d, capture_output=True, text=True,
                                       input=stdin, timeout=limit, env={**os.environ, "LC_ALL": "C"},
                                       errors="replace")
                    return RunOutcome(True, log, p.returncode, p.stdout or "", p.stderr or "", False,
                                      time.monotonic() - start)
                except subprocess.TimeoutExpired as exc:
                    timed = RunOutcome(True, log, 124, _dec(exc.stdout), _dec(exc.stderr), True, limit)
            return timed
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def close(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)


def _dec(x) -> str:
    return (x or b"").decode("utf-8", "replace") if isinstance(x, (bytes, bytearray)) else (x or "")


class CachingRunner(Runner):
    """Persistent cache in front of a real runner (SQLite, thread-safe).

    A run is keyed by (compiler id, source, stdin, data files, args, timeout); identical requests are
    answered from the cache without compiling or executing. Every synthetic build re-runs the same
    bases and mutants, so after the first build only new code is executed. Delete the cache file (or
    pass ``--no-cache``) after changing the compiler or the sandbox.
    """

    def __init__(self, inner: Runner, path: str | Path):
        import sqlite3

        self.inner = inner
        self.runner_id = f"cached:{inner.runner_id}"
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("CREATE TABLE IF NOT EXISTS runs (key TEXT PRIMARY KEY, outcome TEXT NOT NULL)")
        self._db.commit()
        self.hits = 0
        self.misses = 0

    def _key(self, code, stdin, timeout_s, files, args) -> str:
        payload = json.dumps([self.inner.runner_id, code, stdin, float(timeout_s), sorted((files or {}).items()),
                              list(args or [])], ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def run(self, code, stdin, timeout_s, exam_type="single_problem", files=None, args=None):
        key = self._key(code, stdin, timeout_s, files, args)
        with self._lock:
            row = self._db.execute("SELECT outcome FROM runs WHERE key = ?", (key,)).fetchone()
        if row is not None:
            self.hits += 1
            return RunOutcome(**json.loads(row[0]))
        self.misses += 1
        if files or args:
            out = self.inner.run(code, stdin, timeout_s, exam_type, files=files, args=args)
        else:
            out = self.inner.run(code, stdin, timeout_s, exam_type)
        # first stored outcome wins and every caller uses it: two concurrent identical requests can
        # disagree on a timeout under load, which made fresh builds non-deterministic
        with self._lock:
            self._db.execute("INSERT OR IGNORE INTO runs (key, outcome) VALUES (?, ?)",
                             (key, json.dumps(out.__dict__, ensure_ascii=False)))
            self._db.commit()
            row = self._db.execute("SELECT outcome FROM runs WHERE key = ?", (key,)).fetchone()
        return RunOutcome(**json.loads(row[0]))

    def compile(self, code: str):
        return self.inner.compile(code)

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {"cache": str(self.path), "hits": self.hits, "misses": self.misses,
                "hit_rate": round(self.hits / total, 3) if total else 0.0}

    def close(self) -> None:
        with self._lock:
            self._db.close()
        if hasattr(self.inner, "close"):
            self.inner.close()


def make_runner(backend: str = "auto", workdir: str | None = None, cache_path: str | Path | None = None) -> Runner | None:
    """Native g++ on Linux and macOS (Apple clang behind ``g++``); None when no compiler exists.

    With ``cache_path`` the runner is wrapped in a persistent :class:`CachingRunner`."""
    try:
        if backend in ("native", "auto") and shutil.which("g++"):
            runner = LocalRunner(workdir=workdir)
            return CachingRunner(runner, cache_path) if cache_path else runner
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _grade(case: TestCase, outcome: RunOutcome, strip_prefix: str = "") -> TestResult:
    if outcome.timed_out or (case.is_perf and outcome.duration_s > case.timeout_s):
        return TestResult(case, False, False, True, 124, outcome.duration_s)
    stdout = outcome.stdout
    if strip_prefix and stdout.startswith(strip_prefix):
        stdout = stdout[len(strip_prefix):]  # an input prompt is not penalised (rule S-io-prompt)
    strict = _rstrip_nl(stdout) == _rstrip_nl(case.expected)
    return TestResult(case, strict, normalize(stdout) == normalize(case.expected),
                      False, outcome.returncode, outcome.duration_s)


def _rstrip_nl(text: str) -> str:
    """Strict comparison keeps leading/interior characters, drops only trailing newlines."""
    return (text or "").replace("\r\n", "\n").rstrip("\n")


_BOOL_TOKENS = ("True", "False")
_INT_RE = re.compile(r"-?\d+")


def _kind(text: str) -> str:
    t = (text or "").strip()
    if t in _BOOL_TOKENS:
        return "bool"
    if _INT_RE.fullmatch(t):
        return "int"
    return "text"


def format_ok(result: TestResult, stdout: str) -> bool:
    """Is the answer *token* well-formed (rulebook S-io: ``TRUE`` for ``True`` is an IO error,
    a leading space is an IO error caught by the strict comparison, a wrong value is not)?"""
    if result.timed_out:
        return True
    expected_kind = _kind(result.case.expected)
    if expected_kind == "text":
        return True
    return _kind(stdout) == expected_kind


def classify_single(results: list[TestResult], compiles: bool, outputs: list[str] | None = None) -> SingleSignals:
    """Signals for the labeler. ``normal_pass_ratio`` measures logic (case/space-insensitive);
    ``token_normalized`` means "answer format is right" (S3/S9 use it); ``token_exact`` is the
    strict comparison (S5). ``core_incomplete`` = the program prints nothing on any normal test."""
    outputs = outputs if outputs is not None else [""] * len(results)
    non_perf = [(r, o) for r, o in zip(results, outputs) if not r.case.is_perf]
    normal = [(r, o) for r, o in non_perf if not r.case.is_edge and not r.case.is_example]
    examples = [r for r, _ in non_perf if r.case.is_example]
    graded = normal or non_perf
    ratio = (sum(r.normalized for r, _ in graded) / len(graded)) if graded else 1.0
    groups: dict[str, bool] = {}
    for r in results:
        if r.case.is_edge:
            groups[r.case.edge_group] = groups.get(r.case.edge_group, True) and r.normalized
    perf = [r for r in results if r.case.is_perf] + [r for r in results if r.case.is_edge and r.timed_out]
    examples_only = bool(examples) and all(r.normalized for r in examples) and ratio < 1.0
    # "does not terminate" (S2) is judged on the small normal/example inputs only; a timeout on a large
    # edge input is slowness (an edge failure + TLE), not an infinite loop
    small = [(r, o) for r, o in non_perf if not r.case.is_edge] or non_perf
    terminates = not any(r.timed_out for r, _ in small)
    silent = bool(normal) and terminates and all(not (o or "").strip() for _, o in normal)
    return SingleSignals(
        has_code=bool(results),
        compiles=compiles,
        terminates=terminates,
        core_incomplete=silent,
        examples_only_pass=examples_only,
        token_exact=all(r.exact for r, _ in non_perf) if non_perf else True,
        token_normalized=all(format_ok(r, o) for r, o in non_perf) if non_perf else True,
        normal_pass_ratio=ratio,
        edge_groups_failed=sum(1 for ok in groups.values() if not ok),
        perf_ok=all(not r.timed_out for r in perf) if perf else True,
    )


def run_single(runner: Runner, code: str, tests: list[TestCase], exam_type: str = "single_problem",
               strip_prefix: str = "") -> SingleRunReport:
    """Run one submission against all tests; returns results, inferred signals and an exec_report."""
    outcomes, results = [], []
    for case in tests:
        out = runner.run(code, case.input, case.timeout_s, exam_type)
        outcomes.append(out)
        results.append(_grade(case, out, strip_prefix))
        if not out.compiled:
            break
    log = outcomes[0].compile_log if outcomes else ""
    outputs = [(o.stdout[len(strip_prefix):] if strip_prefix and o.stdout.startswith(strip_prefix) else o.stdout)
               for o in outcomes]
    signals = classify_single(results, compiles=bool(outcomes) and outcomes[0].compiled, outputs=outputs)
    return SingleRunReport(outcomes, results, log, signals, build_exec_report(signals, results))


def build_exec_report(signals: SingleSignals, results: list[TestResult]) -> str:
    non_perf = [r for r in results if not r.case.is_perf]
    npass = sum(r.normalized for r in non_perf)
    strict = sum(r.exact for r in non_perf)
    edge = [r for r in results if r.case.is_edge]
    perf = [r for r in results if r.case.is_perf]
    lines = [
        f"compile: {'OK' if signals.compiles else 'FAIL'} (g++ -std=c++11)",
        f"run: {len(results)} test | pass {npass}/{len(non_perf)} | timeout "
        f"{sum(r.timed_out for r in results)} | strict {strict}/{len(non_perf)}",
    ]
    if edge:
        by_group: dict[str, bool] = {}
        for r in edge:
            by_group[r.case.edge_group] = by_group.get(r.case.edge_group, True) and r.normalized
        lines.append("edge_probe: " + ", ".join(f"{g}={'pass' if ok else 'FAIL'}" for g, ok in by_group.items()))
    if perf:
        lines.append(f"perf_probe: {'pass' if all(not r.timed_out for r in perf) else 'TIMEOUT'}")
    return "\n".join(lines)


def classify_multi(states: dict[str, str], compiles: bool, infinite_loop: bool, has_code: bool = True) -> MultiSignals:
    ordered = ["P1", "P2", "P3", "P4"]
    problem_states = tuple(states.get(pid, "missing") for pid in ordered if pid in states) or ("ok",)
    return MultiSignals(has_code=has_code, compiles=compiles, infinite_loop_any=infinite_loop,
                        p1_ok=problem_states[0] == "ok", problem_states=problem_states)


def build_multi_exec_report(states: dict[str, str], compile_log: str) -> str:
    compiled = "OK" if not compile_error(compile_log) else "FAIL"
    per = "  ".join(f"{pid}={st}" for pid, st in states.items())
    return f"compile: {compiled} (g++ -std=c++11)\nper_problem: {per}"
