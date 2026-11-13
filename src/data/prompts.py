"""ChatML prompt builders for Task 1 / 2 / 3 (Qwen2.5-Coder Instruct)."""

from __future__ import annotations

import json
import re
from typing import Any

from src.data.schema import ChatMLRecord, TaskId, UnifiedSample

IM_START = "<|im_start|>"
IM_END = "<|im_end|>"

SYSTEM_TASK1 = (
    "Bạn là giáo viên chấm bài lập trình C++. "
    "Hãy chấm điểm theo rubric 6 chiều và trả về ĐÚNG một JSON object, không giải thích thêm. "
    "Rubric: compilable (0-1), io_format (0-1), logic (0-4), edge_case (0-2), "
    "complexity (0-1), code_quality (0-1); total_score (0-10) = tổng các chiều. "
    "Với đề multi_problem: nếu câu tiên quyết (P1) sai/không biên dịch được thì các câu phụ thuộc nhận 0."
)

SYSTEM_TASK2 = (
    "Bạn là giáo viên phân loại lỗi bài lập trình C++. "
    "Hãy chọn các nhãn lỗi phù hợp (đa nhãn) từ taxonomy cho trước và trả về ĐÚNG một JSON object. "
    "Nếu bài không có lỗi, trả về danh sách rỗng. Không giải thích thêm."
)

SYSTEM_TASK3 = (
    "Bạn là giáo viên đưa phản hồi sư phạm bằng tiếng Việt cho bài lập trình C++. "
    "Tuân thủ đúng target_feedback_level: "
    "Level 1 không nêu nguyên nhân cụ thể và không đưa code; "
    "Level 2 chỉ chẩn đoán, không đưa cách sửa/code; "
    "Level 3 được gợi ý hướng sửa nhưng không đưa lời giải hoàn chỉnh; "
    "Level 4 được phép đưa code sửa / lời giải mẫu. "
    "Chỉ trả về đoạn văn phản hồi, không bọc JSON."
)

TAXONOMY_LIST = [
    "Lỗi biên dịch",
    "Lỗi nhập/xuất",
    "Lỗi logic",
    "Lỗi vòng lặp",
    "Lỗi mảng/chuỗi",
    "Lỗi hàm",
    "Lỗi edge case",
    "Lỗi thuật toán",
    "Lỗi hard-code",
    "Lỗi style",
]


def _format_test_report(test_report: list[dict[str, Any]] | None) -> str:
    if not test_report:
        return "(không có)"
    lines = []
    for i, t in enumerate(test_report, 1):
        status = "PASS" if t.get("passed") else "FAIL"
        lines.append(
            f"  [{i}] {status} | input={t.get('input')!r} | "
            f"expected={t.get('expected')!r} | actual={t.get('actual')!r}"
        )
    return "\n".join(lines)


# The organizer's compile logs in the labelled sample are cut at 2000 characters; a release can ship longer ones
# (one public multi_problem log is ~16K tokens of cascading errors). Same cut everywhere, so a prompt never
# depends on where the log came from.
COMPILE_LOG_MAX_CHARS = 2000


_DIAGNOSTIC = re.compile(r"^\S+:\d+:\d+: (fatal error|error|warning|note):")
_LINKER = re.compile(r"(^/usr/bin/ld|undefined reference|collect2: error|ld returned)")
# Warnings-only log == compiled fine. Shown exactly like an absent log, the only form seen in training (the
# current gold and silver ship no compile_log at all).
NO_COMPILE_ERROR = "(không có compile log)"


def compile_errors_only(log: str) -> str:
    """Keep compiler errors (with their source excerpt) and linker errors; drop warnings/notes.

    A log made only of warnings means the code compiles (the teacher grades e.g. `main()` without a type as
    compilable), but a long block of text in the prompt otherwise reads as a failed build.
    """
    kept, keep = [], False
    for line in log.splitlines():
        m = _DIAGNOSTIC.match(line)
        if m:
            keep = m.group(1) in ("error", "fatal error")
        elif _LINKER.search(line):
            keep = True
        elif line.startswith(("student.cpp: In ", "In file included")):
            keep = False  # context header; the error line that follows carries its own location
        if keep:
            kept.append(line)
    return "\n".join(kept).strip()


