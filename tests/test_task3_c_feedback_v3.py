"""Artificial stage2 contracts; actual Qwen Level/style measured by offline review."""
import importlib
import json
import pytest
from src.task3 import two_pass as v1
from src.task3.inference import MockTokenizer,Generation
from src.synth.feedback import FEEDBACK_LEVELS


@pytest.fixture
def c():
    class Lazy:
        def __getattr__(self,name):
            try:return getattr(importlib.import_module('src.task3.c_feedback_v3'),name)
            except ModuleNotFoundError:pytest.fail('new renderer missing')
    return Lazy()


def unit(sid='ARTIFICIAL-A',level=2):
    return dict(sample_id=sid,level=level,gold_feedback='SECRET-GOLD',task=dict(statement='Add two integers.',code='int result = a-b; // '+sid,
        exam_type='single_problem',problems=[],grading_policy='One problem.',compiler={'status':'unavailable'},tests={'status':'not_run','cases':[]},
        teacher_feedback='SECRET-TEACHER',reviewer='SECRET-REVIEWER',public_test='SECRET-PUBLIC'))


def defs():return [{'level':n,'định nghĩa':'OWN-RULE-'+str(i),'cấm':'OWN-FORBID-'+str(i)}for i,n in enumerate(FEEDBACK_LEVELS,1)]
def prediction(labels=None):
    labels=['Lỗi logic']if labels is None else labels
    return {'taxonomy_error':labels,'issues':[{'label':x,'note':'The active expression subtracts.'}for x in labels]}
CFG={'max_new_tokens':1024,'context_limit':20000,'generation_max_time_s':45}


class Backend:
    tokenizer=MockTokenizer()
    def __init__(self,values,out):self.values=iter(values);self.messages=[];self.out=out
    def generate(self,messages,config):
        sid=json.loads(messages[1]['content'])['sample_id']
        if self.messages and sid!=json.loads(self.messages[-1][1]['content'])['sample_id']:
            assert json.loads((self.out/'results.private.json').read_text())[-1]['sample_id']=='ARTIFICIAL-A'
        self.messages.append(messages);v=next(self.values)
        if isinstance(v,BaseException):raise v
        return Generation(v,10,.01,'eos',True)


def test_stage1_is_exact_v1_function_and_parser(c):
    assert c.stage1_messages is v1.messages_taxonomy and c.stage1_parse is v1.parse_taxonomy
    assert c.stage1_messages(unit())==v1.messages_taxonomy(unit())
    assert c.stage1_parse(json.dumps(prediction()))==v1.parse_taxonomy(json.dumps(prediction()))


@pytest.mark.parametrize('level',[1,2,3,4])
def test_one_requested_level_only_and_official_own_rule(c,level):
    ms=c.messages_feedback(unit(level=level),prediction(),defs());text=json.dumps(ms,ensure_ascii=False)
    assert [m['role']for m in ms]==['system','user']
    for i in [1,2,3,4]:assert ('OWN-RULE-'+str(i)in text)==(i==level)
    assert all(s not in text for s in ['SECRET-GOLD','SECRET-TEACHER','SECRET-REVIEWER','SECRET-PUBLIC'])
    assert 'NGUYÊN VĂN'in text and 'em'in text and 'bạn'in text
    assert json.loads(ms[1]['content'])['predicted']==prediction()
    assert len(ms[0]['content'].split())<260


@pytest.mark.parametrize('level',[2,3])
def test_clean_instruction_precedes_error_Level_instruction(c,level):
    system=c.messages_feedback(unit(level=level),prediction([]),defs())[0]['content']
    assert system.index('Bài đúng')<system.index('Bài có lỗi')
    assert 'không bịa lỗi'in system and 'tối ưu'in system


@pytest.mark.parametrize('level,word',[(1,'nguyên nhân'),(2,'thay thế'),(3,'khả thi')])
def test_specific_level_behavior_is_supplied(c,level,word):
    assert word in c.messages_feedback(unit(level=level),prediction(),defs())[0]['content']


def test_exact_two_call_order_and_saved_before_next_ID(c,tmp_path):
    us=[unit(),unit('ARTIFICIAL-B')];raw='  Em cần đối chiếu phép tính với yêu cầu.  '
    b=Backend([json.dumps(prediction()),json.dumps({'feedback':raw}),json.dumps(prediction([])),json.dumps({'feedback':'Em đã làm đúng.'})],tmp_path)
    result=c.run_units(us,b,CFG,tmp_path,defs())
    assert [json.loads(m[1]['content'])['sample_id']for m in b.messages]==['ARTIFICIAL-A']*2+['ARTIFICIAL-B']*2
    assert b.messages[0]==v1.messages_taxonomy(us[0])
    assert result[0]['output']=={'taxonomy_error':['Lỗi logic'],'feedback':raw}
    resumed=Backend([],tmp_path);assert c.run_units(us,resumed,CFG,tmp_path,defs())==result and not resumed.messages


def test_replay_does_not_generate_stage1_or_alter_its_value(c,tmp_path):
    pred=prediction();raw='Bạn hãy đổi phép trừ thành phép cộng.'
    b=Backend([json.dumps({'feedback':raw})],tmp_path)
    rows=c.run_units([unit()],b,CFG,tmp_path,defs(),replay={'ARTIFICIAL-A':pred})
    assert len(b.messages)==1 and json.loads(b.messages[0][1]['content'])['predicted']==pred
    assert rows[0]['output']['feedback']==raw and rows[0]['output']['taxonomy_error']==pred['taxonomy_error']
    assert rows[0]['stage1']==pred and rows[0]['replayed_stage1']


def test_inconsistent_frozen_stage1_is_unresolved_not_fixed(c,tmp_path):
    bad={'taxonomy_error':[],'issues':[{'label':'Lỗi logic','note':'Contradiction.'}]}
    b=Backend([],tmp_path);rows=c.run_units([unit()],b,CFG,tmp_path,defs(),replay={'ARTIFICIAL-A':bad})
    assert not b.messages and rows[0]['stage1_inconsistent']and rows[0]['output']is None
    assert rows[0]['stage1_observed']==bad and not(tmp_path/'predictions.json').exists()


def test_unsafe_nested_teacher_data_rejected_before_stage1(c,tmp_path):
    u=unit();u['task']['compiler']['teacher_feedback']='FORBIDDEN'
    b=Backend([],tmp_path);rows=c.run_units([u],b,CFG,tmp_path,defs())
    assert not b.messages and rows[0]['status']=='unresolved'


def test_interrupted_renderer_never_reissued(c,tmp_path):
    b=Backend([json.dumps(prediction()),KeyboardInterrupt()],tmp_path)
    with pytest.raises(KeyboardInterrupt):c.run_units([unit()],b,CFG,tmp_path,defs())
    b2=Backend([],tmp_path);rows=c.run_units([unit()],b2,CFG,tmp_path,defs())
    assert not b2.messages and rows[0]['status']=='unresolved'
