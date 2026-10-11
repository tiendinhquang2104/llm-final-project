"""Optional Task 2 augmentation through an API LLM: rewrite a LABELLED gold submission so that it contains one
extra bug of a requested type. The label is known by construction (it is the bug we asked for); only gold code is
sent — never test inputs. Output records feed scripts/run_task2_clm.py (config augment.api_path)."""
from __future__ import annotations

import json
from pathlib import Path

from src.task2.data import Task2Sample
from src.task2.labels import DESCRIPTIONS, LABELS, normalize_labels
from src.utils.json_extractor import extract_json_objects

SCHEMA = {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"],
          "additionalProperties": False}

SYSTEM = ("Bạn là giảng viên lập trình C++. Hãy sửa bài nộp dưới đây để CỐ Ý chèn đúng MỘT lỗi thuộc loại được "
          "yêu cầu, giữ nguyên phần còn lại nhiều nhất có thể, không thêm chú thích nào tiết lộ lỗi. "
          'Trả về DUY NHẤT một object JSON {"code": "<toàn bộ code sau khi sửa>"}.')


def build_messages(exam: dict, sample, label: str) -> list[dict]:
    user = (f"## ĐỀ BÀI ({exam['exam_id']})\n{exam.get('statement', '').strip()}\n\n"
            f"## BÀI NỘP GỐC\n```cpp\n{sample.code}\n```\n\n"
            f"## LOẠI LỖI CẦN CHÈN\n{label}: {DESCRIPTIONS[label]}\n")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def parse_code(text: str, original: str) -> str | None:
    for obj in extract_json_objects(text or ""):
        code = obj.get("code")
        if isinstance(code, str) and code.strip() and code.strip() != original.strip():
            return code
    return None


def plan_jobs(samples, labels, per_label: int) -> list[tuple]:
    """For each label, up to `per_label` labelled samples that do not already carry it (sorted by id)."""
    jobs = []
    for lab in labels:
        cands = [s for s in sorted(samples, key=lambda s: s.sample_id) if s.has_gold and lab not in s.labels]
        jobs.extend((s, lab) for s in cands[:per_label])
    return jobs


def generate_mutants(dataset, jobs, backend, gen: dict) -> list[dict]:
    reqs = [{"sample": s, "exam": dataset.exams[s.exam_id],
             "messages": build_messages(dataset.exams[s.exam_id], s, lab),
             "schema": SCHEMA, "schema_name": "task2_mutant"} for s, lab in jobs]
    outs = backend.generate(reqs, gen) if reqs else []
    records = []
    for (s, lab), texts in zip(jobs, outs):
        code = next((c for c in (parse_code(t, s.code) for t in texts) if c), None)
        if code is None:
            continue
        records.append({"sample_id": f"{s.sample_id}~api-{LABELS.index(lab)}", "source_id": s.sample_id,
                        "exam_id": s.exam_id, "exam_type": s.exam_type, "label": lab,
                        "labels": normalize_labels([*s.labels, lab]), "code": code})
    return records


def load_mutants(path) -> list[Task2Sample]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Task2Sample(sample_id=r["sample_id"], exam_id=r["exam_id"], exam_type=r["exam_type"],
                        language="cpp11", code_file="", code=r["code"], compile_log=None, test_report=None,
                        labels=normalize_labels(r["labels"])) for r in rows]
