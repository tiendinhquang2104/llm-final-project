"""Artificial-only offline report tests; no evaluation artifacts or model runtime."""
import copy
import json

import pytest

from scripts.task3_pilot_report import summarize_arms, summarize_raw, run_report


def cohort():
    records = [dict(sample_id=f's{i}', annotation_v2=['Lỗi logic'],
                    source_reference=['Lỗi logic'], defect_status='defect', exam_type='artificial')
               for i in range(60)]
    requests = [dict(request_id=f'p{i}', sample_id=f's{i}', kind='primary', level=i%4+1)
                for i in range(60)]
    requests += [dict(request_id=f'c{i}-{level}', sample_id=f's{i}', kind='counterfactual', level=level)
                 for i in range(12) for level in (1, 2, 3)]
    predictions = [dict(request_id=r['request_id'], status='completed',
                        output=dict(taxonomy_error=['Lỗi logic'], feedback='Em hãy kiểm tra điều kiện.'))
                   for r in requests]
    return dict(records=records, requests=requests), predictions


def statuses():
    return {arm:dict(complete=True, processed_requests=96, expected_requests=96) for arm in 'ABC'}


def test_complete_cohort_uses_frozen_scorer_and_separates_supports():
    snapshot, predictions = cohort()
    snapshot['records'][0]['annotation_v2'] = []
    got = summarize_arms(snapshot, {arm:predictions for arm in 'ABC'}, statuses())
    assert got['status'] == 'complete'
    metrics = got['arms']['A']['metrics']
    assert metrics['primary']['source_reference']['support'] == 60
    assert metrics['counterfactual']['source_reference']['support'] == 36
    assert metrics['primary']['source_reference']['micro']['f1'] == 1.
    assert metrics['primary']['annotation_v2']['micro']['f1'] < 1.
    assert metrics['invariance']['completed_triples'] == 12
    assert metrics['primary']['feedback_review']['assessments']['vietnamese']['assessed'] == 0
    assert metrics['primary']['feedback_review']['assessments']['vietnamese']['rate'] is None


@pytest.mark.parametrize('change', ['prefix', 'false_complete', 'processed', 'duplicate', 'unknown'])
def test_incomplete_arm_never_receives_prefix_metrics(change):
    snapshot, predictions = cohort()
    by_arm = {arm:copy.deepcopy(predictions) for arm in 'ABC'}
    state = statuses()
    if change == 'prefix': by_arm['C'] = predictions[:4]
    if change == 'false_complete': state['C']['complete'] = False
    if change == 'processed': state['C']['processed_requests'] = 95
    if change == 'duplicate': by_arm['C'][-1] = copy.deepcopy(by_arm['C'][0])
    if change == 'unknown': by_arm['C'][-1]['request_id'] = 'not-frozen'
    got = summarize_arms(snapshot, by_arm, state)
    assert got['status'] == 'incomplete'
    assert got['arms']['C']['status'] == 'incomplete'
    assert 'metrics' not in got['arms']['C']
    assert got['arms']['A']['status'] == 'complete'


def test_canonical_failures_are_preserved_and_unknown_status_rejected():
    snapshot, predictions = cohort()
    predictions[0] = dict(request_id='p0', status='schema_error')
    got = summarize_arms(snapshot, {arm:predictions for arm in 'ABC'}, statuses())
    counts = got['arms']['A']['metrics']['primary']['counts']
    assert counts['statuses']['schema_error'] == 1
    assert counts['completion_rate']['numerator'] == 59
    predictions[0]['status'] = 'ok'
    with pytest.raises(ValueError, match='status'):
        summarize_arms(snapshot, {arm:predictions for arm in 'ABC'}, statuses())


def test_raw_stats_count_diagnosis_by_source_and_cjk_as_diagnostic_only():
    predictions = [dict(request_id='r1', status='completed', output=dict(taxonomy_error=[], feedback='Em thử 日本 한글.')),
                   dict(request_id='r2', status='runtime_error')]
    generated = [dict(request_id='r1', stage='diagnosis', output_tokens=10, input_tokens=20, latency_s=.2, elapsed_s=.3),
                 dict(request_id='r1', stage='feedback', output_tokens=4, input_tokens=30, latency_s=.1, elapsed_s=.15)]
    diagnoses = [dict(source_id='s1', schema_valid=True, resolved=True)]
    decisions = [dict(request_id='r1', source_id='s1', diagnosis_cache_hit=False, error=None, feedback_raw='{}'),
                 dict(request_id='r2', source_id='s1', diagnosis_cache_hit=True, error='runtime', feedback_raw=None)]
    got = summarize_raw(predictions, generations=generated, diagnoses=diagnoses, decisions=decisions)
    assert got['diagnosis']['unique_sources'] == 1
    assert got['diagnosis']['schema_valid_sources'] == 1
    assert got['diagnosis']['cache_hits'] == 1
    assert got['generation']['attempts'] == 2
    assert got['generation']['output_tokens'] == 14
    assert got['generation']['input_tokens'] == 50
    assert got['generation']['latency_s'] == pytest.approx(.3)
    assert got['feedback_length']['characters']['mean'] == len('Em thử 日本 한글.')
    assert got['unicode_diagnostics']['han_request_ids'] == ['r1']
    assert got['unicode_diagnostics']['hangul_request_ids'] == ['r1']
    assert got['unicode_diagnostics']['semantic_judgment'] is False


