import copy
import json
from pathlib import Path

import pytest

from src.task3 import arm_d_plus_v15 as old
from src.task3 import arm_d_plus_v16 as new
from src.task3.source_refs import build_catalog, source_sha, VERSION
from src.task3.inference import MockTokenizer, Generation
from src.task3.level_blind import digest


def unit(sid='test',level=2):
    code='int value(){ return 1 }\n'
    return dict(sample_id=sid,level=level,family='test',source_catalog=build_catalog(code),source_map_version=VERSION,
                local_compiler=dict(source_sha256=source_sha(code),status='compile_error'),
                task=dict(statement='Return one.',exam_type='single_problem',code=code,problems=[dict(pid='P1')]))


def finding():
    return dict(problem_id='P1',kind='defect',location='value',error='The return statement lacks a semicolon.',
                labels=['Lỗi biên dịch'],evidence_refs=[dict(source='code',start_line=1,end_line=1)])


def row(findings=None,raw=None,finish='eos'):
    return dict(raw_text=raw if raw is not None else json.dumps(dict(findings=findings or [])),finish_reason=finish,error=None)


def test_archived_fence_reproduces_old_failure():
    p=Path('outputs/task3/v1.5-observation-20261024/internal/attempts.jsonl')
    r=json.loads(p.read_text().splitlines()[0])
    with pytest.raises(json.JSONDecodeError):old.parse_findings(r['raw_text'],unit())


def test_transport_recovers_payload_without_mutating_quote():
    f=finding();raw='```json\n'+json.dumps(dict(findings=[f]))+'\n```'
    result=new.audit_response(row(raw=raw),unit())
    assert result['schema_reference_success']
    enriched=old.extract_findings(result['findings'],unit())
    assert enriched[0]['evidence_spans'][0]['text']=='int value(){ return 1 }\n'


def test_kind_logic_is_field_specific_failure():
    f=finding();f['kind']='logic'
    result=new.audit_response(row([f]),unit())
    assert result['failure']['category']=='schema'
    assert result['failure']['details']['field_path']=='findings[0].kind'
    assert result['failure']['details']['offending_value']=='logic'
    assert result['findings'] is None


def test_unknown_taxonomy_stays_pending_without_deleting_finding():
    f=finding();f['labels']=['Unknown category']
    result=new.audit_response(row([f]),unit(),labels=list(old.DEFINITIONS))
    assert result['status']=='pending_mapping' and result['findings']==[f]


def test_one_bad_finding_rejects_whole_response():
    bad=finding();bad['evidence_refs'][0]['end_line']=99
    result=new.audit_response(row([finding(),bad]),unit())
    assert result['findings'] is None and result['failure']['category']=='reference_contract'


def test_length_termination_precedes_parse():
    result=new.audit_response(row([],finish='length'),unit())
    assert result['failure']['category']=='generation_termination'


@pytest.mark.parametrize('raw',['{"findings":[],"findings":[]}','{"findings":NaN}','{"findings":Infinity}'])
def test_json_policy_failures_distinct_from_field_schema(raw):
    assert new.audit_response(row(raw=raw),unit())['failure']['category']=='json_syntax'


def test_replay_retains_attempt0_even_if_attempt1_is_cleaner():
    u=unit();first=row([finding()]);later=row([])
    result=new.select_replay(first,later,u,list(old.DEFINITIONS))
    assert result['selected_attempt']==0
    assert result['baseline']['findings']==[finding()]
    assert result['historical_correction']['findings']==[]


def test_invalid_attempt0_never_promotes_historical_correction():
    f=finding();f['kind']='logic'
    result=new.select_replay(row([f]),row([finding()]),unit(),list(old.DEFINITIONS))
    assert result['selected_attempt'] is None and result['baseline']['findings'] is None
    assert result['historical_correction']['schema_reference_success']


def test_b_changes_only_original_reasoning_paragraph():
    assert old.FINDINGS_SYSTEM.replace(new.ORIGINAL_REASONING,new.GROUNDED_REASONING)==new.FINDINGS_B
    assert new.messages_findings(unit(),list(old.DEFINITIONS),'A')[0]['content']==old.FINDINGS_SYSTEM
    assert 'requested_level' not in new.messages_findings(unit(),list(old.DEFINITIONS),'B')[1]['content']


class Backend:
    tokenizer=MockTokenizer()
    def __init__(self,responses):self.responses=iter(responses);self.calls=0
    def generate(self,messages,config):
        self.calls+=1
        return Generation(next(self.responses),3,0.001,'eos',True)


def config():
    return dict(context_limit=100000,findings_max_new_tokens=1536,max_new_tokens=1024)


