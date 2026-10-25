"""Training / evaluation records for F-cls (Qwen + LoRA + 10-sigmoid head, docs/task2_finetune_plan.md).

One record per submission: the chat messages the classifier reads and the 10-label target. The user message is
built by the same helpers as the CoT prompt (statement, exam requirements, numbered code, self-compiled
compile_log and the runs on the statement examples), so training and inference see the same text; only the
long rule/step instructions are dropped (the model learns the conventions from the labels).

Sources (labels never come from the public test):
- synth: the generated set (generate-dataset_v3.zip: silver + heldout/), all used for training;
- gold: the 32 labelled samples (EX01, EX02) — evaluated out-of-fold, one fold per exam;
- gold_mut: bug-injection mutants of gold code (src/task2/augment.py), fold = the exam of their source sample;
- public: the 360 unlabelled samples, inference only.
"""
from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

from src.task2.labels import LABELS, to_vector
from src.task2.prompts_cot import (ALL_COMMENTED, _view, exam_requirements, exam_text_lang, prompt_lang,
                                   strip_comments, submission_text_lang)

SOURCES = ("synth", "gold", "gold_mut", "public")

CLS_SYSTEM = {
    "en": ("You are a C++ programming lecturer. Read the exam, the student's submission and the automatic compile/run "
           "results, then decide which error labels of the course taxonomy apply to the submission: "
           + ", ".join(LABELS) + ". A submission may have no error."),
    "vi": ("Bạn là giảng viên lập trình C++. Đọc đề, bài nộp của sinh viên và kết quả compile/chạy tự động, rồi xác "
           "định các nhãn lỗi trong taxonomy của môn áp dụng cho bài nộp: " + ", ".join(LABELS)
           + ". Bài nộp có thể không có lỗi nào."),
}


def cls_messages(exam: dict, sample, pcfg: dict) -> list[dict]:
    """System + user messages (no assistant turn): the classifier reads the last token of this conversation."""
    lang = prompt_lang(pcfg)
    user = "\n".join(x for x in [exam_text_lang(exam, lang), exam_requirements(exam, lang),
                                  submission_text_lang(_view(sample, pcfg), pcfg, lang)] if x)
    return [{"role": "system", "content": CLS_SYSTEM[lang]}, {"role": "user", "content": user}]


def all_commented(code: str) -> bool:
    return strip_comments(code) == ALL_COMMENTED


def record(exam: dict, sample, source: str, pcfg: dict, fold: str | None) -> dict:
    labels = list(sample.labels) if sample.labels is not None else None
    return {"id": sample.sample_id, "source": source, "exam_id": sample.exam_id, "exam_type": sample.exam_type,
            "fold": fold, "labels": labels, "y": to_vector(labels) if labels is not None else None,
            "compile_log": sample.compile_log, "all_commented": all_commented(sample.code),
            "messages": cls_messages(exam, sample, pcfg)}


# ---------------------------------------------------------------------------------------------- train views


def folds(records: list[dict]) -> list[str]:
    """Gold exams, one fold each (EX01, EX02)."""
    return sorted({r["fold"] for r in records if r["source"] == "gold" and r["fold"]})


def train_records(records: list[dict], holdout: str | None, use_gold: bool = True, use_mutants: bool = True) -> list[dict]:
    """Training pool for one run. holdout=None (or "all"): the final model, trained on everything labelled.
    holdout=<exam>: gold samples of that exam and every mutant made from them are left out (they are its eval set)."""
    keep = []
    for r in records:
        if r["y"] is None or r["source"] == "public":
            continue
        if r["source"] == "gold" and not use_gold or r["source"] == "gold_mut" and not use_mutants:
            continue
        if holdout not in (None, "all") and r["fold"] == holdout:
            continue
        keep.append(r)
    return keep


def eval_records(records: list[dict], holdout: str) -> list[dict]:
    return [r for r in records if r["source"] == "gold" and r["fold"] == holdout]


def sample_weights(train: list[dict], source_weight: dict | None = None) -> list[float]:
    """Per-record loss weight: source weight (e.g. gold ×2 — real code, the lecturer's own labels)."""
    source_weight = source_weight or {}
    return [float(source_weight.get(r["source"], 1.0)) for r in train]


def oversample(train: list[dict], min_count: int, seed: int = 42, max_factor: int = 4) -> list[dict]:
    """Repeat records carrying a rare label until every label occurs >= min_count times (at most max_factor copies
    of a record). Deterministic for a given seed. Labels with no positive at all stay at 0."""
    if min_count <= 0:
        return list(train)
    rng = random.Random(seed)
    out = list(train)
    copies = Counter()
    for j, lab in sorted(enumerate(LABELS), key=lambda t: sum(r["y"][t[0]] for r in train)):
        have = sum(r["y"][j] for r in out)
        pool = [r for r in train if r["y"][j]]
        while pool and have < min_count:
            cand = [r for r in pool if copies[r["id"]] < max_factor - 1]
            if not cand:
                break
            r = rng.choice(cand)
            copies[r["id"]] += 1
            out.append(r)
            have += 1
    return out


def pos_weight(train: list[dict], cap: float = 10.0) -> list[float]:
    """BCE pos_weight per label = negatives / positives, clipped to [1, cap] (1 when a label has no positive)."""
    n = len(train)
    out = []
    for j in range(len(LABELS)):
        pos = sum(r["y"][j] for r in train)
        out.append(1.0 if pos == 0 else float(min(cap, max(1.0, (n - pos) / pos))))
    return out


def label_counts(rows: list[dict]) -> dict[str, int]:
    return {lab: sum(r["y"][j] for r in rows if r["y"] is not None) for j, lab in enumerate(LABELS)}


# ---------------------------------------------------------------------------------------------- io


def write_jsonl(path, rows) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)


def read_jsonl(path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def summary(records: list[dict]) -> dict:
    by_src = Counter(r["source"] for r in records)
    out = {"n": len(records), "by_source": dict(by_src), "folds": folds(records), "labels": {}}
    for src in SOURCES:
        rows = [r for r in records if r["source"] == src and r["y"] is not None]
        if rows:
            out["labels"][src] = label_counts(rows)
            out.setdefault("empty", {})[src] = sum(not any(r["y"]) for r in rows)
    return out

