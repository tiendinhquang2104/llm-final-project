"""Integrity regressions: no replay, no foreign calls, no private input or stale hashes."""
import json
import pytest
from src.task3.prompt_crossover import (CrossoverJournal, call_state, prompt_examples,
                                        validate_population, verify_hashes)
from src.task3.sft_v1 import sha256


def test_budget_rejects_reused_cell_and_foreign_target(tmp_path):
    journal = CrossoverJournal(tmp_path/'journal.jsonl', ['v3-old'], ['S-L1'])
    for key in ('v2-v3/S-L1', 'v3-old/foreign', 'v3-old/S-L1/extra'):
        with pytest.raises(ValueError): journal.reserve(key, 99999)
    assert not journal.reserved()
    journal.reserve('v3-old/S-L1', 99999)
    with pytest.raises(ValueError): journal.reserve('v3-old/S-L1', 99999)


def test_exact_two_cell_ceiling_ignores_legacy_budget(tmp_path):
    ids = [f'S{i}-L1' for i in range(80)]
    journal = CrossoverJournal(tmp_path/'journal.jsonl', ['v2-old','v3-old'], ids)
    for cell in ('v2-old','v3-old'):
        for eid in ids: journal.reserve(cell+'/'+eid, 402)
    assert len(journal.reserved()) == 160
    with pytest.raises(ValueError): journal.reserve('v2-old/extra', 99999)
    with pytest.raises(ValueError): CrossoverJournal(tmp_path/'bad.jsonl', ['unknown'], ids)


def test_uncertain_reservation_cannot_be_treated_as_fresh(tmp_path):
    j=CrossoverJournal(tmp_path/'j.jsonl',['v3-old'],['S-L1'])
    assert call_state(j,'v3-old/S-L1') == ('fresh',None)
    j.reserve('v3-old/S-L1',402)
    assert call_state(j,'v3-old/S-L1') == ('uncertain',None)
    result={'raw':'broken raw','status':'malformed_json','parsed':None}
    j.append({'type':'generation_completed','key':'v3-old/S-L1','result':result})
    assert call_state(j,'v3-old/S-L1') == ('completed',result)
    j.append({'type':'generation_completed','key':'v3-old/S-L1','result':result})
    with pytest.raises(ValueError,match='duplicate'): call_state(j,'v3-old/S-L1')


def fixture_record():
    return dict(sample_id='S-L1',source_id='S',input=dict(statement='Read n and print n.',
        exam_type='single_problem',language='cpp11',code='int main(){}\n',compile_log='',target_feedback_level=1),
        output={'taxonomy_error':[],'feedback':'PRIVATE GOLD'},private_findings='PRIVATE WITNESS')


def test_generation_examples_exclude_gold_and_private_fields(tmp_path):
    (tmp_path/'SYSTEM_PROMPT.txt').write_text('Exact old system.\n')
    row=fixture_record();examples=prompt_examples([row],tmp_path,['Lỗi logic'])
    assert len(examples)==1 and examples[0]['example_id']=='S-L1'
    assert set(examples[0])=={'example_id','sample_id','level','prompt'}
    text=json.dumps(examples[0],ensure_ascii=False)
    assert 'PRIVATE GOLD' not in text and 'PRIVATE WITNESS' not in text
    assert examples[0]['prompt'][0]['content']=='Exact old system.\nAllowed taxonomy labels: ["Lỗi logic"]'
    assert examples[0]['prompt'][1]['content'].count('C++ source:')==1
    row['input']['private_findings']='leak'
    with pytest.raises(ValueError,match='whitelist'): prompt_examples([row],tmp_path,['Lỗi logic'])


def test_full_requested_id_source_level_coverage(tmp_path):
    ex=[{'example_id':'S-L1','sample_id':'S','level':1},{'example_id':'S-L2','sample_id':'S','level':2}]
    assert validate_population(ex,list(reversed(ex)))
    for rows in (ex[:1],ex+[ex[0]],[ex[0],dict(ex[1],level=3)],[ex[0],dict(ex[1],sample_id='other')]):
        with pytest.raises(ValueError): validate_population(rows,ex)


def test_hash_guard_detects_late_input_mutation_and_escape(tmp_path):
    p=tmp_path/'prompt.json';p.write_text('frozen input')
    entries={'prompt.json':sha256(p)}
    assert verify_hashes(tmp_path,entries)
    p.write_text('changed after freeze')
    with pytest.raises(ValueError,match='changed'): verify_hashes(tmp_path,entries)
    with pytest.raises(ValueError,match='path'): verify_hashes(tmp_path,{'../outside':'bad'})


