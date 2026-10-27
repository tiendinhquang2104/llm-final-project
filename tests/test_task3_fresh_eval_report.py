"""Offline population, denominator and artifact checks for the fresh-family report."""
from copy import deepcopy
import hashlib
import importlib
import json

import pytest

from src.task3.fresh_eval import AXES, build_targets


def api():
    return importlib.import_module('scripts.task3_fresh_eval_report')


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')


def fixture(out):
    sources=[]; gold=[]; cases=[]; validation=[]; syntax={}
    for f in range(20):
        for faulty in (False, True):
            sid=f's{f:02}-{int(faulty)}'; family=f'family{f:02}'
            code=f'// <script>alert("source")</script>\nint main(){{return {f*2+faulty};}}\n'
            source=dict(sample_id=sid, family_id=family, statement=f'Đề {f}: <img src=x onerror=alert(1)>',
                        code=code, language='cpp11', exam_type='single_problem', checker='tokens')
            sources.append(source)
            sha=hashlib.sha256(code.encode()).hexdigest()
            g=dict(sample_id=sid, family_id=family, faulty=faulty, taxonomy=['Lỗi logic'] if faulty else [],
                   source_sha256=sha, statement_sha256=hashlib.sha256(source['statement'].encode()).hexdigest(),
                   defect='Sai điều kiện', location='dòng 2', trigger_conditions=['n=0'], expected_behavior='0',
                   acceptable_l3=['Đảo điều kiện'], unacceptable_l3=['Xóa vòng lặp'], clean_invariant='Đếm đúng',
                   alternative_interpretations=[], witness_input='0\n', witness_evidence_path=f'evidence/{sid}.json',
                   test_design='Exhaustive small domain', novelty='Newly authored')
            gold.append(g); syntax[sid]=dict(status='pass', diagnostic='')
            code_file=out/'sources'/f'{sid}.cpp'; code_file.parent.mkdir(exist_ok=True)
            code_file.write_text(code)
            cases.append(dict(sample_id=sid, family_id=family, statement=source['statement'],
                              code_file=str(code_file), source_sha256=sha, harness='', checker='tokens',
                              tests=[{'input':'0\n','expected':'0'}], split='fresh', exam_type='single_problem'))
            v=dict(sample_id=sid, family_id=family, source_sha256=sha, faulty=faulty,
                   evidence_path=g['witness_evidence_path'], compile={'returncode':0},
                   authored_tests=1, executed_tests=1, passed=int(not faulty), failures=int(faulty),
                   witness={'input':'0\n','expected':'0', 'actual':{'stdout':'1' if faulty else '0'}, 'passed':not faulty})
            validation.append(v); write_json(out/g['witness_evidence_path'], dict(v, tests=[v['witness']]))
    targets=build_targets(sources, syntax); by_gold={g['sample_id']:g for g in gold}
    rows=[]; evidence=[]; generations={}
    for system in ('A','V2-old','V3-v3'):
        gens=[]
        for t in targets:
            sid=t['source_id']; level=t['input']['target_feedback_level']; g=by_gold[sid]
            parsed={'taxonomy_error':g['taxonomy'], 'feedback':'Nhận xét <script>alert("output")</script>.'}
            gen=dict(example_id=t['sample_id'], sample_id=sid, level=level, status='valid',
                     raw=json.dumps(parsed, ensure_ascii=False), parsed=parsed,
                     finish_reason='controller_export' if system=='A' else 'eos',
                     input_tokens=10, output_tokens=20, wall_s=0.1)
            if system=='A':
                gen.update(payload_acceptance='historical_A', raw_kind='controller_export',
                           actual_attempt_finish_reasons=['length'])
            gens.append(gen)
            axes={k:'pass' for k in AXES}
            if level==1 or not g['faulty']: axes['location_and_condition']='not_applicable'
            if level!=3 or not g['faulty']: axes['l3_repair_direction']='not_applicable'
            if level!=4: axes['l4_usefulness']='not_applicable'
            row=dict(gen, system_id=system, family_id=g['family_id'], faulty=g['faulty'],
                     gold_taxonomy=g['taxonomy'], axes=axes, code_verdict='absent',
                     taxonomy_feedback_contradiction=False, evidence='Dòng 2 đối chiếu đặc tả; witness 0.',
                     review_id=f'{system}/{t["sample_id"]}')
            rows.append(row)
            evidence.append(dict(system_id=system, example_id=t['sample_id'], status='absent', generation_status='valid',
                                 code_verdict='absent', compile_calls=0, runtime_calls=0, evidence='Không có code.'))
        generations[system]=gens
        write_rows(out/'generations'/system/'final.jsonl', gens)
    write_rows(out/'generations/A/first-attempts.jsonl', generations['A'])
    for filename, value in [('dataset.private.jsonl',sources),('gold.private.jsonl',gold),
                            ('targets.private.jsonl',targets),('reviews.private.jsonl',rows),
                            ('code-evidence.private.jsonl',evidence)]: write_rows(out/filename, value)
    write_json(out/'evidence/cases.private.json', cases)
    write_json(out/'evidence/source-validation.private.json', validation)
    write_json(out/'syntax.private.json', syntax)
    write_json(out/'systems.json', {'A':{'available':True, 'pipeline':'historical multistage'},
                                  'native_systems':{'V2-old':{},'V3-v3':{}}, 'common_native_runtime':{}})
    write_json(out/'costs-and-runtime.json', {'fresh_targets':480, 'model_calls':500, 'reused_targets':0})
    write_json(out/'manifest.json', {'files':{}})
    write_json(out/'manifest.sha256.json', {'sha256':hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest()})
    return rows, generations


