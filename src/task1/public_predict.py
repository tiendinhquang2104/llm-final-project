"""Resumable, submission-safe prediction for the unlabeled public Task 1 release."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
import uuid
from collections import Counter
from pathlib import Path

from src.data.loader import Dataset, load_task1
from src.task1.evaluator import validate_predictions
from src.task1.pipeline import Task1Pipeline, to_submission

PUBLIC_EXAMS = {"Class03-Midterm-1", "Class03-Midterm-2", "Class03-Final-1",
                "Class01-Test1", "Class01-Test2", "Class02-Test1"}


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _source_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"],
                                       cwd=Path(__file__).resolve().parents[2],
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _write_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    os.replace(temporary, path)


def _usage_entries(directory: Path) -> list[dict]:
    entries = [json.loads(path.read_text(encoding="utf-8")) for path in directory.glob("*.json")]
    return sorted(entries, key=lambda entry: entry.get("recorded_at", 0))


def _usage_total(entries: list[dict]) -> dict:
    if not entries:
        return {"api_calls": 0, "input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0,
                "cost_usd": None, "estimated_unbilled_usd": 0.0}
    costs = [e["cost_usd"] for e in entries if isinstance(e.get("cost_usd"), (int, float))]
    return {"api_calls": len(entries),
            "input_tokens": sum(e.get("input_tokens", 0) for e in entries),
            "output_tokens": sum(e.get("output_tokens", 0) for e in entries),
            "thinking_tokens": sum(e.get("thinking_tokens", 0) for e in entries),
            "cost_usd": sum(costs) if costs else None,
            "estimated_unbilled_usd": sum(e.get("estimated_reserve_usd") or 0
                                          for e in entries if e.get("usage_missing"))}


def inspect_public(dataset: Dataset) -> dict:
    ids = [s.sample_id for s in dataset.samples]
    duplicates = [sid for sid, n in Counter(ids).items() if n > 1]
    if duplicates:
        raise ValueError(f"Duplicate public sample IDs: {duplicates[:5]}")
    if len(ids) != 360 or set(dataset.exams) != PUBLIC_EXAMS:
        raise ValueError(f"Expected 360 samples and six known public exams; got {len(ids)} and {sorted(dataset.exams)}")
    if {s.exam_id for s in dataset.samples} != PUBLIC_EXAMS:
        raise ValueError("Every public exam must have submissions")
    if any(s.has_gold for s in dataset.samples):
        raise ValueError("Public prediction input must be unlabeled")
    counts = Counter(s.exam_type for s in dataset.samples)
    if set(counts) != {"single_problem", "multi_problem"}:
        raise ValueError(f"Unexpected exam types: {dict(counts)}")
    return {"samples": len(ids), "exams": dict(sorted(Counter(s.exam_id for s in dataset.samples).items())),
            "exam_types": dict(counts), "empty_code_ids": [s.sample_id for s in dataset.samples if not s.code.strip()]}


def public_preflight(root: str | Path, cfg: dict, demo_dataset: Dataset | None = None,
                     demo_ids: list[str] | None = None, selected_ids: list[str] | None = None) -> tuple[Dataset, dict]:
    dataset = load_task1(root)
    summary = inspect_public(dataset)
    all_ids = set(dataset.by_id())
    chosen = selected_ids or sorted(all_ids)
    if len(chosen) != len(set(chosen)) or set(chosen) - all_ids:
        raise ValueError("--predict-ids must be distinct IDs from the public release")
    pool = [demo_dataset.by_id()[i] for i in (demo_ids or [])] if demo_dataset else []
    pipe = Task1Pipeline(dataset, None, cfg, pool)
    demos = {sid: pipe.build_request(dataset.by_id()[sid])["demos"] for sid in chosen}
    if cfg.get("prompt", {}).get("few_shot_k", 0) == 0 and any(demos.values()):
        raise ValueError("Zero-shot public prompt unexpectedly contains examples")
    summary.update({"selected": len(chosen), "selected_ids": chosen if selected_ids else None,
                    "initial_calls": len(chosen) * int(cfg.get("generation", {}).get("n", 1)),
                    "maximum_calls_with_repairs": len(chosen) * (1 + int(cfg.get("retry_on_parse_fail", 1)))
                                                  * int(cfg.get("generation", {}).get("n", 1)),
                    "few_shot_ids": demos if selected_ids else {"nonempty": sum(bool(x) for x in demos.values())}})
    return dataset, summary


def predict_public(dataset: Dataset, cfg: dict, backend, out_root: str | Path,
                   demo_dataset: Dataset | None = None, demo_ids: list[str] | None = None,
                   selected_ids: list[str] | None = None) -> dict:
    inspect_public(dataset)
    by_id = dataset.by_id()
    expected_ids = sorted(by_id)
    chosen = selected_ids or expected_ids
    if len(chosen) != len(set(chosen)) or set(chosen) - set(expected_ids):
        raise ValueError("Selected public IDs contain duplicates or unknown IDs")
    pool = [demo_dataset.by_id()[i] for i in (demo_ids or [])] if demo_dataset else []
    pipe = Task1Pipeline(dataset, backend, cfg, pool)
    model_info = backend.info()
    provider = str(model_info["backend"])
    model = str(model_info["model"])
    safe_model = re.sub(r"[^A-Za-z0-9._-]+", "-", model)
    release_key = _digest({"exams": dataset.exams,
                           "samples": [(s.sample_id, s.code, s.compile_log, s.test_report) for s in dataset.samples]})[:12]
    out_dir = Path(out_root) / "public" / provider / safe_model / cfg["name"] / release_key
    cache_dir = out_dir / "checkpoints"
    cache_dir.mkdir(parents=True, exist_ok=True)
    submission_path = out_dir / "predictions.json"
    model_key = {"provider": provider, "model": model,
                 "json_mode": model_info.get("json_mode"),
                 "thinking_off": model_info.get("thinking_off"),
                 "thinking_on": model_info.get("thinking_on")}
    keys = {sid: _digest({"model": model_key, "cfg": {k: cfg.get(k) for k in
                           ("prompt", "generation", "rules", "retry_on_parse_fail")},
                          "messages": pipe.build_request(by_id[sid])["messages"]})
            for sid in expected_ids}
    done = {}
    for sid in expected_ids:
        path = cache_dir / f"{sid}.json"
        if path.exists():
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
                row = saved["submission"]
                if saved["key"] == keys[sid] and not validate_predictions([row], [sid]):
                    done[sid] = row
            except (KeyError, ValueError, TypeError, json.JSONDecodeError):
                pass
    ledger_dir = out_dir / "usage_events"
    ledger_dir.mkdir(exist_ok=True)
    errors = []
    stopped = None
    for sid in chosen:
        if sid in done:
            continue
        before = len(getattr(backend, "ledger", []))
        try:
            _, preds = pipe.run([by_id[sid]])
            pred = preds[0]
            if not pred["parse_ok"]:
                errors.append({"sample_id": sid, "error": pred.get("error", "invalid_grade")})
                continue
            row = to_submission([pred])[0]
            problems = validate_predictions([row], [sid])
            if problems:
                errors.append({"sample_id": sid, "error": problems[:3]})
                continue
            _write_atomic(cache_dir / f"{sid}.json", {"key": keys[sid], "submission": row,
                                                    "problems": pred["problems"],
                                                    "rule_trace": pred["rule_trace"]})
            done[sid] = row
        except KeyboardInterrupt:
            stopped = "Interrupted by user"
            break
        except Exception as exc:
            from src.llm.api_client import QuotaExhausted
            from src.llm.openai_client import CostLimitReached
            if isinstance(exc, (QuotaExhausted, CostLimitReached)):
                stopped = str(exc)
                break
            errors.append({"sample_id": sid, "error": type(exc).__name__})
        finally:
            new_ledger = getattr(backend, "ledger", [])[before:]
            for entry in new_ledger:
                _write_atomic(ledger_dir / f"{uuid.uuid4().hex[:16]}.json",
                              {"recorded_at": time.time(), **entry})
    missing = sorted(set(expected_ids) - set(done))
    usage_entries = _usage_entries(ledger_dir)
    usage_tmp = out_dir / "usage.jsonl.tmp"
    usage_tmp.write_text("".join(json.dumps(entry, ensure_ascii=False) + "\n"
                                 for entry in usage_entries), encoding="utf-8")
    os.replace(usage_tmp, out_dir / "usage.jsonl")
    report = {"provider": provider, "model": model, "experiment": cfg["name"],
              "release_key": release_key, "source_commit": _source_commit(),
              "expected": len(expected_ids), "completed": len(done),
              "missing_ids": missing, "errors": errors, "stopped": stopped,
              "usage_this_run": backend.info().get("usage"), "usage_total": _usage_total(usage_entries),
              "price": backend.info().get("price"),
              "config_sha256": _digest({k: cfg.get(k) for k in
                                        ("prompt", "generation", "rules", "retry_on_parse_fail")}),
              "submission_path": str(submission_path) if not missing else None}
    if not missing:
        submission = [done[sid] for sid in expected_ids]
        problems = validate_predictions(submission, expected_ids)
        if problems:
            raise ValueError(f"Submission validation failed: {problems[:5]}")
        _write_atomic(submission_path, submission)
    else:
        submission_path.unlink(missing_ok=True)
    _write_atomic(out_dir / "progress.json", report)
    return report
