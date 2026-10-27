"""Behavioral regression tests for crossover metrics and offline reporting."""
import importlib
import json
from copy import deepcopy
import pytest


def api():
    assert importlib.util.find_spec('src.task3.prompt_crossover_analysis'), 'crossover analysis missing'
    return importlib.import_module('src.task3.prompt_crossover_analysis')


def row(eid='f-L3', faulty=True, level=3, labels=None, **kw):
    axes={k:'pass' for k in ('diagnosis_supported','coverage','factual_fidelity','location_and_condition',
        'disclosure_compliance','required_content','l3_repair_direction','l4_usefulness','vietnamese_compliance')}
    r=dict(cell='v2-old',example_id=eid,sample_id=eid.rsplit('-L',1)[0],family_id=eid[0],level=level,
        status='valid',finish_reason='eos',raw='raw',parsed={'taxonomy_error':labels if labels is not None else ['logic'], 'feedback':'Nhận xét.'},
        faulty=faulty,gold_taxonomy=['logic'] if faulty else [],axes=axes,code_verdict='absent',evidence='source evidence')
    r.update(kw)
    return r


def test_false_praise_can_pass_disclosure_but_never_task_success():
    m=api();r=row(labels=[]);r['axes']['diagnosis_supported']='fail'
    s=m.summarize([r])
    assert s['disclosure_compliant']==1 and s['successful_feedback']==0
    assert s['faulty_misses_with_invalid']==1 and s['supported_faulty_diagnosis']==0
    # Even internally inconsistent semantic data cannot promote empty faulty taxonomy.
    r['axes']['diagnosis_supported']='pass'
    assert not m.successful_feedback(r)


def test_required_content_and_wrong_hint_are_separate_from_disclosure():
    m=api();r=row();r['axes']['required_content']='fail'
    assert not m.successful_feedback(r)
    s=m.summarize([r]);assert s['disclosure_compliant']==1 and s['official_level_complete']==0
    r['axes']['required_content']='pass';r['axes']['l3_repair_direction']='fail'
    s=m.summarize([r]);assert s['official_level_complete']==1 and s['successful_feedback']==0


def test_l4_code_optional_and_supplied_bad_code_blocks_success():
    m=api();r=row(level=4)
    assert m.successful_feedback(r)
    r['code_verdict']='fail';assert not m.successful_feedback(r)


def test_all_target_source_denominators_and_taxonomy_invalid_fn():
    m=api();a=row();b=row('f-L2',level=2,status='malformed_json',parsed=None)
    b['axes']={k:'not_evaluable' for k in b['axes']}
    c=row('c-L3',faulty=False,labels=[])
    s=m.summarize([a,b,c])
    assert (s['targets'],s['sources'],s['clean_targets'],s['faulty_targets'],s['invalid'])==(3,2,1,2,1)
    assert s['axes']['required_content']['not_evaluable']==1
    assert s['faulty_missed_defect_rate_with_invalid']==.5
    assert s['balanced_success']==.75
    assert s['taxonomy_auxiliary']['taxonomy']['all_targets_conservative']['fn']==1
    assert s['taxonomy_auxiliary']['taxonomy']['all_targets_conservative']['targets']==3


def test_paired_full_taxonomy_sets_and_uncertain_semantics():
    m=api();a=row(labels=['logic','bounds']);b=deepcopy(a);b['parsed']['taxonomy_error']=['logic']
    a['axes']['diagnosis_supported']='uncertain';b['axes']['diagnosis_supported']='fail'
    p=m.paired_analysis([a],[b]);o=p['overall']
    assert o['taxonomy_transitions']==[{'before':['bounds','logic'],'after':['logic'],'count':1}]
    assert o['semantic']['assessment']=={'win':0,'loss':0,'tie':0,'uncertain':1}
    assert p['by_level']['3']['targets']==1 and p['by_status']['faulty']['targets']==1
    a['status']='malformed_json';a['parsed']=None
    assert m.paired_analysis([a],[b])['overall']['semantic']['disclosure_compliance']['uncertain']==1


