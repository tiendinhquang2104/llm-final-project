"""Local chat LLMs behind the same `generate(requests, gen) -> list[list[str]]` interface as the API backends.

MLX (Apple Silicon, 4-bit) for local checks, Hugging Face transformers for Kaggle GPUs. Heavy imports happen in
the constructors so tests and --preflight never load a model.
"""
from __future__ import annotations

import platform
import time
import zlib
from pathlib import Path

from src.llm.api_client import Backend


class LocalChatBackend(Backend):
    name = "local"

    def __init__(self, model: str, hardware: str = ""):
        self.model = model
        self.hardware = hardware or f"{platform.system()} {platform.machine()}"
        self.revision: str | None = None  # resolved model commit, filled by subclasses when known
        self.usage = {"requests": 0, "prompt_tokens": 0, "output_tokens": 0}
        self.ledger: list[dict] = []  # one row per completion; run_api appends it to usage.jsonl
        self.top_p = 1.0  # set from gen["top_p"] by generate()

    def _complete(self, messages: list[dict], temperature: float, max_tokens: int, seed: int) -> tuple[str, int, int]:
        """One answer: (text, prompt_tokens, output_tokens). Sampling uses self.top_p when temperature > 0."""
        raise NotImplementedError

    def _complete_n(self, messages: list[dict], temperature: float, max_tokens: int, seed: int,
                    n: int) -> list[tuple[str, int, int, float]]:
        """n answers: [(text, prompt_tokens, output_tokens, seconds)]. Default: n sequential calls with seeds
        seed..seed+n-1; HFChatBackend overrides it with one batched generate call."""
        res = []
        for k in range(n):
            t0 = time.time()
            text, p_tok, o_tok = self._complete(messages, temperature, max_tokens, seed + k)
            res.append((text, p_tok, o_tok, time.time() - t0))
        return res

    def peak_memory_gb(self) -> float | None:
        return None

    def generate(self, requests: list[dict], gen: dict) -> list[list[str]]:
        n = int(gen.get("n", 1))
        temperature = float(gen.get("temperature", 0.0))
        max_tokens = int(gen.get("max_new_tokens", 1024))
        base = int(gen.get("seed", 42))
        self.top_p = float(gen.get("top_p", 1.0))
        if n > 1 and temperature <= 0:
            raise ValueError("n > 1 cần temperature > 0 (greedy cho ra n câu trả lời giống nhau)")
        out = []
        for i, r in enumerate(requests):
            sid = getattr(r.get("sample"), "sample_id", f"#{i}")
            sample_seed = base + (zlib.crc32(sid.encode()) % 100_000) * 10  # stable across cache chunks
            t0 = time.time()
            res = self._complete_n(r["messages"], temperature, max_tokens, sample_seed, n)
            for k, (_, p_tok, o_tok, dt) in enumerate(res):
                self.usage["requests"] += 1
                self.usage["prompt_tokens"] += p_tok
                self.usage["output_tokens"] += o_tok
                self.ledger.append({"sample_id": sid, "vote": k, "prompt_tokens": p_tok, "output_tokens": o_tok,
                                    "seconds": round(dt, 2), "hit_max_tokens": o_tok >= max_tokens,
                                    "temperature": temperature, "top_p": self.top_p, "seed": sample_seed + k})
            total = time.time() - t0
            outs = [o for _, _, o, _ in res]
            cut = sum(o >= max_tokens for o in outs)
            print(f"  {sid}" + (f" x{n}" if n > 1 else "") + f": vào {res[0][1]} token, ra "
                  + ("/".join(map(str, outs)) if n > 1 else str(outs[0]))
                  + f" token, {total:.1f}s, {sum(outs) / max(total, 1e-9):.1f} tok/s"
                  + (f" ({cut} câu chạm max_new_tokens)" if cut else ""), flush=True)
            out.append([t for t, _, _, _ in res])
        return out

    def info(self) -> dict:
        return {**super().info(), "model": self.model, "revision": self.revision, "hardware": self.hardware,
                "usage": dict(self.usage), "peak_memory_gb": self.peak_memory_gb()}


def _snapshot_revision(path) -> str | None:
    """Commit hash of a Hugging Face cache snapshot dir (.../snapshots/<sha>), else None."""
    p = Path(path)
    return p.name if p.parent.name == "snapshots" else None


