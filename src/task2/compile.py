"""Self-compiled compile_log for Task 2 (instructor allowed teams to compile submissions themselves).

Reproduces the organizer's recipe from exams.json notes: single_problem -> `g++ -std=c++11` (compile + link),
multi_problem -> `g++ -std=c++11 -fsyntax-only`, file `student.cpp` alone in `mktemp -d /tmp/tmpXXXXXXXX`.
No global g++ install: macOS runs GCC in Docker (`gcc:13.3.0`, --network none); Linux (Kaggle) uses the g++ on PATH.
Logs are features, not labels.

With `compile.run_examples` a single_problem binary that compiled is also run, in the same job, on the input/output
examples of the statement (src/task2/examples.py): RUN_TIMEOUT seconds, 512 MB of memory and 1 MB of output each.
The runs become the sample's test_report (see run_report), a feature the model reads like compile_log.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from dataclasses import replace
from pathlib import Path

# any compiler diagnostic "file:line:col: error:" (student.cpp or a header it pulls in); the linker's
# "/usr/bin/ld: ..." / "collect2: error" / "undefined reference" lines have no line:col so they never match
_ERROR = re.compile(r"^\S+:\d+:\d+: (?:fatal )?error:", re.MULTILINE)
RUN_TIMEOUT = 2          # seconds per example
RUN_MEMORY_MB = 512
RUN_OUTPUT_KB = 1024     # a program printing in a loop is cut (SIGXFSZ) instead of filling the disk
MAX_ACTUAL_CHARS = 2000  # stdout kept per run


def compile_args(exam_type: str) -> list[str]:
    if exam_type == "multi_problem":
        return ["g++", "-std=c++11", "-fsyntax-only", "student.cpp"]
    return ["g++", "-std=c++11", "student.cpp", "-o", "student"]


def has_compile_error(log: str | None) -> bool:
    """A compiler error (in student.cpp or an included header); link-only errors such as a missing main do not count."""
    return bool(log) and bool(_ERROR.search(log))


def _first_line(cmd: list[str]) -> str:
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
    if out.returncode != 0:
        lines = (out.stderr or "").strip().splitlines()
        raise RuntimeError(f"{' '.join(cmd[:2])} failed (rc={out.returncode}): {lines[0] if lines else 'no stderr'}")
    return (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr).strip() else "unknown"


def _limit_child():  # preexec_fn of a student program: memory, output size, CPU time (each where the OS allows it;
    import resource   # macOS refuses RLIMIT_AS, Linux/Kaggle applies all three)
    for lim, val in ((resource.RLIMIT_AS, RUN_MEMORY_MB << 20), (resource.RLIMIT_FSIZE, RUN_OUTPUT_KB << 10),
                     (resource.RLIMIT_CPU, RUN_TIMEOUT + 1)):
        try:
            resource.setrlimit(lim, (val, val))
        except (ValueError, OSError):
            pass


def _read_out(path: Path) -> str:
    with path.open("rb") as f:
        return f.read(MAX_ACTUAL_CHARS * 4).decode("utf-8", "replace")[:MAX_ACTUAL_CHARS]


class NativeCompiler:
    def __init__(self, cxx: str = "g++", timeout: int = 30):
        self.cxx, self.timeout = cxx, timeout
        self.compiler_id = "native:" + _first_line([cxx, "--version"])

    def _run_tests(self, d: Path, tests: list) -> list[dict]:
        runs = []
        for i, inp in enumerate(tests):
            out = d / f"out_{i}"
            with out.open("wb") as fo:
                try:
                    p = subprocess.run(["./student"], cwd=d, input=inp.encode("utf-8"), stdout=fo,
                                       stderr=subprocess.DEVNULL, timeout=RUN_TIMEOUT, preexec_fn=_limit_child)
                    rc, timed_out = p.returncode, False
                except subprocess.TimeoutExpired:
                    rc, timed_out = 124, True
            runs.append({"actual": _read_out(out), "returncode": rc, "timeout": timed_out})
        return runs

    def run(self, jobs):
        """jobs: (code, exam_type) or (code, exam_type, test_inputs); returns (log, rc) or (log, rc, runs)."""
        results = []
        for job in jobs:
            code, exam_type, tests = job[0], job[1], (job[2] if len(job) > 2 else None)
            d = Path(tempfile.mkdtemp(prefix="tmp", dir="/tmp"))
            try:
                (d / "student.cpp").write_text(code, encoding="utf-8")
                args = [self.cxx, *compile_args(exam_type)[1:]]
                try:
                    p = subprocess.run(args, cwd=d, capture_output=True, timeout=self.timeout,
                                       stdin=subprocess.DEVNULL,
                                       env={**os.environ, "LC_ALL": "C"})
                    log, rc = ((p.stdout or b"").decode("utf-8", "replace")
                               + (p.stderr or b"").decode("utf-8", "replace"), p.returncode)
                except subprocess.TimeoutExpired:
                    log, rc = f"compile timeout after {self.timeout}s", 124
                if tests is None:
                    results.append((log, rc))
                else:
                    ok = rc == 0 and (d / "student").exists()
                    results.append((log, rc, self._run_tests(d, tests) if ok else None))
            finally:
                shutil.rmtree(d, ignore_errors=True)
        return results


_DOCKER_SCRIPT = """#!/bin/bash
# one job per directory: /work/jobs/<i>/{student.cpp,args[,tests/in_<k>]}; writes log + rc next to them, and
# tests/out_<k> + tests/rc_<k> when the program compiled and the job has tests
for job in /work/jobs/*/; do
  d=$(mktemp -d /tmp/tmpXXXXXXXX)
  cp "$job/student.cpp" "$d/student.cpp"
  (cd "$d" && timeout {timeout} $(cat "$job/args") > "$job/log" 2>&1; echo $? > "$job/rc")
  if [ -d "$job/tests" ] && [ "$(cat "$job/rc")" = "0" ] && [ -x "$d/student" ]; then
    for inp in "$job"/tests/in_*; do
      k=${inp##*/in_}
      (cd "$d" && ulimit -v {mem_kb} -f {out_blocks} && timeout {run_timeout} ./student < "$inp" > "$job/tests/out_$k" 2> /dev/null; echo $? > "$job/tests/rc_$k")
    done
  fi
  rm -rf "$d"
