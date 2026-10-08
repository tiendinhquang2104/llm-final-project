"""LLM access through the native Gemini API (generateContent). Stdlib only (urllib + threads).

`generate(requests, gen_cfg) -> list[list[str]]` returns n completions per request, where a request is
{"messages": [...], "sample": Sample, "exam": dict}.

Free-tier friendly: client-side RPM throttle, a per-run request cap, and 429 handling that honours the
server's retryDelay and stops immediately when the daily quota is exhausted.
"""
from __future__ import annotations

import json
import os
import platform
import re
import threading
import time
import urllib.error
import urllib.request

from src.utils.seed import set_seed  # noqa: F401  (re-exported for callers)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class Backend:
    """Interface; tests plug in scripted fakes."""

    name = "base"

    def generate(self, requests: list[dict], gen: dict) -> list[list[str]]:
        raise NotImplementedError

    def info(self) -> dict:
        return {"backend": self.name, "python": platform.python_version()}


class UnsupportedFeature(RuntimeError):
    """HTTP 400 because the model rejects a request feature (JSON mode / system instruction / thinking)."""

    def __init__(self, feature: str, msg: str):
        super().__init__(f"{feature}: {msg}")
        self.feature = feature


# 400-error text -> feature to drop (some models, e.g. Gemma, do not support every generateContent option)
UNSUPPORTED_PATTERNS = [
    ("json_mode", r"response_?mime_?type|json mode|JSON mode is not enabled"),
    ("system", r"system_?instruction|Developer instruction is not enabled"),
    ("thinking", r"thinking_?config|thinking_?level|thinking_?budget|Thinking is not"),
]


class QuotaExhausted(RuntimeError):
    """Daily quota (RPD) or the per-run request cap is used up — retrying will not help."""


def default_thinking(model: str) -> tuple[dict, dict]:
    """(thinking_off, thinking_on) thinkingConfig for a model family served by the Gemini API."""
    m = model.lower()
    if m.startswith("gemma-4"):
        return {"thinkingLevel": "minimal"}, {"thinkingLevel": "high"}  # Gemma 4: on/off toggle
    if m.startswith("gemma"):
        return {}, {}  # older Gemma: no thinking support
    if m.startswith("gemini-2.5"):
        return {"thinkingBudget": 0}, {"thinkingBudget": -1}
    return {"thinkingLevel": "low"}, {"thinkingLevel": "high"}  # Gemini 3.x: cannot fully disable thinking


