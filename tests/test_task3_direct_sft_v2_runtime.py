"""Artificial v2 runtime checks; never load a model or inspect private datasets."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from src.task3.inference import MockTokenizer

ROOT = Path(__file__).resolve().parents[1]


def runtime():
    assert (ROOT/'src/task3/direct_sft_v2_training.py').exists(), 'isolated v2 training runtime is missing'
    from src.task3 import direct_sft_v2_training
    return direct_sft_v2_training


def example(sid='fixture'):
    return dict(sample_id=sid, example_id=f'direct-v2:{sid}@L1',kind='direct',loss_weight=1.,
                source_sha256=hashlib.sha256(b'source').hexdigest(),
                messages=[dict(role='user',content='source')],completion=json.dumps(dict(taxonomy_error=[],feedback='reviewed final')))


def test_v2_config_is_explicit_and_rejects_old_paths_adapters_and_unknowns():
    training=runtime()
    config=json.loads((ROOT/'configs/task3/direct_sft_v2_20261021.json').read_text())
    training.validate_frozen_config(config)
    for key,value in [('work_dir','outputs/task3/direct-sft-v1-20261021'),('resume',True),('adapter','old'),('epochs',3),('revision','main'),('surprise',1)]:
        with pytest.raises(ValueError):training.validate_frozen_config(dict(config,**{key:value}))


def test_v2_preserves_exact_old_validation_membership():
    assert (ROOT/'scripts/task3_direct_sft_v2_prepare.py').exists(), 'isolated v2 prepare is missing'
    from scripts.task3_direct_sft_v2_prepare import preserved_split
    old=[dict(sample_id=f'v{i}',code=f'old{i}') for i in range(14)]
    sources=old+[dict(sample_id='new',code='new')]
    train,val=preserved_split(sources,old)
    assert train==[sources[-1]] and val==old
    with pytest.raises(ValueError,match='validation'):preserved_split(sources[1:],old)
    changed=copy.deepcopy(sources);changed[0]['code']='changed'
    with pytest.raises(ValueError,match='validation'):preserved_split(changed,old)


def test_v2_encoding_reuses_prefix_mask_truncation_and_source_binding():
    training=runtime();examples=[example()]
    rows,audit=training.encode_direct_examples(MockTokenizer(),examples,8192)
    assert rows[0]['labels'][0]==-100 and audit['supervised_tokens']>0
    training.verify_encoded_binding(MockTokenizer(),examples,rows,[dict(sample_id='fixture',code='source')],8192)
    with pytest.raises(ValueError,match='source'):training.verify_encoded_binding(MockTokenizer(),examples,rows,[dict(sample_id='fixture',code='changed')],8192)
    with pytest.raises(ValueError,match='truncated'):training.encode_direct_examples(MockTokenizer(),examples,3)
    class Unstable(MockTokenizer):
        def apply_chat_template(self,messages,**kwargs):
            result=super().apply_chat_template(messages,**kwargs)
            return [999]+result if messages[-1]['role']=='assistant' else result
    with pytest.raises(ValueError,match='prefix'):training.encode_direct_examples(Unstable(),examples,8192)


def test_v2_marker_is_exclusive(tmp_path):
    training=runtime();marker=tmp_path/'optimizer-started.json'
    training.claim_optimizer_start(marker,dict(version='v2'))
    with pytest.raises(FileExistsError):training.claim_optimizer_start(marker,dict(version='v2'))
    assert json.loads(marker.read_text())==dict(version='v2')


def test_v2_only_inference_arm_and_no_resume(tmp_path):
    assert (ROOT/'scripts/task3_direct_sft_v2_infer.py').exists(), 'isolated v2 infer is missing'
    from scripts.task3_direct_sft_v2_infer import start,LOCKED,run_arm
    for arm in ('BASE','SFT','V1'):
        with pytest.raises(ValueError):run_arm([],None,LOCKED,tmp_path/arm,arm=arm)
    start(tmp_path/'v2','V2',LOCKED,[])
    with pytest.raises(FileExistsError):start(tmp_path/'v2','V2',LOCKED,[])
    assert json.loads((tmp_path/'v2/started.json').read_text())['resume_allowed'] is False


def test_v2_guard_keeps_old_validation_out_of_optimizer():
    assert (ROOT/'src/task3/direct_sft_v2_data.py').exists(), 'v2 isolation guard is missing'
    from src.task3.direct_sft_data import signature
    from src.task3.direct_sft_v2_data import require_direct_v2_isolation
    source=dict(sample_id='v',family='F',group='G',original_submission_id='O',code='int alpha(){ return 42; }')
    sig=signature(source)
    registry=dict(version='direct-sft-v2-20261021',near_threshold=.85,eligible=[sig],protected=[])
    assert require_direct_v2_isolation([source],registry,stage='before_targets')['checked']==1
    with pytest.raises(ValueError,match='validation'):
        require_direct_v2_isolation([source],registry,stage='before_optimizer',validation_sources=[source])
    assert registry['version']=='direct-sft-v2-20261021'


def test_v2_examples_bind_source_reference_and_use_new_ids():
    assert (ROOT/'scripts/task3_direct_sft_v2_prepare.py').exists(), 'isolated v2 prepare is missing'
    from scripts.task3_direct_sft_v2_prepare import build_examples,verify_example_bindings
    source=dict(sample_id='x',code='int f(){return 1;}',statement='Return one',problems=[])
    digest=hashlib.sha256(source['code'].encode()).hexdigest()
    target=dict(sample_id='x',source_sha256=digest,source_reference=[],review=dict(human_verified=False),targets=[dict(level=1,output=dict(taxonomy_error=[],feedback='Đoạn mã phù hợp yêu cầu.'))])
    examples=build_examples([source],[target])
    assert examples[0]['example_id']=='direct-v2:x@L1'
    verify_example_bindings([source],[],[target],examples,[])
    changed=copy.deepcopy(examples);changed[0]['messages'][1]['content']='unbound'
    with pytest.raises(ValueError,match='mismatch'):verify_example_bindings([source],[],[target],changed,[])
    target['source_sha256']='bad'
    with pytest.raises(ValueError,match='hash'):build_examples([source],[target])


def test_v2_prior_output_reuse_requires_identical_settings_inputs_and_complete_ids(tmp_path):
    assert (ROOT/'scripts/task3_direct_sft_v2_prepare.py').exists(), 'isolated v2 prepare is missing'
    from scripts.task3_direct_sft_v2_prepare import verify_reused_arm,digest
    from scripts.task3_direct_sft_infer import LOCKED
    rows=[dict(request_id=f'req-{i}',sample_id=f'source-{i}') for i in range(60)]
    start=dict(arm='BASE',config=LOCKED,config_sha256=digest(LOCKED),inputs_sha256=digest(rows),requests=60,resume_allowed=False)
    status=dict(complete=True,requests=60,processed=60,completed=60)
    predictions=[dict(request_id=r['request_id'],sample_id=r['sample_id'],status='completed',output=dict(taxonomy_error=[],feedback='ok')) for r in rows]
    def put(name,value):(tmp_path/name).write_text(json.dumps(value))
    for name,value in [('started.json',start),('status.json',status),('predictions.json',predictions)]:put(name,value)
    result=verify_reused_arm(tmp_path,'BASE',rows)
    assert result['predictions.json']==hashlib.sha256((tmp_path/'predictions.json').read_bytes()).hexdigest()
    start['inputs_sha256']='changed';put('started.json',start)
    with pytest.raises(ValueError,match='input|provenance'):verify_reused_arm(tmp_path,'BASE',rows)


def test_v2_start_rejects_other_arms_before_creating_output(tmp_path):
    from scripts.task3_direct_sft_v2_infer import start,LOCKED
    with pytest.raises(ValueError,match='V2'):start(tmp_path/'forbidden','BASE',LOCKED,[])
    assert not (tmp_path/'forbidden').exists()


@pytest.mark.parametrize('mutation', ['sample_id','group','source_sha256','code_identity','renamed_identity','near'])
def test_v2_gate_protects_identity_token_rename_and_near_at_both_boundaries(mutation):
    from src.task3.direct_sft_data import signature
    from src.task3.direct_sft_v2_data import require_direct_v2_isolation
    row=dict(sample_id='new',family='same-family-allowed',group='new-group',code='int f(){ int a=7; return a*9; }')
    sig=signature(row)
    old=copy.deepcopy(sig)
    for key in ('sample_id','group','source_sha256','source_text_sha256','code_identity','renamed_identity'):
        old[key]='different-'+key
    old['structural_shingles']=['different-shingle']
    if mutation=='near':old['structural_shingles']=sig['structural_shingles']
    else:old[mutation]=sig[mutation]
    registry=dict(version='direct-sft-v2-20261021',near_threshold=.85,eligible=[sig],protected=[old])
    for stage in ('before_targets','before_optimizer'):
        with pytest.raises(ValueError,match='leakage'):require_direct_v2_isolation([row],registry,stage=stage)


def test_v2_optimizer_boundaries_recheck_validation_tokens_and_actual_source_bytes(tmp_path,monkeypatch):
    from scripts import task3_direct_sft_v2_prepare as prepare
    from src.task3.direct_sft_data import signature
    from src.task3.direct_sft_v2_data import require_direct_v2_isolation
    training=runtime()
    monkeypatch.setattr(prepare,'FROZEN',tmp_path)
    old=[dict(sample_id=f'val{i}',code=f'long validation source {i}',family='val',group=f'valgroup{i}') for i in range(14)]
    (tmp_path/'validation-sources.private.json').write_text(json.dumps(old))
    records=[example()]
    train=[dict(sample_id='fixture',code='source',family='train',group='train')]
    val=[example('val0')]
    # This test uses actual token rows and a real registry guard, never a model.
    rows,_=training.encode_direct_examples(MockTokenizer(),records,8192)
    valrows,_=training.encode_direct_examples(MockTokenizer(),val,8192)
    config=json.loads((ROOT/'configs/task3/direct_sft_v2_20261021.json').read_text())
    registry=dict(version='direct-sft-v2-20261021',near_threshold=.85,eligible=[signature(train[0])],protected=[])
    frozen=({},config,records,val,train,registry)
    for boundary in ('before_optimizer_setup','first_optimizer_step'):
        result=training.verify_before_optimizer(lambda:frozen,frozen,MockTokenizer(),rows,require_direct_v2_isolation,validation_rows=valrows,boundary=boundary)
        assert result['guard']['fixed_validation_protected']==14
    drift=copy.deepcopy(valrows);drift[0]['labels'][-1]+=1
    with pytest.raises(ValueError,match='validation'):training.verify_before_optimizer(lambda:frozen,frozen,MockTokenizer(),rows,require_direct_v2_isolation,validation_rows=drift)
    frozen[4][0]['code']='changed actual source'
    with pytest.raises(ValueError,match='source'):training.verify_before_optimizer(lambda:frozen,frozen,MockTokenizer(),rows,require_direct_v2_isolation,validation_rows=valrows)


def test_v2_real_tokenizer_metadata_and_encoding_must_match_prefreeze():
    training=runtime()
    assert hasattr(training,'verify_tokenizer_freeze'), 'missing frozen tokenizer audit enforcement'
    from src.task3.inference import tokenizer_metadata
    tokenizer=MockTokenizer()
    audit=dict(tokens=10,supervised_tokens=3)
    manifest=dict(tokenizer=tokenizer_metadata(tokenizer),token_audit=dict(train=audit,validation=audit))
    training.verify_tokenizer_freeze(manifest,tokenizer,audit,audit)
    with pytest.raises(ValueError,match='tokenizer|token'):
        training.verify_tokenizer_freeze(manifest,tokenizer,dict(tokens=11,supervised_tokens=3),audit)
    manifest['tokenizer']['chat_template_sha256']='drift'
    with pytest.raises(ValueError,match='tokenizer|token'):
        training.verify_tokenizer_freeze(manifest,tokenizer,audit,audit)


def test_v2_helpers_leave_v1_runtime_bytes_and_globals_read_only(tmp_path):
    from src.task3 import direct_sft_data as old_data
    from src.task3 import direct_sft_training as old_training
    from src.task3.direct_sft_v2_data import require_direct_v2_isolation
    paths=[ROOT/'src/task3/direct_sft_data.py',ROOT/'src/task3/direct_sft_training.py',ROOT/'scripts/task3_direct_sft_prepare.py',ROOT/'scripts/task3_direct_sft_infer.py',ROOT/'configs/task3/direct_sft_v1_20261021.json']
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    version=old_data.VERSION;validator=old_training.validate_frozen_config
    source=dict(sample_id='safe',family='F',group='G',code='int answer(){return 123;}')
    sig=old_data.signature(source)
    registry=dict(version='direct-sft-v2-20261021',near_threshold=.85,eligible=[sig],protected=[])
    require_direct_v2_isolation([source],registry,stage='before_targets')
    runtime().encode_direct_examples(MockTokenizer(),[example()],8192)
    assert before=={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    assert old_data.VERSION==version=='direct-sft-v1-20261021'
    assert old_training.validate_frozen_config is validator
    assert registry['version']=='direct-sft-v2-20261021'
