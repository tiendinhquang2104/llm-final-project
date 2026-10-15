"""Problem bank for synthetic generation (synth_plan.md implementation step 3).

A *problem* is one exam: statement, metadata, hand-written standard tests (used to LABEL, never
to train) and a clean reference solution (the base the mutators break). The bank is loaded from
``src/synth/problems/*.yaml`` (or ``.json``); tests can build problems directly in Python.

Layout matches ``sample_dataset/exams.json`` (``exam_id``, ``exam_type``, ``statement``,
``problems`` with ``pid``/``max_score``/``prototype``/``is_prerequisite_for``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PROBLEMS_DIR = Path(__file__).resolve().parent / "problems"


@dataclass(frozen=True)
class ProblemTest:
    input: str
    expected: str
    group: str = "normal"  # normal | example | perf | edge:<name>
    name: str = ""


@dataclass
class Problem:
    exam_id: str
    exam_type: str
    statement: str
    title: str = ""
    language: str = "cpp11"
    problems: list[dict] = field(default_factory=list)
    tests: list[ProblemTest] = field(default_factory=list)
    reference: str = ""
    data_files: dict[str, str] = field(default_factory=dict)
    harness: str = ""
    heldout: bool = False
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.exam_type not in ("single_problem", "multi_problem"):
            raise ValueError(f"{self.exam_id}: bad exam_type {self.exam_type!r}")
        if self.exam_type == "multi_problem":
            ids = [p["pid"] for p in self.problems]
            if ids[:1] != ["P1"]:
                raise ValueError(f"{self.exam_id}: multi_problem problems must start with P1")
        for t in self.tests:
            if not t.group.startswith(("normal", "example", "perf", "edge")):
                raise ValueError(f"{self.exam_id}: bad test group {t.group!r}")

    def exam_dict(self) -> dict:
        """The exam entry exactly as it must appear in exams.json (generation-only keys dropped)."""
        out = {
            "exam_id": self.exam_id,
            "exam_type": self.exam_type,
            "language": self.language,
            "statement": self.statement,
            "problems": self.problems,
        }
        out.update({k: v for k, v in self.metadata.items() if k not in ("targets", "harness")})
        return out


def problem_from_dict(d: dict) -> Problem:
    tests = [ProblemTest(**t) if isinstance(t, dict) else ProblemTest(*t) for t in d.get("tests", [])]
    data_files = d.get("data_files", {}) or {}
    if isinstance(data_files, dict) and "content" in data_files:
        raise ValueError("data_files must map filename -> content")
    return Problem(
        exam_id=d["exam_id"],
        exam_type=d["exam_type"],
        statement=d["statement"],
        title=d.get("title", ""),
        language=d.get("language", "cpp11"),
        problems=d.get("problems", []),
        tests=tests,
        reference=d.get("reference", ""),
        data_files={k: str(v) for k, v in data_files.items()},
        harness=d.get("harness", ""),
        heldout=bool(d.get("heldout", False)),
        metadata=d.get("metadata", {}) or {},
    )


def load_problems(directory: str | Path = PROBLEMS_DIR) -> dict[str, Problem]:
    """Load every *.yaml / *.json problem in a directory (or a single file) into {exam_id: Problem}."""
    directory = Path(directory)
    if directory.is_file():
        paths = [directory]
    else:
        paths = sorted([*directory.glob("*.yaml"), *directory.glob("*.yml"), *directory.glob("*.json")])
    problems: dict[str, Problem] = {}
    for path in paths:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) if path.suffix != ".json" \
            else json.loads(path.read_text(encoding="utf-8"))
        entries = payload["problems_meta"] if isinstance(payload, dict) and "problems_meta" in payload else payload
        if isinstance(entries, dict):
            entries = [entries]
        for entry in entries:
            p = problem_from_dict(entry)
            if p.exam_id in problems:
                raise ValueError(f"duplicate exam_id {p.exam_id} in {path}")
            problems[p.exam_id] = p
    return problems
