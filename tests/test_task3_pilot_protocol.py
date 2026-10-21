import json
from copy import deepcopy
import pytest
from src.task3 import pilot_protocol as p


@pytest.fixture
def task():
    return dict(statement='Compute.',problems=[],grading_policy=None,student_code='int f(){return 0;}',
                compiler_evidence={'status':'not_run','diagnostic':''},allowed_labels=['Lỗi logic'])


@pytest.fixture
def diagnosis():
    return dict(status='defective',taxonomy_error=['Lỗi logic'],findings=[dict(label='Lỗi logic',
        quote='return 0;',location='f',cause_vi='Giá trị sai.',evidence=dict(kind='static_reasoning',
        input='fixture',expected='1',actual_derived='0',reasoning='Literal return.'))],basis='Static fixture.',domain='small ints')


def test_train_eval_tasks_align_without_gold(task):
    train=dict(exam={k:task[k] for k in ('statement','problems','grading_policy')},code=task['student_code'],
               compiler_evidence=task['compiler_evidence'],domain='small ints')
    a=p.normalize_task(train);b=p.normalize_task(task)
    for k in ('statement','problems','grading_policy','code','compiler'):assert a[k]==b[k]
    assert 'reference' not in json.dumps(b)
    assert 'requested_level' not in json.dumps(p.diagnosis_messages(task))
    with pytest.raises(ValueError):p.normalize_task(dict(task,gold=['Lỗi logic']))


def test_feedback_taxonomy_is_detached_and_fixed(task,diagnosis):
    output=p.parse_feedback('{"feedback":"Cần kiểm tra."}',diagnosis)
    output['taxonomy_error'].clear();assert diagnosis['taxonomy_error']==['Lỗi logic']
    for level in (1,2,3,4):
        msg=p.feedback_messages(task,diagnosis,level)
        assert json.loads(msg[-1]['content'])['requested_level']==level


def test_diagnosis_exact_source_binding(task,diagnosis):
    assert p.parse_diagnosis(json.dumps(diagnosis),task)==diagnosis
    for change in ('quote','status','labels','fields'):
        d=deepcopy(diagnosis)
        if change=='quote':d['findings'][0]['quote']='absent'
        if change=='status':d['status']='clean'
        if change=='labels':d['taxonomy_error']=[]
        if change=='fields':d['extra']=1
        with pytest.raises(ValueError):p.parse_diagnosis(json.dumps(d),task)


def test_preserved_optional_evidence_provenance(task,diagnosis):
    diagnosis['findings'][0]['evidence']['verification_status']='author_static; not executed'
    assert p.parse_diagnosis(json.dumps(diagnosis),task)==diagnosis
    diagnosis['findings'][0]['evidence']['unexpected']='bad'
    with pytest.raises(ValueError):p.parse_diagnosis(json.dumps(diagnosis),task)


def test_source_split_keeps_four_examples_together():
    sources=[dict(sample_id=f'SUP-{i}',family='TRAIN',clean=i%2==0) for i in range(10)]
    tr,va=p.source_split(sources,seed=42,validation_fraction=.2)
    assert len(tr)==8 and len(va)==2 and set(tr).isdisjoint(va)
    assert (tr,va)==p.source_split(list(reversed(sources)),seed=42,validation_fraction=.2)
    ex=[dict(sample_id=r['sample_id'],example_id=r['sample_id']+'-'+str(i)) for r in sources for i in range(4)]
    a,b=p.split_examples(ex,tr,va)
    assert len(a)==32 and len(b)==8
    with pytest.raises(ValueError):p.split_examples(ex,tr,va+tr[:1])
