"""Load and join sample_dataset / challenge dataset from disk."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.data.schema import RubricScores, UnifiedSample


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def resolve_dataset_root(data_dir: str | Path) -> Path:
    """
    Accept common layouts:
      - <root>/exams.json
      - <root>/sample_dataset/exams.json
      - <root>/sample_dataset/sample_dataset/exams.json  (zip-extracted)
      - any nested folder under <root> containing exams.json (depth <= 4)
    """
    root = Path(data_dir).resolve()
    if not root.exists():
        raise FileNotFoundError(f"data_dir does not exist: {root}")

    direct_candidates = [
        root,
        root / "sample_dataset",
        root / "sample_dataset" / "sample_dataset",
    ]
    for c in direct_candidates:
        if (c / "exams.json").exists():
            return c

    # Fallback: shallow search for exams.json
    matches = [
        p.parent
        for p in root.rglob("exams.json")
        if len(p.relative_to(root).parts) <= 5
    ]
    # Prefer a folder that also has submissions/ and a task1 file
    for m in matches:
        if (m / "submissions").is_dir() and (m / "task1_grading.json").exists():
            return m
    if matches:
        return matches[0]

    raise FileNotFoundError(
        f"Cannot find exams.json under {root}. "
        "Expected layout like raw/sample_dataset/sample_dataset/exams.json "
        "(or exams.json directly in raw/). Also need task1_grading.json and submissions/."
    )


def load_exams(root: Path) -> dict[str, dict[str, Any]]:
    data = _read_json(root / "exams.json")
    return {e["exam_id"]: e for e in data["exams"]}


def load_task_samples(root: Path, filename: str) -> dict[str, dict[str, Any]]:
    data = _read_json(root / filename)
    return {s["sample_id"]: s for s in data["samples"]}


def load_code(root: Path, code_file: str) -> str:
    path = root / code_file
    if not path.exists():
        raise FileNotFoundError(f"Missing code file: {path}")
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "cp1258", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def load_dataset(data_dir: str | Path) -> list[UnifiedSample]:
    """Join Task1/2/3 + exams + .cpp into UnifiedSample list (sorted by sample_id)."""
    root = resolve_dataset_root(data_dir)
    exams = load_exams(root)
    t1 = load_task_samples(root, "task1_grading.json")
    t2 = load_task_samples(root, "task2_error_taxonomy.json")
    t3 = load_task_samples(root, "task3_feedback.json")

    ids = sorted(set(t1) & set(t2) & set(t3))
    missing = (set(t1) | set(t2) | set(t3)) - set(ids)
    if missing:
        raise ValueError(f"sample_id mismatch across tasks: {sorted(missing)}")

    samples: list[UnifiedSample] = []
    for sid in ids:
        s1, s2, s3 = t1[sid], t2[sid], t3[sid]
        inp = s1["input"]
        exam_id = inp["exam_id"]
        if exam_id not in exams:
            raise KeyError(f"Unknown exam_id={exam_id} for {sid}")
        exam = exams[exam_id]
        if inp["exam_type"] != exam["exam_type"]:
            raise ValueError(f"exam_type mismatch for {sid}: {inp['exam_type']} != {exam['exam_type']}")
        code = load_code(root, inp["code_file"])

        # Task3 may carry taxonomy in input (gold for Task3 independence)
        tax = s2["output"]["taxonomy_error"]
        tax_t3 = s3["input"].get("taxonomy_error", tax)
        if tax != tax_t3:
            # Prefer Task2 gold; Task3 input should match — surface if not
            raise ValueError(f"taxonomy_error mismatch for {sid}: task2={tax} task3_input={tax_t3}")

        samples.append(
            UnifiedSample(
                sample_id=sid,
                exam_id=exam_id,
                exam_type=inp["exam_type"],
                language=inp.get("language", exam.get("language", "cpp11")),
                code_file=inp["code_file"],
                code=code,
                exam_statement=exam["statement"],
                grading_policy=exam.get("grading_policy"),
                compile_log=inp.get("compile_log") or None,
                test_report=inp.get("test_report"),
                rubric=RubricScores(**s1["output"]["rubric"]),
                total_score=s1["output"]["total_score"],
                taxonomy_error=tax,
                target_feedback_level=s3["input"]["target_feedback_level"],
                feedback=s3["output"]["feedback"],
            )
        )
    return samples


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


def read_code(root: Path, code_file: str) -> str:
    return load_code(root, code_file)


def load_task1(root: str | Path, task_file: str = "task1_grading.json") -> Dataset:
    """Load exams, label space and Task 1 samples. Gold labels are attached when present.

    Note: the `feedback` field (Task 3) is never read here — using it for Task 1 is label leakage.
    """
    root = resolve_dataset_root(root)
    exams = {e["exam_id"]: e for e in _read_json(root / "exams.json")["exams"]}
    label_space = _read_json(root / "label_space.json")
    payload = _read_json(root / task_file)
    samples = []
    for s in payload["samples"]:
        inp = s["input"]
        if inp["exam_id"] not in exams:
            raise KeyError(f"Unknown exam_id={inp['exam_id']} for {s['sample_id']}")
        if inp.get("exam_type", exams[inp["exam_id"]]["exam_type"]) != exams[inp["exam_id"]]["exam_type"]:
            raise ValueError(f"exam_type mismatch for {s['sample_id']}")
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


def load_split(splits_dir: str | Path) -> dict:
    """Read <splits_dir>/train_ids.json and val_ids.json -> {"train": [...], "val": [...]}."""
    d = Path(splits_dir)
    return {part: _read_json(d / f"{part}_ids.json") for part in ("train", "val")}
