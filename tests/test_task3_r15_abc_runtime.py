"""Resume safety for the bounded R15 experiment (no GPU required)."""
import copy
from pathlib import Path
import pytest

def test_identity_binds_code_bank_adapter_and_inputs(tmp_path):
    from src.task3 import r15_abc_experiment as exp
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    (adapter / "adapter_config.json").write_text('{"r":16}')
    (adapter / "adapter_model.safetensors").write_bytes(b"first-tensor")
    baseline = {"config": {"seed": 42}, "tokenizer": {"chat_template_sha256": "chat"},
                "code": {"runner": "a"}, "inputs": [{"code": "int main(){}", "requested_level": 2}],
                "compiler": {"projection": "r15"}, "bank": [{"feedback": "vi"}],
                "adapter": exp.adapter_identity(adapter)}
    sealed = exp.execution_identity(baseline)
    for field in baseline:
        changed = copy.deepcopy(baseline)
        changed[field] = {"changed": field}
        assert exp.execution_identity(changed) != sealed
        with pytest.raises(ValueError, match="identity"):
            exp.require_identity(sealed, changed)
    (adapter / "adapter_model.safetensors").write_bytes(b"other-tensor")
    changed = {**baseline, "adapter": exp.adapter_identity(adapter)}
    with pytest.raises(ValueError, match="identity"):
        exp.require_identity(sealed, changed)


def test_adapter_requires_tensor_bytes(tmp_path):
    from src.task3 import r15_abc_experiment as exp
    (tmp_path / "adapter_config.json").write_text('{}')
    with pytest.raises(ValueError, match="tensor"):
        exp.adapter_identity(tmp_path)


def record(level=2, sid="fixture"):
    from src.task3.r15_abc_data import query_record
    return query_record(dict(sample_id=sid, family="artificial", code="int main(){return 0;}",
                             statement="Trả về 0.", compiler={"status": "compiled", "diagnostic": ""}), level)


def bank():
    return [{"level": 2, "sample_id": "demo", "statement": "Trả về 1.", "code": "int main(){return 1;}",
             "compiler": {"status": "compiled", "diagnostic": ""},
             "output": {"taxonomy_error": [], "feedback": "Phù hợp trong phạm vi yêu cầu."}}]


def test_arm_a_messages_equal_historical_r15():
    from src.task3.r15_abc_experiment import arm_messages
    from src.task3.round15 import build_messages
    assert arm_messages(record(), "A", bank()) == build_messages(record(), [])


def test_arm_b_only_adds_demonstrations():
    from src.task3.r15_abc_experiment import arm_messages
    a, b = arm_messages(record(), "A", bank()), arm_messages(record(), "B", bank())
    assert b[0] == a[0] and b[-1] == a[-1]
    assert [m["role"] for m in b] == ["system", "user", "assistant", "user"]


def test_arm_c_messages_equal_a_with_adapter_identity_only():
    from src.task3.r15_abc_experiment import arm_messages
    assert arm_messages(record(), "C", bank()) == arm_messages(record(), "A", bank())


class Backend:
    from src.task3.inference import MockTokenizer
    tokenizer = MockTokenizer()
    def __init__(self, text=None):
        self.calls = 0
        self.text = text
    def generate(self, messages, config):
        from src.task3.inference import Generation
        self.calls += 1
        if self.text == "runtime":
            raise RuntimeError("fixture runtime failure")
        return Generation(self.text or '{"taxonomy_error":[],"feedback":"Phù hợp trong phạm vi đề."}', 12, .1, "eos", True)


def config():
    return dict(max_attempts=3, max_new_tokens=1024, context_limit=16384, prompt_variant="zero_shot",
                few_shot_k=0, seed=42, code_identity="fixture")


def test_attempt_budget_and_resume_no_regenerate_completed(tmp_path):
    from src.task3.r15_abc_experiment import run_arm
    backend = Backend("malformed")
    first = run_arm([record()], "A", config(), tmp_path, examples=[], adapter=None, backend=backend)
    assert first["unresolved"] == ["fixture"] and backend.calls == 3
    run_arm([record()], "A", config(), tmp_path, examples=[], adapter=None, backend=backend)
    assert backend.calls == 3
    successful = tmp_path / "success"
    backend = Backend()
    run_arm([record()], "A", config(), successful, examples=[], adapter=None, backend=backend)
    run_arm([record()], "A", config(), successful, examples=[], adapter=None, backend=backend)
    assert backend.calls == 1


