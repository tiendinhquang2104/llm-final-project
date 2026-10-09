"""Prompts for Task 2 Hướng 1 (API LLM). Pure functions of (exam, sample, demos, cfg); never use `feedback`."""
from __future__ import annotations

import json

from src.task1.prompts import clean_compile_log, format_test_report, number_lines
from src.task2.labels import DESCRIPTIONS, LABELS

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "rationale": {"type": "string"},
        "taxonomy_error": {"type": "array", "items": {"type": "string", "enum": list(LABELS)}},
    },
    "required": ["rationale", "taxonomy_error"],
    "additionalProperties": False,
}

LABEL_GUIDE = "\n".join(f"- {lab}: {DESCRIPTIONS[lab]}" for lab in LABELS)

SYSTEM = (
    "Bạn là giảng viên chấm bài lập trình C++ nhập môn. Nhiệm vụ: xác định các LOẠI LỖI mà bài nộp mắc phải, "
    "chọn trong đúng 10 nhãn dưới đây (đa nhãn). Chỉ gán nhãn khi thấy bằng chứng cụ thể trong code. "
    "Bài không mắc lỗi nào thì trả về danh sách rỗng. Trả về DUY NHẤT một object JSON hợp lệ.\n\n"
    "DANH SÁCH NHÃN:\n" + LABEL_GUIDE
)

OUTPUT_INSTRUCTION = (
    "## YÊU CẦU ĐẦU RA\nTrả về DUY NHẤT JSON dạng:\n"
    '{"rationale": "<1-3 câu: các lỗi chính tìm thấy>", "taxonomy_error": ["<nhãn>", ...]}\n'
    "Chỉ dùng đúng tên nhãn trong danh sách; [] nếu bài không có lỗi."
)


def exam_text(exam: dict) -> str:
    return (f"## ĐỀ BÀI ({exam['exam_id']}, loại {exam['exam_type']}, môn {exam.get('course', '')})\n"
            f"{exam.get('statement', '').strip()}\n")


def submission_text(sample, cfg: dict) -> str:
    s = f"## BÀI NỘP CẦN PHÂN LOẠI\n```cpp\n{number_lines(sample.code, cfg.get('max_code_chars', 12000))}\n```\n"
    if cfg.get("use_aux_signals", False):
        if sample.compile_log:
            s += f"\n### compile_log\n```\n{clean_compile_log(sample.compile_log)}\n```\n"
        if sample.test_report:
            s += f"\n### test_report\n{format_test_report(sample.test_report)}\n"
    return s


def demo_text(demos: list, cfg: dict) -> str:
    if not demos:
        return ""
    lim = cfg.get("demo_max_code_chars", 3000)
    parts = ["## VÍ DỤ ĐÃ ĐƯỢC GIẢNG VIÊN GÁN NHÃN (đề khác, chỉ tham khảo cách gán nhãn)"]
    for k, d in enumerate(demos, 1):
        code = d.code if len(d.code) <= lim else d.code[:lim] + "\n// ...(cắt bớt)"
        parts.append(f"### Ví dụ {k} (đề {d.exam_id}, {d.exam_type})\n```cpp\n{code}\n```\n"
                     f"Nhãn của giảng viên: {json.dumps(d.labels, ensure_ascii=False)}\n")
    return "\n".join(parts) + "\n"


def build_messages(exam: dict, sample, demos: list, cfg: dict) -> list[dict]:
    user = "\n".join(x for x in [exam_text(exam), demo_text(demos, cfg), submission_text(sample, cfg),
                                  OUTPUT_INSTRUCTION] if x)
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def select_demos(pool: list, sample, k: int) -> list:
    """Greedy, deterministic: pick labelled demos (never `sample`) that cover the most not-yet-covered labels,
    preferring the same exam type; one error-free demo ([]) counts as half a new label."""
    if k <= 0:
        return []
    cands = sorted((s for s in pool if s.has_gold and s.sample_id != sample.sample_id),
                   key=lambda s: (s.exam_type != sample.exam_type, s.sample_id))
    chosen, covered = [], set()

    def gain(s) -> float:
        if not s.labels:
            return 0.5 if all(c.labels for c in chosen) else 0.0
        return float(len(set(s.labels) - covered))

    while cands and len(chosen) < k:
        best = max(cands, key=gain)  # max keeps the first of equal gains -> stable order
        chosen.append(best)
        covered |= set(best.labels)
        cands.remove(best)
    return chosen
