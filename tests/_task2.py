"""Synthetic Task 2 fixtures for offline tests: tiny datasets, tokenizer, encoder, backend and CLM heads."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

EXAMS = {"exams": [
    {"exam_id": "EXA", "exam_type": "single_problem", "course": "Cơ sở lập trình",
     "statement": "Viết chương trình đọc số nguyên n và in tổng các chữ số của n.",
     "problems": [{"pid": "P1", "max_score": 10}]},
    {"exam_id": "EXB", "exam_type": "multi_problem", "course": "Cấu trúc dữ liệu & Giải thuật",
     "statement": "Câu 1: đọc file CSV vào mảng struct. Câu 2: tạo linked list từ mảng.",
     "problems": [{"pid": "P1", "max_score": 5, "is_prerequisite_for": ["P2"]}, {"pid": "P2", "max_score": 5}]},
]}
CODE = "#include <iostream>\nint main() {\n  int n; std::cin >> n;\n  std::cout << n % 10;\n}\n"


def make_dataset(root: Path, samples, code: dict | None = None) -> Path:
    """samples: [(sample_id, exam_id, labels or None)]; None = unlabelled release (no `output`)."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "exams.json").write_text(json.dumps(EXAMS, ensure_ascii=False), encoding="utf-8")
    types = {e["exam_id"]: e["exam_type"] for e in EXAMS["exams"]}
    rows = []
    for sid, eid, labels in samples:
        code_file = f"submissions/{eid}/{sid}.cpp"
        (root / code_file).parent.mkdir(parents=True, exist_ok=True)
        (root / code_file).write_text((code or {}).get(sid, CODE + f"// {sid}\n"), encoding="utf-8")
        row = {"sample_id": sid, "input": {"exam_id": eid, "exam_type": types[eid], "language": "cpp11",
                                           "code_file": code_file, "compile_log": "", "test_report": None}}
        if labels is not None:
            row["output"] = {"taxonomy_error": labels}
        rows.append(row)
    (root / "task2_error_taxonomy.json").write_text(
        json.dumps({"task": "task2", "samples": rows}, ensure_ascii=False), encoding="utf-8")
    return root


class CharTokenizer:
    """One token per character: exact, deterministic token budgets in tests."""

    def encode(self, text: str) -> list[int]:
        return [ord(c) for c in text]

    def decode(self, ids: list[int]) -> str:
        return "".join(chr(i) for i in ids)


class FakeEncoder:
    """Deterministic pseudo-random unit vectors keyed by text."""

    encoder_id = "fake-encoder"

    def __init__(self, dim: int = 16):
        self.dim = dim
        self.tokenizer = CharTokenizer()
        self.calls = 0

    def embed(self, texts: list[str]) -> np.ndarray:
        self.calls += 1
        rows = []
        for t in texts:
            seed = int(hashlib.sha256(t.encode("utf-8")).hexdigest()[:8], 16)
            v = np.random.default_rng(seed).standard_normal(self.dim).astype(np.float32)
            rows.append(v / np.linalg.norm(v))
        return np.stack(rows) if rows else np.zeros((0, self.dim), np.float32)

    def peak_memory_gb(self):
        return None


class FakeBackend:
    """Scripted LLM backend: pops one text per requested sample per n."""

    name = "fake"

    def __init__(self, texts):
        self.texts = list(texts)
        self.calls: list[dict] = []

    def generate(self, requests, gen):
        out = []
        for r in requests:
            self.calls.append(r)
            out.append([self.texts.pop(0) for _ in range(int(gen.get("n", 1)))])
        return out

    def info(self):
        return {"backend": "fake", "model": "fake-1", "usage": {}}


def make_fake_heads(path: Path, hidden: int = 16) -> Path:
    """A CLM-format torch checkpoint with tiny random heads (hidden -> 8 -> 8 -> 4, LayerNorm)."""
    import torch

    from src.task2.clm.heads import Head

    torch.manual_seed(0)
    kw = dict(hidden=hidden, width=8, depth=3, proj=4, activation="gelu", layernorm=True, residual=False)
    torch.save({"state_head": Head(**kw).state_dict(), "action_head": Head(**kw).state_dict(),
                "logit_scale": torch.tensor(math.log(20.0)),
                "cfg": {"width": 8, "depth": 3, "hidden_size": hidden, "projection_dim": 4,
                        "activation": "gelu", "layernorm": True, "residual": False}}, path)
    return path
