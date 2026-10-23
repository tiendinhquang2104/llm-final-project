"""Artificial contract and scheduling regressions; semantic quality is reviewed offline."""
import importlib
import json
from types import SimpleNamespace
from contextlib import nullcontext

import pytest
from src.task3.inference import Generation, MockTokenizer, HFBackend
from src.synth.feedback import FEEDBACK_LEVELS


@pytest.fixture
def v():
    class Lazy:
        def __getattr__(self,name):
            try:return getattr(importlib.import_module('src.task3.two_pass_v2'),name)
            except ModuleNotFoundError:pytest.fail('v2 module missing')
    return Lazy()


def unit(sid='ARTIFICIAL-A', level=2):
    return {'sample_id':sid,'level':level,'gold_taxonomy':['SECRET-GOLD'],'teacher':'SECRET-TEACHER',
            'task':{'statement':'Add two integers.','exam_type':'single_problem','problems':[],
                    'grading_policy':'Only the submitted problem.','code':'int result = a - b; // '+sid,
                    'gold_feedback':'NESTED-GOLD','reviewer':'SECRET-REVIEWER','public_test':'SECRET-PUBLIC',
                    'compiler':{'status':'unavailable','teacher_feedback':'EVIDENCE-TEACHER'},
                    'tests':{'status':'not_run','gold':'EVIDENCE-GOLD','cases':[]}}}


def definitions():
    return [{'level':n,'definition':'OWN RULE '+str(i)} for i,n in enumerate(FEEDBACK_LEVELS,1)]


def diagnosis(labels=None):
    labels=['Lỗi logic'] if labels is None else labels
    return {'taxonomy_error':labels,'issues':[{'label':x,'note':'The expression subtracts.'} for x in labels]}


class Backend:
    tokenizer=MockTokenizer()
    def __init__(self, values): self.values=iter(values); self.messages=[]
    def generate(self,messages,config):
        self.messages.append(messages)
        value=next(self.values)
        if isinstance(value,BaseException):raise value
        return Generation(value,12,.01,'eos',True)


CFG={'max_new_tokens':1024,'context_limit':20000,'generation_max_time_s':45}


@pytest.mark.parametrize('level',[2,3])
def test_clean_level2_or3_prompt_prioritizes_warranted_praise(v,level):
    ms=v.messages_feedback(unit(level=level),diagnosis([]),definitions())
    text='\n'.join(m['content'] for m in ms)
    assert 'em' in text and 'NGUYÊN VĂN' in text
    assert 'Không bịa lỗi' in text and 'không bịa tối ưu' in text
    p=json.loads(ms[1]['content'])
    assert p['clean_prediction'] is True and p['requested_level']==level
    assert p['level_rule']['definition']=='OWN RULE '+str(level)


@pytest.mark.parametrize('value',[
    {'taxonomy_error':[],'issues':[{'label':'Lỗi logic','note':'A contradiction.'}]},
    {'taxonomy_error':['Lỗi logic'],'issues':[]},
    {'taxonomy_error':['Lỗi logic'],'issues':[{'label':'Lỗi hàm','note':'Wrong label.'}]},
])
def test_structural_taxonomy_issue_inconsistency_is_not_repaired(v,value):
    before=json.dumps(value)
    with pytest.raises(v.InconsistencyError):v.parse_taxonomy(before)
    assert json.dumps(value)==before


def test_stage2_input_excludes_gold_teacher_reviewer_public(v):
    ms=v.messages_feedback(unit(),diagnosis(),definitions())
    text=json.dumps(ms)
    assert not any(s in text for s in ['SECRET-','NESTED-GOLD','EVIDENCE-TEACHER','EVIDENCE-GOLD'])
    assert json.loads(ms[1]['content'])['predicted']==diagnosis()
    assert [m['role'] for m in ms]==['system','user']


@pytest.mark.parametrize('level',[1,2,3,4])
def test_own_level_mapping_and_prohibitions_are_present(v,level):
    p=json.loads(v.messages_feedback(unit(level=level),diagnosis(),definitions())[1]['content'])
    assert p['level_rule']['level']==FEEDBACK_LEVELS[level-1]
    guidance=p['level_guidance']
    if level==1: assert 'vị trí' in guidance and 'nguyên nhân' in guidance and 'Không' in guidance
    if level==2: assert 'Không' in guidance and 'sửa' in guidance and 'ngầm' in guidance
    if level==3: assert 'khả thi' in guidance


def test_stage1_has_all_ten_label_distinctions_and_no_level(v):
    text=json.dumps(v.messages_taxonomy(unit()),ensure_ascii=False)
    assert 'requested_level' not in text and 'SECRET-' not in text
    for label in v.LABEL_SPACE:assert label in text
    for concept in ['cận lặp','tham số','chỉ số','gán cứng','style']:assert concept in text


@pytest.mark.parametrize('arm',['D','E'])
def test_two_stage_order_one_id_and_immutable_taxonomy(v,tmp_path,arm):
    units=[unit('ARTIFICIAL-A'),unit('ARTIFICIAL-B')]
    if arm=='D':
        for u in units:
            del u['task']['compiler']['teacher_feedback']; del u['task']['tests']['gold']
    b=Backend([json.dumps(diagnosis()),'{"feedback":"Em hãy đối chiếu phép tính với yêu cầu."}']*2)
    rows=v.run_arm(units,b,CFG,tmp_path,definitions(),arm)
    assert [(json.loads(m[1]['content'])['sample_id'],len(m))for m in b.messages]==[('ARTIFICIAL-A',2)]*2+[('ARTIFICIAL-B',2)]*2
    assert all(r['output']['taxonomy_error']==r['stage1']['taxonomy_error'] for r in rows)
    if arm=='D':
        from src.task3.two_pass import messages_feedback
        assert b.messages[1]==messages_feedback(units[0],diagnosis(),definitions())
    b2=Backend([])
    assert v.run_arm(units,b2,CFG,tmp_path,definitions(),arm)==rows and not b2.messages


