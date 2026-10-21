"""Artificial-only source projection/freeze checks."""
import hashlib
import json

import pytest


def source(sid='fixture-a'):
    code='int main() { return 0; }\n'
    return dict(sample_id=sid,code=code,source_sha256=hashlib.sha256(code.encode()).hexdigest(),
        domain='Valid small integers.',findings=[dict(label='Lỗi logic',quote='return 0;')],
        expected_compile='compile_error',parent_exam=dict(statement='Print a value.',problems=[dict(pid='P1')],grading_policy='One task.'))


def test_projection_keeps_domain_source_context_but_no_reference_or_compile_gold():
    from scripts.task3_contract_v1_prepare import build_inputs
    rows=build_inputs([source()],[dict(sample_id='fixture-a',level=2)],expected_count=1)
    assert rows[0]['requested_level']==2
    task=rows[0]['task']
    assert task['code']==source()['code']
    assert 'Valid small integers.' in task['statement']
    assert task['compiler_evidence']['status']=='unavailable'
    assert set(task)=={'statement','problems','grading_policy','code','compiler_evidence','domain'}
    assert 'findings' not in json.dumps(task) and 'compile_error' not in json.dumps(task)


@pytest.mark.parametrize('selection',[
    [dict(sample_id='fixture-a',level=2),dict(sample_id='fixture-a',level=3)],
    [dict(sample_id='unknown',level=2)],
    [dict(sample_id='fixture-a',level=0)]])
def test_projection_rejects_duplicate_unknown_or_invalid_level(selection):
    from scripts.task3_contract_v1_prepare import build_inputs
    with pytest.raises(ValueError):build_inputs([source()],selection,expected_count=len(selection))


def test_projection_rejects_source_byte_drift():
    from scripts.task3_contract_v1_prepare import build_inputs
    r=source();r['code']+='// changed\n'
    with pytest.raises(ValueError,match='hash'):build_inputs([r],[dict(sample_id='fixture-a',level=1)],expected_count=1)


def test_projection_preserves_frozen_string_level_meaning():
    from scripts.task3_contract_v1_prepare import build_inputs
    rows=build_inputs([source()],[dict(sample_id='fixture-a',level='L3')],expected_count=1)
    assert rows[0]['requested_level']==3
    assert rows[0]['request_id'].endswith('@L3')


def test_domain_projection_removes_diagnosis_and_witness_audit_prose():
    from scripts.task3_contract_v1_prepare import project_domain
    assert project_domain('0 <= a <= 10. Both a^b and the erroneously calculated b^a fit; recursion depth is 11.')=='0 <= a <= 10.'
    d=project_domain({'scope':'1 <= n <= 1000 unless the finding is specifically about P1.',
        'audit':'All counterexamples keep intermediate arithmetic safe.'})
    assert '1 <= n <= 1000' in d
    assert not any(word in d.lower() for word in ('finding','counterexample','erroneously','recursion'))


def test_problem_projection_matches_native_r15_context_keys():
    from scripts.task3_contract_v1_prepare import build_inputs
    r=source();r['parent_exam']['problems'][0].update(prototype='int solve();',max_score=10,is_prerequisite_for=['P2'])
    row=build_inputs([r],[dict(sample_id='fixture-a',level=1)],expected_count=1)[0]
    assert row['task']['problems']==[dict(pid='P1',prototype='int solve();')]


def test_snapshot_is_exclusive_and_tampering_rejected(tmp_path):
    from scripts.task3_contract_v1_prepare import write_snapshot,verify_snapshot
    root=tmp_path/'new';artifacts={'inputs.private.json':[{'id':'artificial'}],'config.json':{'seed':42}}
    manifest=write_snapshot(root,artifacts,{'scope':'artificial'})
    assert verify_snapshot(root)==manifest
    with pytest.raises(FileExistsError):write_snapshot(root,artifacts,{})
    (root/'inputs.private.json').write_text('[]')
    with pytest.raises(ValueError,match='hash'):verify_snapshot(root)
