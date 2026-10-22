import pytest
from src.task3.schema import Task3Record
from src.task3 import round15,round15_runner
from src.task3.round24_prompt import messages,adapter,fitted


def record(level=2):
 return Task3Record(source='synthetic',sample_id='S',original_submission_id='S',exam_id='E',exam_type='single_problem',statement='Print n.',grading_policy='One problem',code_path='source.cpp',code='int main(){}',target_feedback_level={1:'Level 1 - Gợi ý nhẹ',2:'Level 2 - Chẩn đoán',3:'Level 3 - Gợi ý sửa'}[level],gold_taxonomy=['Lỗi logic'],gold_feedback='SECRET_GOLD')


def test_control_is_exact_native_for_all_requested_levels():
 for level in [1,2,3]:
  r=record(level)
  assert messages(r,[],arm='R15')==round15.build_messages(r,[])
  assert messages(r,[],arm='R15',retry='same')==round15.build_messages(r,[],retry='same')


def test_candidate_changes_only_system_no_extra_schema_or_annotated_input():
 for level in [1,2,3]:
  r=record(level);a=messages(r,[],arm='R15');b=messages(r,[],arm='C')
  assert a[1:]==b[1:]and b[0]['content'].startswith(a[0]['content'])
  assert 'SECRET_GOLD'not in str(b)and len(b)==2
  assert 'requested_level' in b[1]['content']


def test_adapter_restores_controller_on_exception_and_never_changes_guard():
 old=round15_runner.fitted_messages;guard=round15_runner.disclosure_violations
 with pytest.raises(RuntimeError):
  with adapter('C'):
   assert round15_runner.fitted_messages is not old and round15_runner.disclosure_violations is guard
   raise RuntimeError('probe')
 assert round15_runner.fitted_messages is old and round15_runner.disclosure_violations is guard


def test_fitted_refuses_truncation_or_fewshots():
 class Tokenizer:
  def apply_chat_template(self,*args,**kwargs):return list(range(100))
 with pytest.raises(ValueError):fitted(record(),[],Tokenizer(),{'max_new_tokens':10,'context_limit':109},arm='C')
 with pytest.raises(ValueError):fitted(record(),[{}],Tokenizer(),{'max_new_tokens':10,'context_limit':1000},arm='C')