def change_review(out, rows, system, eid, **changes):
    row=next(r for r in rows if (r['system_id'], r['example_id'])==(system,eid))
    row.update(changes); write_rows(out/'reviews.private.jsonl', rows)
    return row


def test_primary_secondary_clean_faulty_and_all_three_pairs(tmp_path):
    fixture(tmp_path); result=api().analyze(tmp_path)
    for m in result['metrics'].values():
        assert m['primary']['targets']==120 and m['secondary_l4']['targets']==40
        assert m['faulty_l23']['targets']==40 and m['faulty_l3']['targets']==20
        assert m['primary_by_status']['clean']['targets']==60
        assert m['primary_by_status']['faulty']['targets']==60
        assert len(m['grouped']['sources'])==40 and len(m['grouped']['families'])==20
    assert len(result['comparison']['pairs'])==3
    for comparison in result['comparison']['pairs'].values():
        assert comparison['primary']['overall']['targets']==120
        assert comparison['secondary_l4']['overall']['targets']==40
    assert not result['decision']['passed']  # Equal results do not meet strict improvement.
    assert set(result['decision']['comparisons'])=={'A','V2-old'}


@pytest.mark.parametrize('mutation', ['missing_review','duplicate_review','foreign_generation',
    'changed_raw','changed_A_acceptance','gold_binding','source_binding','pending_axes',
    'missing_code_evidence','evidence_verdict','changed_first_binding'])
