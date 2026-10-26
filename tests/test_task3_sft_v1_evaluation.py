"""Regression coverage for strict output parsing and honest paired evaluation."""
import json

import pytest

from src.task3 import sft_v1_evaluation as evaluation


LABELS = ['logic', 'syntax']


def target(eid, sid, level, labels):
    return dict(example_id=eid, sample_id=sid, level=level, loss_weight=1.,
                prompt=[dict(role='system', content='Native contract.'),
                        dict(role='user', content='Statement: a < b\nC++: <script>alert(1)</script>')],
                completion=json.dumps(dict(taxonomy_error=labels, feedback='Phản hồi chuẩn.')))


def generation(example, labels=None, status='valid', raw=None):
    parsed = dict(taxonomy_error=labels or [], feedback='Một cách diễn đạt khác.')
    return dict(example_id=example['example_id'], sample_id=example['sample_id'],
                level=example['level'], raw=json.dumps(parsed) if raw is None else raw,
                parsed=parsed if status == 'valid' else None, status=status,
                finish_reason='eos' if status == 'valid' else status,
                input_tokens=12, output_tokens=4, wall_s=0.5)


@pytest.mark.parametrize('prefix,suffix', [('', ''), (' \n```json\n', '\n``` \n'),
                                         ('```\n', '\n```')])
def test_parser_accepts_exact_payload_or_single_full_outer_fence_without_changing_values(prefix, suffix):
    raw = '{"taxonomy_error":["logic"],"feedback":"  Lỗi ở a < b.  "}'
    result = evaluation.parse_response(prefix + raw + suffix, LABELS)
    assert result['status'] == 'valid'
    assert result['parsed'] == dict(taxonomy_error=['logic'], feedback='  Lỗi ở a < b.  ')


@pytest.mark.parametrize('raw,status', [
    ('before {"taxonomy_error":[],"feedback":"ổn"}', 'malformed_json'),
    ('{"taxonomy_error":[],"feedback":"ổn"} after', 'malformed_json'),
    ('```json\n{"taxonomy_error":[],"feedback":"ổn"}\n```\nextra', 'malformed_json'),
    ('{"taxonomy_error":[],"feedback":"a","feedback":"b"}', 'malformed_json'),
    ('{"taxonomy_error":[],"feedback":NaN}', 'malformed_json'),
    ('{"taxonomy_error":[],"feedback":Infinity}', 'malformed_json'),
    ('[]', 'schema_failure'),
    ('{"taxonomy_error":[],"feedback":"ổn","extra":1}', 'schema_failure'),
    ('{"taxonomy_error":[]}', 'schema_failure'),
    ('{"taxonomy_error":"logic","feedback":"ổn"}', 'schema_failure'),
    ('{"taxonomy_error":["unknown"],"feedback":"ổn"}', 'schema_failure'),
    ('{"taxonomy_error":["logic","logic"],"feedback":"ổn"}', 'schema_failure'),
    ('{"taxonomy_error":[1],"feedback":"ổn"}', 'schema_failure'),
    ('{"taxonomy_error":[],"feedback":true}', 'schema_failure'),
    ('{"taxonomy_error":[],"feedback":"  "}', 'schema_failure'),
    ('', 'missing'),
])
def test_parser_retains_explicit_failures_instead_of_inventing_clean_predictions(raw, status):
    result = evaluation.parse_response(raw, LABELS)
    assert result['status'] == status
    assert result['parsed'] is None


@pytest.mark.parametrize('finish,status', [('timeout', 'timeout'), ('max_time', 'timeout'),
    ('length', 'length'), ('max_new_tokens', 'length'), ('generation_error', 'generation_error'),
    ('missing', 'missing'), ('unknown', 'termination_failure')])
def test_parseable_json_stays_invalid_after_non_eos_termination(finish, status):
    result = evaluation.parse_response('{"taxonomy_error":[],"feedback":"ổn"}', LABELS, finish)
    assert result['status'] == status
    assert result['parsed'] is None


