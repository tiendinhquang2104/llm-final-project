"""Scripted artificial model returns test orchestration, never model accuracy."""
import importlib
import json
from pathlib import Path

import pytest
from src.task3 import compact as c
from src.task3 import grounded as g
from src.task3.grounded_runner import Journal
from src.task3.inference import Generation,MockTokenizer


@pytest.fixture
def runner():
    class Lazy:
        def __getattr__(self,name):
            try:return getattr(importlib.import_module('src.task3.compact_runner'),name)
            except ModuleNotFoundError:pytest.fail('compact runner missing')
    return Lazy()


def unit(multi=False):
    return dict(request_id='artificial',sample_id='artificial',level=2,task=dict(
        statement='Print the required sum.',exam_type='multi_problem'if multi else 'single_problem',
        problems=[{'pid':p,'statement':'Artificial requirement'}for p in ['P1','P2','P3','P4']]if multi else [],
        grading_policy=g.SUPPORTED_PREREQUISITE if multi else {},code='int value=0;',
        compiler={'status':'unavailable','diagnostic':''},tests={'status':'not_run','cases':[]}))


def diagnosis(scope='whole'):
    return dict(verdict='error',reason='Verified fixture arithmetic conflict.',findings=[dict(scope=scope,
        quote='value=0',observed='Trả về hằng0.',conflict='Không phụ thuộc dữ liệu.',when='Tổng khác0.',labels=['Lỗi hard-code'])])


class ScriptedBackend:
    tokenizer=MockTokenizer()
    def __init__(self,values):self.values=iter(values);self.calls=0
    def generate(self,messages,config):
        self.calls+=1;value=next(self.values)
        return Generation(json.dumps(value,ensure_ascii=False),10,0.01,'eos',True)


def journal(tmp_path,values):
    backend=ScriptedBackend(values)
    return Journal(tmp_path,backend,dict(max_new_tokens=1000,context_limit=20000,diagnosis_max_attempts=2,feedback_max_attempts=2),binding='artificial'),backend


def test_p1_failure_blocks_all_later_scopes(runner,tmp_path):
    j,b=journal(tmp_path,[diagnosis('P1'),{'clean_supported':False,'findings':[{'id':'F1','supported':True}]}])
    d=runner.diagnose(unit(True),j)
    assert d['publishable'] and d['scope']['blocked']==['P2','P3','P4'] and b.calls==2


def test_uncertain_p1_never_marks_later_scopes_clean(runner,tmp_path):
    v={'verdict':'uncertain','reason':'Evidence insufficient.','findings':[]}
    j,b=journal(tmp_path,[v,v])
    d=runner.diagnose(unit(True),j)
    assert d['status']=='candidate_unverified' and not d['publishable']
    assert d['scope']['unassessed']==['P2','P3','P4'] and b.calls==2


def test_resume_no_new_calls_and_no_status_conversion(runner,tmp_path):
    values=[diagnosis(),{'clean_supported':False,'findings':[{'id':'F1','supported':True}]}]
    j,b=journal(tmp_path,values);first=runner.diagnose(unit(),j)
    j2,b2=journal(tmp_path,[]);second=runner.diagnose(unit(),j2)
    assert first==second and b2.calls==0


def test_guard_rejects_implicit_repair_without_regex(runner):
    verdict=dict(supported=True,level_compliant=False,main_covered=True,natural_vietnamese=True,reason_codes=['L2_IMPLICIT_REPAIR'])
    assert not runner.guard_accept(json.dumps(verdict))
    verdict.update(level_compliant=True,reason_codes=[])
    assert runner.guard_accept(json.dumps(verdict))


def test_rescue_does_not_call_r15_placeholder_controller(runner,tmp_path):
    # Repeated direct repair leaks must stay unresolved; there is no fallback prose.
    j,b=journal(tmp_path,[{'taxonomy_error':['Lỗi logic'],'feedback':'```cpp\nx = 1;\n```'}]*2)
    result=runner.rescue(unit(),j)
    assert result['status']=='unresolved' and result['origin']=='rescue' and result.get('output')is None


def test_production_rejects_oracle_even_when_render_schema_valid(runner,tmp_path):
    d=c.parse(json.dumps(diagnosis()),unit()['task'],'whole');d['provenance']='offline_oracle'
    j,_=journal(tmp_path,[])
    with pytest.raises(ValueError):runner.render(unit(),d,j)


@pytest.mark.parametrize('problems',[[],[{'pid':'P1'},{'pid':'P1'}]])
def test_missing_or_duplicate_multi_scopes_cannot_be_clean(runner,tmp_path,problems):
    u=unit(True);u['task']['problems']=problems;u['task']['grading_policy']={}
    j,b=journal(tmp_path,[])
    with pytest.raises(ValueError):runner.diagnose(u,j)
    assert b.calls==0


def test_unguarded_c1_is_offline_only(runner,tmp_path):
    u=unit();d=c.parse(json.dumps(diagnosis()),u['task'],'whole');d['semantic_checked']=True
    feedback={'sentences':[{'text':'Bài này cần kiểm tra lại.','finding_ids':['F1']}]}
    rejected={'supported':True,'level_compliant':True,'main_covered':False,'natural_vietnamese':True,'reason_codes':['MAIN_ERROR_MISSING']}
    j,b=journal(tmp_path,[feedback,rejected,feedback,rejected])
    result=runner.render(u,d,j,arm='C1')
    assert result['status']=='unresolved' and b.calls==4


def test_successful_rescue_keeps_origin_support_and_resumes(runner,tmp_path):
    output={'taxonomy_error':['Lỗi hard-code'],'feedback':'Ở phần tính kết quả, giá trị luôn bằng không và không phụ thuộc dữ liệu.'}
    semantic={'clean_supported':False,'findings':[{'id':'F1','supported':True}]}
    guard={'supported':True,'level_compliant':True,'main_covered':True,'natural_vietnamese':True,'reason_codes':[]}
    j,b=journal(tmp_path,[output,diagnosis(),semantic,guard])
    result=runner.rescue(unit(),j)
    assert result['status']=='resolved' and result['origin']=='rescue'
    assert result['output']==output and result['sentence_support'][0]['finding_ids']==['F1']
    j2,b2=journal(tmp_path,[])
    assert runner.rescue(unit(),j2)==result and b2.calls==0
