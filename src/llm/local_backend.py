"""Local chat LLMs behind the same `generate(requests, gen) -> list[list[str]]` interface as the API backends.

MLX (Apple Silicon, 4-bit) for local checks, Hugging Face transformers for Kaggle GPUs. Heavy imports happen in
the constructors so tests and --preflight never load a model.
"""
from __future__ import annotations

import os
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


OOM_MARK = "[OOM]"  # text of an answer lost to CUDA out-of-memory: never parses, so a rerun retries the sample


class HFChatBackend(LocalChatBackend):
    name = "hf"

    def __init__(self, model: str = "Qwen/Qwen2.5-Coder-7B-Instruct", dtype: str = "float16",
                 load_in_4bit: bool = False, revision: str | None = None, hardware: str = "",
                 gpu_reserve_gb: float = 4.0):
        """`gpu_reserve_gb`: memory left free on every GPU when placing the weights, for the KV cache and the
        attention of long prompts (public prompts reach ~5.8k tokens; 2x T4 OOMed without it)."""
        super().__init__(model, hardware)
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")  # before CUDA init
        import torch
        import transformers
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.oom_error = getattr(torch, "OutOfMemoryError", None) or torch.cuda.OutOfMemoryError
        kw = {"device_map": "auto", "revision": revision}
        if torch.cuda.is_available():
            kw["max_memory"] = {i: f"{max(1.0, torch.cuda.get_device_properties(i).total_memory / 2**30
                                         - gpu_reserve_gb):.1f}GiB" for i in range(torch.cuda.device_count())}
        if load_in_4bit:
            from transformers import BitsAndBytesConfig
            kw["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
        else:
            major, minor = (int(x) for x in transformers.__version__.split(".")[:2])
            kw["dtype" if (major, minor) >= (4, 56) else "torch_dtype"] = getattr(torch, dtype)  # renamed in 4.56
        self.lm = AutoModelForCausalLM.from_pretrained(model, **kw).eval()
        self.tok = AutoTokenizer.from_pretrained(model, revision=revision)
        self.revision = revision or getattr(self.lm.config, "_commit_hash", None)
        eos = getattr(self.lm.generation_config, "eos_token_id", None)
        self.eos_ids = set(eos if isinstance(eos, list) else [eos]) | {self.tok.eos_token_id}
        self.eos_ids.discard(None)
        if torch.cuda.is_available() and not hardware:
            self.hardware = f"{torch.cuda.get_device_name(0)} x{torch.cuda.device_count()}"
        print(f"hf: transformers {transformers.__version__}, torch {torch.__version__}, "
              f"max_memory {kw.get('max_memory')}", flush=True)
        print(f"hf: {self.memory_report()}", flush=True)

    def memory_report(self) -> str:
        """Weights dtype, layers per device and memory per GPU: the first thing to read after an OOM."""
        torch = self.torch
        dtypes = sorted({str(p.dtype).replace("torch.", "") for p in self.lm.parameters()})
        placed: dict[str, int] = {}
        for dev in (getattr(self.lm, "hf_device_map", None) or {}).values():
            placed[str(dev)] = placed.get(str(dev), 0) + 1
        gpus = []
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                free, total = torch.cuda.mem_get_info(i)
                gpus.append(f"cuda:{i} {torch.cuda.memory_allocated(i) / 2**30:.1f} GiB allocated, "
                            f"{free / 2**30:.1f}/{total / 2**30:.1f} GiB free")
        return f"dtype {dtypes}, modules per device {placed}, " + "; ".join(gpus)

    def _free(self):
        import gc
        gc.collect()
        if self.torch.cuda.is_available():
            self.torch.cuda.empty_cache()

    def _oom(self, messages, n: int) -> list[tuple[str, int, int, float]]:
        p_tok = len(self.tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)) // 3
        print(f"  CUDA OOM (prompt ~{p_tok} token): bỏ qua bài này, chạy lại sẽ thử lại. {self.memory_report()}",
              flush=True)
        return [(f"{OOM_MARK} CUDA out of memory, prompt ~{p_tok} token", p_tok, 0, 0.0)] * n

    def _complete(self, messages, temperature, max_tokens, seed):
        try:
            return self._generate(messages, temperature, max_tokens, seed, 1)[0][:3]
        except self.oom_error:
            self._free()
            return self._oom(messages, 1)[0][:3]

    def _complete_n(self, messages, temperature, max_tokens, seed, n):
        """Batched n answers; on OOM falls back to one answer at a time, then to an [OOM] placeholder."""
        try:
            return self._generate(messages, temperature, max_tokens, seed, n)
        except self.oom_error:
            self._free()
            if n == 1:
                return self._oom(messages, 1)
            print(f"  CUDA OOM khi sinh {n} câu cùng lúc: sinh lần lượt từng câu", flush=True)
            res = []
            for k in range(n):
                try:
                    res += self._generate(messages, temperature, max_tokens, seed + k, 1)
                except self.oom_error:
                    self._free()
                    res += self._oom(messages, 1)
            return res

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
        rows = out[:, p_tok:].tolist()
        del out, enc  # drop GPU tensors before the next sample
        res = []
        for row in rows:
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