@pytest.mark.parametrize('mutation',['duplicate','foreign','source','level','faulty','gold'])
def test_pairing_rejects_mismatched_populations(mutation):
    m=api();a=row();b=deepcopy(a);before=[a];after=[b]
    if mutation=='duplicate':after.append(deepcopy(b))
    elif mutation=='foreign':b['example_id']='foreign'
    elif mutation=='source':b['sample_id']='other'
    elif mutation=='level':b['level']=2
    elif mutation=='faulty':b['faulty']=False
    else:b['gold_taxonomy']=[]
    with pytest.raises(ValueError):m.paired_analysis(before,after)


def report_api():
    assert importlib.util.find_spec('scripts.task3_prompt_crossover_report'), 'offline crossover report missing'
    return importlib.import_module('scripts.task3_prompt_crossover_report')


def test_casebook_preserves_all_cells_and_escapes_untrusted_source():
    m=report_api();r=row();r['raw']='<script>alert(1)</script>'
    rows=[dict(r,cell=c,completed_review_record={'evidence':'<b>review</b>'}) for c in m.CELLS]
    source={'sample_id':'f-L3','source_id':'f','input':{'statement':'<bad>','code':'int x;'},'output':{'taxonomy_error':['logic']}}
    examples={arm:{'f-L3':dict(example_id='f-L3',prompt=[{'role':'system','content':'<policy>'}])} for arm in ('old','v3')}
    text=m.render_casebook(rows,{'f-L3':source},examples,{(c,'f-L3'):{} for c in m.CELLS})
    assert '<script>alert(1)</script>' not in text and '&lt;script&gt;alert(1)&lt;/script&gt;' in text
    assert text.count('<article')==4 and '&lt;policy&gt;' in text and '&lt;bad&gt;' in text
    assert 'completed_review_record' in text


def test_example_selection_is_deterministic_diverse_and_keeps_uncertain_out():
    m=report_api();rows=[]
    for eid in ('A1-L3','A2-L3','B1-L3'):
        a=row(eid=eid);b=deepcopy(a);a['axes']['diagnosis_supported']='fail'
        rows += [a,dict(b,cell='v2-v3')]
    # Distinct source families rather than first repeated family.
    picked=m.choose_examples(rows,'v2-old','v2-v3',limit=2)
    assert picked['incorrect_to_correct']==['A1-L3','B1-L3']
    assert m.choose_examples(list(reversed(rows)),'v2-old','v2-v3',limit=2)==picked


def test_costs_separate_fresh_and_reused_without_double_charging():
    m=report_api();manifest={'planned_new_calls':2,'cells':{c:{'mode':'fresh' if c in ('v2-old','v3-old') else 'reused'} for c in m.CELLS}}
    generations={c:[dict(row(),wall_s=3,input_tokens=10,output_tokens=4)] for c in m.CELLS}
    result=m.costs(manifest,generations,{})
    assert result['fresh']['generation_calls']==2 and result['reused']['generation_calls']==2
    assert result['fresh']['generation_wall_s']==6 and result['reused']['generation_wall_s']==6
    assert result['new_calls']==2 and result['reused_outputs']==2
    assert result['monetary_total'] is None


def test_report_validation_rejects_pending_before_missing_io(tmp_path):
    m=report_api();r=row();r['axes']['coverage']='pending'
    with pytest.raises(ValueError,match='pending|verdict|review'):
        m.validate_populations(tmp_path,[r])


def test_completed_reviews_do_not_leave_legacy_pending_placeholder():
    s=api().summarize([row()])
    assert 'feedback_quality' not in s['taxonomy_auxiliary']
    assert all('feedback_quality' not in v for v in s['taxonomy_auxiliary']['by_level'].values())


def full_report_fixture(tmp_path):
    m=report_api();records=[];rows=[];examples=[]
    for i in range(20):
        for level in range(1,5):
            eid=f'F{i:02d}-L{level}';source=f'F{i:02d}'
            records.append(dict(sample_id=eid,source_id=source,input={'target_feedback_level':level},output={'taxonomy_error':['logic']}))
            examples.append(dict(example_id=eid,sample_id=source,level=level,prompt=[]))
            for cell in m.CELLS:
                rows.append(row(eid,level=level,cell=cell,review_id=cell+'/'+eid,completed_review_record={'review':'complete'}))
    for arm in ('old','v3'):
        path=tmp_path/f'inputs/{arm}.examples.private.json';path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(examples))
    path=tmp_path/'evaluation/dev.records.private.jsonl';path.parent.mkdir()
    path.write_text('\n'.join(map(json.dumps,records)))
    for cell in m.CELLS:
        folder=tmp_path/f'cells/{cell}';folder.mkdir(parents=True)
        (folder/'generations.jsonl').write_text('\n'.join(json.dumps(r) for r in rows if r['cell']==cell))
        (folder/'complete.json').write_text(json.dumps({'generation':{'calls':80}}))
        folder=tmp_path/f'code-evidence/{cell}';folder.mkdir(parents=True)
        for r in rows:
            if r['cell']==cell:(folder/(r['example_id']+'.json')).write_text('{}')
    return rows


