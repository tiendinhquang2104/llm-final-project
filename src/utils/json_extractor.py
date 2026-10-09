"""Task-agnostic extraction of JSON objects from raw LLM text (thinking blocks, code fences, trailing commas)."""
from __future__ import annotations

import json
import re

_THINK_RE = re.compile(r"<think>.*?</think>", re.S)
_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)


def strip_thinking(text: str) -> str:
    text = _THINK_RE.sub("", text)
    # Unclosed <think> (generation cut off while thinking): drop everything before the last </think>
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    return text.strip()


def balanced_objects(text: str) -> list[str]:
    """All top-level {...} substrings, respecting strings and escapes."""
    out, depth, start, in_str, esc = [], 0, None, False, False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                out.append(text[start : i + 1])
    return out


def loads_lenient(s: str):
    """json.loads that tolerates trailing commas and // comments; None if still invalid."""
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    fixed = re.sub(r",\s*([}\]])", r"\1", s)  # trailing commas
    fixed = re.sub(r"//[^\n]*", "", fixed)  # line comments
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        return None


def extract_json_objects(text: str) -> list[dict]:
    """Every parseable JSON object in the text, last one first (models often restate the answer at the end)."""
    body = strip_thinking(text or "")
    candidates = _FENCE_RE.findall(body) + balanced_objects(body)
    objs = [loads_lenient(c) for c in reversed(candidates)]
    return [o for o in objs if isinstance(o, dict)]
