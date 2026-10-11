# Task 2 — bỏ silver, CV trên gold, augmentation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tuân thủ phán quyết của giảng viên (không dùng nhãn LLM sinh trên input tập test để train): bỏ toàn bộ silver, đánh giá Hướng 2 bằng k-fold CV trên 32 bài gold, thêm augmentation chèn lỗi vào code gold (luật cố định + tuỳ chọn API), cập nhật notebook và docs.

**Architecture:** Hướng 1 giữ nguyên, chỉ bỏ đầu ra `silver_labels.json` và đổi config `api_silver` → `api_predict`. Hướng 2: module mới `src/task2/augment.py` (9 luật chèn lỗi, nhãn biết trước) và `src/task2/augment_api.py` (LLM chèn lỗi vào code gold, ghi JSON); `src/task2/clm/experiment.run_clm` viết lại thành: nhúng gold + mẫu chèn lỗi + public → k-fold CV ra xác suất out-of-fold cho 5 hệ thống → ngưỡng từ OOF → train bản cuối trên toàn bộ gold → dự đoán public.

**Tech Stack:** Python 3.12 (`.venv`), numpy, PyTorch, scikit-learn, re; pytest (test kiểu `unittest`).

**Spec:** `docs/superpowers/specs/2026-10-09-task2-design.md` — §9 "Sửa đổi 2026-10-11" là phần ràng buộc mới và thay thế mọi mục silver.

## Global Constraints

- Không dùng bất kỳ input nào của tập test (360 bài `public_test_release`: code, đề, CSV) để tạo dữ liệu train, nhãn, ngưỡng hay chọn epoch. Tập test chỉ được dùng để **dự đoán** khi nộp bài.
- Augmentation chỉ lấy nguồn từ bài **có nhãn** của `sample_dataset`; mẫu chèn lỗi có `sample_id = "<id gốc>~<tên luật>"` (API: `"<id gốc>~api-<chỉ số nhãn>"`), nhãn = nhãn gốc ∪ nhãn chèn.
- Trong CV, mẫu chèn lỗi chỉ vào fold train khi bài gốc thuộc fold train.
- 10 nhãn đúng thứ tự `src.task2.labels.LABELS`. `predictions.json` chỉ ghi qua `write_submission`.
- Seed 42. Không gọi API, không tải model trong test. Test: `.venv/bin/python -m pytest tests/ -q` (baseline: 2 lỗi có sẵn trong `tests/test_colab_task1_secrets.py`, 106 pass, 5 skip).
- Không ghi file id/link Google Drive vào repo. Không commit dữ liệu, `outputs/`, `checkpoints/`.
- Commit trên nhánh `task-2`, không push; trailer `Co-Authored-By` ghi đúng model đã viết commit.

---

## File Structure

| File | Thay đổi |
|---|---|
| `src/task2/api_experiment.py` | Bỏ ghi `silver_labels.json` |
| `configs/task2/api_silver.yaml` → `configs/task2/api_predict.yaml` | Đổi tên, mô tả = dự đoán để nộp |
| `configs/task2/run_api.yaml`, `scripts/run_task2_api.py` | `predict_config: api_predict`, bỏ chữ silver |
| `src/task2/augment.py` (mới) | 9 luật chèn lỗi, `augment()`, `source_id()` |
| `src/task2/augment_api.py` (mới), `scripts/augment_task2_api.py` (mới) | Chèn lỗi bằng API (tuỳ chọn), `load_mutants()` |
| `src/task2/clm/experiment.py` | `run_clm` mới: CV + augmentation, bỏ silver/split/early stop |
| `scripts/run_task2_clm.py`, `configs/task2/clm_*.yaml` | Bỏ `--silver`, thêm `augment`, `cv` |
| `kaggle/task2_clm.ipynb`, `docs/task2.md`, `README.md` | Bỏ silver, thêm CV/augmentation |
| Test | `tests/test_task2_api_experiment.py`, `tests/test_task2_run_api_script.py`, `tests/test_task2_augment.py` (mới), `tests/test_task2_augment_api.py` (mới), `tests/test_task2_clm_experiment.py` (viết lại) |

---

### Task 1: Hướng 1 — bỏ đầu ra silver

**Files:**
- Modify: `src/task2/api_experiment.py` (docstring dòng 1; dòng `_write_json(out_dir / "silver_labels.json", ...)`)
- Rename: `configs/task2/api_silver.yaml` → `configs/task2/api_predict.yaml`
- Modify: `configs/task2/run_api.yaml`, `scripts/run_task2_api.py`
- Test: `tests/test_task2_api_experiment.py`, `tests/test_task2_run_api_script.py`

**Interfaces:**
- Produces: `run_api(...)` không còn ghi `silver_labels.json`; xác suất từng nhãn vẫn nằm trong `predictions_full.json` (`probs`). Config dự đoán tên `api_predict` (`name: task2_api_predict`).

- [ ] **Step 1: Sửa test trước (RED)**

Trong `tests/test_task2_api_experiment.py`, khối kiểm tra file của `test_outputs_metrics_and_cache` đổi thành:
```python
            for f in ("predictions.json", "predictions_full.json", "metrics.json",
                      "resources.json", "config.json", "raw_outputs.jsonl"):
                self.assertTrue((out / f).exists(), f)
            self.assertFalse((out / "silver_labels.json").exists())  # no labels derived from test inputs
            full = json.loads((out / "predictions_full.json").read_text(encoding="utf-8"))
            self.assertEqual(full[0]["probs"]["Lỗi logic"], 1.0)
```
Trong `tests/test_task2_run_api_script.py`: thay mọi `api_silver` bằng `api_predict`, đổi tên test `test_silver_demos_exclude_gold_val_and_cost_scales_with_n` → `test_predict_demos_exclude_gold_val_and_cost_scales_with_n` (giữ nguyên các assert còn lại).

Run: `.venv/bin/python -m pytest tests/test_task2_api_experiment.py tests/test_task2_run_api_script.py -q` → FAIL (silver_labels.json vẫn được ghi / không có `api_predict.yaml`).

- [ ] **Step 2: Sửa code**

- `src/task2/api_experiment.py`: docstring dòng 1 → `"""Run Task 2 Hướng 1 on a list of samples: cached/resumable inference, predictions, metrics."""`; xoá dòng ghi `silver_labels.json`.
- `git mv configs/task2/api_silver.yaml configs/task2/api_predict.yaml`, nội dung:
```yaml
extends: api_few_shot.yaml
name: task2_api_predict
description: Dự đoán 360 bài public để nộp — self-consistency n=5, T=0.7, nhãn = đa số phiếu. Không dùng làm dữ liệu train.
generation:
  temperature: 0.7
  n: 5
```
- `configs/task2/run_api.yaml`: `predict_config: api_predict  # writes predictions.json for the 360 public samples`; chú thích `max_usd`/`max_requests_per_run` đổi chữ "silver" thành "predict pass".
- `scripts/run_task2_api.py`: đổi chú thích nhắc "silver" thành "predict pass"; dòng in `silver + predictions -> ...` → `predictions -> ...`.

