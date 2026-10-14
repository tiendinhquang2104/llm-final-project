# Task 2 Zero-shot CoT (Qwen2.5-Coder-7B-Instruct) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chấm nhãn lỗi Task 2 bằng Qwen2.5-Coder-7B-Instruct chạy local, prompt zero-shot chain-of-thought vai giáo viên, đo macro-F1 trên 32 bài gold và (tuỳ chọn) dự đoán 360 bài public.

**Architecture:** Tái sử dụng pipeline Hướng 1 có sẵn (`Task2ApiPipeline` + `run_api`: cache, retry, vote, metrics, registry). Thêm (1) prompt CoT mới và bộ parse đọc dòng `KẾT LUẬN:`, bật bằng `prompt.style: cot`; (2) backend local `MLXChatBackend` (Mac) / `HFChatBackend` (Kaggle) cùng interface `generate(requests, gen) -> list[list[str]]` như Gemini/OpenAI; (3) script `run_task2_cot.py` + config.

**Tech Stack:** Python 3.10+, `mlx_lm` 0.32 (Mac, model `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit`), `transformers` (Kaggle, `Qwen/Qwen2.5-Coder-7B-Instruct`), `unittest`/pytest.

**Spec:** `docs/task2_prompting.md`

## Global Constraints

- Backbone: Qwen2.5-Coder-7B-Instruct. Không fine-tune, không LoRA.
- Không bao giờ đọc/đưa `feedback` vào prompt; không dùng `test_report`.
- `compile_log` là log tự compile (`attach_compile_logs`, khối `compile` trong `configs/task2/base.yaml`).
- Zero-shot: không có demo, không tham số nào chọn trên gold → được chấm trên **cả 32 gold**.
- Chỉnh prompt trên silver (`--gold-root <thư mục silver>`), không chỉnh theo điểm gold; không bao giờ nhìn đầu ra public để chọn cấu hình.
- Không dùng 360 bài public làm ví dụ hay nhãn (quy định giảng viên 2026-10-11).
- Claude **không commit**; cuối mỗi task chỉ liệt kê file để người dùng tự commit.
- Test chạy bằng `.venv/bin/python -m pytest`.

## File Structure

| File | Trách nhiệm |
|---|---|
| Create `src/task2/prompts_cot.py` | System prompt giáo viên, 7 bước chấm, dòng `KẾT LUẬN:`; `build_cot_messages` |
| Modify `src/task2/pipeline.py` | `parse_cot_labels`; switch `prompt.style` (json/cot) cho build_request + parse |
| Create `src/llm/local_backend.py` | `LocalChatBackend` (vòng n, seed, usage), `MLXChatBackend`, `HFChatBackend`, `make_local_backend` |
| Modify `src/task2/api_experiment.py:84-86` | `resources.json` lấy `hardware`/`peak_memory_gb` từ backend (không cố định "API") |
| Create `configs/task2/cot_zero_shot.yaml`, `configs/task2/run_cot.yaml` | Cấu hình prompt/generation và backend/run |
| Create `scripts/run_task2_cot.py` | CLI: preflight, smoke, chấm gold, dự đoán public |
| Create `tests/test_task2_cot.py` | Test prompt, parse, pipeline, backend, run_api end-to-end bằng backend giả |
| Modify `docs/task2_prompting.md` | Mục "Chạy" + bảng kết quả |

---

### Task 1: Prompt CoT + parser + switch trong pipeline

**Files:**
- Create: `src/task2/prompts_cot.py`
- Modify: `src/task2/pipeline.py`
- Test: `tests/test_task2_cot.py`

**Interfaces:**
- Consumes: `src.task2.prompts.LABEL_GUIDE`, `exam_text(exam)`, `submission_text(sample, cfg)` (đánh số dòng, thêm compile_log khi `use_aux_signals: true`); `src.task2.pipeline.parse_labels`.
- Produces: `FINAL_MARKER = "KẾT LUẬN:"`, `SYSTEM_COT: str`, `build_cot_messages(exam: dict, sample, cfg: dict) -> list[dict]`, `parse_cot_labels(text: str) -> list[str] | None`, `Task2ApiPipeline.parse` (callable), config key `prompt.style` ∈ {`json`, `cot`} (mặc định `json`, hành vi cũ không đổi).

- [ ] **Step 1: Viết test fail**

