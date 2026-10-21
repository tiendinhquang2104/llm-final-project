"""Artificial boundary fixtures; none are gold labels or historical outputs."""
from dataclasses import replace
import json
import pytest
from tests.test_task3_round14 import sample
from src.task3 import round15
from src.task3.round15_disclosure import disclosure_violations

ALLOWED = [
    'Ở điều kiện `x%2!=0`, chương trình cộng các số lẻ nên tổng in ra không tương ứng với yêu cầu tính tổng số chẵn.',
    'Sau khi xóa phần tử nhỏ nhất, `rbegin()` vẫn chỉ tới phần tử lớn nhất còn lại, nên kết quả không phải giá trị lớn thứ hai.',
    'Tại lời gọi `getline(sa,s,)`, danh sách đối số kết thúc ngay sau dấu phẩy nên compiler báo lỗi cú pháp.',
    'Trong P3, `cur` không thay đổi sau mỗi lượt, nên khi nó khác null, vòng lặp không kết thúc.',
    'Dòng 8 thiếu câu lệnh return nên hàm không trả về kết quả.',
    'Điều kiện `x%2!=0` chọn số lẻ thay vì số chẵn.',
    'main.cpp:8:3: error: expected ; before return\n 8 | return total;',
]
FORBIDDEN = [
    'Đổi `x%2!=0` thành `x%2==0`.',
    'Khởi tạo total bằng 0 rồi cộng tất cả các số.',
    'Xóa phần tử lớn nhất trước rồi lấy phần tử lớn nhất còn lại.',
    'Nên kiểm tra set còn phần tử nào không.',
    'Thêm đối số sau dấu phẩy.',
    'Thêm `cur = cur->next` vào vòng lặp.',
    'Biến total nên khai báo kiểu long long để tránh overflow khi tính tổng các ước.',
]

@pytest.mark.parametrize('level',[1,3,4])
@pytest.mark.parametrize('retry',[None,'disclosure: explicit_repair_disclosure'])
def test_non_l2_messages_identical_to_r15(level,retry):
    from src.task3.level2_prompt import messages
    r=sample(level)
    assert messages(r,[],arm='D',retry=retry)==round15.build_messages(r,[],retry=retry)

@pytest.mark.parametrize('retry',[None,'schema error','disclosure: explicit_repair_disclosure'])
def test_control_and_user_retry_payload_unchanged(retry):
    from src.task3.level2_prompt import messages, L2_INSTRUCTION
    r=sample(2)
    base=round15.build_messages(r,[],retry=retry)
    assert messages(r,[],arm='A',retry=retry)==base
    d=messages(r,[],arm='D',retry=retry)
    assert d[1:]==base[1:]
    assert d[0]['content']==round15.SYSTEM+L2_INSTRUCTION
    for phrase in ['vị trí','cơ chế','hậu quả','không xuất','đang có','đã sửa','long long','JSON']:
        assert phrase in L2_INSTRUCTION
    assert set(json.loads(d[1]['content']))==set(round15.query_payload(r))

@pytest.mark.parametrize('text',ALLOWED)
def test_r15_keeps_useful_diagnoses(text):
    assert disclosure_violations(text,2)==[]

@pytest.mark.parametrize('text',['Thay total bằng 0.'])
def test_r15_known_explicit_repairs(text):
    assert disclosure_violations(text,2)

@pytest.mark.parametrize('text',FORBIDDEN)
def test_document_r15_surface_blind_spots(text):
    # A passing test documents a miss, never semantic compliance.
    assert disclosure_violations(text,2)==[]


def test_adapter_restores_controller_and_budget():
    from src.task3.level2_prompt import adapter
    from src.task3.inference import MockTokenizer
    import src.task3.round15_runner as runner
    original=runner.fitted_messages
    with adapter('D'):
        rendered,budget=runner.fitted_messages(sample(2),[],MockTokenizer(),{'max_new_tokens':1024,'context_limit':20000})
        assert budget['examples_used']==0
        assert budget['input_tokens']==len(MockTokenizer().apply_chat_template(rendered,tokenize=True,add_generation_prompt=True))
    assert runner.fitted_messages is original
    with pytest.raises(ValueError,match='never truncate'):
        with adapter('D'):
            runner.fitted_messages(sample(2),[],MockTokenizer(),{'max_new_tokens':1024,'context_limit':3})
    assert runner.fitted_messages is original


def test_offline_entrypoint_rejects_public_gold_and_wrong_partition(tmp_path):
    from dataclasses import asdict
    from scripts.task3_level2_diagnostic import offline_records
    r=replace(sample(2),source='synthetic',split='exposed-offline-development',gold_taxonomy=None,gold_feedback=None)
    path=tmp_path/'inputs.json'
    path.write_text(json.dumps([asdict(r)]))
    assert offline_records(path)[0].sample_id==r.sample_id
    for changed in [replace(r,source='public'),replace(r,split='synthetic-train'),replace(r,gold_taxonomy=[]),replace(r,target_feedback_level=sample(3).target_feedback_level)]:
        path.write_text(json.dumps([asdict(changed)]))
        with pytest.raises(ValueError,match='offline Level2'):offline_records(path)
