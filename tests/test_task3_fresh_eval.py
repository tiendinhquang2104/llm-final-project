"""Fresh-evaluation boundaries: private inputs, bounded calls and primary screening."""
import hashlib
import json
import pytest
from src.task3.fresh_eval import (EvaluationJournal, validate_dataset, build_targets,
    summarize_system, screen_v3, family_success)
from src.task3.prompt_crossover import call_state


def population():
    sources=[];gold=[]
    for f in range(20):
        for k in range(2):
            sid=f'opaque-{f}-{k}';code=f'int main(){{return {2*f+k};}}\n';statement=f'Task {f}\nC++11 full program.'
            sources.append(dict(sample_id=sid,family_id=f'FE{f:02}',statement=statement,code=code,
                language='cpp11',exam_type='single_problem',checker='tokens'))
            gold.append(dict(sample_id=sid,family_id=f'FE{f:02}',faulty=bool(k),taxonomy=['Lỗi logic'] if k else [],
                source_sha256=hashlib.sha256(code.encode()).hexdigest(),statement_sha256=hashlib.sha256(statement.encode()).hexdigest()))
    return sources,gold


def test_exact_dataset_pair_binding_and_labels():
    sources,gold=population();assert validate_dataset(sources,gold,['Lỗi logic'])
    for src,g in [(sources[:-1],gold),(sources+[sources[0]],gold),(sources,gold[:-1])]:
        with pytest.raises(ValueError):validate_dataset(src,g,['Lỗi logic'])
    broken=[dict(x) for x in sources];broken[1]['statement']='Different paired contract'
    with pytest.raises(ValueError):validate_dataset(broken,gold,['Lỗi logic'])
    bad=[dict(x) for x in gold];bad[1]['taxonomy']=['fake label']
    with pytest.raises(ValueError):validate_dataset(sources,bad,['Lỗi logic'])


def test_private_fields_and_stale_source_hash_cannot_enter_dataset():
    sources,gold=population()
    for extra in ('faulty','expected','witness','reviewer_notes','taxonomy'):
        bad=[dict(x) for x in sources];bad[0][extra]='private'
        with pytest.raises(ValueError,match='whitelist'):validate_dataset(bad,gold,['Lỗi logic'])
    bad=[dict(x) for x in sources];bad[0]['code']+='// changed\n'
    with pytest.raises(ValueError,match='hash'):validate_dataset(bad,gold,['Lỗi logic'])


def test_targets_exact160_and_six_safe_fields_only():
    sources,gold=population();syntax={s['sample_id']:dict(status='pass',diagnostic='') for s in sources}
    targets=build_targets(sources,syntax)
    assert len(targets)==160 and len({r['sample_id'] for r in targets})==160
    assert all(set(r['input'])=={'statement','exam_type','language','code','compile_log','target_feedback_level'} for r in targets)
    assert all('taxonomy' not in str(r['input']) and 'faulty' not in str(r['input']) for r in targets)
    with pytest.raises(ValueError):build_targets(sources,{})


def test_160_native_480_A_ceiling_and_no_foreign_or_fourth_attempt(tmp_path):
    ids=[f'S{i}-L1' for i in range(160)];j=EvaluationJournal(tmp_path/'j',{'A':3,'V2-old':1,'V3-v3':1},ids)
    for bad in ('X/S0-L1/1','A/unknown/1','A/S0-L1/0','A/S0-L1/4','V2-old/S0-L1/2'):
        with pytest.raises(ValueError):j.reserve(bad,99999)
    for system,attempts in [('A',3),('V2-old',1),('V3-v3',1)]:
        for eid in ids:
            for attempt in range(1,attempts+1):
                key=f'{system}/{eid}/{attempt}';j.reserve(key,402)
                j.append(dict(type='generation_completed',key=key,result={'raw':'measured'}))
    assert len(j.reserved())==800
    with pytest.raises(ValueError):j.reserve('A/S0-L1/1',99999)