def test_recovery_names_kind_and_never_repeats_on_resume(tmp_path):
    f=finding();f['kind']='logic';bad=row([f]);backend=Backend([json.dumps(dict(findings=[f]))])
    messages=new.messages_findings(unit(),list(old.DEFINITIONS),'A')
    journal=old.DPlusJournal(tmp_path,backend,config(),'same')
    with pytest.raises(ValueError):new.schema_stage(journal,'test','taxonomy',messages,unit(),historical=bad)
    with pytest.raises(ValueError):new.schema_stage(journal,'test','taxonomy',messages,unit(),historical=bad)
    assert backend.calls==1
    r=next(iter(journal.rows.values()))
    assert r['attempt']==1
    assert 'findings[0].kind' in r['messages'][-1]['content']
    assert 'defect' in r['messages'][-1]['content'] and 'omission' in r['messages'][-1]['content']


def test_prompt_config_identity_prevents_reuse(tmp_path):
    journal=old.DPlusJournal(tmp_path,Backend(['{}']),config(),'one')
    with pytest.raises(ValueError,match='identity'):old.DPlusJournal(tmp_path,Backend([]),config(),'two')


def test_global_selection_requires_all_measures_and_strict_gain():
    a=dict(coverage=30,micro_f1=.3,macro_f1=.2,unsupported_cases=4,paired_score=8)
    assert new.select_method(a,dict(a))['selected']=='A'
    assert new.select_method(a,{**a,'micro_f1':.31})['selected']=='B'
    assert new.select_method(a,{**a,'micro_f1':.31,'unsupported_cases':5})['selected']=='A'
    assert new.select_method(a,{**a,'micro_f1':.31},disputed=True)['selected']=='A'


def test_export_rejects_duplicate_missing_extra_and_mixed_ids(tmp_path):
    from scripts.task3_arm_d_plus import validate_export
    from src.task3.dataset import write_json
    out=dict(taxonomy_error=[],feedback='Chưa phát hiện vấn đề có đủ căn cứ.')
    for ids in (['a','a'],['a'],['a','b','x'],['a','SYN-internal']):
        write_json(tmp_path/'partial.predictions.json',[dict(sample_id=sid,output=out) for sid in ids])
        with pytest.raises(ValueError):validate_export(tmp_path,{'a':'Level 1 - Gợi ý nhẹ','b':'Level 1 - Gợi ý nhẹ'},list(old.DEFINITIONS))
        assert not (tmp_path/'predictions.json').exists()


def test_invalid_l1_never_gets_template_and_later_input_continues(tmp_path):
    bad=finding();bad['kind']='logic'
    backend=Backend([json.dumps(dict(findings=[bad]))]*2+[json.dumps(dict(findings=[]))])
    space=json.loads(Path('outputs/task3/v1.5-observation-20261024/internal/label-space.private.json').read_text())
    results=new.run_units([unit('bad',1),unit('good',1)],backend,config(),tmp_path,space,'A')
    assert results[0]['stage1'] is None and results[0]['output'] is None
    assert results[1]['status']=='resolved' and results[1]['output']['feedback']==old.LEVEL1_FEEDBACK[False]
    assert backend.calls==3
    new.run_units([unit('bad',1),unit('good',1)],backend,config(),tmp_path,space,'A')
    assert backend.calls==3


def test_paired_cases_are_complete_frozen_six_pairs():
    from src.task3.v16_experiment import paired_cases
    cases=paired_cases()
    assert len(cases)==12 and len({c['pair'] for c in cases})==6
    assert sum(c['expected']['defect_present'] for c in cases)==5
    assert all('int main()' in c['code'] and c['code_sha256']==source_sha(c['code']) for c in cases)
    assert all(not c['expected']['defect_present'] for c in cases if c['pair']=='capacity')


def test_disputed_paired_verdict_forces_conservative_a(tmp_path):
    from scripts.task3_v16_run import selection_from_reviews
    from src.task3.v16_experiment import paired_cases
    from src.task3.dataset import write_json
    population=[dict(sample_id=f'internal-{i}',stage1=dict(taxonomy_error=[])) for i in range(30)]
    pairs=[dict(sample_id=c['sample_id'],stage1=dict(taxonomy_error=[])) for c in paired_cases()]
    reviews=dict(internal={},paired={})
    for arm in ('A','B'):
        reviews['internal'][arm]=[dict(sample_id=r['sample_id'],result_sha256=digest(r),
            reason='Source reviewed.',unsupported_case=(arm=='A' and i==0)) for i,r in enumerate(population)]
        reviews['paired'][arm]=[dict(sample_id=r['sample_id'],result_sha256=digest(r),
            expected_diagnosis_pass=True,disputed=(arm=='B' and i==0)) for i,r in enumerate(pairs)]
    write_json(tmp_path/'reviews/internal-and-probes.private.json',reviews)
    write_json(tmp_path/'method-freeze.json',{})
    result=selection_from_reviews(tmp_path,[dict(sample_id=r['sample_id'],taxonomy_error=[]) for r in population],
                                  {'A':population,'B':population},{'A':pairs,'B':pairs})
    assert result['selected']=='A' and result['checks']['undisputed'] is False
