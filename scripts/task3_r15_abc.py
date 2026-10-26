#!/usr/bin/env python3
"""Bounded R15 A/B/C experiment. No submission, package installation or hidden tuning."""
from __future__ import annotations

import argparse
from collections import Counter
import gc
import hashlib
import html
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import traceback

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.task3.r15_abc_experiment import (read_json, write_json, stable_json, sha_file, execution_identity,
    inventory_inputs, freeze_experiment, historical_module, run_arm, replay_historical_a,
    verify_file_hashes, adapter_identity, require_branch, validate_export)
from src.task3.r15_abc_experiment import (phase_costs, preflight_records, require_public_sources,
                                         require_selected_checkpoint, verify_selected_adapter)
from src.task3.r15_abc_data import build_partitions, query_record, validate_training_targets
from src.task3.r15_abc_evaluation import score_reviews, select_checkpoint, select_method, RUBRIC
from src.task3.r15_abc_evaluation import taxonomy_summary, paired_analysis


def append(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def verified_freeze(out):
    freeze = read_json(out / "method-freeze.json")
    verify_file_hashes(freeze["files"])
    if execution_identity({k: v for k, v in freeze.items() if k != "identity"}) != freeze["identity"]:
        raise ValueError("method freeze identity mismatch")
    return freeze


def prepare(config, out):
    """Validate explicit agent-authored review intake; never auto-approve targets."""
    if not (out / "source-inventory.private.json").exists():
        from src.task3.direct_sft_data import inventory_sources, public_fingerprints
        source = inventory_sources(Path(config["data_repo"]))
        historic = Path(config["historical_root"]) / "direct-sft-v2-20261021"
        units = read_json(REPO / config["comparison_inputs"])
        gold = {r["sample_id"]: r["taxonomy_error"] for r in read_json(REPO / config["comparison_gold"])}
        known = {r["sample_id"]: r for r in source["candidates"] + source["heldout"]}
        comparison = []
        for u in units:
            r = {**known.get(u["sample_id"], {}), **{k: u["task"][k] for k in ("code", "statement", "problems", "grading_policy", "exam_type")},
                 "sample_id": u["sample_id"], "family": u["family"], "exam_id": u["family"],
                 "requested_level": u["level"], "taxonomy_annotation": gold[u["sample_id"]],
                 "origin": "exposed-comparison-development"}
            comparison.append(r)
        data = dict(optimizer_candidates=read_json(historic / "frozen/train-sources.private.json"),
                    checkpoint_candidates=read_json(historic / "frozen/validation-sources.private.json"),
                    comparison_sources=comparison,
                    public=public_fingerprints(Path(config["data_repo"]) / "data/raw/public_test_release")["entries"],
                    other_sources=source["candidates"] + source["heldout"])
        write_json(out / "source-inventory.private.json", data)
        parts = build_partitions(data, {"status": "historically_exposed_development"}, config)
        write_json(out / "partitions.pre-review.private.json", parts)
    if not all((out / name).is_file() for name in ("target-review.private.json", "partitions.json", "bank.private.json",
                                                    "train-examples.private.json", "checkpoint-examples.private.json")):
        return {"status": "requires_agent_source_and_target_review", "optimizer_started": False,
                "instructions": "Read complete internal sources/constraints, author separate curated targets with evidence, then encode every full source without truncation."}
    parts = read_json(out / "partitions.json")
    reviewed = read_json(out / "target-review.private.json")
    validation = {}
    for key in ("optimizer_train", "checkpoint_dev"):
        ids = {r["sample_id"] for r in parts[key]}
        result = validate_training_targets([r for r in reviewed if r["sample_id"] in ids], {"optimizer_train": parts[key]})
        if result["excluded"] or len(result["accepted"]) != len(ids):
            raise ValueError("incomplete reviewed references for " + key)
        validation[key] = len(result["accepted"])
    return {"status": "prepared_reviewed", "sources": validation, "comparison_requests": len(parts["comparison_dev"]),
            "public": len(parts["public_fingerprints"]), "model_loaded": False}


def public_freeze(out):
    freeze = verified_freeze(out)
    from src.task3.public_contract import verify_public_contract
    contract = verify_public_contract(Path(freeze["config"]["data_repo"]) / "data/raw/public_test_release")
    requested = contract["requested_levels"]
    selection = read_json(out / "selection.json")
    slice_ids = []
    for level, count in ((1, 6), (2, 10), (3, 8)):
        choices = [sid for sid, lev in requested.items() if int(lev[6]) == level]
        choices.sort(key=lambda sid: hashlib.sha256(("42" + sid).encode()).hexdigest())
        slice_ids.extend(choices[:count])
    dependencies = {str((out / "selection.json").resolve()): sha_file(out / "selection.json")}
    selected_adapter = None
    if freeze["arm_data"]["C"]["status"] == "ready" and (out / "checkpoint-selection.json").exists():
        selected_adapter = verify_selected_adapter(out)
        for p in [out / "checkpoint-selection.json", out / "C/training/training-result.json"]:
            dependencies[str(p.resolve())] = sha_file(p)
    for p in (out / "reviews").glob("*.json"):
        dependencies[str(p.resolve())] = sha_file(p)
    value = {"method_identity": freeze["identity"], "selection_identity": execution_identity(selection),
             "dependencies": dependencies, "selected_adapter": selected_adapter,
             "recommended": selection["recommended"], "requested_levels": requested, "audit_ids": slice_ids,
             "arms": ["A", "B", "C"], "quality_does_not_block_observation": True, "submitted": False}
    stable_json(out / "public-freeze.json", value)
    return {"status": "frozen", "requests": len(requested), "audit_slice": len(slice_ids)}


def load_public(config, out):
    public = read_json(out / "public-freeze.json")
    freeze = verified_freeze(out)
    verify_file_hashes(public["dependencies"])
    verify_file_hashes(freeze["public_input_files"])
    if public["selection_identity"] != execution_identity(read_json(out / "selection.json")):
        raise ValueError("public method selection identity mismatch")
    data = historical_module(out, "task3.dataset")
    levels = out / "official-requested-levels.json"
    stable_json(levels, public["requested_levels"])
    records = data.load_task3(Path(config["data_repo"]) / "data/raw/public_test_release", "public", levels)
    lookup = {r.sample_id: r for r in records}
    if set(lookup) != set(public["requested_levels"]):
        raise ValueError("public population mismatch")
    ordered = [lookup[sid] for sid in public["requested_levels"]]
    require_public_sources(ordered, read_json(out / "partitions.json")["public_fingerprints"])
    return ordered


def public_compile(records, config, out):
    """Public sources are read for inference only after public freeze."""
    from src.task3.compiler import check_cpp_syntax
    cache_path = out / "public-compiler-cache.private.json"
    cache = read_json(cache_path) if cache_path.exists() else {}
    historic = read_json(Path(config["historical_root"]) / "round15/public-candidate-zero/compiler-evidence.json")
    sanitize = historical_module(out, "task3.round14").sanitize
    prepared = []
    for r in records:
        h = hashlib.sha256(r.code.encode()).hexdigest()
        if h not in cache:
            raw = check_cpp_syntax(r.code, compiler=config["cpp_compiler"], standard="c++11", timeout_s=3, full_diagnostics=True)
            projection = {k: v for k, v in raw.items() if k in ("status", "returncode", "latency_s", "command")}
            projection["diagnostic"] = (raw.get("stderr_full") or raw.get("stdout_full") or raw.get("diagnostic", ""))[:8000]
            cache[h] = {"projection": projection, "raw": raw,
                        "binding": execution_identity({"source": h, "toolchain": read_json(out / "compiler-cache.private.json")["toolchain"]})}
            write_json(cache_path, cache)
        prepared.append(sanitize(r, cache[h]["projection"]))
    payload = historical_module(out, "task3.round15").query_payload
    shared = [{"sample_id": r.sample_id, "payload": payload(r)} for r in prepared]
    stable_json(out / "public-inputs.private.json", shared)
    stable_json(out / "public-input-binding.json", {"payload_identity": execution_identity(shared),
        "compiler_cache_sha256": sha_file(cache_path), "public_freeze_sha256": sha_file(out / "public-freeze.json")})
    return prepared


def infer_one(arm, split, checkpoint, out):
    freeze = verified_freeze(out)
    if freeze["arm_data"][arm]["status"] != "ready":
        raise ValueError(arm + " data_blocked: " + freeze["arm_data"][arm]["reason"])
    config = {**freeze["config"], "method_freeze_identity": freeze["identity"]}
    bank = read_json(out / "bank.private.json")
    parts = read_json(out / "partitions.json")
    adapter = None
    if arm == "C":
        trained = read_json(out / "C/training/training-result.json")
        if trained["status"] != "complete":
            raise ValueError("C training incomplete")
        if split != "checkpoint-dev":
            selected_choice = verify_selected_adapter(out)
            require_selected_checkpoint(split, checkpoint, selected_choice["name"])
            name = selected_choice["name"]
            config["checkpoint_selection_identity"] = execution_identity(read_json(out / "checkpoint-selection.json"))
        else:
            name = read_json(out / "checkpoint-selection.json")["selected"] if checkpoint == "selected" else checkpoint
        choice = next(c for c in trained["checkpoints"] if c["name"] == name)
        adapter = Path(choice["adapter_path"])
        if adapter_identity(adapter) != choice["adapter_identity"]:
            raise ValueError("C checkpoint adapter identity drift")
    if split == "public":
        pfreeze = read_json(out / "public-freeze.json")
        if pfreeze["method_identity"] != freeze["identity"]:
            raise ValueError("public/method freeze mismatch")
        records = public_compile(load_public(config, out), config, out)
    elif split == "comparison-dev":
        records = [query_record(r, r["level"]) for r in parts["comparison_dev"]]
    else:
        records = []
        for row in parts["checkpoint_dev"]:
            for level in (1, 2, 3):
                records.append(query_record({**row, "sample_id": row["sample_id"] + "@L" + str(level)}, level))
    phase = out / arm / split
    if arm == "C" and split == "checkpoint-dev":
        phase /= name
    os.environ.update(HF_HOME=config["hf_cache"], HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    inf = historical_module(out, "task3.inference")
    runtime = historical_module(out, "task3.round15")
    tokenizer = inf.load_tokenizer(config)
    budget = preflight_records(records, arm, bank, tokenizer, config, runtime=runtime)
    stable_json(phase / "initial-tokenizer-budget.json", budget)
    if arm == "A" and split == "public" and not (phase / "execution-binding.json").exists():
        try:
            result = replay_historical_a(records, config, phase, tokenizer)
            official_validate(phase, records)
            return result
        except ValueError as exc:
            write_json(phase / "historical-cache-unavailable.json", {"reason": str(exc), "fresh_pass_allowed": True})
    started = time.perf_counter()
    backend = inf.HFBackend({**config, **({"adapter": str(adapter)} if adapter else {})}, tokenizer)
    try:
        runtime_before = backend.runtime_metadata()
        write_json(phase / "runtime-before.json", runtime_before)
        result = run_arm(records, arm, config, phase, examples=bank, adapter=adapter, backend=backend)
        write_json(phase / "runtime-after.json", {**backend.runtime_metadata(), "phase_wall_s": time.perf_counter() - started})
        official_validate(phase, records)
        return {"arm": arm, "split": split, "completed": len(result["predictions"]), "unresolved": len(result["unresolved"])}
    finally:
        del backend
        gc.collect()
        import torch
        torch.cuda.empty_cache()


def official_validate(phase, records):
    requested = {r.sample_id: r.target_feedback_level for r in records}
    write_json(phase / "requested-levels.json", requested)
    if not (phase / "predictions.json").exists():
        return
    command = [sys.executable, str(REPO / "scripts/validate_task3_submission.py"),
               "--predictions", str(phase / "predictions.json"), "--requested-levels", str(phase / "requested-levels.json")]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    write_json(phase / "official-validation.json", {"command": command, "exitcode": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr, "sha256": sha_file(phase / "predictions.json")})
    if result.returncode:
        raise ValueError("official validator rejected complete export")


def manifests(out, split, checkpoint_names=None):
    parts = read_json(out / "partitions.json")
    reviews = {r["sample_id"]: r for r in read_json(out / "target-review.private.json")}
    comparison_refs = {r["sample_id"]: r for r in read_json(out / "comparison-references.private.json")}
    if split == "checkpoint-dev":
        requests = [{**row, "original_sample_id": row["sample_id"], "sample_id": row["sample_id"] + "@L" + str(level),
                     "level": level, "source_group": parts["group_by_id"][row["sample_id"]]}
                    for row in parts["checkpoint_dev"] for level in (1, 2, 3)]
        methods = [("A", out / "A/checkpoint-dev"), *[(name, out / "C/checkpoint-dev" / name) for name in checkpoint_names]]
    else:
        requests = parts["comparison_dev"]
        methods = [(a, out / a / "comparison-dev") for a in "ABC"]
    result = {}
    for method, phase in methods:
        preds = read_json(phase / "predictions.json") if (phase / "predictions.json").exists() else read_json(phase / "partial.predictions.json") if (phase / "partial.predictions.json").exists() else []
        traces = {r["sample_id"]: r for r in read_json(phase / "traces.json")} if (phase / "traces.json").exists() else {}
        lookup = {r["sample_id"]: r["output"] for r in preds}
        rows = []
        for r in requests:
            reference = reviews[r["original_sample_id"]] if split == "checkpoint-dev" else comparison_refs[r["original_sample_id"]]
            rows.append({"sample_id": r["sample_id"], "level": r["level"], "source_group": r["source_group"],
                         "output_sha256": execution_identity(lookup.get(r["sample_id"])), "reference_sha256": execution_identity(reference),
                         "origin": traces.get(r["sample_id"], {}).get("final_origin", "unresolved"), "completed": r["sample_id"] in lookup})
        result[method] = {"requests": rows}
    return result


def make_blind_packet(out, split, checkpoint_names=None):
    population = manifests(out, split, checkpoint_names)
    folder = out / "reviews"
    stable_json(folder / (split + "-manifests.json"), population)
    entries = [(method, r) for method, m in population.items() for r in m["requests"]]
    random.Random(42).shuffle(entries)
    mapping = {}
    for i, (method, req) in enumerate(entries):
        anon = f"review-{i:04d}"
        mapping[anon] = {"method": method, **req}
    stable_json(folder / (split + "-blind-map.private.json"), mapping)
    parts = read_json(out / "partitions.json")
    sources = parts["checkpoint_dev"] if split == "checkpoint-dev" else parts["comparison_original"]
    refs = {r["sample_id"]: r for r in read_json(out / ("target-review.private.json" if split == "checkpoint-dev" else "comparison-references.private.json"))}
    source_by = {r["sample_id"]: r for r in sources}
    groups, phase_cache = {}, {}
    for anon, info in mapping.items():
        method, sid = info["method"], info["sample_id"]
        original = sid.rsplit("@L", 1)[0]
        source = source_by[original]
        group = info["source_group"]
        if group not in groups:
            groups[group] = {"source_group": group, "source": source, "reference": refs[original], "outputs": []}
        if method not in phase_cache:
            phase = out / ("A/checkpoint-dev" if method == "A" and split == "checkpoint-dev" else
                           "C/checkpoint-dev/" + method if split == "checkpoint-dev" else method + "/comparison-dev")
            p = phase / "predictions.json"
            if not p.exists():
                p = phase / "partial.predictions.json"
            outputs = {r["sample_id"]: r["output"] for r in read_json(p)} if p.exists() else {}
            traces = {r["sample_id"]: r for r in read_json(phase / "traces.json")} if (phase / "traces.json").exists() else {}
            phase_cache[method] = outputs, traces
        outputs, traces = phase_cache[method]
        trace = traces.get(sid, {})
        groups[group]["outputs"].append({"anonymous_id": anon, **{k: v for k, v in info.items() if k != "method"},
            "output": outputs.get(sid), "first_raw_output": trace.get("first_raw_schema_output"),
            "first_raw_text": trace.get("first_raw_text"), "fallback": trace.get("fallback_used", False)})
    stable_json(folder / (split + "-blind-packet.private.json"), list(groups.values()))
    return population


def select(out, checkpoint=False):
    names = [c["name"] for c in read_json(out / "C/training/training-result.json")["checkpoints"]] if checkpoint else None
    split = "checkpoint-dev" if checkpoint else "comparison-dev"
    population = make_blind_packet(out, split, names)
    review_path = out / "reviews" / (split + ".json")
    if not review_path.exists():
        return {"status": "requires_blinded_agent_review", "manifest": str(out / "reviews" / (split + "-manifests.json"))}
    ledgers = read_json(review_path)
    metrics = {name: score_reviews(ledgers.get(name, []), manifest) for name, manifest in population.items()}
    if checkpoint:
        candidates = [{**{k: c[k] for k in ("name", "step", "adapter_identity")}, "metrics": metrics[c["name"]]}
                      for c in read_json(out / "C/training/training-result.json")["checkpoints"]]
        selection = select_checkpoint(candidates, [], baseline_score=metrics["A"]["JointScore"])
        selection["baseline_metrics"] = metrics["A"]
        stable_json(out / "checkpoint-selection.json", selection)
    else:
        selection = select_method(metrics)
        selection["metrics_by_arm"] = metrics
        stable_json(out / "selection.json", selection)
    return {k: selection[k] for k in selection if k in ("selected", "recommended", "promotion_eligible")}


def verify(out, *, preservation=True):
    freeze = verified_freeze(out)
    problems, candidates = [], {}
    if (out / "checkpoint-selection.json").exists():
        verify_selected_adapter(out)
    if (out / "public-freeze.json").exists():
        public = read_json(out / "public-freeze.json")
        verify_file_hashes(public["dependencies"])
        if public["method_identity"] != freeze["identity"] or public["selection_identity"] != execution_identity(read_json(out / "selection.json")):
            raise ValueError("public selection dependency mismatch")
        if public["selected_adapter"] is not None and public["selected_adapter"] != verify_selected_adapter(out):
            raise ValueError("public selected adapter differs from semantic selection")
        if (out / "public-input-binding.json").exists():
            shared = read_json(out / "public-input-binding.json")
            if (shared["payload_identity"] != execution_identity(read_json(out / "public-inputs.private.json"))
                    or shared["compiler_cache_sha256"] != sha_file(out / "public-compiler-cache.private.json")
                    or shared["public_freeze_sha256"] != sha_file(out / "public-freeze.json")):
                raise ValueError("shared public source/compiler payload identity mismatch")
    for binding_path in out.glob("[ABC]/**/execution-binding.json"):
        sealed = read_json(binding_path)
        if execution_identity(sealed["binding"]) != sealed["identity"]:
            problems.append(str(binding_path) + ": binding digest")
        for terminal in binding_path.parent.glob("requests/*/terminal.json"):
            item = read_json(terminal)
            try:
                verify_file_hashes(item["files"])
                if item["outer_identity"] != sealed["identity"]:
                    raise ValueError("outer binding mismatch")
                for trace in item["traces"] + [e["trace"] for e in item["errors"].values()]:
                    if len(trace["attempts"]) > 3:
                        raise ValueError("attempt budget exceeded")
                    for index, row in enumerate(trace["attempts"], 1):
                        if row["attempt"] != index or row["prompt_sha256"] != execution_identity(row["prompt_messages"]):
                            raise ValueError("journal order or prompt hash mismatch")
            except ValueError as exc:
                problems.append(str(terminal) + ": " + str(exc))
    if preservation:
        protected = read_json(out / "preservation-before.json")
        changed = [p for p, v in protected.items() if not Path(p).is_file() or sha_file(p) != v["sha256"]]
        if changed:
            problems.extend(changed)
    for arm in "ABC":
        phase = out / arm / "public"
        p = phase / "predictions.json"
        if p.exists():
            requested = read_json(out / "public-freeze.json")["requested_levels"]
            validation = validate_export(read_json(p), requested)
            candidates[arm] = {"complete": validation["valid"], "sha256": sha_file(p), "file": str(p)}
            if not validation["valid"]:
                problems.append(arm + ": incomplete export named complete")
        else:
            candidates[arm] = {"complete": False, "sha256": None}
    result = {"valid": not problems, "problems": problems, "candidates": candidates,
              "method_identity": freeze["identity"], "model_loaded": False, "protected_files": len(read_json(out / "preservation-before.json"))}
    write_json(out / "final-verification.json", result)
    if problems:
        raise ValueError("offline verification failed: " + str(problems[:5]))
    return result


def report(out):
    """Private side-by-side artifacts; the tracked report contains metadata only."""
    parts = read_json(out / "partitions.json")
    selection = read_json(out / "selection.json") if (out / "selection.json").exists() else {"recommended": "A", "status": "semantic_selection_pending"}
    comparison_refs = {r["sample_id"]: r for r in read_json(out / "comparison-references.private.json")}
    rows = {}
    costs = {"arms": {}, "review_cost": {"type": "Codex agent static review", "tokens": None, "cost": None,
                                             "note": "Runtime does not expose per-review metering; not assumed zero."}}
    for arm in "ABC":
        for phase in (out / arm).rglob("result.json"):
            value = read_json(phase)
            costs["arms"][str(phase.parent.relative_to(out))] = phase_costs(phase.parent)
    training = out / "C/training/training-result.json"
    if training.exists():
        costs["training"] = read_json(training)
    write_json(out / "costs-and-runtime.json", costs)
    analysis = {"semantic": selection.get("metrics_by_arm"), "taxonomy_secondary": {}, "raw_and_final": {},
                "paired": {}, "exposure": parts["exposure"], "family_counts": parts["family_counts"],
                "source_groups": len({r["source_group"] for r in parts["comparison_dev"]}),
                "requested_levels_original": {}, "public_gold_authored": False}
    for split, casefile in (("comparison-dev", "CASEBOOK.internal.private.html"), ("public", "CASEBOOK.public.private.html")):
        if split == "comparison-dev":
            requests = parts["comparison_dev"]
        elif (out / "public-freeze.json").exists():
            records = load_public(read_json(out / "method-freeze.json")["config"], out)
            requests = [{"sample_id": r.sample_id, "level": int(r.target_feedback_level[6]), "code": r.code,
                         "statement": r.statement} for r in records]
        else:
            continue
        predictions = {}
        phase_traces = {}
        for arm in "ABC":
            p = out / arm / split / "predictions.json"
            if not p.exists():
                p = p.with_name("partial.predictions.json")
            predictions[arm] = {r["sample_id"]: r["output"] for r in read_json(p)} if p.exists() else {}
            tp = out / arm / split / "traces.json"
            phase_traces[arm] = {t["sample_id"]: t for t in read_json(tp)} if tp.exists() else {}
            ep = out / arm / split / "unresolved.json"
            if ep.exists():
                phase_traces[arm].update({sid: e["trace"] for sid, e in read_json(ep).items()})
            captures = [a for t in phase_traces[arm].values() for a in t["attempts"]]
            analysis["raw_and_final"][arm + "/" + split] = {"requested": len(requests), "final_completed": len(predictions[arm]),
                "raw_schema_count": sum(t.get("first_raw_schema_output") is not None for t in phase_traces[arm].values()),
                "fallback_count": sum(bool(t.get("fallback_used")) for t in phase_traces[arm].values()),
                "final_origins": dict(Counter(t.get("final_origin", "unresolved") for t in phase_traces[arm].values())),
                "shots_per_attempt": dict(Counter(a.get("examples_used", 0) for a in captures)),
                "raw_disclosure_flags": dict(Counter(flag for t in phase_traces[arm].values() for flag in t.get("first_raw_disclosure_violations", []))),
                "final_audit_flags": dict(Counter(flag for t in phase_traces[arm].values() for flag in t.get("final_audit_flags", [])))}
            if split == "comparison-dev":
                gold = [r["taxonomy_annotation"] for r in requests]
                pred = [predictions[arm].get(r["sample_id"], {}).get("taxonomy_error") for r in requests]
                raw = [phase_traces[arm].get(r["sample_id"], {}).get("first_raw_schema_output") for r in requests]
                analysis["taxonomy_secondary"][arm] = {"final": taxonomy_summary(gold, pred),
                    "raw": taxonomy_summary(gold, [p["taxonomy_error"] if p else None for p in raw])}
                if selection.get("metrics_by_arm", {}).get(arm):
                    cases = selection["metrics_by_arm"][arm]["cases"]
                    originals = {r["sample_id"] for r in requests if r["level"] == r["original_requested_level"]}
                    subset = [c for c in cases if c["sample_id"] in originals]
                    analysis["requested_levels_original"][arm] = {"requests": len(subset), "joint_pass": sum(c["joint_pass"] for c in subset),
                                                                 "unknown": sum(c["unknown"] for c in subset)}
        content = ["<!doctype html><meta charset='utf-8'><title>Private R15 ABC casebook</title>",
                   "<style>body{font:16px system-ui;margin:24px}pre{white-space:pre-wrap}td{vertical-align:top;width:33%;padding:10px;border:1px solid #bbb}table{width:100%;table-layout:fixed}</style>",
                   "<h1>Private R15 ABC — " + split + "</h1><p>Agent review; public has no authored gold labels.</p>"]
        cases = []
        for r in requests:
            outputs = {arm: predictions[arm].get(r["sample_id"]) for arm in "ABC"}
            reference = comparison_refs[r["original_sample_id"]] if split == "comparison-dev" else None
            cases.append({"request": r, "reference": reference, "outputs": outputs})
            content.extend(["<h2>" + html.escape(r["sample_id"]) + " · L" + str(r["level"]) + "</h2>",
                            "<details><summary>Statement/source</summary><pre>" + html.escape(r["statement"] + "\n\n" + r["code"]) + "</pre></details><table><tr>"])
            if reference:
                content.insert(len(content) - 1, "<details><summary>Private source review / original reference</summary><pre>" + html.escape(json.dumps(reference, ensure_ascii=False, indent=2)) + "</pre></details>")
            for arm, output in outputs.items():
                content.append("<td><b>" + arm + "</b><pre>" + html.escape(json.dumps(output, ensure_ascii=False, indent=2)) + "</pre></td>")
            content.append("</tr></table>")
        (out / casefile).write_text("\n".join(content))
        rows[split] = cases
    write_json(out / "comparison.private.json", {"selection": selection, "cases": rows})
    if selection.get("metrics_by_arm"):
        for arm in ("B", "C"):
            analysis["paired"][arm + "_minus_A"] = paired_analysis(selection["metrics_by_arm"]["A"], selection["metrics_by_arm"][arm])
    raw_review = out / "reviews/comparison-dev-raw.json"
    if raw_review.exists():
        analysis["raw_semantic_reviews"] = read_json(raw_review)
    write_json(out / "analysis.private.json", analysis)
    examples = sorted(rows.get("comparison-dev", []), key=lambda r: execution_identity([42, r["request"]["sample_id"]]))[:12]
    text = ["# Ví dụ private — chọn trước theo hash, không phải điểm leaderboard\n"]
    for c in examples:
        text.append("## " + c["request"]["sample_id"] + "\n")
        text.extend(arm + ": " + json.dumps(value, ensure_ascii=False) + "\n" for arm, value in c["outputs"].items())
    (out / "EXAMPLES.vi.private.md").write_text("\n".join(text))
    metadata = {"recommended": selection["recommended"], "comparison_requests": len(parts["comparison_dev"]),
                "comparison_original_ids": len(parts["comparison_original"]), "comparison_exact_sources": parts["comparison_exact_sources"],
                "train_sources": len(parts["optimizer_train"]), "checkpoint_sources": len(parts["checkpoint_dev"]),
                "new_leaderboard_scores": [], "submitted": False}
    write_json(out / "report-metadata.json", metadata)
    freeze = read_json(out / "method-freeze.json")
    report_lines = ["# Task 3 R15 A/B/C — 25/10/2026", "",
        "Thử nghiệm có giới hạn; không submit leaderboard, không đổi root predictions và không chỉnh output theo từng ID.", "",
        "A: R15 zero-shot; B: tối đa hai examples cùng Level từ bank sáu nguồn đã review; C: một run QLoRA r16/alpha32, lr2e-5, một epoch, chọn checkpoint bằng semantic checkpoint dev.", "",
        f"Dữ liệu: {len(parts['optimizer_train'])} nguồn train; {len(parts['checkpoint_dev'])} nguồn checkpoint dev; 90 requests comparison từ30 ID/27 exact-source hashes. Đây là development đã phơi nhiễm, có family overlap; không phải heldout mới.", "",
        "Review do Codex agent thực hiện, không phải giảng viên hay human-independent. Original annotations tách khỏi curated targets. Unknown và neutral fallback không được tính joint success. JointScore chỉ là proxy nội bộ theo trọng số115/163/50, không phải điểm grader.", "",
        f"Recommendation chung: **{selection['recommended']}**. Public observation của các arm khác không bị quality gate chặn.", "",
        "| Arm | JointScore nội bộ | J1 | J2 | J3 | Unsupported | L2 repair leak | Critical misses |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for arm, m in selection.get("metrics_by_arm", {}).items():
        report_lines.append(f"| {arm} | {m['JointScore']:.4f} | {m['per_level']['1']['rate']:.4f} | {m['per_level']['2']['rate']:.4f} | {m['per_level']['3']['rate']:.4f} | {m['unsupported_claim_cases']} | {m['l2_repair_leak_cases']} | {m['critical_finding_misses']} |")
    report_lines.extend(["", "Public candidates (chỉ schema/coverage, không phải public accuracy):", "", "| Arm | Complete | SHA256 |", "|---|---|---|"])
    for arm in "ABC":
        p = out / arm / "public/predictions.json"
        report_lines.append(f"| {arm} | {p.exists()} | {sha_file(p) if p.exists() else 'unavailable / incomplete'} |")
    report_lines.extend(["", "Không có điểm leaderboard mới được đo hoặc receipt mới trong phiên này. Hai claim lịch sử ~0,34 và0,3834 vẫn chưa được xác minh bằng receipt.", "",
        "Private artifacts giữ complete source/reference/raw/final casebooks, review ledgers, grouped bootstrap/paired tables, taxonomy phụ so nhãn gốc, shot counts, runtime/VRAM/costs và commands. Review-token/cost metering không có sẵn, được ghi unknown thay vì0.", "",
        f"Method identity: `{freeze['identity']}`. Runtime lịch sử26 modules được snapshot opt-in từ commit f6a17b13a3954755dd55809d9082784e36391546; không rollback module cũ. Không có L4 supervision và không tuyên bố C được kiểm chứng L4.", "",
        "Các giới hạn: lexical near-duplicate screen không chứng nhận mọi trùng ngữ nghĩa; ba original comparison IDs có tranh chấp whitespace giữ unknown; scoped-clean không chứng minh đúng mọi đầu vào; B/C có lượng supervision khác nhau. Cấu hình là giả thuyết thử nghiệm, không được gọi là tối ưu."])
    (REPO / "reports/task3/TASK3_R15_ABC_20261025.md").write_text("\n".join(report_lines) + "\n")
    return metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("inventory", "prepare", "freeze", "train-c", "select-checkpoint", "select-method", "freeze-public", "report", "verify"):
        sub.add_parser(name)
    infer = sub.add_parser("infer")
    infer.add_argument("--arm", choices=["A", "B", "C", "all"], required=True)
    infer.add_argument("--split", choices=["checkpoint-dev", "comparison-dev", "public"], required=True)
    infer.add_argument("--checkpoint", choices=["all", "selected", "half", "final"], default="selected")
    args = parser.parse_args(argv)
    if args.command == "infer" and args.split != "checkpoint-dev" and args.checkpoint == "all":
        parser.error("--checkpoint all is allowed only on checkpoint-dev")
    import yaml
    config = yaml.safe_load(Path(args.config).read_text())
    out = Path(args.out).resolve()
    if out != (REPO / config["out"]).resolve() or not out.is_relative_to(REPO / "outputs/task3"):
        raise ValueError("output must match the named private experiment root")
    require_branch(REPO)
    started = time.time()
    append(out / "commands.jsonl", {"argv": sys.argv, "started_unix": started})
    result = None
    try:
        if args.command == "inventory":
            result = inventory_inputs(REPO, config)
        elif args.command == "prepare":
            result = prepare(config, out)
        elif args.command == "freeze":
            result = {"identity": freeze_experiment(REPO, config, read_json(out / "partitions.json"))["identity"]}
        elif args.command == "train-c":
            from src.task3.r15_abc_training import train_c
            result = train_c(verified_freeze(out), read_json(out / "train-examples.private.json"), out / "C/training")
        elif args.command == "select-checkpoint":
            verified_freeze(out)
            result = select(out, checkpoint=True)
        elif args.command == "select-method":
            verified_freeze(out)
            result = select(out)
        elif args.command == "freeze-public":
            result = public_freeze(out)
        elif args.command == "infer":
            result = []
            for arm in "ABC" if args.arm == "all" else [args.arm]:
                checkpoints = [c["name"] for c in read_json(out / "C/training/training-result.json")["checkpoints"]] if arm == "C" and args.checkpoint == "all" else [args.checkpoint]
                for checkpoint in checkpoints:
                    try:
                        result.append(infer_one(arm, args.split, checkpoint, out))
                    except (ValueError, RuntimeError, FileNotFoundError, StopIteration) as exc:
                        write_json(out / arm / args.split / "blocked.json", {"reason": str(exc), "traceback": traceback.format_exc()})
                        result.append({"arm": arm, "status": "blocked", "reason": str(exc)})
                        if args.arm != "all":
                            raise
        elif args.command == "report":
            result = report(out)
        else:
            result = verify(out)
        print(json.dumps(result, ensure_ascii=False, default=str)[:3000])
        return 0
    finally:
        append(out / "commands.jsonl", {"argv": sys.argv, "finished_unix": time.time(), "elapsed_s": time.time() - started,
                                         "returned": result is not None})
        write_json(out / "commands.json", {"commands": [json.loads(s) for s in (out / "commands.jsonl").read_text().splitlines()],
                                            "implementation": {"data": "src/task3/r15_abc_data.py", "runtime": "src/task3/r15_abc_experiment.py",
                                                               "training": "src/task3/r15_abc_training.py", "evaluation": "src/task3/r15_abc_evaluation.py"}})


if __name__ == "__main__":
    raise SystemExit(main())
