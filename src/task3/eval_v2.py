"""Independent family-first controlled holdout. V1 policy is never modified.

Exposure metadata is descriptive. Used/reserved identities are restrictive.
The training whitelist is frozen before any target writing, not discovered at
optimizer time; both boundary checks require and recompute the actual source.
"""
from __future__ import annotations
from collections import Counter
from copy import deepcopy
import re

from src.task3.eval_snapshot import (
    IDENTITY_KEYS, identity, sha_bytes, structural_shingles, validate_review,
)
from src.task3.schema import _CPP_TOKEN

MATCH_KEYS = tuple(k for k in IDENTITY_KEYS if k != 'family')
THRESHOLD = 0.85


def validate_partition(partition, families):
    train, evaluation = partition['train_families'], partition['evaluation_families']
    if (not train or not evaluation or len(train) != len(set(train)) or
            len(evaluation) != len(set(evaluation)) or set(train) & set(evaluation) or
            set(train) | set(evaluation) != set(families)):
        raise ValueError('family partition must be nonempty, disjoint and exhaustive')


def with_signature(row):
    out = dict(identity(row))
    out['structural_shingles'] = sorted(structural_shingles(row['code'])) if 'code' in row else row.get('structural_shingles', [])
    out['source_text_sha256'] = sha_bytes(row['code'].encode()) if 'code' in row else row.get('source_text_sha256')
    out['reason'] = row.get('reason', 'used or reserved identity')
    return out


def similarity(a, b):
    def sig(r):
        return structural_shingles(r['code']) if 'code' in r else set(r['structural_shingles'])
    x, y = sig(a), sig(b)
    return len(x & y) / len(x | y) if x | y else 1.0


def identity_conflicts(row, protected):
    r = identity(row)
    return [(old['sample_id'], k) for old in protected for k in MATCH_KEYS
            if r.get(k) and r[k] == old.get(k)]


def make_registries(history, v1_records, evaluation_pool):
    """Keep source-only corpus exposure out of the used-ID prohibition."""
    exposure = {}
    used = []
    for e in history['entries']:
        exposure.setdefault(e['family'], set()).update(e['exposures'])
        if e['direct_experiment_use'] or any('heldout reserved' in x for x in e['exposures']):
            used.append(dict(e, reason='historical selected/example/target/output-review or reserved heldout'))
    used += [dict(r, reason='v1 frozen evaluation identity reserved, source-reviewed; no output use asserted') for r in v1_records]
    protected = [with_signature(r) for r in used]
    # Protect every source in evaluation families BEFORE selecting evaluation IDs.
    protected += [with_signature(dict(r, reason='v2 evaluation-family pool')) for r in evaluation_pool]
    unique = {}
    for e in protected:
        key = tuple(e[k] for k in IDENTITY_KEYS)
        if key not in unique:
            unique[key] = e
    return dict(family_exposure={k:sorted(v) for k,v in sorted(exposure.items())},
                used_reserved_identities=[with_signature(r) for r in used],
                training_protected_identities=list(unique.values()))


def select_train(pool, prepared_ids, partition, protected):
    eligible, rejected, seen = [], [], set()
    train = set(partition['train_families'])
    ordered = sorted(pool, key=lambda r:(r['sample_id'] != r['original_submission_id'], r['sample_id']))
    for r in ordered:
        if r['family'] not in train:
            continue
        reason, matches = None, []
        if r['sample_id'] not in prepared_ids:
            reason = 'not fixed prepared train membership'
        else:
            matches = identity_conflicts(r, protected)
            if matches:
                reason = 'used/reserved or evaluation-pool identity'
            else:
                signature = with_signature(r)
                near = next((e for e in protected if similarity(signature,e) >= THRESHOLD), None)
                if near:
                    reason = 'near used/reserved or evaluation-family source'
                    matches = [(near['sample_id'], 'shingle_jaccard>=0.85')]
        if not reason and r['renamed_identity'] in seen:
            reason = 'duplicate train code after identifier normalization'
        if reason:
            rejected.append(dict(sample_id=r['sample_id'],family=r['family'],reason=reason,matches=matches))
        else:
            eligible.append(r);seen.add(r['renamed_identity'])
    return eligible, rejected


def make_guard_registry(eligible, protected, train_families, evaluation_families):
    return dict(version='evaluation-v2', train_families=list(train_families),
                evaluation_families=list(evaluation_families),
                eligible=[with_signature(r) for r in eligible],
                protected=[with_signature(r) for r in protected],
                near_threshold=THRESHOLD,
                policy='Only sealed eligible sources; exposure family metadata alone is never a ban. Recheck source at both boundaries.')


