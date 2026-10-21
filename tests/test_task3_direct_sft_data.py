"""Independent fixtures: guards must reject leakage while permitting same-family TRAIN."""
from copy import deepcopy
import importlib
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest


def module():
    assert importlib.util.find_spec('src.task3.direct_sft_data') is not None, 'new DIRECT data gate is required'
    return importlib.import_module('src.task3.direct_sft_data')


def row(sid, code, family='shared', split='train'):
    return dict(sample_id=sid, code=code, family=family, group=sid, split=split,
                origin='real-train', provenance={'kind':'real'})


TRAIN = 'int main(){ int values[4]={4,8,2,9}; for(int k=3;k>=0;--k) values[k]+=7; return values[0]; }'
PROTECTED = 'double average(double x, double y){ return (x+y)/2.0; }'


def test_same_family_source_is_eligible_without_exposure_blanket_ban():
    m=module();r=row('train',TRAIN);p=row('eval',PROTECTED)
    eligible,excluded=m.select_candidates([r],[p])
    assert [r['sample_id'] for r in eligible]==['train']
    assert excluded==[]
    reg=m.make_registry(eligible,[p])
    assert m.require_direct_isolation(eligible,reg,stage='before_optimizer')['checked']==1


@pytest.mark.parametrize('field,value', [('sample_id','protected'),('group','protected')])
def test_id_or_group_collision_is_excluded(field,value):
    m=module();r=row('train',TRAIN);r[field]=value
    eligible,excluded=m.select_candidates([r],[row('protected',PROTECTED)])
    assert not eligible
    assert any(field in reason for reason in excluded[0]['reasons'])


def test_identifier_renamed_source_collision_is_excluded():
    m=module();r=row('train',PROTECTED.replace('average','mean').replace('x','a').replace('y','b'))
    eligible,excluded=m.select_candidates([r],[row('protected',PROTECTED)])
    assert not eligible
    assert any('renamed_identity' in reason for reason in excluded[0]['reasons'])


def test_near_duplicate_with_changed_literal_is_excluded_at_fixed_threshold():
    m=module()
    long_code=TRAIN+' int constants[]={101,103,107,109,113,127,131,137,139,149,151,157,163,167,173,179,181,191,193,197};'
    r=row('train',long_code.replace('+=7','+=6'))
    eligible,excluded=m.select_candidates([r],[row('protected',long_code)])
    assert not eligible
    assert any('near_duplicate' in reason for reason in excluded[0]['reasons'])


@pytest.mark.parametrize('stage',['before_targets','before_optimizer'])
def test_boundary_recomputes_exact_source_and_rejects_missing_source(stage):
    m=module();sources,_=m.select_candidates([row('train',TRAIN)],[]);reg=m.make_registry(sources,[])
    changed=deepcopy(sources);changed[0]['code']+=' // changed actual bytes'
    with pytest.raises(ValueError,match='source|identity'):m.require_direct_isolation(changed,reg,stage=stage)
    missing=deepcopy(sources);missing[0].pop('code')
    with pytest.raises(ValueError,match='source'):m.require_direct_isolation(missing,reg,stage=stage)


def test_boundary_rejects_duplicate_source_across_train_validation():
    m=module();sources,_=m.select_candidates([row('train',TRAIN)],[]);reg=m.make_registry(sources,[])
    duplicated=deepcopy(sources)*2;duplicated[1]=dict(duplicated[1],split='validation')
    with pytest.raises(ValueError,match='duplicate'):m.require_direct_isolation(duplicated,reg,stage='before_optimizer')


def test_protected_signatures_fail_closed_and_threshold_cannot_be_relaxed():
    m=module()
    with pytest.raises(ValueError,match='signature|shingle'):m.make_registry([row('train',TRAIN)],[{'sample_id':'public'}])
    sources,_=m.select_candidates([row('train',TRAIN)],[]);reg=m.make_registry(sources,[]);reg['near_threshold']=.99
    with pytest.raises(ValueError,match='threshold'):m.require_direct_isolation(sources,reg,stage='before_optimizer')


def test_public_fingerprints_retain_no_source_context_or_outputs(tmp_path):
    m=module();root=tmp_path/'public';root.mkdir();(root/'one.cpp').write_text(PROTECTED)
    (root/'task3_feedback.json').write_text(json.dumps({'samples':[{'sample_id':'PUB1','input':{'code_file':'one.cpp','exam_id':'exam','statement':'SECRET'},'output':{'feedback':'SECRET'}}]}))
    result=m.public_fingerprints(root,expected_count=1)
    assert len(result['entries'])==1
    assert not ({'code','statement','feedback','requested_level'} & result['entries'][0].keys())
    assert 'SECRET' not in json.dumps(result)


def test_inventory_rejects_untrusted_archive_before_loading_any_members(tmp_path):
    m=module();(tmp_path/'generate-dataset_v2.zip').write_bytes(b'not the declared archive')
    with pytest.raises(ValueError,match='archive SHA'):m.inventory_sources(tmp_path)


def test_inventory_cli_is_inspectable_without_model_dependencies():
    import subprocess
    import sys
    result=subprocess.run([sys.executable,'scripts/task3_direct_sft_inventory.py','--help'],capture_output=True,text=True)
    assert result.returncode==0, result.stderr
    assert 'inventory' in result.stdout and 'train-gate' in result.stdout


def test_public_empty_submission_still_gets_protected_fingerprint(tmp_path):
    m=module();(tmp_path/'empty.cpp').write_bytes(b'')
    (tmp_path/'task3_feedback.json').write_text(json.dumps({'samples':[{'sample_id':'EMPTY','input':{'code_file':'empty.cpp','exam_id':'exam'}}]}))
    result=m.public_fingerprints(tmp_path,expected_count=1)
    assert result['entries'][0]['source_sha256']=='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'


def test_supplement_preserves_preexisting_scope_and_never_imports_old_target_prose():
    m=module()
    assert hasattr(m,'normalize_supplement'), 'separate supplemental source normalization required'
    source=dict(sample_id='SUP',family='shared',group='sup',code=TRAIN,clean=True,
        domain='Input is a fixed four-element array.',clean_basis='All four elements are initialized.',
        parent_exam={'exam_id':'shared','exam_type':'single_problem','statement':'Compute result.','problems':[],'grading_policy':None},
        reviewed_clean_basis_vi='OLD_TARGET_PROSE',source_sha256='incorrect')
    with pytest.raises(ValueError,match='hash'):m.normalize_supplement(source)
    source.pop('source_sha256')
    result=m.normalize_supplement(source)
    assert result['statement']=='Compute result.'
    assert result['original_scoped_domain']=='Input is a fixed four-element array.'
    assert result['origin']=='synth-supplement'
    assert result['taxonomy_annotation']==[]
    assert 'OLD_TARGET_PROSE' not in json.dumps(result)
