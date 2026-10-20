"""Deterministic train-only partitions for Round 15 prompt development.

Labels stratify evaluation only. No evaluation/public partition is opened, and
no teacher feedback is copied into a prompt demonstration by this module.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from src.synth.feedback import FEEDBACK_LEVELS
from src.synth.taxonomy import LABEL_SPACE
from src.task3.dataset import load_prepared
from src.task3.round14_eval import _digest, _families, select_development
from src.task3.schema import code_hash

DEVELOPMENT_FAMILIES = (
    'SYN-BASE2', 'SYN-COUNTEVEN', 'SYN-DISTINCT', 'SYN-FIB',
    'SYN-MAXDIFF', 'SYN-MINA', 'SYN-PALIN', 'SYN-PERFECT',
    'SYN-PROD', 'SYN-REVSTR', 'SYN-SUMEVEN', 'SYN-SUMPAIR',
)
IDENTITY_KEYS = ('group_key', 'code_hash', 'renamed_code_hash')


def _identity(row, families):
    return {
        'sample_id': row.sample_id, 'partition': row.split,
        'family': families[row.sample_id], 'exam_id': row.exam_id,
        'group_key': row.group_key or row.original_submission_id,
        'code_hash': row.code_hash, 'renamed_code_hash': code_hash(row.code, renamed=True),
    }


def _training(data_dir):
    """R14's collision-free reserve is the sole eligible parent partition."""
    root = Path(data_dir)
    _, previous = select_development(root)
    rows = [r for split in ('real-train', 'synthetic-train') for r in load_prepared(root, split)]
    families = _families(rows)
    eligible = set(previous['reserve_ids'])
    return sorted((r for r in rows if r.sample_id in eligible), key=lambda r: r.sample_id), families, previous


def _example_partition(rows, families, excluded_families):
    excluded_families = set(excluded_families)
    held = [_identity(r, families) for r in rows if families[r.sample_id] in excluded_families]
    forbidden = {key: {item[key] for item in held} for key in IDENTITY_KEYS}
    examples, excluded = [], []
    for row in rows:
        if families[row.sample_id] in excluded_families:
            continue
        info = _identity(row, families)
        reasons = [key for key in IDENTITY_KEYS if info[key] in forbidden[key]]
        if reasons:
            excluded.append({'sample_id': row.sample_id, 'reasons': reasons})
        else:
            examples.append(row)
    return examples, excluded


def select_example_candidates(data_dir, excluded_families):
    """Return train examples isolated from every row in the excluded families.

    These are candidates for manual source review, not approved demonstrations.
    Feedback-level reassignment must be recorded by the demonstration author.
    """
    rows, families, _ = _training(data_dir)
    examples, _ = _example_partition(rows, families, excluded_families)
    return examples


def select_prompt_development(data_dir):
    """Select exactly 24 records, with Level quotas 4/8/8/4 and three clean L1s.

    Hold out all twelve frozen train task families from the example pool. Each
    contributes two distinct submission identities, with ten-label coverage
    required. Insufficient strata fail instead of silently changing the freeze.
    """
    rows, families, previous = _training(data_dir)
    held_families = set(DEVELOPMENT_FAMILIES)
    candidates = [r for r in rows if families[r.sample_id] in held_families]
    if {families[r.sample_id] for r in candidates} != held_families:
        raise ValueError('required development family stratum is missing')
    selected, covered = [], set()
    used = {key: set() for key in IDENTITY_KEYS}
    family_count = Counter()
    # Protect clean and L4 strata first. L3 precedes L2 because REVSTR has no L3.
    for level_index, quota in ((0, 4), (3, 4), (2, 8), (1, 8)):
        level = FEEDBACK_LEVELS[level_index]
        for position in range(quota):
            want_clean = level_index == 0 and position < 3
            pool = []
            for row in candidates:
                info = _identity(row, families)
                if (row in selected or row.target_feedback_level != level
                        or family_count[info['family']] >= 2
                        or bool(not row.gold_taxonomy) != want_clean
                        or any(info[key] in used[key] for key in IDENTITY_KEYS)):
                    continue
                pool.append(row)
            if not pool:
                raise ValueError(f'insufficient clean/positive identity stratum at {level}')
            row = min(pool, key=lambda r: (
                family_count[families[r.sample_id]],
                -len(set(r.gold_taxonomy) - covered), len(r.gold_taxonomy), r.sample_id,
            ))
            selected.append(row)
            covered.update(row.gold_taxonomy)
            family_count[families[row.sample_id]] += 1
            for key, value in _identity(row, families).items():
                if key in used:
                    used[key].add(value)
    if covered != set(LABEL_SPACE):
        raise ValueError('development stratum does not cover all ten taxonomy groups')
    selected.sort(key=lambda r: (FEEDBACK_LEVELS.index(r.target_feedback_level), r.sample_id))
    examples, excluded = _example_partition(rows, families, held_families)
    if not examples:
        raise ValueError('development families leave no collision-free example candidates')
    example_identity = [_identity(r, families) for r in examples]
    metadata = {
        'selection_policy': 'round15_train_only_prompt_development_v1',
        'partition_identity': previous['partition_identity'],
        'parent_round14_selection_id': previous['selection_id'],
        'parent_reserve_count': len(rows),
        'selected_ids': [r.sample_id for r in selected],
        'selected_records': [_identity(r, families) for r in selected],
        'selected_families': sorted(held_families),
        'selected_count': len(selected),
        'selected_per_level': dict(Counter(r.target_feedback_level for r in selected)),
        'selected_per_family': dict(sorted(family_count.items())),
        'selected_partition_counts': dict(Counter(r.split for r in selected)),
        'label_counts': dict(Counter(label for r in selected for label in r.gold_taxonomy)),
        'covered_labels': [label for label in LABEL_SPACE if label in covered],
        'missing_labels': [],
        'gold_empty_count': sum(not r.gold_taxonomy for r in selected),
        'gold_empty_per_level': {level: sum(not r.gold_taxonomy and r.target_feedback_level == level for r in selected)
                                 for level in FEEDBACK_LEVELS},
        'development_family_pool_count': len(candidates),
        'development_family_pool_ids': [r.sample_id for r in candidates],
        'example_candidate_ids': [r.sample_id for r in examples],
        'example_candidate_count': len(examples),
        'example_candidate_families': sorted({families[r.sample_id] for r in examples}),
        'example_candidate_per_level': dict(Counter(r.target_feedback_level for r in examples)),
        'example_candidate_gold_empty_count': sum(not r.gold_taxonomy for r in examples),
        'example_candidate_identity': {key: sorted({r[key] for r in example_identity}) for key in IDENTITY_KEYS},
        'excluded_example_collisions': excluded,
        'selection_uses_labels_for_evaluation_stratification_only': True,
        'prior_prompt_selection_status': 'not_used_for_round14_prompt_selection; not_never_seen_or_blind',
        'prior_exposure_note': 'Round13 extractor saw training data; source review and manual reference authoring expose training examples. This is not a blind benchmark.',
        'clean_stratum_note': 'Three clean records are Level 1; one positive Level 1 remains. Original target levels are unchanged.',
    }
    metadata['selection_id'] = _digest(metadata)
    return selected, metadata
