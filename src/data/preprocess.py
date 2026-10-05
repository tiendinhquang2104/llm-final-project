"""Build unified ChatML jsonl + train/val splits for all 3 tasks."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Iterable

from src.data.leakage_guard import assert_no_feedback_leakage
from src.data.loader import load_dataset
from src.data.prompts import build_chatml_record
from src.data.schema import ChatMLRecord, TaskId, UnifiedSample

TASKS: tuple[TaskId, ...] = ("task1", "task2", "task3")


def make_split(
    sample_ids: list[str],
    *,
    val_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[list[str], list[str]]:
    """Deterministic train/val split by sample_id (shared across all 3 tasks)."""
    if not 0.0 < val_ratio < 1.0:
        raise ValueError("val_ratio must be in (0, 1)")
    ids = sorted(sample_ids)
    rng = random.Random(seed)
    rng.shuffle(ids)
    n_val = max(1, int(round(len(ids) * val_ratio))) if len(ids) > 1 else 0
    val_ids = sorted(ids[:n_val])
    train_ids = sorted(ids[n_val:])
    return train_ids, val_ids


def expand_to_chatml(
    samples: list[UnifiedSample],
    id_to_split: dict[str, str],
    tasks: Iterable[TaskId] = TASKS,
) -> list[ChatMLRecord]:
    records: list[ChatMLRecord] = []
    for sample in samples:
        split = id_to_split.get(sample.sample_id)
        for task in tasks:
            records.append(build_chatml_record(sample, task, split=split))
    return records


def write_jsonl(path: Path, records: list[ChatMLRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec.model_dump(), ensure_ascii=False) + "\n")


def write_unified_samples(path: Path, samples: list[UnifiedSample]) -> None:
    """Intermediate joined table (code + labels) — useful for EDA / debugging."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s.model_dump(), ensure_ascii=False) + "\n")


def build_unified_jsonl(
    data_dir: str | Path,
    output_dir: str | Path,
    *,
    splits_dir: str | Path | None = None,
    val_ratio: float = 0.2,
    seed: int = 42,
    check_leakage: bool = True,
) -> dict[str, Path]:
    """
    End-to-end preprocess:
      1. Load & join exams + code + 3 task labels
      2. Split by sample_id (seed=42)
      3. Expand each sample into 3 ChatML records (task1/2/3)
      4. Assert zero feedback leakage on task1/2
      5. Write jsonl + split id files
    """
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if splits_dir is not None:
        splits_path = Path(splits_dir).resolve()
    elif out.name == "processed" and out.parent.name == "data":
        # Local repo or Drive layout: <...>/data/processed → <...>/data/splits
        splits_path = out.parent / "splits"
    else:
        splits_path = out / "splits"
    splits_path.mkdir(parents=True, exist_ok=True)

    samples = load_dataset(data_dir)
    train_ids, val_ids = make_split([s.sample_id for s in samples], val_ratio=val_ratio, seed=seed)
    id_to_split = {i: "train" for i in train_ids}
    id_to_split.update({i: "val" for i in val_ids})

    records = expand_to_chatml(samples, id_to_split)
    samples_by_id = {s.sample_id: s for s in samples}

    if check_leakage:
        assert_no_feedback_leakage(records, samples_by_id)

    paths: dict[str, Path] = {}
    paths["unified_samples"] = out / "unified_samples.jsonl"
    write_unified_samples(paths["unified_samples"], samples)

    paths["train_unified"] = out / "train_unified.jsonl"
    paths["val_unified"] = out / "val_unified.jsonl"
    write_jsonl(paths["train_unified"], [r for r in records if r.split == "train"])
    write_jsonl(paths["val_unified"], [r for r in records if r.split == "val"])

    # Also write per-task files (handy for single-task ablation)
    for task in TASKS:
        train_path = out / f"{task}_train.jsonl"
        val_path = out / f"{task}_val.jsonl"
        write_jsonl(train_path, [r for r in records if r.task == task and r.split == "train"])
        write_jsonl(val_path, [r for r in records if r.task == task and r.split == "val"])
        paths[f"{task}_train"] = train_path
        paths[f"{task}_val"] = val_path

    paths["train_ids"] = splits_path / "train_ids.json"
    paths["val_ids"] = splits_path / "val_ids.json"
    paths["train_ids"].write_text(json.dumps(train_ids, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["val_ids"].write_text(json.dumps(val_ids, ensure_ascii=False, indent=2), encoding="utf-8")

    # Manifest for reproducibility
    manifest = {
        "n_samples": len(samples),
        "n_train_ids": len(train_ids),
        "n_val_ids": len(val_ids),
        "n_train_records": sum(1 for r in records if r.split == "train"),
        "n_val_records": sum(1 for r in records if r.split == "val"),
        "tasks": list(TASKS),
        "seed": seed,
        "val_ratio": val_ratio,
        "leakage_checked": check_leakage,
    }
    paths["manifest"] = out / "manifest.json"
    paths["manifest"].write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return paths
