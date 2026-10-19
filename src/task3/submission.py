"""Strict offline validation for Task 3 prediction bundles."""

from __future__ import annotations

from pathlib import Path

from src.synth.feedback import FEEDBACK_LEVELS
from src.synth.taxonomy import LABEL_SPACE
from src.task3.dataset import read_json
from src.task3.schema import validate_taxonomy


def load_requested_levels(path):
    """Read an ID-to-Level map or a list of ID/Level rows without losing order."""
    payload = read_json(path)
    if isinstance(payload, dict):
        for key in ("requested_levels", "samples", "levels"):
            if key in payload:
                payload = payload[key]
                break
        else:
            rows = list(payload.items())
            payload = [{"sample_id": sid, "level": level} for sid, level in rows]
    if isinstance(payload, dict):
        rows = list(payload.items())
        payload = [{"sample_id": sid, "level": level} for sid, level in rows]
    if not isinstance(payload, list):
        raise ValueError("requested levels must be an ID map or a list of rows")

    result = {}
    for row in payload:
        if isinstance(row, (list, tuple)) and len(row) == 2:
            sid, level = row
        elif isinstance(row, dict):
            sid = row.get("sample_id")
            level = row.get("target_feedback_level", row.get("feedback_level", row.get("level")))
        else:
            raise ValueError("invalid requested-level row")
        if not isinstance(sid, str) or not sid.strip() or not isinstance(level, str) or level not in FEEDBACK_LEVELS:
            raise ValueError("invalid requested-level ID or Level")
        if sid in result:
            raise ValueError("duplicate requested-level ID")
        result[sid] = level
    if not result:
        raise ValueError("requested-level file is empty")
    return result


def validate_submission(path, requested_levels):
    """Validate exact output schema and ordered ID coverage, returning only counts."""
    if not isinstance(requested_levels, dict) or not requested_levels:
        raise ValueError("requested levels must be a nonempty ID-to-Level map")
    for sid, level in requested_levels.items():
        if not isinstance(sid, str) or not sid or level not in FEEDBACK_LEVELS:
            raise ValueError("invalid requested-level ID or Level")
    predictions = read_json(path)
    if not isinstance(predictions, list):
        raise ValueError("predictions must be a JSON array")
    observed_ids = []
    level_counts = {level: 0 for level in FEEDBACK_LEVELS}
    for row in predictions:
        if not isinstance(row, dict) or set(row) != {"sample_id", "output"}:
            raise ValueError("prediction item must contain exactly sample_id and output")
        sid = row["sample_id"]
        if not isinstance(sid, str) or not sid:
            raise ValueError("prediction item has an invalid sample_id")
        observed_ids.append(sid)
        output = row["output"]
        if not isinstance(output, dict) or set(output) != {"taxonomy_error", "feedback"}:
            raise ValueError("output must contain exactly taxonomy_error and feedback")
        labels = output["taxonomy_error"]
        validate_taxonomy(labels)
        if any(label not in LABEL_SPACE for label in labels):
            raise ValueError("taxonomy_error contains labels outside the label space")
        feedback = output["feedback"]
        if not isinstance(feedback, str) or not feedback.strip():
            raise ValueError("feedback must be nonempty UTF-8 text")
        if sid in requested_levels:
            level_counts[requested_levels[sid]] += 1

    if len(set(observed_ids)) != len(observed_ids):
        raise ValueError("duplicate prediction IDs")
    if len(predictions) != len(requested_levels):
        raise ValueError("prediction count does not match requested-level count")
    if observed_ids != list(requested_levels):
        raise ValueError("prediction IDs/order do not exactly match requested-level IDs")
    return {"records": len(predictions), "levels": level_counts}


def validate_submission_files(predictions_path, requested_levels_path):
    requested_levels = load_requested_levels(requested_levels_path)
    return validate_submission(Path(predictions_path), requested_levels)
