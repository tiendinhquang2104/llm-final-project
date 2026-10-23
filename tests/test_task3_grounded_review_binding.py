"""A semantic review must never migrate onto changed sources or predictions."""
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def reviewed(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / 'scripts'))
    spec = importlib.util.spec_from_file_location('grounded_report_binding', root / 'scripts/task3_grounded_report.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    unit = dict(request_id='artificial-request', sample_id='artificial-sample', level=2,
                task=dict(code='int main() {}', statement='Artificial task', problems=[]))
    rows = [dict(unit=unit, arms={arm: dict(status='resolved', output=dict(taxonomy_error=[], feedback='Artificial feedback'))
                                 for arm in ['C0', 'C1', 'C2']})]
    monkeypatch.setattr(module, 'outputs', lambda out, split: rows)
    (tmp_path / 'evaluation').mkdir()
    module.packets(tmp_path, 'evaluation')
    return module, tmp_path, rows


def test_unchanged_review_binding_accepts(reviewed):
    module, out, _ = reviewed
    module.verify_review_binding(out, 'evaluation')


@pytest.mark.parametrize('mutation', ['feedback', 'status', 'source', 'key', 'packet'])
def test_changed_review_binding_rejects(reviewed, mutation):
    module, out, rows = reviewed
    directory = out / 'evaluation/review'
    if mutation == 'feedback':
        rows[0]['arms']['C1']['output']['feedback'] = 'A different claim'
    elif mutation == 'status':
        rows[0]['arms']['C1']['status'] = 'unresolved'
    elif mutation == 'source':
        rows[0]['unit']['task']['code'] = 'int main() { return 1; }'
    else:
        path = directory / ('key.private.json' if mutation == 'key' else 'packet-1.private.json')
        value = json.loads(path.read_text())
        if mutation == 'key':
            next(iter(value.values()))['arm'] = 'C9'
        else:
            value['cases'][0]['outputs'][0]['output']['feedback'] = 'Changed packet'
        path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        module.verify_review_binding(out, 'evaluation')


@pytest.mark.parametrize('target', ['packet-seal.json', 'key.private.json'])
def test_score_rejects_changed_sealed_provenance_before_reading_gold(reviewed, target):
    module, out, _ = reviewed
    d = out / 'evaluation'
    module.write_json(d / 'review-seal.json', dict(
        hashes={}, packet_seal_sha256=module.sha(d / 'review/packet-seal.json'),
        key_sha256=module.sha(d / 'review/key.private.json')))
    with (d / 'review' / target).open('a') as stream:
        stream.write(' ')
    with pytest.raises(ValueError):
        module.score(out, 'evaluation')
