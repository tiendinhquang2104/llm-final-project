"""Heuristic disclosure guard. A pass is not a semantic correctness guarantee."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from src.synth.compliance import _strip_compile_log, level_of
from src.synth.compliance import check as synth_check


@dataclass(frozen=True)
class ComplianceResult:
    ok: bool
    level: int
    violations: tuple[str, ...]
    severe: bool
    semantic_status: str = "not automatically measured"

    @property
    def heuristic_compliance(self) -> bool:
        return self.ok

    @property
    def semantic_compliance(self) -> str:
        return "not_measured"


def check(feedback: str, level: str | int, semantic_check: Callable | None = None):
    lvl = level_of(level)
    text = _strip_compile_log(feedback or "")
    # Instructor diagnoses quote identifiers/expressions; preserve actual fenced code detection.
    calibrated = re.sub(r"(?<!`)`([^`\n]+)`(?!`)", r"\1", text) if lvl == 2 else text
    violations = list(synth_check(calibrated, lvl).violations)
    if lvl == 1 and text.strip() != (feedback or "").strip():
        violations.append("specific_diagnosis")
    if not (feedback or "").strip():
        violations.append("empty_feedback")
    code = bool(
        re.search(
            r"```|~~~|#\s*include|\b(?:int|void|auto)\s+\w+\s*\(|\b(?:for|while)\s*\(|\b(?:cout|cin)\s*(?:<<|>>)|(?:^|\n)\s*(?:return\b[^\n]*;|\w+\s*=\s*[^\n]*;)",
            text,
        )
    )
    if lvl <= 2 and code:
        violations.append("code_solution_leak")
    if lvl <= 2 and re.search(
        r"(?:hãy|em cần|bạn cần|nên)\s+(?:thêm|đổi|thay|sửa|dùng|cập nhật|khai báo|xóa|xoá|bỏ|khởi tạo)|cách sửa|lời giải(?: là|:) |đáp án\s*(?:là|:)|để sửa|fix(?: it)? by",
        text,
        re.I,
    ):
        violations.append("repair_guidance")
    if lvl == 2 and re.search(
        r"\b(?:thay|đổi|sửa|doi|sua|replace|change)\b.{0,100}\b(?:thành|bằng|thanh|bang|to|with)\b",
        text,
        re.I | re.S,
    ):
        violations.append("repair_guidance")
    if lvl == 1 and re.search(
        r"\bP\d+\b|\bvì\b|\bdo\b|nguyên nhân|thiếu (?:dấu|return|cập nhật)|vòng lặp (?:sai|không|vô)|lỗi (?:biên dịch|logic|hàm|mảng)|dòng\s*\d+|because|off.by.one|(?:vong lap|loi logic|nguyen nhan|thieu bien).{0,30}(?:sai|khong|do|thieu)",
        text,
        re.I,
    ):
        violations.append("specific_diagnosis")
    if lvl == 3 and re.search(
        r"\b(?:int|void)\s+main\s*\(|\b(?:int|long|bool|void|auto)\s+\w+\s*\([^)]*\)\s*\{[^}]*return\b|lời giải hoàn chỉnh|complete solution|đáp án\s*(?:là|:)",
        text,
        re.I,
    ):
        violations.append("complete_solution")
    if re.search(
        r"(?:công thức nấu ăn|dự báo thời tiết|bóng đá hôm nay|weather forecast|cooking recipe|cong thuc nau an|du bao thoi tiet|bong da)",
        text,
        re.I,
    ):
        violations.append("irrelevant_feedback")
    semantic_status = "not automatically measured"
    if semantic_check is not None:
        # Local callback returns structured violation names, never an invented diagnosis score.
        violations.extend(semantic_check(feedback, lvl))
        semantic_status = "heuristic callback only; independent semantic assessment not measured"
    violations = tuple(dict.fromkeys(violations))
    severe = lvl <= 2 and bool(
        set(violations)
        & {"code_fence", "code_like", "code_solution_leak", "imperative_fix", "repair_guidance"}
    )
    return ComplianceResult(not violations, lvl, violations, severe, semantic_status)


def fallback(level):
    level_of(level)
    return "Em hãy đối chiếu bài làm với yêu cầu đề và tự kiểm tra lại kết quả. Chưa đủ cơ sở để đưa ra nhận xét cụ thể đáng tin cậy."
