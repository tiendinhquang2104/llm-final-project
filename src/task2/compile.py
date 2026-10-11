"""Self-compiled compile_log for Task 2 (instructor allowed teams to compile submissions themselves).

Reproduces the organizer's recipe from exams.json notes: single_problem -> `g++ -std=c++11` (compile + link),
multi_problem -> `g++ -std=c++11 -fsyntax-only`, file `student.cpp` alone in `mktemp -d /tmp/tmpXXXXXXXX`.
Code is only compiled, never executed. No global g++ install: macOS runs GCC in Docker (`gcc:13.3.0`,
--network none); Linux (Kaggle) uses the g++ on PATH. Logs are features, not labels.
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


def compile_args(exam_type: str) -> list[str]:
    if exam_type == "multi_problem":
        return ["g++", "-std=c++11", "-fsyntax-only", "student.cpp"]
    return ["g++", "-std=c++11", "student.cpp", "-o", "student"]


def has_compile_error(log: str | None) -> bool:
    """A compiler error (in student.cpp or an included header); link-only errors such as a missing main do not count."""
    return bool(log) and bool(_ERROR.search(log))


def _first_line(cmd: list[str]) -> str:
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr).strip() else "unknown"


class NativeCompiler:
    def __init__(self, cxx: str = "g++", timeout: int = 30):
        self.cxx, self.timeout = cxx, timeout
        self.compiler_id = "native:" + _first_line([cxx, "--version"])

    def run(self, jobs):
        results = []
        for code, exam_type in jobs:
            d = Path(tempfile.mkdtemp(prefix="tmp", dir="/tmp"))
            try:
                (d / "student.cpp").write_text(code, encoding="utf-8")
                args = [self.cxx, *compile_args(exam_type)[1:]]
                try:
                    p = subprocess.run(args, cwd=d, capture_output=True, timeout=self.timeout,
                                       env={**os.environ, "LC_ALL": "C"})
                    results.append(((p.stdout or b"").decode("utf-8", "replace")
                                    + (p.stderr or b"").decode("utf-8", "replace"), p.returncode))
                except subprocess.TimeoutExpired:
                    results.append((f"compile timeout after {self.timeout}s", 124))
            finally:
                shutil.rmtree(d, ignore_errors=True)
        return results


_DOCKER_SCRIPT = """#!/bin/bash
# one job per directory: /work/jobs/<i>/{student.cpp,args}; writes log + rc next to them
for job in /work/jobs/*/; do
  d=$(mktemp -d /tmp/tmpXXXXXXXX)
  cp "$job/student.cpp" "$d/student.cpp"
  (cd "$d" && timeout {timeout} $(cat "$job/args") > "$job/log" 2>&1; echo $? > "$job/rc")
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
        for i, (code, exam_type) in enumerate(jobs):
            j = self.workdir / "jobs" / f"{i:06d}"
            j.mkdir()
            (j / "student.cpp").write_text(code, encoding="utf-8")
            (j / "args").write_text(" ".join(compile_args(exam_type)), encoding="utf-8")
        (self.workdir / "run.sh").write_text(_DOCKER_SCRIPT.replace("{timeout}", str(self.timeout)), encoding="utf-8")
        subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{self.workdir}:/work", self.image,
                        "bash", "/work/run.sh"], check=True, capture_output=True, text=True)
        out = []
        for i in range(len(jobs)):
            j = self.workdir / "jobs" / f"{i:06d}"
            out.append(((j / "log").read_text(encoding="utf-8", errors="replace"),
                        int((j / "rc").read_text().strip() or 1)))
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
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[compile] backend unavailable: {exc!r}")
    print("[compile] WARNING: no compiler available — compile_log will be empty")
    return None


class CompileCache:
    def __init__(self, compiler, cache_dir):
        self.compiler = compiler
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, code: str, exam_type: str) -> str:
        return hashlib.sha256(json.dumps([self.compiler.compiler_id, compile_args(exam_type), code]).encode()).hexdigest()[:32]

    def logs(self, samples) -> dict[str, str]:
        keys = {s.sample_id: self._key(s.code, s.exam_type) for s in samples}
        todo: dict[str, tuple[str, str]] = {}
        fresh: dict[str, str] = {}  # results not on disk (timeouts), still returned to the caller
        for s in samples:
            if not (self.cache_dir / f"{keys[s.sample_id]}.json").exists():
                todo.setdefault(keys[s.sample_id], (s.code, s.exam_type))
        if todo:
            print(f"[compile] {self.compiler.compiler_id}: compiling {len(todo)} submissions", flush=True)
            for key, (log, rc) in zip(todo, self.compiler.run(list(todo.values()))):
                fresh[key] = log
                if rc == 124:  # timeout: not a property of the code alone, retry next run
                    continue
                path = self.cache_dir / f"{key}.json"
                tmp = path.with_suffix(f".{os.getpid()}.tmp")
                tmp.write_text(json.dumps({"log": log, "returncode": rc}), encoding="utf-8")
                os.replace(tmp, path)
        return {sid: fresh[k] if k in fresh else json.loads((self.cache_dir / f"{k}.json").read_text(encoding="utf-8"))["log"]
                for sid, k in keys.items()}


def with_compile_logs(samples, logs: dict) -> list:
    """Every sample gets the self-compiled log (or None) — organizer logs are never mixed in."""
    return [replace(s, compile_log=logs.get(s.sample_id)) for s in samples]
