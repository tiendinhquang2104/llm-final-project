"""Source metadata stays authoritative when a single problem has a P1 entry."""
import importlib.util
from pathlib import Path
import sys
import json
import zipfile
import pytest


def test_evaluation_type_matches_archive_metadata_not_nonempty_problems():
    root=Path(__file__).resolve().parents[1]
    output=root/'outputs/task3/grounded-20261023'
    if not (output/'selection-seal.json').exists():pytest.skip('private experiment absent')
    sys.path.insert(0,str(root/'scripts'))
    spec=importlib.util.spec_from_file_location('grounded_experiment',root/'scripts/task3_grounded_experiment.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    units=module.units_for('evaluation',output)
    with zipfile.ZipFile(root/'generate-dataset_v2.zip') as z:
        samples=json.loads(z.read('generate-dataset/task3_feedback.json'))['samples']
        exams={e['exam_id']:e for e in json.loads(z.read('generate-dataset/exams.json'))['exams']}
    expected={s['sample_id']:exams[s['input']['exam_id']]['exam_type']for s in samples}
    assert all(u['task']['exam_type']==expected[u['sample_id']]for u in units)