def test_population_corruption_rejected_before_any_report_writes(tmp_path, mutation):
    rows, generations=fixture(tmp_path)
    if mutation=='missing_review': write_rows(tmp_path/'reviews.private.jsonl', rows[:-1])
    elif mutation=='duplicate_review': write_rows(tmp_path/'reviews.private.jsonl', rows+[rows[0]])
    elif mutation=='foreign_generation':
        generations['V3-v3'][0]['example_id']='foreign-L1'
        write_rows(tmp_path/'generations/V3-v3/final.jsonl', generations['V3-v3'])
    elif mutation=='changed_raw': change_review(tmp_path, rows,'A','s00-0-L1',raw='rewritten')
    elif mutation=='changed_A_acceptance': change_review(tmp_path, rows,'A','s00-0-L1',payload_acceptance='native')
    elif mutation=='gold_binding': change_review(tmp_path, rows,'A','s00-0-L1',faulty=True)
    elif mutation=='source_binding':
        sources=[json.loads(s) for s in (tmp_path/'dataset.private.jsonl').read_text().splitlines()]
        sources[0]['code']+='// changed\n'; write_rows(tmp_path/'dataset.private.jsonl', sources)
    elif mutation=='pending_axes':
        axes=deepcopy(rows[0]['axes']); axes['coverage']='pending'
        change_review(tmp_path,rows,'A','s00-0-L1',axes=axes)
    elif mutation=='missing_code_evidence':
        e=[json.loads(s) for s in (tmp_path/'code-evidence.private.jsonl').read_text().splitlines()]
        write_rows(tmp_path/'code-evidence.private.jsonl',e[:-1])
    elif mutation=='evidence_verdict':
        e=[json.loads(s) for s in (tmp_path/'code-evidence.private.jsonl').read_text().splitlines()]
        e[0]['code_verdict']='fail';write_rows(tmp_path/'code-evidence.private.jsonl',e)
    else:
        generations['A'][0]['sample_id']='foreign'
        write_rows(tmp_path/'generations/A/first-attempts.jsonl',generations['A'])
    with pytest.raises(ValueError): api().build(tmp_path)
    assert not (tmp_path/'REPORT.vi.md').exists()
    assert not (tmp_path/'metrics.json').exists()


def test_first_A_schema_objective_is_separate_from_final_semantic_review(tmp_path):
    _, generations=fixture(tmp_path)
    first=deepcopy(generations['A']);first[0].update(status='malformed_json', parsed=None, raw='{broken', finish_reason='length')
    write_rows(tmp_path/'generations/A/first-attempts.jsonl',first)
    result=api().analyze(tmp_path)
    a=result['first_final_objective']['A']
    assert a['first']['invalid']==1 and a['final']['invalid']==0
    assert a['first']['semantic_reviewed'] is False
    assert result['metrics']['A']['primary']['successful_feedback']==120
    assert a['final']['finish_reason_counts']=={'controller_export':160}


def test_source_grounded_code_resolution_preserves_mechanical_evidence(tmp_path):
    rows,_=fixture(tmp_path)
    change_review(tmp_path, rows, 'V3-v3', 's01-1-L3', code_verdict='fail',
                  mechanical_code_verdict='absent', code_resolution_evidence='Snippet changes the wrong branch at source line 2.')
    result=api().analyze(tmp_path)
    assert result['metrics']['V3-v3']['primary']['successful_feedback']==119
    assert result['metrics']['V3-v3']['all']['code_verdicts']['fail']==1
    change_review(tmp_path, rows, 'V3-v3', 's01-1-L3', code_resolution_evidence='')
    with pytest.raises(ValueError):api().analyze(tmp_path)


def test_gold_witness_matches_full_evidence_input_instead_of_historical_first_test(tmp_path):
    fixture(tmp_path)
    path=tmp_path/'evidence/s00-1.json'; evidence=json.loads(path.read_text())
    original=deepcopy(evidence['tests'][0]); evidence['tests'][0]['input']='historical larger witness\n'
    evidence['tests'].append(dict(original,index=48))
    write_json(path,evidence)
    pop=api().validate_populations(tmp_path)
    assert pop['gold_witness']['s00-1']['index']==48
    assert pop['source_validation']['s00-1']['witness']['input']=='0\n'
    book=api().render_casebook(pop)
    assert 'Witness khớp input trong gold' in book
    evidence['tests']=evidence['tests'][:1];write_json(path,evidence)
    with pytest.raises(ValueError, match='witness'):api().validate_populations(tmp_path)


