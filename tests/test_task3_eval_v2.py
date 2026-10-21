"""Family-first v2 policy regressions; artificial code fixtures only."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from src.task3 import eval_v2 as v
from src.task3.eval_snapshot import identity, structural_shingles


def source(sid,family,code):
    r=dict(sample_id=sid,family=family,code=code,original_submission_id=sid)
    return dict(r,**{k:x for k,x in identity(r).items() if k not in r})


def test_partition_disjoint_complete_and_not_exposure_driven():
    p={'train_families':['known-a'],'evaluation_families':['known-b']}
    v.validate_partition(p,{'known-a','known-b'})
    with pytest.raises(ValueError,match='partition'):
        v.validate_partition(dict(p,evaluation_families=['known-a','known-b']),{'known-a','known-b'})
    with pytest.raises(ValueError,match='partition'):
        v.validate_partition(p,{'known-a','known-b','missing'})


def fixture_registry():
    good=source('unused','known-train','int solve(int x){return x*7+3;}')
    bad=source('used','known-train','int old(int a){return a/11;}')
    ev=source('eval','held-family','int main(){return 55;}')
    registry=v.make_guard_registry([good],[bad,ev],['known-train'],['held-family'])
    return good,bad,ev,registry


@pytest.mark.parametrize('stage',['before_targets','before_optimizer'])
def test_prior_family_exposure_does_not_ban_unused_train_source(stage):
    good,bad,ev,registry=fixture_registry()
    registry['family_exposure']={'known-train':['R13 corpus exposure']}
    assert v.require_train_isolation([good],registry,stage=stage)['eligible'] is True
    with pytest.raises(ValueError,match='leakage|not eligible'):
        v.require_train_isolation([bad],registry,stage=stage)


@pytest.mark.parametrize('stage',['before_targets','before_optimizer'])
@pytest.mark.parametrize('attack',['family','code','rename','group','source_hash','unknown_id'])
def test_both_boundaries_reject_identity_spoofing(stage,attack):
    good,bad,ev,registry=fixture_registry();row=deepcopy(good)
    if attack=='family':row['family']='held-family'
    elif attack=='code':row['code']=ev['code']
    elif attack=='rename':row['code']='int z(int y){return y/11;}'
    elif attack=='group':row['group']=bad['group']
    elif attack=='source_hash':row['source_sha256']='0'*64
    elif attack=='unknown_id':row['sample_id']='invented'
    with pytest.raises(ValueError):v.require_train_isolation([row],registry,stage=stage)


def test_guard_fails_closed_on_missing_source_or_stage():
    good,_,_,registry=fixture_registry();del good['code']
    with pytest.raises(ValueError,match='source'):v.require_train_isolation([good],registry,stage='before_targets')
    with pytest.raises(ValueError,match='stage'):v.require_train_isolation([],registry,stage='later')


@pytest.mark.parametrize('stage',['before_targets','before_optimizer'])
def test_near_duplicate_screen_is_enforced_even_for_whitelisted_metadata(stage):
    old=source('old','other-family','int sum(int x){int s=0;for(int i=0;i<x;i++){s+=i;}return s;}')
    near=source('near','train-family',old['code']+';')
    assert v.similarity(near,old)>=0.85
    registry=v.make_guard_registry([near],[old],['train-family'],['eval-family'])
    with pytest.raises(ValueError,match='near'):v.require_train_isolation([near],registry,stage=stage)


def test_style_needs_explicit_rule_and_real_construct():
    assert v.style_assessment('No pow calls permitted.','int f(){return 1;}')['confirmed'] is False
    assert v.style_assessment('No pow calls permitted.','int f(){return pow(2,3);}')['confirmed'] is True
    assert v.style_assessment('Return a square.','int f(){return pow(2,3);}')['confirmed'] is False
    assert v.style_assessment('Lưu ý: không được dùng hàm pow.','// pow(2,3)\nint f(){return 1;}')['confirmed'] is False
    assert v.style_assessment('No pow calls permitted.','const char* s="pow(2,3)";')['confirmed'] is False


def test_real_v2_split_train_positive_and_disjoint():
    from scripts.task3_freeze_eval_v2 import plan
    repo=Path(__file__).resolve().parents[1]
    if not (repo/'generate-dataset_v2.zip').exists() or not (repo/'outputs/task3/eval-freeze-v2-20261021/train-near-review.private.json').exists():pytest.skip('private v2 inputs unavailable')
    data=plan()
    train=data['train_records'];evaluation=data['snapshot']['records'];p=data['partition']
    assert len(train)==8 and len({r['family'] for r in train})==5
    assert {r['family'] for r in train}<=set(p['train_families'])
    assert {r['family'] for r in evaluation}<=set(p['evaluation_families'])
    for key in ['sample_id','group','source_sha256','code_identity','renamed_identity']:
        assert not {r[key] for r in train}&{r[key] for r in evaluation}
    assert all(v.similarity(t,e)<.85 for t in train for e in evaluation)
    for stage in ['before_targets','before_optimizer']:
        assert v.require_train_isolation(train,data['guard_registry'],stage=stage)['eligible']
        for r in evaluation:
            with pytest.raises(ValueError):v.require_train_isolation([r],data['guard_registry'],stage=stage)
    for decision in data['manual_review']['records']:
        if not decision['admit']:
            original=next(r for r in data['archive']['records'] if r['sample_id']==decision['sample_id'])
            for stage in ['before_targets','before_optimizer']:
                with pytest.raises(ValueError):v.require_train_isolation([original],data['guard_registry'],stage=stage)
    assert len(data['disagreement_review']['records'])==19
    assert len(data['support']['annotation_v2'])==len(data['support']['source_reference'])==10


def test_manual_template_review_is_required_complete_and_removes_false_admissions():
    good,bad,_,_=fixture_registry()
    decisions={'records':[{'sample_id':good['sample_id'],'admit':True,'reason':'different computation'},
                          {'sample_id':bad['sample_id'],'admit':False,'reason':'same template with predicate edit'}]}
    admitted,rejected=v.apply_manual_review([good,bad],decisions)
    assert [r['sample_id'] for r in admitted]==[good['sample_id']]
    assert [r['sample_id'] for r in rejected]==[bad['sample_id']]
    with pytest.raises(ValueError,match='manual'):
        v.apply_manual_review([good,bad],{'records':decisions['records'][:1]})
    malformed=deepcopy(decisions);malformed['records'][0]['admit']='yes'
    with pytest.raises(ValueError,match='manual'):v.apply_manual_review([good,bad],malformed)


@pytest.mark.parametrize('field',['code','statement','annotation_v2','family','source_sha256'])
def test_reference_cannot_spoof_archive_source_or_gold(field):
    original=source('a','family-a','int main(){return 0;}')
    original.update(statement='Return0.',annotation_v2=[])
    edited=deepcopy(original)
    edited[field]=['Lỗi logic'] if field=='annotation_v2' else 'tampered'
    with pytest.raises(ValueError,match='archive'):
        v.validate_reference_origin([edited],[original])
    v.validate_reference_origin([original],[original])


def test_v2_plan_preserves_v1_and_does_not_read_prediction_or_public_inputs(monkeypatch):
    from scripts.task3_freeze_eval_v2 import plan, WORK
    if not (WORK/'train-near-review.private.json').exists():pytest.skip('private v2 inputs unavailable')
    baseline=json.loads((WORK/'original-hashes.private.json').read_text())
    original=Path.open
    def checked(path,*args,**kwargs):
        assert not any(part in str(path) for part in ['predictions.json','traces.json','public_test_release','public-test/','A-results.private','B-results.private'])
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',checked)
    data=plan()
    assert data['partition']['stage']=='family assignment before source selection'
    from src.task3.eval_snapshot import sha_file
    # Baseline verification is separate from selection; it may hash preserved files.
    monkeypatch.setattr(Path,'open',original)
    assert all(sha_file(path)==h for path,h in baseline.items())


@pytest.mark.parametrize('partition_hash,manifest_hash',[('old',None),('current','old')])
def test_parent_binding_rejects_other_valid_but_different_v1(partition_hash,manifest_hash):
    with pytest.raises(ValueError,match='parent'):
        v.require_parent_binding({'parent_v1_manifest_sha256':partition_hash},'current',manifest_hash)
    v.require_parent_binding({'parent_v1_manifest_sha256':'current'},'current','current')