def test_renderer_ablation_uses_frozen_stage1_and_records_inconsistent_id(v,tmp_path):
    units=[unit('ARTIFICIAL-A'),unit('ARTIFICIAL-B')]
    bad={'taxonomy_error':[],'issues':[{'label':'Lỗi logic','note':'A contradiction.'}]}
    frozen={'ARTIFICIAL-A':diagnosis([]),'ARTIFICIAL-B':bad}
    b=Backend(['{"feedback":"Em đã thực hiện đúng yêu cầu."}'])
    rows=v.run_arm(units,b,CFG,tmp_path,definitions(),'C',frozen)
    assert len(b.messages)==1 and rows[0]['stage1']==frozen['ARTIFICIAL-A']
    assert rows[1]['status']=='unresolved' and rows[1]['inconsistency'] is True
    assert rows[1]['output'] is None and not (tmp_path/'predictions.json').exists()


def test_bad_new_stage1_contract_skips_renderer_without_retry(v,tmp_path):
    bad={'taxonomy_error':[],'issues':[{'label':'Lỗi logic','note':'Contradiction.'}]}
    b=Backend([json.dumps(bad)])
    rows=v.run_arm([unit()],b,CFG,tmp_path,definitions(),'E')
    assert len(b.messages)==1 and rows[0]['inconsistency'] is True and rows[0]['status']=='unresolved'


def test_interrupted_second_generate_is_never_repeated(v,tmp_path):
    b=Backend([json.dumps(diagnosis()),KeyboardInterrupt()])
    with pytest.raises(KeyboardInterrupt):v.run_arm([unit()],b,CFG,tmp_path,definitions(),'E')
    resumed=Backend([]);rows=v.run_arm([unit()],resumed,CFG,tmp_path,definitions(),'E')
    assert not resumed.messages and rows[0]['status']=='unresolved'
    assert rows[0]['steps']['feedback']['origin']=='reserved_interrupted'


def test_old_renderer_ablation_rejects_unsafe_nested_input_before_generation(v,tmp_path):
    b=Backend([])
    rows=v.run_arm([unit()],b,CFG,tmp_path,definitions(),'D')
    assert not b.messages and rows[0]['status']=='unresolved'
    assert rows[0]['failure']['stage']=='input'


def test_v2_policy_and_level_metadata_cannot_carry_teacher_or_gold(v):
    u=unit();u['task']['grading_policy']={'prerequisites':'P1 first','teacher_feedback':'POLICY-SECRET'}
    rules=definitions();rules[1]['gold_feedback']='RULE-SECRET'
    text=json.dumps(v.messages_feedback(u,diagnosis(),rules))
    assert 'POLICY-SECRET' not in text and 'RULE-SECRET' not in text
    assert 'P1 first' in text


def test_freeze_integrity_requirement_cannot_be_disabled_by_optimized_python():
    import subprocess,sys
    result=subprocess.run([sys.executable,'-O','-c',
        "from scripts.task3_two_pass_v2 import require; require(False, 'blocked')"],capture_output=True,text=True)
    assert result.returncode!=0 and 'ValueError: blocked' in result.stderr


def test_level_violating_generated_text_is_not_semantically_retried(v,tmp_path):
    leak='Em hãy đổi phép trừ thành phép cộng.'
    b=Backend([json.dumps(diagnosis()),json.dumps({'feedback':leak})])
    rows=v.run_arm([unit(level=2)],b,CFG,tmp_path,definitions(),'E')
    assert len(b.messages)==2 and rows[0]['output']['feedback']==leak


def test_real_backend_serializes_roles_and_generation_prefix_and_decodes_only_suffix():
    import torch
    calls=[]
    class Inputs(dict):
        def to(self,device):return self
    class Tokenizer:
        pad_token_id=0
        def apply_chat_template(self,messages,**kwargs):
            calls.append((messages,kwargs));return Inputs(input_ids=torch.tensor([[11,12]]))
        def decode(self,ids,**kwargs):
            assert ids.tolist()==[13,14] and kwargs=={'skip_special_tokens':True}
            return '{"feedback":"Em đã thực hiện đúng yêu cầu."}'
    b=object.__new__(HFBackend);b.tokenizer=Tokenizer()
    b.torch=SimpleNamespace(cuda=SimpleNamespace(synchronize=lambda:None),inference_mode=nullcontext)
    b.model=SimpleNamespace(device='cpu',generation_config=SimpleNamespace(eos_token_id=14),
                            generate=lambda **kwargs:torch.tensor([[11,12,13,14]]))
    messages=[{'role':'system','content':'A teaching assistant.'},{'role':'user','content':'One artificial submission.'}]
    result=b.generate(messages,{'max_new_tokens':10,'do_sample':False})
    assert calls==[(messages,{'tokenize':True,'add_generation_prompt':True,'return_tensors':'pt','return_dict':True})]
    assert result.text.startswith('{"feedback"') and result.output_tokens==2
