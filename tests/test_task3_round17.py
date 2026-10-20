"""Contracts for one frozen diverse-bank experiment; no public/student fixtures."""
from dataclasses import replace
from src.synth.feedback import FEEDBACK_LEVELS
import pytest
from tests.test_task3_round14 import sample


def test_bank_rejects_family_and_source_reuse_across_levels():
    from src.task3.round17 import validate_bank
    bank=[{'id':str(i),'level':i//2+1,'code':f'int f{i}(){{return {i};}}',
           'provenance':{'family':f'family{i}'}} for i in range(8)]
    assert validate_bank(bank,[])==bank
    with pytest.raises(ValueError,match='family'):
        validate_bank([{**e,'provenance':{'family':'same'}} for e in bank],[])
    with pytest.raises(ValueError,match='source'):
        validate_bank([{**e,'code':bank[0]['code']} for e in bank],[])


def test_selection_excludes_round16_identity_and_uses_v2_labels():
    from src.task3.round17 import select_development
    r=sample(2)
    pool=[replace(r,sample_id=f'fresh-{level}-{i}',exam_id=f'family{i}',
        target_feedback_level=FEEDBACK_LEVELS[level-1], code=f'int f{level}_{i}(){{return {100*level+i};}}',
        gold_taxonomy=['Lỗi logic'],group_key=f'group-{level}-{i}') for level in range(1,5) for i in range(10)]
    forbidden=pool[0]
    rows,meta=select_development(pool,[forbidden],quota={1:2,2:2,3:2,4:2})
    assert forbidden.sample_id not in {r.sample_id for r in rows}
    assert len(rows)==8 and all(r.gold_taxonomy==['Lỗi logic'] for r in rows)
    assert meta['missing_labels']==[l for l in meta['official_labels'] if l!='Lỗi logic']
