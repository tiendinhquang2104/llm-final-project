"""Dataset loading and a fixed, seeded train/validation split."""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DIMENSIONS = ["compilable", "io_format", "logic", "edge_case", "complexity", "code_quality"]
DIM_MAX = {"compilable": 1, "io_format": 1, "logic": 4, "edge_case": 2, "complexity": 1, "code_quality": 1}
TOTAL_MAX = sum(DIM_MAX.values())  # 10


@dataclass
class Sample:
    sample_id: str
    exam_id: str
    exam_type: str
    language: str
    code_file: str
    code: str
    compile_log: str | None
    test_report: list[dict] | None
    gold_rubric: dict[str, int] | None = None
    gold_total: int | None = None

    @property
    def has_gold(self) -> bool:
        return self.gold_rubric is not None


@dataclass
class Dataset:
    root: Path
    exams: dict[str, dict]
    label_space: dict
    samples: list[Sample] = field(default_factory=list)

    def by_id(self) -> dict[str, Sample]:
        return {s.sample_id: s for s in self.samples}


def _read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_code(root: Path, code_file: str) -> str:
    raw = (root / code_file).read_bytes()
    for enc in ("utf-8", "utf-8-sig", "cp1258", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def load_task1(root: str | Path, task_file: str = "task1_grading.json") -> Dataset:
    """Load exams, label space and Task 1 samples. Gold labels are attached when present.

    Note: the `feedback` field (Task 3) is never read here — using it for Task 1 is label leakage.
    """
    root = Path(root)
    exams = {e["exam_id"]: e for e in _read_json(root / "exams.json")["exams"]}
    label_space = _read_json(root / "label_space.json")
    payload = _read_json(root / task_file)
    samples = []
    for s in payload["samples"]:
        inp = s["input"]
        out = s.get("output") or {}
        rubric = out.get("rubric")
        samples.append(
            Sample(
                sample_id=s["sample_id"],
                exam_id=inp["exam_id"],
                exam_type=inp.get("exam_type") or exams[inp["exam_id"]]["exam_type"],
                language=inp.get("language", "cpp11"),
                code_file=inp["code_file"],
                code=read_code(root, inp["code_file"]),
                compile_log=inp.get("compile_log"),
                test_report=inp.get("test_report"),
                gold_rubric={k: int(rubric[k]) for k in DIMENSIONS} if rubric else None,
                gold_total=int(out["total_score"]) if "total_score" in out else None,
            )
        )
    return Dataset(root=root, exams=exams, label_space=label_space, samples=samples)


def make_split(samples: list[Sample], val_frac: float = 0.6, seed: int = 42) -> dict[str, list[str]]:
    """Stratified (by exam_id, then by total-score order) deterministic split.

    Within each exam the samples are sorted by gold total, then every k-th one goes to train so that
    the train pool (used for few-shot demos) covers the whole score range. A seeded shuffle breaks ties.
    """
    rng = random.Random(seed)
    by_exam: dict[str, list[Sample]] = {}
    for s in sorted(samples, key=lambda x: x.sample_id):
        by_exam.setdefault(s.exam_id, []).append(s)
    train, val = [], []
    for exam_id in sorted(by_exam):
        group = by_exam[exam_id][:]
        rng.shuffle(group)
        group.sort(key=lambda x: x.gold_total if x.gold_total is not None else 0)
        n_train = max(1, round(len(group) * (1 - val_frac)))
        # Spread train picks evenly over the score-sorted list.
        step = len(group) / n_train
        train_idx = {int(i * step + rng.random() * step) for i in range(n_train)}
        train_idx = {min(i, len(group) - 1) for i in train_idx}
        for i, s in enumerate(group):
            (train if i in train_idx else val).append(s.sample_id)
    return {"seed": seed, "val_frac": val_frac, "train": sorted(train), "val": sorted(val)}


def save_split(split: dict, splits_dir: str | Path) -> None:
    """Write <splits_dir>/train_ids.json and val_ids.json (plain lists of sample_id)."""
    d = Path(splits_dir)
    d.mkdir(parents=True, exist_ok=True)
    for part in ("train", "val"):
        text = json.dumps(split[part], ensure_ascii=False, indent=2) + "\n"
        (d / f"{part}_ids.json").write_text(text, encoding="utf-8")


def load_split(splits_dir: str | Path) -> dict:
    """Read <splits_dir>/train_ids.json and val_ids.json -> {"train": [...], "val": [...]}."""
    d = Path(splits_dir)
    return {part: _read_json(d / f"{part}_ids.json") for part in ("train", "val")}