def test_terminal_runtime_error_not_retried_on_resume(tmp_path):
    from src.task3.r15_abc_experiment import run_arm
    backend = Backend("runtime")
    run_arm([record()], "A", config(), tmp_path, examples=[], adapter=None, backend=backend)
    run_arm([record()], "A", config(), tmp_path, examples=[], adapter=None, backend=backend)
    assert backend.calls == 1


def test_missing_output_not_exported_as_clean(tmp_path):
    from src.task3.r15_abc_experiment import run_arm
    r = run_arm([record()], "A", config(), tmp_path, examples=[], adapter=None, backend=Backend("malformed"))
    assert r["predictions"] == []
    assert not (tmp_path / "predictions.json").exists()
    assert (tmp_path / "partial.predictions.json").exists()


def test_bank_hash_drift_blocks_resume(tmp_path):
    from src.task3.r15_abc_experiment import run_arm
    run_arm([record()], "B", config(), tmp_path, examples=bank(), adapter=None, backend=Backend())
    changed = bank()
    changed[0]["output"]["feedback"] = "Changed bank"
    with pytest.raises(ValueError, match="identity"):
        run_arm([record()], "B", config(), tmp_path, examples=changed, adapter=None, backend=Backend())


def test_bank_level_matches_query():
    from src.task3.r15_abc_experiment import arm_messages
    from src.task3.round15 import build_messages
    assert arm_messages(record(1), "B", bank()) == build_messages(record(1), [])


def test_context_drops_whole_example_not_query():
    from src.task3.r15_abc_experiment import arm_messages
    from src.task3.round15 import fitted_messages, build_messages
    from src.task3.inference import MockTokenizer
    tokenizer = MockTokenizer()
    length = len(tokenizer.apply_chat_template(build_messages(record(), []), tokenize=True, add_generation_prompt=True))
    messages, info = fitted_messages(record(), bank(), tokenizer, dict(context_limit=length+10, max_new_tokens=10, few_shot_k=2))
    assert info["examples_used"] == 0 and info["examples_dropped"] == 1
    assert messages[-1] == build_messages(record(), [])[-1]


def test_duplicate_missing_extra_block_complete_export():
    from src.task3.r15_abc_experiment import validate_export
    pred = {"sample_id": "x", "output": {"taxonomy_error": [], "feedback": "Cần xem lại."}}
    assert validate_export([pred, pred], {"x": 2})["valid"] is False
    assert validate_export([], {"x": 2})["valid"] is False
    assert validate_export([pred], {"y": 2})["valid"] is False


def test_same_ids_but_distinct_levels_preserved():
    from src.task3.r15_abc_experiment import validate_export
    p = lambda sid: {"sample_id": sid, "output": {"taxonomy_error": [], "feedback": "Cần xem lại."}}
    assert validate_export([p("x@L1"), p("x@L2")], {"x@L1": 1, "x@L2": 2})["valid"] is True


def test_root_predictions_untouched(tmp_path):
    from src.task3.r15_abc_experiment import run_arm
    root = tmp_path / "predictions.json"
    root.write_bytes(b"protected")
    run_arm([record()], "A", config(), tmp_path / "A", examples=[], adapter=None, backend=Backend())
    assert root.read_bytes() == b"protected"


def test_cached_a_not_counted_as_fresh_cost(tmp_path):
    from src.task3.r15_abc_experiment import phase_costs, write_json
    write_json(tmp_path / "result.json", {"source": "historical_replay", "historical_cost": {"attempts": 361}})
    (tmp_path / "attempts.jsonl").write_text('{"input_tokens":100,"output_tokens":30,"latency_s":1}\n')
    cost = phase_costs(tmp_path)
    assert cost["fresh_generations"] == 0
    assert cost["fresh_input_tokens"] == 0
    assert cost["historical_cost"]["attempts"] == 361


def test_resume_costs_keep_all_spent_attempts(tmp_path):
    from src.task3.r15_abc_experiment import phase_costs, write_json
    write_json(tmp_path / "result.json", {"source": "fresh_or_exact_resume", "fresh_calls_this_invocation": 0})
    p = tmp_path / "requests/x/attempts.jsonl"
    p.parent.mkdir(parents=True)
    p.write_text('{"input_tokens":100,"output_tokens":30,"latency_s":1}\n' * 2)
    cost = phase_costs(tmp_path)
    assert cost["fresh_generations"] == 2
    assert cost["fresh_output_tokens"] == 60


