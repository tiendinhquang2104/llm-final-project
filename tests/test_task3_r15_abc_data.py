"""Protection boundaries: same-source variants, transitive duplicates and targets."""
import copy
import hashlib
import pytest


def row(sid, code, **kwargs):
    return dict(sample_id=sid, code=code, family="fixture", origin="synthetic-train",
                original_submission_id=sid, statement="Tính giá trị được yêu cầu.", **kwargs)


def test_all_levels_of_same_source_stay_in_one_partition():
    from src.task3.r15_abc_data import build_partitions
    a = row("a", "int f(){return 7;}")
    b = row("b", "int f(){return 7;}")
    b["requested_level"] = 3
    result = build_partitions(dict(optimizer_candidates=[a], checkpoint_candidates=[],
                                  comparison_sources=[b], public=[]), {}, dict(checkpoint_dev_sources=0))
    assert result["optimizer_train"] == []
    assert result["group_by_id"]["a"] == result["group_by_id"]["b"]
    assert len(result["comparison_dev"]) == 3
    assert {r["sample_id"] for r in result["comparison_dev"]} == {"b@L1", "b@L2", "b@L3"}
    assert b["sample_id"] == "b"


def test_near_duplicate_cannot_cross_train_dev():
    from src.task3.r15_abc_data import build_partitions
    code = "int solve(int n){int total=0;for(int i=0;i<n;i++){total+=i;}return total;}"
    train = row("a", code)
    dev = row("b", code.replace("total", "accumulator").replace("solve", "calculate"))
    result = build_partitions(dict(optimizer_candidates=[train], checkpoint_candidates=[dev],
                                  comparison_sources=[], public=[]), {}, dict(checkpoint_dev_sources=1))
    assert result["optimizer_train"] == []
    assert result["group_by_id"]["a"] == result["group_by_id"]["b"]


def test_public_label_never_enters_query_or_bank():
    from src.task3.r15_abc_data import build_partitions, query_record
    source = row("x", "int f(){return 0;}", taxonomy_annotation=["Lỗi logic"], teacher_feedback="SECRET_GOLD")
    record = query_record(source, 2)
    from src.task3.round15 import query_payload
    assert "SECRET_GOLD" not in str(query_payload(record))
    assert "taxonomy_annotation" not in str(query_payload(record))
    source["origin"] = "public"
    with pytest.raises(ValueError, match="public"):
        build_partitions(dict(optimizer_candidates=[source], checkpoint_candidates=[],
                              comparison_sources=[], public=[]), {}, {})


def test_compiler_teacher_disagreement_does_not_rewrite_gold():
    from src.task3.r15_abc_data import validate_training_targets
    code = "void main(){}"
    target = dict(sample_id="x", source_sha256=hashlib.sha256(code.encode()).hexdigest(),
                  annotation_disagreement="unresolved", original_annotation=["Lỗi logic"],
                  curated_targets=[], author="agent", evidence="toolchain disagreement")
    before = copy.deepcopy(target)
    result = validate_training_targets([target], {"optimizer_train": [row("x", code)]})
    assert result["accepted"] == []
    assert result["excluded"][0]["reason"] == "annotation_disagreement"
    assert target == before


def test_full_source_target_overlength_is_excluded_not_truncated():
    from src.task3.r15_abc_data import encode_source_targets
    from src.task3.inference import MockTokenizer
    source = row("x", "int main(){" + "long_name++;" * 100 + "}")
    targets = [{"level": level, "output": {"taxonomy_error": [], "feedback": "Chưa kết luận toàn bài."}}
               for level in (1, 2, 3)]
    examples, audit = encode_source_targets(source, targets, MockTokenizer(), 16)
    assert examples == []
    assert audit["status"] == "overlength"
    assert source["code"].endswith("long_name++;}")


def binding_fixture():
    from src.task3.r15_abc_data import encode_source_targets
    from src.task3.inference import MockTokenizer
    sources, reviews, examples, bank = [], [], [], []
    for i in range(6):
        source = row(str(i), "int main(){return " + str(i) + ";}")
        source["compiler"] = {"status": "compiled", "diagnostic": ""}
        targets = [{"level": level, "output": {"taxonomy_error": [] if i % 2 else ["Lỗi logic"],
                                                "feedback": "Phù hợp trong phạm vi đề." if i % 2 else "Bài cần xem lại."}}
                   for level in (1, 2, 3)]
        sources.append(source)
        reviews.append(dict(sample_id=str(i), curated_targets=targets, defect_status="scoped_clean" if i % 2 else "defect"))
        encoded, _ = encode_source_targets(source, targets, MockTokenizer(), 8192)
        examples.extend(encoded)
        bank.append(dict(sample_id=str(i), level=i//2+1, statement=source["statement"], code=source["code"],
                         problems=[], grading_policy=None, compiler=source["compiler"], output=targets[i//2]["output"]))
    return sources, reviews, examples, bank, MockTokenizer()


def test_frozen_supervision_is_rebuilt_from_approved_sources_and_targets():
    from src.task3.r15_abc_data import validate_supervision_bindings
    args = binding_fixture()
    validate_supervision_bindings(*args)
    bad = copy.deepcopy(args[2])
    bad[0]["messages"][-1]["content"] = "some other source"
    with pytest.raises(ValueError, match="source|binding"):
        validate_supervision_bindings(args[0], args[1], bad, args[3], args[4])
    wrong_bank = copy.deepcopy(args[3])
    wrong_bank[0]["code"] = "int wrong;"
    with pytest.raises(ValueError, match="bank"):
        validate_supervision_bindings(args[0], args[1], args[2], wrong_bank, args[4])


def test_c_data_blocked_does_not_block_independent_a():
    from src.task3.r15_abc_data import assess_arm_data
    status = assess_arm_data({"optimizer_train": [], "checkpoint_dev": []}, [], [], [], [], None)
    assert status["A"]["status"] == "ready"
    assert status["C"]["status"] == "data_blocked"