class GeminiBackend(Backend):
    name = "gemini"

    def __init__(self, api_key: str = "", model: str = "gemini-3.8-flash", rpm: float = 10, tpm: float = 0,
                 max_requests_per_run: int = 200, concurrency: int = 2, timeout: float = 180.0,
                 max_retries: int = 5, json_mode: bool = True,
                 thinking_off: dict | None = None, thinking_on: dict | None = None, **_ignored):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self.api_key or self.api_key.startswith(("PASTE", "your_")):
            raise RuntimeError("Thiếu GEMINI_API_KEY: thêm vào file .env ở thư mục gốc project (xem .env.example)")
        self.model = model
        self.min_interval = 60.0 / rpm if rpm else 0.0
        self.tpm = float(tpm)  # input tokens/minute budget (0 = off); estimated client-side from prompt length
        self._token_log: list[tuple[float, int]] = []
        self.max_requests = int(max_requests_per_run)
        self.concurrency, self.timeout, self.max_retries, self.json_mode = concurrency, timeout, max_retries, json_mode
        # Raw thinkingConfig blocks; defaults depend on the model family (see default_thinking).
        # maxOutputTokens includes thinking tokens, so keep max_new_tokens generous.
        auto_off, auto_on = default_thinking(model)
        self.thinking_off = thinking_off if thinking_off is not None else auto_off
        self.thinking_on = thinking_on if thinking_on is not None else auto_on
        self.usage = {"requests": 0, "failed_requests": 0, "prompt_tokens": 0, "output_tokens": 0,
                      "thinking_tokens": 0, "truncated": 0}
        self.served_models: set[str] = set()
        self._lock = threading.Lock()
        self._next_slot = 0.0
        self._sent = 0
        self._done = self._total = 0
        self.no_system = False  # set automatically if the model rejects systemInstruction
        self.no_thinking = False  # set automatically if the model rejects thinkingConfig

    # -- throttling ---------------------------------------------------------------------------------
    def _wait_turn(self, est_tokens: int = 0) -> None:
        with self._lock:
            if self._sent >= self.max_requests:
                raise QuotaExhausted(f"max_requests_per_run={self.max_requests} reached")
            self._sent += 1
            now = time.monotonic()
            start = max(now, self._next_slot)
            if self.tpm and est_tokens:
                # Sliding 60s window over (start time, tokens) of reserved requests.
                self._token_log = [(t, n) for t, n in self._token_log if t > start - 60]
                while self._token_log and sum(n for _, n in self._token_log) + est_tokens > self.tpm:
                    start = max(start, self._token_log[0][0] + 60)
                    self._token_log.pop(0)
                self._token_log.append((start, est_tokens))
            self._next_slot = start + self.min_interval
        if start > now:
            time.sleep(start - now)

    @staticmethod
    def _quota_kind(body: str) -> str:
        m = re.search(r'"quotaId"\s*:\s*"([^"]+)"', body)
        q = m.group(1) if m else ""
        if "InputTokens" in q or "Tokens" in q:
            return "token/phút"
        if "PerDay" in q:
            return "request/ngày"
        if "PerMinute" in q:
            return "request/phút"
        return q or "không rõ"

    @staticmethod
    def _retry_delay(body: str, default: float) -> float:
        m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', body)
        return float(m.group(1)) + 1 if m else default

    def _post(self, payload: dict, label: str = "") -> dict:
        body = json.dumps(payload).encode()
        est_tokens = len(body) // 3  # rough: ~3 chars/token for Vietnamese text + C++ code
        delay = 5.0
        for attempt in range(self.max_retries):
            self._wait_turn(est_tokens)
            req = urllib.request.Request(GEMINI_URL.format(model=self.model), data=body, method="POST", headers={
                "x-goog-api-key": self.api_key, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                msg = e.read().decode(errors="replace")
                if e.code == 400:
                    for feature, pat in UNSUPPORTED_PATTERNS:
                        if re.search(pat, msg, re.I):
                            raise UnsupportedFeature(feature, msg[:300]) from e
                if e.code == 429 and re.search(r"PerDay|per day|RequestsPerDay", msg, re.I):
                    raise QuotaExhausted("Gemini daily quota exhausted (resets at midnight Pacific time)") from e
                if e.code in (429, 500, 502, 503, 504) and attempt < self.max_retries - 1:
                    wait = self._retry_delay(msg, delay)
                    kind = f" [hạn mức {self._quota_kind(msg)}]" if e.code == 429 else ""
                    print(f"[gemini] {label} HTTP {e.code}{kind} -> chờ {wait:.0f}s rồi thử lại "
                          f"({attempt + 1}/{self.max_retries - 1})", flush=True)
                    time.sleep(wait)
                    delay *= 2
                    continue
                raise RuntimeError(f"HTTP {e.code}: {msg[:400]}") from e
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt == self.max_retries - 1:
                    raise
                print(f"[gemini] {label} {type(e).__name__} -> chờ {delay:.0f}s rồi thử lại", flush=True)
                time.sleep(delay)
                delay *= 2
        raise RuntimeError("unreachable")

    # -- request building ---------------------------------------------------------------------------
    def build_payload(self, messages: list[dict], gen: dict, seed: int) -> dict:
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                    for m in messages if m["role"] != "system"]
        if system and self.no_system and contents:  # model rejects systemInstruction -> prepend to 1st user turn
            contents[0]["parts"][0]["text"] = f"{system}\n\n{contents[0]['parts'][0]['text']}"
            system = ""
        thinking = bool(gen.get("enable_thinking", False))
        cfg = {"temperature": float(gen.get("temperature", 0.0)),
               "maxOutputTokens": int(gen.get("max_new_tokens", 1024)),
               "seed": int(seed), "candidateCount": 1}
        thinking_cfg = self.thinking_on if thinking else self.thinking_off
        if thinking_cfg and not self.no_thinking:
            cfg["thinkingConfig"] = dict(thinking_cfg)
        if float(gen.get("temperature", 0.0)) > 0:
            cfg["topP"] = float(gen.get("top_p", 0.95))
            if gen.get("top_k"):
                cfg["topK"] = int(gen["top_k"])
        if self.json_mode:
            cfg["responseMimeType"] = "application/json"
        payload = {"contents": contents, "generationConfig": cfg}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        return payload

    def _one(self, messages: list[dict], gen: dict, seed: int, label: str = "") -> str:
        t0 = time.monotonic()
        try:
            while True:
                try:
                    r = self._post(self.build_payload(messages, gen, seed), label)
                    break
                except UnsupportedFeature as e:
                    attr = {"json_mode": "json_mode", "system": "no_system", "thinking": "no_thinking"}[e.feature]
                    with self._lock:
                        already = (not self.json_mode) if attr == "json_mode" else getattr(self, attr)
                        if attr == "json_mode":
                            self.json_mode = False
                        else:
                            setattr(self, attr, True)
                    if already:
                        raise
                    print(f"[gemini] {self.model} không hỗ trợ '{e.feature}' -> tắt và gửi lại", flush=True)
        except QuotaExhausted:
            raise
        except Exception as e:  # one failed request must not kill the run -> parse fallback
            with self._lock:
                self.usage["failed_requests"] += 1
            print(f"[gemini] {label} request failed: {e!r}"[:400], flush=True)
            return ""
        u = r.get("usageMetadata") or {}
        cand = (r.get("candidates") or [{}])[0]
        with self._lock:
            self.usage["requests"] += 1
            self.usage["prompt_tokens"] += int(u.get("promptTokenCount", 0))
            self.usage["output_tokens"] += int(u.get("candidatesTokenCount", 0))
            self.usage["thinking_tokens"] += int(u.get("thoughtsTokenCount", 0))
            if cand.get("finishReason") == "MAX_TOKENS":
                self.usage["truncated"] += 1
            if r.get("modelVersion"):
                self.served_models.add(r["modelVersion"])
            self._done += 1
            done, total = self._done, self._total
        print(f"[gemini] {done}/{total} {label} ok {time.monotonic() - t0:.0f}s "
              f"(in={u.get('promptTokenCount', 0)} out={u.get('candidatesTokenCount', 0)} "
              f"think={u.get('thoughtsTokenCount', 0)}{' TRUNCATED' if cand.get('finishReason') == 'MAX_TOKENS' else ''})",
              flush=True)
        parts = (cand.get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts if not p.get("thought"))

    def generate(self, requests, gen):
        from concurrent.futures import ThreadPoolExecutor

        n = int(gen.get("n", 1))
        base_seed = int(gen.get("seed", 42))
        jobs = [(i, k) for i in range(len(requests)) for k in range(n)]
        self._done, self._total = 0, len(jobs)

        def label(i: int, k: int) -> str:
            sample = requests[i].get("sample")
            sid = getattr(sample, "sample_id", f"#{i}")
            return f"{sid}" + (f"[{k + 1}/{n}]" if n > 1 else "")

        with ThreadPoolExecutor(max_workers=self.concurrency) as ex:
            texts = list(ex.map(lambda ik: self._one(requests[ik[0]]["messages"], gen, base_seed + ik[0] * 100 + ik[1],
                                                     label(*ik)), jobs))
        out: list[list[str]] = [[] for _ in requests]
        for (i, _), t in zip(jobs, texts):
            out[i].append(t)
        return out

    def info(self):
        # Never includes the API key — this dict is written to outputs/task1/<run>/config.json.
        return {"backend": self.name, "model": self.model, "json_mode": self.json_mode,
                "no_system": self.no_system, "no_thinking": self.no_thinking,
                "thinking_off": self.thinking_off, "thinking_on": self.thinking_on,
                "served_models": sorted(self.served_models), "usage": dict(self.usage),
                "python": platform.python_version()}


def make_backend(gemini_settings: dict) -> GeminiBackend:
    return GeminiBackend(**gemini_settings)
