"""Transport and log-only evidence projection boundary regressions."""
import copy
import hashlib
import importlib
import json
from pathlib import Path

import pytest

from src.task3 import arm_d_plus_v15 as v15
from src.task3 import source_refs as refs
from tests.test_task3_arm_d_plus import LABELS, unit


def transport():
    return importlib.import_module('src.task3.json_transport')


def diagnostic():
    return importlib.import_module('src.task3.diagnostic_view')


class CharacterTokenizer:
    """Exact, deterministic token budget independent of model downloads."""
    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        rendered = ''.join(m['role'] + ':' + m['content'] + '\n' for m in messages)
        return list(rendered) if tokenize else rendered


def enriched(provided=None, local=None):
    u = unit()
    u['task']['code'] = 'int main() {\n  int n = 1\n  return n;\n}\n'
    u['task']['statement'] = 'Return the positive input unchanged.\nNo optional requirements.'
    u['task']['input_metadata'] = {'valid_input_domain': '1 <= n <= 9'}
    u['task']['compile_log'] = provided
    u['source_catalog'] = refs.build_catalog(u['task']['code'], provided_compile_log=provided,
                                           local_compile_log=local)
    u['source_map_version'] = refs.VERSION
    u['local_compiler'] = {'status': 'compile_error', 'returncode': 1, 'standard': 'c++11',
                           'program_executed': False, 'diagnostic_source_id': 'local_compile_log',
                           'toolchain_fingerprint': 'toolchain-sha', 'capture_complete': True,
                           'diagnostic_truncated': False}
    return u


def finding(source='code', start=2, end=2):
    return dict(problem_id='P1', kind='defect', location='main declaration',
                error='The declaration lacks its terminating semicolon.', labels=['Lỗi biên dịch'],
                evidence_refs=[dict(source=source, start_line=start, end_line=end)])


def scattered_log():
    lines = [f'/usr/include/template.h:{i}: note: repetitive overload candidate ' + 'x' * 130 + '\n'
             for i in range(1, 121)]
    for start, line in [(2, 2), (60, 3), (117, 4)]:
        lines[start - 1] = f'student.cpp:{line}:3: error: root failure at {line}\n'
        lines[start] = f' {line:3} | int n = 1\n'
        lines[start + 1] = '     |          ^\n'
    return ''.join(lines)


@pytest.mark.parametrize('opening', ['```json', '```JSON', '```JsOn', '```'])
def test_single_fence_preserves_exact_crlf_unicode_payload(opening):
    body = ' {\r\n "feedback": "em nói \\"đúng\\" và ``` nguyên văn"\r\n}\r\n'
    raw = '\t\r\n ' + opening + '\r\n' + body + '```\r\n\t '
    payload, audit = transport().normalize(raw)
    assert payload == body
    assert v15.json_object(payload)['feedback'] == 'em nói "đúng" và ``` nguyên văn'
    assert audit['raw_sha256'] == hashlib.sha256(raw.encode()).hexdigest()
    assert audit['payload_sha256'] == hashlib.sha256(body.encode()).hexdigest()
    assert audit['transport_mode'] == 'fenced_json'
    assert audit['normalization_action'] and audit['parser_version']


def test_plain_json_retains_outer_whitespace():
    raw = '\r\n  {"findings": []} \t\n'
    payload, audit = transport().normalize(raw)
    assert payload == raw and v15.json_object(payload) == {'findings': []}
    assert audit['transport_mode'] == 'json_document'


@pytest.mark.parametrize('raw', [
    '```python\n{}\n```', '```json\n{}', '```json {}\n```',
    '```json \n{}\n```', '```json\n{}\n```\n```json\n{}\n```',
    'Here is the JSON:\n```json\n{}\n```', '```json\n{}\n```\nDone.',
    '````json\n{}\n````', '```json\n{}\n``` trailing', '',
])
def test_invalid_envelope_rejected_as_transport(raw):
    with pytest.raises(ValueError) as exc:
        transport().normalize(raw)
    assert exc.value.category == 'transport'


@pytest.mark.parametrize('raw', [
    '{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{} {}', '{} trailing',
    '[]', 'null', '{/* comment */"x":1}', '{"x":',
])
def test_transport_cannot_make_invalid_json_valid(raw):
    for wrapped in (raw, '```json\n' + raw + '\n```'):
        with pytest.raises(ValueError):
            v15.json_object(transport().normalize(wrapped)[0])


@pytest.mark.parametrize('reason', ['length', 'timeout', 'stop', None, 'constrained_choice'])
def test_non_eos_parseable_json_is_generation_failure(reason):
    with pytest.raises(ValueError) as exc:
        transport().generation_text({'raw_text': '{"findings":[]}', 'finish_reason': reason})
    assert exc.value.category == 'generation_termination'