Run: `grep -rn "silver" src scripts configs` → không còn kết quả nào trong các file Task 1 này (file CLM xử lý ở Task 4; chấp nhận kết quả còn lại trong `src/task2/clm/experiment.py`, `scripts/run_task2_clm.py`, `configs/task2/clm_*.yaml`).

- [ ] **Step 3: GREEN + commit**

```bash
.venv/bin/python -m pytest tests/test_task2_api_experiment.py tests/test_task2_run_api_script.py -q
.venv/bin/python scripts/run_task2_api.py --preflight
git add -A src/task2/api_experiment.py configs/task2 scripts/run_task2_api.py tests/test_task2_api_experiment.py tests/test_task2_run_api_script.py
git commit -m "Drop silver labels from Task 2 API runner (instructor ruling)"
```

---

### Task 2: Augmentation bằng luật (`src/task2/augment.py`)

**Files:**
- Create: `src/task2/augment.py`
- Test: `tests/test_task2_augment.py`

**Interfaces:**
- Consumes: `Task2Sample` (`src/task2/data.py`, dataclass), `normalize_labels`, `LABELS`.
- Produces: `Mutator(name: str, label: str, apply: Callable[[str], str | None])`; `MUTATORS: tuple[Mutator, ...]` (9 luật); `augment(samples, mutators=MUTATORS, max_per_mutator: int | None = None) -> list[Task2Sample]`; `source_id(sample_id: str) -> str`.

- [ ] **Step 1: Viết test (RED)**

`tests/test_task2_augment.py`:
```python
import unittest

from src.task2.augment import MUTATORS, augment, source_id
from src.task2.data import Task2Sample
from src.task2.labels import LABELS

CODE = """#include <iostream>
#include <vector>
using namespace std;
int sumDigits(int n) {
    if (n == 0) return 0;
    int s = 0;
    for (int i = 0; i < 10; i++) {
        s += n % 10;
    }
    return s + n;
}
void fill(vector<int> &v) {
    for (int i = 0; i < v.size(); i++) v[i] = i;
}
int main() {
    int n;
    cin >> n;
    if (n > 0) cout << "Tong: " << sumDigits(n) << endl;
    return 0;
}
"""

EXPECT = {
    "drop_return_semicolon": "if (n == 0) return 0\n",
    "alter_output_text": 'cout << "Ket qua: Tong: "',
    "flip_if_comparison": "if (n != 0) return 0;",
    "flip_loop_bound": "for (int i = 0; i <= 10; i++)",
    "off_by_one_size": "v.size() + 1",
    "drop_reference_param": "void fill(vector<int> v)",
    "hardcode_return": "return 1;",
    "strip_indentation": "\nint s = 0;\n",
}


def sample(sid="S1", code=CODE, labels=("Lỗi logic",)):
    return Task2Sample(sample_id=sid, exam_id="EXA", exam_type="single_problem", language="cpp11",
                       code_file=f"{sid}.cpp", code=code, compile_log="log", test_report=[{"x": 1}],
                       labels=list(labels))


class TestMutators(unittest.TestCase):
    def test_nine_mutators_valid_labels(self):
        self.assertEqual(len(MUTATORS), 9)
        self.assertEqual(len({m.name for m in MUTATORS}), 9)
        for m in MUTATORS:
            self.assertIn(m.label, LABELS)
        self.assertNotIn("Lỗi thuật toán", {m.label for m in MUTATORS})

    def test_each_mutator_changes_code(self):
        by_name = {m.name: m for m in MUTATORS}
        for name, needle in EXPECT.items():
            new = by_name[name].apply(CODE)
            self.assertIsNotNone(new, name)
            self.assertNotEqual(new, CODE, name)
            self.assertIn(needle, new, name)
        guarded = by_name["remove_edge_guard"].apply(CODE)
        self.assertNotIn("if (n == 0)", guarded)
        self.assertIn("int s = 0;", guarded)

    def test_not_applicable_returns_none(self):
        plain = "int main(){return 0;}\n"
        by_name = {m.name: m for m in MUTATORS}
        for name in ("alter_output_text", "flip_if_comparison", "flip_loop_bound", "off_by_one_size",
                     "drop_reference_param", "remove_edge_guard", "hardcode_return", "strip_indentation"):
            self.assertIsNone(by_name[name].apply(plain), name)


class TestAugment(unittest.TestCase):
    def test_labels_ids_and_aux_cleared(self):
        out = augment([sample()])
        self.assertEqual(len(out), 9)
        loop = next(m for m in out if m.sample_id == "S1~flip_loop_bound")
        self.assertEqual(loop.labels, ["Lỗi logic", "Lỗi vòng lặp"])
        self.assertIsNone(loop.compile_log)
        self.assertIsNone(loop.test_report)
        self.assertEqual(source_id(loop.sample_id), "S1")
        self.assertEqual(source_id("S1"), "S1")

    def test_cap_and_unlabelled_skipped(self):
        samples = [sample("S1"), sample("S2"), Task2Sample("P1", "EXA", "single_problem", "cpp11", "p.cpp", CODE,
                                                           None, None, None)]
        out = augment(samples, max_per_mutator=1)
        self.assertEqual(len(out), 9)
        self.assertTrue(all(source_id(m.sample_id) == "S1" for m in out))
```

Run: `.venv/bin/python -m pytest tests/test_task2_augment.py -q` → FAIL (`ModuleNotFoundError`).

- [ ] **Step 2: Viết `src/task2/augment.py`**

