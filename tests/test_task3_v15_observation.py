import copy
import json
from pathlib import Path
import pytest
from scripts import task3_v15_observe as obs
from src.task3 import arm_d_plus_v15 as plus
from src.task3.compiler_evidence import prepare
from src.task3.dataset import write_json
from tests.test_task3_arm_d_plus import Backend,SPACE,LABELS,config,unit
from tests.test_task3_v15 import finding,encoded


def inputs(tmp_path):
    u=unit();u2=copy.deepcopy(u);u2['sample_id']='second'
    return prepare([u,u2],tmp_path/'inputs')[0]


def test_failed_quality_does_not_block_internal_or_public():
    for phase in ('internal','public'):
        assert obs.execution_allowed({'integrity':'passed','infrastructure':'ready'}, {'status':'failed','micro_f1':0,'renderer_joint':3},phase)
    with pytest.raises(obs.ExecutionIntegrityFailure):obs.execution_allowed({'integrity':'failed','infrastructure':'ready'},{'status':'passed'},'internal')


def test_exhausted_content_failure_continues_and_resume_does_not_regenerate(tmp_path):
    us=inputs(tmp_path);b=Backend(['bad','bad',encoded(),'{"feedback":"Chưa thấy vấn đề có căn cứ."}'])
    rows=obs.observe_phase(us,b,config(),tmp_path/'run',SPACE)
    assert [r['status'] for r in rows]==['unresolved','resolved'] and len(b.calls)==4
    again=Backend([]);resumed=obs.observe_phase(us,again,config(),tmp_path/'run',SPACE)
    assert resumed==rows and not again.calls
    assert obs.phase_counts(rows)['attempted']==2


def test_detector_valid_preserved_when_renderer_fails(tmp_path):
    us=inputs(tmp_path)[:1];b=Backend([encoded(finding()),'bad','bad'])
    rows=obs.observe_phase(us,b,config(),tmp_path/'run',SPACE)
    assert rows[0]['stage1'] is not None and rows[0]['status']=='unresolved'
    assert obs.phase_counts(rows)=={'attempted':1,'detector_valid':1,'feedback_valid':0,'unresolved':1}
    resumed=Backend([]);obs.observe_phase(us,resumed,config(),tmp_path/'run',SPACE);assert not resumed.calls


def test_catalog_corruption_stops_before_model(tmp_path):
    us=inputs(tmp_path);us[0]['source_catalog']['code']['sha256']='broken';b=Backend([])
    with pytest.raises(ValueError,match='catalog'):obs.observe_phase(us,b,config(),tmp_path/'run',SPACE)
    assert not b.calls


def test_backend_failure_stops_run_after_persisting_raw_failure(tmp_path):
    us=inputs(tmp_path);b=Backend([RuntimeError('CUDA failure')])
    with pytest.raises(obs.ExecutionIntegrityFailure,match='CUDA failure'):obs.observe_phase(us,b,config(),tmp_path/'run',SPACE)
    assert len(b.calls)==1
    rows=[json.loads(l) for l in (tmp_path/'run/attempts.jsonl').read_text().splitlines()]
    assert len(rows)==1 and rows[0]['error']=='CUDA failure'


def test_partial_export_never_complete_and_quality_does_not_remove_valid_output(tmp_path):
    us=inputs(tmp_path);us[0]['level']=1;us[1]['level']=1
    rows=obs.observe_phase(us,Backend([encoded(),'bad','bad']),config(),tmp_path/'run',SPACE)
    requested={u['sample_id']:SPACE['feedback_level'][0]['level'] for u in us}
    status=obs.export_phase(tmp_path/'run',rows,requested,LABELS)
    assert not status['passed'] and status['completed']==1 and not (tmp_path/'run/predictions.json').exists()
    assert len(json.loads((tmp_path/'run/partial.predictions.json').read_text()))==1


