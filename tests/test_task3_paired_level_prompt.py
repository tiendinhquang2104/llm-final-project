from types import SimpleNamespace
import pytest
from src.task3 import paired_level_prompt as p,round15,round15_runner


def test_level_frame_preserves_full_payload_and_retry():
    for level in (1,2,3,4):
        r=SimpleNamespace(statement='s',problems=[],grading_policy=None,code='int f(){return 1;}',target_feedback_level=f'Level {level}',provenance={})
        base=round15.build_messages(r,[],retry='schema');new=p.messages(r,[],retry='schema')
        assert new[1:]==base[1:]
        assert new[0]['content']==base[0]['content']+p.FRAMES[level]
    assert p.FRAMES[4]==''


def test_frame_patch_restores_controller():
    original=round15_runner.fitted_messages
    with pytest.raises(ValueError):
        with p.adapter():raise ValueError('bad context')
    assert round15_runner.fitted_messages is original
