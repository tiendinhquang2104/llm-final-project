def test_supported_keeps_uncertain_and_requires_location():
    from scripts.task3_base_pv3_report import supported
    axes={k:'pass' for k in ['diagnosis_supported','coverage','factual_fidelity','location_and_condition']}
    r=dict(status='valid',parsed={'taxonomy_error':['Lỗi logic']},axes=axes)
    assert supported(r) is True
    axes['location_and_condition']='fail'
    assert supported(r) is False
    axes['location_and_condition']='pass';axes['factual_fidelity']='uncertain'
    assert supported(r) is None
    r['status']='malformed_json';r['parsed']=None
    assert supported(r) is None


def test_uncertain_repair_is_not_a_known_miss():
    from scripts.task3_base_pv3_report import repair
    r=dict(status='valid',parsed={'taxonomy_error':['Lỗi logic']},code_verdict='absent',
        axes=dict(diagnosis_supported='pass',coverage='pass',factual_fidelity='pass',location_and_condition='pass',l3_repair_direction='uncertain'))
    assert repair(r) is None
