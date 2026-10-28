"""Local-only generation backends. Imports/downloads are lazy and explicit."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Protocol

from src.task3.compliance import fallback


@dataclass
class Generation:
    text: str
    output_tokens: int
    latency_s: float
    finish_reason: str | None = None
    eos_reached: bool | None = None


class Backend(Protocol):
    tokenizer: object

    def generate(self, messages: list[dict], config: dict) -> Generation: ...


class MockTokenizer:
    """TEST ONLY byte tokenizer; token counts are not Qwen measurements."""

    chat_template = "TEST-ONLY UTF8 role/content framing v1"
    eos_token_id = 0
    pad_token_id = 0

    def apply_chat_template(self, messages, tokenize=True, add_generation_prompt=False, **kwargs):
        text = "".join(f"<{m['role']}>\n{m['content']}\n</{m['role']}>\n" for m in messages)
        if add_generation_prompt:
            text += "<assistant>\n"
        return list(text.encode()) if tokenize else text

    def encode(self, text, **kwargs):
        return list(text.encode())


class MockBackend:
    tokenizer = MockTokenizer()

    def generate(self, messages, config):
        if messages and "Bạn phân loại lỗi C++" in messages[0].get("content", ""):
            text = json.dumps(
                {
                    "status": "uncertain",
                    "taxonomy_error": [],
                    "findings": [],
                    "prerequisite_review": [],
                    "evidence_limitations": ["TEST-ONLY mock diagnosis; no correctness claim."],
                },
                ensure_ascii=False,
            )
            return Generation(text, len(self.tokenizer.encode(text)), 0.0, "test_mock", True)
        text = fallback(1)
        return Generation(text, len(self.tokenizer.encode(text)), 0.0)


def load_tokenizer(config):
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(config["model_id"], revision=config["revision"], trust_remote_code=False)
    tokenizer._task3_revision = config["revision"]
    if not tokenizer.chat_template:
        raise ValueError("tokenizer has no chat template")
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def model_load_options(config, *, device_index, bf16_supported=None):
    """Keep NF4 unchanged; unquantized inference explicitly requests BF16 on CUDA."""
    import torch
    from transformers import BitsAndBytesConfig

    options = {
        "revision": config["revision"],
        "trust_remote_code": False,
        "device_map": {"": device_index},
    }
    if config.get("load_in_4bit", True):
        supported = torch.cuda.is_bf16_supported() if bf16_supported is None else bf16_supported
        options["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16 if supported else torch.float16,
        )
    else:
        options["dtype"] = torch.bfloat16
    return options


def inspect_model_precision(model, *, load_in_4bit):
    """Inspect actual parameter storage and reject any CPU/disk or BF16 mismatch."""
    from collections import Counter
    import torch

    dtypes, devices = Counter(), Counter()
    for parameter in model.parameters():
        dtypes[str(parameter.dtype)] += parameter.numel()
        devices[str(parameter.device)] += parameter.numel()
    device_map = {key: str(value) for key, value in getattr(model, "hf_device_map", {}).items()}
    if not devices or any(not device.startswith("cuda:") for device in devices):
        raise RuntimeError("Task 3 precision verification requires all parameters on CUDA; no CPU offload")
    if any(value in {"cpu", "disk", "meta"} for value in device_map.values()):
        raise RuntimeError("Task 3 precision verification forbids CPU/disk offload")
    quantized = bool(getattr(model, "is_loaded_in_4bit", False))
    if quantized != bool(load_in_4bit):
        raise RuntimeError("Loaded model quantization differs from requested precision")
    if not load_in_4bit and set(dtypes) != {str(torch.bfloat16)}:
        raise RuntimeError("Unquantized Task 3 model parameters must all be torch.bfloat16")
    quantized_compute_dtypes = []
    if quantized:
        import bitsandbytes as bnb

        quantized_compute_dtypes = sorted({str(module.compute_dtype) for module in model.modules()
                                           if isinstance(module, bnb.nn.Linear4bit)})
    return {
        "actual_precision": "nf4" if quantized else "bf16",
        "parameter_storage_elements_by_dtype": dict(dtypes),
        "parameter_storage_elements_by_device": dict(devices),
        "hf_device_map": device_map,
        "is_loaded_in_4bit": quantized,
        "quantized_compute_dtypes": quantized_compute_dtypes,
        "resolved_model_revision": getattr(getattr(model, "config", None), "_commit_hash", None),
    }


class HFBackend:
    def __init__(self, config, tokenizer=None):
        import torch
        from transformers import AutoModelForCausalLM, set_seed

        set_seed(config.get("seed", 42))
        self.torch = torch
        self.tokenizer = tokenizer or load_tokenizer(config)
        if not torch.cuda.is_available():
            raise RuntimeError("local inference requires CUDA; use --dry-run for offline tests")
        if torch.cuda.device_count() != 1:
            raise RuntimeError("Task 3 inference requires exactly one visible CUDA device")
        if not config.get("load_in_4bit", True) and not torch.cuda.is_bf16_supported():
            raise RuntimeError("BF16 inference requires native BF16 support; no precision fallback")
        torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        options = model_load_options(config, device_index=torch.cuda.current_device())
        self.model = AutoModelForCausalLM.from_pretrained(config["model_id"], **options)
        if config.get("adapter"):
            from peft import PeftModel

            self.model = PeftModel.from_pretrained(self.model, config["adapter"], is_trainable=False)
        self.model.eval()
        torch.cuda.synchronize()
        self.load_latency_s = time.perf_counter() - started
        self.precision_audit = inspect_model_precision(self.model, load_in_4bit=config.get("load_in_4bit", True))
        if self.precision_audit["resolved_model_revision"] != config["revision"]:
            raise RuntimeError("Loaded model revision differs from the pinned revision")

    def runtime_metadata(self):
        self.torch.cuda.synchronize()
        free, total = self.torch.cuda.mem_get_info()
        return {
            **self.precision_audit,
            "load_latency_s": self.load_latency_s,
            "peak_gpu_memory_allocated_bytes": self.torch.cuda.max_memory_allocated(),
            "peak_gpu_memory_reserved_bytes": self.torch.cuda.max_memory_reserved(),
            "current_gpu_memory_allocated_bytes": self.torch.cuda.memory_allocated(),
            "free_gpu_memory_bytes": free,
            "total_gpu_memory_bytes": total,
        }

    def generate(self, messages, config):
        inputs = self.tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_tensors="pt", return_dict=True
        ).to(self.model.device)
        options = {
            "max_new_tokens": config.get("max_new_tokens", 512),
            "do_sample": config.get("do_sample", False),
            "pad_token_id": self.tokenizer.pad_token_id,
        }
        if config.get("bad_words_ids"):
            options["bad_words_ids"] = config["bad_words_ids"]
        if options["do_sample"]:
            options.update(temperature=config.get("temperature", 0.7), top_p=config.get("top_p", 0.9))
        self.torch.cuda.synchronize()
        start = time.perf_counter()
        with self.torch.inference_mode():
            outputs = self.model.generate(**inputs, **options)
        self.torch.cuda.synchronize()
        ids = outputs[0, inputs["input_ids"].shape[-1] :]
        eos_ids = self.model.generation_config.eos_token_id
        eos_ids = [eos_ids] if isinstance(eos_ids, int) else (eos_ids or [])
        eos = bool(len(ids) and int(ids[-1]) in eos_ids)
        reason = "eos" if eos else "length" if len(ids) >= options["max_new_tokens"] else "unknown"
        return Generation(self.tokenizer.decode(ids, skip_special_tokens=True), len(ids), time.perf_counter() - start, reason, eos)


def tokenizer_metadata(tokenizer):
    return {
        "class": type(tokenizer).__name__,
        "chat_template_sha256": hashlib.sha256(str(tokenizer.chat_template).encode()).hexdigest(),
        "revision": getattr(tokenizer, "_task3_revision", None)
        or getattr(tokenizer, "init_kwargs", {}).get("_commit_hash"),
        "mock": isinstance(tokenizer, MockTokenizer),
    }