```python
# tests/test_task2_cot.py
import json
import tempfile
import unittest
from pathlib import Path

from src.task2.data import load_task2
from src.task2.labels import LABELS
from src.task2.pipeline import Task2ApiPipeline, parse_cot_labels
from src.task2.prompts_cot import FINAL_MARKER, SYSTEM_COT
from tests._task2 import FakeBackend, make_dataset

COT_CFG = {"name": "t_cot", "prompt": {"style": "cot", "few_shot_k": 0, "max_code_chars": 4000,
                                       "use_aux_signals": True},
           "generation": {"temperature": 0.0, "n": 1, "max_new_tokens": 512}, "retry_on_parse_fail": 1}


def cot_answer(*labels):
    return ("1. Biên dịch: không lỗi.\n3. Vòng lặp: `for (i = 0; i <= n; i++) { s += a[i]; }` lặp thừa.\n"
            f'{FINAL_MARKER} {json.dumps({"taxonomy_error": list(labels)}, ensure_ascii=False)}')


class TestCotParse(unittest.TestCase):
    def test_reads_final_line_despite_code_braces(self):
        self.assertEqual(parse_cot_labels(cot_answer("Lỗi vòng lặp", "Lỗi style")), ["Lỗi vòng lặp", "Lỗi style"])

    def test_empty_list_is_valid(self):
        self.assertEqual(parse_cot_labels(cot_answer()), [])

    def test_fallback_plain_json(self):  # retry answers are bare JSON without the marker
        self.assertEqual(parse_cot_labels('{"taxonomy_error": ["Lỗi hàm"]}'), ["Lỗi hàm"])

    def test_fallback_last_line_with_key(self):
        text = 'phân tích...\n{"taxonomy_error": ["Lỗi logic"]}'
        self.assertEqual(parse_cot_labels(text), ["Lỗi logic"])

    def test_unparseable(self):
        self.assertIsNone(parse_cot_labels("chưa kết luận"))


class TestCotPrompt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ds = load_task2(make_dataset(Path(self.tmp.name), [("A1", "EXA", ["Lỗi logic"]),
                                                                ("A2", "EXA", [])]))
        self.by = self.ds.by_id()
        self.by["A1"].compile_log = "student.cpp:3:5: error: 'x' was not declared"

    def tearDown(self):
        self.tmp.cleanup()

    def test_messages(self):
        pipe = Task2ApiPipeline(self.ds, None, COT_CFG, demo_pool=self.ds.samples)
        req = pipe.build_request(self.by["A1"])
        self.assertEqual(req["demos"], [])            # zero-shot even if a pool is passed
        self.assertIsNone(req["schema"])
        system, user = req["messages"][0]["content"], req["messages"][1]["content"]
        self.assertEqual(system, SYSTEM_COT)
        self.assertIn("giảng viên", system)
        for lab in LABELS:
            self.assertIn(lab, system)
        self.assertIn("was not declared", user)       # compile_log block
        self.assertIn(FINAL_MARKER, user)
        self.assertIn("7.", user)                     # seven grading steps
        self.assertNotIn("feedback", (system + user).lower())

    def test_json_style_unchanged(self):
        cfg = {**COT_CFG, "prompt": {**COT_CFG["prompt"], "style": "json"}}
        req = Task2ApiPipeline(self.ds, None, cfg).build_request(self.by["A1"])
        self.assertIsNotNone(req["schema"])
        self.assertNotIn(FINAL_MARKER, req["messages"][1]["content"])

    def test_infer_and_postprocess_use_cot_parser(self):
        backend = FakeBackend([cot_answer("Lỗi logic"), "rác", '{"taxonomy_error": []}'])
        pipe = Task2ApiPipeline(self.ds, backend, COT_CFG)
        recs = pipe.infer([self.by["A1"], self.by["A2"]])
        p1, p2 = pipe.postprocess(recs[0]), pipe.postprocess(recs[1])
        self.assertEqual(p1["labels"], ["Lỗi logic"])
        self.assertTrue(p2["parse_ok"])               # recovered by the retry
        self.assertEqual(p2["labels"], [])
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `.venv/bin/python -m pytest tests/test_task2_cot.py -v`
Expected: FAIL với `ImportError: cannot import name 'parse_cot_labels'` / `No module named 'src.task2.prompts_cot'`

- [ ] **Step 3: Viết `src/task2/prompts_cot.py`**

```python
"""Task 2 prompting: zero-shot chain-of-thought with a teacher persona (docs/task2_prompting.md).
Pure functions of (exam, sample, cfg); never use `feedback`."""
from __future__ import annotations

from src.task2.prompts import LABEL_GUIDE, exam_text, submission_text

FINAL_MARKER = "KẾT LUẬN:"

