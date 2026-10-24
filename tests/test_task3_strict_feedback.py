"""Synthetic contract tests, not measurements of model diagnostic accuracy."""
import copy
import json

import pytest

from src.task3 import arm_d_plus as plus
from tests.test_task3_arm_d_plus import Backend, LABELS, SPACE, config, finding, unit


def encoded(f):
    return json.dumps({'findings': [f]})


@pytest.mark.parametrize('error', [
    'Implementation behavior violating a requirement, with relevant condition',
    '  IMPLEMENTATION behavior violating a requirement, with relevant condition.  ',
])
def test_schema_description_is_not_a_diagnosis(error):
    with pytest.raises(ValueError, match='placeholder'):
        plus.parse_findings(encoded({**finding(), 'error': error}))


@pytest.mark.parametrize('field,value,reason', [
    ('problem_id', 'P99', 'problem_id'),
    ('evidence', 'i += 1;', 'verbatim'),
    ('evidence', 'i ... 0;', 'verbatim'),
])
def test_findings_bound_to_this_sample(field, value, reason):
    with pytest.raises(ValueError, match=reason):
        plus.parse_findings(encoded({**finding(), field: value}), unit())


def test_quote_may_come_from_real_diagnostics_or_be_empty_for_omission():
    u = unit()
    u['task']['compile_log'] = 'test.cpp:1: error: unknown name'
    for evidence in ('i += 0;', 'error: unknown name', ''):
        f = {**finding(), 'evidence': evidence}
        assert plus.parse_findings(encoded(f), u) == [f]


def test_contract_failure_retried_before_renderer_and_preserves_valid_diagnosis(tmp_path):
    bad = {**finding(), 'error': 'Implementation behavior violating a requirement, with relevant condition'}
    backend = Backend([encoded(bad), encoded(finding()), '{"feedback":"Vòng lặp không tiến triển."}'])
    rows = plus.run_units([unit()], backend, config(), tmp_path, SPACE)
    assert rows[0]['status'] == 'resolved'
    assert len(backend.calls) == 3
    correction = json.loads(backend.calls[1][-1]['content'])
    assert correction['failure_kind'] == 'content_contract'
    assert 'placeholder' in correction['failure']
    renderer = json.loads(backend.calls[-1][1]['content'])
    assert renderer['findings'][0]['error'] == finding()['error']


def test_invalid_finding_never_becomes_clean_or_reaches_renderer(tmp_path):
    raw = encoded({**finding(), 'evidence': 'invented code; ‘quote’'})
    backend = Backend([raw, raw])
    rows = plus.run_units([unit()], backend, config(), tmp_path, SPACE)
    assert rows[0]['status'] == 'unresolved'
    assert rows[0]['output'] is None and rows[0]['stage1'] is None
    assert rows[0]['failure']['category'] == 'content_contract'
    assert len(backend.calls) == 2
    assert not (tmp_path/'predictions.json').exists()


def test_syntax_repair_receives_exact_failure_and_raw_as_data(tmp_path):
    malformed = '{"findings":[{"evidence":"x";}]}'
    backend = Backend([malformed, '{"findings":[]}', '{"feedback":"Chưa thấy lỗi có căn cứ."}'])
    rows = plus.run_units([unit()], backend, config(), tmp_path, SPACE)
    assert rows[0]['status'] == 'resolved'
    repair = backend.calls[1]
    assert [m['role'] for m in repair] == ['system', 'user', 'user']
    data = json.loads(repair[-1]['content'])
    assert data['invalid_response'] == malformed
    assert data['failure_kind'] == 'schema'
    assert 'char' in data['failure'] and data['failure_context']


@pytest.mark.parametrize('has_findings', [False, True])
def test_level1_is_bounded_renderer_without_llm_call_or_leaking_details(tmp_path, has_findings):
    u = unit(); u['level'] = 1
    raw = encoded(finding()) if has_findings else '{"findings":[]}'
    backend = Backend([raw])
    rows = plus.run_units([u], backend, config(), tmp_path, SPACE)
    assert rows[0]['status'] == 'resolved'
    assert len(backend.calls) == 1
    assert rows[0]['renderer_mode'] == 'level1_template'
    assert rows[0]['output']['feedback'] == plus.LEVEL1_FEEDBACK[has_findings]
    assert rows[0]['output']['taxonomy_error'] == ([LABELS[3]] if has_findings else [])
    assert rows[0]['output']['feedback'] not in ('', 'Đúng hoàn toàn.')


def test_level1_prompt_has_no_source_or_diagnoses_even_when_called_directly():
    u = unit(); u['level'] = 1
    body = json.loads(plus.messages_feedback(u, [finding()], LABELS, SPACE['feedback_level'])[1]['content'])
    assert body['has_findings'] is True
    assert set(body) == {'requested_level', 'level_rule', 'guidance', 'has_findings'}


def test_level2_does_not_repeat_full_source_and_level3_keeps_repair_context():
    u = unit(); original = copy.deepcopy(u)
    body = json.loads(plus.messages_feedback(u, [finding()], LABELS, SPACE['feedback_level'])[1]['content'])
    assert body['findings'] == [finding()]
    assert 'code' not in body and 'statement' not in body and 'compile_log' not in body
    u['level'] = 3
    body = json.loads(plus.messages_feedback(u, [finding()], LABELS, SPACE['feedback_level'])[1]['content'])
    assert body['code'] == u['task']['code']
    assert body['problems'] == u['task']['problems']
    assert original['task'] == u['task']


def test_completed_level1_checkpoint_cannot_bypass_renderer_contract(tmp_path):
    u = unit(); u['level'] = 1
    plus.run_units([u], Backend(['{"findings":[]}']), config(), tmp_path, SPACE)
    path = tmp_path/'results.private.json'
    saved = json.loads(path.read_text())
    saved[0]['output']['feedback'] = 'Hãy đổi điều kiện trong hàm main.'
    path.write_text(json.dumps(saved))
    with pytest.raises(ValueError, match='Level1'):
        plus.run_units([u], Backend([]), config(), tmp_path, SPACE)
