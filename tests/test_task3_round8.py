"""Artificial train-only behavior contracts, not semantic scores on evaluation data."""
import json

import pytest

from src.task3.compliance import check, fallback
from src.task3.evaluator import evaluate
from src.task3.inference import Generation, MockBackend
from src.task3.pipeline import infer
from src.task3.prompts import build_messages, retry_hint
from src.task3.quality_review import quality_review_flags
from tests.test_task3_dataset import record

L1 = 'Level 1 - Gợi ý nhẹ'


@pytest.mark.parametrize('text', [
    'Em thử loại bỏ phần hard-code nhé.',
    'Bạn lưu sai dữ liệu đầu vào.',
    'Hãy chú ý đến việc in kết quả.',
    'Phần xử lý dữ liệu còn thiếu.',
    'Hàm tinhTong chưa được hoàn thiện.',
    'Dùng thuật toán sắp xếp để giải bài này.',
    'Thay phép chia bằng phép lấy dư.',
    'Em hãy bổ sung bước đọc dữ liệu.',
    'Không sao chép mã của bạn khác.',
    'Chương trình chưa xử lý phần tử cuối.',
    'Em đã nộp phiên bản bị comment hết cả bài.',
    'Hãy tiếp tục hoàn thiện các hàm còn lại.',
])
def test_guard3_blocks_specific_level1_details_and_accusation(text):
    assert not check(text, 1, version=3).ok


@pytest.mark.parametrize('text', [
    'Em cứ bình tĩnh, kiểm tra lại bài theo yêu cầu chung rồi tiếp tục nhé.',
    'Chúc em học tốt và tự tin hơn.',
    'Hãy giữ tinh thần học hỏi và kiên trì luyện tập nhé.',
    'Việc kiểm tra lại bài là một thói quen học tập hữu ích.',
])
def test_guard3_does_not_reject_general_encouragement_or_checking(text):
    assert check(text, 1, version=3).ok


@pytest.mark.parametrize('text', ['Đúng rồi!', 'Bài làm hoàn toàn chính xác.', 'Em đã hoàn thành đúng toàn bộ yêu cầu.'])
def test_praise_is_a_candidate_without_inventing_correctness_from_empty_labels(text):
    r = record(target_feedback_level=L1, gold_taxonomy=[], compile_log=None, test_report=None)
    result = quality_review_flags(r, text, version=3)
    assert 'LEVEL1_PRAISE_EVIDENCE_REVIEW_CANDIDATE' in result['flags']
    assert result['semantic_quality'] == 'NOT_MEASURED'
    assert result['praise_evidence_status'] == 'NOT_VERIFIED'
    assert check(text, 1, version=3).ok  # A candidate is not a proved semantic failure.


def test_harmless_good_wishes_are_not_program_correctness_praise():
    result = quality_review_flags(record(target_feedback_level=L1), 'Chúc em học tốt và luôn giữ tinh thần học hỏi.', version=3)
    assert 'LEVEL1_PRAISE_EVIDENCE_REVIEW_CANDIDATE' not in result['flags']


def train_demo(level=L1):
    return record('ARTIFICIAL-TRAIN', source='real', split='real-train', code='// ARTIFICIAL TRAIN SOURCE\n', target_feedback_level=level, gold_feedback='Tốt, em đã bỏ sót phần đọc dữ liệu.', gold_taxonomy=['Lỗi logic'])


def test_prompt4_preserves_train_input_but_does_not_teach_disclosure_or_false_praise():
    r = record('ARTIFICIAL-TARGET', target_feedback_level=L1, code='int main(){return 0;}')
    demo = train_demo()
    messages = build_messages(r, r.gold_taxonomy, [demo], prompt_policy_version=4)
    assistants = [m['content'] for m in messages if m['role']=='assistant']
    assert len(assistants)==1
    assert assistants[0] != demo.gold_feedback
    assert demo.gold_feedback == 'Tốt, em đã bỏ sót phần đọc dữ liệu.'
    assert check(assistants[0],1,version=3).ok
    assert 'LEVEL1_PRAISE_EVIDENCE_REVIEW_CANDIDATE' not in quality_review_flags(demo, assistants[0],version=3)['flags']
    assert demo.code in json.loads(messages[1]['content'].split('UNTRUSTED_SUBMISSION_JSON\n')[1].split('\nEND_SUBMISSION_JSON')[0])['student_code']
    old = build_messages(r,r.gold_taxonomy,[demo],prompt_policy_version=3)
    assert [m['content'] for m in old if m['role']=='assistant']==[demo.gold_feedback]


def test_prompt4_never_exposes_diagnostic_plan_to_level1():
    r=record(target_feedback_level=L1)
    messages=build_messages(r,r.gold_taxonomy,prompt_policy_version=4,additional_messages=[{'role':'user','content':'PRIVATE_DIAGNOSIS_PLAN_SENTINEL'}])
    assert 'PRIVATE_DIAGNOSIS_PLAN_SENTINEL' not in json.dumps(messages)


@pytest.mark.parametrize('level',['Level 2 - Chẩn đoán','Level 3 - Gợi ý sửa','Level 4 - Lời giải mẫu'])
def test_level2_to4_prompts_guards_retries_and_candidates_delegate_to_r7(level):
    r=record(target_feedback_level=level)
    demo=train_demo(level)
    assert build_messages(r,r.gold_taxonomy,[demo],prompt_policy_version=4)==build_messages(r,r.gold_taxonomy,[demo],prompt_policy_version=3)
    text='Biến chưa được khai báo. Hãy khai báo biến trước khi dùng.'
    assert check(text,level,version=3)==check(text,level,version=2)
    assert retry_hint(['repair_guidance'],int(level[6]),4)==retry_hint(['repair_guidance'],int(level[6]),3)
    assert quality_review_flags(r,text,version=3)==quality_review_flags(r,text,version=2)


