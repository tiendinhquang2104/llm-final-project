"""Public contract checks use artificial metadata; no student source is opened."""

import hashlib
import json
import zipfile

import pytest

from src.synth.feedback import FEEDBACK_LEVELS
from src.synth.taxonomy import LABEL_SPACE
from src.task3.public_contract import verify_public_contract


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def release(tmp_path):
    write_json(tmp_path / "task3_requested_levels.json", [
        {"sample_id": "TEST-A", "requested_level": 1},
        {"sample_id": "TEST-B", "requested_level": 2},
    ])
    write_json(tmp_path / "task3_feedback.json", {
        "n_samples": 2,
        "output_fields": ["taxonomy_error: list[str]", "feedback: str"],
        "samples": [
            {"sample_id": "TEST-A", "input": {"target_feedback_level": FEEDBACK_LEVELS[0],
                                                 "code_file": "DO-NOT-OPEN.cpp"}},
            {"sample_id": "TEST-B", "input": {"target_feedback_level": FEEDBACK_LEVELS[1],
                                                 "compile_log": "DO NOT USE"}},
        ],
    })
    write_json(tmp_path / "label_space.json", {
        "taxonomy_error": list(LABEL_SPACE),
        "feedback_level": [{"level": level, "định nghĩa": "metadata"} for level in FEEDBACK_LEVELS],
    })
    return tmp_path


def verify(root, **kwargs):
    return verify_public_contract(root, zip_path=root / "missing.zip", expected_count=2,
                                  expected_counts={1: 1, 2: 1, 3: 0, 4: 0}, **kwargs)


def test_fallback_returns_only_metadata_and_full_level_names(release):
    result = verify(release)
    assert result["records"] == 2
    assert result["requested_levels"] == {"TEST-A": FEEDBACK_LEVELS[0], "TEST-B": FEEDBACK_LEVELS[1]}
    assert result["level_counts"] == {1: 1, 2: 1, 3: 0, 4: 0}
    assert result["taxonomy_labels"] == list(LABEL_SPACE)
    assert result["source"] == "raw-fallback"
    assert result["zip_sha256"] is None
    assert "DO-NOT-OPEN" not in json.dumps(result)
    assert "DO NOT USE" not in json.dumps(result)


@pytest.mark.parametrize("payload", [
    {"TEST-A": 1, "TEST-B": 2},
    {"requested_levels": {"TEST-A": FEEDBACK_LEVELS[0], "TEST-B": FEEDBACK_LEVELS[1]}},
    {"samples": [{"sample_id": "TEST-A", "level": 1}, {"sample_id": "TEST-B", "level": 2}]},
    {"levels": [["TEST-A", 1], ["TEST-B", 2]]},
])
def test_accepts_existing_requested_level_loader_shapes(release, payload):
    write_json(release / "task3_requested_levels.json", payload)
    assert verify(release)["records"] == 2


@pytest.mark.parametrize("mutation,match", [
    ("duplicate-request", "duplicate"),
    ("duplicate-sample", "duplicate"),
    ("id-set", "IDs"),
    ("level", "Level"),
    ("missing-level", "Level"),
    ("bool-level", "Level"),
    ("declared-count", "n_samples"),
    ("count-type", "n_samples"),
    ("output-fields", "output_fields"),
    ("labels", "taxonomy"),
    ("duplicate-label", "taxonomy"),
    ("definitions", "feedback"),
])
def test_rejects_contract_mismatches(release, mutation, match):
    req_path = release / "task3_requested_levels.json"
    sample_path = release / "task3_feedback.json"
    label_path = release / "label_space.json"
    req, payload, labels = (json.loads(p.read_text()) for p in (req_path, sample_path, label_path))
    if mutation == "duplicate-request": req[1]["sample_id"] = "TEST-A"
    if mutation == "duplicate-sample": payload["samples"][1]["sample_id"] = "TEST-A"
    if mutation == "id-set": payload["samples"][1]["sample_id"] = "TEST-UNKNOWN"
    if mutation == "level": payload["samples"][1]["input"]["target_feedback_level"] = FEEDBACK_LEVELS[0]
    if mutation == "missing-level": payload["samples"][1]["input"].pop("target_feedback_level")
    if mutation == "bool-level": req[0]["requested_level"] = True
    if mutation == "declared-count": payload["n_samples"] = 3
    if mutation == "count-type": payload["n_samples"] = 2.0
    if mutation == "output-fields": payload["output_fields"] = ["feedback: str"]
    if mutation == "labels": labels["taxonomy_error"][-1] = "unofficial"
    if mutation == "duplicate-label": labels["taxonomy_error"].append(LABEL_SPACE[0])
    if mutation == "definitions": labels["feedback_level"].pop()
    for path, value in ((req_path, req), (sample_path, payload), (label_path, labels)):
        write_json(path, value)
    with pytest.raises(ValueError, match=match):
        verify(release)


