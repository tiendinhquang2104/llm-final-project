import json
from pathlib import Path

import pytest

from scripts import task3_arm_d_plus as runner
from src.task3.dataset import write_json
from src.task3.submission import validate_submission
from src.synth.feedback import FEEDBACK_LEVELS
from src.synth.taxonomy import LABEL_SPACE


def predictions():
    return [{'sample_id':'fixture-1','output':{'taxonomy_error':[LABEL_SPACE[3]], 'feedback':'Vòng lặp chưa tiến triển.'}},
            {'sample_id':'fixture-2','output':{'taxonomy_error':[], 'feedback':'Chưa thấy lỗi có căn cứ.'}}]


@pytest.mark.parametrize('mutation', ['missing','duplicate','extra','enum','duplicate_label','empty_feedback'])
def test_submission_validator_rejects_invalid_candidates(tmp_path, mutation):
    rows=predictions()
    if mutation=='missing': rows.pop()
    elif mutation=='duplicate': rows[1]['sample_id']='fixture-1'
    elif mutation=='extra': rows.append({'sample_id':'extra','output':rows[0]['output']})
    elif mutation=='enum':rows[0]['output']['taxonomy_error']=['runtime error']
    elif mutation=='duplicate_label':rows[0]['output']['taxonomy_error']=[LABEL_SPACE[3],LABEL_SPACE[3]]
    else:rows[0]['output']['feedback']=' '
    write_json(tmp_path/'partial.predictions.json',rows)
    with pytest.raises(ValueError):
        runner.validate_export(tmp_path,{'fixture-1':FEEDBACK_LEVELS[0],'fixture-2':FEEDBACK_LEVELS[1]},list(LABEL_SPACE))
    assert not(tmp_path/'predictions.json').exists()
    assert json.loads((tmp_path/'validation.json').read_text())['passed'] is False


def test_export_is_validated_before_final_filename_and_rechecks_final(tmp_path):
    write_json(tmp_path/'partial.predictions.json',predictions())
    requested={'fixture-1':FEEDBACK_LEVELS[0],'fixture-2':FEEDBACK_LEVELS[1]}
    validation=runner.validate_export(tmp_path,requested,list(LABEL_SPACE))
    assert validation['passed'] is True
    assert validation['missing']==validation['duplicate']==validation['extra']==0
    assert validate_submission(tmp_path/'predictions.json',requested)['records']==2


def test_frozen_method_rejects_implementation_drift(tmp_path):
    root=tmp_path/'repo';root.mkdir()
    (root/'code.py').write_text('value = 1\n')
    from src.task3.level_blind import sha
    freeze=tmp_path/'freeze.json'
    write_json(freeze,{'config':{'version':'fixture'},'code_sha256':{'code.py':sha(root/'code.py')}})
    assert runner.verify_method(root,freeze,{'version':'fixture'})['config']=={'version':'fixture'}
    (root/'code.py').write_text('value = 2\n')
    with pytest.raises(ValueError,match='drift'):
        runner.verify_method(root,freeze,{'version':'fixture'})


def test_frozen_method_rejects_generation_config_drift(tmp_path):
    freeze=tmp_path/'freeze.json'
    write_json(freeze,{'config':{'max_new_tokens':1024},'code_sha256':{}})
    with pytest.raises(ValueError,match='config'):
        runner.verify_method(tmp_path,freeze,{'max_new_tokens':2048})


def test_reproduction_retains_venv_interpreter_symlink(tmp_path,monkeypatch):
    import shlex
    from types import SimpleNamespace
    venv=tmp_path/'venv'/'bin';venv.mkdir(parents=True)
    executable=venv/'python';executable.symlink_to('/usr/bin/python3')
    monkeypatch.setattr(runner.sys,'executable',str(executable))
    args=SimpleNamespace(phase='internal',public_root=tmp_path,internal_root=tmp_path,
                         history=tmp_path,method_freeze=None)
    runner.write_reproduction(args,tmp_path)
    commands=json.loads((tmp_path/'commands.json').read_text())
    assert shlex.split(commands['resume'])[0]==str(executable)
    assert shlex.split(commands['reproduce'])[0]==str(executable)


def test_backend_exposes_inherited_max_time_termination_as_timeout(monkeypatch):
    from src.task3.inference import Generation
    monkeypatch.setattr(runner.AuditedBackend,'generate',lambda *a:Generation('{',4,45.1,'unknown',False))
    backend=runner.DPlusBackend.__new__(runner.DPlusBackend)
    result=backend.generate([],{'generation_max_time_s':45})
    assert result.finish_reason=='timeout'
