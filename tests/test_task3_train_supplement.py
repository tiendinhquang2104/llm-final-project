"""Artificial sources only; no evaluation or supplement source embedded here."""
from copy import deepcopy
import json
import zipfile

import pytest

from src.task3.eval_snapshot import json_bytes, sha_bytes
from src.task3.eval_v2 import make_guard_registry, with_signature
from src.task3.train_supplement import (
    TRAIN_FAMILIES, load_train_archive, normalize_recipe, validate_reviews,
    screen_sources, build_targets, require_supplement_isolation, verify_bound_snapshot,
    validate_pair_reviews, validate_target_reviews,
    validate_family_reviews,
)


@pytest.fixture
def exam():
    return dict(exam_id='SYN-POWER',exam_type='single_problem',statement='Compute a power.',
                problems=[],grading_policy={'prerequisite':None})


@pytest.fixture
def recipe():
    return dict(sample_id='SUP1-POWER-001',family='SYN-POWER',architecture_id='recursive',
        mechanism_id='wrong-base',mechanism_summary='returns zero at base',
        code='int f(int x) { if (x == 0) return 0; return 2*f(x-1); }',
        domain='nonnegative exponent small enough to avoid overflow',expected_compile='valid_cpp11',
        clean=False,clean_basis='',findings=[dict(label='Lỗi logic',quote='return 0;',
        location='f, base case',cause_vi='Nhánh cơ sở trả về giá trị sai.',impact_vi='Kết quả sai.',
        repair_vi='Đặt lại giá trị cơ sở theo định nghĩa lũy thừa.',
        evidence=dict(kind='static_counterexample',input='x=0',expected='1',actual_derived='0',
                      reasoning='The first branch returns the literal zero.'))],
        testcases=[dict(input='x=0',expected='1',actual_derived='0')],
        provenance=dict(generator='artificial-author',seed=42,origin='archive exam only',not_human_verified=True))


def reviewed(r):
    return dict(sample_id=r['sample_id'],source_sha256=sha_bytes(r['code'].encode()),
        recipe_sha256=sha_bytes(json_bytes(r)),reviewer='independent-reviewer',decision='pass',
        rationale='Checked branch, stated domain and counterexample symbolically.',
        finding_checks=[True for _ in r['findings']],compile_checked=True,domain_checked=True,
        clean_checked=bool(r['clean']),level_text_checked=True)


def test_archive_filters_before_source_read(tmp_path):
    p=tmp_path/'fixture.zip'
    exams=[dict(exam_id=f,exam_type='single_problem',statement=f,problems=[]) for f in TRAIN_FAMILIES]
    rows=[dict(sample_id='OLD-1',input=dict(exam_id='SYN-POWER',code_file='sources/old.cpp'),
               output=dict(taxonomy_error=['Lỗi logic'],feedback='DO NOT RETAIN TEACHER')),
          dict(sample_id='BLOCKED',input=dict(exam_id='SYN-FACT',code_file='missing-eval.cpp'))]
    from src.task3.eval_snapshot import LABEL_SPACE
    with zipfile.ZipFile(p,'w') as z:
        z.writestr('generate-dataset/exams.json',json.dumps({'exams':exams}))
        z.writestr('generate-dataset/label_space.json',json.dumps({'taxonomy_error':LABEL_SPACE}))
        z.writestr('generate-dataset/task3_feedback.json',json.dumps({'samples':rows}))
        z.writestr('generate-dataset/sources/old.cpp','int main(){return 0;}')
    out=load_train_archive(p,expected_sha=sha_bytes(p.read_bytes()))
    assert len(out['originals'])==1
    assert 'DO NOT RETAIN TEACHER' not in json.dumps(out)
    assert 'feedback' not in out['originals'][0]
    assert all('missing-eval' not in p for p in out['member_sha256'])
    with pytest.raises(ValueError,match='SHA'):
        load_train_archive(p,expected_sha='bad')