def test_production_defaults_require_328_records(release):
    with pytest.raises(ValueError, match="328"):
        verify_public_contract(release, zip_path=release / "missing.zip")


def test_rejects_wrong_level_distribution(release):
    with pytest.raises(ValueError, match="counts"):
        verify_public_contract(release, zip_path=release / "missing.zip", expected_count=2,
                               expected_counts={1: 2, 2: 0, 3: 0, 4: 0})


def trusted_archive(release, monkeypatch, *, sample=None, raw=None):
    from src.task3 import public_contract

    requested = raw or (release / "task3_requested_levels.json").read_bytes()
    archive = release / "official.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("t3-feedback/task3_requested_levels.json", requested)
        z.writestr("t3-feedback/sample_submission_task3.json", json.dumps(sample or [{
            "sample_id": "EXAMPLE-ONLY", "output": {"taxonomy_error": ["IGNORE CONTENT"],
                                                       "feedback": "IGNORE CONTENT"}}]))
        z.writestr("t3-feedback/student.cpp", "DO NOT READ OR EXTRACT")
    monkeypatch.setattr(public_contract, "OFFICIAL_ZIP_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest())
    monkeypatch.setattr(public_contract, "REQUESTED_LEVELS_SHA256", hashlib.sha256(requested).hexdigest())
    return archive


def test_verified_archive_precedes_raw_fallback_and_only_reports_example_shape(release, monkeypatch):
    archive = trusted_archive(release, monkeypatch)
    (release / "task3_requested_levels.json").unlink()
    result = verify_public_contract(release, zip_path=archive, expected_count=2,
                                    expected_counts={1: 1, 2: 1, 3: 0, 4: 0})
    assert result["source"] == "official-zip"
    assert result["requested_member"] == "t3-feedback/task3_requested_levels.json"
    assert result["sample_submission_shape"] == {
        "container": "list", "rows": 1, "row_fields": ["sample_id", "output"],
        "output_fields": ["taxonomy_error", "feedback"], "taxonomy_type": "list", "feedback_type": "str",
    }
    assert "IGNORE CONTENT" not in json.dumps(result)
    assert not (release / "t3-feedback").exists()


def test_existing_untrusted_archive_never_falls_back(release):
    archive = release / "wrong.zip"
    archive.write_bytes(b"untrusted archive")
    with pytest.raises(ValueError, match="ZIP SHA256"):
        verify_public_contract(release, zip_path=archive, expected_count=2,
                               expected_counts={1: 1, 2: 1, 3: 0, 4: 0})


def test_rejects_requested_member_hash_mismatch(release, monkeypatch):
    from src.task3 import public_contract

    archive = trusted_archive(release, monkeypatch)
    monkeypatch.setattr(public_contract, "REQUESTED_LEVELS_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="member SHA256"):
        verify_public_contract(release, zip_path=archive)


def test_rejects_example_output_shape_without_inspecting_values(release, monkeypatch):
    archive = trusted_archive(release, monkeypatch, sample=[{
        "sample_id": "EXAMPLE", "output": {"feedback": "content ignored"}}])
    with pytest.raises(ValueError, match="sample submission.*shape"):
        verify_public_contract(release, zip_path=archive, expected_count=2,
                               expected_counts={1: 1, 2: 1, 3: 0, 4: 0})


@pytest.mark.parametrize("name", ["label_space.json", "task3_feedback.json"])
def test_rejects_nonobject_metadata(release, name):
    write_json(release / name, [])
    with pytest.raises(ValueError, match="metadata.*object"):
        verify(release)


def test_rejects_duplicate_json_id_keys(release):
    (release / "task3_requested_levels.json").write_text('{"TEST-A": 1, "TEST-A": 2}')
    with pytest.raises(ValueError, match="duplicate"):
        verify(release)


def test_verified_archive_requires_both_metadata_members(release, monkeypatch):
    from src.task3 import public_contract

    archive = release / "missing-member.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("t3-feedback/task3_requested_levels.json", "[]")
    monkeypatch.setattr(public_contract, "OFFICIAL_ZIP_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match="members"):
        verify_public_contract(release, zip_path=archive)