def _compile_log_text(log: str | None) -> str:
    if not log or not log.strip():
        return "(không có compile log)"
    errors = compile_errors_only(log.strip())
    return errors[:COMPILE_LOG_MAX_CHARS] if errors else NO_COMPILE_ERROR


def _shared_context(sample: Any, *, include_taxonomy: bool = False) -> str:
    """Build the user-visible context. NEVER includes teacher feedback."""
    parts = [
        f"exam_id: {sample.exam_id}",
        f"exam_type: {sample.exam_type}",
        f"language: {sample.language}",
        f"grading_policy: {sample.grading_policy or '(không có)'}",
        "",
        "## Đề bài",
        sample.exam_statement.strip(),
        "",
        "## Code sinh viên",
        "```cpp",
        sample.code.rstrip(),
        "```",
        "",
        "## Compile log",
        _compile_log_text(sample.compile_log),
        "",
        "## Test report (public)",
        _format_test_report(sample.test_report),
    ]
    if include_taxonomy:
        parts.extend(
            [
                "",
                "## Taxonomy lỗi (đã chẩn đoán)",
                json.dumps(sample.taxonomy_error, ensure_ascii=False),
                "",
                f"## Mức phản hồi yêu cầu\n{sample.target_feedback_level}",
            ]
        )
    return "\n".join(parts)


def messages_to_chatml(messages: list[dict[str, str]]) -> str:
    chunks: list[str] = []
    for m in messages:
        role = m["role"]
        content = m["content"]
        chunks.append(f"{IM_START}{role}\n{content}{IM_END}")
    return "\n".join(chunks) + "\n"


def build_task1_prompt(sample: Any) -> list[dict[str, str]]:
    """System + user messages only: the exact inference prompt of the Task 1 adapter (no label needed)."""
    user = (
        _shared_context(sample)
        + "\n\nHãy chấm điểm và trả về JSON đúng schema:\n"
        '{"rubric":{"compilable":0|1,"io_format":0|1,"logic":0-4,'
        '"edge_case":0-2,"complexity":0|1,"code_quality":0|1},"total_score":0-10}'
    )
    return [{"role": "system", "content": SYSTEM_TASK1}, {"role": "user", "content": user}]


def build_task1_messages(sample: Any) -> tuple[list[dict[str, str]], str]:
    prompt = build_task1_prompt(sample)
    target_obj = {
        "rubric": sample.rubric.model_dump() if hasattr(sample.rubric, "model_dump") else sample.rubric,
        "total_score": sample.total_score,
    }
    target = json.dumps(target_obj, ensure_ascii=False, separators=(",", ":"))
    return prompt + [{"role": "assistant", "content": target}], target


def build_task2_messages(sample: UnifiedSample) -> tuple[list[dict[str, str]], str]:
    labels = ", ".join(TAXONOMY_LIST)
    user = (
        _shared_context(sample)
        + f"\n\nTaxonomy cho phép: [{labels}]\n"
        'Hãy trả về JSON: {"taxonomy_error": ["...", ...]}'
    )
    target = json.dumps(
        {"taxonomy_error": sample.taxonomy_error},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    messages = [
        {"role": "system", "content": SYSTEM_TASK2},
        {"role": "user", "content": user},
        {"role": "assistant", "content": target},
    ]
    return messages, target


def build_task3_messages(sample: UnifiedSample) -> tuple[list[dict[str, str]], str]:
    user = (
        _shared_context(sample, include_taxonomy=True)
        + "\n\nViết phản hồi sư phạm bằng tiếng Việt đúng mức yêu cầu."
    )
    target = sample.feedback.strip()
    messages = [
        {"role": "system", "content": SYSTEM_TASK3},
        {"role": "user", "content": user},
        {"role": "assistant", "content": target},
    ]
    return messages, target


_BUILDERS = {
    "task1": build_task1_messages,
    "task2": build_task2_messages,
    "task3": build_task3_messages,
}


def build_chatml_record(sample: UnifiedSample, task: TaskId, split: str | None = None) -> ChatMLRecord:
    messages, target = _BUILDERS[task](sample)
    return ChatMLRecord(
        sample_id=sample.sample_id,
        task=task,
        exam_id=sample.exam_id,
        split=split,
        messages=messages,
        text=messages_to_chatml(messages),
        target=target,
    )
