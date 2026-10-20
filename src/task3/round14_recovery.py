"""Audited identity migration for the bounded, explicit schema recovery amendment.

This helper never generates predictions or changes completed output/trace values.
The caller verifies the original public manifest and freeze before invoking it.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

from src.task3.dataset import write_json


_ARTIFACTS = ('progress.json', 'attempts.jsonl', 'run.json', 'metrics.json',
              'traces.json', 'completed.predictions.json', 'audit-summary.json')
_FAILURE = 'classification_unresolved_after_bounded_independent_fallback'


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _digest(value):
    # Runtime import avoids a cycle when the controller imports this helper.
    from src.task3.round14_runner import digest
    return digest(value)


def _object(raw):
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError('invalid recovery checkpoint JSON') from exc
    if not isinstance(value, dict):
        raise ValueError('recovery checkpoint must be an object')
    return value


def _journal(raw):
    if raw and not raw.endswith(b'\n'):
        raise ValueError('original attempt journal must end with a physical LF')
    rows = []
    for line in raw.split(b'\n')[:-1]:
        rows.append(_object(line))
    return rows


def _state_ids(state, ids):
    if not isinstance(state.get('completed'), dict) or not isinstance(state.get('errors'), dict):
        raise ValueError('invalid completed/error checkpoint mappings')
    completed, errors = set(state['completed']), set(state['errors'])
    if completed & errors or completed | errors != ids:
        raise ValueError('checkpoint IDs must partition the exact input records')


def _eligible(state, rows, retries):
    eligible = []
    stages = [('direct', n) for n in range(1, retries + 2)] + [
        ('classifier_fallback', n) for n in range(1, retries + 2)]
    for sid, failure in state['errors'].items():
        if not isinstance(failure, dict) or failure.get('type') != 'ValueError' or failure.get('reason') != _FAILURE:
            continue
        trace = failure.get('trace', {})
        attempts = trace.get('attempts') if isinstance(trace, dict) else None
        if not isinstance(trace, dict) or trace.get('sample_id') != sid or not isinstance(attempts, list) or len(attempts) != len(stages):
            continue
        valid = True
        for row, (stage, number) in zip(attempts, stages):
            if (not isinstance(row, dict) or row.get('sample_id') != sid
                    or row.get('stage') != stage or type(row.get('attempt')) is not int
                    or row['attempt'] != number or not isinstance(row.get('error'), str)
                    or not row['error'].strip() or row.get('finish_reason') == 'runtime_error'
                    or row.get('token_count_unknown', False)
                    or type(row.get('output_tokens')) is not int or row['output_tokens'] < 0):
                valid = False
                break
        if valid and [row for row in rows if row.get('sample_id') == sid] == attempts:
            eligible.append(sid)
    if not eligible:
        raise ValueError('no exhausted strict classification failures eligible for recovery')
    return sorted(eligible)


def _atomic_bytes(path, raw):
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            os.chmod(temporary, 0o600)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _sealed(meta, status):
    value = {k: v for k, v in meta.items() if k != 'metadata_sha256'}
    value['status'] = status
    value['metadata_sha256'] = _digest(value)
    return value


def prepare_schema_recovery(records, backend, config, output_dir, *, prior_config,
                            prior_implementation_sha256, prior_freeze_sha256,
                            current_freeze_sha256):
    """Snapshot the original run and migrate only its identity, idempotently.

    ``eligible_ids`` is fixed by the original exhausted schema failures. Completed
    original entries are immutable across preparation and every subsequent resume.
    A prepared sidecar makes interruption between its write and migration safe.
    """
    from src.task3.round14_runner import identity

    records = list(records)
    ids = {r.sample_id for r in records}
    if len(ids) != len(records) or not records:
        raise ValueError('recovery requires nonempty unique input IDs')
    strip = lambda value: {k: v for k, v in value.items() if k != 'implementation_sha256'}
    if strip(prior_config) != strip(config) or config.get('method') != 'direct':
        raise ValueError('schema recovery cannot change model/config/method')
    if (not isinstance(prior_implementation_sha256, dict) or not prior_implementation_sha256
            or not isinstance(config.get('implementation_sha256'), dict)
            or not config['implementation_sha256']
            or ('implementation_sha256' in prior_config
                and prior_config['implementation_sha256'] != prior_implementation_sha256)):
        raise ValueError('prior/current implementation hashes required and must agree')
    if not prior_freeze_sha256 or not current_freeze_sha256:
        raise ValueError('original and amended freeze hashes required')
    old_config = dict(prior_config, implementation_sha256=prior_implementation_sha256)
    old_identity = identity(records, backend, dict(old_config, oracle_labels=None, assessment_cache=None))
    new_identity = identity(records, backend, dict(config, oracle_labels=None, assessment_cache=None))
    if old_identity == new_identity:
        raise ValueError('schema recovery must have a distinct amended identity')
    retries = config.get('max_retries', 1)
    if type(retries) is not int or retries not in (0, 1, 2):
        raise ValueError('bounded max_retries must be 0..2')
    out = Path(output_dir)
    state_path, journal_path = out / 'progress.json', out / 'attempts.jsonl'
    sidecar_path, snapshot_dir = out / 'schema-recovery.json', out / 'pre-schema-recovery'
    state = _object(state_path.read_bytes())
    _state_ids(state, ids)
    current_journal = journal_path.read_bytes()
    existing = _object(sidecar_path.read_bytes()) if sidecar_path.exists() else None
    if existing is not None:
        if existing.get('metadata_sha256') != _digest({k: v for k, v in existing.items() if k != 'metadata_sha256'}):
            raise ValueError('recovery sidecar checksum mismatch')
        hashes = existing.get('snapshot_sha256')
        if not isinstance(hashes, dict) or not {'progress.json', 'attempts.jsonl'} <= set(hashes) or not set(hashes) <= set(_ARTIFACTS):
            raise ValueError('invalid recovery snapshot inventory')
        originals = {name: (snapshot_dir / name).read_bytes() for name in hashes}
        if any(_sha(raw) != hashes[name] for name, raw in originals.items()):
            raise ValueError('original recovery snapshot changed')
    else:
        if state.get('identity') != old_identity:
            raise ValueError('original resume identity mismatch')
        if (out / 'predictions.json').exists():
            raise ValueError('incomplete original recovery cannot own a final artifact')
        originals = {name: (out / name).read_bytes() for name in _ARTIFACTS if (out / name).exists()}
    original_state = _object(originals['progress.json'])
    _state_ids(original_state, ids)
    if original_state.get('identity') != old_identity:
        raise ValueError('original resume identity mismatch')
    original_journal = originals['attempts.jsonl']
    eligible_ids = _eligible(original_state, _journal(original_journal), retries)
    immutable = original_state['completed']
    base = {'schema_version': 1, 'old_identity': old_identity, 'new_identity': new_identity,
            'prior_implementation_sha256': prior_implementation_sha256,
            'current_implementation_sha256': config['implementation_sha256'],
            'prior_freeze_sha256': prior_freeze_sha256, 'current_freeze_sha256': current_freeze_sha256,
            'prior_config_sha256': _digest(old_config), 'current_config_sha256': _digest(config),
            'eligible_ids': eligible_ids, 'preserved_completed_ids': sorted(immutable),
            'preserved_completed_sha256': _digest(immutable),
            'journal_prefix_bytes': len(original_journal), 'journal_prefix_sha256': _sha(original_journal),
            'snapshot_sha256': {name: _sha(raw) for name, raw in originals.items()}}
    if existing is not None and existing != _sealed(base, existing.get('status')):
        raise ValueError('recovery sidecar provenance mismatch')
    if not current_journal.startswith(original_journal):
        raise ValueError('original attempt journal prefix changed')
    preserved = {sid: state['completed'].get(sid) for sid in immutable}
    if _digest(preserved) != base['preserved_completed_sha256']:
        raise ValueError('original completed output/trace mapping changed')
    if not set(state['completed']) - set(immutable) <= set(eligible_ids):
        raise ValueError('new completions outside eligible recovery IDs')
    for sid in set(original_state['errors']) - set(eligible_ids):
        if state['errors'].get(sid) != original_state['errors'][sid]:
            raise ValueError('noneligible checkpoint failure changed')
    if existing is None:
        snapshot_dir.mkdir(mode=0o700, exist_ok=True)
        for name, raw in originals.items():
            path = snapshot_dir / name
            if path.exists() and path.read_bytes() != raw:
                raise ValueError('interrupted recovery snapshot conflicts with original artifacts')
        for name, raw in originals.items():
            if not (snapshot_dir / name).exists():
                _atomic_bytes(snapshot_dir / name, raw)
        write_json(sidecar_path, _sealed(base, 'prepared'))
        existing = _sealed(base, 'prepared')
    if existing['status'] not in {'prepared', 'migrated'}:
        raise ValueError('unknown recovery migration status')
    if state.get('identity') == old_identity and existing['status'] == 'prepared':
        if _digest(state) != _digest(original_state) or current_journal != original_journal:
            raise ValueError('prepared original checkpoint changed before migration')
        write_json(state_path, dict(state, identity=new_identity))
    elif state.get('identity') != new_identity:
        raise ValueError('amended resume identity mismatch')
    result = _sealed(base, 'migrated')
    if existing != result:
        write_json(sidecar_path, result)
    return result
