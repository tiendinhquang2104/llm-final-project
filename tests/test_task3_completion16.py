import copy
import json
from pathlib import Path
import pytest

from src.task3 import completion16 as c
from src.task3 import arm_d_plus_v15 as old
from src.task3.source_refs import build_catalog,VERSION
from src.task3.inference import MockTokenizer,Generation


def unit():
    code='int f(){\n return 1;\n}\n'
    return dict(sample_id='unit',level=2,family='test',source_map_version=VERSION,local_compiler={},task=dict(code=code,statement='Provide f returning1.',exam_type='single_problem',problems=[dict(pid='P1')]),source_catalog=build_catalog(code))


def finding():
    return dict(problem_id='P1',kind='defect',location='f',error='The function is faulty.',labels=['Lỗi logic'],evidence_refs=[dict(source='code',start_line=2,end_line=2)])


def row(fs,finish='eos'):
    return dict(raw_text=json.dumps(dict(findings=fs)),finish_reason=finish,error=None)


def test_inventory_all_invalid_fields_not_first_only():
    f=finding();f['kind']='logic';f['evidence_refs']=[dict(source='code',start_line=99,end_line=99),dict(source='code',start_line=0,end_line=1)]
    r=c.inventory(row([f]),unit())
    assert [v['field'] for v in r['violations']]==['kind','reference','reference']
    assert r['findings']==[f]


def test_truncated_prefix_never_becomes_inventory_findings():
    r=c.inventory(row([],finish='length'),unit())
    assert r['findings'] is None and r['route']=='length'


def test_kind_selection_preserves_unrelated_fields_and_findings():
    f=finding();f['kind']='logic';other=finding();other['error']='A different claim.'
    original=[f,other];fixed=c.apply_field(original,0,'kind','defect')
    assert fixed[0]=={**f,'kind':'defect'} and fixed[1]==other and original[0]['kind']=='logic'
    with pytest.raises(ValueError):c.apply_field(original,0,'kind',None)


def test_reference_replacement_no_clamping_or_valid_field_change():
    f=finding();f['evidence_refs'].append(dict(source='code',start_line=99,end_line=99))
    r=c.apply_field([f],0,'reference',dict(source='code',start_line=1,end_line=2),1)
    assert r[0]['evidence_refs'][0]==f['evidence_refs'][0]
    assert r[0]['location']==f['location'] and f['evidence_refs'][1]['start_line']==99


def test_scope_coverage_requires_all_frozen_scopes_and_only_exact_dedup():
    f=finding();different={**f,'error':'Different supported claim.'}
    scopes=[dict(scope_id='one'),dict(scope_id='integration')]
    with pytest.raises(ValueError):c.merge_scopes(scopes,{'one':[f]})
    merged,provenance=c.merge_scopes(scopes,{'one':[f],'integration':[f,different]})
    assert merged==[f,different] and provenance[0]['scopes']==['one','integration']


def test_reassessment_replaces_only_recorded_failed_indices():
    fs=[finding(),{**finding(),'error':'Other unchanged claim.'}]
    r,a=c.replace_reassessed(fs,{0},[])
    assert r==[fs[1]] and a['removed_indices']==[0] and a['reassessment_no_supported_issue']
    with pytest.raises(ValueError):c.replace_reassessed(fs,{0},None)


def test_single_problem_function_scopes_include_integration_and_globals():
    u=unit();u['task']['code']='int g;\nvoid swap(int &a,int &b)\n{ int t=a;a=b;b=t; }\nint main(){return 0;}\n'
    scopes=c.build_scopes(u)
    assert any(s['focus']=='swap' for s in scopes)
    assert any(s['focus']=='main' for s in scopes)
    assert scopes[-1]['scope_id']=='integration'


def test_canonical_312_identity_and_merge_reject_mutation():
    a=dict(sample_id='a',output=dict(taxonomy_error=[],feedback='Nội dung gốc.'))
    b=dict(sample_id='b',output=dict(taxonomy_error=[],feedback='Mới.'))
    hashes={'a':c.object_hash(a['output'])}
    assert c.merge_outputs([a],[b],['b','a'],hashes)==[b,a]
    with pytest.raises(ValueError):c.merge_outputs([{**a,'output':{**a['output'],'feedback':'Changed'}}],[b],['a','b'],hashes)
    with pytest.raises(ValueError):c.merge_outputs([a],[b,b],['a','b'],hashes)