def test_environment_restore_resume_skips_failed_reserved_call_and_runs_pending(tmp_path):
    us=inputs(tmp_path);b=Backend([RuntimeError('CUDA unavailable')])
    with pytest.raises(obs.ExecutionIntegrityFailure):obs.observe_phase(us,b,config(),tmp_path/'run',SPACE)
    restored=Backend([encoded(),'{"feedback":"Chưa thấy vấn đề có căn cứ."}'])
    results=obs.observe_phase(us,restored,config(),tmp_path/'run',SPACE)
    assert [r['status'] for r in results]==['unresolved','resolved'] and len(restored.calls)==2
    attempts=[json.loads(l) for l in (tmp_path/'run/attempts.jsonl').read_text().splitlines()]
    assert sum(r['sample_id']==us[0]['sample_id'] for r in attempts)==1


def test_schema_valid_poor_feedback_is_observed_without_semantic_retry(tmp_path):
    us=inputs(tmp_path)[:1]
    b=Backend([encoded(finding()),'{"feedback":"Em hãy xóa vòng lặp này."}'])
    rows=obs.observe_phase(us,b,config(),tmp_path/'run',SPACE)
    assert rows[0]['status']=='resolved' and rows[0]['output']['feedback']=='Em hãy xóa vòng lặp này.'
    assert len(b.calls)==2


def test_runtime_capture_failure_is_recorded_without_hiding_original_error(tmp_path):
    class Broken:
        def runtime_metadata(self):raise RuntimeError('device synchronization failed')
    result=obs.capture_runtime(Broken(),tmp_path/'runtime-after.json')
    assert result['capture_status']=='unavailable' and 'synchronization' in result['reason']
    assert json.loads((tmp_path/'runtime-after.json').read_text())==result


def test_systemic_generation_value_error_stops_instead_of_schema_retry(tmp_path):
    us=inputs(tmp_path);b=Backend([ValueError('systemic generation configuration rejected')])
    with pytest.raises(obs.ExecutionIntegrityFailure,match='systemic generation'):obs.observe_phase(us,b,config(),tmp_path/'run',SPACE)
    assert len(b.calls)==1


def test_isolated_context_overflow_remains_sample_failure(tmp_path):
    us=inputs(tmp_path);b=Backend([])
    results=obs.observe_phase(us,b,{**config(),'context_limit':100},tmp_path/'run',SPACE)
    assert len(results)==2 and all(r['failure']['category']=='context' for r in results)
    assert not b.calls


def test_treatment_comparison_uses_json_canonical_freeze_keys():
    persisted={'prompts':{'guidance':{'1':'same'}},'mapping':{},'config':{'seed':42}}
    runtime={'prompts':{'guidance':{1:'same'}},'mapping':{},'config':{'seed':42}}
    assert obs.verify_treatment(runtime,persisted)
    runtime['prompts']['guidance'][1]='changed'
    with pytest.raises(ValueError,match='treatment'):obs.verify_treatment(runtime,persisted)


def test_investigated_dependency_guard_retains_exact_status_and_evidence(tmp_path):
    u=unit();u['task']['code']='#include <sstring>\n'
    out=tmp_path/'inputs'
    with pytest.raises(ValueError,match='prerequisite'):prepare([u],out)
    from src.task3.level_blind import digest
    audit=json.loads((out/'compiler-audit.private.json').read_text());row=audit['samples'][0]
    cached=json.loads((out/'compiler-cache'/(row['cache_key']+'.json')).read_text())
    decision={'approved_evidence':[{'source_sha256':row['source_sha256'],'cache_key':row['cache_key'],
                'toolchain_fingerprint':row['toolchain_fingerprint'],'diagnostic_sha256':digest(cached['result']['diagnostic'])}],
              'readiness':'investigated_source_dependency','compiler_policy_changed':False,'reason':'Original source requests nonexistent sstring; toolchain standard-header control passes.'}
    enriched,a=obs.restore_investigated_evidence([u],out,decision)
    assert enriched[0]['local_compiler']['status']=='dependency_failure'
    assert enriched[0]['source_catalog']['local_compile_log']['text']==cached['result']['diagnostic']
    assert enriched[0]['task']['code']==u['task']['code']
    bad=copy.deepcopy(decision);bad['approved_evidence'][0]['source_sha256']='tampered'
    with pytest.raises(obs.ExecutionIntegrityFailure):obs.restore_investigated_evidence([u],out,bad)
