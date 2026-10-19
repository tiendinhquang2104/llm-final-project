"""Heuristic disclosure guard. A pass is not a semantic correctness guarantee."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Callable

from src.synth.compliance import _strip_compile_log, level_of
from src.synth.compliance import check as synth_check


def _without_diacritics(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn").replace("đ", "d").replace("Đ", "D")


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


def check(feedback: str, level: str | int, semantic_check: Callable | None = None, *, version=1):
    if isinstance(version, bool) or version not in (1, 2, 3):
        raise ValueError("guard policy version must be 1, 2 or 3")
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
    normalized = _without_diacritics(text).casefold()
    if version >= 2 and lvl == 1 and re.search(
        r"\b(?:in|xuat|dau ra|ket qua)\b.{0,45}\b(?:thua|thieu|sai|khong dung|khong chinh xac)\b"
        r"|\b(?:thieu|thua|sai)\s+(?:dau\s+(?:cach|cham phay|phay|ngoac)|dinh dang|ky tu)\b"
        r"|\b(?:loi bien dich|loi nhap xuat|loi dinh dang|truy cap ngoai|vong lap vo han)\b",
        normalized,
    ):
        violations.append("specific_diagnosis")
    if version == 3 and lvl == 1:
        # Surface disclosure/accusation policy, never a correctness classifier.
        if re.search(
            r"\bhard[- ]?code\b|\b(?:viet cung|ma co dinh|gia tri co dinh|dau vao|dau ra|input|output|doc file|doc du lieu|nhap du lieu|xuat ket qua|in ket qua|hien thi ket qua|phep chia|phep lay du|vong lap|phan tu cuoi|comment)\b"
            r"|\b(?:phan|doan|buoc)\s+(?:xu ly|doc|nhap|xuat|tinh)\b"
            r"|\b(?:ham|chuc nang)\s+(?:con lai|bi thieu|chua hoan thien|chua hoan thanh)\b",
            normalized,
        ):
            violations.append("level1_technical_disclosure")
        if re.search(
            r"\b(?:loai bo|bo sung|chinh sua|cai dat)\s+(?:(?:viec|cac|mot|nhung|phan|buoc)\s+){0,2}(?:hard[- ]?code|code|ma|ham|bien|dau|lenh|dong|dieu kien|vong lap|phep|thuat toan|doc|nhap|xuat|gia tri|return|tham so)\b"
            r"|\b(?:dung|su dung|ap dung|chon)\s+(?:thuat toan|phep|ham|bien|cong thuc)\b"
            r"|\b(?:thay|doi|chuyen)\s+(?:phep|ham|bien|gia tri|dau|lenh|ma|code|so|kieu|tham so)\b.{0,60}\b(?:thanh|bang|sang)\b"
            r"|\bhoan thien\s+(?:cac\s+)?(?:ham|phan|chuc nang)\b",
            normalized,
        ):
            violations.append("level1_repair_instruction")
        if re.search(
            r"`[^`\n]+`|\b(?:hàm|thủ tục)\s+(?!(?:của|và|trong|ngoài|còn|khác|những|này|đã|chưa)\b)[A-Za-z_][A-Za-z0-9_]*\b"
            r"|\b(?:tên biến\s+[A-Za-z_][A-Za-z0-9_]*\b|biến\s+[A-Za-z_][A-Za-z0-9_]*\s+(?:chưa|không|bị|cần)\b)",
            text, re.I,
        ):
            violations.append("level1_identifier_disclosure")
        if re.search(r"\b(?:sao chep|dao van|copy(?:paste)?|plagiar\w*)\b", normalized):
            violations.append("level1_copying_accusation")
    if lvl == 1 and re.search(
        r"\b(?:hàm|function)\s+[A-Za-z_]\w*|\b(?:vòng\s+lặp|for\s+loop|while\s+loop)\b"
        r"|\b(?:tính\s+lũy\s+thừa|phép\s+tính|công\s+thức)\b",
        text, re.I,
    ):
        violations.append("level1_specific_computation")
    guidance_text = normalized
    if version == 3 and lvl == 1:
        # Learning encouragement is not a code repair command. Preserve v1/v2.
        guidance_text = re.sub(r"\bbo sung\s+(?:kien thuc|ky nang|kinh nghiem)\b", "on luyen", guidance_text)
    if lvl <= 2 and re.search(
        r"\b(?:hay|nen|can|phai)\s+(?:(?:em|ban)\s+)?"
        r"(?:them|doi|thay|sua|dieu chinh|tang|nang|dung|su dung|cap nhat|khai bao|xoa|bo|khoi tao|viet lai)\b"
        r"|cach sua|loi giai(?: la|:)|dap an\s*(?:la|:)|de sua|fix(?: it)? by",
        guidance_text,
    ):
        violations.append("repair_guidance")
    if lvl == 2 and re.search(
        r"\bthay vi\s+(?:(?:em|ban)\s+)?(?:dung|su dung|dung den)\b.{0,80}\b(?:tham so|bien|ham|gia tri|code|ma|cach)\b",
        normalized,
    ):
        violations.append("repair_guidance")
    if lvl == 2 and re.search(
        r"\b(?:thay|doi|sua|replace|change)\b.{0,100}\b(?:thanh|bang|to|with)\b",
        normalized,
        re.S,
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
        & {"code_fence", "code_like", "code_solution_leak", "imperative_fix", "repair_guidance", "level1_repair_instruction"}
    )
    return ComplianceResult(not violations, lvl, violations, severe, semantic_status)


def fallback(level):
    level_of(level)
    return "Chưa đủ cơ sở để đưa ra nhận xét cụ thể đáng tin cậy. Cảm ơn em đã chia sẻ bài làm."
