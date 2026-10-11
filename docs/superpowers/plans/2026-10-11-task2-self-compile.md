# Task 2 — tự compile bài nộp (compile_log) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Giảng viên cho phép nhóm tự compile. Sinh `compile_log` cho mọi bài (gold, mẫu chèn lỗi, 360 bài public) bằng đúng công thức của ban tổ chức, chạy trong môi trường project (Docker `gcc:13.3.0` trên Mac, g++ có sẵn trên Linux/Kaggle — không cài g++ global), rồi dùng log làm đặc trưng cho cả Hướng 1 và Hướng 2.

**Architecture:** `src/task2/compile.py` (tạo lệnh theo loại đề, chạy theo lô qua backend Docker hoặc native, chuẩn hoá và cache log, phát hiện lỗi biên dịch). `with_compile_logs()` ghi đè `compile_log` của mọi mẫu bằng log tự sinh (kể cả gold, để train và test cùng một nguồn). Hướng 1 bật `use_aux_signals`; Hướng 2 thêm khối compile_log vào context CLM, thêm cột đặc trưng `has_compile_error` cho probe, và thêm biến thể hậu xử lý `+cr` (gán `Lỗi biên dịch` theo log) được đánh giá OOF trên gold.

**Tech Stack:** Python 3.12 `.venv`, subprocess, Docker CLI (Mac), numpy, pytest.

**Spec:** `docs/superpowers/specs/2026-10-09-task2-design.md` (§9 vẫn ràng buộc; plan này thêm §10 — xem Task 5).

## Global Constraints

- Công thức compile (theo `note` trong `exams.json`): đề `single_problem` → `g++ -std=c++11 student.cpp -o student` (có link); đề `multi_problem` → `g++ -std=c++11 -fsyntax-only student.cpp`. File luôn tên `student.cpp`, nằm trong thư mục tạm `mktemp -d /tmp/tmpXXXXXXXX` chỉ chứa mỗi file đó (giống log gốc `/tmp/tmpaes44i5r/student.cpp:…`).
- Không cài g++ global. Mac: Docker image `gcc:13.3.0`, `--network none`, thư mục làm việc trong `outputs/task2/_compile_work/` (gitignored). Linux (Kaggle): `g++` trên PATH. Không bao giờ dùng `/usr/bin/g++` của macOS (đó là Apple clang).
- Chỉ compile, **không chạy** code sinh viên. Timeout 30 giây mỗi bài.
- Log tự sinh thay cho log của ban tổ chức ở **mọi** mẫu (gold + mẫu chèn lỗi + public), để đặc trưng nhất quán. Ghi phiên bản compiler vào cache key và vào output.
- Compile là trích đặc trưng từ input (được giảng viên cho phép), **không** tạo nhãn. Mọi lựa chọn (ngưỡng, lr, hệ thống cuối, bật/tắt `+cr`) vẫn chỉ dựa trên OOF của gold.
- Không có compiler → cảnh báo và `compile_log = None` (pipeline vẫn chạy); `--no-compile` tắt hẳn (ablation / fallback).
- Test không gọi Docker hay g++ thật (dùng runner giả). Baseline suite: 129 pass, 5 skip, 2 lỗi có sẵn trong `tests/test_colab_task1_secrets.py`.
- Nhánh `task-2`, không push; trailer `Co-Authored-By` ghi đúng model viết commit.

---

### Task 1: Module compile (`src/task2/compile.py`)

**Files:**
- Create: `src/task2/compile.py`
- Test: `tests/test_task2_compile.py`

