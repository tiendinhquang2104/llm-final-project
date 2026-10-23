"""Artificial fixtures verify runner contracts, never Qwen semantic quality."""
import copy
import importlib
import json

import pytest
from src.task3.inference import Generation, MockTokenizer
from src.task3.submission import validate_submission
from src.synth.feedback import FEEDBACK_LEVELS

LABELS=['Lỗi biên dịch','Lỗi nhập/xuất','Lỗi logic','Lỗi vòng lặp','Lỗi mảng/chuỗi','Lỗi hàm','Lỗi edge case','Lỗi thuật toán','Lỗi hard-code','Lỗi style']
SPACE={'taxonomy_error':LABELS,'feedback_level':[{'level':n,'định nghĩa':f'OWN{i}','cấm':f'BAN{i}'}for i,n in enumerate(FEEDBACK_LEVELS,1)]}
CFG={'max_new_tokens':1024,'findings_max_new_tokens':1536,'context_limit':30000,'generation_max_time_s':45,'seed':42}

@pytest.fixture
def t():
    try:return importlib.import_module('src.task3.two_pass_findings')
    except ModuleNotFoundError:pytest.fail('new findings arm not implemented')

def unit(sid='TEST-A',level=2):
    return {'sample_id':sid,'level':level,'family':'TEST', 'task':{'statement':'Compute sum.', 'exam_type':'single_problem',
        'problems':[], 'grading_policy':'one problem', 'code':f'int x=a-b; // {sid}',
        'compiler':{'status':'unavailable','diagnostic':'','gold':'NESTED'},'tests':{'status':'not_run','cases':[],'feedback':'NESTED'}},
        'gold_taxonomy':['SECRET'],'gold_feedback':'SECRET','reviewer':'SECRET'}

def finding(label='Lỗi logic'):
    return {'problem_id':'SINGLE','location':'expression','evidence':'a-b','error':'Difference instead of sum','label':label}

def first(fs=None):return json.dumps({'findings':[finding()]if fs is None else fs},ensure_ascii=False)

class Backend:
    tokenizer=MockTokenizer()
    def __init__(self,values,out,check=None):self.values=iter(values);self.calls=[];self.out=out;self.check=check
    def generate(self,messages,config):
        if self.check:self.check(len(self.calls),messages)
        self.calls.append((messages,config.copy()))
        assert (self.out/'reservations.jsonl').exists()
        v=next(self.values)
        if isinstance(v,BaseException):raise v
        return v if isinstance(v,Generation) else Generation(v,12,.01,'eos',True)

def test_stage1_allowlists_and_is_level_blind(t):
    u=unit();u['task']['problems']=[{'pid':'P1','statement':'Read','prototype':'read()', 'is_prerequisite_for':['P2'],'gold':'SECRET'}]
    text=json.dumps(t.messages_findings(u,LABELS),ensure_ascii=False)
    assert all(s not in text for s in ['SECRET','NESTED','requested_level','TEST-A"','gold','feedback_level','reviewer'])
    assert json.loads(t.messages_findings(u,LABELS)[1]['content'])['problems'][0]['is_prerequisite_for']==['P2']
    v=copy.deepcopy(u);v['level']=3
    assert t.messages_findings(v,LABELS)==t.messages_findings(u,LABELS)
    assert 'TEST-A' in text  # present only as untrusted code, never a model-facing ID

@pytest.mark.parametrize('fs,want',[([],[]),([finding(),finding()],['Lỗi logic']),([finding('Lỗi hard-code'),finding('Lỗi nhập/xuất'),finding()],['Lỗi nhập/xuất','Lỗi logic','Lỗi hard-code'])])
def test_union_official_order(t,fs,want):
    parsed=t.parse_findings(first(fs),LABELS)
    assert t.taxonomy(parsed,LABELS)==want

@pytest.mark.parametrize('bad',['oops','{"findings":null}','{"findings":[],"taxonomy_error":[]}',first([finding('logic')]),first([{**finding(),'evidence':3}]),first([{k:v for k,v in finding().items()if k!='problem_id'}]),'{"findings":[],"findings":[]}'])
def test_structural_errors_fail(t,bad):
    with pytest.raises(ValueError):t.parse_findings(bad,LABELS)

@pytest.mark.parametrize('level',[1,2,3,4])
def test_renderer_own_level_only_and_own_findings(t,level):
    ms=t.messages_feedback(unit(level=level),[finding()],LABELS,SPACE['feedback_level'])
    text=json.dumps(ms,ensure_ascii=False);payload=json.loads(ms[1]['content'])
    assert payload['level_rule']['định nghĩa']==f'OWN{level}'
    assert all(f'OWN{i}'not in text for i in range(1,5)if i!=level)
    assert payload['findings']==[finding()]and payload['taxonomy_error']==['Lỗi logic']
    assert 'SECRET'not in text and 'NESTED'not in text


