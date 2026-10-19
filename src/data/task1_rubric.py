"""Task 1 rubric text and prompt-only removal of the P1 grading gate."""

from __future__ import annotations

import re

from src.data.loader import DIMENSIONS, DIM_MAX


DEFAULT_DESCRIPTIONS = {
    "compilable": "Biên dịch được",
    "io_format": "Đúng định dạng input/output",
    "logic": "Đúng logic",
    "edge_case": "Đúng edge case",
    "complexity": "Độ phức tạp / hiệu năng",
    "code_quality": "Code quality",
}


def rubric_guide(label_space: dict | None = None) -> str:
    """Render the six Task 1 definitions in label_space.json, in schema order."""
    if label_space is None:
        definitions = [
            {"name": name, "range": [0, DIM_MAX[name]], "vi": DEFAULT_DESCRIPTIONS[name]}
            for name in DIMENSIONS
        ]
    else:
        definitions = label_space.get("rubric", {}).get("dimensions")
        if not isinstance(definitions, list):
            raise ValueError("label_space.json must define rubric.dimensions")
    by_name = {entry["name"]: entry for entry in definitions}
    if len(definitions) != len(DIMENSIONS) or set(by_name) != set(DIMENSIONS):
        raise ValueError("label_space.json must define exactly the six Task 1 rubric dimensions")
    lines = ["Rubric Task 1 (theo label_space.json; tổng điểm bằng tổng sáu chiều):"]
    for name in DIMENSIONS:
        entry = by_name[name]
        if entry.get("range") != [0, DIM_MAX[name]] or not str(entry.get("vi", "")).strip():
            raise ValueError(f"Invalid Task 1 rubric definition for {name}")
        lines.append(f"- {name} (0-{DIM_MAX[name]}): {entry['vi'].strip()}")
    return "\n".join(lines)


_GATE_SENTENCES = (
    re.compile(r"\*?Lưu ý:\s*nếu không đọc được file thì các câu còn lại\s*\*?\*?không\*?\*?\s*được chấm\.?", re.I),
    re.compile(r"Nếu (?:câu )?P?1\s*\([^)]*\)\s*sai thì các câu P?2\s*[–-]\s*P?4 không được chấm\.?", re.I),
    re.compile(r"Nếu (?:câu )?P?1\s*sai thì các câu P?2\s*[–-]\s*P?4 không được chấm\.?", re.I),
    re.compile(r"If you fail to read the file, the remaining problems will\s*\*?\*?not\*?\*?\s*be graded\.?", re.I),
    re.compile(r"(?m)^[ \t]*-[ \t]*SIMILAR to others,[ \t]*\r?\n?", re.I),
)


def statement_without_p1_gate(statement: str) -> str:
    """Keep the problem statement, omitting P1 gating and cross-submission comparison."""
    cleaned = statement
    for pattern in _GATE_SENTENCES:
        cleaned = pattern.sub("", cleaned)
    return cleaned.strip()