**Interfaces:**
- Produces:
  - `compile_args(exam_type: str) -> list[str]` — `["g++", "-std=c++11", "-fsyntax-only", "student.cpp"]` cho `multi_problem`, `["g++", "-std=c++11", "student.cpp", "-o", "student"]` cho loại còn lại.
  - `has_compile_error(log: str | None) -> bool` — True nếu có dòng khớp `student\.cpp:\d+:\d+: (?:fatal )?error:` (lỗi link như `undefined reference to 'main'` không tính).
  - `class Compiler` (protocol): `compiler_id: str`, `run(jobs: list[tuple[str, str]]) -> list[tuple[str, int]]` (jobs = `(code, exam_type)`, trả `(log, returncode)` cùng thứ tự).
  - `NativeCompiler(cxx="g++", timeout=30)`, `DockerCompiler(image="gcc:13.3.0", workdir="outputs/task2/_compile_work", timeout=30)`; cả hai có `compiler_id` = `"<backend>:" + dòng đầu của `g++ --version``.
  - `make_compiler(backend="auto", image="gcc:13.3.0", workdir=...) -> Compiler | None` — `auto`: Linux + `shutil.which("g++")` → Native; macOS + `shutil.which("docker")` và `docker info` chạy được → Docker; ngược lại `None` (in cảnh báo).
  - `CompileCache(compiler, cache_dir)` với `logs(samples) -> dict[sample_id, str]` — key cache = sha256(`compiler_id`, args, code); chỉ gọi `compiler.run` cho các mẫu chưa có cache, một lần theo lô.
  - `with_compile_logs(samples, logs: dict) -> list` — `dataclasses.replace(s, compile_log=logs.get(s.sample_id))` cho mọi mẫu.

- [ ] **Step 1: Test (RED)** — `tests/test_task2_compile.py`:
```python
import tempfile
import unittest
from pathlib import Path

from src.task2.compile import CompileCache, compile_args, has_compile_error, with_compile_logs
from src.task2.data import Task2Sample

LOG_ERR = ("/tmp/tmpab12cd34/student.cpp: In function 'int main()':\n"
           "/tmp/tmpab12cd34/student.cpp:5:3: error: 'x' was not declared in this scope\n")
LOG_FATAL = '/tmp/tmpq/student.cpp:5:10: fatal error: data.csv: No such file or directory\n'
LOG_LINK = ("/usr/bin/ld: Scrt1.o: in function `_start':\n(.text+0x1b): undefined reference to `main'\n"
            "collect2: error: ld returned 1 exit status\n")
LOG_WARN = "/tmp/tmpz/student.cpp:10:1: warning: no return statement [-Wreturn-type]\n"


class FakeCompiler:
    compiler_id = "fake:g++ 13.3.0"

    def __init__(self):
        self.calls = []

    def run(self, jobs):
        self.calls.append(list(jobs))
        return [(("ERR " if "bad" in code else "") + exam_type, 1 if "bad" in code else 0) for code, exam_type in jobs]


def s(sid, code, exam_type="single_problem"):
    return Task2Sample(sid, "EXA", exam_type, "cpp11", f"{sid}.cpp", code, "organizer log", None, [])


class TestCompile(unittest.TestCase):
    def test_args_follow_exam_notes(self):
        self.assertEqual(compile_args("multi_problem"), ["g++", "-std=c++11", "-fsyntax-only", "student.cpp"])
        self.assertEqual(compile_args("single_problem"), ["g++", "-std=c++11", "student.cpp", "-o", "student"])

    def test_has_compile_error(self):
        self.assertTrue(has_compile_error(LOG_ERR))
        self.assertTrue(has_compile_error(LOG_FATAL))
        self.assertFalse(has_compile_error(LOG_LINK))
        self.assertFalse(has_compile_error(LOG_WARN))
        self.assertFalse(has_compile_error(None))
        self.assertFalse(has_compile_error(""))

    def test_cache_batches_and_reuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeCompiler()
            samples = [s("A", "ok"), s("B", "bad", "multi_problem"), s("C", "ok")]
            logs = CompileCache(fake, tmp).logs(samples)
            self.assertEqual(logs, {"A": "single_problem", "B": "ERR multi_problem", "C": "single_problem"})
            self.assertEqual(len(fake.calls), 1)
            self.assertEqual(len(fake.calls[0]), 2)  # A and C share code+type -> compiled once
            fake2 = FakeCompiler()
            self.assertEqual(CompileCache(fake2, tmp).logs(samples), logs)
            self.assertEqual(fake2.calls, [])

    def test_with_compile_logs_replaces_every_sample(self):
        out = with_compile_logs([s("A", "x"), s("B", "y")], {"A": "log A"})
        self.assertEqual([o.compile_log for o in out], ["log A", None])  # organizer log never kept
