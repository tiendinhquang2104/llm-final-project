"""Load Task 2 samples (labelled sample_dataset or the unlabelled public release). Never reads `feedback`."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from src.data.loader import load_code, resolve_dataset_root
from src.task2.labels import normalize_labels


@dataclass
class Task2Sample:
    sample_id: str
    exam_id: str
    exam_type: str
    language: str
    code_file: str
    code: str
    compile_log: str | None
    test_report: list | None
    labels: list[str] | None = None

    @property
    def has_gold(self) -> bool:
        return self.labels is not None


@dataclass
class Task2Dataset:
    root: Path
    exams: dict[str, dict]
    samples: list[Task2Sample] = field(default_factory=list)

    def by_id(self) -> dict[str, Task2Sample]:
        return {s.sample_id: s for s in self.samples}


def load_task2(root, task_file: str = "task2_error_taxonomy.json") -> Task2Dataset:
    root = resolve_dataset_root(root)
    exams = {e["exam_id"]: e for e in json.loads((root / "exams.json").read_text(encoding="utf-8"))["exams"]}
    payload = json.loads((root / task_file).read_text(encoding="utf-8"))
    samples = []
    for s in payload["samples"]:
        inp = s["input"]
        if inp["exam_id"] not in exams:
            raise KeyError(f"Unknown exam_id={inp['exam_id']} for {s['sample_id']}")
        out = s.get("output") or {}
        labels = None
        if "taxonomy_error" in out:
            raw = out["taxonomy_error"]
            labels = normalize_labels(raw)
            if len(labels) != len(set(raw)):
                raise ValueError(f"{s['sample_id']}: unknown taxonomy label in {raw}")
        samples.append(Task2Sample(
            sample_id=s["sample_id"], exam_id=inp["exam_id"],
            exam_type=inp.get("exam_type") or exams[inp["exam_id"]]["exam_type"],
            language=inp.get("language", "cpp11"), code_file=inp["code_file"],
            code=load_code(root, inp["code_file"]),
            compile_log=inp.get("compile_log") or None, test_report=inp.get("test_report"),
            labels=labels,
        ))
    return Task2Dataset(root=root, exams=exams, samples=samples)