def test_uncertain_attempt_blocks_replay_and_next_recovery(tmp_path):
    j=EvaluationJournal(tmp_path/'j',{'A':3},['S-L2']);j.reserve('A/S-L2/1')
    assert call_state(j,'A/S-L2/1')==('uncertain',None)
    with pytest.raises(ValueError):j.reserve('A/S-L2/1')
    with pytest.raises(ValueError,match='previous'):j.reserve('A/S-L2/2')
    j.append(dict(type='generation_completed',key='A/S-L2/1',result={'raw':'bad json'}))
    j.reserve('A/S-L2/2');assert len(j.reserved())==2


def row(sid,level,faulty=False,success=True):
    from src.task3.prompt_crossover import AXES
    axes={k:'pass' for k in AXES}
    if level==1 or not faulty:axes['location_and_condition']='not_applicable'
    if level!=3 or not faulty:axes['l3_repair_direction']='not_applicable'
    if level!=4:axes['l4_usefulness']='not_applicable'
    if not success:axes['factual_fidelity']='fail'
    parsed=dict(taxonomy_error=['Lỗi logic'] if faulty else [],feedback='Có căn cứ')
    return dict(sample_id=sid,example_id=f'{sid}-L{level}',family_id='F',level=level,faulty=faulty,status='valid',finish_reason='eos',
        raw=json.dumps(parsed,ensure_ascii=False),parsed=parsed,gold_taxonomy=['Lỗi logic'] if faulty else [],
        axes=axes,code_verdict='absent',taxonomy_feedback_contradiction=False)


def test_L4_is_separate_and_family_is_not_target_unit():
    rows=[row(s,l,faulty=f,success=l!=4) for s,f in [('s1',False),('s2',True)] for l in (1,2,3,4)]
    summary=summarize_system(rows)
    assert summary['primary']['targets']==6 and summary['primary']['successful_feedback']==6
    assert summary['secondary_l4']['targets']==2 and summary['secondary_l4']['successful_feedback']==0
    assert summary['faulty_l23']['targets']==2 and summary['faulty_l3']['targets']==1
    groups=family_success(rows)
    assert groups['families']['F']['primary_targets']==6 and groups['families']['F']['primary_success']==6
    assert groups['sources']['s1']['primary_targets']==3


def test_false_praise_can_pass_disclosure_but_not_diagnosis_or_success():
    r=row('s',2,True);r['parsed']['taxonomy_error']=[]
    r['raw']=json.dumps(r['parsed'],ensure_ascii=False)
    r['axes']['diagnosis_supported']='fail';r['axes']['coverage']='fail';r['axes']['required_content']='fail'
    s=summarize_system([r])['primary']
    assert s['disclosure_compliant']==1 and s['successful_feedback']==0 and s['supported_faulty_diagnosis']==0
    assert s['faulty_misses_with_invalid']==1


def screening_fixture():
    s={}
    for name,n in [('A',50),('V2-old',60),('V3-v3',61)]:
        s[name]=dict(primary=dict(successful_feedback=n,clean_false_alarms=2,invalid=3,
                                  contradiction_families=0,uncertain_reviews=0),
                     faulty_l23=dict(supported_faulty_diagnosis=25),faulty_l3=dict(faulty_l3_correct=8))
    return s,{'V2-old':dict(new_disclosure_failures=0,new_required_content_failures=0,uncertain_level_pairs=0),
              'A':dict(new_disclosure_failures=0,new_required_content_failures=0,uncertain_level_pairs=0)}


def test_screen_requires_strict_primary_improvement_against_every_available_baseline():
    s,p=screening_fixture();assert screen_v3(s,p)['passed']
    s['A']['primary']['successful_feedback']=61
    decision=screen_v3(s,p);assert not decision['passed'] and not decision['comparisons']['A']['joint_primary']['passed']


@pytest.mark.parametrize('group,key,value',[('primary','clean_false_alarms',3),('primary','invalid',4),
    ('faulty_l23','supported_faulty_diagnosis',24),('faulty_l3','faulty_l3_correct',7),
    ('primary','contradiction_families',2),('primary','uncertain_reviews',1)])
def test_single_worse_or_disputed_primary_gate_blocks_promotion(group,key,value):
    s,p=screening_fixture();s['V3-v3'][group][key]=value
    assert not screen_v3(s,p)['passed']


