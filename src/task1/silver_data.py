"""Prepare audited Task 1 silver examples without reading Task 2/3 labels."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.data.leakage_guard import assert_no_feedback_leakage
from src.data.loader import DIMENSIONS, DIM_MAX, load_code, load_exams, resolve_dataset_root
from src.data.prompts import build_task1_messages, messages_to_chatml
from src.data.schema import ChatMLRecord
from src.task1.score import to_cents


@dataclass
class PromptSample:
    sample_id: str
    exam_id: str
    exam_type: str
    language: str
    code: str
    exam_statement: str
    grading_policy: str | None
    compile_log: str | None
    test_report: list[dict[str, Any]] | None
    rubric: dict[str, int | float]
    total_score: int | float


def code_hash(code: str) -> str:
    """Normalize whitespace only; do not claim semantic equivalence."""
    return hashlib.sha256("".join(code.split()).encode("utf-8")).hexdigest()


def _task1_rows(root: Path) -> list[dict[str, Any]]:
    path = root / "task1_grading.json"
    rows = json.loads(path.read_text(encoding="utf-8"))["samples"]
    ids = [row["sample_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate Task 1 sample_id in {path}")
    return rows


def _source_fingerprints(root: str | Path) -> tuple[set[str], set[str]]:
    root = resolve_dataset_root(root)
    ids, hashes = set(), set()
    for row in _task1_rows(root):
        ids.add(row["sample_id"])
        hashes.add(code_hash(load_code(root, row["input"]["code_file"])))
    return ids, hashes


def _validate_output(row: dict[str, Any]) -> tuple[dict[str, int | float], int | float]:
    sid = row["sample_id"]
    output = row.get("output")
    if not isinstance(output, dict) or set(output) != {"rubric", "total_score"}:
        raise ValueError(f"Invalid Task 1 output schema for {sid}")
    rubric = output["rubric"]
    if not isinstance(rubric, dict) or set(rubric) != set(DIMENSIONS):
        raise ValueError(f"Invalid six-dimension rubric for {sid}")
    total = sum(to_cents(rubric[dim], DIM_MAX[dim]) for dim in DIMENSIONS)
    if to_cents(output["total_score"], 10) != total:
        raise ValueError(f"Rubric sum differs from total_score for {sid}")
    return rubric, output["total_score"]


def _quality_reasons(report: str, rubric: dict[str, int | float], total: int | float) -> list[str]:
    reasons = []
    if re.search(r"\bcompile:\s*FAIL\b", report, re.IGNORECASE) and rubric["compilable"] == 1:
        reasons.append("compile_FAIL_but_compilable_1")
    match = re.search(r"statement_examples:\s*\d+\s*\|\s*pass\s+0/([1-9]\d*)\b", report)
    if match and float(total) >= 8:
        reasons.append("zero_statement_examples_pass_but_total_at_least_8")
    return reasons


def prepare_silver_task1(
    silver_root: str | Path,
    gold_root: str | Path,
    public_root: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Write accepted silver JSONL and an audit of every excluded Task 1 record.

    Only the main Task 1 file is read. `heldout` and Task 3 extra IDs have no
    route into the training file. `exec_report` is used solely for quality checks.
    """
    root = resolve_dataset_root(silver_root)
    gold_dataset_root = resolve_dataset_root(gold_root)
    label_space = json.loads((gold_dataset_root / "label_space.json").read_text(encoding="utf-8"))
    gold_ids, gold_hashes = _source_fingerprints(gold_root)
    public_ids, public_hashes = _source_fingerprints(public_root)
    exams = load_exams(root)
    rows = _task1_rows(root)
    main_ids = {row["sample_id"] for row in rows}
    heldout_path = root / "heldout" / "task1_grading.json"
    heldout_ids = (
        {row["sample_id"] for row in json.loads(heldout_path.read_text(encoding="utf-8"))["samples"]}
        if heldout_path.is_file() else set()
    )
    task3_path = root / "task3_feedback.json"
    task3_only_ids = (
        {row["sample_id"] for row in json.loads(task3_path.read_text(encoding="utf-8"))["samples"]}
        - main_ids if task3_path.is_file() else set()
    )
    if main_ids & heldout_ids:
        raise ValueError("Main Task 1 and heldout share sample IDs")
    excluded: list[dict[str, str]] = []
    accepted: list[ChatMLRecord] = []
    seen_code: dict[tuple[str, str], str] = {}

    for row in sorted(rows, key=lambda x: x["sample_id"]):
        sid = row["sample_id"]
        inp = row["input"]
        if Path(inp["code_file"]).parts[0] != "submissions":
            raise ValueError(f"Task 1 code_file is outside main submissions: {sid}")
        exam_id = inp["exam_id"]
        if exam_id not in exams or inp["exam_type"] != exams[exam_id]["exam_type"]:
            raise ValueError(f"Unknown or mismatched exam for {sid}")
        rubric, total = _validate_output(row)
        code = load_code(root, inp["code_file"])
        digest = code_hash(code)
        if sid in gold_ids or sid in public_ids or digest in gold_hashes or digest in public_hashes:
            raise ValueError(f"Silver overlaps gold/public by ID or normalized code: {sid}")
        report = inp.get("exec_report")
        if not isinstance(report, str) or not report.strip():
            raise ValueError(f"Missing exec_report for quality audit: {sid}")
        reasons = []
        key = (exam_id, digest)
        if key in seen_code:
            reasons.append(f"duplicate_code_same_exam_as:{seen_code[key]}")
        else:
            seen_code[key] = sid
        reasons.extend(_quality_reasons(report, rubric, total))
        if reasons:
            excluded.append({"sample_id": sid, "reason": ";".join(reasons)})
            continue

        sample = PromptSample(
            sample_id=sid, exam_id=exam_id, exam_type=inp["exam_type"],
            language=inp.get("language") or exams[exam_id].get("language", "cpp11"),
            code=code, exam_statement=exams[exam_id]["statement"],
            grading_policy=exams[exam_id].get("grading_policy"),
            compile_log=inp.get("compile_log"), test_report=inp.get("test_report"),
            rubric=rubric, total_score=total,
        )
        messages, target = build_task1_messages(sample, label_space)
        rec = ChatMLRecord(
            sample_id=sid, task="task1", exam_id=exam_id, split="silver",
            messages=messages, text=messages_to_chatml(messages), target=target,
        )
        if "exec_report" in messages[0]["content"] + messages[1]["content"] or report in messages[1]["content"]:
            raise ValueError(f"exec_report leaked into prompt for {sid}")
        accepted.append(rec)

    assert_no_feedback_leakage(accepted)
    if len(accepted) + len(excluded) != len(rows):
        raise AssertionError("Silver audit does not account for every Task 1 record")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "task1_silver_train.jsonl"
    with path.open("w", encoding="utf-8") as stream:
        for rec in accepted:
            stream.write(rec.model_dump_json() + "\n")
    manifest = {
        "source": str(root), "n_source_task1": len(rows), "n_accepted": len(accepted),
        "n_excluded": len(excluded), "excluded": excluded,
        "n_heldout_not_read": len(heldout_ids),
        "n_task3_only_not_read": len(task3_only_ids),
        "gold_public_overlap_checked": True, "exec_report_used_as_prompt": False,
    }
    (out / "silver_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
