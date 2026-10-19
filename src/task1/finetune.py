"""Task 1 QLoRA data checks, chat tokenization, and generated-output evaluation.

This module has no GPU dependencies so its safety checks can run before Colab
downloads the model. Training uses only the per-task JSONL files, never the
unified training file or teacher feedback as a model input.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.data.leakage_guard import assert_no_feedback_leakage
from src.data.loader import DIM_MAX, DIMENSIONS
from src.data.schema import ChatMLRecord
from src.task1.evaluator import evaluate
from src.task1.score import from_cents, to_cents


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}; run colab/01_prepare_data.ipynb first")
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _validate_target(target: str, sample_id: str) -> None:
    try:
        obj = json.loads(target)
        rubric = obj["rubric"]
        if set(obj) != {"rubric", "total_score"} or set(rubric) != set(DIMENSIONS):
            raise ValueError("incorrect Task 1 target keys")
        total = sum(to_cents(rubric[d], DIM_MAX[d]) for d in DIMENSIONS)
        if to_cents(obj["total_score"], 10) != total:
            raise ValueError("total_score differs from rubric sum")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid Task 1 output for {sample_id}: {exc}") from exc


def load_task1_splits(
    processed_dir: str | Path,
    splits_dir: str | Path,
    *,
    expected_train: int = 26,
    expected_val: int = 6,
) -> tuple[list[ChatMLRecord], list[ChatMLRecord]]:
    """Load the fixed sample split; reject mixed tasks, ID drift, and leakage."""
    processed = Path(processed_dir)
    splits = Path(splits_dir)
    partitions: dict[str, list[ChatMLRecord]] = {}
    for part, expected in (("train", expected_train), ("val", expected_val)):
        rows = _read_jsonl(processed / f"task1_{part}.jsonl")
        records = [ChatMLRecord.model_validate(row) for row in rows]
        if len(records) != expected:
            raise ValueError(f"Task 1 {part} must contain {expected} records; found {len(records)}")
        ids = [rec.sample_id for rec in records]
        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate sample_id in Task 1 {part}")
        split_path = splits / f"{part}_ids.json"
        split_ids = json.loads(split_path.read_text(encoding="utf-8"))
        if set(ids) != set(split_ids) or len(split_ids) != expected:
            raise ValueError(f"Task 1 {part} IDs do not match {split_path}")
        for rec in records:
            if rec.task != "task1" or rec.split != part:
                raise ValueError(f"Unexpected task/split for {rec.sample_id}: {rec.task}/{rec.split}")
            if [m.get("role") for m in rec.messages] != ["system", "user", "assistant"]:
                raise ValueError(f"Expected system/user/assistant messages for {rec.sample_id}")
            if rec.messages[-1]["content"] != rec.target:
                raise ValueError(f"Assistant message and target differ for {rec.sample_id}")
            _validate_target(rec.target, rec.sample_id)
        assert_no_feedback_leakage(records)
        partitions[part] = records

    if {r.sample_id for r in partitions["train"]} & {r.sample_id for r in partitions["val"]}:
        raise ValueError("Train and validation contain the same sample_id")

    # The joined file is used only for a leakage assertion, never as a model
    # feature. It is optional because per-task JSONL files are sufficient.
    joined_path = processed / "unified_samples.jsonl"
    if joined_path.is_file():
        feedback = {row["sample_id"]: row.get("feedback", "") for row in _read_jsonl(joined_path)}
        for rec in partitions["train"] + partitions["val"]:
            gold = feedback.get(rec.sample_id, "").strip()
            prompt = rec.messages[0]["content"] + "\n" + rec.messages[1]["content"]
            if len(gold) >= 20 and gold in prompt:
                raise ValueError(f"Teacher feedback leaked into Task 1 prompt for {rec.sample_id}")

    return partitions["train"], partitions["val"]


def prompt_messages(record: ChatMLRecord) -> list[dict[str, str]]:
    """Exclude the gold assistant response from inference inputs."""
    return record.messages[:2]


def encode_training_record(record: ChatMLRecord, tokenizer: Any, max_length: int) -> dict[str, Any]:
    """Apply Qwen's own chat template and mask every prompt token from loss."""
    prompt_ids = tokenizer.apply_chat_template(
        prompt_messages(record), tokenize=True, add_generation_prompt=True
    )
    full_ids = tokenizer.apply_chat_template(record.messages, tokenize=True, add_generation_prompt=False)
    if full_ids[: len(prompt_ids)] != prompt_ids:
        raise ValueError(f"Chat template prefix mismatch for {record.sample_id}")
    if len(full_ids) > max_length:
        raise ValueError(
            f"{record.sample_id} uses {len(full_ids)} tokens, exceeding max_length={max_length}; "
            "increase context length instead of truncating the question or code"
        )
    if len(full_ids) == len(prompt_ids):
        raise ValueError(f"Empty assistant completion for {record.sample_id}")
    return {
        "input_ids": full_ids,
        "attention_mask": [1] * len(full_ids),
        "labels": [-100] * len(prompt_ids) + full_ids[len(prompt_ids) :],
        "sample_id": record.sample_id,
        "prompt_tokens": len(prompt_ids),
        "total_tokens": len(full_ids),
    }