class VLLMChatBackend(LocalChatBackend):
    """vLLM (Kaggle GPUs): continuous batching over a paged KV cache reserved up front, so a long prompt waits for
    room instead of OOMing. One generate() call schedules all its requests together (the n answers of a prompt
    share its prefill), hence `checkpoint_every`: run_api passes that many samples per call instead of the
    config's 2-4. Greedy answers can differ slightly from the HF backend (batched kernels), so runs are named
    `__vllm__` and never share the HF cache."""
    name = "vllm"

    def __init__(self, model: str = "Qwen/Qwen2.5-Coder-7B-Instruct", dtype: str = "half", revision: str | None = None,
                 hardware: str = "", tensor_parallel_size: int | None = None, gpu_memory_utilization: float = 0.90,
                 max_model_len: int = 16384, max_num_seqs: int | None = None, enforce_eager: bool = False,
                 checkpoint_every: int = 64):
        super().__init__(model, hardware)
        import torch
        import vllm
        from vllm import LLM

        tp = tensor_parallel_size or max(1, torch.cuda.device_count())
        kw = {"model": model, "revision": revision, "dtype": dtype, "tensor_parallel_size": tp,
              "gpu_memory_utilization": gpu_memory_utilization, "max_model_len": max_model_len,
              "enforce_eager": enforce_eager, "disable_custom_all_reduce": True}  # T4 pairs have no NVLink/P2P
        if max_num_seqs:
            kw["max_num_seqs"] = max_num_seqs
        self.llm = LLM(**kw)
        self.tok = self.llm.get_tokenizer()
        self.max_model_len = max_model_len
        self.checkpoint_every = checkpoint_every
        self.revision = revision or _hub_revision(model)
        if torch.cuda.is_available() and not hardware:
            self.hardware = f"{torch.cuda.get_device_name(0)} x{torch.cuda.device_count()}"
        print(f"vllm {vllm.__version__}: tensor_parallel {tp}, max_model_len {max_model_len}, "
              f"gpu_memory_utilization {gpu_memory_utilization}", flush=True)

    def generate(self, requests: list[dict], gen: dict) -> list[list[str]]:
        from vllm import SamplingParams

        n = int(gen.get("n", 1))
        temperature = float(gen.get("temperature", 0.0))
        max_tokens = int(gen.get("max_new_tokens", 1024))
        base = int(gen.get("seed", 42))
        self.top_p = float(gen.get("top_p", 1.0))
        if n > 1 and temperature <= 0:
            raise ValueError("n > 1 cần temperature > 0 (greedy cho ra n câu trả lời giống nhau)")
        sids, seeds, prompts, params, out = [], [], [], [], [None] * len(requests)
        for i, r in enumerate(requests):
            sid = getattr(r.get("sample"), "sample_id", f"#{i}")
            seed = base + (zlib.crc32(sid.encode()) % 100_000) * 10  # same per-sample seed as the other backends
            ids = self.tok.apply_chat_template(r["messages"], add_generation_prompt=True, tokenize=True)
            ids = list(ids["input_ids"] if hasattr(ids, "keys") else ids)  # newer transformers return a dict
            room = min(max_tokens, self.max_model_len - len(ids))
            if room <= 0:  # vLLM rejects the whole call for one over-long prompt: answer it with a placeholder
                print(f"  {sid}: prompt {len(ids)} token > max_model_len {self.max_model_len}, bỏ qua", flush=True)
                out[i] = [f"{OOM_MARK} prompt {len(ids)} token > max_model_len {self.max_model_len}"] * n
                continue
            sids.append((i, sid, len(ids)))
            seeds.append(seed)
            prompts.append({"prompt_token_ids": ids})
            params.append(SamplingParams(n=n, temperature=temperature, max_tokens=room,
                                         **({"top_p": self.top_p, "seed": seed} if temperature > 0 else {})))
        t0 = time.time()
        results = self.llm.generate(prompts, params, use_tqdm=False) if prompts else []
        total = time.time() - t0
        n_out = 0
        for (i, sid, p_tok), seed, res in zip(sids, seeds, results):
            outs = [len(c.token_ids) for c in res.outputs]
            n_out += sum(outs)
            for k, o_tok in enumerate(outs):
                self.usage["requests"] += 1
                self.usage["prompt_tokens"] += p_tok
                self.usage["output_tokens"] += o_tok
                self.ledger.append({"sample_id": sid, "vote": k, "prompt_tokens": p_tok, "output_tokens": o_tok,
                                    "seconds": round(total / max(1, len(results) * n), 2),  # batch share
                                    "hit_max_tokens": o_tok >= max_tokens, "temperature": temperature,
                                    "top_p": self.top_p, "seed": seed + k if temperature > 0 else seed})
            cut = sum(o >= max_tokens for o in outs)
            print(f"  {sid}" + (f" x{n}" if n > 1 else "") + f": vào {p_tok} token, ra " + "/".join(map(str, outs))
                  + " token" + (f" ({cut} câu chạm max_new_tokens)" if cut else ""), flush=True)
            out[i] = [c.text for c in res.outputs]
        if results:
            print(f"  batch {len(results)} bài: {total:.1f}s, {n_out / max(total, 1e-9):.0f} tok/s ra", flush=True)
        return out


def _hub_revision(model: str) -> str | None:
    """Commit of a Hub model id (None for a local path or offline)."""
    if Path(model).exists():
        return _snapshot_revision(model)
    try:
        from huggingface_hub import HfApi
        return HfApi().model_info(model).sha
    except Exception:  # noqa: BLE001 - offline / gated: the bundle just records no revision
        return None


def make_local_backend(kind: str, settings: dict) -> LocalChatBackend:
    cls = {"mlx": MLXChatBackend, "hf": HFChatBackend, "vllm": VLLMChatBackend}[kind]
    return cls(**settings.get(kind, {}))
