"""Privacy-safe loading, grouped isolation, audits and prompt/completion preparation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path, PureWindowsPath

from src.synth.feedback import FEEDBACK_LEVELS
from src.synth.taxonomy import LABEL_SPACE
from src.task3.schema import Task3Record, code_hash, validate_taxonomy


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def safe_code_path(root, reference):
    root = Path(root).resolve()
    if not isinstance(reference, str) or "\\" in reference or PureWindowsPath(reference).drive:
        raise ValueError("invalid code_file path")
    relative = Path(reference)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("code_file traversal")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path.suffix.lower() != ".cpp":
        raise ValueError("code_file must be a .cpp within its dataset root")
    if not path.is_file():
        raise FileNotFoundError(f"missing referenced .cpp: {reference}")
    return path


def decode_code(path):
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1258", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise ValueError("cannot decode source")


def load_task3(root, source):
    root = Path(root).resolve()
    exams = read_json(root / "exams.json")["exams"]
    by_exam = {e["exam_id"]: e for e in exams}
    if len(by_exam) != len(exams):
        raise ValueError("duplicate exam IDs")
    label_path = root / "label_space.json"
    if not label_path.exists() and source == "synthetic-heldout":
        label_path = root.parent / "label_space.json"
    label_space = read_json(label_path)
    if set(label_space["taxonomy_error"]) != set(LABEL_SPACE):
        raise ValueError("taxonomy label-space mismatch")
    definitions = label_space["feedback_level"]
    if {d["level"] for d in definitions} != set(FEEDBACK_LEVELS):
        raise ValueError("feedback level-space mismatch")
    provenance_path = root / "provenance.jsonl"
    provenance = {}
    if provenance_path.exists():
        provenance = {d["sample_id"]: d for d in read_jsonl(provenance_path)}
    payload = read_json(root / "task3_feedback.json")
    samples = payload["samples"]
    if payload.get("n_samples", len(samples)) != len(samples):
        raise ValueError("n_samples mismatch")
    if source == "public":
        fields = " ".join(payload.get("output_fields", []))
        if not all(k in fields for k in ("taxonomy_error", "feedback")):
            raise ValueError("public metadata must declare taxonomy_error and feedback")
    seen, records = set(), []
    for s in samples:
        sid = s["sample_id"]
        if not isinstance(sid, str) or not sid or sid in seen:
            raise ValueError("missing or duplicate sample_id")
        seen.add(sid)
        i, o = s["input"], s.get("output") or {}
        e = by_exam[i["exam_id"]]
        if i.get("exam_type", e["exam_type"]) != e["exam_type"]:
            raise ValueError(f"{sid}: exam_type mismatch")
        if source == "real":
            tax = validate_taxonomy(i.get("taxonomy_error"))
        elif source.startswith("synthetic"):
            tax = validate_taxonomy(o.get("taxonomy_error"))
        else:
            if "taxonomy_error" in i or o:
                raise ValueError(f"{sid}: public must have missing labels and output")
            tax = None
        if source != "public" and (not isinstance(o.get("feedback"), str) or not o["feedback"].strip()):
            raise ValueError(f"{sid}: missing feedback target")
        path = safe_code_path(root, i["code_file"])
        orig = path.stem  # clones refer to the ORIGINAL file, not their -L... ID
        p = provenance.get(sid, provenance.get(orig, {}))
        orig = p.get("duplicate_of") or orig
        records.append(
            Task3Record(
                source=source,
                sample_id=sid,
                original_submission_id=orig,
                exam_id=e["exam_id"],
                exam_type=e["exam_type"],
                statement=e["statement"],
                grading_policy=e.get("grading_policy"),
                problems=e.get("problems", []),
                code_path=str(path),
                code=decode_code(path),
                compile_log=i.get("compile_log") or None,
                test_report=i.get("test_report"),
                target_feedback_level=i["target_feedback_level"],
                gold_taxonomy=tax,
                gold_feedback=o.get("feedback"),
                synthetic_exec_report=i.get("exec_report") if source.startswith("synthetic") else None,
                provenance=p,
                level_definitions=definitions,
            )
        )
    return records


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def fixed_splits(repo, splits_dir="data/splits"):
    """Read the checked-in ID lists only; never recover or regenerate missing splits."""
    repo = Path(repo).resolve()
    parts, origins = {}, {}
    for part in ("train", "val"):
        relative = Path(splits_dir) / f"{part}_ids.json"
        path = repo / relative
        if not path.is_file():
            raise FileNotFoundError(f"required fixed split file is missing: {relative.as_posix()}")
        raw, origin = path.read_bytes(), "working-tree"
        ids = json.loads(raw)
        if not isinstance(ids, list) or any(not isinstance(x, str) for x in ids) or len(ids) != len(set(ids)):
            raise ValueError("invalid fixed split IDs")
        parts[part] = set(ids)
        origins[part] = {"origin": origin, "sha256": hashlib.sha256(raw).hexdigest(), "count": len(ids)}
    if parts["train"] & parts["val"]:
        raise ValueError("fixed split IDs overlap")
    return parts, origins


def assign_splits(records, fixed, seed=42):
    """Union connected original identities, hashes, rename variants and provenance families.

    Fixed real partitions never change. Training entries overlapping evaluation/public are
    quarantined; supplied heldout entries overlapping any other partition are quarantined.
    """
    real_ids = {r.sample_id for r in records if r.source == "real"}
    if real_ids != fixed["train"] | fixed["val"]:
        raise ValueError("real IDs do not exactly match the fixed split")
    parent = list(range(len(records)))

    def find(x):
        while x != parent[x]:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    keys = {}
    for n, r in enumerate(records):
        r.split = {
            "real": "real-train" if r.sample_id in fixed["train"] else "real-val",
            "synthetic": "synthetic-train",
            "synthetic-heldout": "synthetic-heldout",
            "public": "public",
        }[r.source]
        group_keys = [
            f"code:{r.code_hash}",
            f"renamed:{code_hash(r.code, renamed=True)}",
            f"identity:{r.original_submission_id}",
        ]
        p = r.provenance
        for k in ("base_id", "pair_id", "original_submission_id", "duplicate_of"):
            if p.get(k):
                # ~vN denotes a renamed version of the same base
                value = re.sub(r"~v\d+$", "", str(p[k]))
                group_keys.append(f"{k}:{value}")
        for key in group_keys:
            if key in keys:
                union(n, keys[key])
            else:
                keys[key] = n
    groups = defaultdict(list)
    for n, r in enumerate(records):
        groups[find(n)].append(r)
    findings = []
    for group in groups.values():
        identity = sorted(f"{r.source}:{r.sample_id}" for r in group)
        key = hashlib.sha256("\n".join(identity).encode()).hexdigest()
        splits = {r.split for r in group}
        for r in group:
            r.group_key = key
        if "real-train" in splits and "real-val" in splits:
            raise ValueError(
                "fixed real train/validation share a code/provenance group; cannot silently change fixed IDs"
            )
        if len(splits) > 1:
            conflict_reasons = []
            if "real-train" in splits and "real-val" in splits:
                conflict_reasons.append("fixed_real_split_collision")
            if "public" in splits:
                conflict_reasons.append("public_group_overlap")
            if "synthetic-heldout" in splits:
                conflict_reasons.append("heldout_group_overlap")
            if "real-val" in splits:
                conflict_reasons.append("real_validation_overlap")
            members = [
                {
                    "source": member.source,
                    "sample_id": member.sample_id,
                    "partition": member.split,
                }
                for member in sorted(group, key=lambda item: (item.source, item.sample_id))
            ]
            for r in group:
                quarantine = r.source == "synthetic-heldout" or (
                    r.source == "synthetic" and bool(splits & {"real-val", "synthetic-heldout", "public"})
                )
                if quarantine:
                    r.split = "quarantine"
                findings.append(
                    {
                        "source": r.source,
                        "sample_id": r.sample_id,
                        "source_ids": identity,
                        "members": members,
                        "group_sha256": key,
                        "reason": conflict_reasons,
                        "partitions": sorted(splits),
                        "quarantined": quarantine,
                    }
                )
    return findings


def audit(records):
    from src.task3.compliance import check

    counts = {
        k: dict(Counter(str(getattr(r, k)) for r in records))
        for k in ("source", "split", "target_feedback_level", "exam_type")
    }
    counts["taxonomy"] = dict(Counter(t for r in records for t in (r.gold_taxonomy or [])))
    flags, lengths = [], []
    for r in records:
        reasons = []
        lengths.append(len(re.findall(r"\w+|[^\w\s]", r.code)))
        if len(r.compile_log or "") > 8000:
            reasons.append("long_compile_log")
        if not r.compile_log:
            reasons.append("compile_status_unknown_from_log")
        if r.test_report is None:
            reasons.append("missing_optional_test_report")
        if r.source.startswith("synthetic"):
            if not r.provenance:
                reasons.append("missing_optional_synthetic_provenance")
            feedback = r.gold_feedback or ""
            result = check(feedback, r.target_feedback_level)
            reasons.extend(f"gold_compliance:{v}" for v in result.violations)
            if re.search(r"(?:em hãy cố gắng|hãy kiểm tra lại bài|cần xem lại bài|keep trying)", feedback, re.I):
                reasons.append("generic_template_feedback")
            if len(re.findall(r"\b(?:tiên quyết|prerequisite)\b", feedback, re.I)) > 1:
                reasons.append("duplicated_prerequisite_text")
            if r.target_feedback_level.startswith("Level 4") and re.search(
                r"```(?:cpp)?\s*//|viết nốt|bổ sung|TODO|\.\.\.", r.gold_feedback or "", re.I
            ):
                reasons.append("placeholder_level4")
            report = str(r.synthetic_exec_report or "")
            fail = bool(re.search(r"compile:\s*(?:FAIL|ERROR)", report, re.I))
            if fail and "Lỗi biên dịch" not in (r.gold_taxonomy or []):
                reasons.append("signal_contradiction_compile_fail")
            if re.search(r"compile:\s*OK", report, re.I) and "Lỗi biên dịch" in (r.gold_taxonomy or []):
                reasons.append("signal_contradiction_compile_ok")
            failed_probe = any(int(m[1]) < int(m[2]) for m in re.finditer(r"\bpass\s+(\d+)/(\d+)", report, re.I))
            failed_probe |= bool(re.search(r"\b(?:timeout|crash)\s+[1-9]\d*", report, re.I))
            if not r.gold_taxonomy and (failed_probe or re.search(r"(?:FAIL|TIMEOUT|crash\([^)]+\))", report, re.I)):
                reasons.append("signal_contradiction_clean")
        if reasons:
            flags.append({"source": r.source, "sample_id": r.sample_id, "reasons": reasons})
    lengths.sort()
    groups = Counter(r.group_key for r in records)
    return {
        "counts": counts,
        "duplicate_groups": sum(n > 1 for n in groups.values()),
        "largest_group": max(groups.values(), default=0),
        "flags": flags,
        "schema_mismatches": 0,
        "schema_policy": "fail closed on required-field/schema errors",
        "code_lexical_tokens": {
            "method": "regex proxy, NOT model tokenizer",
            "min": min(lengths, default=0),
            "median": lengths[len(lengths) // 2] if lengths else 0,
            "max": max(lengths, default=0),
        },
    }


def prepare(roots, output, repo, seed=42, filter_synthetic="none", *, require_official_split=True):
    from src.task3.prompts import build_messages

    if seed != 42:
        raise ValueError("Task 3 uses the official fixed split with seed 42")
    if filter_synthetic not in {"none", "strict"}:
        raise ValueError("filter_synthetic must be 'none' or 'strict'")
    records, data_manifest = [], {}
    for source, root in roots.items():
        source_records = load_task3(root, source)
        records.extend(source_records)
        root_path = Path(root)
        source_files = {p for p in root_path.rglob("*") if p.is_file()}
        code_digests = sorted(
            hashlib.sha256(path.read_bytes()).hexdigest()
            for path in source_files
            if path.suffix.lower() == ".cpp"
        )
        metadata_files = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(source_files)
            if path.suffix.lower() in {".json", ".jsonl"}
        }
        data_manifest[source] = {
            "metadata_sha256": metadata_files,
            "code_file_count": len(code_digests),
            "code_files_sha256": hashlib.sha256("\n".join(code_digests).encode()).hexdigest(),
            "total_file_count": len(source_files),
        }
    fixed, split_manifest = fixed_splits(repo)
    if require_official_split and (len(fixed["train"]) != 26 or len(fixed["val"]) != 6):
        raise ValueError("official Task 3 split must contain exactly 26 train and 6 validation IDs")
    overlap_report = assign_splits(records, fixed, seed)
    excluded = [finding for finding in overlap_report if finding["quarantined"]]
    report = audit(records)
    before_filter = Counter(r.split for r in records)
    quality_quarantine = Counter()
    quality_filtered_count = 0
    if filter_synthetic == "strict":
        bad = {
            (f["source"], f["sample_id"]): [
                v for v in f["reasons"] if v.startswith(("gold_compliance:", "placeholder_", "signal_contradiction"))
            ]
            for f in report["flags"]
        }
        for r in records:
            reasons = bad.get((r.source, r.sample_id))
            if r.source == "synthetic" and reasons and r.split != "quarantine":
                r.split = "quarantine"
                quality_filtered_count += 1
                quality_quarantine.update(reasons)
                excluded.append(
                    {
                        "source": r.source,
                        "sample_id": r.sample_id,
                        "reason": reasons,
                        "quarantined": True,
                    }
                )
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    partitions = {
        name: [] for name in ("real-train", "real-val", "synthetic-train", "synthetic-heldout", "public", "quarantine")
    }
    for r in records:
        row = {
            "record": asdict(r),
            "prompt": build_messages(r, r.gold_taxonomy) if r.gold_taxonomy is not None else None,
        }
        # Public has no completion key, even when a dataset tries to supply one.
        if r.source != "public":
            row["completion"] = [{"role": "assistant", "content": r.gold_feedback}]
        partitions[r.split].append(row)
    manifest = {
        "dataset_version": "task3-v1",
        "seed": seed,
        "filter_synthetic": filter_synthetic,
        "fixed_splits": split_manifest,
        "data_files_sha256": data_manifest,
        "partitions": {k: len(v) for k, v in partitions.items()},
        "partition_counts_before_quality_filter": dict(before_filter),
        "partition_counts_after_filter": dict(Counter(r.split for r in records)),
        "quality_filtered_count": quality_filtered_count,
        "quality_quarantine_reasons": dict(quality_quarantine),
        "overlap_report": overlap_report,
        "excluded": excluded,
        "audit": report,
        "grouping_rules": [
            "exact code tokens",
            "identifier-renamed code tokens",
            "original submission identity",
            "provenance base/pair/duplicate identity",
        ],
        "strict_filter_rules": [
            "synthetic gold compliance flags",
            "synthetic Level 4 placeholder targets",
            "contradictory synthetic execution signals",
        ],
    }
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent))
    backup = output.with_name(f".{output.name}.backup-{uuid.uuid4().hex}")
    try:
        for split, rows in partitions.items():
            (staging / f"{split}.jsonl").write_text(
                "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8"
            )
        manifest["processed_sha256"] = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in staging.glob("*.jsonl")
        }
        write_json(staging / "manifest.json", manifest)
        if output.exists():
            os.replace(output, backup)
        try:
            os.replace(staging, output)
        except OSError:
            if backup.exists():
                os.replace(backup, output)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest


def load_prepared(root, split):
    return [Task3Record(**row["record"]) for row in read_jsonl(Path(root) / f"{split}.jsonl")]
