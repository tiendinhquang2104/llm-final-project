import pytest
from src.task3.sft_v4 import EvaluationJournal
from scripts.task3_sft_v4_verify import validate_durable_rows


def test_jointly_edited_review_and_generation_cannot_override_journal(tmp_path):
    j = EvaluationJournal(tmp_path / 'journal', {'test/base': ['s-L1']})
    j.reserve('test/base/s-L1')
    original = dict(example_id='s-L1', sample_id='s', level=1, raw='original')
    j.append(dict(type='generation_completed', key='test/base/s-L1', result=original))
    examples = [dict(example_id='s-L1', sample_id='s', level=1)]
    validate_durable_rows([dict(original, utc='saved')], examples, j, 'test/base')
    with pytest.raises(ValueError, match='journal'):
        validate_durable_rows([dict(original, raw='edited', utc='saved')], examples, j, 'test/base')
