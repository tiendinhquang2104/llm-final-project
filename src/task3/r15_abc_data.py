"""Group before Level projection; public is an opaque protected fingerprint set."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from src.synth.feedback import FEEDBACK_LEVELS
from src.task3.eval_snapshot import structural_shingles
from src.task3.schema import Task3Record, code_hash
from src.task3.round15 import build_messages, parse_response
from src.task3.train import encode_completion
from src.task3.prompts import ContextTooLong
from src.task3.r15_abc_experiment import execution_identity, sha_file


def signature(row):
    if "code" not in row:
        if not row.get("structural_shingles"):
            raise ValueError("protected source lacks fingerprint")
        return dict(row)
    code = row["code"]
    return {**row, "raw_sha256": row.get("source_sha256", hashlib.sha256(code.encode()).hexdigest()),
            "decoded_sha256": hashlib.sha256(code.encode()).hexdigest(),
            "normalized_token_sha256": code_hash(code), "structural_shingles": sorted(structural_shingles(code))}


def source_groups(rows, threshold=.85):
    """Connected components over parents, exact/token hashes and lexical edges."""
    rows = [signature(r) for r in rows]
    parent = list(range(len(rows)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    def union(i, j):
        parent[find(j)] = find(i)
    index = {}
    aliases = [("parent", ("original_submission_id", "group", "group_key")),
               ("hash", ("raw_sha256", "decoded_sha256", "source_sha256", "source_text_sha256")),
               ("token", ("normalized_token_sha256", "code_identity"))]
    for i, row in enumerate(rows):
        for category, keys in aliases:
            for key in keys:
                value = row.get(key)
                if value:
                    tag = (category, value)
                    if tag in index:
                        union(i, index[tag])
                    else:
                        index[tag] = i
    shingles = [set(r["structural_shingles"]) for r in rows]
    edges = 0
    for i, left in enumerate(shingles):
        for j in range(i):
            right = shingles[j]
            if min(len(left), len(right)) < threshold * max(len(left), len(right)):
                continue
            if len(left & right) / max(1, len(left | right)) >= threshold:
                union(i, j)
                edges += 1
    members = defaultdict(list)
    for i, row in enumerate(rows):
        members[find(i)].append(row["sample_id"])
    group_names = {key: execution_identity(sorted(set(value))) for key, value in members.items()}
    by_id = {}
    for i, row in enumerate(rows):
        name = group_names[find(i)]
        if row["sample_id"] in by_id and by_id[row["sample_id"]] != name:
            raise ValueError("same sample ID has conflicting source identity")
        by_id[row["sample_id"]] = name
    return by_id, {"groups": len(members), "near_edges": edges, "threshold": threshold,
                   "method": "identifier-erased five-token shingle Jaccard; lexical screen only"}


def deterministic_sources(rows, limit):
    families = defaultdict(list)
    for r in rows:
        families[r["family"]].append(r)
    for pool in families.values():
        pool.sort(key=lambda r: hashlib.sha256(("42" + r["sample_id"]).encode()).hexdigest())
    selected = []
    while families and len(selected) < limit:
        for family in sorted(list(families)):
            selected.append(families[family].pop(0))
            if not families[family]:
                del families[family]
            if len(selected) == limit:
                break
    return selected


def build_partitions(inventory: dict, exposure: dict, config: dict) -> dict:
    pool = inventory["optimizer_candidates"]
    if any(r.get("origin") == "public" for r in pool):
        raise ValueError("public cannot enter optimizer or bank")
    val = inventory.get("checkpoint_candidates", [])
    comparison = inventory.get("comparison_sources", [])
    public = inventory.get("public", [])
    rows = pool + val + comparison + public + inventory.get("other_sources", [])
    group, audit = source_groups(rows, config.get("near_threshold", .85))
    protected = {group[r["sample_id"]] for r in comparison + public}
    selected_val, val_groups = [], set()
    need = config.get("checkpoint_dev_sources", 14)
    ordered_val = val + deterministic_sources(pool, len(pool))
    for r in ordered_val:
        g = group[r["sample_id"]]
        if len(selected_val) < need and g not in protected | val_groups:
            selected_val.append(r)
            val_groups.add(g)
    selected_train, seen = [], set()
    for r in sorted(pool, key=lambda r: (r.get("origin") != "real-train", r["sample_id"])):
        g = group[r["sample_id"]]
        if g not in protected | val_groups | seen:
            selected_train.append(r)
            seen.add(g)
    requests = []
    for r in comparison:
        for level in (1, 2, 3):
            requests.append({**r, "original_sample_id": r["sample_id"],
                             "original_requested_level": r.get("requested_level"),
                             "sample_id": r["sample_id"] + "@L" + str(level), "level": level,
                             "source_group": group[r["sample_id"]]})
    counts = lambda rs: dict(Counter(r.get("family", "unknown") for r in rs))
    return {"optimizer_train": selected_train, "checkpoint_dev": selected_val, "comparison_dev": requests,
            "comparison_original": comparison, "public_fingerprints": public,
            "group_by_id": group, "group_audit": audit,
            "exposure": exposure, "family_counts": {"train": counts(selected_train), "checkpoint": counts(selected_val),
                                                       "comparison": counts(comparison), "public": counts(public)},
            "checkpoint_replacements": [r["sample_id"] for r in selected_val
                                        if r["sample_id"] not in {x["sample_id"] for x in val}],
            "comparison_exact_sources": len({hashlib.sha256(r["code"].encode()).hexdigest() for r in comparison})}


def query_record(row, level):
    """Whitelist R15 deployment inputs; supervision never goes into provenance."""
    return Task3Record(source="synthetic", sample_id=row["sample_id"],
                       original_submission_id=row.get("original_submission_id", row["sample_id"]),
                       exam_id=row.get("exam_id", row["family"]), exam_type=row.get("exam_type", "single_problem"),
                       statement=row["statement"], grading_policy=row.get("grading_policy"),
                       code_path=row.get("source_member", "private-snapshot.cpp"), code=row["code"],
                       target_feedback_level=next(x for x in FEEDBACK_LEVELS if x.startswith("Level " + str(level))),
                       problems=row.get("problems", []),
                       provenance={"_task3_compile_check": row.get("compiler", {})})


def validate_training_targets(rows: list[dict], partitions: dict) -> dict:
    sources = {r["sample_id"]: r for r in partitions["optimizer_train"]}
    accepted, excluded = [], []
    seen = set()
    for row in rows:
        sid = row.get("sample_id")
        reason = None
        if row.get("annotation_disagreement") == "unresolved":
            reason = "annotation_disagreement"
        elif sid not in sources or sid in seen:
            reason = "outside_partition_or_duplicate"
        elif row.get("source_sha256") != hashlib.sha256(sources[sid]["code"].encode()).hexdigest():
            reason = "source_binding"
        elif not row.get("author") or not row.get("evidence") or row.get("status") != "accepted":
            reason = "missing_review_provenance"
        else:
            targets = row.get("curated_targets", [])
            try:
                if len(targets) != 3 or sorted(t["level"] for t in targets) != [1, 2, 3]:
                    raise ValueError("three Levels required")
                for t in targets:
                    parse_response(json.dumps(t["output"], ensure_ascii=False))
            except (ValueError, KeyError, TypeError):
                reason = "invalid_targets"
        seen.add(sid)
        if reason:
            excluded.append({"sample_id": sid, "reason": reason})
        else:
            accepted.append(row)
    return {"accepted": accepted, "excluded": excluded}


def encode_source_targets(source, targets, tokenizer, max_length, *, prompt_builder=build_messages):
    examples = []
    try:
        for target in sorted(targets, key=lambda t: t["level"]):
            level = target["level"]
            completion = json.dumps(target["output"], ensure_ascii=False)
            messages = prompt_builder(query_record(source, level), [])
            row = encode_completion(tokenizer, messages, completion, max_length)
            examples.append({"sample_id": source["sample_id"], "example_id": source["sample_id"] + "@L" + str(level),
                             "level": level, "kind": "direct", "loss_weight": 1., "messages": messages,
                             "completion": completion, "source_sha256": hashlib.sha256(source["code"].encode()).hexdigest(),
                             "tokens": len(row["input_ids"]), "supervised_tokens": sum(x != -100 for x in row["labels"])})
    except ContextTooLong as exc:
        return [], {"status": "overlength", "reason": str(exc), "truncated": False}
    return examples, {"status": "accepted", "lengths": [e["tokens"] for e in examples], "truncated": False}


def validate_supervision_bindings(sources, reviews, examples, bank, tokenizer, *, prompt_builder=build_messages):
    """Reconstruct prompts/targets from source records, never trust assembled prose."""
    by_review = {r["sample_id"]: r for r in reviews}
    by_source = {r["sample_id"]: r for r in sources}
    expected = []
    for source in sources:
        target = by_review.get(source["sample_id"], {}).get("curated_targets", [])
        if len(target) != 3 or sorted(t["level"] for t in target) != [1, 2, 3]:
            raise ValueError("source target binding requires all three Levels")
        rows, audit = encode_source_targets(source, target, tokenizer, 8192, prompt_builder=prompt_builder)
        if not rows:
            raise ValueError("source target overlength; do not truncate")
        expected.extend(rows)
    if expected != examples:
        raise ValueError("rendered training/source/target binding mismatch")
    if bank is not None:
        if len(bank) != 6 or len({e["sample_id"] for e in bank}) != 6:
            raise ValueError("bank requires six distinct sources")
        for level in (1, 2, 3):
            pair = [e for e in bank if e["level"] == level]
            statuses = [by_review.get(e["sample_id"], {}).get("defect_status") for e in pair]
            if len(pair) != 2 or set(statuses) != {"defect", "scoped_clean"}:
                raise ValueError("bank requires a defect and scoped-clean example per Level")
        for example in bank:
            source = by_source.get(example["sample_id"])
            if source is None:
                raise ValueError("bank source outside optimizer partition")
            target = next(t for t in by_review[example["sample_id"]]["curated_targets"] if t["level"] == example["level"])
            expected_payload = dict(statement=source["statement"], code=source["code"], problems=source.get("problems", []),
                                    grading_policy=source.get("grading_policy"),
                                    compiler={k: source.get("compiler", {}).get(k, "unknown" if k == "status" else "") for k in ("status", "diagnostic")},
                                    output=target["output"])
            if any(example.get(k) != v for k, v in expected_payload.items()):
                raise ValueError("bank source/target/payload binding mismatch")
    return {"sources": len(sources), "examples": len(examples), "bank": len(bank) if bank is not None else None}


def assess_arm_data(partitions, reviews, train, validation, bank, tokenizer, *, prompt_builder=build_messages):
    status = {"A": {"status": "ready"}}
    sources = partitions["optimizer_train"]
    try:
        if not sources or not partitions["checkpoint_dev"] or not train or not validation:
            raise ValueError("C requires separate reviewed optimizer and checkpoint data")
        approved = validate_training_targets([r for r in reviews if r["sample_id"] in {s["sample_id"] for s in sources}], partitions)
        if approved["excluded"] or len(approved["accepted"]) != len(sources):
            raise ValueError("C target review incomplete")
        validate_supervision_bindings(sources, reviews, train, None, tokenizer, prompt_builder=prompt_builder)
        validate_supervision_bindings(partitions["checkpoint_dev"], reviews, validation, None, tokenizer, prompt_builder=prompt_builder)
        status["C"] = {"status": "ready"}
    except (ValueError, KeyError) as exc:
        status["C"] = {"status": "data_blocked", "reason": str(exc)}
    try:
        if not bank:
            raise ValueError("reviewed bank unavailable")
        # B depends on only its six source/target records, even if C data fails.
        ids = {e["sample_id"] for e in bank}
        subset = [s for s in sources if s["sample_id"] in ids]
        ordered_examples = []
        for s in subset:
            target = next(r for r in reviews if r["sample_id"] == s["sample_id"])
            rows, _ = encode_source_targets(s, target["curated_targets"], tokenizer, 8192, prompt_builder=prompt_builder)
            ordered_examples.extend(rows)
        validate_supervision_bindings(subset, reviews, ordered_examples, bank, tokenizer, prompt_builder=prompt_builder)
        status["B"] = {"status": "ready"}
    except (ValueError, KeyError, StopIteration) as exc:
        status["B"] = {"status": "data_blocked", "reason": str(exc)}
    return status