def test_normalization_binds_context_and_quotes(recipe,exam):
    r=normalize_recipe(recipe,exam)
    assert r['parent_exam_sha256']==sha_bytes(json_bytes(exam))
    assert r['quote_spans'][0]['start']==r['code'].index('return 0;')
    assert r['compiler_diagnostic'] is None
    assert r['compile_evidence']=='static_only'
    assert 'requested_level' not in r


@pytest.mark.parametrize('change', ['family','quote','clean','evidence','human','compile','provenance'])
def test_reject_unsupported_recipe(recipe,exam,change):
    r=deepcopy(recipe)
    if change=='family':r['family']='SYN-FACT'
    if change=='quote':r['findings'][0]['quote']='absent'
    if change=='clean':r['clean']=True
    if change=='evidence':r['findings'][0]['evidence']['reasoning']=''
    if change=='human':r['provenance']['not_human_verified']=False
    if change=='compile':r['expected_compile']='compiler-confirmed'
    if change=='provenance':r['provenance']['generator']=''
    with pytest.raises(ValueError):normalize_recipe(r,exam)


def test_review_hash_and_independence(recipe):
    assert validate_reviews([recipe],[reviewed(recipe)])[recipe['sample_id']]['decision']=='pass'
    for field,value in [('reviewer','artificial-author'),('source_sha256','bad'),('recipe_sha256','bad'),
                        ('finding_checks',[]),('level_text_checked',False)]:
        rr=reviewed(recipe);rr[field]=value
        with pytest.raises(ValueError):validate_reviews([recipe],[rr])
    with pytest.raises(ValueError):validate_reviews([recipe],[])


def test_screen_copy_rename_and_within_bank(recipe,exam):
    r=normalize_recipe(recipe,exam)
    other=dict(r,sample_id='OLD',code=r['code'].replace('f(', 'g(').replace('int x','int y').replace('x ==','y ==').replace('x-1','y-1'))
    decisions=screen_sources([r],[with_signature(other)])
    assert decisions[0]['decision']=='reject'
    a=dict(r,sample_id='OTHER')
    assert screen_sources([r,a],[])[1]['decision']=='reject'


@pytest.mark.parametrize('stage',['before_targets','before_optimizer'])
def test_both_boundaries_positive_negative(recipe,exam,stage):
    r=normalize_recipe(recipe,exam)
    reg=make_guard_registry([r],[],TRAIN_FAMILIES,['SYN-FACT'])
    reg['version']='train-supplement-v1'
    assert require_supplement_isolation([r],reg,stage=stage)['unique_sources']==1
    changes=[dict(family='SYN-FACT'),dict(source_sha256='bad'),dict(code=r['code']+'\n//changed'),
             dict(code=r['code'].replace('f(', 'g(')),dict(group='fake'),dict(sample_id='fake')]
    for change in changes:
        with pytest.raises(ValueError):require_supplement_isolation([dict(r,**change)],reg,stage=stage)
    protected=dict(r,sample_id='OLD')
    for code in [r['code'],r['code']+';']:
        mutated=dict(sample_id=r['sample_id'],family=r['family'],code=code)
        blocked=make_guard_registry([mutated],[protected],TRAIN_FAMILIES,['SYN-FACT'])
        blocked['version']='train-supplement-v1'
        with pytest.raises(ValueError):require_supplement_isolation([mutated],blocked,stage=stage)


def test_true_near_duplicate_and_below_threshold(recipe):
    from src.task3.eval_v2 import similarity
    original=dict(sample_id='OLD',family='SYN-POWER',code=recipe['code'])
    near=dict(sample_id='SUP1-POWER-001',family='SYN-POWER',code=recipe['code']+';')
    far=dict(near,code='struct Box { double values[31]; };')
    assert .85 <= similarity(near,original) < 1
    assert similarity(far,original)<.85
    for stage in ('before_targets','before_optimizer'):
        reg=make_guard_registry([near],[original],TRAIN_FAMILIES,['SYN-FACT']);reg['version']='train-supplement-v1'
        with pytest.raises(ValueError,match='near-duplicate'):require_supplement_isolation([near],reg,stage=stage)
        reg=make_guard_registry([far],[original],TRAIN_FAMILIES,['SYN-FACT']);reg['version']='train-supplement-v1'
        assert require_supplement_isolation([far],reg,stage=stage)['eligible']


