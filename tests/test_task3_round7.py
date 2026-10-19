"""R7 mechanical contracts; scripted text is not a semantic model evaluation."""
import json

import pytest

from src.task3.cli import select_sample_records
from src.task3.compliance import check
from src.task3.generation_audit import inspect_generation
from src.task3.inference import Generation, MockBackend
from src.task3.pipeline import infer
from src.task3.prompts import build_messages
from src.task3.quality_review import quality_review_flags
from src.task3.strategy import build_plan_messages, validate_plan_text
from tests.test_task3_dataset import record


@pytest.mark.parametrize('text', ['Tốt, nhưng em in thừa dấu cách.', 'Em thiếu dấu chấm phẩy.', 'Đầu ra bị sai định dạng.'])
def test_v2_guard_rejects_overt_level1_disclosures(text):
    assert not check(text, 1, version=2).ok


@pytest.mark.parametrize('text', ['Cảm ơn em đã cố gắng. Em hãy tiếp tục luyện tập nhé.', 'Em cứ bình tĩnh và đọc kỹ yêu cầu bài nhé.', 'Chúc em giữ vững tinh thần học tập!'])
def test_v2_guard_keeps_harmless_encouragement(text):
    assert check(text, 1, version=2).ok


def test_guard_default_preserves_archived_verdict():
    text = 'Tốt, nhưng em in thừa dấu cách.'
    assert check(text, 1).ok
    assert not check(text, 1, version=2).ok


def test_praise_with_empty_taxonomy_remains_only_a_review_candidate():
    r = record(target_feedback_level='Level 1 - Gợi ý nhẹ', gold_taxonomy=[])
    flags = quality_review_flags(r, 'Tốt.', version=2)
    assert 'LEVEL1_UNSUPPORTED_PRAISE_REVIEW_CANDIDATE' in flags['flags']
    assert flags['semantic_quality'] == 'NOT_MEASURED'
    assert check('Tốt.', 1, version=2).ok


def test_level3_diagnosis_without_direction_is_a_candidate_not_a_grade():
    r = record(target_feedback_level='Level 3 - Gợi ý sửa')
    flags = quality_review_flags(r, 'Biến dùng trong điều kiện vòng lặp chưa được khai báo.', version=2)
    assert 'LEVEL3_ACTIONABILITY_REVIEW_CANDIDATE' in flags['flags']
    assert flags['semantic_quality'] == 'NOT_MEASURED'
    good = quality_review_flags(r, 'Biến chưa được khai báo. Hãy dùng biến đếm chữ số đã được tính trước vòng lặp.', version=2)
    assert 'LEVEL3_ACTIONABILITY_REVIEW_CANDIDATE' not in good['flags']


def test_r7_prompt_filters_cross_level_definitions_without_removing_source():
    r = record(target_feedback_level='Level 1 - Gợi ý nhẹ', level_definitions=[{'level': 'Level 1 - Gợi ý nhẹ', 'description': 'động viên'}, {'level': 'Level 4 - Lời giải mẫu', 'description': 'viết code'}])
    messages = build_messages(r, r.gold_taxonomy, prompt_policy_version=3)
    assert r.code in json.loads(messages[-1]['content'].split('UNTRUSTED_SUBMISSION_JSON\n')[1].split('\nEND_SUBMISSION_JSON')[0])['student_code']
    assert 'Level 1:' in messages[0]['content']
    assert 'Level 4' not in json.dumps(messages, ensure_ascii=False)


def test_v4_plan_keeps_uncertain_empty_and_has_a_distinct_prompt():
    r = record(problems=[{'pid': 'P1'}])
    messages = build_plan_messages(r, r.gold_taxonomy, compact_v3=True, substantive_v4=True)
    assert messages != build_plan_messages(r, r.gold_taxonomy, compact_v3=True)
    assert validate_plan_text('{"status":"uncertain","findings":[]}', r, compact_v3=True) == {'status': 'uncertain', 'findings': []}


def test_truncated_level4_output_is_retained_retried_and_not_model_complete():
    class Clipped(MockBackend):
        def generate(self, messages, config):
            return Generation('```cpp\nint main(){', 512, .1)

    r = record(target_feedback_level='Level 4 - Lời giải mẫu')
    _, traces = infer([r], Clipped(), {'context_limit': 10000, 'guard_policy_version': 2, 'completion_policy_version': 1, 'retry_policy_version': 3, 'max_retries': 1})
    trace = traces[0]
    assert trace['fallback_reason'] == 'feedback_incomplete'
    assert trace['model_response_complete'] is False
    assert len([a for a in trace['attempts'] if a.get('model_generated')]) == 2
    assert trace['attempts'][0]['raw_text'] == '```cpp\nint main(){'
    assert trace['attempts'][0]['generation_audit']['token_cap_reached'] is True
    assert 'unclosed_code_fence' in trace['attempts'][0]['generation_audit']['signals']


def test_closed_eos_feedback_rescues_truncation_without_becoming_disclosure_rescue():
    class Rescue(MockBackend):
        calls = 0

        def generate(self, messages, config):
            self.calls += 1
            if self.calls == 1:
                return Generation('```cpp\nint main(){', 512, .1)
            return Generation('Đoạn sửa tập trung:\n```cpp\nreturn 0;\n```', 18, .1, finish_reason='eos', eos_reached=True)

    _, traces = infer([record(target_feedback_level='Level 4 - Lời giải mẫu')], Rescue(), {'context_limit': 10000, 'guard_policy_version': 2, 'completion_policy_version': 1, 'retry_policy_version': 3})
    assert not traces[0]['fallback_used']
    assert traces[0]['model_response_complete'] is True
    assert traces[0]['raw_first_attempt_compliance'] is True
    assert traces[0]['completion_retry_rescued'] is True