@pytest.mark.parametrize('change',['none','missing','duplicate','foreign','source','generation','detail_escape'])
def test_report_population_join_and_rejection_happen_without_writes(tmp_path,change):
    m=report_api();rows=full_report_fixture(tmp_path)
    if change=='none':
        records,examples,generations,evidence,complete=m.validate_populations(tmp_path,rows)
        assert len(records)==80 and len(evidence)==320
        return
    if change=='missing':rows.pop()
    elif change=='duplicate':rows[-1]=deepcopy(rows[0])
    elif change=='foreign':rows[0]['example_id']='foreign'
    elif change=='source':rows[0]['sample_id']='other'
    elif change=='generation':rows[0]['raw']='different'
    else:
        path=tmp_path/'code-evidence/v2-old/F00-L1.json'
        path.write_text(json.dumps({'detail_path':'../../outside.json'}))
    with pytest.raises(ValueError):m.validate_populations(tmp_path,rows)
    assert not (tmp_path/'analysis.json').exists() and not (tmp_path/'paired-casebook.html').exists()


def test_contradiction_examples_require_explicit_source_grounded_annotation():
    m=report_api();a=row(labels=[]);a['axes']['factual_fidelity']='fail'
    b=deepcopy(a);b['cell']='v2-v3'
    selected=m.choose_examples([a,b],'v2-old','v2-v3')
    assert selected['contradiction']==[]  # false praise alone does not prove taxonomy/prose disagree
    b['completed_review_record']={'taxonomy_feedback_contradiction':True,'evidence':'Labels name a defect but feedback asserts no defect.'}
    assert m.choose_examples([a,b],'v2-old','v2-v3')['contradiction']==['f-L3']


def test_reused_completion_validates_historical_calls_without_new_billing(tmp_path):
    m=report_api();rows=full_report_fixture(tmp_path)
    for cell in ('v2-v3','v3-v3'):
        (tmp_path/f'cells/{cell}/complete.json').write_text(json.dumps(dict(mode='reused',targets=80,
            new_generation_calls=0,historical_generation_calls=80,historical_generation_wall_s=12,memory_scope='historical')))
    records,examples,gens,evidence,complete=m.validate_populations(tmp_path,rows)
    manifest={'planned_new_calls':160,'cells':{c:{'mode':'reused' if c in ('v2-v3','v3-v3') else 'fresh'} for c in m.CELLS}}
    c=m.costs(manifest,gens,complete)
    assert c['new_calls']==160 and c['reused_outputs']==160
    assert c['per_cell']['v2-v3']['phase_wall_s'] is None


def test_fresh_uncertain_reservation_stays_in_target_and_cost_totals(tmp_path):
    m=report_api();rows=full_report_fixture(tmp_path);r=rows[0]
    r.update(status='generation_error',parsed=None,call_count_uncertain=True,code_verdict='uncertain')
    r['axes']={k:'not_evaluable' for k in r['axes']}
    (tmp_path/'cells/v2-old/generations.jsonl').write_text('\n'.join(json.dumps(x) for x in rows if x['cell']=='v2-old'))
    (tmp_path/'cells/v2-old/complete.json').write_text(json.dumps(dict(mode='fresh',targets=80,generation={'calls':79},unknown=1)))
    records,examples,gens,evidence,complete=m.validate_populations(tmp_path,rows)
    manifest={'planned_new_calls':320,'cells':{c:{'mode':'fresh'} for c in m.CELLS}}
    accounting=m.costs(manifest,gens,complete)
    assert accounting['new_calls']==320 and accounting['fresh']['uncertain_call_rows']==1
    assert accounting['fresh']['confirmed_generation_calls']==319


