from scripts.task3_paired_report import summarize


def test_schema_valid_fallback_does_not_become_feedback_success():
    row=dict(gold=[],output={'taxonomy_error':[],'feedback':'Nhắc chung'},fallback=True,functional_status='defective',requested_level=1,
             review={'material_unknown':False,'taxonomy_review':{'supported_labels':[],'unsupported_labels':[],'missed_labels':['Lỗi logic'],'disputed_labels':[]},
                     'feedback_review':{'usefulness':'1','unsupported_or_false_claims':[],'level_violation':[],'repair_leak':False,'generic_feedback':True,'feasible_L3_repair':False,'important_errors_covered':[],'important_errors_missed':['m'],'taxonomy_feedback_contradiction':[]}})
    x=summarize([row],['Lỗi logic'])
    assert x['taxonomy_delivered']['exact']==1
    assert x['taxonomy_no_fallback_credit']['exact']==0
    assert x['feedback']['mean_proxy']==0
    assert x['feedback']['raw_reviewer_mean_proxy']==1
    assert x['source_review']['false_clean']==1
    assert x['source_review']['clean_denominator']==0
    assert x['source_review']['false_accusation_rate'] is None


def test_repeated_output_cannot_hide_changed_level_or_false_claim_verdict():
    import pytest
    from scripts.task3_paired_report import check_repeated
    a={'feedback_review':{'usefulness':'0.5','level_violation':[],'repair_leak':False,'unsupported_or_false_claims':[]},'material_unknown':False}
    b={'feedback_review':{**a['feedback_review'],'level_violation':['L2 gives replacement value']},'material_unknown':False}
    with pytest.raises(ValueError,match='repeated-output'):check_repeated(a,b)
    assert check_repeated(a,a)


def test_false_claim_evidence_is_required_and_source_finding_cannot_drift():
    import pytest
    from scripts.task3_paired_report import audit_evidence
    source={'code':'int a=0;'};findings=[{'evidence':'int a=0;','claim':'zero','confidence':'supported','taxonomy_groups':[]}]
    pair={'output':{'feedback':'x'}}
    review={'source_findings':findings,'feedback_review':{'unsupported_or_false_claims':['false']}}
    with pytest.raises(ValueError,match='evidence'):audit_evidence(review,pair,source,findings)
    review['feedback_review']['claim_evidence']=[{'output_quote':'x','source_evidence':['int a=0;'],'review_claim':'false'}]
    assert audit_evidence(review,pair,source,findings)
    with pytest.raises(ValueError,match='source findings'):audit_evidence(review,pair,source,[])