```python
"""Task 2 training-data augmentation: inject one known bug type into LABELLED gold code.

Only labelled training samples (sample_dataset) are mutated — never test inputs (instructor ruling 2026-10-11:
no labels derived from the test set). The injected label is known by construction; the mutant keeps the source
sample's own labels as well. compile_log/test_report are cleared because they no longer describe the code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Callable

from src.task2.labels import normalize_labels


@dataclass(frozen=True)
class Mutator:
    name: str
    label: str
    apply: Callable[[str], "str | None"]  # None = rule not applicable to this code


def _sub_first(pattern: str, repl, code: str, flags: int = 0) -> str | None:
    new, n = re.subn(pattern, repl, code, count=1, flags=flags)
    return new if n and new != code else None


def drop_return_semicolon(code: str) -> str | None:
    return _sub_first(r"(\breturn\b[^;\n{}]*);", r"\1", code)


def alter_output_text(code: str) -> str | None:
    return _sub_first(r'(\bcout\s*<<\s*"|\bprintf\s*\(\s*")', r"\1Ket qua: ", code)


_SWAP = {"==": "!=", "!=": "==", ">=": "<", "<=": ">", ">": "<=", "<": ">="}


def flip_if_comparison(code: str) -> str | None:
    return _sub_first(r"(\bif\s*\([^()\n]*?\s)(==|!=|>=|<=|>|<)(\s)",
                      lambda m: m.group(1) + _SWAP[m.group(2)] + m.group(3), code)


def flip_loop_bound(code: str) -> str | None:
    return _sub_first(r"(\bfor\s*\([^;]*;[^;<>]*?)(<=|<)([^;]*;)",
                      lambda m: m.group(1) + ("<" if m.group(2) == "<=" else "<=") + m.group(3), code)


def off_by_one_size(code: str) -> str | None:
    return _sub_first(r"(\.(?:size|length)\(\)|\bstrlen\s*\([^()]*\))", r"\1 + 1", code)


def drop_reference_param(code: str) -> str | None:
    return _sub_first(r"([(,]\s*(?:const\s+)?[\w:<>*]+\s*)&\s*(\w+)", r"\1\2", code)


_GUARD = re.compile(r"^[ \t]*if\s*\((?:[^()\n]|\([^()\n]*\))*(?:==\s*0|<=\s*0|<\s*1|==\s*NULL|==\s*nullptr|!\s*\w+)"
                    r"\s*\)[^\n]*\n", re.M)


def remove_edge_guard(code: str) -> str | None:
    """Delete the first edge-case guard (n == 0, n <= 0, ptr == NULL, !ptr, ...) and its one-statement body."""
    m = _GUARD.search(code)
    if not m:
        return None
    line, end = m.group(0).rstrip(), m.end()
    if line.endswith(")"):  # body on the next line: one statement or a flat { } block
        nxt = re.match(r"[ \t]*\{[^{}]*\}[ \t]*\n|[ \t]*[^\n]*;[ \t]*\n", code[end:])
        if nxt:
            end += nxt.end()
    elif line.endswith("{"):  # flat block opened on the guard line
        close = code.find("}", end)
        if close == -1 or "{" in code[end:close]:
            return None
        nl = code.find("\n", close)
        end = len(code) if nl == -1 else nl + 1
    return code[:m.start()] + code[end:]


def hardcode_return(code: str) -> str | None:
    """First non-main function returning a computed value now returns a constant."""
    for m in re.finditer(r"\b(?:int|bool|long|double|float)\s+(\w+)\s*\([^)]*\)\s*\{", code):
        if m.group(1) == "main":
            continue
        r = re.compile(r"\breturn\s+(?!0;|1;|true;|false;)[^;\n]+;").search(code, m.end())
        if r:
            return code[:r.start()] + "return 1;" + code[r.end():]
    return None


def strip_indentation(code: str) -> str | None:
    new = "\n".join(line.strip() for line in code.splitlines() if line.strip()) + "\n"
    return new if new != code else None


MUTATORS: tuple[Mutator, ...] = (
    Mutator("drop_return_semicolon", "Lỗi biên dịch", drop_return_semicolon),
    Mutator("alter_output_text", "Lỗi nhập/xuất", alter_output_text),
    Mutator("flip_if_comparison", "Lỗi logic", flip_if_comparison),
    Mutator("flip_loop_bound", "Lỗi vòng lặp", flip_loop_bound),
    Mutator("off_by_one_size", "Lỗi mảng/chuỗi", off_by_one_size),
    Mutator("drop_reference_param", "Lỗi hàm", drop_reference_param),
    Mutator("remove_edge_guard", "Lỗi edge case", remove_edge_guard),
    Mutator("hardcode_return", "Lỗi hard-code", hardcode_return),
    Mutator("strip_indentation", "Lỗi style", strip_indentation),
)


def source_id(sample_id: str) -> str:
    """Id of the gold sample a mutant was made from (the id itself for non-mutants)."""
    return sample_id.split("~", 1)[0]


def augment(samples, mutators=MUTATORS, max_per_mutator: int | None = None) -> list:
    """One mutant per (labelled sample, applicable mutator), sorted by sample id, at most `max_per_mutator` each."""
    out = []
    for mu in mutators:
        made = 0
        for s in sorted(samples, key=lambda s: s.sample_id):
            if max_per_mutator is not None and made >= max_per_mutator:
                break
            if not s.has_gold:
                continue
            new = mu.apply(s.code)
            if new is None:
                continue
            out.append(replace(s, sample_id=f"{s.sample_id}~{mu.name}", code=new, compile_log=None,
                               test_report=None, labels=normalize_labels([*s.labels, mu.label])))
            made += 1
    return out
```

Tự kiểm tra với `CODE` trong test: `drop_return_semicolon` sửa `return 0;` đầu tiên (trong `if (n == 0) return 0;`) thành `return 0`; `flip_if_comparison` đổi `n == 0` → `n != 0`; `remove_edge_guard` xoá cả dòng `if (n == 0) return 0;` (dòng kết thúc bằng `;`); `hardcode_return` bỏ qua `return 0;` (lookahead) và thay `return s + n;`.

- [ ] **Step 3: GREEN + kiểm tra trên dữ liệu thật + commit**

```bash
.venv/bin/python -m pytest tests/test_task2_augment.py -q
.venv/bin/python -c "
from collections import Counter
from src.task2.augment import augment
from src.task2.data import load_task2
g = load_task2('data/raw/sample_dataset'); out = augment(g.samples)
print(len(out), Counter(m.sample_id.split('~')[1] for m in out))"
git add src/task2/augment.py tests/test_task2_augment.py
git commit -m "Add rule-based bug-injection augmentation for Task 2 gold code"
```
Expected: in số mẫu chèn lỗi theo từng luật trên 32 bài gold (ghi lại trong report; luật nào ra 0 mẫu thì ghi chú, không sửa regex ở task này).

---

### Task 3: Augmentation bằng API (tuỳ chọn)

**Files:**
- Create: `src/task2/augment_api.py`, `scripts/augment_task2_api.py`
- Test: `tests/test_task2_augment_api.py`

**Interfaces:**
- Consumes: backend `generate(requests, gen) -> list[list[str]]`, `info()` (Gemini/OpenAI, `tests/_task2.FakeBackend`); request keys `sample`, `exam`, `messages`, `schema`, `schema_name`; `extract_json_objects`; `DESCRIPTIONS`, `LABELS`, `normalize_labels`; `Task2Sample`.
- Produces: `SCHEMA`, `build_messages(exam, sample, label) -> list[dict]`, `parse_code(text, original) -> str | None`, `plan_jobs(samples, labels, per_label) -> list[tuple[Task2Sample, str]]`, `generate_mutants(dataset, jobs, backend, gen) -> list[dict]` (record: `sample_id, source_id, exam_id, exam_type, label, labels, code`), `load_mutants(path) -> list[Task2Sample]`. CLI `scripts/augment_task2_api.py [--provider gemini|openai] [--labels ...] [--per-label 6] [--output outputs/task2/augment_api/mutants.json] [--preflight]`.

- [ ] **Step 1: Viết test (RED)**

