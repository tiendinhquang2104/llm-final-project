"""Level-compliance checker (synth_plan.md section T3.3).

Used both when generating Task 3 feedback and when scoring a model's feedback at inference. A
Level 1/2 answer that hands the student code (or a concrete fix) is a violation; Level 3 may give
a direction but not a full solution; Level 4 is unrestricted.

Calibration (2026-10-13): the 32 real instructor answers are the ground truth. Their Level 2
answers name the offending expression inline (``cur = cur->next``, ``abs(...)``) and paste the
g++ diagnostic, so the checker only flags *code blocks and statements*, never inline identifiers,
and it strips g++ log blocks before checking. See tests/test_synth_compliance.py for the gate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_LEVEL_RE = re.compile(r"level\s*([1-4])", re.IGNORECASE)
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_CODE_LINE_RE = re.compile(
    r"(\{[^}]*\}|<<|>>|==|\bc(?:out|in)\b|\bfor\s*\(|\bwhile\s*\(|\bif\s*\(|^\s*\w+\s*=\s*\S)",
)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_FUNC_CALL_RE = re.compile(r"[A-Za-z_]\w*\s*\(")
_CODE_IDENT_RE = re.compile(
    r"\b(?:[a-z]+[A-Z]\w*|[A-Za-z]\w*_[A-Za-z]\w*|(?:prob|node|ptr|cur|head|root|arr|tmp|stoi|stof)\w*)\b"
)
_LINE_NUMBER_RE = re.compile(r"(?:\bline\b|\bdòng\b)\s*\d+", re.IGNORECASE)
_IMPERATIVE_RE = re.compile(
    r"(sửa thành|sửa lại|thêm dòng|thay bằng|thay thế bằng|đổi thành|viết lại|bỏ dòng|thêm vào|sửa code)",
    re.IGNORECASE,
)
# g++ diagnostics: `file.cpp:5:10: error: ...` plus the quoted source line and caret line it prints
_LOG_HEAD_RE = re.compile(r"^\s*\S+\.(?:cpp|h|hpp|c|cc):\d+:\d+:\s")
_LOG_SRC_RE = re.compile(r"^\s*\d+\s*[|│].*$")
_LOG_CARET_RE = re.compile(r"^\s*[|│^~ \t-]*$")
_IN_FUNCTION_RE = re.compile(r"^\S+:\s*In function\b")
_CODE_FENCE_OPEN = re.compile(r"^\s*```")


def level_of(level: str | int) -> int:
    """Accept 'Level 2 - Chẩn đoán', 'level 2', or 2 -> 2."""
    if isinstance(level, int):
        if level not in (1, 2, 3, 4):
            raise ValueError(f"bad level {level}")
        return level
    m = _LEVEL_RE.search(level)
    if not m:
        raise ValueError(f"cannot read level from {level!r}")
    return int(m.group(1))


def _strip_compile_log(text: str) -> str:
    lines = text.splitlines()
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if _LOG_HEAD_RE.match(line) or _IN_FUNCTION_RE.match(line):
            i += 1
            while i < len(lines) and (_LOG_SRC_RE.match(lines[i]) or _LOG_CARET_RE.match(lines[i])
                                      or _LOG_HEAD_RE.match(lines[i]) or _IN_FUNCTION_RE.match(lines[i])):
                i += 1
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


@dataclass(frozen=True)
class ComplianceResult:
    ok: bool
    level: int
    violations: tuple[str, ...]

    def __bool__(self) -> bool:
        return self.ok


def _code_blocks(text: str) -> list[str]:
    return _FENCE_RE.findall(text)


def _has_code_line(text: str) -> bool:
    if _INLINE_CODE_RE.search(text):
        return True
    for line in text.splitlines():
        if _CODE_FENCE_OPEN.match(line):
            return True
        if _CODE_LINE_RE.search(line):
            return True
    return False


def check(feedback: str, level: str | int) -> ComplianceResult:
    lvl = level_of(level)
    text = _strip_compile_log(feedback or "")
    violations: list[str] = []

    blocks = _code_blocks(text)
    if lvl in (1, 2):
        if blocks:
            violations.append("code_fence")
        if _has_code_line(text):
            violations.append("code_like")
        if _IMPERATIVE_RE.search(text):
            violations.append("imperative_fix")
        if lvl == 1:
            if _LINE_NUMBER_RE.search(text):
                violations.append("line_number")
            if _FUNC_CALL_RE.search(text) or _CODE_IDENT_RE.search(text):
                violations.append("identifier")
    elif lvl == 3:
        for block in blocks:
            lines = block.splitlines()
            if lines and _CODE_FENCE_OPEN.match(lines[0]):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            # A language tag belongs to the opening fence, not the code body.
            body = [ln for ln in lines if ln.strip()]
            if len(body) > 1:
                violations.append("code_block_gt_1_line")
                break
    if violations:
        return ComplianceResult(False, lvl, tuple(dict.fromkeys(violations)))
    return ComplianceResult(True, lvl, ())
