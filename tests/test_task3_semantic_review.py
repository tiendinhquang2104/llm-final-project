from src.task3.quality_review import quality_review_flags, validate_code_claims
from src.task3.compliance import check
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
