"""Offline experiment safeguards; scripted generations are TEST ONLY."""
import copy
import importlib
import importlib.util
import json

import pytest

from src.task3.inference import Generation, MockTokenizer


def api():
    assert importlib.util.find_spec('src.task3.level_blind') is not None, 'isolated runner missing'
    return importlib.import_module('src.task3.level_blind')


def payload():
    return dict(statement='An existing problem mentions Level in its title.', problems=[],
                grading_policy='', code='int main() { return 0; }',
                compiler={'status': 'unknown', 'diagnostic': ''})


def unit():
    return dict(source_id='S', source_sha256='abc', query_ids={'1': 'Q1', '2': 'Q2', '3': 'Q3'}, payload=payload())


class Scripted:
    tokenizer = MockTokenizer()

    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def generate(self, messages, config):
        self.calls.append(copy.deepcopy(messages))
        text = next(self.responses)
        if isinstance(text, Exception):
            raise text
        return Generation(text, 8, 0.01, 'eos', True)


def test_one_taxonomy_call_reused_at_exact_three_ids(tmp_path):
    m = api()
    backend = Scripted(['{"taxonomy_error":["Lỗi logic"]}'])
    result = m.run_taxonomy([unit()], backend, {'context_limit': 20000, 'max_new_tokens': 100}, tmp_path)
    projected = m.project_taxonomy([unit()], result)
    assert len(backend.calls) == 1
    assert [x['sample_id'] for x in projected] == ['Q1', 'Q2', 'Q3']
    assert all(x['taxonomy_error'] == ['Lỗi logic'] for x in projected)
    assert 'requested_level' not in json.loads(backend.calls[0][1]['content'])


@pytest.mark.parametrize('text', ['broken', '{}', '{"taxonomy_error":null}',
    '{"taxonomy_error":["off_by_one"]}', '{"taxonomy_error":["Lỗi logic","Lỗi logic"]}',
    '{"taxonomy_error":[],"feedback":"text"}', '{"taxonomy_error":[],"taxonomy_error":["Lỗi logic"]}',
    '<think>hidden</think>{"taxonomy_error":[]}', '{"taxonomy_error":[]} trailing'])
def test_strict_schema_rejects_invalid(text):
    with pytest.raises(ValueError):
        api().parse_taxonomy(text)


def test_single_fenced_object_and_genuine_empty_are_valid():
    assert api().parse_taxonomy('```json\n{"taxonomy_error":[]}\n```') == []


def test_exhaustion_stays_invalid_not_empty(tmp_path):
    m = api()
    backend = Scripted(['broken', '{"taxonomy_error":["sub-label"]}'])
    rows = m.run_taxonomy([unit()], backend, {'context_limit': 20000, 'max_new_tokens': 100}, tmp_path)
    assert rows[0]['status'] == 'invalid' and rows[0]['taxonomy_error'] is None
    assert rows[0]['calls'] == 2 and len(backend.calls) == 2
    assert 'JSON/schema' in backend.calls[1][-1]['content']
    assert m.project_taxonomy([unit()], rows)[0]['taxonomy_error'] is None
    assert len((tmp_path / 'attempts.jsonl').read_text().splitlines()) == 2


def test_runtime_error_never_retried_or_treated_as_clean(tmp_path):
    backend = Scripted([RuntimeError('device failure')])
    rows = api().run_taxonomy([unit()], backend, {'context_limit': 20000, 'max_new_tokens': 100}, tmp_path)
    assert rows[0]['status'] == 'invalid' and rows[0]['taxonomy_error'] is None
    assert rows[0]['calls'] == 1


def test_valid_wrong_label_is_not_semantically_retried(tmp_path):
    backend = Scripted(['{"taxonomy_error":["Lỗi style"]}'])
    rows = api().run_taxonomy([unit()], backend, {'context_limit': 20000, 'max_new_tokens': 100}, tmp_path)
    assert rows[0]['calls'] == 1 and rows[0]['taxonomy_error'] == ['Lỗi style']


def test_payload_and_actual_render_never_include_annotations():
    m = api()
    u = unit()
    u.update(gold_taxonomy=['GOLD_SENTINEL'], gold_feedback='TEACHER_SENTINEL',
             prediction='PRIOR_SENTINEL', public_fields='PUBLIC_SENTINEL', split='SPLIT_SENTINEL',
             target_feedback_level='LEVEL_SENTINEL')
    messages = m.taxonomy_messages(u['payload'])
    rendered = MockTokenizer().apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    assert all(s not in rendered for s in ['GOLD_SENTINEL', 'TEACHER_SENTINEL', 'PRIOR_SENTINEL',
        'PUBLIC_SENTINEL', 'SPLIT_SENTINEL', 'LEVEL_SENTINEL'])
    assert json.loads(messages[1]['content']) == payload()  # natural occurrence of Level is permitted
    contaminated = payload() | {'target_feedback_level': 1}
    with pytest.raises(ValueError):
        m.taxonomy_messages(contaminated)


@pytest.mark.parametrize('corruption', ['duplicate_source', 'duplicate_query', 'wrong_source', 'wrong_hash', 'missing_level'])
def test_mapping_corruption_fails_before_any_calls(tmp_path, corruption):
    m = api()
    u = unit()
    rows = [dict(source_id='S', source_sha256='abc', status='valid', taxonomy_error=[])]
    units = [u]
    if corruption == 'duplicate_source':
        units.append(copy.deepcopy(u))
    elif corruption == 'duplicate_query':
        u['query_ids']['3'] = 'Q1'
    elif corruption == 'missing_level':
        del u['query_ids']['2']
    elif corruption == 'wrong_source':
        rows[0]['source_id'] = 'OTHER'
    else:
        rows[0]['source_sha256'] = 'DIFFERENT'
    with pytest.raises(ValueError):
        m.project_taxonomy(units, rows)


def test_cannot_repeat_official_run_in_same_directory(tmp_path):
    m = api()
    cfg = {'context_limit': 20000, 'max_new_tokens': 100}
    m.run_taxonomy([unit()], Scripted(['{"taxonomy_error":[]}']), cfg, tmp_path)
    second = Scripted([])
    with pytest.raises(ValueError):
        m.run_taxonomy([unit()], second, cfg, tmp_path)
    assert not second.calls


def test_gate_strict_improvement_and_fp_review_required():
    m = api()
    baseline = {'n': 20, 'invalid': 0, 'micro_f1': .3, 'exact': 3}
    candidate = baseline | {'micro_f1': .31}
    assert not m.numeric_gate(baseline, baseline)['passed']
    assert m.numeric_gate(baseline, candidate)['passed']
    assert not m.numeric_gate(baseline, candidate | {'invalid': 1})['passed']
    assert not m.numeric_gate(baseline, candidate | {'exact': 2})['passed']