SYSTEM_COT = (
    "Bạn là giảng viên môn Lập trình C++ nhập môn, đang chấm bài nộp của sinh viên. "
    "Nhiệm vụ: xác định TẤT CẢ các loại lỗi có trong bài, theo đúng danh sách nhãn bên dưới. "
    "Một bài có thể có 0, 1 hoặc nhiều lỗi. Bài đúng hoàn toàn thì trả về danh sách rỗng.\n\n"
    "DANH SÁCH NHÃN (chỉ dùng đúng tên này):\n" + LABEL_GUIDE + "\n\n"
    "NGUYÊN TẮC CHẤM:\n"
    "- Chỉ gán nhãn khi chỉ ra được dòng code cụ thể gây lỗi. Không đoán.\n"
    '- Nếu compile_log có "error" thì chắc chắn có "Lỗi biên dịch". Cảnh báo (warning) thì không tính.\n'
    '- Bám sát yêu cầu đề: làm khác yêu cầu (ví dụ đề bắt dùng đệ quy mà dùng vòng lặp) là "Lỗi thuật toán".'
)

STEPS = (
    "Biên dịch: compile_log có lỗi không?",
    "Nhập/xuất: đọc dữ liệu và định dạng in ra có khớp đề không?",
    "Vòng lặp và mảng/chuỗi: chỉ số, điều kiện dừng, kích thước có đúng không?",
    "Hàm: prototype, kiểu trả về, return, cách truyền tham số có đúng không?",
    "Logic, edge case, hard-code: có nhánh/công thức sai, bỏ sót trường hợp biên, hoặc gán cứng kết quả không?",
    "Thuật toán: cách làm và cấu trúc dữ liệu có đúng yêu cầu đề không?",
    "Style: đặt tên, thụt lề, code lặp, biến toàn cục có chấp nhận được không?",
)


def cot_instruction() -> str:
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(STEPS, 1))
    return ("## CÁCH CHẤM\nHãy chấm theo từng bước, mỗi bước ghi ngắn gọn bằng chứng (số dòng / đoạn code):\n"
            f"{steps}\n\nCuối cùng viết đúng một dòng, không thêm gì sau nó:\n"
            f'{FINAL_MARKER} {{"taxonomy_error": ["<nhãn>", ...]}}\n'
            "Chỉ dùng đúng tên nhãn trong danh sách; [] nếu bài không có lỗi.")


def build_cot_messages(exam: dict, sample, cfg: dict) -> list[dict]:
    user = "\n".join([exam_text(exam), submission_text(sample, cfg), cot_instruction()])
    return [{"role": "system", "content": SYSTEM_COT}, {"role": "user", "content": user}]
```

- [ ] **Step 4: Sửa `src/task2/pipeline.py`**

Thêm import và hàm parse ngay dưới `parse_labels`:

```python
from src.task2.prompts_cot import FINAL_MARKER, build_cot_messages
```

```python
def parse_cot_labels(text: str) -> list[str] | None:
    """CoT answer: labels from the JSON after the last `KẾT LUẬN:`; else from the last line naming
    `taxonomy_error`; else anywhere (bare-JSON retry answers). Reasoning may quote code with braces,
    so the whole text is the last resort only."""
    text = text or ""
    if FINAL_MARKER in text:
        got = parse_labels(text.rsplit(FINAL_MARKER, 1)[1])
        if got is not None:
            return got
    lines = [ln for ln in text.splitlines() if "taxonomy_error" in ln]
    if lines:
        got = parse_labels(lines[-1])
        if got is not None:
            return got
    return parse_labels(text)
```

Trong `Task2ApiPipeline.__init__` thêm:

```python
        self.style = self.prompt_cfg.get("style", "json")
        self.parse = parse_cot_labels if self.style == "cot" else parse_labels
```

Thay thân `build_request`:

```python
    def build_request(self, sample) -> dict:
        exam = self.ds.exams[sample.exam_id]
        if self.style == "cot":  # zero-shot CoT: no demos, free-text reasoning then the KẾT LUẬN line
            return {"sample": sample, "exam": exam, "demos": [],
                    "messages": build_cot_messages(exam, sample, self.prompt_cfg),
                    "schema": None, "schema_name": "task2_cot"}
        demos = select_demos(self.demo_pool, sample, int(self.prompt_cfg.get("few_shot_k", 0)))
        return {"sample": sample, "exam": exam, "demos": [d.sample_id for d in demos],
                "messages": build_messages(exam, sample, demos, self.prompt_cfg),
                "schema": RESPONSE_SCHEMA, "schema_name": "task2_labels"}
