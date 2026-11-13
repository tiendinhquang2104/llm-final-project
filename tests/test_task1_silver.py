"""CPU checks for Task 1 silver filtering and gold-only tie priority."""

from __future__ import annotations

import json
import re
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.task1.finetune import choose_variant, encode_training_record, load_silver_records
from src.task1.silver_data import prepare_silver_task1


FULL = {
    "compilable": 1, "io_format": 1, "logic": 4,
    "edge_case": 2, "complexity": 1, "code_quality": 1,
}


@contextmanager
def expect_raises(error: type[Exception], match: str):
    try:
        yield
    except error as exc:
        assert re.search(match, str(exc)), str(exc)
    else:
        raise AssertionError(f"Expected {error.__name__}: {match}")


def _dataset(root: Path, rows: list[tuple[str, str, str, dict, int]]) -> None:
    root.mkdir()
    (root / "submissions").mkdir()
    (root / "exams.json").write_text(json.dumps({"exams": [{
        "exam_id": "EX1", "exam_type": "single_problem", "statement": "Add two integers",
        "grading_policy": "Evaluate rubric",
    }]}), encoding="utf-8")
    samples = []
    for sid, code, report, rubric, total in rows:
        (root / "submissions" / f"{sid}.cpp").write_text(code, encoding="utf-8")
        samples.append({
            "sample_id": sid,
            "input": {"exam_id": "EX1", "exam_type": "single_problem", "language": "cpp11",
                      "code_file": f"submissions/{sid}.cpp", "compile_log": "", "test_report": None,
                      "exec_report": report},
            "output": {"rubric": rubric, "total_score": total},
        })
    (root / "task1_grading.json").write_text(json.dumps({"samples": samples}), encoding="utf-8")


def test_silver_filters_and_prompt(tmp_path):
    ok_report = "compile: OK (g++ -std=c++11)\nstatement_examples: 2 | pass 2/2"
    fail_report = "compile: FAIL (g++ -std=c++11) | error"
    zero_report = "compile: OK (g++ -std=c++11)\nstatement_examples: 2 | pass 0/2"
    _dataset(tmp_path / "gold", [("G1", "int gold(){return 1;}", ok_report, FULL, 10)])
    _dataset(tmp_path / "public", [("P1", "int pub(){return 1;}", ok_report, FULL, 10)])
    _dataset(tmp_path / "silver", [
        ("S1", "int a(){return 1;}", ok_report, FULL, 10),
        ("S2", "int a(){ return 1; }", ok_report, FULL, 10),
        ("S3", "int b(){return 2;}", fail_report, FULL, 10),
        ("S4", "int c(){return 3;}", zero_report, FULL, 10),
    ])
    # The generated archive's heldout directory is never traversed.
    _dataset(tmp_path / "silver" / "heldout", [("H1", "int h(){return 4;}", ok_report, FULL, 10)])
    (tmp_path / "silver" / "task3_feedback.json").write_text(
        json.dumps({"samples": [{"sample_id": "S1"}, {"sample_id": "T3"}]}), encoding="utf-8"
    )
    manifest = prepare_silver_task1(
        tmp_path / "silver", tmp_path / "gold", tmp_path / "public", tmp_path / "out"
    )
    assert (manifest["n_source_task1"], manifest["n_accepted"], manifest["n_excluded"]) == (4, 1, 3)
    assert (manifest["n_heldout_not_read"], manifest["n_task3_only_not_read"]) == (1, 1)
    assert {x["sample_id"] for x in manifest["excluded"]} == {"S2", "S3", "S4"}
    records = load_silver_records(tmp_path / "out/task1_silver_train.jsonl", [], expected=1)
    assert [r.sample_id for r in records] == ["S1"]
    prompt = records[0].messages[1]["content"]
    assert "(không có compile log)" in prompt
    assert "biên dịch OK" not in prompt
    assert "exec_report" not in prompt and "statement_examples" not in prompt
    assert "feedback" not in prompt.lower()

    class Tokenizer:
        def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
            text = "".join(f"<{m['role']}>{m['content']}</{m['role']}>" for m in messages)
            return list((text + ("<assistant>" if add_generation_prompt else "")).encode())

    encoded = encode_training_record(records[0], Tokenizer(), 4096)
    assert all(label == -100 for label in encoded["labels"][:encoded["prompt_tokens"]])
    with expect_raises(ValueError, match="exceeding max_length"):
        encode_training_record(records[0], Tokenizer(), encoded["total_tokens"] - 1)


def test_silver_overlap_and_tie_priority(tmp_path):
    report = "compile: OK (g++ -std=c++11)"
    _dataset(tmp_path / "gold", [("G1", "int same(){return 1;}", report, FULL, 10)])
    _dataset(tmp_path / "public", [("P1", "int pub(){return 1;}", report, FULL, 10)])
    _dataset(tmp_path / "silver", [("S1", "int same() {return 1;}", report, FULL, 10)])
    with expect_raises(ValueError, match="overlaps gold/public"):
        prepare_silver_task1(tmp_path / "silver", tmp_path / "gold", tmp_path / "public", tmp_path / "out")
    task1_path = tmp_path / "silver" / "task1_grading.json"
    payload = json.loads(task1_path.read_text(encoding="utf-8"))
    payload["samples"][0]["output"]["rubric"].pop("logic")
    task1_path.write_text(json.dumps(payload), encoding="utf-8")
    with expect_raises(ValueError, match="six-dimension rubric"):
        prepare_silver_task1(tmp_path / "silver", tmp_path / "gold", tmp_path / "public", tmp_path / "out")
    gold = {"variant": "gold_only", "metrics": {"qwk": 0.5, "mae": 1.0}}
    silver = {"variant": "silver_then_gold", "metrics": {"qwk": 0.5, "mae": 1.0}}
    assert choose_variant(gold, silver) is gold
    silver["metrics"]["mae"] = 0.9
    assert choose_variant(gold, silver) is silver


if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parents[1] / "data"
    with tempfile.TemporaryDirectory(dir=data_dir) as directory:
        test_silver_filters_and_prompt(Path(directory))
    with tempfile.TemporaryDirectory(dir=data_dir) as directory:
        test_silver_overlap_and_tie_priority(Path(directory))
    print("Task 1 silver tests passed")