def test_backend_error_keeps_infrastructure_category_and_eos_returns_raw():
    with pytest.raises(ValueError) as exc:
        transport().generation_text({'raw_text': '{}', 'finish_reason': 'eos', 'error': 'CUDA failed'})
    assert exc.value.category == 'infrastructure'
    assert transport().generation_text({'raw_text': '```json\n{}\n```', 'finish_reason': 'eos'}) == '```json\n{}\n```'


def test_any_invalid_finding_rejects_whole_response_and_kind_is_not_label():
    u = enriched()
    bad = dict(finding(), kind='logic')
    raw = '```json\n' + json.dumps({'findings': [finding(), bad]}) + '\n```'
    with pytest.raises(v15.ValidationFailure) as exc:
        v15.parse_findings(transport().normalize(raw)[0], u)
    assert exc.value.details['field_path'] == 'findings[1].kind'
    assert exc.value.details['offending_value'] == 'logic'
    other = dict(finding(), labels=['unresolved label'])
    assert v15.parse_findings(transport().normalize(json.dumps({'findings': [other]}))[0], u) == [other]


def test_historical_fence_failure_recovered_without_changing_source_quote():
    u = enriched()
    raw = '```json\n' + json.dumps({'findings': [finding()]}) + '\n```'
    with pytest.raises(json.JSONDecodeError) as exc:
        v15.parse_findings(raw, u)
    assert exc.value.pos == 0
    normalized = v15.extract_findings(v15.parse_findings(transport().normalize(raw)[0], u), u)
    assert normalized[0]['evidence_spans'][0]['text'] == '  int n = 1\n'
    assert ';' not in normalized[0]['evidence_spans'][0]['text']


def test_fitting_prompt_is_byte_unchanged_and_full_refs_remain_valid():
    u = enriched('student.cpp:2:3: error: expected semicolon\n', None)
    messages = v15.messages_findings(u, LABELS)
    original = copy.deepcopy(messages)
    projected, audit = diagnostic().prepare_messages(u, messages, CharacterTokenizer(), 100, 20000)
    assert projected == original and messages == original
    assert audit['selection_applied'] is False
    assert audit['sources']['provided_compile_log']['presented_ranges'] == [[1, 1]]
    assert audit['sources']['provided_compile_log']['omitted_ranges'] == []
    diagnostic().validate_presented_refs([finding('provided_compile_log', 1, 1)], audit, u)


def test_oversize_view_preserves_full_code_requirements_and_scattered_primaries():
    u = enriched(scattered_log(), scattered_log().replace('student.cpp', '<stdin>'))
    original = copy.deepcopy(u)
    messages = v15.messages_findings(u, LABELS)
    projected, audit = diagnostic().prepare_messages(u, messages, CharacterTokenizer(), 300, 16000)
    assert u == original
    before, after = json.loads(messages[1]['content']), json.loads(projected[1]['content'])
    for field in ('statement', 'problems', 'problem_ids', 'input_metadata', 'sources'):
        if field != 'sources':
            assert after[field] == before[field]
    assert after['sources']['code'] == before['sources']['code']
    assert projected[0] == messages[0]
    assert audit['selection_applied'] is True
    assert audit['incomplete_diagnostic_coverage'] is False
    assert audit['local_compiler']['toolchain_fingerprint'] == 'toolchain-sha'
    assert audit['token_accounting']['presented_prompt_tokens'] + 300 <= 16000
    assert audit['token_accounting']['correction_reserve_tokens'] > 0
    assert 'selected diagnostic view' in after['diagnostic_view']['notice'].lower()
    for source in ('provided_compile_log', 'local_compile_log'):
        presented = after['sources'][source]['numbered_text']
        assert '2 | ' in presented and '60 | ' in presented and '117 | ' in presented
        assert '3 |    2 | int n = 1\n' in presented
        assert '4 |      |          ^\n' in presented
        assert audit['sources'][source]['primary_presented_count'] == 3
        assert audit['sources'][source]['omitted_line_count'] > 0
        assert audit['sources'][source]['sha256'] == refs.source_sha(u['source_catalog'][source]['text'])
        diagnostic().validate_presented_refs([finding(source, 117, 119)], audit, u)
        with pytest.raises(refs.ReferenceFailure):
            diagnostic().validate_presented_refs([finding(source, 20, 20)], audit, u)
        with pytest.raises(refs.ReferenceFailure):
            diagnostic().validate_presented_refs([finding(source, 2, 60)], audit, u)
    diagnostic().validate_presented_refs([finding('code', 1, 4)], audit, u)


