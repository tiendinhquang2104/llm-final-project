import json
from dataclasses import asdict

import pytest

from src.synth.feedback import FEEDBACK_LEVELS
from src.synth.taxonomy import LABEL_SPACE
from tests.test_task3_dataset import record


def fixture_rows():
    rows = []
    for family, exam in enumerate(['EX01', 'SYN-GEN', 'EX02', 'SYN-ARM', 'SYN-PRIME', 'SYN-RESERVE']):
        for level in range(4):
            sid = f'TEST-{family}-{level}'
            rows.append(record(sid, source='synthetic', split='synthetic-train', exam_id=exam,
                               statement=f'Artificial task family {family // 2 if family < 4 else family}',
                               group_key=sid, code=f'int main() {{return {family * 10 + level};}}',
                               gold_taxonomy=[] if level == 0 else [LABEL_SPACE[(family * 3 + level) % 10]],
                               target_feedback_level=FEEDBACK_LEVELS[level]))
    return rows


def write_train(root, rows):
    root.mkdir(exist_ok=True)
    (root / 'real-train.jsonl').write_text('')
    (root / 'synthetic-train.jsonl').write_text(''.join(json.dumps({'record': asdict(r)}) + '\n' for r in rows))
    # These must never be read, even to validate a manifest.
    for name in ['real-val', 'public', 'synthetic-heldout']:
        (root / f'{name}.jsonl').write_text('NOT JSON; FORBIDDEN INPUT')


def test_selector_is_deterministic_family_disjoint_and_uses_only_train(tmp_path):
    from src.task3.round14_eval import select_development
    write_train(tmp_path, fixture_rows())
    selected, meta = select_development(tmp_path, per_level=2)
    assert selected and meta['reserve_count'] > 0
    assert not set(meta['selected_families']) & set(meta['reserve_families'])
    assert set(meta['selected_ids']).isdisjoint(meta['reserve_ids'])
    assert len(meta['partition_identity']) == 2
    for key in ['group_key', 'code_hash', 'renamed_code_hash']:
        assert {r[key] for r in meta['selected_records']}.isdisjoint(meta['reserve_identity'][key])
    again, other = select_development(tmp_path, per_level=2)
    assert [r.sample_id for r in selected] == [r.sample_id for r in again]
    assert meta == other
    assert meta['gold_empty_count'] > 0


def test_selector_quarantines_cross_family_rename_collision(tmp_path):
    from src.task3.round14_eval import select_development
    rows = fixture_rows()
    rows[-1].code = rows[0].code
    write_train(tmp_path, rows)
    _, meta = select_development(tmp_path, per_level=2)
    assert rows[-1].sample_id not in meta['reserve_ids']
    assert any(x['sample_id'] == rows[-1].sample_id and 'code_hash' in x['reasons'] for x in meta['excluded_collisions'])


def test_taxonomy_metrics_measure_all_ten_groups_and_empty_false_positives():
    from src.task3.round14_eval import taxonomy_metrics
    records = [record('A', gold_taxonomy=[LABEL_SPACE[0], LABEL_SPACE[1]]), record('B', gold_taxonomy=[])]
    predictions = [dict(sample_id='A', output={'taxonomy_error': [LABEL_SPACE[0]]}),
                   dict(sample_id='B', output={'taxonomy_error': [LABEL_SPACE[1]]})]
    scores = taxonomy_metrics(records, predictions)
    assert scores['micro_f1'] == .5
    assert scores['macro_f1'] == .1
    assert scores['exact_set_accuracy'] == 0
    assert scores['gold_empty_false_positive_count'] == 1
    assert scores['gold_empty_count'] == 1
    assert scores['per_group'][LABEL_SPACE[1]]['fp'] == 1
    assert scores['per_group'][LABEL_SPACE[1]]['fn'] == 1
    with pytest.raises(ValueError, match='IDs'):
        taxonomy_metrics(records, predictions[:1])


def test_feedback_projection_is_not_fallback_and_level_four_is_separate():
    from src.task3.round14_eval import feedback_metrics
    rows = [record('A', target_feedback_level=FEEDBACK_LEVELS[0]), record('B', target_feedback_level=FEEDBACK_LEVELS[3])]
    pred = [dict(sample_id='A', output={'feedback': 'Bài làm cần xem lại.'}),
            dict(sample_id='B', output={'feedback': '请检查'})]
    traces = [dict(sample_id='A', feedback_origin='level1_projection', fallback_used=False, attempts=[]),
              dict(sample_id='B', feedback_origin='fallback', fallback_used=True, attempts=[])]
    scores = feedback_metrics(rows, pred, traces)
    assert scores['fallback_count'] == 1
    assert scores['per_level']['1']['fallback_count'] == 0
    assert scores['per_level']['4']['cjk_count'] == 1
    assert scores['per_level']['4']['count'] == 1
    assert scores['factual_correctness'] == 'not_measured'