class ScriptedBackend(MockBackend):
    def __init__(self,texts):
        self.texts=iter(texts)

    def generate(self,messages,config):
        return Generation(next(self.texts),20,.1,finish_reason='eos',eos_reached=True)


def cfg():
    return {'context_limit':12000,'prompt_policy_version':4,'guard_policy_version':3,'retry_policy_version':4,'completion_policy_version':1,'adequacy_retry_policy_version':1,'max_retries':2,'few_shot_k':1,'few_shot_source_allowlist':['real'],'few_shot_same_level_only':True}


def test_violation_retry_retains_raw_instruction_k_demo_realization_and_guard(tmp_path):
    r=record('ARTIFICIAL-TARGET',target_feedback_level=L1,code='int main(){return 0;}')
    _,ts=infer([r],ScriptedBackend(['Em hãy bỏ phần hard-code.','Em cứ kiên trì luyện tập và tự tin hơn nhé.']),cfg(),demo_pool=[train_demo()],progress_path=tmp_path/'progress.jsonl',attempt_journal_path=tmp_path/'attempts.jsonl')
    t=ts[0]
    assert not t['fallback_used']
    a,b=t['attempts']
    assert a['raw_text']=='Em hãy bỏ phần hard-code.' and not a['heuristic_compliance']
    assert b['retry_instruction'] and b['retry_instruction'] in b['prompt_messages'][0]['content']
    assert a['effective_exemplars'][0]['feedback_source']=='authored_neutral_train_realization_v4'
    assert a['effective_exemplars'][0]['original_gold_feedback']==train_demo().gold_feedback
    assert a['effective_k']==b['effective_k']==1
    assert all(json.loads(line)['attempt'] in t['attempts'] for line in (tmp_path/'attempts.jsonl').read_text().splitlines())


def test_praise_candidate_retry_is_not_a_disclosure_failure_or_semantic_rescue():
    _,ts=infer([record(target_feedback_level=L1,gold_taxonomy=[])],ScriptedBackend(['Đúng rồi!','Em hãy giữ tinh thần học hỏi và tiếp tục luyện tập nhé.']),cfg())
    t=ts[0]
    assert t['raw_first_attempt_compliance'] is True
    assert t['attempts'][0]['retry_reasons']==['level1_praise_review_candidate']
    assert t['level1_praise_candidate_cleared_after_retry'] is True
    assert not t['fallback_used'] and t['semantic_quality']=='NOT_MEASURED'


def test_persistent_praise_candidate_does_not_silently_change_fallback_policy():
    _,ts=infer([record(target_feedback_level=L1,gold_taxonomy=[])],ScriptedBackend(['Đúng rồi!']*3),cfg())
    t=ts[0]
    assert len(t['attempts'])==3
    assert not t['fallback_used']
    assert t['level1_praise_candidate_persisted'] is True
    assert 'LEVEL1_PRAISE_EVIDENCE_REVIEW_CANDIDATE' in t['quality_review_candidates']['flags']
    assert t['fallback_policy_version']==2 and t['fallback_text_policy_version']==1


def test_repeated_disclosure_uses_unchanged_fallback_and_excludes_model_success():
    outputs,ts=infer([record(target_feedback_level=L1)],ScriptedBackend(['Bỏ phần hard-code.']*3),cfg())
    assert ts[0]['fallback_reason']=='guard_retries_exhausted'
    assert outputs[0]['output']['feedback']==fallback(1)
    assert not ts[0]['model_response_complete']


def test_correct_case_neutral_feedback_is_not_forced_to_fallback():
    text='Em hãy tự tin và tiếp tục rèn luyện nhé.'
    _,ts=infer([record(target_feedback_level=L1,gold_taxonomy=[],test_report={'observed_tests':[{'passed':True}]})],ScriptedBackend([text]),cfg())
    assert not ts[0]['fallback_used'] and len(ts[0]['attempts'])==1


def test_manifest_only_reevaluation_accepts_guard3_and_keeps_candidates_separate():
    r=record(target_feedback_level=L1,gold_taxonomy=[])
    predictions=[{'sample_id':r.sample_id,'output':{'feedback':'Đúng rồi!','taxonomy_error':[]}}]
    result=evaluate([r],predictions,run_manifest={'config':{'guard_policy_version':3}})
    assert result['guard_policy_version']==3 and result['compliance']==1
    assert result['quality_review_candidates']['flag_counts']['LEVEL1_PRAISE_EVIDENCE_REVIEW_CANDIDATE']==1

@pytest.mark.parametrize('text',[
    'Em hãy tiếp tục bổ sung kiến thức và kiên trì luyện tập nhé.',
    'Em hãy bổ sung kiến thức qua việc luyện tập đều đặn.',
    'Hãy biến khó khăn thành động lực học tập.',
    'Hãy biến lo lắng thành động lực học tập.',
])
def test_review_learning_metaphors_and_knowledge_are_not_code_details(text):
    assert check(text,1,version=3).ok


@pytest.mark.parametrize('text',['Hoàn toàn chính xác!','Em làm đúng rồi!','Chương trình hoạt động tốt.'])
def test_review_bare_correctness_praise_still_requires_evidence_review(text):
    flags=quality_review_flags(record(target_feedback_level=L1,gold_taxonomy=[]),text,version=3)
    assert 'LEVEL1_PRAISE_EVIDENCE_REVIEW_CANDIDATE' in flags['flags']
