"""CPU-only regressions for durable calls lost before controller capture."""
import json

import pytest

from scripts import task3_fresh_eval as fresh


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def test_costs_charge_completed_A_call_even_without_controller_capture(tmp_path, monkeypatch):
    # A returned and globally persisted its result, then died before the
    # historical controller could append attempts.jsonl. Resume retains the
    # missing target; accounting must still charge the completed physical call.
    rows = {
        'A': [{'status': 'missing'}, {'status': 'missing'}],
        'V2-old': [{'status': 'valid'}],
        'V3-v3': [{'status': 'missing'}],
    }
    monkeypatch.setattr(fresh, 'final_rows', lambda out: rows)
    for name in rows:
        _write(tmp_path / 'generations' / name / 'complete.json', {
            'physical_calls': 0 if name == 'A' else int(name == 'V2-old'),
            'input_tokens': 0, 'output_tokens': 0, 'generation_wall_s': 0,
        })
    for path, value in [
        ('evidence/source-validation.private.json', []),
        ('syntax.private.json', {}),
    ]:
        _write(tmp_path / path, value)
    (tmp_path / 'code-evidence.private.jsonl').write_text('')
    events = [
        {'type': 'base_model_load_completed', 'profile': 'A', 'wall_s': 4.0},
        {'type': 'base_model_load_completed', 'profile': 'native', 'wall_s': 6.0},
        {'type': 'generation_reserved', 'key': 'A/s1-L1/1'},
        {'type': 'generation_completed', 'key': 'A/s1-L1/1', 'result': {
            'raw': '{"feedback":"returned"}', 'finish_reason': 'eos',
            'input_tokens': 101, 'output_tokens': 19, 'wall_s': 2.25,
        }},
        {'type': 'generation_reserved', 'key': 'A/s2-L1/1'},
        {'type': 'generation_completed', 'key': 'A/s2-L1/1', 'result': {
            'raw': None, 'status': 'generation_error', 'finish_reason': 'runtime_error',
            'input_tokens': 103, 'output_tokens': 0, 'output_tokens_unknown': True,
            'wall_s': 1.25,
        }},
        {'type': 'generation_reserved', 'key': 'V2-old/s1-L1/1'},
        {'type': 'generation_completed', 'key': 'V2-old/s1-L1/1', 'result': {
            'status': 'valid', 'finish_reason': 'eos',
            'input_tokens': 107, 'output_tokens': 23, 'wall_s': 0.75,
        }},
        {'type': 'generation_reserved', 'key': 'V3-v3/s1-L1/1'},
    ]
    journal = tmp_path / 'journal.jsonl'
    journal.write_text(''.join(json.dumps(e) + '\n' for e in events))
    original_journal = journal.read_bytes()

    fresh.costs(tmp_path)
    report_path = tmp_path / 'costs-and-runtime.json'
    report = json.loads(report_path.read_text())
    a = report['systems']['A']
    assert a['physical_calls'] == 2
    assert a['historical_controller_captured_calls'] == 0
    assert a['completed_calls_without_controller_capture'] == 2
    assert a['unknown_reserved_calls'] == 0
    assert a['input_tokens'] == 204 and a['output_tokens'] == 19
    assert a['generation_wall_s'] == pytest.approx(3.5)
    assert a['failed_model_calls'] == 1
    assert a['finish_reasons'] == {'eos': 1, 'runtime_error': 1}
    assert a['invalid'] == 2  # Accounting does not salvage unresolved targets.
    assert report['systems']['V3-v3']['unknown_reserved_calls'] == 1
    assert report['systems']['V3-v3']['physical_calls'] == 0
    assert report['actual_model_calls'] == 3
    assert report['reserved_model_calls'] == 4
    assert report['unknown_reserved_calls'] == 1
    assert report['input_tokens'] == 311 and report['output_tokens'] == 42
    assert report['inference_wall_s'] == pytest.approx(4.25)
    assert report['model_load_wall_s'] == pytest.approx(10)
    assert report['fresh_targets'] == 4 and report['reused_targets'] == 0

    first_report = report_path.read_bytes()
    fresh.costs(tmp_path)
    assert report_path.read_bytes() == first_report
    assert journal.read_bytes() == original_journal
