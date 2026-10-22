import pytest
from src.task3.round24_audit import validate_defect_links,audit_model_payload
from src.task3.round15 import query_payload
from src.task3.schema import Task3Record


def test_credited_defect_needs_its_own_source_and_causal_proof():
 ref={'defects':[{'defect_id':'a','source_quote':'int a;'},{'defect_id':'b','source_quote':'int b;'}]}
 r={'claims':[{'defect_ids':['a'],'defect_evidence':[{'defect_id':'a','source_quote':'int b;','causal_link':'explanation'}]}]}
 with pytest.raises(ValueError):validate_defect_links(r,ref,'int a;int b;')
 r['claims'][0]['defect_evidence'][0]['source_quote']='int a;';validate_defect_links(r,ref,'int a;int b;')
 r['claims'][0]['defect_evidence'][0]['causal_link']=''
 with pytest.raises(ValueError):validate_defect_links(r,ref,'int a;int b;')

def test_uncounted_or_duplicate_links_are_not_accepted():
 ref={'defects':[{'defect_id':'a','source_quote':'int a;'}]}
 with pytest.raises(ValueError):validate_defect_links({'claims':[{'defect_ids':['a'],'defect_evidence':[]}]},ref,'int a;')

def test_payload_binds_statement_and_problem_and_policy_not_only_source():
 r=Task3Record(source='real',sample_id='x',original_submission_id='x',exam_id='E',exam_type='single_problem',statement='Original task',grading_policy='original policy',code_path='source.cpp',code='int main(){}',target_feedback_level='Level 2 - Chẩn đoán')
 payload=query_payload(r);audit_model_payload(payload,r,2)
 for key in ['statement','problems','grading_policy','compiler']:
  edited=dict(payload);edited[key]='changed'
  with pytest.raises(ValueError):audit_model_payload(edited,r,2)

def test_present_output_without_native_trace_is_rejected():
 from src.task3.round24_audit import audit_completion
 with pytest.raises(ValueError):audit_completion({'x'},{'x':{}},{},{})
 audit_completion({'x'},{},{},{'x':{'reason':'failed'}})
