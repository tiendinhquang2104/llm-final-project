#!/usr/bin/env python3
"""Check provenance and coverage of the manually reviewed original-train ledger.

This is a structural/evidence-binding check, not a semantic judge. The source-
grounded annotation decisions and repair directions were authored by an agent
after reading the 160 training sources, statements, and all four target Levels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(repo: Path, audit_path: Path) -> dict:
    old_root = repo / "data/raw/task3-sft-v1"
    cases_path = old_root / "cases.private.json"
    evidence_path = old_root / "verification/execution.private.json"
    cases = json.loads(cases_path.read_text())
    train = {c["sample_id"]: c for c in cases if c["split"] == "train"}
    evidence = json.loads(evidence_path.read_text())
    audit = json.loads(audit_path.read_text())
    assert audit["annotation_version"] == "v2.0"
    assert audit["coverage"] == {"sources": 160, "targets": 640}
    assert len(train) == 160
    assert sha256(cases_path) == audit["input_provenance"]["cases_sha256"]
    assert sha256(evidence_path) == audit["input_provenance"]["execution_sha256"]
    reviews = audit["reviews"]
    assert len(reviews) == 160
    assert {x["source_id"] for x in reviews} == set(train)
    assert all(x["reviewed_levels"] == [1, 2, 3, 4] for x in reviews)
    changes = {}
    for change in audit["changes"]:
        sid, level = change["source_id"], str(change["level"])
        assert sid in train and level in {"1", "2", "3", "4"}
        assert (sid, level) not in changes
        assert change["original"] == train[sid]["targets"][level]
        assert change["original"] != change["revised"]
        assert change["revised"]["taxonomy_error"] == train[sid]["labels"]
        assert isinstance(change["revised"]["feedback"], str)
        assert all(change[x] for x in ["reason", "source_evidence", "verification_result"])
        assert change["annotation_version"] == "v2.0"
        changes[sid, level] = change["revised"]
    for review in reviews:
        expected = "revised" if any(sid == review["source_id"] for sid, _ in changes) else "retained"
        assert review["verdict"] == expected
        assert review["evidence"]
    quoted_examples = []
    code_bindings = []
    approved = []
    example_re = re.compile(r'Ví dụ, với dữ liệu "(.*?)", kết quả cần nhận là "(.*?)"\.', re.S)
    for sid, case in train.items():
        source = old_root / case["code_file"]
        assert sha256(source) == case["source_sha256"] == evidence[sid]["source_sha256"]
        assert set(case["targets"]) == {"1", "2", "3", "4"}
        solution_id = case["solution_source_id"]
        assert solution_id in train
        solution_case = train[solution_id]
        solution_code = (old_root / solution_case["code_file"]).read_text()
        assert evidence[solution_id]["all_tests_passed"]
        for level in ["1", "2", "3", "4"]:
            target = changes.get((sid, level), case["targets"][level])
            assert target["taxonomy_error"] == case["labels"]
        target_l4 = changes.get((sid, "4"), case["targets"]["4"])
        blocks = re.findall(r"```cpp\n(.*?)```", target_l4["feedback"], re.S)
        assert len(blocks) == 1 and blocks[0] == solution_code
        code_bindings.append({"source_id": sid, "solution_source_id": solution_id,
                              "code_sha256": hashlib.sha256(blocks[0].encode()).hexdigest(),
                              "verified_solution_tests": len(evidence[solution_id]["tests"])})
        for match in example_re.finditer(target_l4["feedback"]):
            example_input, example_output = (x.replace("\\n", "\n").replace("\\t", "\t") for x in match.groups())
            matches = [t for t in evidence[solution_id]["tests"]
                       if t["input"].strip() == example_input.strip()
                       and t["expected"].strip() == example_output.strip()
                       and t["passed"]]
            assert matches, f"Unbound numeric/output example: {sid}"
            quoted_examples.append({"source_id": sid, "solution_source_id": solution_id,
                                    "test_indices": [t["test_index"] for t in matches],
                                    "input": example_input, "claimed_value": example_output,
                                    "observed_stdout": matches[0]["stdout"]})
        if case["annotation_origin"] == "approved_mini_feedback":
            assert not any(s == sid for s, _ in changes)
            approved.append(sid)
    assert len(approved) == 8
    additional_path = repo / audit["additional_verification"]
    additional = json.loads(additional_path.read_text())
    assert additional["passed"] and len(additional["records"]) == 2
    assert all(x["passed"] for x in additional["records"])
    manual_numeric_bindings = [
        {"target": "F01-P01-D L4", "execution_key": "F01-P01-C", "test_index": 4,
         "scope": "The repaired sum of 1,2,3 is observed as 6."},
        {"target": "F02-P01-D L4", "additional_record": 0,
         "scope": "Divisor 2 and values 3,4,6 give observed output 2."},
        {"target": "F15-P01-D L4", "additional_record": 1,
         "scope": "Positive input 3 gives observed output 10."},
        {"target": "F03-P02-D L3/L4", "execution_key": "F03-P02-D", "test_index": 4,
         "scope": "Equal x coordinates with differing y give observed faulty output 0."},
        {"target": "F06-P02-D L3/L4", "execution_key": "F06-P02-D", "test_index": 7,
         "scope": "Input 999999999 has the recorded signed-overflow diagnostic."},
        {"target": "F09-P02-D L3/L4", "execution_key": "F09-P02-D", "test_index": 1,
         "scope": "A singleton equal to target is observed as not found."},
        {"target": "F10-P01-C L4", "source": "sources/F10-P01-C.cpp",
         "scope": "Source invariant: an update sets best=p->value, making the next strict comparison false at the same node; otherwise p advances. Each node therefore needs at most two iterations. This is a source-derived bound, not a claim of measured runtime."},
    ]
    for binding in manual_numeric_bindings:
        if "execution_key" in binding:
            binding["record"] = evidence[binding["execution_key"]]["tests"][binding["test_index"]]
        elif "additional_record" in binding:
            binding["record"] = additional["records"][binding["additional_record"]]
    return {"passed": True, "review_type": audit["review_type"],
            "coverage": audit["coverage"], "changes": len(changes),
            "changed_levels": {str(i): sum(level == str(i) for _, level in changes) for i in [1, 2, 3, 4]},
            "all_source_hashes_match_packaged_evidence": True,
            "all_l4_code_matches_verified_train_solution": True,
            "approved_mini_sources_retained": approved,
            "approved_mini_targets_retained": 32,
            "generic_quoted_examples_bound": len(quoted_examples),
            "quoted_example_bindings": quoted_examples,
            "other_numeric_or_observed_claim_bindings": manual_numeric_bindings,
            "l4_code_bindings": code_bindings,
            "additional_numeric_verification": str(additional_path.relative_to(repo)),
            "additional_numeric_verification_sha256": sha256(additional_path),
            "semantic_verdict_source": "Manual source-grounded agent review; this program only checks structure and evidence provenance."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    audit = args.audit or repo / "data/raw/task3-sft-v2-authoring/original-target-audit.private.json"
    report = args.report or repo / "data/raw/task3-sft-v2-authoring/original-target-verification/audit-validation.private.json"
    result = validate(repo, audit)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ["passed", "coverage", "changes", "changed_levels", "generic_quoted_examples_bound", "approved_mini_targets_retained"]}))


if __name__ == "__main__":
    main()