`tests/test_task2_augment_api.py`:
```python
import json
import tempfile
import unittest
from pathlib import Path

from src.task2.augment_api import (SCHEMA, build_messages, generate_mutants, load_mutants, parse_code,
                                    plan_jobs)
from src.task2.data import load_task2
from tests._task2 import FakeBackend, make_dataset


class TestAugmentApi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ds = load_task2(make_dataset(Path(self.tmp.name) / "g", [
            ("A1", "EXA", ["Lỗi logic"]), ("A2", "EXA", []), ("B1", "EXB", ["Lỗi hàm"])]))

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_skips_samples_that_already_have_label(self):
        jobs = plan_jobs(self.ds.samples, ["Lỗi logic", "Lỗi hàm"], per_label=5)
        pairs = [(s.sample_id, lab) for s, lab in jobs]
        self.assertNotIn(("A1", "Lỗi logic"), pairs)
        self.assertNotIn(("B1", "Lỗi hàm"), pairs)
        self.assertIn(("A2", "Lỗi logic"), pairs)
        self.assertEqual(len(plan_jobs(self.ds.samples, ["Lỗi logic"], per_label=1)), 1)

    def test_messages_and_parse(self):
        s = self.ds.by_id()["A2"]
        text = "\n".join(m["content"] for m in build_messages(self.ds.exams["EXA"], s, "Lỗi edge case"))
        self.assertIn("Lỗi edge case", text)
        self.assertIn(s.code.strip()[:20], text)
        self.assertNotIn("feedback", text.lower())
        self.assertEqual(parse_code('{"code": "int x;"}', "int y;"), "int x;")
        self.assertIsNone(parse_code('{"code": "int y;"}', "int y;"))  # unchanged
        self.assertIsNone(parse_code("rác", "int y;"))
        self.assertEqual(SCHEMA["required"], ["code"])

    def test_generate_and_load_roundtrip(self):
        jobs = plan_jobs(self.ds.samples, ["Lỗi edge case"], per_label=2)
        backend = FakeBackend([json.dumps({"code": "int changed1;"}), "rác"])
        recs = generate_mutants(self.ds, jobs, backend, {"n": 1})
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["source_id"], jobs[0][0].sample_id)
        self.assertIn("Lỗi edge case", recs[0]["labels"])
        self.assertTrue(recs[0]["sample_id"].startswith(jobs[0][0].sample_id + "~api-"))
        self.assertEqual(backend.calls[0]["schema_name"], "task2_mutant")
        path = Path(self.tmp.name) / "m.json"
        path.write_text(json.dumps(recs, ensure_ascii=False), encoding="utf-8")
        loaded = load_mutants(path)
        self.assertEqual(loaded[0].code, "int changed1;")
        self.assertTrue(loaded[0].has_gold)
```

Run: `.venv/bin/python -m pytest tests/test_task2_augment_api.py -q` → FAIL.

- [ ] **Step 2: Viết `src/task2/augment_api.py`**

```python
"""Optional Task 2 augmentation through an API LLM: rewrite a LABELLED gold submission so that it contains one
extra bug of a requested type. The label is known by construction (it is the bug we asked for); only gold code is
sent — never test inputs. Output records feed scripts/run_task2_clm.py (config augment.api_path)."""
from __future__ import annotations

import json
from pathlib import Path

from src.task2.data import Task2Sample
from src.task2.labels import DESCRIPTIONS, LABELS, normalize_labels
from src.utils.json_extractor import extract_json_objects

SCHEMA = {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"],
          "additionalProperties": False}

SYSTEM = ("Bạn là giảng viên lập trình C++. Hãy sửa bài nộp dưới đây để CỐ Ý chèn đúng MỘT lỗi thuộc loại được "
          "yêu cầu, giữ nguyên phần còn lại nhiều nhất có thể, không thêm chú thích nào tiết lộ lỗi. "
          'Trả về DUY NHẤT một object JSON {"code": "<toàn bộ code sau khi sửa>"}.')


def build_messages(exam: dict, sample, label: str) -> list[dict]:
    user = (f"## ĐỀ BÀI ({exam['exam_id']})\n{exam.get('statement', '').strip()}\n\n"
            f"## BÀI NỘP GỐC\n```cpp\n{sample.code}\n```\n\n"
            f"## LOẠI LỖI CẦN CHÈN\n{label}: {DESCRIPTIONS[label]}\n")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def parse_code(text: str, original: str) -> str | None:
    for obj in extract_json_objects(text or ""):
        code = obj.get("code")
        if isinstance(code, str) and code.strip() and code.strip() != original.strip():
            return code
    return None


def plan_jobs(samples, labels, per_label: int) -> list[tuple]:
    """For each label, up to `per_label` labelled samples that do not already carry it (sorted by id)."""
    jobs = []
    for lab in labels:
        cands = [s for s in sorted(samples, key=lambda s: s.sample_id) if s.has_gold and lab not in s.labels]
        jobs.extend((s, lab) for s in cands[:per_label])
    return jobs


def generate_mutants(dataset, jobs, backend, gen: dict) -> list[dict]:
    reqs = [{"sample": s, "exam": dataset.exams[s.exam_id], "messages": build_messages(dataset.exams[s.exam_id], s, lab),
             "schema": SCHEMA, "schema_name": "task2_mutant"} for s, lab in jobs]
    outs = backend.generate(reqs, gen) if reqs else []
    records = []
    for (s, lab), texts in zip(jobs, outs):
        code = next((c for c in (parse_code(t, s.code) for t in texts) if c), None)
        if code is None:
            continue
        records.append({"sample_id": f"{s.sample_id}~api-{LABELS.index(lab)}", "source_id": s.sample_id,
                        "exam_id": s.exam_id, "exam_type": s.exam_type, "label": lab,
                        "labels": normalize_labels([*s.labels, lab]), "code": code})
    return records


def load_mutants(path) -> list[Task2Sample]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Task2Sample(sample_id=r["sample_id"], exam_id=r["exam_id"], exam_type=r["exam_type"],
                        language="cpp11", code_file="", code=r["code"], compile_log=None, test_report=None,
                        labels=normalize_labels(r["labels"])) for r in rows]
```

- [ ] **Step 3: Viết `scripts/augment_task2_api.py`**

