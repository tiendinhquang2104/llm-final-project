"""Input/output examples quoted in the statement of a stdin/stdout exam, to run submissions on (src/task2/compile.py).

They are part of the exam text the model already reads, not labels or hidden tests. A markdown table
`| Input | Output |` is read row by row; when the **Input:** section lists k bullet lines (Class03-Midterm-2: "the first
line ... / the second line ..."), every k consecutive rows form one example whose input and output are the k cells
joined by newlines. Exams without such a table get no examples."""
from __future__ import annotations

import re

_HEAD = re.compile(r"^\|\s*\**\s*(input|đầu vào)\s*\**\s*\|\s*\**\s*(output|đầu ra)\s*\**\s*\|\s*$", re.I)
_SEP = re.compile(r"^\|\s*:?-{2,}:?\s*\|\s*:?-{2,}:?\s*\|\s*$")
_ROW = re.compile(r"^\|(.*)\|(.*)\|\s*$")
_INPUT_SECTION = re.compile(r"\*\*\s*(input|đầu vào)\s*:?\s*\**\s*:?\s*\n(.*?)(?=\n\s*\*\*|\Z)", re.I | re.S)
_BULLET = re.compile(r"^\s*[-*]\s+\S", re.M)


def _cell(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] == "`":
        text = text[1:-1]
    return text.strip()


def _table_rows(statement: str) -> list[tuple[str, str]]:
    lines = statement.splitlines()
    for i, line in enumerate(lines):
        if not _HEAD.match(line.strip()):
            continue
        rows, j = [], i + 1
        if j < len(lines) and _SEP.match(lines[j].strip()):
            j += 1
        while j < len(lines):
            m = _ROW.match(lines[j].strip())
            if not m:
                break
            rows.append((_cell(m.group(1)), _cell(m.group(2))))
            j += 1
        if rows:
            return rows
    return []


def input_lines(statement: str) -> int:
    """Number of input lines the **Input:** section describes as bullets (1 when it is plain prose)."""
    m = _INPUT_SECTION.search(statement or "")
    return max(1, len(_BULLET.findall(m.group(2)))) if m else 1


def statement_examples(exam: dict) -> list[dict]:
    """[{"input": "...\\n", "expected": "..."}] for a single stdin/stdout exam; [] otherwise."""
    if exam.get("exam_type") == "multi_problem":
        return []
    problems = exam.get("problems") or []
    if problems and not any(p.get("io_mode") == "stdin/stdout" for p in problems):
        return []
    statement = exam.get("statement") or ""
    rows = _table_rows(statement)
    if not rows:
        return []
    k = input_lines(statement)
    if k <= 1 or len(rows) % k:
        k = 1
    out = []
    for a in range(0, len(rows), k):
        group = rows[a:a + k]
        out.append({"input": "\n".join(r[0] for r in group) + "\n",
                    "expected": "\n".join(r[1] for r in group if r[1])})
    return out