def test_direction_retry_is_labeled_candidate_and_k_is_per_attempt():
    class DirectionBackend(MockBackend):
        calls = 0

        def generate(self, messages, config):
            self.calls += 1
            text = 'Biến trong điều kiện chưa khai báo.' if self.calls == 1 else 'Biến trong điều kiện chưa khai báo. Hãy dùng biến đếm đã tính ở bước trước.'
            return Generation(text, 20, .1)

    cfg = {'context_limit': 10000, 'guard_policy_version': 2, 'adequacy_retry_policy_version': 1, 'retry_policy_version': 3, 'few_shot_k': 0}
    _, traces = infer([record(target_feedback_level='Level 3 - Gợi ý sửa')], DirectionBackend(), cfg)
    attempts = [a for a in traces[0]['attempts'] if a.get('model_generated')]
    assert attempts[0]['retry_reasons'] == ['level3_direction_candidate']
    assert all(a['examples_requested'] == a['effective_k'] == 0 for a in attempts)
    assert traces[0]['semantic_quality'] == 'NOT_MEASURED'


def test_declared_pilot_ids_preserve_prepared_order_and_reject_unknowns(tmp_path):
    records = [record(sample_id='one'), record(sample_id='two'), record(sample_id='three')]
    path = tmp_path / 'ids.json'
    path.write_text('["one", "three"]')
    assert [r.sample_id for r in select_sample_records(records, path)] == ['one', 'three']
    path.write_text('["three", "one"]')
    with pytest.raises(ValueError, match='order'):
        select_sample_records(records, path)
    path.write_text('["unknown"]')
    with pytest.raises(ValueError, match='missing'):
        select_sample_records(records, path)


def test_observed_eos_at_exact_cap_is_separate_from_clipping():
    audit = inspect_generation('Nhận xét đã kết thúc.', output_tokens=512, max_new_tokens=512, finish_reason='eos', eos_reached=True)
    assert audit['token_cap_reached'] is True
    assert audit['mechanically_complete'] is True


def test_v4_nonempty_plan_is_visible_in_trace_but_isolated_from_level1():
    class Backend(MockBackend):
        calls = []

        def generate(self, messages, config):
            self.calls.append(messages)
            if len(self.calls) == 1:
                return Generation('{"status":"faulty","findings":[{"problem_id":"P1","source_field":"student_code","quote":"return 2;","diagnosis":"Một giả thuyết cần kiểm chứng"}]}', 60, .1)
            return Generation('Cảm ơn em đã cố gắng, hãy tiếp tục luyện tập nhé.', 18, .1)

    backend = Backend()
    r = record(code='int f(){return 2;}', problems=[{'pid': 'P1'}], target_feedback_level='Level 1 - Gợi ý nhẹ')
    _, traces = infer([r], backend, {'context_limit': 12000, 'prompt_strategy': 'structured_cot', 'cot_quality_version': 4, 'prompt_policy_version': 3, 'guard_policy_version': 2})
    assert traces[0]['cot_plan_audit']['finding_count'] == 1
    assert 'Một giả thuyết cần kiểm chứng' not in json.dumps(backend.calls[-1], ensure_ascii=False)
    assert not traces[0]['fallback']


def test_r7_resume_invalidates_when_validator_implementation_changes(tmp_path, monkeypatch):
    from src.task3 import pipeline

    class Backend(MockBackend):
        def __init__(self, text):
            self.text = text

        def generate(self, messages, config):
            return Generation(self.text, 10, .1)

    cfg = {'context_limit': 10000, 'guard_policy_version': 2}
    progress = tmp_path / 'progress.jsonl'
    monkeypatch.setattr(pipeline, 'implementation_digest', lambda: 'a' * 64)
    first, _ = infer([record()], Backend('Điều kiện vòng lặp chưa khớp yêu cầu.'), cfg, progress_path=progress)
    monkeypatch.setattr(pipeline, 'implementation_digest', lambda: 'b' * 64)
    second, _ = infer([record()], Backend('Biến trong điều kiện chưa có khai báo.'), cfg, progress_path=progress, resume=True)
    assert second != first

@pytest.mark.parametrize('text', ['~~~cpp\nint f(){return 0;\n~~~', '```cpp\nint f(){return 0;}\n~~~'])
def test_completion_handles_tilde_braces_and_mismatched_fences(text):
    audit = inspect_generation(text, output_tokens=30, max_new_tokens=512, finish_reason='eos', eos_reached=True)
    assert not audit['mechanically_complete']


def test_reevaluation_uses_manifest_guard_and_rejects_conflict():
    from src.task3.evaluator import evaluate
    r = record(target_feedback_level='Level 1 - Gợi ý nhẹ')
    predictions = [{'sample_id': r.sample_id, 'output': {'feedback': 'Tốt, nhưng em in thừa dấu cách.', 'taxonomy_error': r.gold_taxonomy}}]
    manifest = {'config': {'guard_policy_version': 2}}
    result = evaluate([r], predictions, run_manifest=manifest)
    assert result['guard_policy_version'] == 2
    assert result['compliance'] == 0
    with pytest.raises(ValueError, match='guard policy'):
        evaluate([r], predictions, traces=[{'sample_id': r.sample_id, 'guard_policy_version': 1}], run_manifest=manifest)
