"""Software fixtures, not claims about Qwen content quality."""
import copy
import json
import pytest
from src.task3 import two_pass_findings as old
from tests.test_task3_two_pass_findings import Backend, CFG, LABELS, SPACE, unit, finding, first
from src.task3.inference import Generation
from src.task3 import language_precision_ablation as new


def test_matrix_and_original_vi_bytes():
    assert list(new.ARMS)==list('ABCD')
    configs=[new.arm_config(a) for a in new.ARMS]
    assert [(c['language'],c['load_in_4bit']) for c in configs]==[('vi',True),('en',True),('vi',False),('en',False)]
    common=[{k:v for k,v in c.items() if k not in ('arm','language','load_in_4bit')} for c in configs]
    assert all(c==common[0] for c in common)
    assert new.bundle('vi')==dict(findings=old.FINDINGS_SYSTEM,feedback=old.FEEDBACK_SYSTEM,guidance=old.GUIDANCE)
    for token in ['em','bạn','mình','thầy','tôi','Chương trình cần được kiểm tra lại']:
        assert token in new.bundle('en')['feedback']

@pytest.mark.parametrize('language',['vi','en'])
@pytest.mark.parametrize('level',[1,2,3,4])
def test_payload_schema_roles_and_level(language,level):
    u=unit(level=level)
    ms=new.messages_findings(u,LABELS,language)
    assert [m['role'] for m in ms]==['system','user']
    assert ms[1]==old.messages_findings(u,LABELS)[1]
    assert 'requested_level' not in ms[1]['content'] and 'SECRET' not in str(ms)
    fb=new.messages_feedback(u,[finding()],LABELS,SPACE['feedback_level'],language)
    body=json.loads(fb[1]['content']); original=json.loads(old.messages_feedback(u,[finding()],LABELS,SPACE['feedback_level'])[1]['content'])
    assert {k:v for k,v in body.items() if k!='guidance'}=={k:v for k,v in original.items() if k!='guidance'}
    assert body['level_rule']['định nghĩa']==f'OWN{level}'
    if language=='vi':assert fb==old.messages_feedback(u,[finding()],LABELS,SPACE['feedback_level'])

@pytest.mark.parametrize('language',['vi','en'])
@pytest.mark.parametrize('bad',['{"findings":"bad"}',first([finding('logic')]),'{"findings":["\\q"]}',Generation(first([]),4,.01,'length',False)])
def test_stage1_invalid_never_calls_stage2(tmp_path,language,bad):
    cfg={**CFG,'arm':'TEST','language':language,'load_in_4bit':True}
    b=Backend([bad],tmp_path)
    rows=new.run_arm([unit()],b,cfg,tmp_path,SPACE)
    assert len(b.calls)==1 and len(rows)==1 and rows[0]['status']=='unresolved' and rows[0]['output'] is None


def test_empty_union_verbatim_feedback_and_resume(tmp_path):
    text='  Bạn nói "em".\nChương trình cần được kiểm tra lại.  '
    cfg={**CFG,'arm':'A','language':'vi','load_in_4bit':True}
    b=Backend([first([]),json.dumps({'feedback':text})],tmp_path)
    rows=new.run_arm([unit()],b,cfg,tmp_path,SPACE)
    assert rows[0]['output']=={'taxonomy_error':[],'feedback':text}
    assert [c['max_new_tokens'] for _,c in b.calls]==[1536,1024]
    assert json.loads(b.calls[1][0][1]['content'])['findings']==[]
    b2=Backend([],tmp_path); assert new.run_arm([unit()],b2,cfg,tmp_path,SPACE)==rows and not b2.calls
    for delta in [{'arm':'C','load_in_4bit':False},{'language':'en'}]:
        with pytest.raises(ValueError):new.run_arm([unit()],b2,{**cfg,**delta},tmp_path,SPACE)


def test_interrupted_reservation_not_reissued(tmp_path):
    cfg={**CFG,'arm':'A','language':'vi','load_in_4bit':True}
    b=Backend([KeyboardInterrupt()],tmp_path)
    with pytest.raises(KeyboardInterrupt):new.run_arm([unit()],b,cfg,tmp_path,SPACE)
    b2=Backend([],tmp_path); rows=new.run_arm([unit()],b2,cfg,tmp_path,SPACE)
    assert not b2.calls and rows[0]['status']=='unresolved'


def test_ordered_union_and_arm_specific_findings(tmp_path):
    fs=[finding('Lỗi hard-code'),finding('Lỗi nhập/xuất'),finding('Lỗi hard-code')]
    cfg={**CFG,'arm':'B','language':'en','load_in_4bit':True}
    b=Backend([first(fs),'{"feedback":"Nguyên văn."}'],tmp_path)
    rows=new.run_arm([unit()],b,cfg,tmp_path,SPACE)
    payload=json.loads(b.calls[1][0][1]['content'])
    assert payload['findings']==fs and payload['taxonomy_error']==['Lỗi nhập/xuất','Lỗi hard-code']
    assert rows[0]['stage1']['findings']==fs


def test_full_denominator_and_null_prediction_policy(tmp_path):
    from scripts.task3_language_precision_ablation import arm_metrics
    rows=[{'sample_id':'x','status':'unresolved','stage1':{'findings':[],'taxonomy_error':[]},'output':None,'failure':{'stage':'feedback','reason':'bad'}}]
    metrics=arm_metrics(rows,{'x':[]},tmp_path)
    assert metrics['completed']==0 and metrics['taxonomy']['exact_count']==0
    assert metrics['stage1_taxonomy']['exact_count']==1
    assert metrics['taxonomy']['macro_f1']==0