def test_selection_is_frozen_deterministic_includes_harms_and_two_faulty_L3(tmp_path):
    rows,_=fixture(tmp_path)
    def fail(system,eid,axis='factual_fidelity'):
        next(r for r in rows if r['system_id']==system and r['example_id']==eid)['axes'][axis]='fail'
    fail('V2-old','s01-1-L3');fail('V3-v3','s02-1-L3')
    next(r for r in rows if r['system_id']=='A' and r['example_id']=='s03-0-L2')['taxonomy_feedback_contradiction']=True
    invalid=next(r for r in rows if r['system_id']=='V3-v3' and r['example_id']=='s04-1-L2')
    invalid.update(status='malformed_json',parsed=None,raw='{bad',axes={k:'not_evaluable' for k in AXES})
    selection=api().choose_examples(rows)
    assert selection==api().choose_examples(list(reversed(rows)))
    ids=selection['example_ids']; lookup={r['example_id']:r for r in rows}
    assert len(ids)>=6 and len(set(ids))==len(ids)
    assert sum(lookup[e]['faulty'] and lookup[e]['level']==3 for e in ids)>=2
    assert {lookup[e]['faulty'] for e in ids}=={True,False}
    assert {'s01-1-L3','s02-1-L3','s03-0-L2','s04-1-L2'}<=set(ids)
    assert selection['categories']['improvements'] and selection['categories']['regressions']
    assert api().EXAMPLE_POLICY['minimum_examples']==6


def test_L3_examples_prefer_actual_repair_directions_over_false_praise(tmp_path):
    rows,_=fixture(tmp_path)
    actual={'s06-1-L3','s07-1-L3'}
    for r in rows:
        if r['faulty'] and r['level']==3 and r['example_id'] not in actual:
            r['axes']['required_content']='fail'
            r['axes']['l3_repair_direction']='not_applicable'
    selection=api().choose_examples(rows)
    assert set(selection['categories']['faulty_l3_direction'])==actual


def test_casebook_preserves_all_480_outputs_and_escapes_source_output_and_reasons(tmp_path):
    rows,_=fixture(tmp_path)
    rows[0]['evidence']='reason </pre><script>alert("reason")</script>'
    write_rows(tmp_path/'reviews.private.jsonl',rows)
    result=api().build(tmp_path)
    assert result['passed'] and result['panels']==480
    book=(tmp_path/'paired-casebook.html').read_text()
    assert book.count('class="system-panel"')==480 and book.count('class="case"')==160
    assert '<script>alert(' not in book and '<img src=x' not in book
    assert '&lt;script&gt;' in book and '&lt;img' in book and '&lt;/pre&gt;' in book
    assert 'type="search"' in book and 'Raw output' in book and 'Gold và bằng chứng riêng tư' in book
    report=(tmp_path/'REPORT.vi.md').read_text()
    assert '120' in report and '40' in report and 'agent' in report
    assert 'không phải điểm chính thức' in report
    assert (tmp_path/'EXAMPLES.vi.md').exists() and (tmp_path/'decision.json').exists()


def test_missing_A_requires_explicit_unavailability_and_native_report_still_completes(tmp_path):
    rows,_=fixture(tmp_path)
    (tmp_path/'generations/A/final.jsonl').unlink()
    with pytest.raises(ValueError):api().analyze(tmp_path)
    write_json(tmp_path/'systems.json',{'A':{'available':False,'reason':'Missing authentic checkpoint'},'native_systems':{}})
    write_rows(tmp_path/'reviews.private.jsonl',[r for r in rows if r['system_id']!='A'])
    e=[json.loads(s) for s in (tmp_path/'code-evidence.private.jsonl').read_text().splitlines()]
    write_rows(tmp_path/'code-evidence.private.jsonl',[r for r in e if r['system_id']!='A'])
    result=api().build(tmp_path)
    assert result['panels']==320 and result['systems']==['V2-old','V3-v3']
    assert result['passed'] and not result['decision_passed']

