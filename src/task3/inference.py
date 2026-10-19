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


class HFBackend:
    def __init__(self, config, tokenizer=None):
        import torch
        from transformers import AutoModelForCausalLM, BitsAndBytesConfig, set_seed

        set_seed(config.get("seed", 42))
        self.torch = torch
        self.tokenizer = tokenizer or load_tokenizer(config)
        if not torch.cuda.is_available():
            raise RuntimeError("local 4-bit inference requires CUDA; use --dry-run for offline tests")
        if torch.cuda.device_count() != 1:
            raise RuntimeError("Task 3 inference requires exactly one visible CUDA device")
        options = {
            "revision": config["revision"],
            "trust_remote_code": False,
            "device_map": {"": torch.cuda.current_device()},
        }
        if config.get("load_in_4bit", True):
            options["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
            )
        self.model = AutoModelForCausalLM.from_pretrained(config["model_id"], **options)
        if config.get("adapter"):
            from peft import PeftModel

            self.model = PeftModel.from_pretrained(self.model, config["adapter"], is_trainable=False)
        self.model.eval()

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
        start = time.perf_counter()
        with self.torch.inference_mode():
            outputs = self.model.generate(**inputs, **options)
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