def test_cross_input_tendency_requires_both_paired_changes_and_diverse_sources():
    m=report_api();rows=[]
    for eid,faulty,before_labels,after_labels in [
        ('A1-L3',False,['logic'],[]),('A2-L3',False,['logic'],[]),('B1-L3',True,['logic'],[]),
        ('C1-L3',False,['logic'],[]),('D1-L3',True,['logic'],[]),
        ('E1-L3',False,['logic'],['logic']),('F1-L3',True,[],[])]:
        rows += [row(eid,faulty=faulty,labels=before_labels),row(eid,faulty=faulty,labels=after_labels,cell='v2-v3')]
    selected=m.choose_examples(rows,'v2-old','v2-v3')
    assert selected['cross_input_tendency']==[
        {'clean_example_id':'A1-L3','faulty_example_id':'B1-L3'},
        {'clean_example_id':'C1-L3','faulty_example_id':'D1-L3'}]
    assert m.choose_examples(list(reversed(rows)),'v2-old','v2-v3')==selected
    unchanged=[r for r in rows if r['example_id'] in ('E1-L3','F1-L3')]
    assert m.choose_examples(unchanged,'v2-old','v2-v3')['cross_input_tendency']==[]


def test_uncertain_cost_placeholders_are_unmeasured_not_zero_observations():
    m=report_api();manifest={'planned_new_calls':2,'cells':{c:{'mode':'fresh'} for c in m.CELLS}}
    known=dict(row(),wall_s=3,input_tokens=10,output_tokens=4)
    unknown=dict(row(),call_count_uncertain=True,wall_s=0,input_tokens=0,output_tokens=0)
    generations={c:[] for c in m.CELLS};generations['v2-old']=[known,unknown]
    result=m.costs(manifest,generations,{})['fresh']
    assert result['generation_calls']==2 and result['uncertain_call_rows']==1
    assert result['generation_wall_s']==3 and result['generation_wall_s_measured_rows']==1
    assert result['input_tokens']==10 and result['input_tokens_measured_rows']==1
    assert result['output_tokens']==4 and result['output_tokens_unmeasured_rows']==1
    generations['v2-old']=[unknown]
    result=m.costs(manifest,generations,{})['fresh']
    assert result['generation_wall_s'] is None and result['input_tokens'] is None
    assert result['generation_wall_s_measured_rows']==0 and result['generation_wall_s_unmeasured_rows']==1
    assert 'không đo' in m.table(['Measurement'],[[None]])


def test_rendered_cross_input_examples_show_both_cells_for_both_sources(tmp_path):
    m=report_api();rows=[];records={}
    for eid,faulty in [('A1-L3',False),('B1-L3',True)]:
        records[eid]={'input':{'statement':'source specification','code':eid}}
        for c in m.CELLS:
            labels=['logic'] if c.endswith('-old') else []
            rows.append(row(eid,faulty=faulty,labels=labels,cell=c,evidence='evidence:'+c+'/'+eid))
    manifest={'planned_new_calls':8,'technical_matching':True,'cells':{c:{'mode':'fresh'} for c in m.CELLS}}
    metrics=m.summarize_cells(rows)
    analysis={'metrics':metrics,'paired':{k:api().paired_analysis([r for r in rows if r['cell']==a],[r for r in rows if r['cell']==b]) for k,(a,b) in m.PAIRS.items()},
        'costs':m.costs(manifest,{c:[r for r in rows if r['cell']==c] for c in m.CELLS},{}),
        'examples':{k:m.choose_examples(rows,a,b) for k,(a,b) in m.PAIRS.items()}}
    report,examples=m.render_reports(tmp_path,manifest,analysis,rows,records)
    selected=examples.split('#### Cross-input: A1-L3 / B1-L3',1)[1].split('## v3_prompt',1)[0]
    for c in ('v2-old','v2-v3'):
        for eid in ('A1-L3','B1-L3'):assert 'evidence:'+c+'/'+eid in selected
    assert 'Không có cặp đáp ứng đồng thời' in examples  # adapter pairs have no matching tendency
    assert 'không đo (0/2)' in report  # no fake zero token/wall measurements
    assert not (tmp_path/'analysis.json').exists()