```python
"""Optional: generate API bug-injection mutants of the LABELLED gold samples (never test inputs).
Writes a JSON list for configs/task2/clm_*.yaml `augment.api_path`. --preflight never calls an API."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from src.llm.api_client import GeminiBackend, QuotaExhausted  # noqa: E402
from src.llm.openai_client import CostLimitReached, OpenAIBackend  # noqa: E402
from src.task2.augment_api import generate_mutants, plan_jobs  # noqa: E402
from src.task2.data import load_task2  # noqa: E402
from src.task2.labels import LABELS  # noqa: E402
from src.utils.config import load_config, load_dotenv  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-config", default=str(ROOT / "configs" / "task2" / "run_api.yaml"))
    ap.add_argument("--provider", choices=("gemini", "openai"))
    ap.add_argument("--gold-root", default=str(ROOT / "data" / "raw" / "sample_dataset"))
    ap.add_argument("--labels", nargs="*", default=list(LABELS))
    ap.add_argument("--per-label", type=int, default=6)
    ap.add_argument("--output", default=str(ROOT / "outputs" / "task2" / "augment_api" / "mutants.json"))
    ap.add_argument("--preflight", action="store_true")
    a = ap.parse_args()
    load_dotenv()
    settings = load_config(a.run_config)
    provider = a.provider or settings.get("provider", "gemini")
    gold = load_task2(a.gold_root)
    out = Path(a.output)
    done = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    have = {r["sample_id"] for r in done}
    jobs = [(s, lab) for s, lab in plan_jobs(gold.samples, a.labels, a.per_label)
            if f"{s.sample_id}~api-{LABELS.index(lab)}" not in have]
    print(json.dumps({"provider": provider, "model": settings[provider]["model"], "existing": len(done),
                      "new_requests": len(jobs)}, ensure_ascii=False))
    if a.preflight or not jobs:
        return
    backend = GeminiBackend(**settings["gemini"]) if provider == "gemini" else OpenAIBackend(**settings["openai"])
    gen = {"temperature": 0.7, "max_new_tokens": 4096, "n": 1, "seed": 42}
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        for k in range(0, len(jobs), 8):  # checkpoint every 8 requests
            done += generate_mutants(gold, jobs[k:k + 8], backend, gen)
            out.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    except (QuotaExhausted, CostLimitReached) as exc:
        print(f"DỪNG: {exc}. Đã lưu {len(done)} mẫu; chạy lại sẽ làm tiếp.")
    print(f"{len(done)} mutants -> {out}  usage: {json.dumps(backend.info().get('usage'))}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: GREEN + preflight + commit**

```bash
.venv/bin/python -m pytest tests/test_task2_augment_api.py -q
.venv/bin/python scripts/augment_task2_api.py --preflight
git add src/task2/augment_api.py scripts/augment_task2_api.py tests/test_task2_augment_api.py
git commit -m "Add optional API bug-injection augmentation of gold Task 2 code"
```
Expected preflight: in `new_requests` ≈ 10 nhãn × tối đa 6 (không gọi API).

---

### Task 4: Hướng 2 — k-fold CV trên gold + augmentation (`run_clm` mới)

**Files:**
- Modify: `src/task2/clm/experiment.py` (viết lại `run_clm`, thêm `kfold_ids`, đổi `SYSTEMS`; giữ `embed_candidates`, `embed_samples`, `_select_public`, `_gold_matrix`)
- Modify: `scripts/run_task2_clm.py`, `configs/task2/clm_base.yaml`, `configs/task2/clm_local.yaml`, `configs/task2/clm_kaggle.yaml`
- Test: `tests/test_task2_clm_experiment.py` (viết lại)

**Interfaces:**
- Consumes: `augment`, `source_id` (Task 2); `load_mutants` (Task 3); `NoulModel.from_checkpoint`, `TrainConfig`, `train_noul(model, S, C, Y, cfg, eval_fn=None)`, `predict_noul`, `LinearProbe` (`src/task2/clm/heads.py`); `tune_thresholds`, `apply_thresholds`; `f1_scores`, `write_submission`.
- Produces:
  - `SYSTEMS = ("clm_zero_shot", "clm_noul", "clm_noul_aug", "probe", "probe_aug")`.
  - `kfold_ids(ids: list[str], k: int, seed: int) -> list[list[str]]` (k fold rời nhau, phủ đủ, deterministic; `k` bị giới hạn ≤ số id).
  - `run_clm(cfg, encoder, heads_path, gold, public, out_dir, mutants=(), registry=REGISTRY) -> dict` — `metrics.json` = `{"name", "n_gold", "n_mutants", "cv_folds", "evaluation": "out-of-fold over gold", "systems": {"<sys>@0.5": f1, "<sys>@tuned": f1}, "history": {"folds": [...], "final": {...}}, "final_system"}`; ghi `thresholds.json`, `resources.json` (khoá như cũ, `n_samples` = gold + mutants + public), `config.json`, `clm_noul_heads.pt`, `clm_noul_aug_heads.pt`, và nếu có public: `predictions.json`, `predictions_full.json`.
  - Config keys: `cv.folds` (mặc định 4), `augment.rules` (bool), `augment.max_per_mutator` (int|null), `augment.api_path` (str|null), `final_system` (mặc định `clm_noul_aug`, phải thuộc `SYSTEMS`, sai thì `ValueError`).

- [ ] **Step 1: Viết lại test (RED)**

`tests/test_task2_clm_experiment.py`:
```python
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from src.task2.augment import augment
from src.task2.clm.encoder import CachedEncoder
from src.task2.clm.experiment import SYSTEMS, kfold_ids, run_clm
from src.task2.data import load_task2
from src.task2.evaluator import validate_predictions
from tests._task2 import FakeEncoder, make_dataset, make_fake_heads

CFG = {"name": "task2_clm_test", "seed": 42, "data": {"public_per_exam": None},
       "text": {"max_tokens": 512, "max_statement_tokens": 64},
       "train": {"epochs": 2, "lr": 1e-3, "batch_size": 16}, "probe": {"C": 1.0},
       "thresholds": {"min_rate": 0.0, "default": 0.5}, "cv": {"folds": 3}, "final_system": "clm_noul_aug"}
GOLD = [("G1", "EXA", ["Lỗi logic"]), ("G2", "EXA", []), ("G3", "EXB", ["Lỗi hàm", "Lỗi logic"]),
        ("G4", "EXB", ["Lỗi biên dịch"]), ("G5", "EXA", ["Lỗi logic"]), ("G6", "EXB", [])]


class TestKfold(unittest.TestCase):
    def test_disjoint_cover_deterministic(self):
        ids = [f"S{i}" for i in range(10)]
        folds = kfold_ids(ids, 4, 42)
        self.assertEqual(len(folds), 4)
        self.assertEqual(sorted(sum(folds, [])), sorted(ids))
        self.assertEqual(folds, kfold_ids(list(reversed(ids)), 4, 42))
        self.assertEqual(len(kfold_ids(ids[:2], 4, 42)), 2)