def require_train_isolation(rows, registry, *, stage):
    if stage not in ('before_targets', 'before_optimizer'):
        raise ValueError('invalid guard stage')
    eligible = {e['sample_id']:e for e in registry['eligible']}
    checked = []
    for r in rows:
        if not isinstance(r.get('code'), str) or not r['code'].strip():
            raise ValueError('source required at both guard boundaries')
        sid = r.get('sample_id'); allowed = eligible.get(sid)
        if not allowed:
            raise ValueError(f'not eligible frozen training ID: {sid}')
        actual = identity(r)
        if (actual['family'] not in registry['train_families'] or
                actual['family'] in registry['evaluation_families']):
            raise ValueError('family leakage')
        for k in IDENTITY_KEYS:
            if not actual.get(k) or actual[k] != allowed[k]:
                raise ValueError('training identity mismatch: '+k)
            if k in r and r[k] != allowed[k]:
                raise ValueError('declared training identity mismatch: '+k)
        if sha_bytes(r['code'].encode()) != allowed['source_text_sha256']:
            raise ValueError('training source changed since eligibility freeze')
        collisions = identity_conflicts(r, registry['protected'])
        if collisions:
            raise ValueError('training leakage: '+str(collisions[:3]))
        signature = with_signature(r)
        if any(similarity(signature,e) >= registry['near_threshold'] for e in registry['protected']):
            raise ValueError('training near-duplicate leakage')
        checked.append(sid)
    return dict(stage=stage,checked=len(checked),unique_sources=len(set(checked)),eligible=True)


# This is a narrow, source-verifiable explicit method constraint, not a generic
# style heuristic. Generic TODO/comments/unused identifiers are not defects.
def style_assessment(statement, code):
    rule = next((text for text in (
        'không được dùng hàm pow', 'No pow calls permitted.', 'Do not use pow'
    ) if text.casefold() in statement.casefold()), None)
    tokens = [m.group() for m in _CPP_TOKEN.finditer(code) if not m.group().startswith(('//','/*'))]
    call = any(t == 'pow' and i+1 < len(tokens) and tokens[i+1] == '(' for i,t in enumerate(tokens))
    return dict(explicit_rule=rule,active_pow_construct=call,confirmed=bool(rule and call),
                criterion='Explicit source method restriction plus an active forbidden construct; no generic cosmetic labels.')


def v2_references(v1_records, extra_reviews, partition):
    """Subset only after family split; preserve annotation v2 verbatim."""
    evaluation = set(partition['evaluation_families'])
    result = [deepcopy(r) for r in v1_records if r['family'] in evaluation]
    for r in extra_reviews:
        if r['family'] not in evaluation:
            raise ValueError('extra reference from TRAIN family')
        validate_review(r,r)
        result.append(deepcopy(r))
    for key in ('sample_id','group','source_sha256','code_identity','renamed_identity'):
        if len({r[key] for r in result}) != len(result):
            raise ValueError('evaluation duplicate '+key)
    for r in result:
        r['style_review'] = style_assessment(r['statement'],r['code'])
        if 'Lỗi style' in (r['source_reference'] or []) and not r['style_review']['confirmed']:
            raise ValueError('unsupported source style label')
    return result


def apply_manual_review(candidates, review):
    """Below-threshold template decisions are mandatory, complete and auditable."""
    rows = review.get('records', [])
    by = {r.get('sample_id'):r for r in rows}
    if len(by) != len(rows) or set(by) != {r['sample_id'] for r in candidates}:
        raise ValueError('manual near-template review missing/duplicate/extra ID')
    admitted, excluded = [], []
    for candidate in candidates:
        decision = by[candidate['sample_id']]
        if type(decision.get('admit')) is not bool or not decision.get('reason'):
            raise ValueError('manual review requires bool decision and source-grounded rationale')
        (admitted if decision['admit'] else excluded).append(candidate)
    return admitted, excluded


def validate_reference_origin(records, archive_records):
    """Annotations and source/context come from the hashed archive, not review."""
    archive = {r['sample_id']:r for r in archive_records}
    fields = ('code','statement','annotation_v2','family','source_sha256','source_text_sha256',
              'code_identity','renamed_identity','group','exam_id','statement_sha256',
              'problems','grading_policy','source_member')
    for r in records:
        original = archive.get(r['sample_id'])
        if original is None:
            raise ValueError('reference ID outside archive')
        for field in fields:
            if field in original and r.get(field) != original[field]:
                raise ValueError('reference differs from archive: '+r['sample_id']+' '+field)


def require_parent_binding(partition, current_parent_sha256, frozen_parent_sha256=None):
    if partition.get('parent_v1_manifest_sha256') != current_parent_sha256:
        raise ValueError('v1 parent digest differs from fixed family partition')
    if frozen_parent_sha256 is not None and frozen_parent_sha256 != current_parent_sha256:
        raise ValueError('v1 parent digest differs from frozen v2 manifest')
