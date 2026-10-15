"""Base solutions for mutation (synth_plan.md "Cải tiến 1", implementation step 4).

Two sources of clean bases:

0. Hand-written persona solutions (the ones used, decision 2026-10-15): src/synth/persona_bases/
   <exam_id>/<persona>__0.cpp, loaded by scripts/build_synth_dataset.py --bases-dir.
1. (optional, unused) LLM persona solutions — a local model writes >=4 correct solutions per
   problem in different student styles, guided by the public-test ``style_profile`` (aggregate
   only). Only solutions that pass 100% of the standard tests are kept.
2. Repair-then-break on the 32 real submissions (tagged with ``fold``) — handled elsewhere.

The LLM is injected as a ``complete(prompt) -> str`` callable, so the module is fully testable
offline (``reference_generator`` returns the problem's own clean reference).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

PERSONAS = {
    "verbose_first_year": "sinh viên năm 1 viết dài dòng: thừa biến tạm, if-else lồng nhau, tên biến tiếng Việt không dấu (dem, tich)",
    "all_in_main": "sinh viên dồn hết logic vào main, không tách hàm hoặc tách nhưng dùng biến toàn cục",
    "exam_style": "sinh viên kiểu thi cử: #define ll long long, bits/stdc++.h, viết tắt",
    "careful_oop": "sinh viên cẩn thận: nhiều hàm phụ, comment tiếng Việt, tách hàm rõ ràng",
    "debug_leftover": "sinh viên còn code debug: các cout debug đã bị comment, main tự kiểm thử",
}


class CompleteFn(Protocol):
    def __call__(self, prompt: str) -> str: ...


@dataclass
class SolutionGenerator:
    def __call__(self, problem, k: int) -> list[str]:  # pragma: no cover - protocol-like
        raise NotImplementedError


def reference_generator(problem, k: int = 1) -> list[str]:
    """Offline fallback: the problem's own clean reference (already correct)."""
    return [problem.reference] if problem.reference else []


def strip_code_fence(text: str) -> str:
    import re

    m = re.search(r"```(?:cpp|c\+\+)?\s*(.*?)```", text or "", re.DOTALL)
    return (m.group(1) if m else (text or "")).strip()


def persona_prompt(problem, persona: str, *, style_profile_text: str | None = None) -> str:
    """Prompt asking for ONE correct C++ solution in the given persona's style."""
    lines = [
        f"Đây là đề bài (ngôn ngữ {problem.language}):",
        problem.statement.strip(),
        "",
        f"Hãy viết một lời giải C++ ĐÚNG HOÀN TOÀN theo phong cách: {PERSONAS.get(persona, persona)}.",
        "Yêu cầu: giữ nguyên prototype hàm của đề (nếu có); không thêm main nếu đề chỉ yêu cầu hàm.",
    ]
    if style_profile_text:
        lines.append(f"Tham khảo văn phong sinh viên (chỉ là mô tả, KHÔNG sao chép code): {style_profile_text}")
    lines.append("Chỉ trả về code trong một khối ```cpp ... ```.")
    return "\n".join(lines)


@dataclass
class LLMGenerator:
    """Generate k persona solutions with an injected completion function; optionally validate."""

    complete: CompleteFn
    personas: list[str] = field(default_factory=lambda: list(PERSONAS))
    style_profile_text: str | None = None
    validate: Callable[[str], bool] | None = None

    def __call__(self, problem, k: int) -> list[str]:
        out: list[str] = []
        for persona in self.personas:
            if len(out) >= k:
                break
            code = strip_code_fence(self.complete(persona_prompt(problem, persona, style_profile_text=self.style_profile_text)))
            if not code:
                continue
            if self.validate is None or self.validate(code):
                out.append(code)
        return out


def repair_prompt(code: str, problem) -> str:
    return "\n".join([
        "Đây là một bài nộp C++ chưa đúng. Hãy sửa với thay đổi NHỎ NHẤT để chạy đúng.",
        "Giữ nguyên văn phong, tên biến, cách xuống dòng của sinh viên. Chỉ trả về code đã sửa trong ```cpp```.",
        f"Đề bài:\n{problem.statement.strip()}",
        f"Bài nộp:\n```cpp\n{code}\n```",
    ])


def repair(code: str, problem, complete: CompleteFn) -> str:
    """Minimal-diff repair via LLM (used only to make a real submission a valid base)."""
    return strip_code_fence(complete(repair_prompt(code, problem)))
