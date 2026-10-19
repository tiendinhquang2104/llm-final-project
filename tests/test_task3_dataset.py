"""All fixtures are artificial TEST-ONLY data, never copied from student submissions."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from src.synth.feedback import FEEDBACK_LEVELS
from src.synth.taxonomy import LABEL_SPACE
from src.task3.dataset import (
    assign_splits,
    audit,
    decode_code,
    fixed_splits,
    load_task3,
    prepare,
    read_json,
    read_jsonl,
    safe_code_path,
    write_json,
)
from src.task3.schema import Task3Record, code_hash, validate_taxonomy

REPOSITORY = Path(__file__).resolve().parents[1]


def record(sid="TEST-A", source="synthetic", **kw):
    values = dict(
        source=source,
        sample_id=sid,
        original_submission_id=sid,
        exam_id="TEST-EXAM",
        exam_type="single_problem",
        statement="TEST-ONLY: tính tổng.",
        grading_policy=None,
        code_path="submissions/TEST.cpp",
        code="int main(){return 17;}",
        target_feedback_level=FEEDBACK_LEVELS[1],
        gold_taxonomy=["Lỗi logic"],
        gold_feedback="TEST-ONLY: kết quả tính tổng chưa đúng.",
        split="synthetic-train",
    )
    if source == "public":
        values.update(gold_taxonomy=None, gold_feedback=None)
    return Task3Record(**(values | kw))


def make_root(path, source, samples=None):
    path.mkdir(parents=True)
    write_json(
        path / "label_space.json",
        {
            "taxonomy_error": list(LABEL_SPACE),
            "feedback_level": [{"level": x, "định nghĩa": "TEST ONLY"} for x in FEEDBACK_LEVELS],
        },
    )
    write_json(
        path / "exams.json",
        {"exams": [{"exam_id": "TEST-EXAM", "exam_type": "single_problem", "statement": "TEST-ONLY exam"}]},
    )
    if samples is None:
        samples = []
        for n, level in enumerate(FEEDBACK_LEVELS):
            codefile = f"submissions/TEST-{n}.cpp"
            codepath = path / codefile
            codepath.parent.mkdir(exist_ok=True)
            codepath.write_text(f"int main(){{return {n + 10};}}", encoding="utf-8")
            i = dict(exam_id="TEST-EXAM", exam_type="single_problem", code_file=codefile, target_feedback_level=level)
            if source == "real":
                i["taxonomy_error"] = [] if n == 0 else ["Lỗi logic"]
            if source.startswith("synthetic"):
                i["exec_report"] = "compile: OK\nstatement_examples: none"
            s = dict(sample_id=f"TEST-{n}", input=i)
            if source != "public":
                s["output"] = {"feedback": "TEST-ONLY: Em kiểm tra lại nhé."}
                if source.startswith("synthetic"):
                    s["output"]["taxonomy_error"] = [] if n == 0 else ["Lỗi logic"]
            samples.append(s)
    write_json(
        path / "task3_feedback.json",
        {"n_samples": len(samples), "output_fields": ["taxonomy_error", "feedback"], "samples": samples},
    )
    return path


@pytest.mark.parametrize("source", ["real", "public", "synthetic", "synthetic-heldout"])
def test_four_schemas_all_levels(tmp_path, source):
    root = make_root(tmp_path / source, source)
    rows = load_task3(root, source)
    assert len(rows) == 4
    assert [r.target_feedback_level for r in rows] == list(FEEDBACK_LEVELS)
    assert rows[0].gold_taxonomy == (None if source == "public" else [])
    assert (rows[0].gold_feedback is None) == (source == "public")
    assert (rows[0].synthetic_exec_report is not None) == source.startswith("synthetic")


def test_public_requested_levels_are_merged_without_taxonomy_or_output(tmp_path):
    root = make_root(tmp_path / "public", "public")
    payload = read_json(root / "task3_feedback.json")
    levels = {}
    for sample in payload["samples"]:
        levels[sample["sample_id"]] = sample["input"].pop("target_feedback_level")
    write_json(root / "task3_feedback.json", payload)
    write_json(root / "task3_requested_levels.json", {"requested_levels": levels})

    rows = load_task3(root, "public")

    assert [row.target_feedback_level for row in rows] == list(FEEDBACK_LEVELS)
    assert all(row.gold_taxonomy is None and row.gold_feedback is None for row in rows)


def test_public_requested_level_mismatch_fails_closed(tmp_path):
    root = make_root(tmp_path / "public", "public")
    write_json(
        root / "task3_requested_levels.json",
        {"TEST-0": FEEDBACK_LEVELS[1], "TEST-1": FEEDBACK_LEVELS[1], "TEST-2": FEEDBACK_LEVELS[2], "TEST-3": FEEDBACK_LEVELS[3]},
    )

    with pytest.raises(ValueError, match="requested Level"):
        load_task3(root, "public")


def test_heldout_inherits_parent_label_space(tmp_path):
    parent = make_root(tmp_path / "synthetic", "synthetic")
    child = make_root(parent / "heldout", "synthetic-heldout")
    (child / "label_space.json").unlink()
    assert len(load_task3(child, "synthetic-heldout")) == 4


@pytest.mark.parametrize("bad", [None, "[]", ["unknown"], ["Lỗi logic", "Lỗi logic"], [None]])
def test_taxonomy_rejects_missing_invalid(bad):
    with pytest.raises(ValueError):
        validate_taxonomy(bad)


def test_missing_gold_is_not_empty(tmp_path):
    root = make_root(tmp_path / "real", "real")
    d = read_json(root / "task3_feedback.json")
    del d["samples"][0]["input"]["taxonomy_error"]
    write_json(root / "task3_feedback.json", d)
    with pytest.raises(ValueError, match="missing is not"):
        load_task3(root, "real")


@pytest.mark.parametrize(
    "reference",
    [
        "../escape.cpp",
        "/tmp/escape.cpp",
        "submissions/../../escape.cpp",
        "C:\\escape.cpp",
        "submissions\\test.cpp",
        "test.txt",
    ],
)
def test_safe_path_rejects_traversal(tmp_path, reference):
    with pytest.raises(ValueError):
        safe_code_path(tmp_path, reference)


def test_symlink_and_missing(tmp_path):
    (tmp_path / "inner").mkdir()
    external = tmp_path / "outside.cpp"
    external.write_text("TEST ONLY")
    (tmp_path / "inner" / "link.cpp").symlink_to(external)
    with pytest.raises(ValueError):
        safe_code_path(tmp_path / "inner", "link.cpp")
    with pytest.raises(FileNotFoundError, match="missing referenced"):
        safe_code_path(tmp_path, "missing.cpp")


def test_code_decoding_fallback_and_literals(tmp_path):
    p = tmp_path / "test.cpp"
    p.write_bytes(b"// \xff\nint main(){return 0;}")
    assert "int main" in decode_code(p)
    assert code_hash('cout << "//foo"; // comment') == code_hash('cout<<"//foo";')
    assert code_hash('cout << "a";') != code_hash('cout << "b";')
    assert code_hash("int x=2; return x;", renamed=True) == code_hash("int y=2; return y;", renamed=True)


def test_synthetic_level_clones_reference_original_file(tmp_path):
    root = make_root(tmp_path / "synth", "synthetic")
    d = read_json(root / "task3_feedback.json")
    clone = json.loads(json.dumps(d["samples"][0]))
    clone["sample_id"] += "-L3"
    clone["input"]["target_feedback_level"] = FEEDBACK_LEVELS[2]
    d["samples"].append(clone)
    d["n_samples"] += 1
    write_json(root / "task3_feedback.json", d)
    rows = load_task3(root, "synthetic")
    assign_splits(rows, {"train": set(), "val": set()})
    assert rows[0].original_submission_id == rows[-1].original_submission_id
    assert rows[0].group_key == rows[-1].group_key


def test_overlap_quarantine_preserves_real_fixed_partitions():
    real = [record("REAL-A", "real"), record("REAL-B", "real", code="int main(){return 99;}")]
    synth = record("SYN-A", code=real[1].code)
    held = record("HELD-A", "synthetic-heldout", code=real[0].code)
    rows = real + [synth, held]
    findings = assign_splits(rows, {"train": {"REAL-A"}, "val": {"REAL-B"}})
    assert [r.split for r in real] == ["real-train", "real-val"]
    assert synth.split == held.split == "quarantine"
    assert sum(finding["quarantined"] for finding in findings) == 2
    assert all(finding["source_ids"] for finding in findings)


def test_public_code_overlap_is_reported_without_moving_fixed_real_ids():
    real = record("REAL-TRAIN", "real")
    public = record("PUBLIC", "public", code=real.code)
    report = assign_splits([real, public], {"train": {"REAL-TRAIN"}, "val": set()})
    assert real.split == "real-train"
    assert public.split == "public"
    assert any("public_group_overlap" in finding["reason"] for finding in report)
    assert any(finding["source_ids"] == ["public:PUBLIC", "real:REAL-TRAIN"] for finding in report)


def test_fixed_real_code_overlap_fails_loudly():
    rows = [record("A", "real"), record("B", "real")]
    with pytest.raises(ValueError, match="fixed real"):
        assign_splits(rows, {"train": {"A"}, "val": {"B"}})


def test_transitive_provenance_grouping():
    rows = [
        record("A", provenance={"base_id": "TEST~v0"}),
        record("B", code="int z=10;", provenance={"base_id": "TEST~v1", "pair_id": "pair"}),
        record("C", code="return 9;", provenance={"pair_id": "pair"}),
    ]
    assign_splits(rows, {"train": set(), "val": set()})
    assert len({r.group_key for r in rows}) == 1


def test_audit_is_ids_and_aggregates_only():
    r = record(
        gold_feedback="PRIVATE-TARGET",
        code="PRIVATE-CODE",
        synthetic_exec_report="compile: FAIL",
        gold_taxonomy=[],
        compile_log="x" * 9000,
    )
    report = audit([r])
    text = json.dumps(report)
    assert "PRIVATE-TARGET" not in text and "PRIVATE-CODE" not in text
    assert "long_compile_log" in text and "signal_contradiction_compile_fail" in text


def test_missing_fixed_splits_fail_closed_instead_of_reading_head(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    with pytest.raises(FileNotFoundError, match="fixed split file"):
        fixed_splits(tmp_path)


def test_clean_clone_contains_official_fixed_splits_and_history(tmp_path):
    origin = tmp_path / "origin"
    origin.mkdir()
    relatives = (
        "data/README.md",
        "data/raw/.gitkeep",
        "data/processed/.gitkeep",
        "data/splits/train_ids.json",
        "data/splits/val_ids.json",
        "data/splits/history_13_19/train_ids.json",
        "data/splits/history_13_19/val_ids.json",
    )
    for relative in relatives:
        destination = origin / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY / relative, destination)
    subprocess.run(["git", "init", "-q", str(origin)], check=True)
    subprocess.run(["git", "add", "."], cwd=origin, check=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.invalid", "-c", "user.name=TEST", "commit", "-qm", "TEST split clone"],
        cwd=origin,
        check=True,
    )
    clean_clone = tmp_path / "clean-clone"
    subprocess.run(["git", "clone", "--quiet", str(origin), str(clean_clone)], check=True)
    splits, origins = fixed_splits(clean_clone)
    assert (len(splits["train"]), len(splits["val"])) == (26, 6)
    assert not splits["train"] & splits["val"]
    assert all(origins[name]["origin"] == "working-tree" for name in ("train", "val"))
    assert all((clean_clone / relative).is_file() for relative in relatives)
    for relative in relatives:
        assert (clean_clone / relative).read_bytes() == (REPOSITORY / relative).read_bytes()


def test_prepare_end_to_end_public_has_no_completion_and_strict_filter_reported(tmp_path):
    roots = {}
    for n, source in enumerate(("real", "synthetic", "synthetic-heldout", "public")):
        root = make_root(tmp_path / source, source)
        d = read_json(root / "task3_feedback.json")
        for i, s in enumerate(d["samples"]):
            (root / s["input"]["code_file"]).write_text(f"int main(){{return {100 * n + i};}}", encoding="utf-8")
            if source != "real":
                original = root / s["input"]["code_file"]
                new_path = original.with_name(f"{source}-{i}.cpp")
                original.rename(new_path)
                s["input"]["code_file"] = new_path.relative_to(root).as_posix()
                s["sample_id"] = f"{source}-{i}"
        if source == "synthetic":
            d["samples"][0]["output"]["feedback"] = "```cpp\nreturn 0;\n```"
        write_json(root / "task3_feedback.json", d)
        roots[source] = root
    repo = tmp_path / "repo"
    write_json(repo / "data/splits/train_ids.json", ["TEST-0", "TEST-1"])
    write_json(repo / "data/splits/val_ids.json", ["TEST-2", "TEST-3"])
    before = (repo / "data/splits/train_ids.json").read_bytes()
    output = tmp_path / "processed"
    manifest = prepare(roots, output, repo, filter_synthetic="strict", require_official_split=False)
    assert manifest["partitions"]["real-train"] == 2
    assert manifest["partitions"]["real-val"] == 2
    assert manifest["partitions"]["synthetic-train"] == 3
    assert manifest["partitions"]["quarantine"] == 1
    assert manifest["quality_filtered_count"] == 1
    assert manifest["partition_counts_before_quality_filter"] != manifest["partition_counts_after_filter"]
    assert all("completion" not in row and row["prompt"] is None for row in read_jsonl(output / "public.jsonl"))
    for row in read_jsonl(output / "real-train.jsonl"):
        assert row["completion"][0]["content"] == row["record"]["gold_feedback"]
        assert row["record"]["gold_feedback"] not in json.dumps(row["prompt"], ensure_ascii=False)
    assert (repo / "data/splits/train_ids.json").read_bytes() == before
    assert "TEST-ONLY exam" not in json.dumps(manifest)
    manifest2 = prepare(
        roots,
        tmp_path / "processed-again",
        repo,
        filter_synthetic="strict",
        require_official_split=False,
    )
    assert manifest == manifest2


@pytest.mark.parametrize(
    "field,value", [("target_feedback_level", "Level 5"), ("gold_feedback", ""), ("exam_type", "other")]
)
def test_typed_record_rejects_schema_mismatch(field, value):
    with pytest.raises(ValueError):
        record(**{field: value})


def test_public_input_cannot_smuggle_gold_labels(tmp_path):
    root = make_root(tmp_path / "public", "public")
    d = read_json(root / "task3_feedback.json")
    d["samples"][0]["input"]["taxonomy_error"] = []
    write_json(root / "task3_feedback.json", d)
    with pytest.raises(ValueError, match="public must have missing"):
        load_task3(root, "public")
