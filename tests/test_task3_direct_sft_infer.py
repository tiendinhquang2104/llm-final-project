"""Artificial only: fake generation through unchanged direct R15 controller."""
import json
from types import SimpleNamespace
import pytest
from scripts.task3_direct_sft_infer import run_arm,LOCKED,validate_rows
from src.task3.inference import MockTokenizer


def rows():
 return [dict(request_id=f'fixture-{i}@L2',sample_id=f'fixture-{i}',kind='primary',requested_level=2,task=dict(statement='Trả giá trị nguyên theo đề.',problems=[],grading_policy={},student_code=f'int f(){{return {i};}}',compiler_evidence={'status':'unavailable'},allowed_labels=[])) for i in range(2)]

class Backend:
 tokenizer=MockTokenizer()
 def generate(self,messages,config):
  return SimpleNamespace(text=json.dumps(dict(taxonomy_error=['Lỗi logic'],feedback='Biểu thức trả về trong hàm chưa khớp phép tính yêu cầu.')),output_tokens=20,latency_s=.01,finish_reason='eos',eos_reached=True)

def test_same_direct_controller_base_and_sft(tmp_path):
 a=run_arm(rows(),Backend(),dict(LOCKED),tmp_path/'base',arm='BASE')
 b=run_arm(rows(),Backend(),dict(LOCKED),tmp_path/'sft',arm='SFT')
 assert len(a['predictions'])==2 and a['predictions']==b['predictions']
 captures=[json.loads(l) for l in (tmp_path/'sft/generations.jsonl').read_text().splitlines()]
 assert all(r['stage']=='direct' and r['request_id'] for r in captures)
 assert all('diagnosis' not in json.loads(r['prompt_messages'][1]['content']) for r in captures)
 with pytest.raises(FileExistsError):run_arm(rows(),Backend(),dict(LOCKED),tmp_path/'base',arm='BASE')

def test_reject_unsafe_or_duplicate_rows():
 r=rows();r[0]['task']['reference']='forbidden'
 with pytest.raises(ValueError):validate_rows(r)
 r=rows();r.append(r[0])
 with pytest.raises(ValueError):validate_rows(r)
