import json
import pytest
from scripts.task3_base_pv3_control import ControlJournal, matched_population
from src.task3.prompt_crossover import call_state


def test_control_single_attempt_and_unknown_not_replayed(tmp_path):
    j = ControlJournal(tmp_path/'j.jsonl', ['s-L1'])
    j.reserve('base/s-L1')
    assert call_state(j, 'base/s-L1') == ('uncertain', None)
    with pytest.raises(ValueError): j.reserve('base/s-L1')
    with pytest.raises(ValueError): j.reserve('base/s-L2')
    j.append(dict(type='generation_completed', key='base/s-L1', result={'raw':'x'}))
    assert call_state(ControlJournal(j.path, ['s-L1']), 'base/s-L1') == ('completed', {'raw':'x'})


def test_corrupt_journal_rejected(tmp_path):
    p = tmp_path/'j.jsonl'
    p.write_text(json.dumps(dict(type='generation_completed',key='base/s-L1',result={}))+'\n')
    with pytest.raises(ValueError): ControlJournal(p, ['s-L1'])


def test_matching_uses_binding_not_order_and_excludes_l4():
    e = [dict(example_id='s-L2',sample_id='s',level=2), dict(example_id='s-L1',sample_id='s',level=1)]
    r = [dict(example_id='s-L1',sample_id='s',level=1), dict(example_id='s-L2',sample_id='s',level=2)]
    assert matched_population(e,r)
    r[0]['sample_id']='wrong'
    with pytest.raises(ValueError): matched_population(e,r)
    with pytest.raises(ValueError): matched_population([dict(example_id='s-L4',sample_id='s',level=4)], [dict(example_id='s-L4',sample_id='s',level=4)])
