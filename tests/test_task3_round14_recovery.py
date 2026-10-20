"""Artificial checkpoint migration tests; no model or public inputs."""
import json
from dataclasses import replace

import pytest

from src.task3.dataset import write_json
from src.task3.round14_runner import identity
from tests.test_task3_round14 import sample
from tests.test_task3_round14_runner import Scripted, config


def checkpoint(tmp_path):
    records = [replace(sample(), sample_id='DONE'), replace(sample(), sample_id='FAILED')]
    backend = Scripted([])
    prior = dict(config(), implementation_sha256={'runner': 'old'})
    current = dict(config(), implementation_sha256={'runner': 'new'})
    rows = [{'sample_id': 'FAILED', 'stage': stage, 'attempt': number,
             'error': 'strict schema rejection', 'finish_reason': 'eos',
             'output_tokens': 20, 'input_tokens': 30, 'latency_s': .1}
            for stage in ('direct', 'classifier_fallback') for number in (1, 2)]
    state = {'identity': identity(records, backend, dict(prior, oracle_labels=None, assessment_cache=None)),
             'completed': {'DONE': {'output': {'taxonomy_error': ['Lỗi logic'], 'feedback': 'Artificial diagnosis.'},
                                    'trace': {'sample_id': 'DONE', 'attempts': []}}},
             'errors': {'FAILED': {'type': 'ValueError',
                                  'reason': 'classification_unresolved_after_bounded_independent_fallback',
                                  'trace': {'sample_id': 'FAILED', 'attempts': rows}}}}
    write_json(tmp_path / 'progress.json', state)
    (tmp_path / 'attempts.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    write_json(tmp_path / 'run.json', {'status': 'incomplete_resumable'})
    kwargs = dict(prior_config=prior, prior_implementation_sha256={'runner': 'old'},
                  prior_freeze_sha256='original-freeze', current_freeze_sha256='amended-freeze')
    return records, backend, current, kwargs, state


def prepare(tmp_path, fixture):
    from src.task3.round14_recovery import prepare_schema_recovery
    records, backend, current, kwargs, _ = fixture
    return prepare_schema_recovery(records, backend, current, tmp_path, **kwargs)


def test_migration_preserves_completed_and_exact_artifact_bytes(tmp_path):
    fixture = checkpoint(tmp_path)
    original = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    meta = prepare(tmp_path, fixture)
    migrated = json.loads((tmp_path / 'progress.json').read_text())
    assert meta['eligible_ids'] == ['FAILED']
    assert migrated['completed'] == fixture[-1]['completed']
    assert migrated['errors'] == fixture[-1]['errors']
    assert migrated['identity'] == meta['new_identity'] != meta['old_identity']
    assert (tmp_path / 'attempts.jsonl').read_bytes() == original['attempts.jsonl']
    for name, raw in original.items():
        assert (tmp_path / 'pre-schema-recovery' / name).read_bytes() == raw


@pytest.mark.parametrize('change', ['source', 'config', 'identity', 'prior-hashes'])
def test_mismatched_original_binding_cannot_migrate(tmp_path, change):
    fixture = checkpoint(tmp_path)
    records, backend, current, kwargs, state = fixture
    if change == 'source': records[0] = replace(records[0], code='int main(){return 99;}')
    if change == 'config': current['seed'] = 19
    if change == 'identity':
        state['identity'] = 'unrelated-checkpoint'; write_json(tmp_path / 'progress.json', state)
    if change == 'prior-hashes': kwargs['prior_implementation_sha256'] = {'runner': 'wrong'}
    before = (tmp_path / 'progress.json').read_bytes()
    with pytest.raises(ValueError): prepare(tmp_path, fixture)
    assert (tmp_path / 'progress.json').read_bytes() == before
    assert not (tmp_path / 'schema-recovery.json').exists()


@pytest.mark.parametrize('change', ['runtime', 'missing-attempt', 'successful-attempt', 'wrong-stage', 'journal-mismatch', 'nonmapping-trace'])
def test_only_exhausted_strict_classification_failures_are_eligible(tmp_path, change):
    fixture = checkpoint(tmp_path); state = fixture[-1]
    failure = state['errors']['FAILED']; rows = failure['trace']['attempts']
    if change == 'runtime': failure.update(type='RuntimeError', reason='GPU failure')
    if change == 'missing-attempt': rows.pop()
    if change == 'successful-attempt': rows[0]['error'] = None
    if change == 'wrong-stage': rows[-1]['stage'] = 'feedback'
    if change == 'journal-mismatch': rows[0]['output_tokens'] = 999
    if change == 'nonmapping-trace': failure['trace'] = []
    write_json(tmp_path / 'progress.json', state)
    with pytest.raises(ValueError): prepare(tmp_path, fixture)
    assert not (tmp_path / 'schema-recovery.json').exists()


def test_idempotence_accepts_eligible_new_completion_and_journal_append(tmp_path):
    fixture = checkpoint(tmp_path); first = prepare(tmp_path, fixture)
    p = tmp_path / 'progress.json'; state = json.loads(p.read_text())
    state['completed']['FAILED'] = {'output': {'taxonomy_error': [], 'feedback': 'Explicit artificial model decision.'}, 'trace': {'sample_id': 'FAILED'}}
    state['errors'].pop('FAILED'); write_json(p, state)
    with (tmp_path / 'attempts.jsonl').open('a') as f: f.write(json.dumps({'stage': 'classify', 'sample_id': 'FAILED'}) + '\n')
    assert prepare(tmp_path, fixture) == first


@pytest.mark.parametrize('change', ['completed', 'prefix', 'snapshot', 'sidecar'])
def test_idempotent_resume_rejects_mutated_original_evidence(tmp_path, change):
    fixture = checkpoint(tmp_path); prepare(tmp_path, fixture)
    if change == 'completed':
        p = tmp_path / 'progress.json'; state = json.loads(p.read_text()); state['completed']['DONE']['output']['feedback'] = 'CHANGED'; write_json(p, state)
    if change == 'prefix': (tmp_path / 'attempts.jsonl').write_text('{}\n')
    if change == 'snapshot': (tmp_path / 'pre-schema-recovery' / 'run.json').write_text('{}')
    if change == 'sidecar':
        p = tmp_path / 'schema-recovery.json'; meta = json.loads(p.read_text()); meta['eligible_ids'] = ['DONE']; write_json(p, meta)
    with pytest.raises(ValueError): prepare(tmp_path, fixture)


def test_prepared_sidecar_finishes_interrupted_identity_migration(tmp_path):
    fixture = checkpoint(tmp_path); meta = prepare(tmp_path, fixture)
    meta['status'] = 'prepared'; meta.pop('metadata_sha256', None)
    from src.task3.round14_runner import digest
    meta['metadata_sha256'] = digest(meta)
    write_json(tmp_path / 'schema-recovery.json', meta)
    write_json(tmp_path / 'progress.json', fixture[-1])
    result = prepare(tmp_path, fixture)
    assert result['status'] == 'migrated'
    assert json.loads((tmp_path / 'progress.json').read_text())['identity'] == result['new_identity']