def encode_inference_prompt(record: ChatMLRecord, tokenizer: Any, max_length: int) -> list[int]:
    ids = tokenizer.apply_chat_template(prompt_messages(record), tokenize=True, add_generation_prompt=True)
    if len(ids) >= max_length:
        raise ValueError(f"Validation prompt for {record.sample_id} exceeds max_length={max_length}")
    return ids


def strip_code_fence(text: str) -> str:
    """Remove one surrounding Markdown code fence (```json ... ```), which instruct models often add."""
    t = (text or "").strip()
    if t.startswith("```") and t.endswith("```") and t.count("```") == 2:
        t = t[3:-3]
        first, _, rest = t.partition("\n")
        t = rest if first.strip().lower() in ("", "json") else t
    return t.strip()


def parse_generated_score(text: str) -> tuple[dict[str, Any] | None, bool, bool]:
    """Return a normalized score, JSON parse flag, and strict output-valid flag.

    If six valid rubric scores are present, total_score is recomputed so the
    prediction is internally consistent. Malformed responses count as missing
    predictions in the evaluator; no score is silently fabricated here.
    """
    try:
        obj = json.loads(strip_code_fence(text))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None, False, False
    if not isinstance(obj, dict) or not isinstance(obj.get("rubric"), dict):
        return None, True, False
    rubric = obj["rubric"]
    if set(rubric) != set(DIMENSIONS):
        return None, True, False
    try:
        cents = {d: to_cents(rubric[d], DIM_MAX[d]) for d in DIMENSIONS}
    except ValueError:
        return None, True, False
    total_cents = sum(cents.values())
    prediction = {
        "rubric": {d: from_cents(cents[d]) for d in DIMENSIONS},
        "total_score": from_cents(total_cents),
    }
    try:
        raw_total = to_cents(obj["total_score"], 10)
    except (KeyError, ValueError):
        raw_total = None
    strict_valid = set(obj) == {"rubric", "total_score"} and raw_total == total_cents
    return prediction, True, strict_valid


def evaluate_generations(records: list[ChatMLRecord], raw_by_id: dict[str, str]) -> tuple[dict, list[dict]]:
    expected = {rec.sample_id for rec in records}
    if set(raw_by_id) != expected:
        raise ValueError("Generated sample_ids do not match validation IDs")
    gold = {rec.sample_id: json.loads(rec.target) for rec in records}
    predictions: dict[str, dict] = {}
    details: list[dict] = []
    for rec in records:
        raw = raw_by_id[rec.sample_id]
        pred, json_ok, strict_ok = parse_generated_score(raw)
        if pred is not None:
            predictions[rec.sample_id] = pred
        details.append(
            {"sample_id": rec.sample_id, "exam_id": rec.exam_id, "raw_output": raw, "prediction": pred,
             "gold": gold[rec.sample_id], "json_ok": json_ok, "strict_output_ok": strict_ok}
        )
    metrics = evaluate(gold, predictions)
    metrics["json_parse_rate"] = sum(x["json_ok"] for x in details) / len(details)
    metrics["valid_output_rate"] = sum(x["strict_output_ok"] for x in details) / len(details)
    metrics["n_normalized_total"] = sum(
        x["prediction"] is not None and not x["strict_output_ok"] for x in details
    )
    return metrics, details


def best_epoch(results: list[dict]) -> dict:
    if not results:
        raise ValueError("No checkpoint evaluation results")
    return max(results, key=lambda r: (r["metrics"]["qwk"], -r["metrics"]["mae"], -r["epoch"]))


def load_silver_records(path: str | Path, gold_records: list[ChatMLRecord], *, expected: int | None = None) -> list[ChatMLRecord]:
    """Load audited Task 1 silver prompts, rejecting task/ID leakage."""
    records = [ChatMLRecord.model_validate(row) for row in _read_jsonl(Path(path))]
    if expected is not None and len(records) != expected:
        raise ValueError(f"Expected {expected} silver records; found {len(records)}")
    gold_ids = {rec.sample_id for rec in gold_records}
    ids = [rec.sample_id for rec in records]
    if len(ids) != len(set(ids)) or gold_ids.intersection(ids):
        raise ValueError("Duplicate silver ID or silver/gold ID overlap")
    for rec in records:
        if rec.task != "task1" or rec.split != "silver":
            raise ValueError(f"Unexpected silver task/split for {rec.sample_id}")
        if [m.get("role") for m in rec.messages] != ["system", "user", "assistant"]:
            raise ValueError(f"Invalid silver messages for {rec.sample_id}")
        if rec.messages[-1]["content"] != rec.target:
            raise ValueError(f"Silver target mismatch for {rec.sample_id}")
        _validate_target(rec.target, rec.sample_id)
        if "exec_report" in rec.messages[0]["content"] + rec.messages[1]["content"]:
            raise ValueError(f"exec_report leaked for {rec.sample_id}")
    assert_no_feedback_leakage(records)
    return records