def test_sequential_save_before_stage2_and_next_id(t,tmp_path):
    text='  Bạn nói "em".\nEm hãy đổi phép trừ thành cộng.  '
    def check(i,ms):
        if i==1:
            rows=json.loads((tmp_path/'results.private.json').read_text());assert rows[0]['stage1']['findings']==[finding()]
        if i==2:
            rows=json.loads((tmp_path/'results.private.json').read_text());assert rows[0]['status']=='resolved'
    b=Backend([first(),json.dumps({'feedback':text}),first([]),'{"feedback":"Em đã dùng phép tính."}'],tmp_path,check)
    rows=t.run_units([unit(),unit('TEST-B',3)],b,CFG,tmp_path,SPACE)
    assert len(b.calls)==4 and rows[0]['output']['feedback']==text
    assert [c['max_new_tokens']for m,c in b.calls]==[1536,1024,1536,1024]
    assert 'TEST-B'not in str(b.calls[0])and 'TEST-A'not in str(b.calls[2])
    assert rows[1]['output']['taxonomy_error']==[]
    validate_submission(tmp_path/'predictions.json',{'TEST-A':FEEDBACK_LEVELS[1],'TEST-B':FEEDBACK_LEVELS[2]})

@pytest.mark.parametrize('stage',[1,2])
def test_truncation_even_valid_json_unresolved_no_retry(t,tmp_path,stage):
    values=[Generation(first([]),1536,.01,'length',False)]if stage==1 else [first(),Generation('{"feedback":"ok"}',1024,.01,'length',False)]
    b=Backend(values,tmp_path);rows=t.run_units([unit()],b,CFG,tmp_path,SPACE)
    assert len(b.calls)==stage and rows[0]['status']=='unresolved'and rows[0]['output']is None
    assert 'truncat' in rows[0]['failure']['reason']
    assert not(tmp_path/'predictions.json').exists()
    assert len(json.loads((tmp_path/'results.private.json').read_text()))==1
    assert json.loads((tmp_path/'completed.predictions.json').read_text())==[]

@pytest.mark.parametrize('values,n',[[['oops'],1],[[first(),'{"feedback":"x","taxonomy_error":[]}'],2]])
def test_failure_does_not_become_clean_or_fallback(t,tmp_path,values,n):
    b=Backend(values,tmp_path);rows=t.run_units([unit()],b,CFG,tmp_path,SPACE)
    assert len(b.calls)==n and rows[0]['output']is None and rows[0]['status']=='unresolved'

@pytest.mark.parametrize('change',['code','level','evidence','config','label_order','tokenizer'])
def test_resume_rejects_provenance_drift(t,tmp_path,change):
    b=Backend([first(),'{"feedback":"Original"}'],tmp_path);t.run_units([unit()],b,CFG,tmp_path,SPACE)
    u=unit();cfg=CFG.copy();space=copy.deepcopy(SPACE);b2=Backend([],tmp_path)
    if change=='code':u['task']['code']+=' extra'
    if change=='level':u['level']=1
    if change=='evidence':u['task']['compiler']['diagnostic']='different'
    if change=='config':cfg['seed']=0
    if change=='label_order':space['taxonomy_error'].reverse()
    if change=='tokenizer':b2.tokenizer=copy.copy(MockTokenizer());b2.tokenizer.chat_template='changed'
    with pytest.raises(ValueError):t.run_units([u],b2,cfg,tmp_path,space)
    assert not b2.calls


def test_resume_reuses_without_new_generate(t,tmp_path):
    b=Backend([first(),'{"feedback":"Original"}'],tmp_path);a=t.run_units([unit()],b,CFG,tmp_path,SPACE)
    b2=Backend([],tmp_path);assert t.run_units([unit()],b2,CFG,tmp_path,SPACE)==a
    assert not b2.calls


def test_interrupted_reservation_never_reissued(t,tmp_path):
    b=Backend([KeyboardInterrupt()],tmp_path)
    with pytest.raises(KeyboardInterrupt):t.run_units([unit()],b,CFG,tmp_path,SPACE)
    b2=Backend([],tmp_path);rows=t.run_units([unit()],b2,CFG,tmp_path,SPACE)
    assert not b2.calls and rows[0]['status']=='unresolved'


def test_context_overflow_no_truncation_or_generate(t,tmp_path):
    b=Backend([],tmp_path);rows=t.run_units([unit()],b,{**CFG,'context_limit':1},tmp_path,SPACE)
    assert len(rows)==1 and rows[0]['status']=='unresolved'and not b.calls

@pytest.mark.parametrize('target',['policy','problem','compiler','test_case','level_rule'])
def test_nested_metadata_cannot_enter_allowed_prompt_fields(t,target):
    u=unit();space=copy.deepcopy(SPACE)
    poison={'gold_feedback':'NESTED-SECRET','requested_level':4}
    if target=='policy':u['task']['grading_policy']={'prerequisites':[poison]}
    if target=='problem':u['task']['problems']=[{'pid':'P1','prerequisites':[poison]}]
    if target=='compiler':u['task']['compiler']['diagnostic']=poison
    if target=='test_case':u['task']['tests']['cases']=[{'input':poison}]
    if target=='level_rule':space['feedback_level'][1]['định nghĩa']=poison
    with pytest.raises(ValueError):
        t.messages_feedback(u,[finding()],LABELS,space['feedback_level'])if target=='level_rule'else t.messages_findings(u,LABELS)

@pytest.mark.parametrize('field',['statement','code','exam_type'])
def test_task_text_cannot_be_a_record(t,field):
    u=unit();u['task'][field]={'gold':'SECRET'}
    with pytest.raises(ValueError):t.messages_findings(u,LABELS)


def test_level_rule_matches_name_even_if_file_order_changes(t):
    definitions=list(reversed(SPACE['feedback_level']))
    payload=json.loads(t.messages_feedback(unit(level=2),[finding()],LABELS,definitions)[1]['content'])
    assert payload['level_rule']['định nghĩa']=='OWN2'
