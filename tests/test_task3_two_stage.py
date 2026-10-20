import json
from dataclasses import replace
from types import SimpleNamespace
import pytest
from src.task3.schema import Task3Record
from src.synth.taxonomy import LABEL_SPACE
from src.task3.two_stage import diagnosis_messages,feedback_messages,parse_diagnosis,TwoStageRunner,StageFailure


def record():
 return Task3Record(source='synthetic',sample_id='TEST-ONLY',original_submission_id='TEST-ONLY',exam_id='TEST-FAMILY',exam_type='single_problem',statement='In ra 0.',grading_policy={},code_path='test.cpp',code='int main(){return 1;}',target_feedback_level='Level 1 - Gợi ý nhẹ',gold_taxonomy=['Lỗi style'],gold_feedback='SECRET-TEACHER',provenance={'_task3_compile_check':{'status':'compiled','diagnostic':''}})
def diagnostic(labels=None,status='defect'):
 labels=labels or ['Lỗi logic']
 return {'status':status,'taxonomy_error':labels,'findings':[{'label':l,'quote':'return 1;','location':'main','evidence':'Trả1 thay0.'} for l in labels],'basis':'Đối chiếu đề và source.'}
class Backend:
 def __init__(self,answers):self.answers=iter(answers);self.calls=[]
 def generate(self,m,c):self.calls.append(m);return SimpleNamespace(text=next(self.answers),output_tokens=1,latency_s=0)
def dumps(x):return json.dumps(x,ensure_ascii=False)
def test_diagnosis_identical_all_levels_and_no_gold():
 r=record();messages=diagnosis_messages(r)
 for level in range(1,5):
  from src.synth.feedback import FEEDBACK_LEVELS
  assert diagnosis_messages(replace(r,target_feedback_level=FEEDBACK_LEVELS[level-1]))==messages
 text=dumps(messages)
 assert 'requested_level' not in text and 'SECRET' not in text and 'Level' not in text
 assert 'Lỗi style' in text # allowed space, not a supplied gold list
 assert set(json.loads(messages[-1]['content']))=={'task','statement','problems','grading_policy','code','compiler'}
@pytest.mark.parametrize('label',LABEL_SPACE)
def test_all_ten_labels(label):
 assert parse_diagnosis(dumps(diagnostic([label])),record())['taxonomy_error']==[label]
def test_exact_official_space():assert len(LABEL_SPACE)==10
@pytest.mark.parametrize('level',[1,2,3])
def test_feedback_rules_and_taxonomy_copied(tmp_path,level):
 backend=Backend([dumps(diagnostic()),dumps({'feedback':'Bài còn vấn đề.'})]);runner=TwoStageRunner(backend,{},tmp_path/'journal.jsonl')
 diag=runner.diagnose(record());out=runner.feedback(record(),diag,level)
 assert out['taxonomy_error']==['Lỗi logic']
 assert json.loads(backend.calls[-1][-1]['content'])['requested_level']==level
 assert 'SECRET' not in dumps(backend.calls)
 assert 'Level '+str(level) in feedback_messages(record(),diag,level)[0]['content']
def test_shared_diagnosis_one_call_for_four_levels(tmp_path):
 backend=Backend([dumps(diagnostic())]+[dumps({'feedback':'Có vấn đề.'})]*4);runner=TwoStageRunner(backend,{},tmp_path/'journal.jsonl')
 for level in range(1,5):runner.feedback(record(),runner.diagnose(record()),level)
 assert len(backend.calls)==5
@pytest.mark.parametrize('raw',['bad json',dumps({'taxonomy_error':[]}),dumps(diagnostic(['unknown'])),dumps({**diagnostic(),'findings':[]}),dumps({**diagnostic(),'status':'clean'})])
def test_schema_failure_never_clean(tmp_path,raw):
 runner=TwoStageRunner(Backend([raw]),{},tmp_path/'journal.jsonl')
 with pytest.raises(StageFailure):runner.diagnose(record())
 rows=[json.loads(x) for x in (tmp_path/'journal.jsonl').read_text().splitlines()]
 assert rows[0]['raw_text']==raw and rows[-1]['status']=='error'
def test_uncertain_is_explicit_not_clean(tmp_path):
 d={'status':'uncertain','taxonomy_error':[],'findings':[],'basis':'Chưa đủ bằng chứng.'}
 runner=TwoStageRunner(Backend([dumps(d)]),{},tmp_path/'journal.jsonl')
 with pytest.raises(StageFailure,match='uncertain'):runner.diagnose(record())
def test_clean_basis_and_compiler_evidence(tmp_path):
 r=record();d={'status':'clean','taxonomy_error':[],'findings':[],'basis':'Miền kiểm tra hữu hạn; đối chiếu đầu ra.'}
 assert parse_diagnosis(dumps(d),r)==d
 r=replace(r,provenance={'_task3_compile_check':{'status':'compile_error','diagnostic':'error: expected semicolon'}})
 d=diagnostic(['Lỗi biên dịch']);d['findings'][0]['quote']='error: expected semicolon'
 assert parse_diagnosis(dumps(d),r)['taxonomy_error']==['Lỗi biên dịch']
def test_feedback_cannot_overwrite_taxonomy(tmp_path):
 runner=TwoStageRunner(Backend([dumps(diagnostic()),dumps({'feedback':'ok','taxonomy_error':[]})]),{},tmp_path/'journal.jsonl')
 d=runner.diagnose(record())
 with pytest.raises(StageFailure):runner.feedback(record(),d,2)
 assert d['taxonomy_error']==['Lỗi logic']
def test_cache_changes_with_source_or_evidence(tmp_path):
 backend=Backend([dumps(diagnostic()),dumps(diagnostic())]);runner=TwoStageRunner(backend,{},tmp_path/'journal.jsonl');r=record();runner.diagnose(r)
 runner.diagnose(replace(r,statement='In ra1.'))
 assert len(backend.calls)==2

def test_prior_evaluation_id_or_renamed_source_is_excluded():
 from src.task3.two_stage_data import historical_overlap
 train=[{'sample_id':'train','group':'g1','renamed_identity':'same'}]
 historical=[{'sample_id':'eval-renamed','group_key':'g2','renamed_code_hash':'same'}]
 assert historical_overlap(train,historical)[0]['matched_on']==['renamed_identity']
 historical=[{'sample_id':'train','group_key':'g2','renamed_code_hash':'different'}]
 assert historical_overlap(train,historical)[0]['matched_on']==['sample_id']

def test_distinct_historical_source_is_allowed():
 from src.task3.two_stage_data import historical_overlap
 assert historical_overlap([{'sample_id':'a','group':'1','renamed_identity':'x'}],[{'sample_id':'b','group_key':'2','renamed_code_hash':'y'}])==[]

def test_abstention_not_awarded_clean_exact_set():
 from src.task3.two_stage_eval import taxonomy_metrics
 m=taxonomy_metrics({'clean':[], 'bug':['Lỗi logic']},{'bug':None})
 assert m['exact_set_count']==0 and m['unresolved']==2
 assert m['per_label']['Lỗi logic']['fn']==1
 assert len(m['per_label'])==10
