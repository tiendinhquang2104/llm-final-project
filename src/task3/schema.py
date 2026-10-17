"""Task 3 schema independent of the three-task join."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from src.synth.feedback import FEEDBACK_LEVELS
from src.synth.taxonomy import LABEL_SPACE

MODEL_ID = "Qwen/Qwen2.5-Coder-7B-Instruct"


def validate_taxonomy(value: Any) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(x, str) or x not in LABEL_SPACE for x in value):
        raise ValueError("taxonomy_error must be a list of allowed labels; missing is not []")
    if len(set(value)) != len(value):
        raise ValueError("duplicate taxonomy labels")
    return list(value)


# Preserve literals and token order; ignore comments and formatting. Also group renamed variants.
_CPP_TOKEN = re.compile(
    r'R"([^ ()\\\t\r\n]{0,16})\(.*?\)\1"|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*.*?\*/|[A-Za-z_]\w*|\d+(?:\.\d+)?|\S',
    re.S,
)


def code_hash(code: str, *, renamed: bool = False) -> str:
    tokens, names = [], {}
    keywords = set(
        "int long short char float double bool void if else for while do return break continue class struct public private const static using namespace std include true false nullptr new delete auto unsigned signed switch case default sizeof template typename".split()
    )
    for match in _CPP_TOKEN.finditer(code):
        t = match.group()
        if t.startswith(("//", "/*")):
            continue
        if renamed and re.fullmatch(r"[A-Za-z_]\w*", t) and t not in keywords:
            t = names.setdefault(t, f"ID{len(names)}")
        tokens.append(t)
    return hashlib.sha256(" ".join(tokens).encode()).hexdigest()


@dataclass
class Task3Record:
    source: str
    sample_id: str
    original_submission_id: str
    exam_id: str
    exam_type: str
    statement: str
    grading_policy: Any
    code_path: str
    code: str
    target_feedback_level: str
    compile_log: str | None = None
    test_report: Any = None
    gold_taxonomy: list[str] | None = None
    gold_feedback: str | None = None
    synthetic_exec_report: Any = None
    split: str = ""
    problems: list[dict] = field(default_factory=list)
    level_definitions: list[dict] = field(default_factory=list)
    provenance: dict = field(default_factory=dict)
    group_key: str = ""

    def __post_init__(self):
        for name in ("sample_id", "original_submission_id", "exam_id", "statement", "code_path", "code"):
            value = getattr(self, name)
            if not isinstance(value, str) or (name not in {"code"} and not value.strip()):
                raise ValueError(f"invalid required string field: {name}")
        if self.compile_log is not None and not isinstance(self.compile_log, str):
            raise ValueError("compile_log must be text or null")
        if not isinstance(self.problems, list) or any(not isinstance(p, dict) for p in self.problems):
            raise ValueError("problems must be a list of objects")
        if self.source not in {"real", "synthetic", "synthetic-heldout", "public"}:
            raise ValueError("unknown source")
        if self.target_feedback_level not in FEEDBACK_LEVELS:
            raise ValueError(f"{self.sample_id}: invalid target_feedback_level")
        if self.exam_type not in {"single_problem", "multi_problem"}:
            raise ValueError(f"{self.sample_id}: invalid exam_type")
        if self.gold_taxonomy is not None:
            validate_taxonomy(self.gold_taxonomy)
        if self.gold_feedback is not None and (
            not isinstance(self.gold_feedback, str) or not self.gold_feedback.strip()
        ):
            raise ValueError(f"{self.sample_id}: empty or invalid gold feedback")
        if self.source == "public" and (self.gold_feedback is not None or self.gold_taxonomy is not None):
            raise ValueError("public records cannot contain gold outputs")

    @property
    def code_hash(self):
        return code_hash(self.code)