def test_new_level_failures_are_separate_from_disclosure_totals_and_L4():
    s,p=screening_fixture();s['V3-v3']['secondary_l4']={'successful_feedback':99999}
    p['V2-old']['new_required_content_failures']=1
    assert not screen_v3(s,p)['passed']
    p['V2-old']['new_required_content_failures']=0;p['A']['new_disclosure_failures']=1
    assert not screen_v3(s,p)['passed']


def test_A_unavailable_does_not_block_complete_native_screening():
    s,p=screening_fixture();del s['A'];del p['A']
    d=screen_v3(s,p);assert d['passed'] and d['available_baselines']==['V2-old']


def test_isolated_syntax_uses_historical_stdin_flags_deadline_and_diagnostic_cap(tmp_path,monkeypatch):
    from scripts.task3_fresh_eval import isolated_syntax
    import subprocess
    observations={}
    class Sandbox:
        def create(self,parent):
            jail=tmp_path/'jail';jail.mkdir();return jail
        def _enter(self,jail,compile_phase):observations['isolated']=(jail,compile_phase)
    class Process:
        pid=123;returncode=0
        def wait(self,timeout):assert timeout==3
    def popen(args,**kw):
        observations['args']=args;observations['stdin']=kw['stdin'].read().decode()
        assert kw['close_fds']is True
        kw['preexec_fn']();kw['stderr'].write(b'w'*9000);return Process()
    monkeypatch.setattr(subprocess,'Popen',popen)
    monkeypatch.setattr('os.killpg',lambda *args:None)
    result=isolated_syntax(Sandbox(),'int main(){}\n',tmp_path)
    assert observations['args']==['/usr/bin/g++','-std=c++11','-fsyntax-only','-fno-diagnostics-color','-x','c++','-']
    assert observations['stdin']=='int main(){}\n' and observations['isolated'][1]is True
    assert len(result['diagnostic'])==8000 and len(result['stderr'])==9000


def test_frozen_file_mutation_blocks_before_inference(tmp_path):
    from scripts.task3_fresh_eval import verify_frozen
    p=tmp_path/'input';p.write_text('exact source')
    m={'files':{str(p):hashlib.sha256(p.read_bytes()).hexdigest()}}
    (tmp_path/'manifest.json').write_text(json.dumps(m))
    (tmp_path/'manifest.sha256.json').write_text(json.dumps({'sha256':hashlib.sha256((tmp_path/'manifest.json').read_bytes()).hexdigest()}))
    assert verify_frozen(tmp_path)['passed']
    p.write_text('changed source')
    with pytest.raises(ValueError,match='changed'):verify_frozen(tmp_path)


def test_historical_A_acceptance_preserves_real_termination_in_metrics():
    r=row('s',2);r.update(finish_reason='length',payload_acceptance='historical_A')
    assert summarize_system([r])['primary']['valid']==1
    assert r['finish_reason']=='length'
    del r['payload_acceptance']
    with pytest.raises(ValueError):summarize_system([r])


def test_native_resume_preserves_known_unknown_without_replay(tmp_path):
    from scripts.task3_fresh_eval import validate_native_rows
    journal=EvaluationJournal(tmp_path/'j',{'V2-old':1},['s-L1'])
    journal.reserve('V2-old/s-L1/1')
    examples=[dict(example_id='s-L1',sample_id='s',level=1)]
    missing=dict(example_id='s-L1',sample_id='s',level=1,status='missing',parsed=None,
        raw='',finish_reason='interrupted_unknown',call_count_uncertain=True)
    assert validate_native_rows([missing],examples,journal,'V2-old')=={'s-L1'}
    with pytest.raises(ValueError):validate_native_rows([dict(missing,status='valid')],examples,journal,'V2-old')


def test_unknown_essential_review_or_contradiction_blocks_screen_but_legitimate_NA_does_not():
    r=row('s',1);assert summarize_system([r])['primary']['uncertain_reviews']==0
    r['axes']['diagnosis_supported']='not_evaluable'
    assert summarize_system([r])['primary']['uncertain_reviews']==1
    r=row('s',2);r['taxonomy_feedback_contradiction']='uncertain'
    assert summarize_system([r])['primary']['uncertain_reviews']==1
