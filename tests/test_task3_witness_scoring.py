from src.task3.witness_scoring import score_witness,pair_metrics


def prediction(witness,actual='0',expected='2'):
    return {'status':'defect','input':witness,'predicted_actual':{'termination':'ok','stdout':actual},'predicted_expected':expected}


def test_hidden_oracle_and_actual_are_compared_independently():
    p=prediction({'stdin':'2\n1 2','files':{}},actual='0',expected='2')
    r=score_witness('SYN-SUMEVEN',p,{'status':'pass'},lambda w:{'returncode':0,'stdout':'1','stderr':'','timeout':False,'executed':True})
    assert r['input_valid']and r['expected_correct']and not r['actual_correct']and r['distinguishes']


def test_out_of_domain_never_executes():
    def forbidden(_):raise AssertionError('must not run')
    r=score_witness('SYN-MAXARR',prediction({'stdin':'0','files':{}}),{'status':'pass'},forbidden)
    assert not r['input_valid']and r['actual_correct']is None


def test_compile_error_is_diagnostic_not_program_output_execution():
    p=prediction({'stdin':'0','files':{}},actual='',expected='1');p['predicted_actual']['termination']='compile_error'
    def forbidden(_):raise AssertionError('compile error cannot execute')
    r=score_witness('SYN-FACT',p,{'status':'error','stderr':'main must return int'},forbidden)
    assert r['actual_correct']and r['expected_correct']and r['distinguishes']
    assert r['actual']['executed']is False


def test_pair_denominator_keeps_schema_and_uncertain_failures():
    rows=[{'pair_id':'a','base_success':True,'mutant_success':True},
          {'pair_id':'b','base_success':False,'mutant_success':True},
          {'pair_id':'c','base_success':True,'mutant_success':False}]
    m=pair_metrics(rows)
    assert m=={'pairs':3,'successes':1,'accuracy':1/3}


def test_malformed_raw_actual_cannot_crash_observational_scoring():
    p=prediction({'stdin':'2\n1 2','files':{}});p['predicted_actual']='not an object'
    r=score_witness('SYN-SUMEVEN',p,{'status':'pass'},lambda w:{'returncode':0,'stdout':'2','stderr':'','timeout':False,'executed':True})
    assert r['input_valid']and r['actual_correct']is False


def test_null_stdout_is_incorrect_rather_than_crashing():
    p=prediction({'stdin':'0','files':{}},actual=None,expected='1')
    r=score_witness('SYN-FACT',p,{'status':'pass'},lambda w:{'returncode':0,'stdout':'1','timeout':False})
    assert r['input_valid'] and r['actual_correct'] is False


def test_non_ascii_numeric_input_never_executes():
    def forbidden(_):raise AssertionError('invalid C-locale input cannot execute')
    for witness in [{'stdin':'١','files':{}},{'stdin':'1\u00a0','files':{}},{'stdin':'1\x1c','files':{}}]:
        r=score_witness('SYN-FACT',prediction(witness),{'status':'pass'},forbidden)
        assert r['input_valid'] is False