def test_insufficient_primary_budget_discloses_incomplete_coverage():
    log = ''.join(f'student.cpp:{i}:1: error: ' + 'x' * 450 + '\n' for i in range(1, 45))
    u = enriched(log)
    projected, audit = diagnostic().prepare_messages(u, v15.messages_findings(u, LABELS),
                                                    CharacterTokenizer(), 300, 7500)
    assert audit['incomplete_diagnostic_coverage'] is True
    counts = audit['sources']['provided_compile_log']
    assert 0 < counts['primary_presented_count'] < counts['primary_total_count'] == 44
    assert any(start > 20 for start, end in counts['presented_ranges'])
    assert len(CharacterTokenizer().apply_chat_template(projected, tokenize=True,
                                                       add_generation_prompt=True)) + 300 <= 7500


def test_source_and_requirements_overflow_is_explicit_context_failure():
    u = enriched(scattered_log())
    u['task']['statement'] = 'requirements must be preserved ' * 1000
    with pytest.raises(ValueError) as exc:
        diagnostic().prepare_messages(u, v15.messages_findings(u, LABELS), CharacterTokenizer(), 300, 7000)
    assert exc.value.category == 'context'


def test_audit_drift_and_invalid_code_coordinates_rejected():
    u = enriched(scattered_log())
    _, audit = diagnostic().prepare_messages(u, v15.messages_findings(u, LABELS), CharacterTokenizer(), 300, 10000)
    with pytest.raises(refs.ReferenceFailure):
        diagnostic().validate_presented_refs([finding('code', 99, 99)], audit, u)
    tampered = copy.deepcopy(audit)
    tampered['sources']['provided_compile_log']['sha256'] = 'changed'
    with pytest.raises(ValueError):
        diagnostic().validate_presented_refs([finding('provided_compile_log', 2, 2)], tampered, u)


@pytest.mark.parametrize('reason', ['backend_failure', 'runtime_error'])
def test_backend_failure_finish_reason_is_infrastructure_even_without_error_text(reason):
    with pytest.raises(ValueError) as exc:
        transport().generation_text({'finish_reason': reason, 'raw_text': None})
    assert exc.value.category == 'infrastructure'


def test_real_archived_response_preserves_original_raw_payload_and_evidence():
    root = Path('outputs/task3/v1.5-observation-20261024/internal')
    if not (root / 'attempts.jsonl').exists():
        pytest.skip('private historical artifacts are unavailable')
    row = json.loads((root / 'attempts.jsonl').read_text().splitlines()[0])
    units = json.loads((root / 'enriched-inputs.private.json').read_text())['units']
    u = next(u for u in units if u['sample_id'] == row['sample_id'])
    raw = transport().generation_text(row)
    with pytest.raises(json.JSONDecodeError) as exc:
        v15.parse_findings(raw, u)
    assert exc.value.pos == 0
    payload, audit = transport().normalize(raw)
    assert payload == ''.join(raw.strip().splitlines(keepends=True)[1:-1])
    parsed = v15.parse_findings(payload, u)
    normalized = v15.extract_findings(parsed, u)
    assert audit['raw_sha256'] == hashlib.sha256(row['raw_text'].encode()).hexdigest()
    for f in normalized:
        for span in f['evidence_spans']:
            source = u['source_catalog'][span['source']]['text'].splitlines(keepends=True)
            assert span['text'] == ''.join(source[span['start_line'] - 1:span['end_line']])


def test_oversize_resolver_nested_task_uses_same_view_without_changing_finding():
    u = enriched(scattered_log(), scattered_log().replace('student.cpp', '<stdin>'))
    messages = v15.messages_resolver(u, finding(), 'unknown original label', LABELS)
    before = json.loads(messages[1]['content'])
    projected, audit = diagnostic().prepare_messages(u, messages, CharacterTokenizer(), 1, 16000)
    after = json.loads(projected[1]['content'])
    assert audit['selection_applied'] is True
    assert after['finding'] == before['finding']
    assert after['original_label'] == before['original_label']
    assert after['choices'] == before['choices']
    assert after['task']['sources']['code'] == before['task']['sources']['code']
    assert after['task']['statement'] == before['task']['statement']
    assert after['task']['local_compiler']['status'] == 'compile_error'
    assert after['task']['local_compiler']['toolchain_fingerprint'] == 'toolchain-sha'
    assert after['task']['diagnostic_view']['incomplete_diagnostic_coverage'] is False
    assert audit['token_accounting']['presented_prompt_tokens'] + 1 <= 16000
