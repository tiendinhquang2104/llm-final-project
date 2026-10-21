"""Artificial fixtures for the new direct protocol; no private data reads."""
import json
import pytest
from scripts.task3_direct_sft_prepare import build_examples, source_split, native_record
from src.task3.round15 import build_messages

def source(i,code=None):
 return dict(sample_id=f'FIX-{i}',family='F',group=f'G{i}',code=code or f'int main(){{return {i};}}',statement='In kết quả theo đề.',problems=[],grading_policy={},origin='synthetic-train')

def reviewed(s):
 from hashlib import sha256
 return dict(sample_id=s['sample_id'],source_sha256=sha256(s['code'].encode()).hexdigest(),source_reference=['Lỗi logic'],defect_status='defect',review=dict(human_verified=False),targets=[dict(level=2,output=dict(taxonomy_error=['Lỗi logic'],feedback='Phép tính cuối không khớp yêu cầu.'))])

def test_native_prompt_exact_no_diagnosis_fields():
 s=source(1);r=reviewed(s);examples=build_examples([s],[r])
 assert len(examples)==1 and examples[0]['kind']=='direct' and examples[0]['loss_weight']==1
 assert examples[0]['messages']==build_messages(native_record(s,2),())
 assert set(json.loads(examples[0]['completion']))=={'taxonomy_error','feedback'}
 assert 'diagnosis' not in json.loads(examples[0]['messages'][-1]['content'])

@pytest.mark.parametrize('change',[dict(source_sha256='stale'),dict(source_reference=None),dict(targets=[dict(level=2,output=dict(taxonomy_error=['invented'],feedback='x'))])])
def test_reject_binding_or_unresolved(change):
 s=source(1);r=reviewed(s);r.update(change)
 with pytest.raises(ValueError):build_examples([s],[r])

def test_split_exact_group_cluster_and_determinism():
 rows=[source(i,code=f'int main(){{int x={i};return x+{i};}}') for i in range(10)]
 rows[1]['group']=rows[0]['group']
 # injected similarity prevents accidental template identity in this fixture
 train,val=source_split(rows,similarity=lambda a,b:1.0 if a['group']==b['group'] else 0.)
 assert train and val and not {r['group'] for r in train}&{r['group'] for r in val}
 assert source_split(rows,similarity=lambda a,b:1.0 if a['group']==b['group'] else 0.)==(train,val)


def test_no_false_split_of_single_near_component():
 with pytest.raises(ValueError):source_split([source(1),source(2)],similarity=lambda a,b:1.)

def test_critical_runtime_hash_drift_rejected(tmp_path):
 from hashlib import sha256
 from scripts.task3_direct_sft_prepare import verify_hashes
 p=tmp_path/'identity.py';p.write_text('fixed gate')
 expected={'identity.py':sha256(p.read_bytes()).hexdigest()}
 verify_hashes(expected,root=tmp_path)
 p.write_text('relaxed gate')
 with pytest.raises(ValueError):verify_hashes(expected,root=tmp_path)

def test_frozen_source_context_and_validation_binding():
 from scripts.task3_direct_sft_prepare import verify_example_bindings
 train=[source(1)];val=[source(2)];reviews=[reviewed(s) for s in train+val]
 ex=build_examples(train,[reviews[0]]);vx=build_examples(val,[reviews[1]])
 verify_example_bindings(train,val,reviews,ex,vx)
 vx[0]['messages'][-1]['content']='{"code":"other source"}'
 with pytest.raises(ValueError):verify_example_bindings(train,val,reviews,ex,vx)

def test_raw_source_hash_and_decoded_training_hash_are_distinct_bindings():
 from hashlib import sha256
 s=source(1);s['source_sha256']=sha256(b'\xef\xbb\xbf'+s['code'].encode()).hexdigest()
 s['source_text_sha256']=sha256(s['code'].encode()).hexdigest()
 r=reviewed(s);r['source_sha256']=s['source_sha256']
 ex=build_examples([s],[r])
 assert ex[0]['source_sha256']==s['source_text_sha256']
 assert ex[0]['source_sha256']!=r['source_sha256']
