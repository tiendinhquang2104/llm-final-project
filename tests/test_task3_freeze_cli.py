"""Preparation contracts, with source review generated only from private inputs."""
import copy
import json
from pathlib import Path
import pytest
from scripts.task3_freeze_eval import assemble, verify_snapshot
from src.task3.eval_snapshot import read_archive
from src.task3.eval_history import historical_inventory


@pytest.fixture(scope='module')
def assembled():
    repo=Path(__file__).resolve().parents[1];work=repo/'outputs/task3/eval-freeze-v1-20261021'
    if not (work/'review-2.private.json').exists():pytest.skip('private source review unavailable')
    a=read_archive(repo/'generate-dataset_v2.zip');h=historical_inventory(repo,a)
    reviews=sum([json.loads((work/f'review-{i}.private.json').read_text()) for i in range(3)],[])
    ids=json.loads((work/'selection-draft.private.json').read_text())+['SYN-PRIME-0010']
    return assemble(a,h,reviews,ids)


def test_assembly_has_unique_sources_clean_scopes_and_fixed_cf(assembled):
    snapshot,registry,inputs,meta,near=assembled
    assert len(snapshot['records'])==86
    assert len({r['renamed_identity'] for r in snapshot['records']})==86
    assert len(snapshot['requests'])==122
    assert len([r for r in snapshot['requests'] if r['kind']=='counterfactual'])==36
    assert len({r['sample_id'] for r in snapshot['requests'] if r['kind']=='counterfactual'})==12
    assert len(meta['support']['annotation_v2'])==len(meta['support']['source_reference'])==10
    assert meta['support']['source_reference']['Lỗi style']==0
    assert meta['support']['defect_status']['scoped_clean']>=9
    assert meta['support']['defect_status']['unresolved']==1
    assert meta['new_source_count']==7
    assert meta['blind_benchmark'] is False
    assert meta['planned_train_eligible_count']==0
    assert not near['admitted_train_overlaps']


def test_model_inputs_are_gold_free_and_cf_task_identical(assembled):
    snapshot,registry,inputs,meta,near=assembled
    by={}
    for row in inputs:
        assert set(row)=={'request_id','sample_id','kind','requested_level','task'}
        assert set(row['task'])=={'statement','problems','grading_policy','student_code','compiler_evidence','allowed_labels'}
        assert 'taxonomy_error' not in row['task']
        if row['kind']=='counterfactual':
            by.setdefault(row['sample_id'],[]).append(row)
    for rows in by.values():
        assert {r['requested_level'] for r in rows}=={1,2,3}
        assert rows[0]['task']==rows[1]['task']==rows[2]['task']


def test_every_finding_has_source_spans_and_level_rubric(assembled):
    snapshot=assembled[0]
    for r in snapshot['records']:
        for f in r['findings']:
            assert f['quote_spans']
            for span in f['quote_spans']:
                assert r['code'][span['start']:span['end']]==f['quote']
            assert set(f['feedback_rubric'])=={'1','2','3','4'}
            assert f['feedback_rubric']['2']['forbidden']==['concrete repair direction','repair code']


def test_assembly_rejects_reused_ids_and_missing_review(assembled):
    # Pure malformed reference input should fail rather than create a partial freeze.
    from scripts.task3_freeze_eval import assemble
    with pytest.raises(ValueError,match='duplicate'):
        assemble({'records':[]},{'entries':[]},[],['same','same'])


def test_conditional_after_repair_is_not_a_required_primary_finding(assembled):
    records=assembled[0]['records']
    r=next(r for r in records if r['sample_id']=='SYN-POWER-0008')
    assert r['conditional_findings']
    assert all(f['status']!='conditional' for f in r['findings'])
    assert assembled[3]['support']['conditional_finding_count']==1


def test_review_cannot_override_archive_code_or_gold():
    from scripts.task3_freeze_eval import assemble
    row={'sample_id':'x','code':'int main(){return 0;}', 'family':'f', 'group':'g',
         'source_sha256':'s','code_identity':'c','renamed_identity':'r'}
    rev={'sample_id':'x','defect_status':'scoped_clean','domain':'scoped','clean_basis':'proof',
         'source_reference':[],'findings':[], 'code':'int main(){return 1;}'}
    with pytest.raises(ValueError,match='review.*field|immutable'):
        assemble({'records':[row]},{'entries':[]},[rev],['x'])


def test_freeze_hashes_identity_and_taxonomy_dependencies():
    from scripts.task3_freeze_eval import IMPLEMENTATION
    assert {'src/task3/schema.py','src/synth/taxonomy.py','src/synth/feedback.py'}<=set(IMPLEMENTATION)
