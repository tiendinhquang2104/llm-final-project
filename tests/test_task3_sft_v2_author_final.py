"""Specification and provenance checks for the separately authored final set."""
import importlib.util
from pathlib import Path


P = Path(__file__).resolve().parents[1] / 'scripts/task3_sft_v2_author_final.py'


def author():
    spec = importlib.util.spec_from_file_location('author_final', P)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exact_final_balance_and_pair_contract():
    m = author()
    cases = m.build_cases()
    m.validate_cases(cases)
    assert len(cases) == 40
    assert sum(c['intended_defective'] for c in cases) == 20
    assert sum(len(c['targets']) for c in cases) == 160
    for f in range(1, 11):
        group = [c for c in cases if c['family_id'] == f'V2E{f:02}']
        assert {c['sample_id'] for c in group} == {
            f'V2E{f:02}-{v}' for v in ('C1', 'C2', 'D1', 'D2')}
        assert len({c['code'] for c in group}) == 4


def test_specification_oracles_have_independent_known_results():
    m = author()
    assert m.oracle('csv', '"a,b","c""d",\n') == '3\n3:a,b\n3:c"d\n0:\n'
    assert m.oracle('ipv4', '01.2.3.4\n') == 'NO\n'
    assert m.oracle('ipv4', '255.0.1.2\n') == 'YES\n'
    assert m.oracle('rotate', '4 1 9\n') == '3\n'
    assert m.oracle('floor', '-7 3\n') == '-3\n'
    assert m.oracle('permutation', '3\n1 2 1\n') == '2 1 1\n'
    assert m.oracle('glob', '\na*\n') == 'NO\n'
    assert m.oracle('glob', 'ab\na*\n') == 'YES\n'
    assert m.oracle('mines', '2 2\n*.\n.*\n') == '*2\n2*\n'
    assert m.oracle('merge', '3\n1 2 3\n') == '9\n'
    assert m.oracle('power', '0 0 1\n') == '0\n'
    assert m.oracle('rook', 'R.......\n........\n........\n........\n........\n........\n........\n........\n') == '14\n'


def test_mutations_and_l4_are_bound_to_corresponding_clean_source():
    m = author()
    cases = m.build_cases()
    by_id = {c['sample_id']: c for c in cases}
    for c in cases:
        clean = by_id[c['solution_source_id']]
        assert not clean['intended_defective']
        assert m.extract_l4(c) == clean['code']
        assert all(t['expected'] == m.oracle(c['oracle_key'], t['input'])
                   for t in c['tests'])
        if c['intended_defective']:
            change = c['mutation']
            assert clean['code'].count(change['before']) == 1
            assert c['code'] == clean['code'].replace(change['before'], change['after'], 1)
            assert c['targets']['2']['feedback'].count('\n') == 0
        else:
            assert c['labels'] == []
            assert c['expected_failure_kind'] == 'none'
