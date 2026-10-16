"""Pedagogical Guardrail for Task 3 Feedback.

Enforces pedagogical level constraints and prevents code leakage in Level 1 and Level 2 feedback,
avoiding zero-score penalties from contest judges.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence


# Regex patterns indicating code blocks or C++ syntax constructs
FENCED_CODE_PATTERN = re.compile(r"```(?:cpp|c\+\+|c|text)?\s*[\s\S]*?```", re.IGNORECASE)
INDENTED_CODE_PATTERN = re.compile(r"(?:\n|^)(?: {4}|\t)[a-zA-Z0-9_#].*", re.MULTILINE)

# Common C++ syntax keywords and patterns that signal code leakage
CPP_SYNTAX_PATTERNS = [
    re.compile(r"\b(?:int|float|double|char|bool|void|auto|long)\s+[a-zA-Z_]\w*\s*(=|\(|;)", re.IGNORECASE),
    re.compile(r"\b(?:cout|cin)\s*(<<|>>)", re.IGNORECASE),
    re.compile(r"\b(?:printf|scanf)\s*\(", re.IGNORECASE),
    re.compile(r"#include\s*<[^>]+>", re.IGNORECASE),
    re.compile(r"\bfor\s*\([^;]+;[^;]+;[^)]*\)"),
    re.compile(r"\bwhile\s*\([^)]+\)\s*\{?"),
    re.compile(r"\bif\s*\([^)]+\)\s*\{?"),
    re.compile(r"\breturn\s+[^;]+;"),
    re.compile(r"->\s*(?:next|prev|val|data)\s*="),
    re.compile(r"\b(?:malloc|free)\s*\(", re.IGNORECASE),
    re.compile(r"\bdelete(\s*\[\])?\s+[a-zA-Z_]\w*;"),
    re.compile(r"\bnullptr\b"),
]

# Location indicator patterns (disallowed in Level 1)
LOCATION_PATTERNS = [
    re.compile(r"\b(?:dòng|dong|line|lines)\s*\d+", re.IGNORECASE),
    re.compile(r"\b(?:ở dòng|tại dòng|ở line|tại line)\b", re.IGNORECASE),
    re.compile(r"\b(?:hàm|function)\s+[a-zA-Z_]\w*\(\)", re.IGNORECASE),
]


@dataclass
class GuardReport:
    """Audit report for feedback pedagogical compliance."""

    is_compliant: bool
    target_level: str
    violations: list[str] = field(default_factory=list)
    sanitized_feedback: str = ""


def normalize_level_name(level: str) -> str:
    """Normalize level strings like 'Level 1 - Gợi ý nhẹ' to 'Level 1'."""
    level = level.strip()
    if level.startswith("Level 1"):
        return "Level 1"
    if level.startswith("Level 2"):
        return "Level 2"
    if level.startswith("Level 3"):
        return "Level 3"
    if level.startswith("Level 4"):
        return "Level 4"
    return level


def detect_code_leakage(text: str) -> list[str]:
    """Detect presence of code blocks or direct C++ statements in text."""
    reasons: list[str] = []
    if FENCED_CODE_PATTERN.search(text):
        reasons.append("Chứa fenced code block (```)")
    for pattern in CPP_SYNTAX_PATTERNS:
        match = pattern.search(text)
        if match:
            reasons.append(f"Chứa cú pháp code C++: '{match.group(0).strip()}'")
            break
    return reasons


def detect_location_leakage(text: str) -> list[str]:
    """Detect explicit location disclosures (prohibited in Level 1)."""
    reasons: list[str] = []
    for pattern in LOCATION_PATTERNS:
        match = pattern.search(text)
        if match:
            reasons.append(f"Chỉ ra vị trí cụ thể trong code: '{match.group(0).strip()}'")
            break
    return reasons


def audit_feedback(
    feedback: str,
    target_level: str,
    taxonomy_error: Sequence[str] | None = None,
) -> GuardReport:
    """
    Audit whether a generated feedback string complies with contest rules.

    Rules:
    - If taxonomy_error is empty: feedback must be empty ("").
    - Level 1: No code, no specific location, no root cause. General hint or praise only.
    - Level 2: Diagnosis and location allowed. NO code or concrete fix instructions.
    - Level 3: Diagnosis and guidance on how to fix allowed. NO full solution.
    - Level 4: Code and full solution allowed.
    """
    text = feedback.strip()
    norm_level = normalize_level_name(target_level)
    violations: list[str] = []

    # Rule: Empty errors must have empty feedback
    if taxonomy_error is not None and len(taxonomy_error) == 0:
        if text != "":
            violations.append("Bài không có lỗi (taxonomy_error rỗng) nhưng feedback không rỗng")
        return GuardReport(
            is_compliant=len(violations) == 0,
            target_level=norm_level,
            violations=violations,
            sanitized_feedback="" if violations else text,
        )

    # Empty feedback for a problem that has errors is technically safe from code leak, but incomplete
    if not text:
        return GuardReport(
            is_compliant=True,
            target_level=norm_level,
            violations=[],
            sanitized_feedback="",
        )

    # Check for code leakage in Level 1 and Level 2
    if norm_level in ("Level 1", "Level 2"):
        code_leaks = detect_code_leakage(text)
        violations.extend(code_leaks)

    # Check for location leakage in Level 1
    if norm_level == "Level 1":
        loc_leaks = detect_location_leakage(text)
        violations.extend(loc_leaks)

    is_compliant = len(violations) == 0
    sanitized = text if is_compliant else sanitize_feedback(text, target_level, taxonomy_error)

    return GuardReport(
        is_compliant=is_compliant,
        target_level=norm_level,
        violations=violations,
        sanitized_feedback=sanitized,
    )


def sanitize_feedback(
    feedback: str,
    target_level: str,
    taxonomy_error: Sequence[str] | None = None,
) -> str:
    """
    Sanitize and strip forbidden code or structures from feedback text.
    Guarantees that sanitized output is safe from contest zero-score penalties.
    """
    # If no errors exist, output must be empty string
    if taxonomy_error is not None and len(taxonomy_error) == 0:
        return ""

    text = feedback.strip()
    norm_level = normalize_level_name(target_level)

    # Level 4 allows code
    if norm_level == "Level 4":
        return text

    # Remove all fenced code blocks
    text = FENCED_CODE_PATTERN.sub("", text).strip()

    # In Level 1 and Level 2, strip individual C++ statement lines
    if norm_level in ("Level 1", "Level 2"):
        cleaned_lines = []
        for line in text.splitlines():
            stripped = line.strip()
            # If line is purely a C++ code statement or comment
            if any(p.search(stripped) for p in CPP_SYNTAX_PATTERNS):
                continue
            cleaned_lines.append(line)
        text = "\n".join(cleaned_lines).strip()

    # In Level 1, remove location references if present
    if norm_level == "Level 1":
        for loc_p in LOCATION_PATTERNS:
            text = loc_p.sub("trong bài làm", text)

    # If aggressive cleaning emptied the text, provide a safe fallback
    if not text:
        if norm_level == "Level 1":
            text = "Bài làm của em còn một số điểm chưa chính xác về logic và xử lý yêu cầu, em hãy rà soát lại kỹ đề bài và thuật toán."
        elif norm_level == "Level 2":
            err_str = ", ".join(taxonomy_error) if taxonomy_error else "logic"
            text = f"Bài làm gặp vấn đề về {err_str}. Em hãy kiểm tra lại điều kiện biên và cách xử lý dữ liệu."
        else:
            text = "Bài làm cần điều chỉnh lại giải thuật để đáp ứng đầy đủ yêu cầu đề bài."

    return text