def test_legacy_retries_and_fallback_count_once_per_request():
    attempts = [dict(sample_id='r1', attempt=i, output_tokens=3, latency_s=.1) for i in (1, 2, 3)]
    got = summarize_raw([], legacy_attempts=attempts,
                        legacy_decisions=[dict(schema_valid=True)]*3,
                        legacy_traces=[dict(sample_id='r1', fallback_used=True)])
    assert got['generation']['attempts'] == 3
    assert got['generation']['retries'] == 2
    assert got['fallback_requests'] == 1
    assert got['schema_attempts']['valid'] == 3


def test_legacy_final_schema_count_uses_predictions_instead_of_two_stage_decisions():
    predictions = [dict(request_id='r1', status='completed', output=dict(
        taxonomy_error=[], feedback='Em kiểm tra lại.')),
        dict(request_id='r2', status='schema_error')]
    got = summarize_raw(predictions,
        legacy_attempts=[dict(sample_id='r1', attempt=1)],
        legacy_decisions=[dict(schema_valid=True)],
        legacy_traces=[dict(sample_id='r1', fallback_used=False)])
    assert got['feedback']['schema_valid_requests'] == 1
    assert got['feedback']['requested'] == 2


def test_incomplete_cli_workflow_never_calls_reference_loader(tmp_path):
    (tmp_path/'training').mkdir()
    (tmp_path/'training'/'training-result.json').write_text(json.dumps(dict(status='complete')))
    def forbidden():
        raise AssertionError('reference must not be read before all final arms')
    result = run_report(tmp_path, verify_pilot=lambda: ({}, {}, [], [], [], {}), load_reference=forbidden)
    assert result['status'] == 'incomplete'
    assert all('metrics' not in report for report in result['arms'].values())


def test_report_outputs_are_immutable_and_keep_input_hashes(tmp_path):
    snapshot, predictions = cohort()
    (tmp_path/'training').mkdir()
    (tmp_path/'training'/'training-result.json').write_text(json.dumps(dict(status='complete')))
    for arm in 'ABC':
        folder = tmp_path/'inference'/f'arm-{arm}'; folder.mkdir(parents=True)
        (folder/'status.json').write_text(json.dumps(statuses()[arm]))
        (folder/'predictions.json').write_text(json.dumps(predictions))
    result = run_report(tmp_path, verify_pilot=lambda: ({}, {}, [], [], [], {}), load_reference=lambda: snapshot)
    assert result['status'] == 'complete'
    report = tmp_path/'reports'/'arm-A.summary.private.json'
    before = report.read_bytes()
    assert json.loads(before)['input_sha256']['predictions.json']
    with pytest.raises(FileExistsError):
        run_report(tmp_path, verify_pilot=lambda: ({}, {}, [], [], [], {}), load_reference=lambda: snapshot)
    assert report.read_bytes() == before


def test_report_cli_without_explicit_score_flag_never_reads_files(monkeypatch):
    from scripts import task3_pilot_report as report
    def forbidden(*args, **kwargs):
        raise AssertionError('file reads are forbidden without --score')
    monkeypatch.setattr(report, '_read', forbidden)
    with pytest.raises(SystemExit):
        report.main([])


def test_primary_cohort_requires_sixty_distinct_sources():
    snapshot, predictions = cohort()
    snapshot['requests'][1]['sample_id'] = snapshot['requests'][0]['sample_id']
    with pytest.raises(ValueError, match='60|sixty|source'):
        summarize_arms(snapshot, {arm:predictions for arm in 'ABC'}, statuses())


def test_invalid_journal_does_not_leave_partial_immutable_reports(tmp_path):
    snapshot, predictions = cohort()
    (tmp_path/'training').mkdir()
    (tmp_path/'training'/'training-result.json').write_text(json.dumps(dict(status='complete')))
    for arm in 'ABC':
        folder = tmp_path/'inference'/f'arm-{arm}'; folder.mkdir(parents=True)
        (folder/'status.json').write_text(json.dumps(statuses()[arm]))
        (folder/'predictions.json').write_text(json.dumps(predictions))
    duplicate = json.dumps(dict(source_id='same', schema_valid=True))+'\n'
    (tmp_path/'inference'/'arm-C'/'diagnoses.jsonl').write_text(duplicate*2)
    with pytest.raises(ValueError, match='source exactly once'):
        run_report(tmp_path, verify_pilot=lambda: ({}, {}, [], [], [], {}), load_reference=lambda: snapshot)
    assert not (tmp_path/'reports'/'arm-A.summary.private.json').exists()