def test_guard_rejects_duplicate_batch(recipe,exam):
    r=normalize_recipe(recipe,exam);reg=make_guard_registry([r],[],TRAIN_FAMILIES,['SYN-FACT'])
    reg['version']='train-supplement-v1'
    with pytest.raises(ValueError):require_supplement_isolation([r,r],reg,stage='before_targets')
    with pytest.raises(ValueError):require_supplement_isolation([],reg,stage='before_optimizer')


def test_structured_domain_and_location(recipe,exam):
    r=deepcopy(recipe);r['domain']={'bounds':'nonnegative small exponent'}
    r['findings'][0]['location']={'function':'f','line_start':1}
    rows=build_targets([normalize_recipe(r,exam)])
    assert 'f (dòng 1)' in rows[2]['output']['feedback']


def test_pair_reviews_bind_both_recipe_and_source(recipe):
    other=dict(recipe,sample_id='SUP1-POWER-002',code=recipe['code']+'\n// note')
    pairs=[dict(left=recipe['sample_id'],right=other['sample_id'],similarity=1.0)]
    v=dict(pairs[0],reviewer='reviewer',decision='reject_right',rationale='Only comment differs.')
    for side,r in [('left',recipe),('right',other)]:
        v[side+'_source_sha256']=sha_bytes(r['code'].encode())
        v[side+'_recipe_sha256']=sha_bytes(json_bytes(r))
    assert validate_pair_reviews([recipe,other],pairs,[v])
    for side in ('left','right'):
        for key in ('source','recipe'):
            broken=dict(v);broken[side+'_'+key+'_sha256']='bad'
            with pytest.raises(ValueError,match='binding'):validate_pair_reviews([recipe,other],pairs,[broken])
    with pytest.raises(ValueError,match='author'):
        validate_pair_reviews([recipe,other],pairs,[dict(v,reviewer=recipe['provenance']['generator'])])


def test_target_reviews_bind_actual_render_and_independent_reviewer(recipe,exam):
    r=normalize_recipe(recipe,exam);examples=build_targets([r]);ledger=[]
    for e in examples:
        ledger.append(dict(example_id=e['example_id'],example_sha256=sha_bytes(json_bytes(e)),
            reviewer='independent-reviewer',rationale='Source and Level contract checked.',pass_=True,
            checks={k:True for k in ('source_grounded','level_contract','vietnamese','taxonomy_consistent')}))
        ledger[-1]['pass']=ledger[-1].pop('pass_')
    assert validate_target_reviews(examples,ledger,[r])
    for key,value in [('reviewer',recipe['provenance']['generator']),('example_sha256','bad'),('checks',{})]:
        broken=deepcopy(ledger);broken[0][key]=value
        with pytest.raises(ValueError):validate_target_reviews(examples,broken,[r])


def test_family_audits_bind_code_recipe_and_reviewer(recipe):
    recipes=[dict(recipe,family=f,sample_id='SUP1-'+f[4:]+'-001') for f in TRAIN_FAMILIES]
    audits=[]
    for r in recipes:
        design={k:r[k] for k in ('sample_id','architecture_id','mechanism_id')}
        design.update(source_sha256=sha_bytes(r['code'].encode()),recipe_sha256=sha_bytes(json_bytes(r)))
        audits.append(dict(family=r['family'],reviewer='independent-reviewer',assessment='Core designs compared.',designs=[design]))
    assert validate_family_reviews(recipes,audits)
    for field in ('source_sha256','recipe_sha256'):
        broken=deepcopy(audits);broken[0]['designs'][0][field]='bad'
        with pytest.raises(ValueError):validate_family_reviews(recipes,broken)
    broken=deepcopy(audits);broken[0]['reviewer']=recipe['provenance']['generator']
    with pytest.raises(ValueError):validate_family_reviews(recipes,broken)
    with pytest.raises(ValueError):validate_family_reviews(recipes,audits[:-1])


