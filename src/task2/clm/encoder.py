"""Frozen Qwen3-8B encoder for CLM: last-token hidden state after the final norm, float32, L2-normalised.

Two backends producing the same kind of vectors:
  * MLXEncoder — Apple Silicon, the 4-bit `mlx-community/CLM-v0.1-8B-MLX-4bit` encoder (logic follows that
    repo's clm_mlx/encoder.py, Apache-2.0: head truncation, right padding, last real token);
  * HFEncoder  — CUDA (Kaggle), `Qwen/Qwen3-8B` via transformers.
CachedEncoder stores every embedding on disk, so re-runs and new heads never re-encode.
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

import numpy as np


class HFTokenizer:
    def __init__(self, tok):
        self.tok = tok

    def encode(self, text: str) -> list[int]:
        return list(self.tok(text, add_special_tokens=True)["input_ids"])

    def decode(self, ids: list[int]) -> str:
        return self.tok.decode(ids, skip_special_tokens=False)


def _l2(v: np.ndarray) -> np.ndarray:
    return (v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-12)).astype(np.float32)


class CachedEncoder:
    def __init__(self, encoder, cache_dir):
        self.encoder = encoder
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.encoder_id = encoder.encoder_id
        self.tokenizer = encoder.tokenizer
        self.n_hits = self.n_computed = 0
        self.seconds = 0.0

    def _path(self, text: str) -> Path:
        key = hashlib.sha256(f"{self.encoder_id}\n{text}".encode("utf-8")).hexdigest()[:32]
        return self.cache_dir / key[:2] / f"{key}.npy"

    @staticmethod
    def _load(p: Path):
        if not p.exists():
            return None
        try:
            return np.load(p)
        except (ValueError, OSError, EOFError):  # corrupt / truncated entry: treat as a miss
            return None

    def embed(self, texts: list[str]) -> np.ndarray:
        vecs: dict[str, np.ndarray] = {}
        todo = []
        for t in dict.fromkeys(texts):
            p = self._path(t)
            v = self._load(p)
            if v is None:
                todo.append(t)
            else:
                vecs[t] = v
                self.n_hits += 1
        if todo:
            t0 = time.time()
            got = _l2(np.asarray(self.encoder.embed(todo), dtype=np.float32))
            self.seconds += time.time() - t0
            self.n_computed += len(todo)
            for t, v in zip(todo, got):
                p = self._path(t)
                p.parent.mkdir(parents=True, exist_ok=True)
                tmp = p.with_name(p.name + f".{os.getpid()}.tmp")
                with open(tmp, "wb") as f:  # atomic: a killed run never leaves a half-written .npy
                    np.save(f, v)
                os.replace(tmp, p)
                vecs[t] = v
        if not texts:
            return np.zeros((0, 0), np.float32)
        return np.stack([vecs[t] for t in texts])

    def peak_memory_gb(self):
        fn = getattr(self.encoder, "peak_memory_gb", None)
        return fn() if fn else None


class MLXEncoder:
    def __init__(self, model_dir, max_tokens: int = 2048, batch_tokens: int = 4096):
        import mlx.core as mx
        import mlx.nn as nn
        from mlx_lm import load
        from transformers import AutoTokenizer

        self.mx = mx
        loaded = load(str(model_dir), lazy=True)
        model = loaded[0]
        if hasattr(model, "lm_head"):
            model.lm_head = nn.Identity()  # never used; skip loading it
        model.eval()
        mx.eval(model.model.parameters())
        self.model, self.max_tokens, self.batch_tokens = model, max_tokens, batch_tokens
        self.tokenizer = HFTokenizer(AutoTokenizer.from_pretrained(str(model_dir)))
        self.encoder_id = f"mlx4bit:{Path(model_dir).resolve().parent.name}:{max_tokens}"

    def _ids(self, text: str) -> list[int]:
        ids = self.tokenizer.encode(text) or self.tokenizer.encode(" ")
        return ids[:self.max_tokens]  # head truncation, as the reference vLLM server

    def embed(self, texts: list[str]) -> np.ndarray:
        mx = self.mx
        id_lists = [self._ids(t) for t in texts]
        order = sorted(range(len(id_lists)), key=lambda i: len(id_lists[i]))
        out: list = [None] * len(id_lists)
        i = 0
        while i < len(order):
            j = i + 1
            while j < len(order) and (j - i + 1) * len(id_lists[order[j]]) <= self.batch_tokens:
                j += 1
            rows = [id_lists[k] for k in order[i:j]]
            width = len(rows[-1])
            x = mx.array([r + [0] * (width - len(r)) for r in rows], dtype=mx.int32)  # right padding
            h = self.model.model(x)  # [b, L, hidden] after the final norm
            last = mx.array([len(r) - 1 for r in rows], dtype=mx.int32)
            idx = mx.broadcast_to(last[:, None, None], (len(rows), 1, h.shape[-1]))
            v = mx.take_along_axis(h, idx, axis=1)[:, 0].astype(mx.float32)
            mx.eval(v)
            arr = np.array(v)
            for k, r in zip(order[i:j], range(len(rows))):
                out[k] = arr[r]
            i = j
        return _l2(np.stack(out))

    def peak_memory_gb(self):
        mx = self.mx
        fn = getattr(mx, "get_peak_memory", None) or mx.metal.get_peak_memory
        return fn() / 2**30


class HFEncoder:
    def __init__(self, model_id: str = "Qwen/Qwen3-8B", max_tokens: int = 2048, dtype: str = "float16",
                 load_in_8bit: bool = False, batch_size: int = 2):
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.torch = torch
        kw = {"device_map": "auto"}
        if load_in_8bit:
            from transformers import BitsAndBytesConfig
            kw["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        else:
            kw["torch_dtype"] = getattr(torch, dtype)
        self.model = AutoModel.from_pretrained(model_id, **kw).eval()
        self.tokenizer = HFTokenizer(AutoTokenizer.from_pretrained(model_id))
        self.max_tokens, self.batch_size = max_tokens, batch_size
        self.encoder_id = f"hf:{model_id}:{'int8' if load_in_8bit else dtype}:{max_tokens}"

    def embed(self, texts: list[str]) -> np.ndarray:
        torch = self.torch
        ids = [(self.tokenizer.encode(t) or self.tokenizer.encode(" "))[:self.max_tokens] for t in texts]
        order = sorted(range(len(ids)), key=lambda i: len(ids[i]))
        device = self.model.get_input_embeddings().weight.device
        out: list = [None] * len(ids)
        with torch.no_grad():
            for b in range(0, len(order), self.batch_size):
                idx = order[b:b + self.batch_size]
                rows = [ids[i] for i in idx]
                width = max(map(len, rows))
                x = torch.tensor([r + [0] * (width - len(r)) for r in rows], device=device)
                mask = torch.tensor([[1] * len(r) + [0] * (width - len(r)) for r in rows], device=device)
                h = self.model(input_ids=x, attention_mask=mask).last_hidden_state
                last = torch.tensor([len(r) - 1 for r in rows], device=h.device)
                v = h[torch.arange(len(rows), device=h.device), last].float().cpu().numpy()
                if not np.isfinite(v).all():
                    raise RuntimeError("non-finite embeddings (fp16 overflow?) — set encoder.load_in_8bit: true "
                                       "in the config (T4 has no native bfloat16)")
                for i, row in zip(idx, v):
                    out[i] = row
        return _l2(np.stack(out))

    def peak_memory_gb(self):
        torch = self.torch
        return sum(torch.cuda.max_memory_allocated(i) for i in range(torch.cuda.device_count())) / 2**30