class Backend:
    tokenizer=MockTokenizer()
    def __init__(self):self.calls=0
    def generate(self,messages,config):self.calls+=1;return Generation('{"findings":[]}',5,.001,'eos',True)


def test_journal_resume_and_frozen_case_budget(tmp_path):
    b=Backend();config=dict(context_limit=10000,findings_max_new_tokens=1536,max_new_tokens=1024)
    j=c.RecoveryJournal(tmp_path,b,config,'identity',{'unit':{'total_calls':1}})
    m=[dict(role='user',content='data')]
    assert j.call('unit','taxonomy',m)['raw_text']=='{"findings":[]}'
    assert j.call('unit','taxonomy',m)['raw_text']=='{"findings":[]}' and b.calls==1
    with pytest.raises(ValueError):j.call('unit','taxonomy',m,attempt=1)
    assert b.calls==1


def test_journal_prompt_drift_stops_as_infrastructure(tmp_path):
    b=Backend();config=dict(context_limit=10000,findings_max_new_tokens=1536,max_new_tokens=1024)
    j=c.RecoveryJournal(tmp_path,b,config,'identity',{'unit':{'total_calls':2}})
    j.call('unit','taxonomy',[dict(role='user',content='data')])
    with pytest.raises(ValueError) as caught:
        j.call('unit','taxonomy',[dict(role='user',content='changed')])
    assert getattr(caught.value,'category',None)=='infrastructure' and b.calls==1


class ScopeJournal:
    backend=Backend()
    config=dict(context_limit=100000,findings_max_new_tokens=1536,max_new_tokens=1024)
    def __init__(self,out,answers):self.out=out;self.answers=iter(answers);self.calls=[]
    def call(self,sid,stage,messages,**kwargs):
        self.calls.append((stage,messages,kwargs))
        return dict(next(self.answers),key=str(len(self.calls)))


def test_nonobject_scope_finding_uses_bounded_structural_followup(tmp_path):
    j=ScopeJournal(tmp_path,[row([None]),row([])])
    r=c.Recoverer(unit(),j,[],list(old.DEFINITIONS),dict(budget={'generated_field_slots':16}))
    assert r.generate_scope(dict(scope_id='problem:P1',problem_ids=['P1']),'length')==[]
    assert len(j.calls)==2 and j.calls[-1][2]['attempt']==1


def test_failed_length_claims_coalesced_before_single_problem_reassessment(monkeypatch):
    scopes=[dict(scope_id='function:f',problem_ids=['P1']),dict(scope_id='integration',problem_ids=['P1'])]
    r=c.Recoverer(unit(),None,[],list(old.DEFINITIONS),dict(scopes=scopes))
    one=finding();two={**finding(),'error':'Second unsupported claim.'}
    seen=[]
    def generated(scope,purpose,prior=None):
        if purpose=='reassessment':
            seen.append(prior);r.ledger.append(dict(scope=scope,status='valid',purpose=purpose));return []
        return ([one] if scope['scope_id']=='function:f' else [two]),{0}
    monkeypatch.setattr(r,'generate_scope',generated)
    result,_=r.detector(row([],finish='length'),None)
    assert result['findings']==[] and seen==[[one,two]]
    assert len([e for e in r.events if e['kind']=='scoped_reassessment'])==1


def test_empty_field_retraction_cannot_claim_unassessed_scopes_clean(monkeypatch):
    r=c.Recoverer(unit(),None,[],list(old.DEFINITIONS),dict(scopes=[]))
    monkeypatch.setattr(r,'fields',lambda *args:([finding()],{0}))
    monkeypatch.setattr(r,'reassess',lambda *args:[])
    with pytest.raises(c.RecoveryFailure,match='empty.*coverage'):
        r.detector(row([finding()]),None)
