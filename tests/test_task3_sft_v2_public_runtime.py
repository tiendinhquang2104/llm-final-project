import json
import pytest
from src.task3.sft_v2_public_runtime import recover_results, verify_hashes, verified_results, normalized_results, jsonl
from src.task3.sft_v1 import sha256


def test_recover_completed_not_replayed_and_unknown_stays_unknown():
    examples = [dict(sample_id=x, example_id=x, level=2) for x in ['a','b','c']]
    events = [dict(type='generation_reserved',key='a'),
              dict(type='generation_completed',key='a',result=dict(sample_id='a',status='valid')),
              dict(type='generation_reserved',key='b')]
    rows = recover_results(examples, events, {'c'})
    assert rows['a']['status'] == 'valid'
    assert rows['b']['finish_reason'] == 'interrupted_unknown'
    assert rows['b']['call_count_uncertain'] is True
    assert rows['c']['status'] == 'context_preflight_failure'


def test_frozen_bytes_must_match_and_paths_cannot_escape(tmp_path):
    p = tmp_path/'a'; p.write_text('before')
    verify_hashes(tmp_path, {'a':sha256(p)})
    p.write_text('after')
    with pytest.raises(ValueError,match='changed'): verify_hashes(tmp_path, {'a':'wrong'})
    with pytest.raises(ValueError,match='escape'): verify_hashes(tmp_path, {'../outside':'x'})


def test_pre_generation_allocation_failure_is_preserved_without_call():
    examples=[dict(sample_id='a',example_id='a',level=1)]
    event=dict(type='public_input_allocation_failed',key='a',result=dict(sample_id='a',status='generation_error',physical_call_reserved=False))
    assert recover_results(examples,[event],set())['a']['physical_call_reserved'] is False


def test_export_recovery_rejects_mutable_normalized_response(tmp_path):
    from src.task3.sft_v2_public import PublicJournal
    from src.task3.sft_v1_runtime import digest
    examples=[dict(sample_id='a',example_id='a',level=1,prompt=[dict(role='user',content='source')])]
    jsonl(tmp_path/'examples.private.jsonl',examples)
    (tmp_path/'context-preflight.json').write_text(json.dumps([dict(sample_id='a',status='evaluable')]))
    (tmp_path/'public-freeze.json').write_text('{}')
    journal=PublicJournal(tmp_path/'generation-journal.jsonl',{'a':digest(examples[0]['prompt'])})
    journal.reserve('a')
    original=dict(sample_id='a',raw='original',finish_reason='eos',status='valid')
    journal.append(dict(type='generation_completed',key='a',result=original))
    jsonl(tmp_path/'generations.jsonl',normalized_results(examples,{'a':original},tmp_path))
    assert verified_results(tmp_path)[0]['raw']=='original'
    changed=normalized_results(examples,{'a':dict(original,raw='substituted')},tmp_path)
    jsonl(tmp_path/'generations.jsonl',changed)
    with pytest.raises(ValueError,match='durable journal'): verified_results(tmp_path)
