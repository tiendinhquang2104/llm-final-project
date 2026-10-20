"""Train-only Round 14 development selection and descriptive, non-factual metrics."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from src.synth.feedback import FEEDBACK_LEVELS
from src.synth.taxonomy import LABEL_SPACE
from src.task3.compliance import check
from src.task3.dataset import load_prepared
from src.task3.schema import code_hash, validate_taxonomy


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _families(rows):
    """Union train exams by known task aliases and identical statement/problem text."""
    aliases = {'EX01': 'generals', 'SYN-GEN': 'generals', 'EX02': 'armstrong', 'SYN-ARM': 'armstrong'}
    parent = {r.exam_id: aliases.get(r.exam_id, r.exam_id) for r in rows}
    for value in list(parent.values()):
        parent.setdefault(value, value)

    def root(key):
        while parent[key] != key:
            key = parent[key]
        return key

    seen = {}
    for row in rows:
        texts = [row.statement] + [p.get('statement', '') for p in row.problems]
        for text in texts:
            if not text.strip():
                continue
            normalized = re.sub(r'\s+', ' ', text).strip().casefold()
            if normalized in seen:
                a, b = root(row.exam_id), root(seen[normalized])
                # Prefer the documented aliases over synthetic exam identifiers.
                keep = next((x for x in ('generals', 'armstrong') if x in (a, b)), min(a, b))
                parent[a if a != keep else b] = keep
            seen[normalized] = row.exam_id
    return {r.sample_id: root(r.exam_id) for r in rows}


def select_development(data_dir, per_level=6):
    """Freeze a train-derived family holdout; never open evaluation/public partitions.

    The returned reserve excludes *all* records in the held-out families, plus any
    code/group/renaming collision. Selected labels balance evaluation only.
    """
    if isinstance(per_level, bool) or not isinstance(per_level, int) or per_level < 1:
        raise ValueError('per_level must be a positive integer')
    data_dir = Path(data_dir)
    rows, partitions = [], {}
    for split in ('real-train', 'synthetic-train'):
        path = data_dir / f'{split}.jsonl'
        part = load_prepared(data_dir, split)
        if any(r.split != split or r.source != ('real' if split == 'real-train' else 'synthetic') for r in part):
            raise ValueError('partition/source identity mismatch')
        rows.extend(part)
        partitions[split] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'count': len(part)}
    rows.sort(key=lambda r: r.sample_id)
    if len({r.sample_id for r in rows}) != len(rows) or any(r.gold_taxonomy is None for r in rows):
        raise ValueError('train IDs must be unique and have evaluation labels')
    families = _families(rows)
    all_families = set(families.values())
    if len(all_families) < 2:
        raise ValueError('at least two disjoint train families are required')
    preferred = {'generals', 'armstrong', 'SYN-DIGITSUM', 'SYN-PRIME', 'SYN-MAXARR', 'SYN-COUNTUPPER'}
    held = preferred & all_families
    if not held:
        held = set(sorted(all_families)[:-1])
    if held == all_families:
        held.remove(sorted(held - {'generals', 'armstrong'} or held)[-1])
    candidates = [r for r in rows if families[r.sample_id] in held]
    selected, covered = [], set()
    # Prefer previously unseen labels and clean examples inside each Level quota.
    for level in FEEDBACK_LEVELS:
        pool = [r for r in candidates if r.target_feedback_level == level]
        for _ in range(min(per_level, len(pool))):
            row = min(pool, key=lambda r: (-len(set(r.gold_taxonomy) - covered),
                                          -(not r.gold_taxonomy and not any(not s.gold_taxonomy for s in selected)),
                                          r.sample_id))
            selected.append(row)
            covered.update(row.gold_taxonomy)
            pool.remove(row)
    # Rare labels and the empty-set stratum may add rows beyond the approximate quota.
    for label in LABEL_SPACE:
        if label not in covered:
            extra = next((r for r in candidates if label in r.gold_taxonomy and r not in selected), None)
            if extra:
                selected.append(extra)
                covered.update(extra.gold_taxonomy)
    if not any(not r.gold_taxonomy for r in selected):
        extra = next((r for r in candidates if not r.gold_taxonomy), None)
        if extra:
            selected.append(extra)
    selected.sort(key=lambda r: (FEEDBACK_LEVELS.index(r.target_feedback_level), r.sample_id))

    def identity(r):
        return {'sample_id': r.sample_id, 'partition': r.split, 'family': families[r.sample_id],
                'exam_id': r.exam_id, 'group_key': r.group_key or r.original_submission_id,
                'code_hash': r.code_hash, 'renamed_code_hash': code_hash(r.code, renamed=True)}

    held_identity = [identity(r) for r in candidates]
    keys = ('group_key', 'code_hash', 'renamed_code_hash')
    forbidden = {key: {r[key] for r in held_identity} for key in keys}
    reserve, excluded = [], []
    for row in rows:
        if families[row.sample_id] in held:
            continue
        info = identity(row)
        reasons = [key for key in keys if info[key] in forbidden[key]]
        if reasons:
            excluded.append({'sample_id': row.sample_id, 'reasons': reasons})
        else:
            reserve.append(row)
    if not reserve:
        raise ValueError('family holdout leaves no collision-free reserve training records')
    reserve_info = [identity(r) for r in reserve]
    metadata = {
        'selection_policy': 'round14_train_only_family_holdout_v1', 'per_level_target': per_level,
        'partition_identity': partitions, 'selected_ids': [r.sample_id for r in selected],
        'selected_records': [identity(r) for r in selected],
        'selected_families': sorted(held), 'selected_count': len(selected),
        'selected_per_level': dict(Counter(r.target_feedback_level for r in selected)),
        'covered_labels': [label for label in LABEL_SPACE if label in covered],
        'missing_labels': [label for label in LABEL_SPACE if label not in covered],
        'gold_empty_count': sum(not r.gold_taxonomy for r in selected),
        'reserve_ids': [r.sample_id for r in reserve], 'reserve_count': len(reserve),
        'reserve_families': sorted({families[r.sample_id] for r in reserve}),
        'reserve_partition_counts': dict(Counter(r.split for r in reserve)),
        'reserve_identity': {key: sorted({r[key] for r in reserve_info}) for key in keys},
        'excluded_collisions': excluded,
        'unselected_held_family_ids': sorted(r.sample_id for r in candidates if r not in selected),
        'selection_uses_labels_for_evaluation_stratification_only': True,
    }
    metadata['selection_id'] = _digest(metadata)
    return selected, metadata


def _align(records, values):
    if isinstance(values, dict):
        values = [{'sample_id': sid, 'output': value} for sid, value in values.items()]
    ids = [r.sample_id for r in records]
    by_id = {v['sample_id']: v for v in values}
    if len(ids) != len(set(ids)) or len(by_id) != len(values) or set(ids) != set(by_id):
        raise ValueError('prediction/trace IDs must match records exactly')
    return [by_id[sid] for sid in ids]


def taxonomy_metrics(records, predictions):
    """Score exact ten-group sets, including honest empty-gold false positives."""
    predictions = _align(records, predictions)
    pairs = [(set(validate_taxonomy(r.gold_taxonomy)), set(validate_taxonomy(p['output']['taxonomy_error'])))
             for r, p in zip(records, predictions)]
    per_group = {}
    for label in LABEL_SPACE:
        tp = sum(label in gold and label in pred for gold, pred in pairs)
        fp = sum(label not in gold and label in pred for gold, pred in pairs)
        fn = sum(label in gold and label not in pred for gold, pred in pairs)
        per_group[label] = {'tp': tp, 'fp': fp, 'fn': fn,
                            'precision': tp / (tp + fp) if tp + fp else 0,
                            'recall': tp / (tp + fn) if tp + fn else 0,
                            'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0}
    tp, fp, fn = (sum(v[k] for v in per_group.values()) for k in ('tp', 'fp', 'fn'))
    empty = sum(not gold for gold, _ in pairs)
    empty_fp = sum(not gold and bool(pred) for gold, pred in pairs)
    return {'count': len(pairs), 'macro_f1': sum(v['f1'] for v in per_group.values()) / len(LABEL_SPACE),
            'micro_f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
            'exact_set_accuracy': sum(gold == pred for gold, pred in pairs) / len(pairs) if pairs else 0,
            'per_group': per_group, 'gold_empty_count': empty,
            'gold_empty_false_positive_count': empty_fp,
            'gold_empty_false_positive_rate': empty_fp / empty if empty else None}


def feedback_metrics(records, predictions, traces):
    """Disclosure/language/fallback screens; never a factual correctness score."""
    predictions, traces = _align(records, predictions), _align(records, traces)
    per_level = {str(i): {'count': 0, 'guard_pass_count': 0, 'cjk_count': 0,
                          'fallback_count': 0, 'classification_fallback_count': 0,
                          'level1_projection_count': 0, 'action_only_heuristic_count': 0,
                          'round14_policy_error_count': 0, 'insufficient_requested_level_count': 0}
                 for i in range(1, 5)}
    for r, p, trace in zip(records, predictions, traces):
        level = FEEDBACK_LEVELS.index(r.target_feedback_level) + 1
        text = p['output']['feedback']
        bucket = per_level[str(level)]
        bucket['count'] += 1
        bucket['guard_pass_count'] += check(text, level, version=3).ok
        bucket['cjk_count'] += bool(re.search(r'[\u3400-\u9fff\uf900-\ufaff]', text))
        bucket['fallback_count'] += bool(trace.get('fallback_used', False))
        bucket['round14_policy_error_count'] += bool(trace.get('feedback_level_errors',[]))
        bucket['insufficient_requested_level_count'] += trace.get('usefulness')=='insufficient_for_requested_level'
        bucket['classification_fallback_count'] += bool(trace.get('classification_fallback', False))
        bucket['level1_projection_count'] += trace.get('feedback_origin') == 'level1_projection'
        action = bool(re.search(r'\b(?:hãy|nên|cần|thay|sửa|bổ sung|loại bỏ|kiểm tra)\b', text, re.I))
        causal = bool(re.search(r'\b(?:vì|do|khiến|dẫn đến|chưa|thiếu|thừa|sai|không)\b', text, re.I))
        bucket['action_only_heuristic_count'] += action and not causal
    return {'count': len(records), 'per_level': per_level,
            'fallback_count': sum(v['fallback_count'] for v in per_level.values()),
            'factual_correctness': 'not_measured', 'guard_policy_version': 3,
            'guard_metric_scope':'legacy disclosure screen; round14_policy_error_count additionally includes experimental action/coherence checks',
            'action_only_heuristic_definition': 'Vietnamese action cue without causal/defect cue; not factual or adequacy score',
            'level4_correctness': 'not_measured'}
