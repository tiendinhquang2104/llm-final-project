"""Verify public release metadata without loading source or prediction content.

The verifier never extracts an archive, opens a referenced code file, or uses a
public sample's exam, compile log, test report, taxonomy or feedback. The example
submission is inspected only for container, field and value types.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from src.synth.feedback import FEEDBACK_LEVELS
from src.synth.taxonomy import LABEL_SPACE

OFFICIAL_ZIP = Path("/workspace/public-test-cham-diem-phan-hoi-files.zip")
OFFICIAL_ZIP_SHA256 = "7ae1fc242e44aab07d8606fd17efca8b43a42139c65906bf6c4db843d37c2158"
REQUESTED_MEMBER = "t3-feedback/task3_requested_levels.json"
REQUESTED_LEVELS_SHA256 = "17b8d690f2d86a53a6908da7b95a966194671c9e06117d635da24b1edd70bfa5"
SAMPLE_MEMBER = "t3-feedback/sample_submission_task3.json"
EXPECTED_COUNTS = {1: 115, 2: 163, 3: 50, 4: 0}


def _level(value):
    if type(value) is int and 1 <= value <= 4:
        return FEEDBACK_LEVELS[value - 1]
    if isinstance(value, str) and value in FEEDBACK_LEVELS:
        return value
    raise ValueError("invalid requested Level")


def _requested_levels(raw):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate requested-level JSON key")
            result[key] = value
        return result

    payload = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object)
    if isinstance(payload, dict):
        for key in ("requested_levels", "samples", "levels"):
            if key in payload:
                payload = payload[key]
                break
    if isinstance(payload, dict):
        payload = list(payload.items())
    if not isinstance(payload, list):
        raise ValueError("requested levels must be an ID map or list")
    result = {}
    for row in payload:
        if isinstance(row, (list, tuple)) and len(row) == 2:
            sid, value = row
        elif isinstance(row, dict):
            sid = row.get("sample_id")
            value = row.get("requested_level", row.get("target_feedback_level",
                            row.get("feedback_level", row.get("level"))))
        else:
            raise ValueError("invalid requested-level row")
        if not isinstance(sid, str) or not sid.strip():
            raise ValueError("invalid requested-level ID")
        if sid in result:
            raise ValueError("duplicate requested-level ID")
        result[sid] = _level(value)
    return result


def _sample_shape(raw):
    payload = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("sample submission has invalid shape")
    for row in payload:
        if not isinstance(row, dict) or set(row) != {"sample_id", "output"}:
            raise ValueError("sample submission row has invalid shape")
        output = row["output"]
        if (not isinstance(row["sample_id"], str) or not isinstance(output, dict)
                or set(output) != {"taxonomy_error", "feedback"}
                or not isinstance(output["taxonomy_error"], list)
                or not isinstance(output["feedback"], str)):
            raise ValueError("sample submission output has invalid shape")
    return {"container": "list", "rows": len(payload), "row_fields": ["sample_id", "output"],
            "output_fields": ["taxonomy_error", "feedback"],
            "taxonomy_type": "list", "feedback_type": "str"}


def verify_public_contract(root, zip_path=None, *, expected_count=328, expected_counts=None):
    """Return verified metadata, with production defaults fixed to the 328-ID release.

    ``root`` is the public dataset directory (or repository root). ``zip_path``
    defaults to the supplied official archive; an existing archive must pass both
    SHA256 checks, and only its absence permits the raw requested-level fallback.
    The keyword count overrides support small artificial test fixtures.

    Return keys: ``requested_levels`` (ordered ID -> full Level string),
    ``records``, ``level_counts`` (integer keys 1..4), ``taxonomy_labels``,
    ``feedback_levels`` (definition metadata), ``declarations``, ``source``,
    ``zip_path``, ``zip_sha256``, ``requested_member``, ``requested_sha256`` and
    ``sample_submission_shape`` (None when no archive was present).
    """
    root = Path(root)
    if not (root / "task3_feedback.json").is_file() and (root / "data/raw/public_test_release").is_dir():
        root = root / "data/raw/public_test_release"
    expected_counts = dict(EXPECTED_COUNTS if expected_counts is None else expected_counts)
    if (type(expected_count) is not int or expected_count <= 0
            or set(expected_counts) != {1, 2, 3, 4}
            or any(type(key) is not int for key in expected_counts)
            or any(type(value) is not int or value < 0 for value in expected_counts.values())
            or sum(expected_counts.values()) != expected_count):
        raise ValueError("expected counts must be nonnegative integers summing to expected_count")

    archive = OFFICIAL_ZIP if zip_path is None else Path(zip_path)
    zip_sha256, shape = None, None
    if archive.exists():
        zip_sha256 = hashlib.sha256(archive.read_bytes()).hexdigest()
        if zip_sha256 != OFFICIAL_ZIP_SHA256:
            raise ValueError("official ZIP SHA256 mismatch")
        with ZipFile(archive) as bundle:
            names = bundle.namelist()
            if names.count(REQUESTED_MEMBER) != 1 or names.count(SAMPLE_MEMBER) != 1:
                raise ValueError("official ZIP requires unique requested and sample submission members")
            raw = bundle.read(REQUESTED_MEMBER)
            if hashlib.sha256(raw).hexdigest() != REQUESTED_LEVELS_SHA256:
                raise ValueError("requested-level member SHA256 mismatch")
            shape = _sample_shape(bundle.read(SAMPLE_MEMBER))
        source, member = "official-zip", REQUESTED_MEMBER
    else:
        path = root / "task3_requested_levels.json"
        raw = path.read_bytes()
        source, member = "raw-fallback", None
    requested = _requested_levels(raw)
    if len(requested) != expected_count:
        raise ValueError(f"requested levels must contain exactly {expected_count} unique IDs")
    counts = Counter(FEEDBACK_LEVELS.index(level) + 1 for level in requested.values())
    counts = {level: counts[level] for level in range(1, 5)}
    if counts != expected_counts:
        raise ValueError("requested Level counts mismatch")

    labels = json.loads((root / "label_space.json").read_text(encoding="utf-8-sig"))
    if not isinstance(labels, dict):
        raise ValueError("label metadata must be an object")
    taxonomy = labels.get("taxonomy_error")
    if (not isinstance(taxonomy, list) or len(taxonomy) != 10
            or any(not isinstance(label, str) for label in taxonomy)
            or len(LABEL_SPACE) != 10 or set(taxonomy) != set(LABEL_SPACE)):
        raise ValueError("taxonomy must contain exactly the 10 official labels")
    definitions = labels.get("feedback_level")
    if (not isinstance(definitions, list) or len(definitions) != 4
            or any(not isinstance(item, dict) or item.get("level") not in FEEDBACK_LEVELS
                   for item in definitions)
            or {item["level"] for item in definitions} != set(FEEDBACK_LEVELS)):
        raise ValueError("feedback Level definitions mismatch")

    payload = json.loads((root / "task3_feedback.json").read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("public metadata must be an object")
    samples = payload.get("samples")
    if not isinstance(samples, list):
        raise ValueError("public samples must be a list")
    if type(payload.get("n_samples")) is not int or payload["n_samples"] != len(samples):
        raise ValueError("public n_samples mismatch or noninteger declaration")
    fields = payload.get("output_fields")
    if (not isinstance(fields, list) or any(not isinstance(field, str) for field in fields)
            or {field.split(":", 1)[0].strip() for field in fields} != {"taxonomy_error", "feedback"}
            or len(fields) != 2):
        raise ValueError("public output_fields must declare taxonomy_error and feedback")
    observed = {}
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("invalid public sample metadata")
        sid = sample.get("sample_id")
        if not isinstance(sid, str) or not sid.strip():
            raise ValueError("invalid public sample ID")
        if sid in observed:
            raise ValueError("duplicate public sample ID")
        inputs = sample.get("input")
        if not isinstance(inputs, dict):
            raise ValueError("public input must declare a requested Level")
        observed[sid] = _level(inputs.get("target_feedback_level"))
    if set(observed) != set(requested):
        raise ValueError("public sample IDs do not exactly match requested-level IDs")
    if observed != requested:
        raise ValueError("public input Level does not match requested Level")

    declarations = {key: payload[key] for key in (
        "task", "description", "level_definition_ref", "input_fields", "output_fields", "metric", "n_samples"
    ) if key in payload}
    return {
        "requested_levels": requested, "records": len(requested), "level_counts": counts,
        "taxonomy_labels": taxonomy, "feedback_levels": definitions, "declarations": declarations,
        "source": source, "zip_path": str(archive), "zip_sha256": zip_sha256,
        "requested_member": member, "requested_sha256": hashlib.sha256(raw).hexdigest(),
        "sample_submission_shape": shape,
    }
