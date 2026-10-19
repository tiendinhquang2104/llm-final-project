"""Warning-only adequacy and language screens, separate from disclosure compliance."""

from __future__ import annotations

import re

from src.task3.compliance import _without_diacritics

_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_ENGLISH_PHRASES = re.compile(
    r"(?i)\b(?:file reading error handling|incorrect memory allocation|memory leak|inefficient search algorithm)\b"
)
_POSITIVE_COMPLETION = re.compile(r"(?i)\b(?:tốt|hoàn thiện|hoàn thành|chính xác|đúng hết)\b")
_LEVEL1_SPECIFIC = re.compile(
    r"(?i)\bP[1-4]\b|\bdòng\s*\d+|\b(?:lỗi|sai|thiếu|nguyên nhân|vì|do)\b|```"
)
_LEVEL3_ACTION = re.compile(
    r"(?i)\b(?:nên|cần|hãy|thử|kiểm tra|xem xét|điều chỉnh|cập nhật|khởi tạo|đảm bảo|sử dụng|rà soát)\b"
)
_PLAN_NARRATION = re.compile(r"(?i)dựa trên bảng phân tích|kế hoạch phân tích|structured evidence plan")
_DIRECTION_V2 = re.compile(
    r"(?i)(?:\b(?:hãy|nên|cần|thử|có thể)\s+(?:(?:em|bạn|phải)\s+)?"
    r"(?:thêm|khai báo|dùng|sử dụng|thay|đổi|sửa|cập nhật|khởi tạo|bỏ|tăng|giảm|điều chỉnh|kiểm tra|đối chiếu|đảm bảo|rà soát)\b"
    r"|(?:^|[.!?;]\s*|\n)\s*(?:thêm|khai báo|dùng|thay|sửa|cập nhật|khởi tạo|điều chỉnh|kiểm tra)\b)"
)


def quality_review_flags(record, feedback: str, *, fallback_used: bool = False, version=1) -> dict:
    """Return review candidates only; never assign semantic correctness or a quality score."""
    text = feedback or ""
    if isinstance(version, bool) or version not in (1, 2, 3):
        raise ValueError("quality review version must be 1, 2 or 3")
    if version == 3:
        base = quality_review_flags(record, feedback, fallback_used=fallback_used, version=2)
        if record.target_feedback_level != "Level 1 - Gợi ý nhẹ":
            return base  # Exact R7 behavior, including metadata, outside Level 1.
        base["version"] = 3
        base["flags"] = [f for f in base["flags"] if f not in {"LEVEL1_UNSUPPORTED_PRAISE_REVIEW_CANDIDATE", "LEVEL1_FALSE_PRAISE_REVIEW_CANDIDATE"}]
        normalized = _without_diacritics(text).casefold()
        praise = bool(not fallback_used and re.search(
            r"(?:^|[.!?]\s*)\s*(?:(?:em|ban)\s+)?(?:(?:da|lam|lam bai|thuc hien)\s+)?(?:hoan toan\s+)?(?:dung|chinh xac|tot)(?:\s+(?:roi|qua|lam))?(?:[.!?,]|$)"
            r"|\b(?:bai(?: lam)?|chuong trinh|ket qua|tinh toan|em da|ban da)\b.{0,60}\b(?:dung|chinh xac|hoan thien|hoan thanh|lam(?: bai)? tot|chay tot|hoat dong tot|van hanh tot|xu ly dung)\b",
            normalized,
        ))
        if praise:
            base["flags"].append("LEVEL1_PRAISE_EVIDENCE_REVIEW_CANDIDATE")
        base.update(praise_evidence_status="NOT_VERIFIED" if praise else "NOT_APPLICABLE", correctness_assessed=False, reference_feedback_is_verified_truth=False)
        return base
    flags = []
    if fallback_used:
        flags.append("FALLBACK_EXCLUDED_FROM_SEMANTIC_QUALITY_ASSESSMENT")
    else:
        if record.target_feedback_level == "Level 1 - Gợi ý nhẹ":
            if version == 2 and _POSITIVE_COMPLETION.search(text):
                flags.append("LEVEL1_UNSUPPORTED_PRAISE_REVIEW_CANDIDATE")
            if record.gold_taxonomy and _POSITIVE_COMPLETION.search(text):
                flags.append("LEVEL1_FALSE_PRAISE_REVIEW_CANDIDATE")
            if _LEVEL1_SPECIFIC.search(text):
                flags.append("LEVEL1_DISCLOSURE_REVIEW_CANDIDATE")
        if record.target_feedback_level == "Level 2 - Chẩn đoán" and not re.search(
            r"(?i)\b(?:P[1-4]|hàm|dòng|vòng lặp|điều kiện|biến|lỗi|nguyên nhân)\b|`[^`]+`", text
        ):
            flags.append("LEVEL2_DIAGNOSIS_SPECIFICITY_REVIEW_CANDIDATE")
        if record.target_feedback_level == "Level 3 - Gợi ý sửa" and not (_DIRECTION_V2 if version == 2 else _LEVEL3_ACTION).search(text):
            flags.append("LEVEL3_ACTIONABILITY_REVIEW_CANDIDATE")
        if record.target_feedback_level == "Level 4 - Lời giải mẫu" and record.gold_taxonomy and not re.search(
            r"```|\b(?:return|cout|cin|int|bool|long)\b|\b(?:sửa|điều chỉnh|thay|dùng|sử dụng|kiểm tra)\b", text, re.I
        ):
            flags.append("LEVEL4_COMPLETENESS_REVIEW_CANDIDATE")
    if _CJK.search(text):
        flags.append("NON_VIETNAMESE_CJK_SCRIPT_REVIEW_CANDIDATE")
    if _ENGLISH_PHRASES.search(text):
        flags.append("ENGLISH_PROSE_REVIEW_CANDIDATE")
    if _PLAN_NARRATION.search(text):
        flags.append("INTERNAL_PLAN_NARRATION_REVIEW_CANDIDATE")
    return {
        "flags": flags,
        "assessment_type": "warning_only_candidate_screen",
        "semantic_quality": "NOT_MEASURED",
        "fallback_used": bool(fallback_used),
        "taxonomy_used_as_screen_only": True,
        "version": version,
    }