class TestRunClm(unittest.TestCase):
    def test_end_to_end_cv_with_mutants(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gold = load_task2(make_dataset(tmp / "g", GOLD))
            public = load_task2(make_dataset(tmp / "p", [("P1", "EXA", None), ("P2", "EXB", None)]))
            mutants = augment(gold.samples)
            self.assertGreater(len(mutants), 0)
            leaked = replace(mutants[0], sample_id="P1~strip_indentation")  # not from a gold source
            m = run_clm(CFG, CachedEncoder(FakeEncoder(dim=16), tmp / "c"), make_fake_heads(tmp / "h.pt"), gold,
                        public, tmp / "out", [*mutants, leaked], registry=None)
            for system in SYSTEMS:
                for suffix in ("@0.5", "@tuned"):
                    self.assertEqual(m["systems"][system + suffix]["n"], 6)
            self.assertEqual(m["n_gold"], 6)
            self.assertEqual(m["n_mutants"], len(mutants))  # the non-gold-source mutant was dropped
            self.assertEqual(m["cv_folds"], 3)
            self.assertEqual(len(m["history"]["folds"]), 3 * 2)  # (no-aug, aug) per fold
            sub = json.loads((tmp / "out" / "predictions.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_predictions(sub, ["P1", "P2"]), [])
            res = json.loads((tmp / "out" / "resources.json").read_text(encoding="utf-8"))
            self.assertEqual(res["n_samples"], 6 + len(mutants) + 2)
            for f in ("clm_noul_heads.pt", "clm_noul_aug_heads.pt", "thresholds.json", "metrics.json"):
                self.assertTrue((tmp / "out" / f).exists(), f)

    def test_missing_checkpoint_fails_before_embedding(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gold = load_task2(make_dataset(tmp / "g", GOLD))
            fake = FakeEncoder()
            with self.assertRaises(Exception):
                run_clm(CFG, CachedEncoder(fake, tmp / "c"), tmp / "missing.pt", gold, None, tmp / "o", (),
                        registry=None)
            self.assertEqual(fake.calls, 0)

    def test_unknown_final_system_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gold = load_task2(make_dataset(tmp / "g", GOLD))
            with self.assertRaises(ValueError):
                run_clm({**CFG, "final_system": "nope"}, CachedEncoder(FakeEncoder(), tmp / "c"),
                        make_fake_heads(tmp / "h.pt"), gold, None, tmp / "o", (), registry=None)

    def test_public_per_exam_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gold = load_task2(make_dataset(tmp / "g", GOLD))
            public = load_task2(make_dataset(tmp / "p", [("P1", "EXA", None), ("P2", "EXA", None),
                                                         ("P3", "EXB", None)]))
            run_clm({**CFG, "data": {"public_per_exam": 1}}, CachedEncoder(FakeEncoder(), tmp / "c"),
                    make_fake_heads(tmp / "h.pt"), gold, public, tmp / "o", (), registry=None)
            ids = [r["sample_id"] for r in json.loads((tmp / "o" / "predictions.json").read_text(encoding="utf-8"))]
            self.assertEqual(ids, ["P1", "P3"])
```

Run: `.venv/bin/python -m pytest tests/test_task2_clm_experiment.py -q` → FAIL (`ImportError: kfold_ids`).

- [ ] **Step 2: Viết lại phần dưới `_gold_matrix` trong `src/task2/clm/experiment.py`**

Docstring đầu file thành:
```python
"""Task 2 Hướng 2 end to end (no test-derived labels — instructor ruling 2026-10-11):
embed gold + bug-injection mutants of gold + public (cached) -> k-fold CV on gold giving out-of-fold
probabilities for zero-shot CLM / fine-tuned CLM / linear probe, each with and without augmentation
-> per-label thresholds from OOF -> final models on all gold -> public predictions."""
```
Thêm import `from src.task2.augment import source_id`; đổi `SYSTEMS`; giữ nguyên `embed_candidates`, `embed_samples`, `_select_public`, `_gold_matrix`; thay toàn bộ `run_clm` bằng:
```python
SYSTEMS = ("clm_zero_shot", "clm_noul", "clm_noul_aug", "probe", "probe_aug")


def kfold_ids(ids, k: int, seed: int) -> list[list[str]]:
    ids = sorted(ids)
    k = max(1, min(int(k), len(ids)))
    perm = np.random.default_rng(seed).permutation(len(ids))
    return [sorted(ids[i] for i in perm[f::k]) for f in range(k)]


def run_clm(cfg: dict, encoder, heads_path, gold, public, out_dir, mutants=(),
            registry: Path | None = REGISTRY) -> dict:
    seed = int(cfg.get("seed", 42))
    set_seed(seed)
    final = cfg.get("final_system", "clm_noul_aug")
    if final not in SYSTEMS:
        raise ValueError(f"final_system={final!r} not in {SYSTEMS}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    text_cfg = cfg.get("text", {})
    gold_s = sorted((s for s in gold.samples if s.has_gold), key=lambda s: s.sample_id)
    gold_ids = {s.sample_id for s in gold_s}
    mutants = [m for m in mutants if source_id(m.sample_id) in gold_ids]  # never anything test-derived
    pub = _select_public(public, (cfg.get("data") or {}).get("public_per_exam")) if public else []

    # 0. fail fast on a wrong / missing checkpoint, before hours of embedding
    zero = NoulModel.from_checkpoint(heads_path)

    # 1. embeddings (frozen encoder, cached on disk)
    t0 = time.time()
    C = embed_candidates(encoder)
    dim = C.shape[-1]
    e_gold = embed_samples(gold_s, gold.exams, encoder, text_cfg, dim)
    e_mut = embed_samples(mutants, gold.exams, encoder, text_cfg, dim)
    e_pub = embed_samples(pub, public.exams if public else {}, encoder, text_cfg, dim)
    embed_seconds = time.time() - t0
    Y_gold, Y_mut = _gold_matrix(gold_s), _gold_matrix(mutants)
    src_mut = np.array([source_id(m.sample_id) for m in mutants])
    tcfg = TrainConfig(**{**(cfg.get("train") or {}), "seed": seed})
    probe_c = float((cfg.get("probe") or {}).get("C", 1.0))

    def fit(rows: np.ndarray, with_aug: bool):
        """Train CLM heads + probe on gold rows (+ mutants whose source gold sample is among those rows)."""
        S, X, Y = e_gold["S"][rows], e_gold["X"][rows], Y_gold[rows]
        if with_aug and len(mutants):
            keep = np.isin(src_mut, [gold_s[i].sample_id for i in rows])
            S = np.concatenate([S, e_mut["S"][keep]])
            X = np.concatenate([X, e_mut["X"][keep]])
            Y = np.concatenate([Y, Y_mut[keep]])
        model = NoulModel.from_checkpoint(heads_path)
        hist = train_noul(model, S, C, Y, tcfg)
        return model, LinearProbe(C=probe_c, seed=seed).fit(X, Y), hist, int(len(S))

    def probe_proba(probe, X) -> np.ndarray:
        return probe.predict_proba(X) if len(X) else np.zeros((0, len(LABELS)), np.float32)

    # 2. k-fold CV -> out-of-fold probabilities for every gold sample
    n = len(gold_s)
    pos = {s.sample_id: i for i, s in enumerate(gold_s)}
    folds = kfold_ids(list(pos), int((cfg.get("cv") or {}).get("folds", 4)), seed)
    oof = {system: np.zeros((n, len(LABELS)), np.float32) for system in SYSTEMS}
    oof["clm_zero_shot"] = predict_noul(zero, e_gold["S"], C)
    fold_hist = []
    t1 = time.time()
    for f, held in enumerate(folds):
        te = np.array([pos[i] for i in held])
        tr = np.array([i for i in range(n) if i not in set(te.tolist())])
        for with_aug, (s_clm, s_probe) in ((False, ("clm_noul", "probe")), (True, ("clm_noul_aug", "probe_aug"))):
            model, probe, hist, n_fit = fit(tr, with_aug)
            oof[s_clm][te] = predict_noul(model, e_gold["S"][te], C)
            oof[s_probe][te] = probe_proba(probe, e_gold["X"][te])
            fold_hist.append({"fold": f, "augment": with_aug, "n_train": n_fit, "loss": hist["loss"]})
    cv_seconds = time.time() - t1

    # 3. thresholds from OOF; metrics = OOF over all gold (@tuned is optimistic: same rows)
    th = cfg.get("thresholds") or {}
    gold_map = {s.sample_id: s.labels for s in gold_s}

    def score(P, thr) -> dict:
        pred = apply_thresholds(P, thr)
        return f1_scores(gold_map, {s.sample_id: from_vector(r) for s, r in zip(gold_s, pred)})

    thresholds, systems = {}, {}
    for system in SYSTEMS:
        thr = tune_thresholds(oof[system], Y_gold >= 0.5, default=float(th.get("default", 0.5)))
        thresholds[system] = thr.tolist()
        systems[f"{system}@0.5"] = score(oof[system], np.full(len(LABELS), 0.5))
        systems[f"{system}@tuned"] = score(oof[system], thr)

    # 4. final models on all gold (+ all mutants), public predictions
    t2 = time.time()
    rows = np.arange(n)
    m_plain, p_plain, h_plain, n_plain = fit(rows, False)
    m_aug, p_aug, h_aug, n_aug = fit(rows, True)
    train_seconds = time.time() - t2
    if pub:
        P_pub = {"clm_zero_shot": predict_noul(zero, e_pub["S"], C), "clm_noul": predict_noul(m_plain, e_pub["S"], C),
                 "clm_noul_aug": predict_noul(m_aug, e_pub["S"], C), "probe": probe_proba(p_plain, e_pub["X"]),
                 "probe_aug": probe_proba(p_aug, e_pub["X"])}
        pred = apply_thresholds(P_pub[final], np.array(thresholds[final]), float(th.get("min_rate", 0.0)))
        labels = {s.sample_id: from_vector(r) for s, r in zip(pub, pred)}
        write_submission(out_dir / "predictions.json", labels, [s.sample_id for s in pub])
        _write_json(out_dir / "predictions_full.json", [
            {"sample_id": s.sample_id, "exam_id": s.exam_id, "labels": labels[s.sample_id],
             "probs": {system: dict(zip(LABELS, np.round(P_pub[system][k], 4).tolist())) for system in SYSTEMS}}
            for k, s in enumerate(pub)])
    torch.save(m_plain.state_dict(), out_dir / "clm_noul_heads.pt")
    torch.save(m_aug.state_dict(), out_dir / "clm_noul_aug_heads.pt")

    n_samples = n + len(mutants) + len(pub)
    peak = encoder.peak_memory_gb() if hasattr(encoder, "peak_memory_gb") else None
    resources = {"backend": "clm", "model": getattr(encoder, "encoder_id", ""), "hardware": hardware_info(),
                 "n_samples": n_samples,
                 "seconds_per_sample": (getattr(encoder, "seconds", embed_seconds) / n_samples) if n_samples else None,
                 "embed_seconds_total": embed_seconds, "n_encoded": getattr(encoder, "n_computed", None),
                 "n_cache_hits": getattr(encoder, "n_hits", None), "cv_seconds": cv_seconds,
                 "train_seconds": train_seconds, "peak_memory_gb": peak, "tokens_in": None, "tokens_out": None,
                 "cost_usd": 0.0}
    metrics = {"name": cfg["name"], "n_gold": n, "n_mutants": len(mutants), "cv_folds": len(folds),
               "evaluation": "out-of-fold over gold", "systems": systems,
               "history": {"folds": fold_hist, "final": {"clm_noul": {"n_train": n_plain, "loss": h_plain["loss"]},
                                                         "clm_noul_aug": {"n_train": n_aug, "loss": h_aug["loss"]}}},
               "final_system": final}
    _write_json(out_dir / "metrics.json", metrics)
    _write_json(out_dir / "thresholds.json", {s: dict(zip(LABELS, t)) for s, t in thresholds.items()})
    _write_json(out_dir / "resources.json", resources)
    _write_json(out_dir / "config.json", {"config": cfg, "heads": str(heads_path),
                                          "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                                          "folds": folds, "mutant_ids": [m.sample_id for m in mutants],
                                          "public_ids": [s.sample_id for s in pub]})
    if registry is not None:
        best = systems.get(f"{final}@tuned") or {}
        append_registry({"experiment_id": cfg["name"], "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                         "task": "task2", "model": resources["model"], "config_path": cfg.get("_config_path", ""),
                         "train_loss": h_aug["loss"][-1] if h_aug["loss"] else "",
                         "metrics": json.dumps({"macro_f1_oof_tuned": best.get("macro_f1"),
                                                "micro_f1_oof_tuned": best.get("micro_f1"),
                                                "n_gold": n, "n_mutants": len(mutants), "cv_folds": len(folds)}),
                         "git_commit": _git_commit(), "notes": cfg.get("description", "")}, registry)
    return metrics
```
Xoá các import không còn dùng nếu có.

- [ ] **Step 3: Sửa `scripts/run_task2_clm.py`**

- Bỏ import `json`/`load_split` nếu không còn dùng; thêm `from src.task2.augment import augment` và `from src.task2.augment_api import load_mutants`.
- Bỏ đối số `--silver`; thêm `ap.add_argument("--augment-api", help="mutants.json from scripts/augment_task2_api.py (overrides config augment.api_path)")`.
- Thay khối split/silver và lời gọi `run_clm` bằng:
```python
    aug = cfg.get("augment") or {}
    mutants = augment(gold.samples, max_per_mutator=aug.get("max_per_mutator")) if aug.get("rules", True) else []
    api_path = a.augment_api or aug.get("api_path")
    if api_path:
        api_path = Path(api_path) if Path(api_path).is_absolute() else ROOT / api_path
        mutants += load_mutants(api_path)
    print(f"augmentation: {len(mutants)} mutants of gold code (rules={aug.get('rules', True)}, api={api_path or '-'})")
    encoder, heads = build_encoder(cfg["encoder"], int(cfg["text"]["max_tokens"]))
    enc = CachedEncoder(encoder, ROOT / cfg.get("cache_dir", "outputs/task2/_emb_cache"))
    out_dir = Path(a.output_dir) / cfg["name"]
    m = run_clm(cfg, enc, heads, gold, public, out_dir, mutants)
    for key, v in m["systems"].items():
        print(f"{key:24s} macro-F1={v['macro_f1']:.3f}  micro-F1={v['micro_f1']:.3f}  exact={v['exact_match']:.2f}")
    print(f"outputs -> {out_dir}  (metrics: out-of-fold over {m['n_gold']} gold, {m['cv_folds']} folds)")
```

- [ ] **Step 4: Sửa config**

`configs/task2/clm_base.yaml`: xoá khối `silver:`; thêm
```yaml
cv:
  folds: 4                    # k-fold over the 32 gold samples (out-of-fold metrics + thresholds)
augment:
  rules: true                 # src/task2/augment.py bug injection on gold code (never test inputs)
  max_per_mutator: null       # null = every applicable gold sample
  api_path: null              # optional mutants.json from scripts/augment_task2_api.py
```
và `final_system: clm_noul_aug`; mô tả: `Hướng 2 — CLM-8B (Qwen3-8B frozen + head), câu hỏi noul cho từng nhãn; train trên 32 bài gold + mẫu chèn lỗi, đánh giá k-fold; probe tuyến tính làm ablation.`
`configs/task2/clm_local.yaml`: mô tả `Chạy tối thiểu trên Mac (MLX 4-bit) — 32 bài gold + ≤4 mẫu chèn lỗi mỗi luật + 1 bài public mỗi đề, ít epoch.`; thêm `augment: {max_per_mutator: 4}` (YAML khối).
`configs/task2/clm_kaggle.yaml`: mô tả `Chạy đầy đủ trên Kaggle T4x2 — Qwen3-8B fp16 + head CLM gốc, 32 bài gold + mọi mẫu chèn lỗi, 360 bài public.`

- [ ] **Step 5: GREEN + toàn bộ suite + commit**

```bash
.venv/bin/python -m pytest tests/test_task2_clm_experiment.py -q
.venv/bin/python -m pytest tests/ -q
grep -rn "silver" src scripts configs tests || echo "no silver left"
git add src/task2/clm/experiment.py scripts/run_task2_clm.py configs/task2/clm_*.yaml tests/test_task2_clm_experiment.py
git commit -m "Evaluate Task 2 CLM by k-fold CV on gold with bug-injection augmentation"
```
Expected: suite = baseline (2 lỗi có sẵn) + test mới pass; `no silver left`.

---

### Task 5: Notebook Kaggle, docs, README

**Files:**
- Modify: `kaggle/task2_clm.ipynb` (tái tạo JSON bằng script như lần trước; giữ 7 cell), `docs/task2.md`, `README.md`

- [ ] **Step 1: Notebook** — đọc notebook hiện tại; bỏ biến `SILVER_PATH` và mọi nhắc tới silver; cell cấu hình thay bằng `AUGMENT_API_PATH = ''  # optional mutants.json (Kaggle dataset) from scripts/augment_task2_api.py`; lệnh chạy: `args = ['--config', 'configs/task2/clm_kaggle.yaml'] + (['--augment-api', AUGMENT_API_PATH] if AUGMENT_API_PATH else [])`; cell markdown: bỏ mục silver, thêm 1 dòng "Không dùng nhãn sinh trên tập test (quy định của giảng viên); train = 32 bài gold + mẫu chèn lỗi". Giữ nguyên phần `/kaggle/tmp`, secret, pin transformers. Kiểm tra: JSON parse được, 7 cell, `git ls-files | xargs grep -l 1gfMQ9` rỗng.
- [ ] **Step 2: `docs/task2.md`** — viết lại các phần nhắc silver:
  - Mục Dữ liệu: nhãn = 32 bài gold; **không** dùng nhãn sinh trên input tập test (phán quyết giảng viên 2026-10-11); Hướng 1 dự đoán 360 bài chỉ để nộp.
  - Mục Hướng 1: `run.predict: true` → `outputs/task2/task2_api_predict__*/predictions.json` (n=5 bỏ phiếu); bỏ `silver_labels.json`; chi phí ước tính giữ nguyên số ($0.85–1.25, `max_usd` 3.0) nhưng gọi là "lượt dự đoán 360×5".
  - Mục Hướng 2: hệ thống `clm_zero_shot`, `clm_noul`, `clm_noul_aug`, `probe`, `probe_aug`; đánh giá = k-fold (4) out-of-fold trên 32 bài gold; augmentation 9 luật (bảng luật → nhãn, ghi rõ không có luật cho `Lỗi thuật toán`), tuỳ chọn API `python scripts/augment_task2_api.py --preflight` / `--provider gemini`, rồi `augment.api_path` hoặc `--augment-api`; mẫu chèn lỗi chỉ vào fold train khi bài gốc thuộc fold train.
  - Mục Kết quả local: giữ bảng cũ dưới tiêu đề "Lần chạy 2026-10-09 (thiết kế cũ, 6 bài val)"; thêm tiêu đề "Lần chạy CV + augmentation" với dòng `<chờ kết quả Task 6>` — Task 6 sẽ thay dòng này.
  - Mục Rủi ro: thêm "lỗi chèn nhân tạo có thể khác cách giảng viên gán nhãn; so `*_aug` với bản không aug trong ablation"; "nên hỏi giảng viên xác nhận augmentation từ bộ mẫu".
- [ ] **Step 3: `README.md`** — dòng Task 2 trong Overview: `Hướng 1 prompts an API LLM (Gemini/OpenAI) for the submission; Hướng 2 fine-tunes the CLM-8B heads (frozen Qwen3-8B, MLX locally / Kaggle GPU) on the 32 labelled samples plus bug-injection augmentation, evaluated by k-fold CV, with a linear-probe ablation. No labels are derived from the test set. See docs/task2.md.`
- [ ] **Step 4: Kiểm tra + commit**

```bash
grep -rn "silver" kaggle docs/task2.md README.md || echo "no silver left"
.venv/bin/python -c "import json; nb=json.load(open('kaggle/task2_clm.ipynb')); print(len(nb['cells']))"
git ls-files | xargs grep -l 1gfMQ9 || echo "no drive id"
git add kaggle/task2_clm.ipynb docs/task2.md README.md
git commit -m "Update Task 2 notebook and docs: no silver, gold CV, augmentation"
```

---

### Task 6: Chạy local (controller) và cập nhật số liệu

**Files:** chỉ `docs/task2.md` (thay dòng `<chờ kết quả Task 6>`), `experiments/registry.csv`.

- [ ] **Step 1:** `time .venv/bin/python scripts/run_task2_clm.py --config configs/task2/clm_local.yaml` (embedding gold đã có cache; chỉ mẫu chèn lỗi và public mới phải encode — khoảng ≤36 × 11 lần encode).
- [ ] **Step 2:** `.venv/bin/python scripts/task2_benchmark.py`; kiểm tra `predictions.json` hợp lệ.
- [ ] **Step 3:** Thay `<chờ kết quả Task 6>` trong `docs/task2.md` bằng bảng benchmark mới + số mẫu chèn lỗi, thời gian, ghi chú (OOF trên 32 bài, `@tuned` lạc quan). Commit docs và `experiments/registry.csv` (hai commit riêng).
