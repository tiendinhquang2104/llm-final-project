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
    r"|(?:^|[.!?;]\s*|\n)\s*(?:thêm|khai báo|dùng|thay|sửa|cập nhật|khởi tạo|điều chỉnh|kiểm tra)\b"
    r"|\b(?:hướng sửa|gợi ý sửa)\s*:\s*(?:(?:hãy|nên|cần|thử)\s+)?"
    r"(?:thêm|khai báo|dùng|sử dụng|thay|đổi|sửa|cập nhật|khởi tạo|bỏ|tăng|giảm|điều chỉnh|kiểm tra|đối chiếu|đảm bảo|rà soát)\b)"
)


def validate_code_claims(code: str, claims: list[dict], *, statement: str = "") -> list[dict]:
    """Flag only narrow, statically checkable contradictions; all other claims stay unverified."""
    results = []
    for claim in claims:
        text = str(claim.get("claim", ""))
        evidence = str(claim.get("evidence", ""))
        status, reason = "unverified", "No deterministic source check applies."
        if re.search(r"uninitiali[sz]ed|(?:chưa|không)\s+(?:được\s+)?khởi\s+tạo|(?:chua|khong)\s+(?:duoc\s+)?khoi\s+tao", text, re.I):
            target = re.search(
                r"\b(?:biến|variable)\s+`?([A-Za-z_]\w*)`?[^.!?;]{0,100}(?:uninitiali[sz]ed|(?:chưa|không)\s+(?:được\s+)?khởi\s+tạo|(?:chua|khong)\s+(?:duoc\s+)?khoi\s+tao)"
                r"|\b([A-Za-z_]\w*)\s+(?:is\s+)?uninitiali[sz]ed\b"
                r"|\b([A-Za-z_]\w*)\s*=\s*1\b[^.!?;]{0,60}uninitiali[sz]ed",
                text, re.I,
            )
            name = next((group for group in target.groups() if group), None) if target else None
            initialized = bool(name and re.search(
                rf"\b(?:int|long|short|char|float|double|bool|auto)\s+(?:[A-Za-z_]\w*\s+)*{re.escape(name)}\s*=", code
            ))
            if initialized:
                status, reason = "contradicted", "The named scalar has an explicit initializer in its declaration."
        if re.search(
            r"pointer\s+index(?:ing)?\s+is\s+illegal|không\s+(?:thể|được)\s+(?:truy\s+cập|dùng).{0,30}(?:chỉ\s+số|\[\])|khong\s+(?:the|duoc).{0,30}(?:chi so|\[\])"
            r"|(?:toán tử\s*)?\[\].{0,35}con trỏ.{0,30}(?:không hợp lệ|sai)|con trỏ.{0,35}\[\].{0,30}(?:không hợp lệ|sai)",
            text, re.I,
        ):
            if re.search(r"\*\s*[A-Za-z_]\w*\s*(?:[,;=\[])", code) and re.search(r"\b[A-Za-z_]\w*\s*\[[^]]+\]", code):
                status, reason = "contradicted", "Pointer subscripting is valid C++; other bounds/ownership issues need separate evidence."
        if re.search(
            r"header.{0,60}(?:skip|bỏ qua|bo qua).{0,40}(?:first|đầu|dau).{0,30}(?:data|dữ liệu|du lieu)"
            r"|(?:đọc lại|doc lai).{0,60}(?:tiêu đề|tieu de|header).{0,40}(?:bỏ qua|bo qua).{0,50}(?:dữ liệu|du lieu|hàng|hang)",
            text, re.I,
        ):
            if re.search(r"seekg\s*\(\s*0[^;]*\);[\s\S]{0,150}getline\s*\([^;]+\);[\s\S]{0,120}(?:while|for)\s*\([^)]*getline", code, re.I):
                status, reason = "contradicted", "The stream is rewound, the header is consumed, then data iteration begins."
        if re.search(r"(?:chia|divide)\s*(?:cho|by)?\s*10.{0,50}(?:sai|wrong|error)", text, re.I):
            if re.search(r"Armstrong", statement, re.I) and re.search(r"(?:/=\s*10|/\s*=\s*10)", code):
                status, reason = "contradicted", "Dividing a digit-copy by ten is the standard decimal digit traversal here."
        if re.search(r"\b(?:d|n)\s*=\s*0\b.{0,60}(?:invalid|failure|lỗi|sai)", text, re.I):
            lower = re.search(r"(?:1\s*<=\s*n|n\s*>=\s*1|n\s*>\s*0)", statement)
            if lower:
                status, reason = "unsupported_by_constraints", "Zero is outside the stated input domain; a zero counter initializer is not itself an error."
        if re.search(r"\bp\s*=\s*1\b.{0,60}(?:invalid|failure|lỗi|sai)|(?:invalid|failure|lỗi|sai).{0,60}\bp\s*=\s*1\b", text, re.I):
            if re.search(r"\b(?:long\s+long|long|int)\s+p\s*=\s*1\b", code):
                status, reason = "contradicted", "p is explicitly initialized to the multiplicative identity; this assignment alone is not an error."
        results.append({"claim": text, "evidence": evidence, "status": status, "reason": reason})
    return results