```

Trong `infer` và `postprocess`, đổi mọi `parse_labels(` / `map(parse_labels, ...)` thành `self.parse(` / `map(self.parse, ...)` (3 chỗ: điều kiện `bad` trong `infer`, hai dòng `parsed` trong `postprocess`).

- [ ] **Step 5: Chạy test, xác nhận pass (kể cả test cũ của pipeline)**

Run: `.venv/bin/python -m pytest tests/test_task2_cot.py tests/test_task2_api_pipeline.py tests/test_task2_api_experiment.py -v`
Expected: PASS tất cả

- [ ] **Step 6: Báo người dùng commit** `src/task2/prompts_cot.py src/task2/pipeline.py tests/test_task2_cot.py`

---

### Task 2: Backend LLM local (MLX / HF)

**Files:**
- Create: `src/llm/local_backend.py`
- Test: `tests/test_task2_cot.py` (thêm class)

**Interfaces:**
- Consumes: `src.llm.api_client.Backend` (interface `generate`, `info`).
- Produces: `LocalChatBackend(model: str, hardware: str = "")` với hook `_complete(messages, temperature, max_tokens, seed) -> tuple[str, int, int]` (text, prompt_tokens, output_tokens) và `peak_memory_gb() -> float | None`; `generate(requests, gen) -> list[list[str]]`; `info()` có `backend, model, hardware, usage{requests,prompt_tokens,output_tokens}, peak_memory_gb`. `MLXChatBackend(model=..., hardware="")`, `HFChatBackend(model=..., dtype="float16", load_in_4bit=False, hardware="")`, `make_local_backend(kind: str, settings: dict) -> LocalChatBackend`.

- [ ] **Step 1: Viết test fail** (thêm vào `tests/test_task2_cot.py`)

```python
from types import SimpleNamespace

from src.llm.local_backend import LocalChatBackend


class ScriptedLocal(LocalChatBackend):
    name = "scripted"

    def __init__(self):
        super().__init__("fake-qwen", hardware="test-box")
        self.seen = []

    def _complete(self, messages, temperature, max_tokens, seed):
        self.seen.append((messages[-1]["content"], temperature, max_tokens, seed))
        return f"out{len(self.seen)}", 10, 3


def req(sid):
    return {"sample": SimpleNamespace(sample_id=sid), "messages": [{"role": "user", "content": sid}]}


class TestLocalBackend(unittest.TestCase):
    def test_n_samples_usage_and_info(self):
        b = ScriptedLocal()
        out = b.generate([req("A"), req("B")], {"n": 2, "temperature": 0.7, "max_new_tokens": 64, "seed": 1})
        self.assertEqual(out, [["out1", "out2"], ["out3", "out4"]])
        self.assertEqual(b.usage, {"requests": 4, "prompt_tokens": 40, "output_tokens": 12})
        info = b.info()
        self.assertEqual((info["backend"], info["model"], info["hardware"]), ("scripted", "fake-qwen", "test-box"))
        self.assertIsNone(info["peak_memory_gb"])

    def test_seeds_differ_per_vote_and_are_stable_per_sample(self):
        b1, b2 = ScriptedLocal(), ScriptedLocal()
        gen = {"n": 2, "temperature": 0.7, "seed": 5}
        b1.generate([req("A"), req("B")], gen)
        b2.generate([req("B")], gen)          # same sample in another chunk -> same seeds
        seeds1 = {(c, s) for c, _, _, s in b1.seen}
        self.assertEqual(len({s for _, s in seeds1}), 4)
        self.assertEqual({s for c, s in seeds1 if c == "B"}, {s for _, _, _, s in b2.seen})

    def test_greedy_with_n_gt_1_rejected(self):
        with self.assertRaises(ValueError):
            ScriptedLocal().generate([req("A")], {"n": 3, "temperature": 0.0})
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `.venv/bin/python -m pytest tests/test_task2_cot.py::TestLocalBackend -v`
Expected: FAIL `No module named 'src.llm.local_backend'`

- [ ] **Step 3: Viết `src/llm/local_backend.py`**

```python
"""Local chat LLMs behind the same `generate(requests, gen) -> list[list[str]]` interface as the API backends.

MLX (Apple Silicon, 4-bit) for local runs, Hugging Face transformers for Kaggle GPUs. Heavy imports happen in
the constructors so tests and --preflight never load a model.
"""
from __future__ import annotations

import platform
import time
import zlib

from src.llm.api_client import Backend


class LocalChatBackend(Backend):
    name = "local"

    def __init__(self, model: str, hardware: str = ""):
        self.model = model
        self.hardware = hardware or f"{platform.system()} {platform.machine()}"
        self.usage = {"requests": 0, "prompt_tokens": 0, "output_tokens": 0}

    def _complete(self, messages: list[dict], temperature: float, max_tokens: int, seed: int) -> tuple[str, int, int]:
        raise NotImplementedError

    def peak_memory_gb(self) -> float | None:
        return None

    def generate(self, requests: list[dict], gen: dict) -> list[list[str]]:
        n = int(gen.get("n", 1))
        temperature = float(gen.get("temperature", 0.0))
        max_tokens = int(gen.get("max_new_tokens", 1024))
        base = int(gen.get("seed", 42))
        if n > 1 and temperature <= 0:
            raise ValueError("n > 1 cần temperature > 0 (greedy cho ra n câu trả lời giống nhau)")
        out = []
        for i, r in enumerate(requests):
            sid = getattr(r.get("sample"), "sample_id", f"#{i}")
            sample_seed = base + (zlib.crc32(sid.encode()) % 100_000) * 10  # stable across cache chunks
            texts = []
            for k in range(n):
                t0 = time.time()
                text, p_tok, o_tok = self._complete(r["messages"], temperature, max_tokens, sample_seed + k)
                self.usage["requests"] += 1
                self.usage["prompt_tokens"] += p_tok
                self.usage["output_tokens"] += o_tok
                print(f"  {sid}" + (f"[{k + 1}/{n}]" if n > 1 else "") + f": {o_tok} token, {time.time() - t0:.1f}s",
                      flush=True)
                texts.append(text)
            out.append(texts)
        return out

    def info(self) -> dict:
        return {**super().info(), "model": self.model, "hardware": self.hardware, "usage": dict(self.usage),
                "peak_memory_gb": self.peak_memory_gb()}


class MLXChatBackend(LocalChatBackend):
    name = "mlx"

    def __init__(self, model: str = "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit", hardware: str = ""):
        super().__init__(model, hardware)
        import mlx.core as mx
        from mlx_lm import load

        self.mx = mx
        self.lm, self.tok = load(model)

    def _complete(self, messages, temperature, max_tokens, seed):
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        self.mx.random.seed(seed)
        prompt = self.tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
        text = generate(self.lm, self.tok, prompt, max_tokens=max_tokens, sampler=make_sampler(temp=temperature))
        return text, len(self.tok.encode(prompt)), len(self.tok.encode(text))

    def peak_memory_gb(self):
        fn = getattr(self.mx, "get_peak_memory", None) or self.mx.metal.get_peak_memory
        return fn() / 2**30


class HFChatBackend(LocalChatBackend):
    name = "hf"

    def __init__(self, model: str = "Qwen/Qwen2.5-Coder-7B-Instruct", dtype: str = "float16",
                 load_in_4bit: bool = False, hardware: str = ""):
        super().__init__(model, hardware)
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        kw = {"device_map": "auto"}
        if load_in_4bit:
            from transformers import BitsAndBytesConfig
            kw["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
        else:
            kw["torch_dtype"] = getattr(torch, dtype)
        self.lm = AutoModelForCausalLM.from_pretrained(model, **kw).eval()
        self.tok = AutoTokenizer.from_pretrained(model)
        if torch.cuda.is_available() and not hardware:
            self.hardware = f"{torch.cuda.get_device_name(0)} x{torch.cuda.device_count()}"

    def _complete(self, messages, temperature, max_tokens, seed):
        torch = self.torch
        torch.manual_seed(seed)
        enc = self.tok.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt",
                                           return_dict=True).to(self.lm.device)
        kw = {"do_sample": True, "temperature": temperature, "top_p": 0.95} if temperature > 0 else {"do_sample": False}
        with torch.no_grad():
            out = self.lm.generate(**enc, max_new_tokens=max_tokens, pad_token_id=self.tok.eos_token_id, **kw)
        new = out[0, enc["input_ids"].shape[1]:]
        return self.tok.decode(new, skip_special_tokens=True), int(enc["input_ids"].shape[1]), int(len(new))

    def peak_memory_gb(self):
        t = self.torch
        if not t.cuda.is_available():
            return None
        return sum(t.cuda.max_memory_allocated(i) for i in range(t.cuda.device_count())) / 2**30


def make_local_backend(kind: str, settings: dict) -> LocalChatBackend:
    cls = {"mlx": MLXChatBackend, "hf": HFChatBackend}[kind]
    return cls(**settings.get(kind, {}))
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `.venv/bin/python -m pytest tests/test_task2_cot.py -v`
Expected: PASS

- [ ] **Step 5: Báo người dùng commit** `src/llm/local_backend.py tests/test_task2_cot.py`

---

### Task 3: `run_api` ghi đúng phần cứng/bộ nhớ của backend local

**Files:**
- Modify: `src/task2/api_experiment.py` (khối `resources = {...}`, khoảng dòng 84-86)
- Test: `tests/test_task2_cot.py` (thêm class)

**Interfaces:**
- Consumes: `run_api(cfg, dataset, samples, backend, out_dir, demo_pool=(), registry=REGISTRY, use_cache=True) -> dict`; `backend.info()` có thể có `hardware`, `peak_memory_gb`.
- Produces: `resources.json` với `hardware = info.get("hardware", "API")`, `peak_memory_gb = info.get("peak_memory_gb")` (giá trị sau khi chạy). Backend API cũ không có hai khoá này → kết quả giữ nguyên ("API", null).

- [ ] **Step 1: Viết test fail (end-to-end với backend giả)**

```python
from src.task2.api_experiment import run_api


class TestRunApiCot(unittest.TestCase):
    def test_end_to_end_metrics_and_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds = load_task2(make_dataset(Path(tmp) / "d", [("A1", "EXA", ["Lỗi logic"]), ("A2", "EXA", [])]))

            class Answering(ScriptedLocal):
                def _complete(self, messages, temperature, max_tokens, seed):
                    super()._complete(messages, temperature, max_tokens, seed)
                    return cot_answer("Lỗi logic"), 10, 3

            m = run_api(COT_CFG, ds, ds.samples, Answering(), Path(tmp) / "out", registry=None)
            self.assertEqual(m["parse_failures"], 0)
            self.assertIn("macro_f1", m["systems"]["api"])
            res = json.loads((Path(tmp) / "out" / "resources.json").read_text(encoding="utf-8"))
            self.assertEqual(res["hardware"], "test-box")
            self.assertEqual(res["tokens_out"], 6)
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `.venv/bin/python -m pytest tests/test_task2_cot.py::TestRunApiCot -v`
Expected: FAIL `AssertionError: 'API' != 'test-box'`

- [ ] **Step 3: Sửa `src/task2/api_experiment.py`**

Thay:

```python
    resources = {"backend": info.get("backend"), "model": info.get("model"), "hardware": "API",
                 "n_samples": len(samples), "seconds_per_sample": seconds,
                 "train_seconds": None, "peak_memory_gb": None, **totals}
```

bằng:

```python
    info_after = backend.info()  # local backends report their hardware and peak memory; API backends do not
    resources = {"backend": info.get("backend"), "model": info.get("model"),
                 "hardware": info_after.get("hardware", "API"),
                 "n_samples": len(samples), "seconds_per_sample": seconds,
                 "train_seconds": None, "peak_memory_gb": info_after.get("peak_memory_gb"), **totals}
```

- [ ] **Step 4: Chạy toàn bộ test Task 2, xác nhận pass**

Run: `.venv/bin/python -m pytest tests/test_task2_cot.py tests/test_task2_api_experiment.py tests/test_task2_api_pipeline.py tests/test_task2_run_api_script.py -v`
Expected: PASS

- [ ] **Step 5: Báo người dùng commit** `src/task2/api_experiment.py tests/test_task2_cot.py`

---

### Task 4: Config + script `run_task2_cot.py` + docs

**Files:**
- Create: `configs/task2/cot_zero_shot.yaml`, `configs/task2/run_cot.yaml`, `scripts/run_task2_cot.py`
- Modify: `docs/task2_prompting.md` (thêm mục "Chạy")

**Interfaces:**
- Consumes: `load_task2`, `attach_compile_logs(compile_cfg, [list, list], enabled=..., root=...) -> (lists, compiler_id)`, `Task2ApiPipeline`, `run_api`, `make_local_backend`, `load_config`.
- Produces: CLI `scripts/run_task2_cot.py [--backend mlx|hf] [--preflight] [--smoke] [--limit N] [--gold-root DIR] [--public-root DIR] [--no-compile] [--output-dir DIR]`; thư mục kết quả `outputs/task2/task2_cot_zero_shot__<backend>__<model>/` (cùng định dạng run API: `predictions.json`, `metrics.json`, `resources.json`, `raw_outputs.jsonl`).

- [ ] **Step 1: Tạo `configs/task2/cot_zero_shot.yaml`**

```yaml
extends: base.yaml
name: task2_cot_zero_shot
description: Zero-shot chain-of-thought, vai giảng viên, 7 bước chấm rồi dòng KẾT LUẬN; có compile_log tự compile; không demo, không test_report.
prompt:
  style: cot
  few_shot_k: 0
  max_code_chars: 12000
  use_aux_signals: true
generation:
  temperature: 0.0     # zero-shot greedy; self-consistency (bước sau) = n: 5, temperature: 0.7
  max_new_tokens: 1024
  enable_thinking: false
  n: 1
retry_on_parse_fail: 1
checkpoint_every: 4
```

- [ ] **Step 2: Tạo `configs/task2/run_cot.yaml`**

```yaml
# Runtime settings for scripts/run_task2_cot.py (local Qwen2.5-Coder-7B-Instruct, no API key).
backend: mlx                  # override with --backend hf (Kaggle GPU)
mlx:
  model: mlx-community/Qwen2.5-Coder-7B-Instruct-4bit
hf:
  model: Qwen/Qwen2.5-Coder-7B-Instruct
  dtype: float16
  load_in_4bit: false         # true nếu GPU < 16 GB
run:
  experiment: cot_zero_shot   # evaluated on all 32 gold (zero-shot: nothing is tuned on gold)
  smoke_sample_ids: [EX02-S201]
  predict: false              # true: also label the 360 public samples (predictions.json for submission)
  use_cache: true
output_dir: outputs/task2
```

- [ ] **Step 3: Tạo `scripts/run_task2_cot.py`**

```python
"""Task 2 zero-shot CoT with a local Qwen2.5-Coder-7B-Instruct (MLX on Mac, transformers on Kaggle).
--preflight builds prompts and prints the first one; it never loads a model."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from src.llm.local_backend import make_local_backend  # noqa: E402
from src.task2.api_experiment import run_api  # noqa: E402
from src.task2.compile import attach_compile_logs  # noqa: E402
from src.task2.data import load_task2  # noqa: E402
from src.task2.pipeline import Task2ApiPipeline  # noqa: E402
from src.utils.config import load_config  # noqa: E402

CONFIG_DIR = ROOT / "configs" / "task2"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-config", default=str(CONFIG_DIR / "run_cot.yaml"))
    ap.add_argument("--backend", choices=("mlx", "hf"))
    ap.add_argument("--gold-root", help="Labelled set to score (default: 32 gold; point at silver to tune the prompt)")
    ap.add_argument("--public-root")
    ap.add_argument("--output-dir")
    ap.add_argument("--preflight", action="store_true", help="Build prompts, print the first one; no model")
    ap.add_argument("--smoke", action="store_true", help="Only run.smoke_sample_ids, no public run")
    ap.add_argument("--limit", type=int, help="Only the first N labelled samples")
    ap.add_argument("--no-compile", action="store_true", help="No self-compiled compile_log (ablation / fallback)")
    a = ap.parse_args()
    settings = load_config(a.run_config)
    kind = a.backend or settings.get("backend", "mlx")
    run = settings["run"]
    base = load_config(CONFIG_DIR / "base.yaml")
    gold = load_task2(ROOT / (a.gold_root or base["data"]["gold_root"]))
    public = None
    if run.get("predict") and not (a.smoke or a.preflight):
        public = load_task2(ROOT / (a.public_root or base["data"]["public_root"]))
    compile_on = not (a.no_compile or a.preflight)
    lists, compiler_id = attach_compile_logs(base.get("compile"), [gold.samples, public.samples if public else []],
                                             enabled=compile_on, root=ROOT)
    gold.samples[:] = lists[0]
    if public:
        public.samples[:] = lists[1]
    samples = [gold.by_id()[i] for i in run["smoke_sample_ids"]] if a.smoke else gold.samples[:a.limit]

    path = CONFIG_DIR / f"{run['experiment']}.yaml"
    cfg = load_config(path)
    cfg["_config_path"] = str(path.relative_to(ROOT))
    tag = re.sub(r"[^A-Za-z0-9._-]+", "-", settings[kind]["model"])
    cfg["name"] += ("_smoke" if a.smoke else "") + ("_silver" if a.gold_root else "") + f"__{kind}__{tag}"

    pipe = Task2ApiPipeline(gold, None, cfg)
    first = pipe.build_request(samples[0])["messages"]
    chars = sum(len(m["content"]) for s in samples for m in pipe.build_request(s)["messages"])
    print(json.dumps({"backend": kind, "model": settings[kind]["model"], "compiler": compiler_id,
                      "n_labelled": len(samples), "n_public": len(public.samples) if public else 0,
                      "approx_input_tokens": chars // 3}, ensure_ascii=False, indent=2))
    if a.preflight:
        print("\n=== SYSTEM ===\n" + first[0]["content"] + "\n\n=== USER ===\n" + first[1]["content"])
        return

    backend = make_local_backend(kind, settings)
    out = Path(a.output_dir) if a.output_dir else ROOT / settings.get("output_dir", "outputs/task2")
    m = run_api(cfg, gold, samples, backend, out / cfg["name"], use_cache=run.get("use_cache", True))
    api = m["systems"].get("api") or {}
    print(f"{cfg['name']}: macro-F1={api.get('macro_f1')} micro-F1={api.get('micro_f1')} "
          f"parse_fail={m['parse_failures']}")
    if public:
        pcfg = {**cfg, "name": cfg["name"] + "_predict"}
        run_api(pcfg, public, public.samples, backend, out / pcfg["name"], use_cache=run.get("use_cache", True))
        print(f"predictions -> {out / pcfg['name']}")
    print(f"{kind} usage: {json.dumps(backend.info().get('usage'))}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Kiểm tra preflight (không tải model)**

Run: `.venv/bin/python scripts/run_task2_cot.py --preflight`
Expected: JSON với `n_labelled: 32`, rồi in SYSTEM (vai giảng viên, 10 nhãn) và USER (đề EX01, code đánh số dòng, 7 bước, dòng `KẾT LUẬN:`); không có chữ `feedback`.

- [ ] **Step 5: Smoke 1 bài trên Mac** (lần đầu tải ~4.3 GB model MLX: hỏi người dùng trước khi chạy)

Run: `.venv/bin/python scripts/run_task2_cot.py --smoke`
Expected: in `EX02-S201: <k> token, <t>s`, rồi `task2_cot_zero_shot_smoke__mlx__...: macro-F1=... parse_fail=0`. Mở `outputs/task2/task2_cot_zero_shot_smoke__mlx__*/raw_outputs.jsonl` đọc lời chấm: có đủ các bước và dòng `KẾT LUẬN:`. Nếu `parse_fail=1`, sửa prompt (không sửa parser cho khớp một câu trả lời).

- [ ] **Step 6: Chạy 32 gold** (ước tính ~15–25 phút trên M3 Pro)

Run: `.venv/bin/python scripts/run_task2_cot.py`
Expected: `macro-F1`, `micro-F1`, `parse_fail` in ra; `metrics.json`, `resources.json` (hardware, peak_memory_gb, tokens) trong thư mục kết quả.

- [ ] **Step 7: Thêm mục "Chạy" vào `docs/task2_prompting.md`** (ngay trước "## Ví dụ prompt")

```markdown
## Chạy (zero-shot CoT)

Code: `src/task2/prompts_cot.py` (prompt), `src/task2/pipeline.py` (`prompt.style: cot`, `parse_cot_labels`),
`src/llm/local_backend.py` (MLX/HF), `scripts/run_task2_cot.py`; config `configs/task2/cot_zero_shot.yaml`,
`configs/task2/run_cot.yaml`.

```bash
.venv/bin/python scripts/run_task2_cot.py --preflight          # in prompt bài đầu, không tải model
.venv/bin/python scripts/run_task2_cot.py --smoke              # 1 bài gold
.venv/bin/python scripts/run_task2_cot.py                      # 32 gold (MLX 4-bit, Mac)
.venv/bin/python scripts/run_task2_cot.py --backend hf         # Kaggle GPU
.venv/bin/python scripts/run_task2_cot.py --gold-root <silver> # chỉnh prompt trên silver
```

Dự đoán 360 bài public: đặt `run.predict: true` trong `configs/task2/run_cot.yaml`.
Zero-shot không chọn gì trên gold nên số trên 32 gold không bị lạc quan như số `@tuned` của CLM.
```

Sau Step 6, thêm bảng kết quả thật (macro-F1, micro-F1, parse_fail, giây/bài, bộ nhớ đỉnh, token vào/ra) lấy từ `metrics.json`/`resources.json`, đặt cạnh `probe_aug` (.287 @0.5 / .362 @tuned, có compile).

- [ ] **Step 8: Báo người dùng commit** `configs/task2/cot_zero_shot.yaml configs/task2/run_cot.yaml scripts/run_task2_cot.py docs/task2_prompting.md`

---

## Ngoài phạm vi plan này (bước sau)

- Self-consistency: chỉ cần config mới (`n: 5`, `temperature: 0.7`); `vote` và ngưỡng 0.5 đã có sẵn.
- RAG few-shot từ gold/silver: plan riêng sau khi có 500 silver.
- Notebook Kaggle cho `--backend hf` nếu chạy 360 bài trên Mac quá chậm (~25 s/bài × 360 ≈ 2.5 giờ với n=1).
