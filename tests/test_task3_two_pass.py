"""Artificial one-ID scheduling and structural-contract tests."""
import importlib
import json
from pathlib import Path

import pytest
from src.task3.inference import Generation,MockTokenizer
from src.task3.submission import validate_submission
from src.synth.feedback import FEEDBACK_LEVELS


@pytest.fixture
def t():
    class Lazy:
        def __getattr__(self,name):
            try:return getattr(importlib.import_module('src.task3.two_pass'),name)
            except ModuleNotFoundError:pytest.fail('two-pass module missing')
    return Lazy()


def unit(sid='TEST-A',level=2):
    return dict(sample_id=sid,level=level,task=dict(statement='Add two integers.',exam_type='single_problem',
        problems=[],grading_policy={},code='int answer = a - b; // '+sid,
        compiler={'status':'unavailable','diagnostic':''},tests={'status':'not_run','cases':[]}),
        gold_taxonomy=['SECRET-GOLD'],gold_feedback='SECRET-TEACHER',reviewer='SECRET-REVIEW')


def first(labels=None):
    return json.dumps({'taxonomy_error':['Lỗi logic']if labels is None else labels,
                       'issues':[{'label':'Lỗi logic','note':'Phép tính trả hiệu thay vì tổng.'}]if labels is None else []},ensure_ascii=False)


class Backend:
    tokenizer=MockTokenizer()
    def __init__(self,values,out):self.values=iter(values);self.messages=[];self.out=out
    def generate(self,messages,config):
        self.messages.append(messages)
        reservations=[json.loads(x)for x in (self.out/'reservations.jsonl').read_text().splitlines()]
        assert len(reservations)==len(self.messages)
        value=next(self.values)
        if isinstance(value,BaseException):raise value
        return Generation(value,12,.01,'eos',True)


def config():return dict(max_new_tokens=1024,generation_max_time_s=45,context_limit=20000)


def levels():return [{'level':name,'định nghĩa':'RULE'+str(i),'cấm':'FORBID'+str(i)}for i,name in enumerate(FEEDBACK_LEVELS,1)]


def test_one_sample_each_call_and_no_shared_history(t,tmp_path):
    units=[unit('TEST-A'),unit('TEST-B')]
    b=Backend([first(),'{"feedback":"Phép tính cho hiệu nên kết quả lệch yêu cầu tổng."}',first([]),'{"feedback":"Bài làm phù hợp."}'],tmp_path)
    result=t.run_units(units,b,config(),tmp_path,levels())
    assert [(json.loads(ms[1]['content'])['sample_id'],len(ms))for ms in b.messages]==[('TEST-A',2),('TEST-A',2),('TEST-B',2),('TEST-B',2)]
    assert 'TEST-B'not in json.dumps(b.messages[0]) and 'TEST-A'not in json.dumps(b.messages[2])
    assert result[0]['output']['taxonomy_error']==['Lỗi logic'] and result[1]['output']['taxonomy_error']==[]
    assert 'predicted'not in json.loads(b.messages[0][1]['content'])
    assert json.loads(b.messages[1][1]['content'])['predicted']['taxonomy_error']==['Lỗi logic']
    assert (tmp_path/'predictions.json').exists()


def test_no_gold_teacher_reviewer_or_level_in_first_prompt(t):
    u=unit();u['task'].update(gold_taxonomy=['NESTED-GOLD'],feedback='NESTED-TEACHER',requested_level=2)
    text=json.dumps(t.messages_taxonomy(u),ensure_ascii=False)
    assert all(x not in text for x in ['SECRET-GOLD','SECRET-TEACHER','SECRET-REVIEW','NESTED-GOLD','NESTED-TEACHER','requested_level'])


@pytest.mark.parametrize('level',[1,2,3,4])
def test_second_stage_uses_own_level_and_actual_prediction(t,level):
    payload=json.loads(t.messages_feedback(unit(level=level),json.loads(first()),levels())[1]['content'])
    assert payload['requested_level']==level and payload['level_rule']['định nghĩa']=='RULE'+str(level)
    assert payload['level_rule']['cấm']=='FORBID'+str(level)
    assert payload['predicted']==json.loads(first())


@pytest.mark.parametrize('bad',['broken JSON','{"taxonomy_error":["syntax_error"],"issues":[]}','{"taxonomy_error":null,"issues":[]}'])
def test_bad_first_stage_skips_second_and_never_becomes_clean(t,tmp_path,bad):
    b=Backend([bad],tmp_path);result=t.run_units([unit()],b,config(),tmp_path,levels())
    assert len(b.messages)==1 and result[0]['status']=='unresolved' and result[0].get('output')is None
    assert not (tmp_path/'predictions.json').exists()


def test_bad_second_stage_no_retry_or_label_change(t,tmp_path):
    b=Backend([first(),'{"feedback":"x","taxonomy_error":[]}'],tmp_path)
    result=t.run_units([unit()],b,config(),tmp_path,levels())
    assert len(b.messages)==2 and result[0]['status']=='unresolved'
    assert result[0]['stage1']['taxonomy_error']==['Lỗi logic']


