import pytest

from src.task3.quality_review import quality_review_flags, validate_code_claims
from src.task3.compliance import check
from src.task3.inference import Generation, MockBackend
from src.task3.pipeline import infer
from tests.test_task3_dataset import record


def test_code_claim_validator_rejects_known_contradictions_and_preserves_unknowns():
    code = 'int d=0; long long p=1; int* ptr = values; ptr[i];'
    claims = [
        {'claim': 'd is uninitialized', 'evidence': 'd'},
        {'claim': 'p is uninitialized', 'evidence': 'p'},
        {'claim': 'pointer indexing is illegal', 'evidence': 'ptr[i]'},
        {'claim': 'unknown issue', 'evidence': 'line 2'},
    ]
    result = validate_code_claims(code, claims, statement='n >= 1')
    assert [item['status'] for item in result] == ['contradicted', 'contradicted', 'contradicted', 'unverified']


def test_zero_and_one_edge_claims_respect_statement_constraints():
    result = validate_code_claims('int d=0; long long p=1;', [
        {'claim': 'd=0 is a failure', 'evidence': 'd=0'},
        {'claim': 'p=1 is an uninitialized accumulator', 'evidence': 'p=1'},
    ], statement='1 <= n <= 10^9')
    assert result[0]['status'] == 'unsupported_by_constraints'
    assert result[1]['status'] == 'contradicted'


def test_level_guards_reject_specific_level1_and_vague_level3_feedback():
    level1 = check('Em hãy xem lại hàm ArmstrongNumber và vòng lặp for đang tính lũy thừa.', 1, version=3)
    level2 = check('Hãy đổi p thành 1 rồi nhân thêm một lần.', 2, version=3)
    assert 'level1_technical_disclosure' in level1.violations
    assert 'repair_guidance' in level2.violations
    vague = quality_review_flags(record(target_feedback_level='Level 3 - Gợi ý sửa'), 'Chương trình cần được kiểm tra lại.')
    assert check('Chương trình cần được kiểm tra lại.', 3, version=3).ok  # guard is not a content score
    assert {'LEVEL3_DIAGNOSIS_REVIEW_CANDIDATE', 'LEVEL3_DIRECTION_REVIEW_CANDIDATE'} <= set(vague['flags'])
    useful = quality_review_flags(record(target_feedback_level='Level 3 - Gợi ý sửa'), 'Sai số mũ ở vòng lặp tính lũy thừa; hãy dùng số chữ số vừa đếm làm số lần nhân.')
    assert not {'LEVEL3_DIAGNOSIS_REVIEW_CANDIDATE', 'LEVEL3_DIRECTION_REVIEW_CANDIDATE'} & set(useful['flags'])


def test_level3_direction_review_recognizes_specific_direction_after_heading():
    text = (
        'Biến `cnt` chưa được khai báo trong điều kiện vòng lặp. '
        'Hướng sửa: Khởi tạo biến `cnt` bằng số chữ số đã đếm trước khi dùng nó làm giới hạn.'
    )
    result = quality_review_flags(record(target_feedback_level='Level 3 - Gợi ý sửa'), text)
    assert 'LEVEL3_DIRECTION_REVIEW_CANDIDATE' not in result['flags']


def test_feedback_source_review_catches_false_pointer_and_header_claims():
    row = record(
        target_feedback_level='Level 2 - Chẩn đoán',
        code=(
            'Node* a = new Node; a[n].next = nullptr;\n'
            'fin.seekg(0); getline(fin, header); while (getline(fin, row)) {}'
        ),
    )
    text = (
        'Dùng toán tử [] trên con trỏ không hợp lệ. '
        'Đọc lại tiêu đề khiến chương trình bỏ qua dữ liệu đầu tiên.'
    )
    result = quality_review_flags(row, text, version=2)
    assert 'SOURCE_CONTRADICTION_REVIEW_CANDIDATE' in result['flags']
    assert 'SOURCE_CONTRADICTION_REVIEW_CANDIDATE' in quality_review_flags(row, text, version=3)['flags']


def test_feedback_source_review_rejects_false_d_and_p_claims_but_not_valid_claims():
    row = record(
        target_feedback_level='Level 2 - Chẩn đoán',
        code='int d = 0; long long p = 1;',
        statement='Input n is positive and n >= 1.',
    )
    bad = quality_review_flags(row, 'Biến d chưa được khởi tạo và p=1 là sai.', version=2)
    good = quality_review_flags(row, 'Biến d=0 và p=1 được khởi tạo hợp lệ.', version=2)
    assert 'SOURCE_CONTRADICTION_REVIEW_CANDIDATE' in bad['flags']
    assert 'SOURCE_CONTRADICTION_REVIEW_CANDIDATE' not in good['flags']
    d_claim = quality_review_flags(
        row,
        'Biến d được dùng làm chỉ số nhưng không được khởi tạo.',
        version=2,
    )
    assert 'SOURCE_CONTRADICTION_REVIEW_CANDIDATE' in d_claim['flags']


def test_feedback_source_review_does_not_treat_proposed_code_as_student_source():
    row = record(
        target_feedback_level='Level 3 - Gợi ý sửa',
        code='int numdigi = 0; for (int i = 1; i <= cnt; i++) {}',
    )
    text = (
        'Biến `cnt` chưa được khai báo. Hướng sửa: Khởi tạo biến `cnt` bằng `numdigi`.\n'
        '```cpp\nint cnt = numdigi;\n```'
    )
    result = quality_review_flags(row, text, version=2)
    assert 'SOURCE_CONTRADICTION_REVIEW_CANDIDATE' not in result['flags']


def test_uninitialized_claim_matches_named_variable_not_other_initialized_identifier():
    review = validate_code_claims(
        'int numdigi = 0; for (int i = 1; i <= cnt; i++) {}',
        [{'claim': 'Biến cnt chưa được khởi tạo; hãy dùng numdigi làm số lần lặp.', 'evidence': ''}],
    )
    assert review[0]['status'] == 'unverified'


def test_source_contradiction_feedback_is_retried_before_export():
    class CorrectingBackend(MockBackend):
        calls = 0

        def generate(self, messages, config):
            self.calls += 1
            text = (
                'Đọc lại tiêu đề khiến chương trình bỏ qua dữ liệu đầu tiên.'
                if self.calls == 1 else
                'Phần đọc dữ liệu có bước đọc tiêu đề trước vòng lặp xử lý các dòng.'
            )
            return Generation(text, 20, 0.1)

    backend = CorrectingBackend()
    row = record(
        target_feedback_level='Level 2 - Chẩn đoán',
        code='fin.seekg(0); getline(fin, s); while (getline(fin, s)) {}',
    )
    predictions, traces = infer([row], backend, {'context_limit': 10000, 'max_retries': 1})
    assert backend.calls == 2
    assert traces[0]['attempts'][0]['retry_reasons'] == ['source_claim_candidate']
    assert 'bỏ qua dữ liệu đầu tiên' not in predictions[0]['output']['feedback']


def test_level3_exhausted_quality_retry_refuses_to_export_generic_fallback():
    class VagueBackend(MockBackend):
        calls = 0

        def generate(self, messages, config):
            self.calls += 1
            return Generation('Chương trình cần được kiểm tra lại.', 20, .1)

    backend = VagueBackend()
    row = record(target_feedback_level='Level 3 - Gợi ý sửa')
    with pytest.raises(RuntimeError, match='Level 3.*generic fallback'):
        infer([row], backend, {
            'context_limit': 10000,
            'adequacy_retry_policy_version': 1,
            'max_retries': 1,
        })
    assert backend.calls == 2