def test_reordered_ids_block_complete_export():
    from src.task3.r15_abc_experiment import validate_export
    p = lambda sid: {"sample_id": sid, "output": {"taxonomy_error": [], "feedback": "Cần xem lại."}}
    assert validate_export([p("b"), p("a")], {"a": 1, "b": 2})["valid"] is False


def test_cli_entrypoint_runs_without_model_access():
    import subprocess
    import sys
    path = Path(__file__).resolve().parents[1] / "scripts/task3_r15_abc.py"
    result = subprocess.run([sys.executable, str(path), "--help"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "select-checkpoint" in result.stdout
    assert "freeze-public" in result.stdout


def test_interrupted_generation_cannot_spend_an_unrecorded_retry(tmp_path):
    from src.task3.r15_abc_experiment import run_arm, phase_costs
    class Interrupted(Backend):
        def generate(self, messages, config):
            self.calls += 1
            if self.calls == 1:
                raise KeyboardInterrupt("simulated process interruption")
            from src.task3.inference import Generation
            return Generation("malformed", 3, .1, "eos", True)
    backend = Interrupted()
    with pytest.raises(KeyboardInterrupt):
        run_arm([record()], "A", config(), tmp_path, examples=[], adapter=None, backend=backend)
    result = run_arm([record()], "A", config(), tmp_path, examples=[], adapter=None, backend=backend)
    assert backend.calls == 1
    assert result["unresolved"] == ["fixture"]
    costs = phase_costs(tmp_path)
    assert costs["fresh_generations"] == 1 and costs["unknown_output_token_calls"] == 1


def test_one_overlong_query_does_not_prevent_other_requests(tmp_path):
    from dataclasses import replace
    from src.task3.r15_abc_experiment import preflight_records, run_arm
    backend = Backend()
    records = [replace(record(sid="long"), code="int huge;" * 4000), record(sid="short")]
    budget = preflight_records(records, "A", [], backend.tokenizer, config())
    assert budget[0]["status"] == "query_over_context" and budget[1]["status"] == "ready"
    result = run_arm(records, "A", config(), tmp_path, examples=[], adapter=None, backend=backend)
    assert [p["sample_id"] for p in result["predictions"]] == ["short"]
    assert result["unresolved"] == ["long"]
    assert backend.calls == 1


def test_public_source_drift_after_fingerprint_screen_is_rejected(tmp_path):
    from dataclasses import replace
    import hashlib
    from src.task3.r15_abc_experiment import require_public_sources
    from src.task3.direct_sft_data import signature
    source = record()
    path = tmp_path / "source.cpp"
    path.write_text(source.code)
    source = replace(source, code_path=str(path))
    sig = signature(dict(sample_id=source.sample_id, family="fixture", code=source.code,
                         source_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    require_public_sources([source], [sig])
    path.write_text("int main(){return 99;}")
    with pytest.raises(ValueError, match="public source"):
        require_public_sources([replace(source, code=path.read_text())], [sig])


def test_downstream_checkpoint_cannot_bypass_semantic_selection():
    from src.task3.r15_abc_experiment import require_selected_checkpoint
    require_selected_checkpoint("public", "selected", "half")
    require_selected_checkpoint("checkpoint-dev", "final", "half")
    with pytest.raises(ValueError, match="selected"):
        require_selected_checkpoint("public", "final", "half")
    with pytest.raises(ValueError, match="selected"):
        require_selected_checkpoint("comparison-dev", "final", "half")


def test_offline_dependency_check_rehashes_selected_adapter(tmp_path):
    from src.task3.r15_abc_experiment import verify_selected_adapter, adapter_identity, write_json
    adapter = tmp_path / "C/training/half/adapter"
    adapter.mkdir(parents=True)
    (adapter / "adapter_config.json").write_text('{}')
    (adapter / "adapter_model.safetensors").write_bytes(b"tensor")
    choice = dict(name="half", step=1, adapter_path=str(adapter), adapter_identity=adapter_identity(adapter))
    write_json(tmp_path / "C/training/training-result.json", {"status": "complete", "checkpoints": [choice]})
    write_json(tmp_path / "checkpoint-selection.json", {"selected": "half", "step": 1, "candidates": [choice]})
    assert verify_selected_adapter(tmp_path)["name"] == "half"
    (adapter / "adapter_model.safetensors").write_bytes(b"changed")
    with pytest.raises(ValueError, match="adapter"):
        verify_selected_adapter(tmp_path)
