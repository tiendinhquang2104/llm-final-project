"""Source-only Task 3 snapshot identities, archive validation and training guard.

No model imports, execution, public readers, or old-prediction readers. Archive
loading retains v2 taxonomy but deliberately drops teacher prose/exec reports.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import random
import re
import zipfile

from src.synth.taxonomy import LABEL_SPACE
from src.task3.schema import code_hash, validate_taxonomy

ZIP_SHA256 = '6bda70c29254a3bce91933b65f4a311d73a052e72d181c97e977152e14602f9b'
LEVEL_CONTRACTS = {
    '1': dict(allow_location=False, allow_cause=False, allow_repair=False, allow_full_solution=False,
              requirement='State problem or appropriate scoped praise; false-clean on a confirmed defect fails.'),
    '2': dict(allow_location=True, allow_cause=True, allow_repair=False, allow_full_solution=False,
              requirement='Correct location and cause; no concrete repair or code.'),
    '3': dict(allow_location=True, allow_cause=True, allow_repair=True, require_feasible_repair=True,
              allow_full_solution=False, requirement='Correct location/cause and feasible direction, no full solution.'),
    '4': dict(allow_location=True, allow_cause=True, allow_repair=True, allow_full_solution=True,
              requirement='Sample solution allowed; source correctness still required.'),
}
IDENTITY_KEYS = ('sample_id', 'group', 'family', 'source_sha256', 'code_identity', 'renamed_identity')


def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def sha_file(path):
    return sha_bytes(Path(path).read_bytes())


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(json_bytes(value))
    path.chmod(0o600)


def _source_member(reference, prefix):
    if not isinstance(reference, str) or '\\' in reference:
        raise ValueError('unsafe source path')
    p = PurePosixPath(reference)
    if p.is_absolute() or '..' in p.parts or not p.parts or p.suffix != '.cpp' or ':' in reference:
        raise ValueError('unsafe source path')
    return prefix + str(p)


def read_archive(path, *, expected_sha=ZIP_SHA256, expected_count=627):
    """Read required members in memory; never extract over prepared data."""
    if sha_file(path) != expected_sha:
        raise ValueError('archive SHA mismatch')
    members = {}
    with zipfile.ZipFile(path) as z:
        if len(z.namelist()) != len(set(z.namelist())):
            raise ValueError('duplicate archive member')
        def read(member):
            raw = z.read(member)
            members[member] = sha_bytes(raw)
            return raw
        base = 'generate-dataset/'
        official = json.loads(read(base+'label_space.json'))['taxonomy_error']
        if set(official) != set(LABEL_SPACE) or len(official) != 10:
            raise ValueError('archive must have exactly 10 official labels')
        def load(prefix):
            exams_list = json.loads(read(prefix+'exams.json'))['exams']
            exams = {e['exam_id']: e for e in exams_list}
            if len(exams) != len(exams_list):
                raise ValueError('duplicate exam ID')
            samples = json.loads(read(prefix+'task3_feedback.json'))['samples']
            records, seen = [], set()
            for sample in samples:
                sid = sample['sample_id']
                if not isinstance(sid, str) or not sid or sid in seen:
                    raise ValueError('duplicate or invalid sample ID')
                seen.add(sid)
                i = sample['input']; e = exams[i['exam_id']]
                member = _source_member(i['code_file'], prefix)
                raw = read(member)
                code = raw.decode('utf-8-sig')
                labels = validate_taxonomy(sample['output']['taxonomy_error'])
                if e['exam_type'] not in ('single_problem', 'multi_problem'):
                    raise ValueError('unknown exam type')
                record = dict(sample_id=sid, family=e['exam_id'], exam_id=e['exam_id'],
                    exam_type=e['exam_type'], statement=e['statement'], problems=e.get('problems', []),
                    grading_policy=e.get('grading_policy'), code=code, code_path=i['code_file'],
                    source_member=member, source_sha256=sha_bytes(raw), source_text_sha256=sha_bytes(code.encode()),
                    statement_sha256=sha_bytes(e['statement'].encode()), annotation_v2=labels,
                    original_level=i.get('target_feedback_level'), group=code_hash(code),
                    original_submission_id=PurePosixPath(i['code_file']).stem,
                    code_identity=code_hash(code), renamed_identity=code_hash(code, renamed=True))
                records.append(record)
            return records
        records = load(base)
        if len(records) != expected_count:
            raise ValueError('archive root record count mismatch')
        heldout = load(base+'heldout/') if base+'heldout/task3_feedback.json' in z.namelist() else []
    return dict(archive_sha256=expected_sha, records=records, heldout=heldout,
                members_sha256=members, official_labels=list(LABEL_SPACE))


def identity(row):
    """Derive identities from source when available; otherwise require metadata."""
    code = row.get('code')
    result = dict(sample_id=row['sample_id'], family=row.get('family', row.get('exam_id')),
                  group=row.get('group') or row.get('group_key') or row.get('original_submission_id'))
    if code is not None:
        result.update(source_sha256=row.get('source_sha256', sha_bytes(code.encode())),
                      code_identity=code_hash(code), renamed_identity=code_hash(code, renamed=True))
        result['group'] = result['group'] or code_hash(code)
    else:
        result.update({k: row.get(k) for k in IDENTITY_KEYS[3:]})
    return result


# Similarity is a conservative review signal, not proof of semantic equivalence.
_TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*.*?\*/|[A-Za-z_]\w*|\d+|\S', re.S)
_KEEP = set('int long short char float double bool void if else for while do return break continue class struct const static using namespace include true false nullptr new delete auto unsigned signed switch case default sizeof template typename'.split())


def structural_shingles(code):
    tokens = []
    for m in _TOKEN.finditer(code):
        t = m.group()
        if t.startswith(('//', '/*')):
            continue
        if re.fullmatch(r'[A-Za-z_]\w*', t) and t not in _KEEP:
            t = 'IDENT'
        tokens.append(t)
    return {sha_bytes(' '.join(tokens[i:i+5]).encode())[:24] for i in range(max(1, len(tokens)-4))}


def near_similarity(a, b):
    x, y = structural_shingles(a), structural_shingles(b)
    return len(x & y) / len(x | y) if x | y else 1.0


def require_train_isolation(rows, registry, *, stage):
    """Mandatory pre-target AND pre-optimizer guard; identities fail closed.

    Family denial intentionally makes all current-corpus families unavailable.
    New-family source-bearing candidates additionally undergo the frozen shingle
    screen. A >=0.85 match is blocked for review, never silently admitted.
    """
    if stage not in ('before_targets', 'before_optimizer'):
        raise ValueError('guard stage must be before_targets or before_optimizer')
    entries = registry['entries']
    indexes = {k: {r[k] for r in entries if r.get(k)} for k in IDENTITY_KEYS}
    for row in rows:
        item = identity(row)
        if any(not isinstance(item.get(k), str) or not item[k] for k in IDENTITY_KEYS):
            raise ValueError('missing training identity; fail closed')
        matches = [k for k in IDENTITY_KEYS if item[k] in indexes[k]]
        if 'code' in row:
            sig = structural_shingles(row['code'])
            for old in entries:
                prior = set(old.get('structural_shingles', []))
                if prior and len(sig & prior) / len(sig | prior) >= 0.85:
                    matches.append('near_duplicate_review_required')
                    break
        elif not matches:
            raise ValueError('missing source for near-duplicate identity screening; fail closed')
        if matches:
            raise ValueError(f'training leakage at {stage}: {item["sample_id"]}: {sorted(set(matches))}')
    return {'stage': stage, 'checked': len(rows), 'eligible': True}


def assign_levels(records):
    """Six L4 for >=60 sources; largest remainder L1/2/3 115:163:50."""
    n = len(records); l4 = min(6, n//10); main = n-l4
    targets = [main*x/328 for x in (115, 163, 50)]
    quota = [math.floor(x) for x in targets]
    for i in sorted(range(3), key=lambda i: (-(targets[i]-quota[i]), i))[:main-sum(quota)]:
        quota[i] += 1
    levels = [level for level, count in enumerate(quota+[l4], 1) for _ in range(count)]
    random.Random(42).shuffle(levels)
    return {r['sample_id']: level for r, level in zip(sorted(records, key=lambda r: r['sample_id']), levels)}


def validate_review(record, review):
    if review.get('sample_id') != record['sample_id'] or not review.get('domain'):
        raise ValueError('review identity/domain missing')
    status = review.get('defect_status')
    if status not in ('defect', 'scoped_clean', 'unresolved'):
        raise ValueError('review status missing')
    findings = review.get('findings', [])
    labels = review.get('source_reference')
    if labels is not None:
        validate_taxonomy(labels)
    if status == 'scoped_clean' and (not review.get('clean_basis') or findings or labels != []):
        raise ValueError('clean requires a scoped proof and no confirmed findings')
    if status == 'unresolved' and labels is not None:
        raise ValueError('unresolved reference must be null')
    if status == 'defect' and (not findings or set(labels or []) != {f['label'] for f in findings}):
        raise ValueError('defect labels/findings mismatch')
    seen = set()
    for f in findings:
        if not f.get('finding_id') or f['finding_id'] in seen:
            raise ValueError('duplicate/missing finding ID')
        seen.add(f['finding_id'])
        if not f.get('quote') or f['quote'] not in record['code']:
            raise ValueError('finding quote not in exact source')
        validate_taxonomy([f['label']])
        for k in ('cause', 'impact', 'status', 'repair_direction'):
            if not f.get(k):
                raise ValueError('incomplete finding: '+k)
        if not f.get('evidence', {}).get('reasoning'):
            raise ValueError('finding evidence reasoning missing')


def write_seal(path, hashes):
    write_new(path, {'format_version': 1, 'hashes': hashes})


def verify_seal(path, *, expected_hashes=None):
    path = Path(path)
    hashes = json.loads(path.read_text())['hashes']
    if expected_hashes is not None and hashes != expected_hashes:
        raise ValueError('sealed hash inventory mismatch with handoff')
    for relative, expected in hashes.items():
        p = Path(relative)
        if p.is_absolute() or '..' in p.parts:
            raise ValueError('unsafe seal path')
        if sha_file(path.parent/p) != expected:
            raise ValueError('snapshot hash mismatch: '+relative)
    return hashes
