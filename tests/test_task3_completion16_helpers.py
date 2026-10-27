"""Recovery helpers: real ranges and finite logits, never guessed coordinates."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from src.task3 import diagnostic_view, source_refs as refs
from src.task3.level_blind import digest


def helpers():
    # Import here so RED reports missing implementation as individual failures.
    from src.task3 import finite_choice, recovery_candidates
    return finite_choice, recovery_candidates


class Tokenizer:
    all_special_ids = [0]
    unk_token_id = 0

    def __len__(self):
        return 128

    def encode(self, code, add_special_tokens=False):
        return [ord(code)]

    def decode(self, ids):
        return ''.join(chr(i) for i in ids)

    def apply_chat_template(self, messages, **kwargs):
        class Batch(dict):
            def to(self, device):
                return self
        return Batch(input_ids=torch.tensor([[3, 4, 5]]), attention_mask=torch.ones((1, 3)))


class LogitModel:
    device = torch.device('cpu')

    def __init__(self, scores):
        self.scores = scores
        self.calls = 0

    def __call__(self, **kwargs):
        assert kwargs['use_cache'] is False
        assert kwargs['logits_to_keep'] == 1
        self.calls += 1
        logits = torch.full((1, 1, 128), -100.0)
        logits[0, 0, ord('Z')] = 1000  # Disallowed global argmax must be ignored.
        for code, score in self.scores.items():
            logits[0, 0, ord(code)] = score
        return SimpleNamespace(logits=logits)


def test_finite_choice_selects_only_allowed_logits_and_keeps_none_value():
    finite, _ = helpers()
    model = LogitModel({'A': 2, 'B': 5, 'C': 8})
    backend = SimpleNamespace(torch=torch, model=model, tokenizer=Tokenizer())
    result = finite.select(backend, [{'role': 'user', 'content': 'choose'}],
                           {'A': 'defect', 'B': 'omission', 'C': None})
    assert result['code'] == 'C' and result['value'] is None
    assert result['scores'] == [2.0, 5.0, 8.0]
    assert result['token_ids'] == [65, 66, 67]
    assert result['forward_passes'] == model.calls == 1
    assert result['input_tokens'] == 3 and result['output_tokens'] == 0
    assert result['finish_reason'] == 'constrained_choice'
    assert 'not' in result['score_kind'] and result['latency_s'] >= 0


def test_finite_choice_tie_preserves_choice_order_and_exact_value():
    finite, _ = helpers()
    value = {'candidate_id': 'immutable'}
    backend = SimpleNamespace(torch=torch, model=LogitModel({'B': 2, 'A': 2}), tokenizer=Tokenizer())
    result = finite.select(backend, [], {'B': value, 'A': None})
    assert result['code'] == 'B' and result['value'] is value


@pytest.mark.parametrize('codes', [[], ['A'] * 2, ['R'], ['AA'], list('ABCDEFGHIJKLMNOPQR')])
def test_finite_choice_rejects_invalid_code_sets(codes):
    finite, _ = helpers()
    with pytest.raises((ValueError, RuntimeError)):
        finite.choice_token_ids(Tokenizer(), codes)


@pytest.mark.parametrize('bad', [[1, 2], [0], [-1], [128], [65]])
def test_finite_choice_rejects_invalid_or_colliding_real_tokenizations(bad):
    finite, _ = helpers()
    tok = Tokenizer()
    tok.encode = lambda code, add_special_tokens=False: [65] if code == 'A' else bad
    with pytest.raises((ValueError, RuntimeError)):
        finite.choice_token_ids(tok, ['A', 'B'])


def test_finite_choice_nonfinite_scores_fail_without_fallback():
    finite, _ = helpers()
    backend = SimpleNamespace(torch=torch, model=LogitModel({'A': float('nan')}), tokenizer=Tokenizer())
    with pytest.raises(RuntimeError, match='nonfinite'):
        finite.select(backend, [], {'A': 'defect'})


def unit_fixture():
    code = '\tint café=0;\r\nvoid f(){\r\n\tmissing(café);\r\n}\r\nlast'
    log = ''.join(f'header note {i}\r\n' for i in range(1, 29))
    log += '<stdin>:3: error: missing was not declared\r\n 3 | missing(café);\r\n   | ^~~~~~~\r\n'
    return {'source_catalog': refs.build_catalog(code, provided_compile_log=log,
                                                local_compile_log='local:2: error: bad\n',
                                                test_report='case one\ncase two'), 'task': {'code': code}}


def test_all_documents_are_covered_and_every_candidate_roundtrips_exact_bytes():
    _, candidates = helpers()
    unit = unit_fixture()
    original = copy.deepcopy(unit)
    catalog = candidates.build_catalog(unit)
    assert catalog == candidates.build_catalog(unit)
    assert len({c['candidate_id'] for c in catalog}) == len(catalog)
    covered = {source: set() for source in unit['source_catalog']}
    for c in catalog:
        ref = candidates.refs_for(c)
        assert ref == [{'source': c['source'], 'start_line': c['start_line'], 'end_line': c['end_line']}]
        span = refs.extract(unit['source_catalog'], ref[0])
        assert c['text'].encode() == span['text'].encode()
        assert c['text_sha256'] == hashlib.sha256(span['text'].encode()).hexdigest()
        assert c['document_sha256'] == span['document_sha256']
        assert c['boundary_kind']
        covered[c['source']].update(range(c['start_line'], c['end_line'] + 1))
    for source, document in unit['source_catalog'].items():
        assert covered[source] == set(range(1, document['line_count'] + 1))
    assert unit == original
    assert any('\t' in c['text'] and '\r\n' in c['text'] for c in catalog)
    revised = copy.deepcopy(unit)
    revised['source_catalog'] = refs.build_catalog(unit['task']['code'] + 'x')
    assert not {c['candidate_id'] for c in catalog if c['source'] == 'code'} & {
        c['candidate_id'] for c in candidates.build_catalog(revised)}


def test_rank_uses_source_identifiers_not_gold_and_pages_are_disjoint():
    _, candidates = helpers()
    unit = unit_fixture()
    catalog = candidates.build_catalog(unit)
    finding = {'location': 'missing, dòng 3', 'error': 'missing chưa khai báo', 'labels': ['x']}
    ranked = candidates.rank_candidates(catalog, finding, unit)
    changed = copy.deepcopy(unit)
    changed.update(gold={'evidence': 'header'}, reviewer='header')
    finding_changed = {**finding, 'gold': 'header', 'reviewer': 'header', 'labels': ['different']}
    assert ranked == candidates.rank_candidates(list(reversed(catalog)), finding_changed, changed)
    assert any('missing' in c['text'] for c in ranked[:3])
    first, second = candidates.page_candidates(ranked, 0), candidates.page_candidates(ranked, 1)
    assert len(first) <= 16 and len(second) <= 16
    assert not {c['candidate_id'] for c in first} & {c['candidate_id'] for c in second}
    assert first + second == ranked[:32]
    for page, size in [(-1, 16), (True, 16), (0, 17), (0, 0)]:
        with pytest.raises(ValueError):
            candidates.page_candidates(ranked, page, size)


def test_student_primary_error_ranks_before_header_overload_notes():
    _, candidates = helpers()
    log = '/usr/include/c++/12/ostream:3: note: candidate operator<< overload\n' * 12
    log += '<stdin>:1: error: no match for operator<< (operand type Student)\n'
    unit = {'source_catalog': refs.build_catalog('Student student;\nstd::cout << student;\n', provided_compile_log=log)}
    ranked = candidates.rank_candidates(candidates.build_catalog(unit),
                                         {'location': 'operator<<', 'error': 'no match operator<< Student'}, unit)
    logs = [c for c in ranked if c['source'] == 'provided_compile_log']
    assert '<stdin>:1: error:' in logs[0]['text']


def test_new_call_line29_is_allowed_only_by_new_view_without_clamping():
    _, candidates = helpers()
    unit = unit_fixture()
    catalog = candidates.build_catalog(unit)
    chosen = next(c for c in catalog if c['source'] == 'provided_compile_log' and c['start_line'] <= 29 <= c['end_line'])
    new_view = candidates.candidate_view(unit, [chosen])
    assert new_view['sources']['code']['presented_ranges'] == [[1, 5]]
    old_view = copy.deepcopy(new_view)
    old_view['sources']['provided_compile_log']['presented_ranges'] = [[1, 2]]
    ref = {'source': 'provided_compile_log', 'start_line': 29, 'end_line': 29}
    finding = {'evidence_refs': [ref]}
    with pytest.raises(refs.ReferenceFailure, match='not presented'):
        diagnostic_view.validate_presented_refs([finding], old_view, unit)
    assert diagnostic_view.validate_presented_refs([finding], new_view, unit) == [finding]
    assert old_view['sources']['provided_compile_log']['presented_ranges'] == [[1, 2]]
    bad = {**chosen, 'end_line': 999}
    with pytest.raises((ValueError, refs.ReferenceFailure)):
        candidates.candidate_view(unit, [bad])
    bad = {**chosen, 'text': 'fabricated'}
    with pytest.raises(ValueError):
        candidates.candidate_view(unit, [bad])


def test_archived_line29_was_omitted_and_new_view_is_separate():
    _, candidates = helpers()
    root = Path(__file__).resolve().parents[1]
    path = root / 'outputs/task3/v1.5-observation-20261024/public/enriched-inputs.private.json'
    attempts = root / 'outputs/task3/v1.6-json-transport-grounded/public/attempts.jsonl'
    if not path.exists() or not attempts.exists():
        pytest.skip('optional archived public artifacts unavailable')
    unit = next(u for u in json.loads(path.read_text())['units'] if u['sample_id'] == 'Class01-Test1-S01')
    rows = [json.loads(line) for line in attempts.read_text().splitlines()]
    row = next(r for r in reversed(rows) if r['sample_id'] == unit['sample_id'] and r['stage'] == 'taxonomy')
    view_path = root / 'outputs/task3/v1.6-json-transport-grounded/public/views' / (digest([row['sample_id'], row['stage'], row['attempt']]) + '.json')
    old_view = json.loads(view_path.read_text())
    before = copy.deepcopy(old_view)
    ref = {'source': 'provided_compile_log', 'start_line': 29, 'end_line': 29}
    with pytest.raises(refs.ReferenceFailure):
        diagnostic_view.validate_presented_refs([{'evidence_refs': [ref]}], old_view, unit)
    chosen = next(c for c in candidates.build_catalog(unit)
                  if c['source'] == ref['source'] and c['start_line'] <= 29 <= c['end_line'])
    new_view = candidates.candidate_view(unit, [chosen])
    diagnostic_view.validate_presented_refs([{'evidence_refs': [ref]}], new_view, unit)
    assert old_view == before


def test_header_keyword_density_cannot_displace_student_primary_diagnostic():
    _, candidates = helpers()
    words = 'alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron'
    log = '/usr/include/c++/12/header:8: note: candidate ' + words + '\n'
    log += 'submission.cpp:1: error: incompatible operands\n'
    unit = {'source_catalog': refs.build_catalog('int x;\n', provided_compile_log=log)}
    ranked = candidates.rank_candidates(candidates.build_catalog(unit),
                                         {'location': words, 'error': words}, unit)
    diagnostics = [c for c in ranked if c['boundary_kind'].startswith('compiler_')]
    assert diagnostics[0]['boundary_kind'] == 'compiler_primary_context'


def test_seventeen_choice_page_maps_q_to_none_supported():
    finite, _ = helpers()
    codes = list('ABCDEFGHIJKLMNOPQ')
    assert finite.choice_token_ids(Tokenizer(), codes) == list(range(65, 82))
    choices = {code: ('NONE_SUPPORTED' if code == 'Q' else 'span-' + code) for code in codes}
    backend = SimpleNamespace(torch=torch, model=LogitModel({'Q': 99}), tokenizer=Tokenizer())
    result = finite.select(backend, [], choices)
    assert result['code'] == 'Q' and result['value'] == 'NONE_SUPPORTED'
