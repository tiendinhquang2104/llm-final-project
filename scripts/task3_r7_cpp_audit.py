#!/usr/bin/env python3
"""Audit archived/new correction text locally without changing inference evidence.

Example: python scripts/task3_r7_cpp_audit.py --archive R6.zip \
  --runs-root outputs/task3/r7/RUN_ID/runs --output outputs/task3/r7/RUN_ID/cpp_audit

The destination must not exist. Compile/run observations apply to supported
synthetic complete programs only; verbal explanations are never assessed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.task3.cpp_checks import VERSION, check_correction, isolation_support


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _records(data: bytes) -> list[dict]:
    rows = [json.loads(line) for line in data.splitlines() if line.strip()]
    return [row.get("record", row) for row in rows]


def _candidates(predictions: list, traces: list):
    for prediction in predictions:
        output = prediction.get("output", {})
        feedback = output.get("feedback")
        if isinstance(feedback, str):
            yield {"sample_id": prediction["sample_id"], "kind": "final_feedback", "feedback": feedback}
    for trace in traces:
        for number, attempt in enumerate(trace.get("attempts", [])):
            text = attempt.get("raw_text")
            stage = attempt.get("stage", "")
            if isinstance(text, str) and stage == "final_feedback":
                yield {
                    "sample_id": trace["sample_id"],
                    "kind": "raw_attempt",
                    "attempt_index": number,
                    "stage": stage,
                    "feedback": text,
                    "original_violations": attempt.get("violations"),
                    "model_generated": attempt.get("model_generated"),
                }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument(
        "--records",
        type=Path,
        action="append",
        default=[],
        help="Optional authorized input JSONL (record wrapper supported).",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.runs_root and not args.archive:
        parser.error("at least --archive or --runs-root is required")
    if args.output.exists():
        parser.error("--output must be a new directory; existing evidence is never overwritten")
    records = {}
    jobs = []
    sources = []
    if args.archive:
        with zipfile.ZipFile(args.archive) as archive:
            bad = archive.testzip()
            if bad:
                parser.error("archive CRC failed: " + bad)
            sources.append({"path": str(args.archive), "sha256": _sha(args.archive.read_bytes()), "crc": "PASS"})
            for name in archive.namelist():
                if name.startswith("input_evidence/") and name.endswith(".jsonl"):
                    raw = archive.read(name)
                    for row in _records(raw):
                        records[row["sample_id"]] = row
                    sources.append({"archive_member": name, "sha256": _sha(raw)})
            for name in sorted(archive.namelist()):
                if name.startswith("runs/") and name.endswith("/predictions.json"):
                    trace_name = name.replace("/predictions.json", "/predictions.traces.json")
                    raw = archive.read(name)
                    trace_raw = archive.read(trace_name) if trace_name in archive.namelist() else b"[]"
                    traces = json.loads(trace_raw)
                    jobs.append(
                        (
                            "archive",
                            name.split("/")[1],
                            name,
                            _sha(raw),
                            json.loads(raw),
                            traces,
                            trace_name,
                            _sha(trace_raw),
                        )
                    )
    for path in args.records:
        raw = path.read_bytes()
        for row in _records(raw):
            existing = records.get(row["sample_id"])
            if existing is not None and existing != row:
                parser.error("conflicting input record: " + row["sample_id"])
            records[row["sample_id"]] = row
        sources.append({"path": str(path), "sha256": _sha(raw)})
    if args.runs_root:
        for path in sorted(args.runs_root.rglob("predictions.json")):
            raw = path.read_bytes()
            trace_path = path.with_name("predictions.traces.json")
            trace_raw = trace_path.read_bytes() if trace_path.exists() else b"[]"
            traces = json.loads(trace_raw)
            jobs.append(
                (
                    "local",
                    str(path.parent.relative_to(args.runs_root)),
                    str(path),
                    _sha(raw),
                    json.loads(raw),
                    traces,
                    str(trace_path),
                    _sha(trace_raw),
                )
            )
    if not jobs:
        parser.error("no runs/*/predictions.json artifacts found")
    args.output.mkdir(parents=True)
    counts = {"final_feedback": Counter(), "raw_attempt": Counter()}
    total = 0
    with (args.output / "checks.jsonl").open("w", encoding="utf-8") as stream:
        for origin, run_id, artifact, artifact_sha, predictions, traces, trace_artifact, trace_sha in jobs:
            for candidate in _candidates(predictions, traces):
                row = records.get(candidate["sample_id"])
                if row is None:
                    result = {
                        "version": VERSION,
                        "status": "NOT_VERIFIED",
                        "reason": "missing_input_record",
                        "explanation_assessment": "NOT_ASSESSED",
                        "compile": None,
                        "tests": [],
                        "extracted_code": None,
                    }
                else:
                    result = check_correction(
                        row,
                        candidate["feedback"],
                        work_root=args.output / "cases",
                        case_tag=f"{origin}-{run_id}-{candidate['sample_id']}-{candidate['kind']}-{candidate.get('attempt_index', 'final')}",
                    )
                raw_attempt = candidate["kind"] == "raw_attempt"
                result_row = {
                    "origin": origin,
                    "run_id": run_id,
                    "artifact": trace_artifact if raw_attempt else artifact,
                    "artifact_sha256": trace_sha if raw_attempt else artifact_sha,
                    **candidate,
                    "check": result,
                }
                stream.write(json.dumps(result_row, ensure_ascii=False) + "\n")
                counts[candidate["kind"]][result["status"]] += 1
                total += 1
    summary = {
        "version": VERSION,
        "records": len(records),
        "runs": len(jobs),
        "observations": total,
        "status_counts_by_kind": counts,
        "sources": sources,
        "isolation": isolation_support(),
        "semantic_assessment": "NOT_PERFORMED",
        "limitations": [
            "Supported exact synthetic single-problem statement contracts only.",
            "Final feedback and original raw attempts counted separately; neither is a semantic score.",
            "Small-case matches do not prove full solution correctness or explanation accuracy.",
            "Compiler/runtime isolation must apply successfully or the check is blocked.",
        ],
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"output": str(args.output), "observations": total, "status_counts_by_kind": counts}, ensure_ascii=False
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
