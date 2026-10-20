"""Artificial train-only fixtures for Round 15 partition isolation."""

import importlib
import json
from collections import Counter
from dataclasses import asdict

import pytest

from src.synth.feedback import FEEDBACK_LEVELS
from src.synth.taxonomy import LABEL_SPACE
from src.task3.schema import code_hash
from tests.test_task3_dataset import record

DEV_FAMILIES = (
    'SYN-BASE2', 'SYN-COUNTEVEN', 'SYN-DISTINCT', 'SYN-FIB',
    'SYN-MAXDIFF', 'SYN-MINA', 'SYN-PALIN', 'SYN-PERFECT',
    'SYN-PROD', 'SYN-REVSTR', 'SYN-SUMEVEN', 'SYN-SUMPAIR',
)


def selector():
    return importlib.import_module('src.task3.round15_selection')


def write_fixture(root, mutate=None):
    rows = []
    for family, exam in enumerate((*DEV_FAMILIES, 'SYN-COUNT', 'SYN-FACT', 'SYN-ARM')):
        for level in range(4):
            sid = f'TEST-{family:02}-{level}'
            rows.append(record(
                sid, exam_id=exam, statement=f'TEST ONLY family {family}', group_key=sid,
                code=f'int main() {{return {1000 + family * 10 + level};}}',
                target_feedback_level=FEEDBACK_LEVELS[level],
                gold_taxonomy=[] if level == 0 and family < 3 else [LABEL_SPACE[family % 10]],
            ))
    if mutate:
        mutate(rows)
    (root / 'real-train.jsonl').write_text('')
    (root / 'synthetic-train.jsonl').write_text(''.join(json.dumps({'record': asdict(r)}) + '\n' for r in rows))
    for name in ('real-val', 'public', 'synthetic-heldout'):
        (root / f'{name}.jsonl').write_text('FORBIDDEN INPUT, NOT JSON')
    return rows


def test_frozen_quotas_clean_stratum_and_disjoint_examples(tmp_path):
    # Removing level quotas, clean stratification, or family isolation breaks this.
    write_fixture(tmp_path)
    mod = selector()
    selected, meta = mod.select_prompt_development(tmp_path)
    examples = mod.select_example_candidates(tmp_path, meta['selected_families'])
    assert Counter(r.target_feedback_level for r in selected) == dict(zip(FEEDBACK_LEVELS, (4, 8, 8, 4)))
    assert len(selected) == 24
    assert sum(not r.gold_taxonomy for r in selected) == 3
    assert set(x for r in selected for x in r.gold_taxonomy) == set(LABEL_SPACE)
    assert Counter(r.exam_id for r in selected) == dict.fromkeys(DEV_FAMILIES, 2)
    assert examples and {r.exam_id for r in examples} == {'SYN-COUNT', 'SYN-FACT'}
    assert {r.sample_id for r in selected}.isdisjoint(r.sample_id for r in examples)
    assert meta['example_candidate_count'] == len(examples)
    assert meta['partition_identity'].keys() == {'real-train', 'synthetic-train'}
    assert meta['prior_prompt_selection_status'] == 'not_used_for_round14_prompt_selection; not_never_seen_or_blind'
    _, again = mod.select_prompt_development(tmp_path)
    assert meta == again
    # Audit artifacts must not accidentally carry code/feedback into version control.
    assert all('code' not in r and 'gold_feedback' not in r for r in meta['selected_records'])


def test_examples_exclude_unselected_family_group_and_renaming_collisions(tmp_path):
    # Checking only chosen rows would leak the other held-family variants.
    def collisions(rows):
        rows[48].group_key = rows[0].group_key
        rows[49].code = rows[1].code.replace('main', 'renamedMain')
        rows[50].code = rows[2].code
    rows = write_fixture(tmp_path, collisions)
    mod = selector()
    selected, meta = mod.select_prompt_development(tmp_path)
    examples = mod.select_example_candidates(tmp_path, meta['selected_families'])
    assert {r.sample_id for r in examples}.isdisjoint(r.sample_id for r in rows[48:51])
    assert len(examples) == 5
    assert len(meta['excluded_example_collisions']) == 3
    for attribute in ('group_key', 'code_hash'):
        assert {getattr(r, attribute) for r in selected}.isdisjoint(getattr(r, attribute) for r in examples)
    assert {code_hash(r.code, renamed=True) for r in selected}.isdisjoint(code_hash(r.code, renamed=True) for r in examples)


def test_rejects_missing_clean_stratum_instead_of_silently_changing_quota(tmp_path):
    def remove_clean(rows):
        for row in rows:
            row.gold_taxonomy = [LABEL_SPACE[0]]
    write_fixture(tmp_path, remove_clean)
    with pytest.raises(ValueError, match='clean|stratum'):
        selector().select_prompt_development(tmp_path)


def test_rejects_forged_partition_source_identity(tmp_path):
    write_fixture(tmp_path, lambda rows: setattr(rows[-1], 'source', 'real'))
    with pytest.raises(ValueError, match='identity'):
        selector().select_prompt_development(tmp_path)


def test_family_without_level_three_does_not_strand_the_last_slot(tmp_path):
    # A greedy L2 pass must not strand a family that has no L3 submissions.
    def no_l3(rows):
        rows[9 * 4 + 2].target_feedback_level = FEEDBACK_LEVELS[1]
    write_fixture(tmp_path, no_l3)
    selected, _ = selector().select_prompt_development(tmp_path)
    assert len(selected) == 24
    assert sum(r.exam_id == 'SYN-REVSTR' for r in selected) == 2