def choose_variant(gold_only: dict, silver_then_gold: dict) -> dict:
    """Select by gold-validation QWK, then MAE; exact ties keep gold-only."""
    gold_key = (gold_only["metrics"]["qwk"], -gold_only["metrics"]["mae"])
    silver_key = (silver_then_gold["metrics"]["qwk"], -silver_then_gold["metrics"]["mae"])
    return silver_then_gold if silver_key > gold_key else gold_only


# -- public / private test prediction with the selected adapter ----------------------------------

def load_unlabelled_prompts(root: str | Path, task_file: str = "task1_grading.json") -> list[dict[str, Any]]:
    """Inference prompts for an unlabelled release (public or private test), built exactly like training.

    Uses src.data.prompts.build_task1_prompt, so statement, code, compile log and test report are formatted as
    in the gold/silver training records. Labels, if present, are never read.
    """
    from types import SimpleNamespace

    from src.data.loader import load_code, load_exams, resolve_dataset_root
    from src.data.prompts import build_task1_prompt

    root = resolve_dataset_root(root)
    exams = load_exams(root)
    label_space_path = root / "label_space.json"
    label_space = json.loads(label_space_path.read_text(encoding="utf-8")) if label_space_path.is_file() else None
    rows = json.loads((root / task_file).read_text(encoding="utf-8"))["samples"]
    ids = [row["sample_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate sample_id in {root / task_file}")
    prompts = []
    for row in rows:
        inp = row["input"]
        if "feedback" in inp:
            raise ValueError(f"Task 1 input of {row['sample_id']} carries teacher feedback; refusing to build a prompt")
        exam = exams[inp["exam_id"]]
        sample = SimpleNamespace(
            exam_id=inp["exam_id"], exam_type=inp.get("exam_type") or exam["exam_type"],
            language=inp.get("language") or exam.get("language", "cpp11"),
            grading_policy=exam.get("grading_policy"), exam_statement=exam["statement"],
            code=load_code(root, inp["code_file"]), compile_log=inp.get("compile_log"),
            test_report=inp.get("test_report"),
        )
        prompts.append({"sample_id": row["sample_id"], "exam_id": sample.exam_id, "exam_type": sample.exam_type,
                        "messages": build_task1_prompt(sample, label_space)})
    return prompts


def record_exam_type(record: ChatMLRecord) -> str | None:
    """exam_type as written in the record's own prompt (src.data.prompts._shared_context)."""
    for line in record.messages[1]["content"].splitlines():
        if line.startswith("exam_type:"):
            return line.split(":", 1)[1].strip()
    return None


def fallback_score(gold_records: list[ChatMLRecord], exam_type: str) -> dict[str, Any]:
    """Median teacher rubric of gold training records of the same exam type (for an unparseable output).

    The submission must contain every sample_id; such samples are flagged `fallback_used` and counted.
    """
    import statistics

    pool = [json.loads(r.target)["rubric"] for r in gold_records if record_exam_type(r) == exam_type]
    pool = pool or [json.loads(r.target)["rubric"] for r in gold_records]
    cents = {d: int(statistics.median_low(to_cents(rub[d], DIM_MAX[d]) for rub in pool)) for d in DIMENSIONS}
    return {"rubric": {d: from_cents(cents[d]) for d in DIMENSIONS}, "total_score": from_cents(sum(cents.values()))}


def validation_error_report(output_dir: str | Path, threshold: float = 2.0) -> str:
    """Markdown error analysis of the selected adapter on gold validation (|pred - gold| >= threshold or invalid)."""
    out = Path(output_dir)
    summary = json.loads((out / "training_summary.json").read_text(encoding="utf-8"))
    variant, epoch = summary["selected_variant"], summary["selected_epoch"]
    details = json.loads((out / variant / f"epoch_{epoch}" / "validation_predictions.json").read_text(encoding="utf-8"))
    lines = [f"# Task 1 QLoRA — error analysis ({variant}, epoch {epoch}, gold validation)", "",
             f"Selected metrics: QWK {summary['selected_metrics']['qwk']:.3f}, "
             f"MAE {summary['selected_metrics']['mae']:.2f}, n {summary['selected_metrics']['n']}.", "",
             "| sample_id | exam | gold total | predicted total | dimensions wrong | valid JSON |",
             "|---|---|---|---|---|---|"]
    flagged = 0
    for d in details:
        gold, pred = d.get("gold"), d.get("prediction")
        if gold is None:
            continue
        diff = None if pred is None else abs(float(pred["total_score"]) - float(gold["total_score"]))
        if pred is not None and diff < threshold:
            continue
        flagged += 1
        wrong = "" if pred is None else ", ".join(
            f"{k} {gold['rubric'][k]}→{pred['rubric'][k]}" for k in DIMENSIONS if pred["rubric"][k] != gold["rubric"][k])
        lines.append(f"| {d['sample_id']} | {d.get('exam_id', '')} | {gold['total_score']} | "
                     f"{'—' if pred is None else pred['total_score']} | {wrong or '—'} | {d['strict_output_ok']} |")
    lines += ["", f"{flagged}/{len(details)} samples deviate by >= {threshold:g} points or produced no valid score."]
    return "\n".join(lines) + "\n"
