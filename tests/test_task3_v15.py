import copy
import json
import pytest
from src.task3 import arm_d_plus_v15 as plus
from src.task3.compiler_evidence import prepare
from tests.test_task3_arm_d_plus import Backend,LABELS,SPACE,config,unit


def finding(**kw):
    return dict(problem_id='P1',kind='defect',location='main',error='The traversal does not progress for n > 0.',
                labels=['Lỗi vòng lặp'],evidence_refs=[{'source':'code','start_line':1,'end_line':1}],**kw)


def encoded(f=None):return json.dumps({'findings':[] if f is None else [f]})


def enriched(tmp_path):return prepare([unit()],tmp_path/'inputs')[0][0]


def test_raw_normalized_separate_and_omission_retained(tmp_path):
    u=enriched(tmp_path);raw=plus.parse_findings(encoded(finding()),u)
    normalized=plus.extract_findings(raw,u)
    assert normalized[0]['evidence_spans'][0]['text']==u['task']['code']
    assert plus.validate_normalized(normalized,u,LABELS)==normalized
    with pytest.raises(ValueError):plus.parse_findings(encoded(normalized[0]),u)
    omitted={**finding(),'kind':'omission','location':'required output absent','evidence_refs':[]}
    assert plus.extract_findings(plus.parse_findings(encoded(omitted),u),u)[0]['evidence']==''
    with pytest.raises(ValueError):plus.parse_findings(encoded({**omitted,'kind':'defect'}),u)
    for key in ('evidence','evidence_spans'):
        bad=copy.deepcopy(normalized);bad[0][key]='tamper'
        with pytest.raises(ValueError):plus.validate_normalized(bad,u,LABELS)


def test_valid_coordinates_are_not_semantic_review(tmp_path):
    u=enriched(tmp_path);f={**finding(),'error':'A false initialization allegation accepted structurally.'}
    assert plus.parse_findings(encoded(f),u)==[f]


def test_payload_numbered_once_no_gold_and_l2_projection(tmp_path):
    u=enriched(tmp_path);u['task']['teacher_feedback']='SECRET';u['level']=2
    messages=plus.messages_findings(u,LABELS);p=json.loads(messages[1]['content'])
    assert 'code' not in p and p['sources']['code']['numbered_text']=='1 | '+u['task']['code']
    assert p['local_compiler']['standard']=='c++11' and p['local_compiler']['program_executed'] is False
    assert 'SECRET' not in str(messages) and 'requested_level' not in p
    fs=plus.extract_findings([finding()],u)
    body=json.loads(plus.messages_feedback(u,fs,LABELS,SPACE['feedback_level'])[1]['content'])
    assert set(body)=={'requested_level','level_rule','findings'}
    assert set(body['findings'][0])=={'problem_id','location','error'}
    assert plus.messages_feedback(u,fs,LABELS,SPACE['feedback_level'])[0]['content']==plus.LEVEL2_SYSTEM
    u['level']=3
    body=json.loads(plus.messages_feedback(u,fs,LABELS,SPACE['feedback_level'])[1]['content'])
    assert 'sources' in body and body['findings']==fs


def test_field_specific_recovery_and_exhaustion(tmp_path):
    u=enriched(tmp_path);f=finding();f['evidence_refs'][0]['end_line']=99
    backend=Backend([encoded(f),encoded(f)])
    rows=plus.run_units([u],backend,config(),tmp_path/'run',SPACE)
    assert rows[0]['status']=='unresolved' and rows[0]['output'] is None
    assert rows[0]['failure']['category']=='reference_contract'
    assert len(backend.calls)==2
    details=json.loads(backend.calls[1][-1]['content'])
    assert details['field_path']=='findings[0].evidence_refs[0].end_line'
    assert details['offending_value']==99 and details['allowed_sources']['code']==1
    assert 'parser_position' not in details
    assert plus.run_units([u],Backend([]),config(),tmp_path/'run',SPACE)[0]['status']=='unresolved'


def test_recovery_success_unknown_label_resolver_and_resume(tmp_path):
    u=enriched(tmp_path);f={**finding(),'labels':['runtime error']}
    b=Backend(['oops',encoded(f),'{"feedback":"Vòng lặp không tiến triển khi n dương."}'])
    rows=plus.run_units([u],b,config(),tmp_path/'run',SPACE)
    assert rows[0]['status']=='resolved' and len(b.calls)==3
    assert b.resolver_messages and 'evidence_spans' in b.resolver_messages[0][1]['content']
    assert plus.run_units([u],Backend([]),config(),tmp_path/'run',SPACE)==rows
    p=tmp_path/'run/results.private.json';saved=json.loads(p.read_text());saved[0]['stage1']['findings'][0]['evidence_spans'][0]['document_sha256']='tamper';p.write_text(json.dumps(saved))
    with pytest.raises(ValueError,match='mismatch'):plus.run_units([u],Backend([]),config(),tmp_path/'run',SPACE)


def test_renderer_failure_and_resume_never_reruns_detector(tmp_path):
    u=enriched(tmp_path);b=Backend([encoded(finding()),'bad','bad'])
    rows=plus.run_units([u],b,config(),tmp_path/'run',SPACE)
    assert rows[0]['stage1'] is not None and rows[0]['status']=='unresolved'
    assert len(b.calls)==3
    resumed=Backend([]);plus.run_units([u],resumed,config(),tmp_path/'run',SPACE);assert not resumed.calls


def test_level1_zero_renderer_and_context_failure(tmp_path):
    u=enriched(tmp_path);u['level']=1;b=Backend([encoded(finding())])
    assert plus.run_units([u],b,config(),tmp_path/'run',SPACE)[0]['status']=='resolved'
    assert len(b.calls)==1
    b=Backend([]);r=plus.run_units([u],b,{**config(),'context_limit':100},tmp_path/'small',SPACE)
    assert r[0]['failure']['category']=='context' and not b.calls


@pytest.mark.parametrize('field',['local_compiler','source_map_version','source_catalog'])
def test_input_identity_change_rejected(tmp_path,field):
    u=enriched(tmp_path);plus.run_units([u],Backend([encoded(),'{"feedback":"Chưa xác định vấn đề có căn cứ."}']),config(),tmp_path/'run',SPACE)
    u[field]=copy.deepcopy(u[field])
    if isinstance(u[field],dict):u[field]['changed']='changed'
    else:u[field]+='changed'
    with pytest.raises(ValueError):plus.run_units([u],Backend([]),config(),tmp_path/'run',SPACE)


def test_stale_final_file_removed_on_failed_export(tmp_path):
    from scripts.task3_arm_d_plus import validate_export
    from src.task3.dataset import write_json
    write_json(tmp_path/'predictions.json',[{'stale':True}]);write_json(tmp_path/'partial.predictions.json',[])
    with pytest.raises(ValueError):validate_export(tmp_path,{'fixture':SPACE['feedback_level'][1]['level']},LABELS)
    assert not (tmp_path/'predictions.json').exists()


def test_length_terminated_generation_keeps_raw_failure_context(tmp_path):
    from src.task3.inference import Generation
    u=enriched(tmp_path);b=Backend([]);calls=[]
    def generate(messages,cfg):
        calls.append(copy.deepcopy(messages))
        if len(calls)==1:return Generation('{"findings":[',7,.1,'length',False)
        return Generation('{"findings":[]}',8,.1,'eos',True)
    b.generate=generate;u['level']=1
    rows=plus.run_units([u],b,config(),tmp_path/'run',SPACE)
    assert rows[0]['status']=='resolved'
    assert json.loads(calls[1][-1]['content'])['invalid_response']=='{"findings":['
