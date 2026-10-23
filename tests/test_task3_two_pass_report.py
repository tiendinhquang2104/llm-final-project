"""Artificial report integrity regressions; never read experiment artifacts."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import task3_two_pass as runner
from scripts import task3_two_pass_report as report
from src.task3.dataset import write_json
from src.task3.level_blind import read, sha


class IntegrityPassed(Exception):
    """Stop before gold/accounting once the integrity boundary is crossed."""


@pytest.fixture
def sealed(tmp_path, monkeypatch):
    out = tmp_path / 'experiment'
    review = out / 'review'
    monkeypatch.setattr(report, 'ROOT', tmp_path)
    monkeypatch.setattr(report, 'OUT', out)
    monkeypatch.setattr(report, 'REVIEW', review)
    verified = []
    monkeypatch.setattr(runner, 'verify', lambda: verified.append(True))

    def artificial_read(path):
        path = Path(path)
        assert path.is_relative_to(tmp_path), 'Test attempted a real artifact read'
        if path.name == 'train-eligible.private.json':
            raise IntegrityPassed
        return read(path)

    monkeypatch.setattr(report, 'read', artificial_read)
    unit = {'sample_id': 'ARTIFICIAL-ONLY', 'level': 2,
            'task': {'statement': 'Add two integers.', 'code': 'answer = a - b;',
                     'grading_policy': {}, 'exam_type': 'single_problem', 'problems': []}}
    write_json(out / 'units.private.json', [unit])
    control = {'sample_id': unit['sample_id'],
               'output': {'taxonomy_error': ['Lỗi logic'], 'feedback': 'Artificial control prose.'}}
    candidate = {'sample_id': unit['sample_id'],
                 'output': {'taxonomy_error': ['Lỗi logic'], 'feedback': 'Artificial candidate prose.'}}
    write_json(out / 'control.private.json', [control])
    write_json(out / 'B/results.private.json', [candidate])
    write_json(out / 'frozen/level-definitions.json', [])
    for who in ['a', 'b']:
        write_json(review / f'source-{who}.private.json', {
            'output_unseen': True,
            'cases': [{'sample_id': unit['sample_id'], 'source_taxonomy': ['Lỗi logic'],
                       'source_disputed': False}]})
    write_json(review / 'source-seal.json', {
        'source_before_outputs_and_gold': True,
        'hashes': {f'source-{who}.private.json': sha(review / f'source-{who}.private.json')
                   for who in ['a', 'b']}})
    report.packets()
    for who in ['a', 'b']:
        packet = read(review / f'paired-packet-{who}.private.json')
        cases = []
        for case in packet['cases']:
            outputs = []
            for output in case['outputs']:
                outputs.append({'output_id': output['output_id'],
                                'finding_supported': True, 'main_covered': True,
                                'false_claim': False, 'consistent': True, 'level_ok': True,
                                'natural': True, 'generic_only': False, 'disputed': False,
                                'l2_repair_leak': False, 'l3_actionable': None,
                                'evidence': [], 'reason': 'Artificial fixture only.'})
            cases.append({'sample_id': case['sample_id'], 'outputs': outputs})
        write_json(review / f'paired-{who}.private.json', {'reviewer': who.upper(), 'cases': cases})
    report.seal_reviews()
    return SimpleNamespace(out=out, review=review, verified=verified)


def test_untouched_seals_reach_accounting_only_after_frozen_verify(sealed):
    with pytest.raises(IntegrityPassed):
        report.score()
    assert sealed.verified == [True]


def test_frozen_verify_failure_stops_scoring(sealed, monkeypatch):
    def fail():
        raise ValueError('artificial frozen input drift')
    monkeypatch.setattr(runner, 'verify', fail)
    with pytest.raises(ValueError, match='frozen input drift'):
        report.score()


def test_changed_blind_key_is_rejected_even_with_same_sample_ids(sealed):
    path = sealed.review / 'blind-key.private.json'
    key = read(path)
    for value in key.values():
        value['arm'] = 'two_pass' if value['arm'] == 'R15' else 'R15'
    write_json(path, key)
    with pytest.raises(AssertionError, match='blind-key.private.json'):
        report.score()


@pytest.mark.parametrize('who', ['a', 'b'])
def test_changed_packet_leaf_is_rejected(sealed, who):
    path = sealed.review / f'paired-packet-{who}.private.json'
    packet = read(path)
    packet['cases'][0]['task']['code'] = 'answer = a + b;'
    write_json(path, packet)
    with pytest.raises(AssertionError, match=f'paired-packet-{who}'):
        report.score()


@pytest.mark.parametrize('arm', ['control.private.json', 'B/results.private.json'])
@pytest.mark.parametrize('field', ['feedback', 'taxonomy_error'])
def test_whole_current_output_must_match_reviewed_output(sealed, arm, field):
    path = sealed.out / arm
    rows = read(path)
    rows[0]['output'][field] = 'Changed artificial prose.' if field == 'feedback' else []
    write_json(path, rows)
    with pytest.raises(AssertionError, match='current output differs'):
        report.score()


@pytest.mark.parametrize('field', ['level', 'task'])
def test_current_level_and_source_must_match_reviewed_packet(sealed, field):
    path = sealed.out / 'units.private.json'
    units = read(path)
    if field == 'level':
        units[0]['level'] = 3
    else:
        units[0]['task']['code'] = 'answer = a + b;'
    write_json(path, units)
    with pytest.raises(AssertionError):
        report.score()


@pytest.mark.parametrize('name', ['source-b-extra.private.json', 'paired-b-extra.private.json',
                                  'extra-packet-seal.json', 'paired-packet-b-extra.private.json'])
def test_extra_artifacts_added_after_paired_seal_are_rejected(sealed, name):
    write_json(sealed.review / name, {})
    with pytest.raises(AssertionError, match='unsealed extra artifact'):
        report.score()


@pytest.mark.parametrize('change', ['missing', 'extra', 'duplicate'])
def test_candidate_id_coverage_and_uniqueness(sealed, change):
    path = sealed.out / 'B/results.private.json'
    rows = read(path)
    if change == 'missing':
        rows = []
    else:
        extra = deepcopy(rows[0])
        if change == 'extra':
            extra['sample_id'] = 'UNSELECTED-ARTIFICIAL'
        rows.append(extra)
    write_json(path, rows)
    with pytest.raises(AssertionError):
        report.score()


@pytest.mark.parametrize('change', ['source_content', 'missing_leaf', 'extra_leaf', 'false_order'])
def test_source_seal_rejects_changed_sources_and_incomplete_leaf_sets(sealed, change):
    path = sealed.review / 'source-seal.json'
    seal = read(path)
    if change == 'source_content':
        source_path = sealed.review / 'source-a.private.json'
        source = read(source_path)
        source['cases'][0]['source_taxonomy'] = []
        write_json(source_path, source)
    elif change == 'missing_leaf':
        del seal['hashes']['source-b.private.json']
    elif change == 'extra_leaf':
        seal['hashes']['unexpected.json'] = 'not-an-authorized-source'
    else:
        seal['source_before_outputs_and_gold'] = False
    write_json(path, seal)
    with pytest.raises(AssertionError):
        report.verify_source_seal()
