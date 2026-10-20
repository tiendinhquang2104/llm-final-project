"""Snapshot safety tests use artificial code only; real sources remain ignored."""
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from src.task3 import eval_snapshot as s


def toy_archive(path, *, code_path='submissions/a.cpp', duplicate=False):
    samples=[{'sample_id':'toy-a','input':{'exam_id':'toy','code_file':code_path},
              'output':{'taxonomy_error':[], 'feedback':'NEVER USE THIS TEACHER PROSE'}}]
    if duplicate: samples*=2
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('generate-dataset/task3_feedback.json',json.dumps({'samples':samples}))
        z.writestr('generate-dataset/exams.json',json.dumps({'exams':[{'exam_id':'toy','exam_type':'single_problem','statement':'Return zero.'}]}))
        z.writestr('generate-dataset/label_space.json',json.dumps({'taxonomy_error':list(s.LABEL_SPACE)}))
        z.writestr('generate-dataset/submissions/a.cpp','int main(){return 0;}')
    return s.sha_file(path)


def test_archive_checks_bytes_and_retains_member_provenance_not_teacher(tmp_path):
    p=tmp_path/'anything.zip';h=toy_archive(p)
    d=s.read_archive(p,expected_sha=h,expected_count=1)
    assert d['records'][0]['source_sha256']==hashlib.sha256(b'int main(){return 0;}').hexdigest()
    assert 'NEVER USE' not in json.dumps(d)
    assert len(d['members_sha256'])==4
    with pytest.raises(ValueError,match='archive SHA'):s.read_archive(p,expected_sha='0'*64,expected_count=1)
    with pytest.raises(ValueError,match='record count'):s.read_archive(p,expected_sha=h,expected_count=2)


@pytest.mark.parametrize('path',['../a.cpp','/a.cpp','submissions/../../a.cpp','submissions\\a.cpp'])
def test_archive_rejects_unsafe_source_paths(tmp_path,path):
    p=tmp_path/'a.zip';h=toy_archive(p,code_path=path)
    with pytest.raises(ValueError,match='source path'):s.read_archive(p,expected_sha=h,expected_count=1)


def test_duplicate_ids_rejected(tmp_path):
    p=tmp_path/'a.zip';h=toy_archive(p,duplicate=True)
    with pytest.raises(ValueError,match='duplicate'):s.read_archive(p,expected_sha=h,expected_count=2)


def test_rename_and_near_duplicate_detection():
    a='int sum(int x){int s=0;for(int i=0;i<x;i++){s+=i;}return s;}'
    b='int total(int n){int q=0;for(int j=0;j<n;j++){q+=j;}return q;}'
    assert s.identity({'sample_id':'a','family':'f','code':a})['renamed_identity']==s.identity({'sample_id':'b','family':'g','code':b})['renamed_identity']
    assert s.near_similarity(a,b)==1.0
    assert s.near_similarity(a,a.replace('s+=i','s-=i'))>0.65
    assert s.near_similarity(a,'int main(){return 0;}')<0.5


@pytest.mark.parametrize('stage',['before_targets','before_optimizer'])
@pytest.mark.parametrize('field',['sample_id','group','family','source_sha256','code_identity','renamed_identity'])
def test_train_gate_blocks_every_identity_dimension(stage,field):
    old={'sample_id':'history','group':'g','family':'fam','source_sha256':'s','code_identity':'c','renamed_identity':'r'}
    new={'sample_id':'new','group':'newg','family':'newfam','source_sha256':'news','code_identity':'newc','renamed_identity':'newr'}
    new[field]=old[field]
    with pytest.raises(ValueError,match='leakage'):s.require_train_isolation([new],{'entries':[old]},stage=stage)


def test_gate_fails_closed_on_missing_identities_and_unknown_stage():
    with pytest.raises(ValueError,match='identity'):s.require_train_isolation([{'sample_id':'x'}],{'entries':[]},stage='before_targets')
    with pytest.raises(ValueError,match='stage'):s.require_train_isolation([],{'entries':[]},stage='later')


def test_level_assignment_is_deterministic_and_matches_public_ratio():
    records=[{'sample_id':f'x-{i}','family':f'f-{i%28}'} for i in range(86)]
    levels=s.assign_levels(records)
    assert levels==s.assign_levels(records)
    from collections import Counter
    assert Counter(levels.values())=={1:28,2:40,3:12,4:6}


