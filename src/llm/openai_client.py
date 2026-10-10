"""OpenAI Responses backend for the shared Task 1 pipeline."""

from __future__ import annotations

import os
import platform
from datetime import datetime, timezone

from src.data.loader import DIM_MAX, DIMENSIONS
from src.llm.api_client import Backend


class CostLimitReached(RuntimeError):
    """The configured estimated USD budget for this invocation is exhausted."""


def response_schema(exam: dict, template: str = "structured") -> dict:
    rubric = {
        "type": "object",
        "properties": {d: {"type": "number", "minimum": 0, "maximum": DIM_MAX[d], "multipleOf": 0.01}
                       for d in DIMENSIONS},
        "required": DIMENSIONS,
        "additionalProperties": False,
    }
    if template == "plain":
        return rubric
    problem = {
        "type": "object",
        "properties": {
            "pid": {"type": "string", "enum": [p["pid"] for p in exam.get("problems", [])]},
            "status": {"type": "string", "enum": ["correct", "partial", "wrong", "runtime_error", "not_attempted"]},
            "note": {"type": "string"},
        },
        "required": ["pid", "status", "note"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "rationale": {"type": "string"},
            "problems": {"type": "array", "items": problem},
            "rubric": rubric,
        },
        "required": ["rationale", "problems", "rubric"],
        "additionalProperties": False,
    }


class OpenAIBackend(Backend):
    name = "openai"

    def __init__(self, api_key: str = "", model: str = "gpt-4o-mini", max_usd: float = 1.0,
                 input_usd_per_million: float = 0.15, cached_input_usd_per_million: float = 0.075,
                 output_usd_per_million: float = 0.60, price_checked_date: str = "2026-10-08",
                 max_requests_per_run: int = 150, client=None, **_ignored):
        key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if client is None:
            if not key or key.startswith(("PASTE", "your_")):
                raise RuntimeError("Thiếu OPENAI_API_KEY: thêm vào Colab Secrets hoặc biến môi trường.")
            from openai import OpenAI
            client = OpenAI(api_key=key, max_retries=0)
        self.client = client
        self.model = model
        self.max_usd = float(max_usd)
        self.max_requests = int(max_requests_per_run)
        self.price = {
            "checked_date": price_checked_date,
            "source": "https://developers.openai.com/api/docs/models/gpt-4o-mini",
            "input_usd_per_million": float(input_usd_per_million),
            "cached_input_usd_per_million": float(cached_input_usd_per_million),
            "output_usd_per_million": float(output_usd_per_million),
        }
        self.usage = {"requests": 0, "failed_requests": 0, "prompt_tokens": 0,
                      "cached_input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
                      "estimated_unbilled_usd": 0.0}
        self.ledger: list[dict] = []

    def _estimate(self, messages: list[dict], max_output_tokens: int) -> float:
        chars = sum(len(m["content"]) for m in messages)
        input_est = max(1, chars // 3)
        return (input_est * self.price["input_usd_per_million"]
                + max_output_tokens * self.price["output_usd_per_million"]) / 1_000_000

    def _one(self, request: dict, gen: dict) -> str:
        messages = request["messages"]
        sample_id = getattr(request.get("sample"), "sample_id", "")
        max_output = int(gen.get("max_new_tokens", 1024))
        reserve = self._estimate(messages, max_output)
        committed = self.usage["cost_usd"] + self.usage["estimated_unbilled_usd"]
        if self.usage["requests"] + self.usage["failed_requests"] >= self.max_requests:
            raise CostLimitReached(f"max_requests_per_run={self.max_requests} reached")
        if committed + reserve > self.max_usd:
            raise CostLimitReached(f"estimated cost would exceed max_usd={self.max_usd:.2f}")
        schema = response_schema(request["exam"], request.get("template", "structured"))
        try:
            response = self.client.responses.create(
                model=self.model,
                input=messages,
                text={"format": {"type": "json_schema", "name": "task1_grade", "strict": True, "schema": schema}},
                temperature=float(gen.get("temperature", 0.0)),
                max_output_tokens=max_output,
                store=False,
            )
        except Exception as exc:
            self.usage["failed_requests"] += 1
            self.ledger.append({"sample_id": sample_id, "api_error": type(exc).__name__,
                                "cost_usd": None, "estimated_reserve_usd": reserve})
            return ""
        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        details = getattr(usage, "input_tokens_details", None)
        cached = min(input_tokens, int(getattr(details, "cached_tokens", 0) or 0))
        billed = ((input_tokens - cached) * self.price["input_usd_per_million"]
                  + cached * self.price["cached_input_usd_per_million"]
                  + output_tokens * self.price["output_usd_per_million"]) / 1_000_000
        self.usage["requests"] += 1
        self.usage["prompt_tokens"] += input_tokens
        self.usage["cached_input_tokens"] += cached
        self.usage["output_tokens"] += output_tokens
        if usage is None:
            self.usage["estimated_unbilled_usd"] += reserve
        else:
            self.usage["cost_usd"] += billed
        self.ledger.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sample_id": sample_id,
            "response_id": getattr(response, "id", None),
            "input_tokens": input_tokens,
            "cached_input_tokens": cached,
            "output_tokens": output_tokens,
            "cost_usd": billed if usage is not None else None,
            "usage_missing": usage is None,
            "estimated_reserve_usd": reserve if usage is None else None,
        })
        return (getattr(response, "output_text", "") or "") if getattr(response, "status", "completed") == "completed" else ""

    def generate(self, requests: list[dict], gen: dict) -> list[list[str]]:
        n = int(gen.get("n", 1))
        return [[self._one(request, gen) for _ in range(n)] for request in requests]

    def info(self) -> dict:
        return {"backend": self.name, "model": self.model, "json_mode": "structured_outputs",
                "usage": dict(self.usage), "price": dict(self.price), "max_usd": self.max_usd,
                "python": platform.python_version()}