def test_actual_target_writer_checks_source_freeze_before_any_write(tmp_path,monkeypatch):
    import scripts.task3_train_supplement as cli
    monkeypatch.setattr(cli,'TARGET',tmp_path/'targets')
    monkeypatch.setattr(cli,'TARGET_MANIFEST',tmp_path/'target-manifest.json')
    def stale():raise ValueError('source seal drift')
    monkeypatch.setattr(cli,'verify_sources',stale)
    with pytest.raises(ValueError,match='seal drift'):cli.targets()
    assert not (tmp_path/'targets').exists()


def test_actual_writer_rechecks_guard_and_refuses_overwrite(recipe,exam,tmp_path,monkeypatch):
    import scripts.task3_train_supplement as cli
    r=normalize_recipe(recipe,exam);reg=make_guard_registry([r],[],TRAIN_FAMILIES,['SYN-FACT']);reg['version']='train-supplement-v1'
    monkeypatch.setattr(cli,'TARGET',tmp_path/'targets');monkeypatch.setattr(cli,'TARGET_MANIFEST',tmp_path/'manifest-target.json')
    manifest=tmp_path/'source-manifest.json';manifest.write_text('{}');monkeypatch.setattr(cli,'MANIFEST',manifest)
    changed=dict(r,code=r['code']+'changed')
    monkeypatch.setattr(cli,'verify_sources',lambda: ({},[changed],reg))
    with pytest.raises(ValueError):cli.targets()
    assert not cli.TARGET.exists()
    monkeypatch.setattr(cli,'verify_sources',lambda: ({},[r],reg))
    assert cli.targets()['draft_examples']==4
    with pytest.raises(FileExistsError):cli.targets()


def test_level_blind_targets(recipe,exam):
    r=normalize_recipe(recipe,exam)
    rows=build_targets([r])
    assert len(rows)==4
    diagnostic=rows[0]
    assert 'requested_level' not in diagnostic['input']
    assert diagnostic['output']['taxonomy_error']==['Lỗi logic']
    feedback=rows[1:]
    assert [r['input']['requested_level'] for r in feedback]==[1,2,3]
    assert all(r['input']['diagnosis']==diagnostic['output'] for r in feedback)
    assert 'f, base case' not in feedback[0]['output']['feedback']
    assert recipe['findings'][0]['repair_vi'] not in feedback[1]['output']['feedback']
    assert recipe['findings'][0]['repair_vi'] in feedback[2]['output']['feedback']
    assert all(r['draft'] and not r['human_verified'] for r in rows)


def test_clean_is_scoped_not_compile_pass(recipe,exam):
    r=deepcopy(recipe);r.update(clean=True,findings=[],clean_basis='Invariant within stated domain.')
    n=normalize_recipe(r,exam);rows=build_targets([n])
    assert rows[0]['output']['taxonomy_error']==[]
    assert 'miền' in rows[1]['output']['feedback']
    r['clean_basis']=''
    with pytest.raises(ValueError):normalize_recipe(r,exam)


def test_snapshot_pins_inventory_and_rejects_tamper(tmp_path):
    from src.task3.eval_snapshot import write_new,write_seal,sha_file
    write_new(tmp_path/'data.json',{'x':1})
    hashes={'data.json':sha_file(tmp_path/'data.json')}
    write_seal(tmp_path/'seal.json',hashes)
    assert verify_bound_snapshot(tmp_path,hashes)==hashes
    (tmp_path/'data.json').write_text('{}')
    with pytest.raises(ValueError):verify_bound_snapshot(tmp_path,hashes)
    write_new(tmp_path/'other.json',{})
    (tmp_path/'seal.json').write_text(json.dumps({'hashes':{'other.json':sha_file(tmp_path/'other.json')}}))
    with pytest.raises(ValueError):verify_bound_snapshot(tmp_path,hashes)