```
Run: `.venv/bin/python -m pytest tests/test_task2_compile.py -q` → FAIL (`ModuleNotFoundError`).

- [ ] **Step 2: Code** — `src/task2/compile.py`:
```python
"""Self-compiled compile_log for Task 2 (instructor allowed teams to compile submissions themselves).

Reproduces the organizer's recipe from exams.json notes: single_problem -> `g++ -std=c++11` (compile + link),
multi_problem -> `g++ -std=c++11 -fsyntax-only`, file `student.cpp` alone in `mktemp -d /tmp/tmpXXXXXXXX`.
Code is only compiled, never executed. No global g++ install: macOS runs GCC in Docker (`gcc:13.3.0`,
--network none); Linux (Kaggle) uses the g++ on PATH. Logs are features, not labels.
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
import shutil
import subprocess
import tempfile
from dataclasses import replace
from pathlib import Path

_ERROR = re.compile(r"student\.cpp:\d+:\d+: (?:fatal )?error:")


def compile_args(exam_type: str) -> list[str]:
    if exam_type == "multi_problem":
        return ["g++", "-std=c++11", "-fsyntax-only", "student.cpp"]
    return ["g++", "-std=c++11", "student.cpp", "-o", "student"]


def has_compile_error(log: str | None) -> bool:
    """A compiler error in student.cpp (link-only errors such as a missing main do not count)."""
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
                    p = subprocess.run(args, cwd=d, capture_output=True, text=True, timeout=self.timeout)
                    results.append(((p.stdout or "") + (p.stderr or ""), p.returncode))
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
        for s in samples:
            if not (self.cache_dir / f"{keys[s.sample_id]}.json").exists():
                todo.setdefault(keys[s.sample_id], (s.code, s.exam_type))
        if todo:
            print(f"[compile] {self.compiler.compiler_id}: compiling {len(todo)} submissions", flush=True)
            for key, (log, rc) in zip(todo, self.compiler.run(list(todo.values()))):
                (self.cache_dir / f"{key}.json").write_text(json.dumps({"log": log, "returncode": rc}), encoding="utf-8")
        return {sid: json.loads((self.cache_dir / f"{k}.json").read_text(encoding="utf-8"))["log"]
                for sid, k in keys.items()}


def with_compile_logs(samples, logs: dict) -> list:
    """Every sample gets the self-compiled log (or None) — organizer logs are never mixed in."""
    return [replace(s, compile_log=logs.get(s.sample_id)) for s in samples]
```

- [ ] **Step 3: GREEN** — `.venv/bin/python -m pytest tests/test_task2_compile.py -q`.
- [ ] **Step 4: Kiểm tra thật bằng Docker (không phải test tự động)**:
```bash
docker pull gcc:13.3.0
.venv/bin/python - <<'EOF'
import json
from src.task2.compile import CompileCache, make_compiler, has_compile_error
from src.task2.data import load_task2
g = load_task2("data/raw/sample_dataset")
comp = make_compiler("auto"); print(comp.compiler_id)
logs = CompileCache(comp, "outputs/task2/_compile_cache").logs(g.samples)
agree = sum(has_compile_error(logs[s.sample_id]) == has_compile_error(s.compile_log) for s in g.samples)
tp = sum(has_compile_error(logs[s.sample_id]) and "Lỗi biên dịch" in s.labels for s in g.samples)
fp = sum(has_compile_error(logs[s.sample_id]) and "Lỗi biên dịch" not in s.labels for s in g.samples)
fn = sum((not has_compile_error(logs[s.sample_id])) and "Lỗi biên dịch" in s.labels for s in g.samples)
print("agree with organizer error flag:", agree, "/", len(g.samples), "| vs label tp/fp/fn:", tp, fp, fn)
EOF
```
Expected: `compiler_id` chứa `gcc:13.3.0` và `g++ (GCC) 13.3.0`; mức đồng thuận với cờ lỗi của ban tổ chức gần 32/32; ghi kết quả vào report (không sửa code nếu lệch, chỉ báo cáo).
- [ ] **Step 5: Commit** — `git add src/task2/compile.py tests/test_task2_compile.py && git commit -m "Add self-compile module reproducing the organizer's g++ recipe"`.

---

### Task 2: Đưa compile_log vào Hướng 1 và Hướng 2

**Files:**
- Modify: `configs/task2/base.yaml` (khối `compile`), `configs/task2/api_zero_shot.yaml` (`use_aux_signals: true`, mô tả), `configs/task2/clm_base.yaml` (`text.use_compile_log`, `text.max_compile_tokens`, `probe.compile_feature`)
- Modify: `scripts/run_task2_api.py`, `scripts/run_task2_clm.py` (áp `with_compile_logs` cho gold, public; CLM cả mẫu chèn lỗi; cờ `--no-compile`)
- Modify: `src/task2/clm/text.py` (khối compile_log tuỳ chọn trong context), `src/task2/clm/experiment.py` (cột `has_compile_error` cho probe; biến thể `+cr`)
- Test: `tests/test_task2_clm_text.py`, `tests/test_task2_clm_experiment.py`, `tests/test_task2_run_api_script.py` (nếu cần)

**Interfaces:**
- Config (`base.yaml`): `compile: {enabled: true, backend: auto, image: "gcc:13.3.0", cache_dir: outputs/task2/_compile_cache, workdir: outputs/task2/_compile_work}`.
- `build_state_texts(exam, sample, tok, max_tokens=2048, max_statement_tokens=512, use_compile_log=False, max_compile_tokens=256)` — khi `use_compile_log` và `sample.compile_log`: chèn `"\n\nKết quả biên dịch (g++ -std=c++11):\n" + head_truncate(clean_log, max_compile_tokens)` **giữa đề và code** (để không bị cắt mất); khi log rỗng chèn `"\n\nKết quả biên dịch: không có lỗi hay cảnh báo."`; `clean_log` = bỏ tiền tố `/tmp/tmp\w+/` (dùng `clean_compile_log` của `src/task1/prompts.py` hoặc regex tương đương). Mặc định `False` giữ nguyên hành vi cũ.
- `run_clm`: khi `probe.compile_feature` (mặc định true) — X của probe = `[embedding, has_compile_error]` (cột cuối 0/1, mọi tập: gold, mẫu chèn lỗi, public). Thêm vào `metrics["systems"]` các khoá `"<system>+cr@0.5"`, `"<system>+cr@tuned"` cho mọi system: dự đoán như bản gốc rồi đặt nhãn `Lỗi biên dịch` = `has_compile_error(compile_log)`. `final_system` hợp lệ = tên trong `SYSTEMS` hoặc `<tên>+cr`. Public: áp `+cr` sau `min_rate` khi final kết thúc bằng `+cr`. `metrics["compile"] = {"enabled": bool, "compiler_id": str | None}` (script truyền vào qua `cfg["_compiler_id"]`).
- Scripts: khi `compile.enabled` và không `--no-compile`: `comp = make_compiler(...)`; nếu `comp` → `logs = CompileCache(comp, cache_dir).logs(<tất cả mẫu cần dùng>)` và `with_compile_logs` cho từng dataset/list; nếu `None` → in cảnh báo, đặt `compile_log=None` cho mọi mẫu (không dùng log ban tổ chức). Với `--no-compile`: cũng đặt `compile_log=None` cho mọi mẫu (ablation sạch). CLM: tính `mutants` trước, compile chung gold + mutants + public trong một lô.
- `clm_base.yaml`: `text.use_compile_log: true`, `text.max_compile_tokens: 256`, `probe.compile_feature: true`; mô tả cập nhật. `api_zero_shot.yaml`: `use_aux_signals: true`, mô tả "có compile_log tự compile (g++ 13, cùng công thức ban tổ chức)".

- [ ] **Step 1: Test (RED)**:
  - `tests/test_task2_clm_text.py`: với `use_compile_log=True` và log `"/tmp/tmpab/student.cpp:3:1: error: x"`, mọi state text chứa `"Kết quả biên dịch"`, chứa `"student.cpp:3:1: error: x"`, không chứa `"/tmp/tmpab/"`, khối compile đứng trước code, độ dài ≤ `max_tokens`; log `""` → chứa `"không có lỗi hay cảnh báo"`; `use_compile_log=False` → không chứa `"Kết quả biên dịch"`.
  - `tests/test_task2_clm_experiment.py`: gold fixture đặt `compile_log` (qua `dataclasses.replace` trên `gold.samples`) có lỗi cho các mẫu mang nhãn `Lỗi biên dịch`; chạy `run_clm` → `metrics["systems"]` có `"probe_aug+cr@tuned"`, và F1 của nhãn `Lỗi biên dịch` ở `+cr` = 1.0; `final_system: "probe_aug+cr"` chạy được và `predictions.json` hợp lệ; `final_system: "nope+cr"` → `ValueError`.
  Run: `.venv/bin/python -m pytest tests/test_task2_clm_text.py tests/test_task2_clm_experiment.py -q` → FAIL.
- [ ] **Step 2: Code** theo Interfaces ở trên. Giữ nguyên quy tắc không rò rỉ của CV (mẫu chèn lỗi theo fold) và chọn ngưỡng/lr chỉ trên OOF gold. Probe ở cả CV lẫn bản cuối dùng cùng cách ghép cột.
- [ ] **Step 3: GREEN + suite** — chạy test liên quan, rồi `.venv/bin/python -m pytest tests/ -q`; `.venv/bin/python scripts/run_task2_api.py --preflight` (không gọi API; preflight được phép compile gold val qua Docker — nếu không muốn chờ, preflight dùng `--no-compile`).
- [ ] **Step 4: Commit** — `git commit -m "Use self-compiled compile_log in Task 2 prompts, CLM context and probe"`.

---

### Task 3: Notebook Kaggle + docs

**Files:** `kaggle/task2_clm.ipynb`, `docs/task2.md`, `README.md`

- [ ] Notebook: thêm vào cell cài đặt dòng `!g++ --version` (in phiên bản, Kaggle dùng g++ native); ghi chú markdown: compile chỉ chạy `g++ -std=c++11` (`-fsyntax-only` cho đề nhiều câu), không chạy code; phiên bản g++ của Kaggle có thể khác GCC 13.3 của bản local → log khác chữ đôi chút, cache tách theo `compiler_id`. Giữ 7 cell, `/kaggle/tmp`, secret, pin transformers.
- [ ] `docs/task2.md`: mục mới "Tự compile (giảng viên cho phép, 2026-10-11)": công thức, Docker `gcc:13.3.0` trên Mac (không cài g++ global), native trên Linux, log thay cho log ban tổ chức ở mọi mẫu, chỉ compile không chạy, `--no-compile` cho ablation/fallback, `+cr` là hậu xử lý; kết quả so khớp với log ban tổ chức trên gold (số từ Task 1 Step 4); thay ghi chú cũ "không đưa compile_log/test_report vào input" bằng "test_report vẫn không dùng (không có testcase)". Mục câu hỏi giảng viên: bỏ ý đã được trả lời nếu có, ghi "Tự compile: được phép (2026-10-11)".
- [ ] `README.md`: dòng Quick Start Task 2 thêm `docker pull gcc:13.3.0  # macOS: self-compile runs in Docker, no global g++`.
- [ ] Kiểm tra: notebook 7 cell, `git ls-files | xargs grep -l <DRIVE_ID_PREFIX>` rỗng. Commit `"Document self-compile for Task 2"`.

---

### Task 4: Chạy thật (controller) và ghi số liệu

- [ ] `time .venv/bin/python scripts/run_task2_clm.py --config configs/task2/clm_local.yaml` (compile gold + mẫu chèn lỗi + 6 public trong Docker; context đổi nên encode lại ~72 × 11).
- [ ] So sánh với lần chạy không compile (`--no-compile`, embedding cũ trong cache): bảng ablation có/không compile cho các hệ thống chính + `+cr`.
- [ ] Ghi bảng vào `docs/task2.md`, commit docs và `experiments/registry.csv` riêng.

### Task 5: Spec

- [ ] Thêm `## 10. Sửa đổi 2026-10-11 — tự compile` vào spec: giảng viên cho phép; công thức; môi trường; log thay thế ở mọi mẫu; đặc trưng (prompt, context CLM, cột probe, `+cr`); `test_report` vẫn không dùng; chọn cấu hình vẫn chỉ dựa trên OOF gold. Commit cùng Task 3.
