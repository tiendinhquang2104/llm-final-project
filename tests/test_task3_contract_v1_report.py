"""Artificial-only offline accounting for the new TRAIN development study."""
import pytest


def test_taxonomy_abstention_with_real_feedback_never_gets_exact_clean():
    from scripts.task3_contract_v1_report import taxonomy
    records=[dict(sample_id='a',labels=[]),dict(sample_id='b',labels=['Lỗi logic'])]
    predictions=[dict(sample_id='a',status='abstained',output=dict(taxonomy_error=[],feedback='Chưa đủ căn cứ.')),
                 dict(sample_id='b',status='schema_error')]
    r=taxonomy(records,predictions,'labels')
    assert r['exact_set']==dict(numerator=0,denominator=2)
    assert r['per_label']['Lỗi logic']['fn']==1
    assert len(r['per_label'])==10


def test_taxonomy_null_reference_is_excluded_not_clean():
    from scripts.task3_contract_v1_report import taxonomy
    r=taxonomy([dict(sample_id='a',labels=None)],[],'labels')
    assert r['supported_sources']==0 and r['excluded_sources']==1
    assert r['micro']['f1'] is None and r['macro_f1'] is None


def test_taxonomy_reports_support_and_false_positive_for_unused_label():
    from scripts.task3_contract_v1_report import taxonomy
    r=taxonomy([dict(sample_id='a',labels=['Lỗi hàm'])],
        [dict(sample_id='a',status='completed',output=dict(taxonomy_error=['Lỗi style'],feedback='Gợi ý.'))],'labels')
    assert r['per_label']['Lỗi style']==dict(tp=0,fp=1,fn=0,support=0)
    assert r['per_label']['Lỗi hàm']['fn']==1


def test_incomplete_arm_has_no_prefix_metrics():
    from scripts.task3_contract_v1_report import require_complete
    with pytest.raises(ValueError,match='complete'):
        require_complete([{'request_id':'r1'}],{'complete':False,'processed_requests':1},['r1','r2'])


def test_duplicate_or_other_request_rejected_even_if_count_matches():
    from scripts.task3_contract_v1_report import require_complete
    with pytest.raises(ValueError):
        require_complete([{'request_id':'r1'},{'request_id':'r1'}],{'complete':True,'processed_requests':2},['r1','r2'])


def test_score_rejects_wrong_source_for_an_otherwise_valid_request():
    from scripts.task3_contract_v1_report import require_complete
    with pytest.raises(ValueError,match='source'):
        require_complete([dict(request_id='r1',sample_id='other')],
            dict(complete=True,processed_requests=1),['r1'],expected_sources={'r1':'expected'})