def test_rubric_contract_is_level_not_taxonomy():
    assert set(s.LEVEL_CONTRACTS)=={'1','2','3','4'}
    assert s.LEVEL_CONTRACTS['1']['allow_location'] is False
    assert s.LEVEL_CONTRACTS['2']['allow_repair'] is False
    assert s.LEVEL_CONTRACTS['3']['require_feasible_repair'] is True
    assert s.LEVEL_CONTRACTS['3']['allow_full_solution'] is False
    assert s.LEVEL_CONTRACTS['4']['allow_full_solution'] is True


def test_seal_rejects_tamper_and_refuses_overwrite(tmp_path):
    p=tmp_path/'a.json';p.write_text('{}')
    seal=tmp_path/'seal.json'
    s.write_seal(seal,{'a.json':s.sha_file(p)})
    assert s.verify_seal(seal)=={'a.json':s.sha_file(p)}
    with pytest.raises(FileExistsError):s.write_seal(seal,{'a.json':s.sha_file(p)})
    p.write_text('{"tamper":true}')
    with pytest.raises(ValueError,match='hash mismatch'):s.verify_seal(seal)


def test_review_validation_checks_exact_quotes_and_clean_proof():
    row={'sample_id':'x','code':'int main(){return 0;}'}
    review={'sample_id':'x','defect_status':'defect','source_reference':['Lỗi logic'], 'domain':'valid input','findings':[{'finding_id':'f','label':'Lỗi logic','quote':'return 0;', 'cause':'wrong return', 'impact':'wrong status','evidence':{'reasoning':'spec says1'},'status':'agent-reviewed static reasoning','repair_direction':'return1'}]}
    s.validate_review(row,review)
    review['findings'][0]['quote']='return 2;'
    with pytest.raises(ValueError,match='quote'):s.validate_review(row,review)
    with pytest.raises(ValueError,match='clean'):s.validate_review(row,dict(sample_id='x',defect_status='scoped_clean',source_reference=[],domain='valid',findings=[],clean_basis=''))


def test_historical_inventory_is_complete_and_uses_metadata_only():
    from src.task3.eval_history import historical_inventory, METADATA_PATHS
    repo=Path(__file__).resolve().parents[1]
    if not (repo/'generate-dataset_v2.zip').exists():pytest.skip('private archive unavailable')
    archive=s.read_archive(repo/'generate-dataset_v2.zip')
    h=historical_inventory(repo,archive)
    ids={r['sample_id'] for r in h['entries']}
    assert {'SYN-COUNTEVEN-0001','SYN-SUMPAIR-0003'}<=ids
    assert h['counts']['r18_training_ids']==20
    assert h['counts']['prepared_synthetic_train']==495
    assert h['counts']['prepared_synthetic_heldout']==47
    assert h['counts']['prepared_real_val']==6
    assert len(h['new_source_ids'])==15
    for part in ['real-val','synthetic-heldout']:
        for line in (repo/f'data/processed/task3/{part}.jsonl').read_text().splitlines():
            assert json.loads(line)['record']['sample_id'] in ids
    assert all('public' not in p and 'predictions' not in p and 'RESULTS' not in p for p in METADATA_PATHS)
    assert len(h['input_hashes'])>=15
    assert all(all(row.get(k) for k in s.IDENTITY_KEYS) for row in h['entries'])


def test_candidate_pool_is_not_reported_as_model_output_exposure(monkeypatch):
    from src.task3.eval_history import historical_inventory
    repo=Path(__file__).resolve().parents[1]
    if not (repo/'generate-dataset_v2.zip').exists():pytest.skip('private archive unavailable')
    archive=s.read_archive(repo/'generate-dataset_v2.zip')
    original=Path.open
    def checked(path,*a,**kw):
        name=str(path)
        assert not any(x in name for x in ['public-test','public_test','predictions.json','traces.json','RESULTS_','-results.private'])
        return original(path,*a,**kw)
    monkeypatch.setattr(Path,'open',checked)
    h=historical_inventory(repo,archive)
    rows=[r for r in h['entries'] if r['sample_id']=='SYN-COUNT-0008']
    assert rows and all(not r['direct_experiment_use'] for r in rows)
    assert any('source pool' in e for r in rows for e in r['exposures'])


def test_rewritten_seal_cannot_override_handoff_hashes(tmp_path):
    p=tmp_path/'a.json';p.write_text('{}');expected={'a.json':s.sha_file(p)}
    seal=tmp_path/'seal.json';s.write_seal(seal,expected)
    p.write_text('{"tampered":true}')
    seal.write_text(json.dumps({'hashes':{'a.json':s.sha_file(p)}}))
    with pytest.raises(ValueError,match='sealed hash inventory mismatch|hash mismatch'):
        s.verify_seal(seal,expected_hashes=expected)