def quality_review_flags(record, feedback: str, *, fallback_used: bool = False, version=1) -> dict:
    """Return review candidates only; never assign semantic correctness or a quality score."""
    text = feedback or ""
    if isinstance(version, bool) or version not in (1, 2, 3, 4):
        raise ValueError("quality review version must be 1, 2, 3 or 4")
    if version == 4:
        from src.task3.adequacy import assess_repair_action
        base = quality_review_flags(record, feedback, fallback_used=fallback_used, version=2)
        base["version"] = 4
        if record.target_feedback_level == "Level 3 - Gợi ý sửa" and not fallback_used:
            action = assess_repair_action(record, text)
            base["repair_action_review"] = action
            base["flags"] = [f for f in base["flags"] if f not in {
                "LEVEL3_ACTIONABILITY_REVIEW_CANDIDATE", "LEVEL3_DIRECTION_REVIEW_CANDIDATE"}]
            if action["kind"] != "specific":
                base["flags"].append("LEVEL3_DIRECTION_REVIEW_CANDIDATE")
        return base
    source_candidate = False
    if record.target_feedback_level != "Level 1 - Gợi ý nhẹ":
        source_reviews = validate_code_claims(
            record.code,
            [{"claim": text, "evidence": ""}],
            statement=record.statement,
        )
        source_candidate = any(
            item["status"] in {"contradicted", "unsupported_by_constraints"}
            for item in source_reviews
        )
    if version == 3:
        base = quality_review_flags(record, feedback, fallback_used=fallback_used, version=2)
        if record.target_feedback_level != "Level 1 - Gợi ý nhẹ":
            if source_candidate and "SOURCE_CONTRADICTION_REVIEW_CANDIDATE" not in base["flags"]:
                base["flags"].append("SOURCE_CONTRADICTION_REVIEW_CANDIDATE")
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
    if source_candidate:
        flags.append("SOURCE_CONTRADICTION_REVIEW_CANDIDATE")
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
        if record.target_feedback_level == "Level 3 - Gợi ý sửa":
            if not re.search(r"\b(?:lỗi|sai|thiếu|chưa|không|đang|vì|do|nguyên nhân|hàm|biến|vòng lặp|điều kiện|phép tính|compiler|undeclared|syntax)\b", text, re.I):
                flags.append("LEVEL3_DIAGNOSIS_REVIEW_CANDIDATE")
            if not re.search(
                r"\b(?:hãy|nên|cần|thử)\s+(?:(?:em|bạn)\s+)?(?:dùng|sử dụng|thay|đổi|sửa|cập nhật|khởi tạo|đảm bảo|bổ sung)\b"
                r"|\b(?:hướng sửa|gợi ý sửa)\s*:\s*(?:(?:hãy|nên|cần|thử)\s+)?(?:dùng|sử dụng|thay|đổi|sửa|cập nhật|khởi tạo|đảm bảo|bổ sung)\b"
                r"|\b(?:kiểm tra|đối chiếu|rà soát)\b.{0,50}\b(?:biến|vòng lặp|điều kiện|phép tính|phép cộng|hàm|đầu vào|kết quả|lệnh)\b",
                text, re.I,
            ):
                flags.append("LEVEL3_DIRECTION_REVIEW_CANDIDATE")
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
