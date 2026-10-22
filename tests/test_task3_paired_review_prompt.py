from types import SimpleNamespace
import pytest
from src.task3 import round15,round15_runner
from src.task3 import paired_review_prompt as p


def record(level):
    return SimpleNamespace(statement='Tính tổng',problems=[],grading_policy=None,code='int f(){return 0;}',target_feedback_level=f'Level {level}',provenance={})


def test_self_check_changes_only_system_instruction():
    for level in (1,2,3,4):
        r=record(level);base=round15.build_messages(r,[],retry='schema')
        result=p.messages(r,[],retry='schema')
        assert result[1:]==base[1:]
        assert result[0]['content']==base[0]['content']+p.INSTRUCTION
        assert 'taxonomy_error' in result[0]['content']


def test_prompt_patch_restores_after_runtime_failure():
    original=round15_runner.fitted_messages
    with pytest.raises(RuntimeError):
        with p.adapter():
            assert round15_runner.fitted_messages is not original
            raise RuntimeError('backend unavailable')
    assert round15_runner.fitted_messages is original
