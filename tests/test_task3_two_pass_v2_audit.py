"""Artificial offline scoring checks: no model response is assumed correct by regex."""
import pytest
from scripts import task3_two_pass_v2_audit as audit


def review(**updates):
    row={k:True for k in ['finding_supported','main_covered','consistent','level_ok','natural','direct_em']}
    row.update({k:False for k in ['false_claim','meta','clean_false_error','generic_only','disputed']})
    row.update(l1_detail_leak=None,l2_repair_leak=False,l3_actionable=None)
    row.update(updates);return row


def test_contains_em_does_not_override_reviewer_meta_verdict():
    output={'taxonomy_error':[],'feedback':'Giảng viên khen em.'}
    refs=[{'source_taxonomy':[],'source_disputed':False}]*2
    score=audit.combine(output,[review(direct_em=False,meta=True)]*2,refs)
    assert score['meta'] is True and score['direct_em'] is False and not score['strict_joint']


def test_missing_output_and_source_dispute_never_get_joint_credit():
    ref={'source_taxonomy':[],'source_disputed':True}
    assert not audit.combine(None,[review()]*2,[ref]*2)['strict_joint']
    assert not audit.combine({'taxonomy_error':[],'feedback':'Em đã làm đúng.'},[review()]*2,[ref]*2)['strict_joint']


def test_label_and_entire_feedback_are_bound_to_reviewed_packet():
    units=[{'sample_id':'ARTIFICIAL','level':2,'task':{'code':'fake'}}]
    arms={'A':{'ARTIFICIAL':{'status':'resolved','output':{'taxonomy_error':[],'feedback':'Original.'}}}}
    key={'oid':{'sample_id':'ARTIFICIAL','arm':'A'}}
    packet={'cases':[{'sample_id':'ARTIFICIAL','level':2,'task':{'code':'fake'},'outputs':[{'output_id':'oid',**arms['A']['ARTIFICIAL']}]}]}
    audit.bind(units,arms,key,packet)
    arms['A']['ARTIFICIAL']['output']={'taxonomy_error':[],'feedback':'Changed.'}
    with pytest.raises(ValueError):audit.bind(units,arms,key,packet)


def test_taxonomy_gain_alone_cannot_open_E_gate():
    base={'taxonomy_original':{'micro_f1':.2,'macro_f1':.1,'per_label':{'Lỗi mảng/chuỗi':{'TP':0}}}}
    candidate={'taxonomy_original':{'micro_f1':.5,'macro_f1':.4,'per_label':{'Lỗi mảng/chuỗi':{'TP':1}}}}
    c={'completed':15,'meta':1,'clean_false_error':0,'clean_false_error_confirmed':0,'direct_em':15}
    assert not all(audit.e_checks({'B':base,'C':c,'D':candidate}).values())


def test_one_reviewer_clean_error_disagreement_blocks_E():
    base={'taxonomy_original':{'micro_f1':.2,'macro_f1':.1,'per_label':{'Lỗi mảng/chuỗi':{'TP':0}}}}
    candidate={'taxonomy_original':{'micro_f1':.5,'macro_f1':.4,'per_label':{'Lỗi mảng/chuỗi':{'TP':1}}}}
    c={'completed':15,'meta':0,'clean_false_error':1,'clean_false_error_confirmed':0,'direct_em':15}
    assert not all(audit.e_checks({'B':base,'C':c,'D':candidate}).values())


def test_level_ok_cannot_override_reported_repair_leak():
    refs=[{'source_taxonomy':['Lỗi logic'],'source_disputed':False}]*2
    output={'taxonomy_error':['Lỗi logic'],'feedback':'Em hãy đổi phép tính.'}
    result=audit.combine(output,[review(l2_repair_leak=True)]*2,refs)
    assert not result['feedback_pass'] and not result['strict_joint']


def test_E_authorization_rechecks_current_reviewed_packet_before_loading(monkeypatch):
    from scripts import task3_two_pass_v2 as runner
    def stale(phase):raise ValueError('changed current C output')
    monkeypatch.setattr(audit,'verify_packet',stale)
    with pytest.raises(ValueError,match='changed current C output'):runner.authorize_E()


def test_changed_gold_reference_is_rejected_by_frozen_input_hash(tmp_path,monkeypatch):
    from scripts import task3_two_pass_v2 as runner
    from src.task3.dataset import write_json
    from src.task3.level_blind import sha
    out=tmp_path/'run';frozen=out/'frozen';frozen.mkdir(parents=True)
    monkeypatch.setattr(runner,'ROOT',tmp_path);monkeypatch.setattr(runner,'OUT',out)
    gold=tmp_path/'original-reference.json';write_json(gold,{'artificial':'original'})
    write_json(frozen/'level-definitions.json',[]);write_json(out/'review/source-seal.json',{'hashes':{}})
    write_json(frozen/'freeze.json',{'code_sha256':{},'input_sha256':{'original-reference.json':sha(gold)},'definitions_sha256':sha(frozen/'level-definitions.json')})
    (frozen/'freeze.sha256').write_text(sha(frozen/'freeze.json')+'\n')
    runner.verify();write_json(gold,{'artificial':'modified'})
    with pytest.raises(ValueError,match='original-reference.json'):runner.verify()


@pytest.mark.parametrize('level,key',[(1,'l1_detail_leak'),(2,'l2_repair_leak'),(3,'l3_actionable')])
def test_reviewer_cannot_omit_applicable_Level_assessment(level,key):
    row={k:None for k in audit.SPECIAL}
    with pytest.raises(ValueError):audit.validate_level_fields(row,level,True)