def test_notes_semantics_do_not_trigger_new_gate(t):
    value={'taxonomy_error':[],'issues':[{'label':'Lỗi logic','note':'A disputed but structurally valid note.'}]}
    assert t.parse_taxonomy(json.dumps(value))==value


def test_level_leak_is_retained_for_offline_review_not_model_retry(t,tmp_path):
    text='Em hãy đổi phép trừ sang phép cộng.'
    b=Backend([first(),json.dumps({'feedback':text})],tmp_path)
    result=t.run_units([unit()],b,config(),tmp_path,levels())
    assert len(b.messages)==2 and result[0]['output']=={'taxonomy_error':['Lỗi logic'],'feedback':text}
    validate_submission(tmp_path/'predictions.json',{'TEST-A':FEEDBACK_LEVELS[1]})


def test_single_json_fence_only(t):
    assert t.parse_taxonomy('```json\n'+first()+'\n```')==json.loads(first())
    with pytest.raises(ValueError):t.parse_taxonomy('```json\n'+first()[:-2])


def test_resume_does_not_repeat_calls_and_detects_changed_source(t,tmp_path):
    b=Backend([first(),'{"feedback":"Nhận xét cụ thể."}'],tmp_path)
    result=t.run_units([unit()],b,config(),tmp_path,levels())
    b2=Backend([],tmp_path)
    assert t.run_units([unit()],b2,config(),tmp_path,levels())==result and not b2.messages
    changed=unit();changed['task']['code']+=' changed'
    with pytest.raises(ValueError):t.run_units([changed],b2,config(),tmp_path,levels())


def test_interrupted_reserved_generate_is_never_reissued(t,tmp_path):
    b=Backend([KeyboardInterrupt()],tmp_path)
    with pytest.raises(KeyboardInterrupt):t.run_units([unit()],b,config(),tmp_path,levels())
    resumed=Backend([],tmp_path);result=t.run_units([unit()],resumed,config(),tmp_path,levels())
    assert not resumed.messages and result[0]['status']=='unresolved'


def test_raw_precedes_parser(t,tmp_path,monkeypatch):
    module=importlib.import_module('src.task3.two_pass')
    original=module.parse_taxonomy
    def checked(raw):
        rows=[json.loads(x)for x in (tmp_path/'attempts.jsonl').read_text().splitlines()]
        assert rows[-1]['raw_text']==raw
        return original(raw)
    monkeypatch.setattr(module,'parse_taxonomy',checked)
    b=Backend([first(),'{"feedback":"Nhận xét."}'],tmp_path)
    assert t.run_units([unit()],b,config(),tmp_path,levels())[0]['status']=='resolved'


def test_fixed_hybrid_replaces_whole_pair(t):
    failed={'sample_id':'TEST-A','status':'unresolved','stage1':{'taxonomy_error':['Lỗi logic']}}
    control=[{'sample_id':'TEST-A','output':{'taxonomy_error':[],'feedback':'R15 original pair'}}]
    result=t.hybrid([failed],control)
    assert result[0]['output']==control[0]['output']


def test_cli_records_zero_calls_if_every_source_overflows_context(tmp_path,monkeypatch):
    from scripts import task3_two_pass as cli
    from src.task3 import inference
    from types import SimpleNamespace
    out=tmp_path;frozen=out/'frozen';frozen.mkdir()
    (frozen/'freeze.json').write_text('{}')
    (frozen/'level-definitions.json').write_text(json.dumps(levels()))
    (out/'units.private.json').write_text(json.dumps([unit()]))
    control=[{'sample_id':'TEST-A','output':{'taxonomy_error':[],'feedback':'Original R15'}}]
    (out/'control.private.json').write_text(json.dumps(control))
    cfg={**config(),'context_limit':1,'minimum_free_gpu_mib':1}
    b=Backend([],out/'B');b.model=SimpleNamespace(generation_config=SimpleNamespace())
    b.runtime_metadata=lambda: {'artificial_test_only':True}
    monkeypatch.setattr(cli,'OUT',out)
    monkeypatch.setattr(cli,'verify',lambda: {'config':cfg,'tokenizer':inference.tokenizer_metadata(b.tokenizer)})
    monkeypatch.setattr(cli.subprocess,'check_output',lambda *a,**k:'32000\n')
    monkeypatch.setattr(inference,'load_tokenizer',lambda config:b.tokenizer)
    monkeypatch.setattr(inference,'HFBackend',lambda config,tokenizer:b)
    cli.run()
    summary=json.loads((out/'run.private.json').read_text())
    assert summary['unresolved']==1 and summary['model_reservations']==0 and summary['maximum_calls_per_ID']==0
    assert json.loads((out/'development.hybrid.predictions.json').read_text())==control