def test_metrics_keep_invalids_and_missing_targets_in_each_denominator():
    examples = [target('bad-L1', 'bad', 1, ['logic']), target('bad-L2', 'bad', 2, ['logic']),
                target('good-L1', 'good', 1, []), target('good-L2', 'good', 2, [])]
    rows = [generation(examples[0], ['logic']), generation(examples[1], status='length'),
            generation(examples[2], ['syntax'])]
    metrics = evaluation.aggregate_metrics(examples, rows)
    assert metrics['targets'] == 4
    assert metrics['sources'] == 2
    assert metrics['valid_outputs'] == 2
    assert metrics['invalid_outputs'] == 2
    assert metrics['status_counts'] == {'valid': 2, 'length': 1, 'missing': 1}
    assert metrics['valid_output_coverage'] == 0.5
    assert metrics['taxonomy']['valid_only']['tp'] == 1
    assert metrics['taxonomy']['valid_only']['fp'] == 1
    assert metrics['taxonomy']['valid_only']['fn'] == 0
    assert metrics['taxonomy']['valid_only']['f1'] == pytest.approx(2 / 3)
    assert metrics['taxonomy']['all_targets_conservative']['fn'] == 1
    assert metrics['taxonomy']['all_targets_conservative']['f1'] == 0.5
    assert metrics['taxonomy']['exact_match_all_targets'] == dict(correct=1, denominator=4, rate=0.25)
    assert metrics['clean_false_alarms']['targets'] == dict(
        false_alarms=1, denominator=2, invalid=1, valid=1, rate=0.5)
    assert metrics['clean_false_alarms']['sources'] == dict(
        false_alarms=1, denominator=1, with_invalid=1, rate=1.0)
    assert metrics['by_level']['2']['targets'] == 2
    assert metrics['by_level']['2']['sources'] == 2
    assert metrics['by_level']['2']['invalid_outputs'] == 2
    assert metrics['feedback_quality'] == dict(
        review_type='agent_review_not_independent_or_official', reviewed=0,
        pending_source_grounded_review=2, not_evaluable=2)
    assert metrics['costs']['input_tokens']['sum'] == 36
    assert metrics['costs']['wall_s']['sum'] == 1.5


@pytest.mark.parametrize('change', ['duplicate', 'foreign', 'wrong_source', 'wrong_level'])
def test_metrics_reject_misaligned_generation_records(change):
    examples = [target('a-L1', 'a', 1, ['logic'])]
    rows = [generation(examples[0])]
    if change == 'duplicate':
        rows.append(dict(rows[0]))
    elif change == 'foreign':
        rows[0]['example_id'] = 'other'
    elif change == 'wrong_source':
        rows[0]['sample_id'] = 'other'
    else:
        rows[0]['level'] = 2
    with pytest.raises(ValueError):
        evaluation.aggregate_metrics(examples, rows)


def test_full_split_reports_80_targets_as_20_sources_with_four_levels():
    examples = [target(f's{s}-L{level}', f's{s}', level, ['logic'] if s % 2 else [])
                for s in range(20) for level in range(1, 5)]
    metrics = evaluation.aggregate_metrics(examples, [])
    assert (metrics['targets'], metrics['sources'], metrics['invalid_outputs']) == (80, 20, 80)
    assert metrics['taxonomy']['all_targets_conservative']['fn'] == 40
    assert metrics['taxonomy']['exact_match_all_targets']['correct'] == 0
    assert metrics['source_coverage']['sources_all_targets_valid'] == 0
    assert all(v['targets'] == 20 and v['sources'] == 20 for v in metrics['by_level'].values())


def test_casebook_contains_all_paired_states_and_complete_escaped_source_gold_raw(tmp_path):
    examples = [target('source<&>-L1', 'source<&>', 1, ['logic']),
                target('source<&>-L2', 'source<&>', 2, ['logic'])]
    before = generation(examples[0], ['logic'], raw='<img src=x onerror=alert(2)>')
    after = generation(examples[0], ['logic'], status='malformed_json', raw='{bad')
    path = tmp_path / 'nested' / 'paired.html'
    evaluation.write_casebook(path, examples, {'base': [before], 'step80': [after]},
                              {'base': 1.3, 'step80': 1.1})
    html = path.read_text()
    assert 'source&lt;&amp;&gt;-L1' in html and 'source&lt;&amp;&gt;-L2' in html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html
    assert '&lt;img src=x onerror=alert(2)&gt;' in html
    assert '<img src=x' not in html
    assert 'Native contract.' in html and 'Phản hồi chuẩn.' in html
    assert 'base' in html and 'step80' in html and 'malformed_json' in html and 'missing' in html
    assert '1.3' in html and '1.1' in html
    assert 'not_evaluable' in html and 'pending_source_grounded_review' in html
    assert 'type="search"' in html and 'data-level="2"' in html