def test_resume_rejects_changed_durable_raw_and_unbound_unknown(tmp_path):
    from src.task3 import prompt_crossover as pc
    ex=[{'example_id':'S-L1','sample_id':'S','level':1}]
    j=CrossoverJournal(tmp_path/'resume.jsonl',['v3-old'],['S-L1'])
    result=dict(ex[0],raw='original',parsed=None,status='malformed_json')
    j.reserve('v3-old/S-L1',402)
    j.append(dict(type='generation_completed',key='v3-old/S-L1',result=result))
    assert pc.validate_durable_rows([dict(result,utc='export time')],ex,j,'v3-old')
    with pytest.raises(ValueError,match='durable'): pc.validate_durable_rows([dict(result,raw='changed')],ex,j,'v3-old')
    with pytest.raises(ValueError): pc.validate_durable_rows([dict(result,sample_id='other')],ex,j,'v3-old')
    unknown=dict(ex[0],raw='',parsed=None,status='missing',finish_reason='interrupted_unknown',call_count_uncertain=True)
    fresh=CrossoverJournal(tmp_path/'fresh.jsonl',['v3-old'],['S-L1'])
    with pytest.raises(ValueError):pc.validate_durable_rows([unknown],ex,fresh,'v3-old')
    fresh.reserve('v3-old/S-L1',402)
    assert pc.validate_durable_rows([unknown],ex,fresh,'v3-old')


def test_changed_external_tokenizer_blocks_run_before_any_generation(tmp_path):
    from src.task3 import prompt_crossover as pc
    snapshot=tmp_path/'snapshot';snapshot.mkdir();tokenizer=snapshot/'tokenizer.json';tokenizer.write_text('frozen')
    out=tmp_path/'out';out.mkdir()
    manifest=dict(code_files={},historical_bindings={},input_files={},cells={},runtime=dict(
        loader_manifest=dict(config={'tokenizer_local':str(snapshot)},model_files={},versions={}),
        common_profile={'tokenizer':{'files':{'tokenizer.json':sha256(tokenizer)}}},hardware={}))
    (out/'manifest.json').write_text(json.dumps(manifest));(out/'manifest.sha256.json').write_text(json.dumps({'sha256':sha256(out/'manifest.json')}))
    tokenizer.write_text('same length different tokenizer')
    with pytest.raises(ValueError,match='tokenizer'):pc.verify_run(out)


def test_actual_runtime_profile_must_match_frozen_inference_contract():
    from copy import deepcopy
    from src.task3 import prompt_crossover as pc
    profile=dict(active_adapters=['default'],adapter_names=['default'],all_modules_eval=True,
        parameter_dtypes={'torch.uint8':196,'torch.float32':424},lora_dtypes={'torch.float32':392},
        attention='sdpa',model_config_use_cache=False,generation_use_cache=True,
        compute_type_flags={'True':196},
        quantization=dict(linear4bit_modules=196,compute_dtypes={'torch.bfloat16':196},storage_dtypes={'torch.uint8':196},quant_types={'nf4':196},nested=True),
        generation_config={'repetition_penalty':1.1,'cache_implementation':None})
    assert pc.validate_runtime_profile(profile)
    for key,value in [('attention','eager'),('all_modules_eval',False),('active_adapters',['default','other']),('lora_dtypes',{'torch.bfloat16':392}),('compute_type_flags',{'False':196})]:
        changed=deepcopy(profile);changed[key]=value
        with pytest.raises(ValueError):pc.validate_runtime_profile(changed)
    changed=deepcopy(profile);changed['quantization']['nested']=False
    with pytest.raises(ValueError):pc.validate_runtime_profile(changed)


def test_huggingface_snapshot_accepts_same_model_blob_but_rejects_other_links(tmp_path):
    from src.task3 import prompt_crossover as pc
    snapshot=tmp_path/'model/snapshots/revision';snapshot.mkdir(parents=True)
    blobs=tmp_path/'model/blobs';blobs.mkdir();blob=blobs/'pinned';blob.write_text('tokenizer')
    link=snapshot/'tokenizer.json';link.symlink_to(blob)
    assert pc.verify_snapshot_hashes(snapshot,{'tokenizer.json':sha256(blob)})
    outside=tmp_path/'outside';outside.write_text('tokenizer');link.unlink();link.symlink_to(outside)
    with pytest.raises(ValueError,match='path'):pc.verify_snapshot_hashes(snapshot,{'tokenizer.json':sha256(outside)})