class MLXChatBackend(LocalChatBackend):
    name = "mlx"

    def __init__(self, model: str = "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit", hardware: str = ""):
        super().__init__(model, hardware)
        import mlx.core as mx
        from mlx_lm import load

        self.mx = mx
        if Path(model).exists():
            resolved = Path(model)
        else:
            from huggingface_hub import snapshot_download
            resolved = Path(snapshot_download(model))
        self.revision = _snapshot_revision(resolved)
        self.lm, self.tok = load(str(resolved))

    def _complete(self, messages, temperature, max_tokens, seed):
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        self.mx.random.seed(seed)
        prompt = self.tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
        sampler = make_sampler(temp=temperature, top_p=self.top_p if temperature > 0 else 1.0)
        text = generate(self.lm, self.tok, prompt, max_tokens=max_tokens, sampler=sampler)
        return text, len(self.tok.encode(prompt)), len(self.tok.encode(text))

    def peak_memory_gb(self):
        fn = getattr(self.mx, "get_peak_memory", None) or self.mx.metal.get_peak_memory
        return fn() / 2**30


class HFChatBackend(LocalChatBackend):
    name = "hf"

    def __init__(self, model: str = "Qwen/Qwen2.5-Coder-7B-Instruct", dtype: str = "float16",
                 load_in_4bit: bool = False, revision: str | None = None, hardware: str = ""):
        super().__init__(model, hardware)
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        kw = {"device_map": "auto", "revision": revision}
        if load_in_4bit:
            from transformers import BitsAndBytesConfig
            kw["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
        else:
            kw["torch_dtype"] = getattr(torch, dtype)
        self.lm = AutoModelForCausalLM.from_pretrained(model, **kw).eval()
        self.tok = AutoTokenizer.from_pretrained(model, revision=revision)
        self.revision = revision or getattr(self.lm.config, "_commit_hash", None)
        eos = getattr(self.lm.generation_config, "eos_token_id", None)
        self.eos_ids = set(eos if isinstance(eos, list) else [eos]) | {self.tok.eos_token_id}
        self.eos_ids.discard(None)
        if torch.cuda.is_available() and not hardware:
            self.hardware = f"{torch.cuda.get_device_name(0)} x{torch.cuda.device_count()}"

    def _complete(self, messages, temperature, max_tokens, seed):
        return self._generate(messages, temperature, max_tokens, seed, 1)[0][:3]

    def _complete_n(self, messages, temperature, max_tokens, seed, n):
        return self._generate(messages, temperature, max_tokens, seed, n)

    def _generate(self, messages, temperature, max_tokens, seed, n):
        """One generate call for n answers (num_return_sequences): the prompt is prefilled once and the n answers
        are decoded as a batch, so self-consistency costs far less than n separate calls."""
        torch = self.torch
        torch.manual_seed(seed)
        enc = self.tok.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt",
                                           return_dict=True).to(self.lm.device)
        kw = ({"do_sample": True, "temperature": temperature, "top_p": self.top_p, "num_return_sequences": n}
              if temperature > 0 else {"do_sample": False})
        t0 = time.time()
        with torch.no_grad():
            out = self.lm.generate(**enc, max_new_tokens=max_tokens, pad_token_id=self.tok.eos_token_id, **kw)
        dt = (time.time() - t0) / n
        p_tok = int(enc["input_ids"].shape[1])
        res = []
        for row in out[:, p_tok:].tolist():
            o_tok = next((i + 1 for i, t in enumerate(row) if t in self.eos_ids), len(row))  # rest is padding
            res.append((self.tok.decode(row[:o_tok], skip_special_tokens=True), p_tok, o_tok, dt))
        return res

    def save(self, out_dir) -> Path:
        """Write the weights + tokenizer actually used, so the bundle runs offline later."""
        out_dir = Path(out_dir)
        self.lm.save_pretrained(out_dir, safe_serialization=True)
        self.tok.save_pretrained(out_dir)
        return out_dir

    def peak_memory_gb(self):
        t = self.torch
        if not t.cuda.is_available():
            return None
        return sum(t.cuda.max_memory_allocated(i) for i in range(t.cuda.device_count())) / 2**30


def make_local_backend(kind: str, settings: dict) -> LocalChatBackend:
    cls = {"mlx": MLXChatBackend, "hf": HFChatBackend}[kind]
    return cls(**settings.get(kind, {}))