done
"""


class DockerCompiler:
    def __init__(self, image: str = "gcc:13.3.0", workdir="outputs/task2/_compile_work", timeout: int = 30):
        self.image, self.timeout = image, timeout
        self.workdir = Path(workdir).resolve()
        self.compiler_id = f"docker:{image}:" + _first_line(["docker", "run", "--rm", image, "g++", "--version"])

    def run(self, jobs):
        if not jobs:
            return []
        shutil.rmtree(self.workdir, ignore_errors=True)
        (self.workdir / "jobs").mkdir(parents=True)
        for i, job in enumerate(jobs):
            code, exam_type, tests = job[0], job[1], (job[2] if len(job) > 2 else None)
            j = self.workdir / "jobs" / f"{i:06d}"
            j.mkdir()
            (j / "student.cpp").write_text(code, encoding="utf-8")
            (j / "args").write_text(" ".join(compile_args(exam_type)), encoding="utf-8")
            if tests is not None:
                (j / "tests").mkdir()
                for k, inp in enumerate(tests):
                    (j / "tests" / f"in_{k:03d}").write_text(inp, encoding="utf-8")
        script = (_DOCKER_SCRIPT.replace("{timeout}", str(self.timeout)).replace("{run_timeout}", str(RUN_TIMEOUT))
                  .replace("{mem_kb}", str(RUN_MEMORY_MB << 10)).replace("{out_blocks}", str(RUN_OUTPUT_KB)))
        (self.workdir / "run.sh").write_text(script, encoding="utf-8")
        subprocess.run(["docker", "run", "--rm", "--network", "none", "--memory", "1g", "--pids-limit", "256", "-v", f"{self.workdir}:/work", self.image,
                        "bash", "/work/run.sh"], check=True, capture_output=True, text=True)
        out = []
        for i, job in enumerate(jobs):
            j = self.workdir / "jobs" / f"{i:06d}"
            log = (j / "log").read_text(encoding="utf-8", errors="replace")
            rc = int((j / "rc").read_text().strip() or 1)
            if len(job) <= 2 or job[2] is None:
                out.append((log, rc))
                continue
            runs = None
            if (j / "tests" / "rc_000").exists():
                runs = []
                for k in range(len(job[2])):
                    rck = int((j / "tests" / f"rc_{k:03d}").read_text().strip() or 1)
                    o = j / "tests" / f"out_{k:03d}"
                    runs.append({"actual": _read_out(o) if o.exists() else "", "returncode": rck,
                                 "timeout": rck == 124})
            out.append((log, rc, runs))
        shutil.rmtree(self.workdir, ignore_errors=True)
        return out


def make_compiler(backend: str = "auto", image: str = "gcc:13.3.0", workdir="outputs/task2/_compile_work"):
    """Native g++ on Linux, Docker GCC on macOS; None (with a warning) when neither is usable."""
    system = platform.system()
    try:
        if system == "Darwin" and backend == "native":
            print("[compile] native backend refused on macOS (/usr/bin/g++ is Apple clang); trying Docker")
            backend = "docker"
        if backend == "native" or (backend == "auto" and system == "Linux" and shutil.which("g++")):
            return NativeCompiler()
        if backend == "docker" or (backend == "auto" and shutil.which("docker")):
            subprocess.run(["docker", "info"], check=True, capture_output=True, timeout=30)
            return DockerCompiler(image, workdir)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"[compile] backend unavailable: {exc!r}")
    print("[compile] WARNING: no compiler available — compile_log will be empty")
    return None


class CompileCache:
    """One cached result per (compiler, recipe, code[, example inputs]): {"log", "returncode"[, "runs"]}. Jobs without
    examples keep the compile-only key, so existing caches stay valid."""

    def __init__(self, compiler, cache_dir):
        self.compiler = compiler
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, code: str, exam_type: str, tests: list | None = None) -> str:
        parts = [self.compiler.compiler_id, compile_args(exam_type), code]
        if tests:
            parts += [{"run": tests, "timeout": RUN_TIMEOUT, "mem_mb": RUN_MEMORY_MB, "out_kb": RUN_OUTPUT_KB}]
        return hashlib.sha256(json.dumps(parts).encode()).hexdigest()[:32]

    def results(self, samples, tests_by_id: dict | None = None) -> dict[str, dict]:
        """sample_id -> {"log", "returncode", "runs"}; runs is None without examples or when the program did not
        compile."""
        tests_by_id = tests_by_id or {}
        tests = {s.sample_id: (tests_by_id.get(s.sample_id) or None) for s in samples}
        keys = {s.sample_id: self._key(s.code, s.exam_type, tests[s.sample_id]) for s in samples}
        todo: dict[str, tuple] = {}
        fresh: dict[str, dict] = {}  # results not on disk (timeouts), still returned to the caller
        for s in samples:
            if not (self.cache_dir / f"{keys[s.sample_id]}.json").exists():
                t = tests[s.sample_id]
                todo.setdefault(keys[s.sample_id], (s.code, s.exam_type) if t is None else (s.code, s.exam_type, t))
        if todo:
            n_run = sum(len(j) > 2 for j in todo.values())
            print(f"[compile] {self.compiler.compiler_id}: compiling {len(todo)} submissions"
                  + (f" ({n_run} also run on the statement examples)" if n_run else ""), flush=True)
            for key, res in zip(todo, self.compiler.run(list(todo.values()))):
                log, rc = res[0], res[1]
                row = {"log": log, "returncode": rc, **({"runs": res[2]} if len(res) > 2 else {})}
                fresh[key] = row
                if rc == 124:  # timeout: not a property of the code alone, retry next run
                    continue
                path = self.cache_dir / f"{key}.json"
                tmp = path.with_suffix(f".{os.getpid()}.tmp")
                tmp.write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
                os.replace(tmp, path)
        out = {}
        for sid, k in keys.items():
            row = fresh[k] if k in fresh else json.loads((self.cache_dir / f"{k}.json").read_text(encoding="utf-8"))
            out[sid] = {"log": row["log"], "returncode": row.get("returncode"), "runs": row.get("runs")}
        return out

    def logs(self, samples) -> dict[str, str]:
        return {sid: r["log"] for sid, r in self.results(samples).items()}


def _lines(text: str) -> list[str]:
    lines = [ln.rstrip() for ln in (text or "").replace("\r\n", "\n").split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return lines


def compare_output(actual: str, expected: str) -> str:
    """pass: same lines (trailing spaces / final newline ignored, as online judges do); prompt_then_pass: right
    output after an input prompt ("Nhap n: True"); whitespace: same tokens, other spacing or line breaks; case: same
    tokens up to letter case; fail: anything else."""
    a, e = _lines(actual), _lines(expected)
    if a == e:
        return "pass"
    ja, je = " ".join(a), " ".join(e)
    if je and ja.endswith(je) and ja != je and ja[:-len(je)].rstrip().endswith((":", "?", ">")):
        return "prompt_then_pass"
    ta, te = ja.split(), je.split()
    if ta == te:
        return "whitespace"
    if [t.lower() for t in ta] == [t.lower() for t in te]:
        return "case"
    return "fail"


def run_report(examples: list[dict], runs: list[dict] | None) -> list[dict] | None:
    """test_report rows {"input", "expected", "actual", "passed", "status"}; status one of compare_output's, or
    "timeout" / "runtime_error" (non-zero exit, e.g. a crash). None when the program was not run."""
    if not examples or runs is None:
        return None
    rows = []
    for ex, r in zip(examples, runs):
        if r.get("timeout"):
            status = "timeout"
        elif r.get("returncode"):
            status = "runtime_error"
        else:
            status = compare_output(r.get("actual", ""), ex["expected"])
        rows.append({"input": ex["input"], "expected": ex["expected"], "actual": r.get("actual", ""),
                     "returncode": r.get("returncode"), "status": status, "passed": status == "pass"})
    return rows


def with_compile_logs(samples, logs: dict) -> list:
    """Every sample gets the self-compiled log (or None) — organizer logs are never mixed in."""
    return [replace(s, compile_log=logs.get(s.sample_id)) for s in samples]


def attach_compile_logs(compile_cfg: dict | None, sample_lists: list[list], enabled: bool = True,
                        root=None, source: str = "self", exams: dict | None = None) -> tuple[list[list], str | None]:
    """Attach compile logs to every sample of every list and return (new lists, compiler_id).

    source="self": organizer logs are never kept; every sample is compiled in one batch (None without compiler).
    source="dataset": samples whose compile_log is not None (incl. "" = clean) keep it; only samples with None
    (e.g. bug-injection mutants) are compiled. compiler_id is then the compiler used, else "dataset".
    With `enabled` False (--no-compile / config off) every compile_log is None. test_report is cleared too
    (the public release has none, so gold must not show it), unless compile.run_examples is on and `exams` is
    given: then a stdin/stdout submission that compiles gets the report of its runs on the statement examples
    (the same for gold, silver and public, since all come from the statement)."""
    if source not in ("self", "dataset"):
        raise ValueError(f"unknown compile source {source!r} (expected 'self' or 'dataset')")
    cfg = compile_cfg or {}
    root = Path(root) if root else Path(".")
    on = enabled and cfg.get("enabled", True)
    run_on = on and bool(cfg.get("run_examples")) and exams is not None
    examples = {}
    if run_on:
        from src.task2.examples import statement_examples
        examples = {s.sample_id: statement_examples(exams[s.exam_id])
                    for lst in sample_lists for s in lst if s.exam_id in exams}
        examples = {k: v for k, v in examples.items() if v}
    keep = on and source == "dataset"
    todo = [s for lst in sample_lists for s in lst
            if not (keep and s.compile_log is not None) or s.sample_id in examples]
    comp = None
    if on and todo:
        comp = make_compiler(cfg.get("backend", "auto"), cfg.get("image", "gcc:13.3.0"),
                             root / cfg.get("workdir", "outputs/task2/_compile_work"))
    res: dict = {}
    if comp is not None:
        res = CompileCache(comp, root / cfg.get("cache_dir", "outputs/task2/_compile_cache")).results(
            todo, {sid: [e["input"] for e in ex] for sid, ex in examples.items()})
    out = []
    for lst in sample_lists:
        new = []
        for s in lst:
            r = res.get(s.sample_id) or {}
            report = run_report(examples.get(s.sample_id) or [], r.get("runs"))
            if keep and s.compile_log is not None:
                new.append(replace(s, test_report=report))
            else:
                new.append(replace(s, compile_log=r.get("log"), test_report=report))
        out.append(new)
    if comp is not None:
        cid = comp.compiler_id
    else:
        cid = "dataset" if keep else None
    if keep and comp is None and todo:
        print(f"[compile] WARNING: {len(todo)} samples without a dataset log and no compiler: compile_log=None")
    if run_on and examples:
        n = sum(s.test_report is not None for lst in out for s in lst)
        print(f"[run] {n}/{len(examples)} stdin/stdout submissions ran on the statement examples", flush=True)
    return out, cid
