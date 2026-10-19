"""Local-only generation backends. Imports/downloads are lazy and explicit."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Protocol

from src.task3.compliance import fallback


@dataclass
class Generation:
    text: str
    output_tokens: int
    latency_s: float


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
        if torch.cuda.device_count() < 1:
            raise RuntimeError("Task 3 inference requires at least one visible CUDA device")
        device_map = config.get("device_map") or ("auto" if torch.cuda.device_count() > 1 else {"": torch.cuda.current_device()})
        options = {
            "revision": config["revision"],
            "trust_remote_code": False,
            "device_map": device_map,
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
        if options["do_sample"]:
            options.update(temperature=config.get("temperature", 0.7), top_p=config.get("top_p", 0.9))
        start = time.perf_counter()
        with self.torch.inference_mode():
            outputs = self.model.generate(**inputs, **options)
        ids = outputs[0, inputs["input_ids"].shape[-1] :]
        text = self.tokenizer.decode(ids, skip_special_tokens=True)
        tokens_count = len(ids)
        del inputs, outputs
        if self.torch.cuda.is_available():
            self.torch.cuda.empty_cache()
        return Generation(text, tokens_count, time.perf_counter() - start)


def tokenizer_metadata(tokenizer):
    return {
        "class": type(tokenizer).__name__,
        "chat_template_sha256": hashlib.sha256(str(tokenizer.chat_template).encode()).hexdigest(),
        "revision": getattr(tokenizer, "_task3_revision", None)
        or getattr(tokenizer, "init_kwargs", {}).get("_commit_hash"),
        "mock": isinstance(tokenizer, MockTokenizer),
    }


SUPPORTED_PROVIDERS = ("hf", "gemini", "openai")


def resolve_provider(config: dict) -> str:
    """Resolve provider: 'gemini', 'openai', or default 'hf' (local HuggingFace Qwen)."""
    provider = str(config.get("provider", "hf")).lower().strip()
    if not provider:
        provider = "hf"
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider '{provider}'. Expected one of {SUPPORTED_PROVIDERS}")
    return provider


def is_api_model(config: dict) -> bool:
    """Return True if model resolves to an external API (Gemini or OpenAI)."""
    return resolve_provider(config) in ("gemini", "openai")



class GeminiBackend:
    """Gemini API backend matching Task 3 Backend protocol."""

    def __init__(self, config: dict, tokenizer=None):
        from src.llm.api_client import GeminiBackend as CoreGeminiBackend

        self.config = config
        self.tokenizer = tokenizer or MockTokenizer()
        self.client = CoreGeminiBackend(
            model=config.get("model_id", "gemini-2.5-flash"),
            rpm=config.get("rpm", 15),
            tpm=config.get("tpm", 0),
            max_requests=config.get("max_requests_per_run", 400),
        )

    def generate(self, messages: list[dict], config: dict) -> Generation:
        start = time.perf_counter()
        req = {"messages": messages}
        gen_cfg = {
            "max_new_tokens": config.get("max_new_tokens", 512),
            "temperature": config.get("temperature", 0.0),
            "n": 1,
        }
        res = self.client.generate([req], gen_cfg)
        text = res[0][0] if res and res[0] else ""
        elapsed = time.perf_counter() - start
        tokens = len(self.tokenizer.encode(text)) if hasattr(self.tokenizer, "encode") else len(text.split())
        return Generation(text.strip(), tokens, elapsed)


class OpenAIBackend:
    """OpenAI API backend matching Task 3 Backend protocol."""

    def __init__(self, config: dict, tokenizer=None):
        from src.llm.openai_client import OpenAIBackend as CoreOpenAIBackend

        self.config = config
        self.tokenizer = tokenizer or MockTokenizer()
        self.client = CoreOpenAIBackend(
            model=config.get("model_id", "gpt-4o-mini"),
            rpm=config.get("rpm", 60),
            tpm=config.get("tpm", 0),
            max_requests=config.get("max_requests_per_run", 400),
        )

    def generate(self, messages: list[dict], config: dict) -> Generation:
        start = time.perf_counter()
        req = {"messages": messages}
        gen_cfg = {
            "max_new_tokens": config.get("max_new_tokens", 512),
            "temperature": config.get("temperature", 0.0),
            "n": 1,
        }
        res = self.client.generate([req], gen_cfg)
        text = res[0][0] if res and res[0] else ""
        elapsed = time.perf_counter() - start
        tokens = len(self.tokenizer.encode(text)) if hasattr(self.tokenizer, "encode") else len(text.split())
        return Generation(text.strip(), tokens, elapsed)


def load_backend(config: dict, tokenizer=None):
    """Switch-case to instantiate the requested backend (Gemini, OpenAI, or local HF)."""
    match resolve_provider(config):
        case "gemini":
            return GeminiBackend(config, tokenizer)
        case "openai":
            return OpenAIBackend(config, tokenizer)
        case "hf" | _:
            return HFBackend(config, tokenizer)


