from copy import deepcopy
import pytest
from scripts import task3_pilot_prepare as p


def test_training_view_binds_actual_code_and_preserves_completion():
    r=dict(sample_id='S',code='int f(){return 1;}',parent_exam={})
    task=dict(exam=dict(statement='Task',problems=[],grading_policy=None),code=r['code'],
              domain='small ints',compiler_evidence={'available':False,'diagnostic':None})
    diagnosis=dict(status='clean',taxonomy_error=[],findings=[],basis='Invariant.',domain='small ints')
    draft=dict(sample_id='S',example_id='S-D',kind='diagnostic',input=task,output=diagnosis)
    out=p.training_view([draft],[r])
    assert out[0]['loss_weight']==2
    import json
    assert json.loads(out[0]['completion'])==diagnosis
    broken=deepcopy(draft);broken['input']['code']='changed'
    with pytest.raises(ValueError,match='code'):p.training_view([broken],[r])


def test_review_selection_fixed_all_families_and_levels():
    selection=[dict(sample_id=f'SYN-F{i//4}-{i}',family=f'F{i//4}',level=i%4+1) for i in range(72)]
    requests=[dict(sample_id=r['sample_id'],request_id=r['sample_id']+'-p',kind='primary',level=r['level']) for r in selection]
    a=p.review_selection(selection,requests,24)
    assert len(a)==24
    rows=[r for r in selection if r['sample_id'] in {x['sample_id'] for x in a}]
    assert len({r['family'] for r in rows})==18
    assert {r['level'] for r in rows}=={1,2,3,4}
    assert a==p.review_selection(list(reversed(selection)),requests,24)
