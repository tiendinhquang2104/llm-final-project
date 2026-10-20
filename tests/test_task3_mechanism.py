"""Mechanism regression contracts on artificial records only."""
import json
from dataclasses import replace
import pytest

from tests.test_task3_dataset import record
from tests.test_task3_diagnosis import valid_diagnosis
from src.task3.inference import Generation, MockTokenizer, MockBackend


def test_direct_cardinality_ablation_changes_only_one_or_zero_phrase():
    from src.task3.direct_baseline import build_direct_messages
    r=record()
    one=build_direct_messages(r,taxonomy_minimum=1)
    zero=build_direct_messages(r,taxonomy_minimum=0)
    before=json.dumps(one,ensure_ascii=False)
    after=json.dumps(zero,ensure_ascii=False)
    assert before.count('one or more')==1
    assert after==before.replace('one or more','zero or more')


def test_feedback_prompt_distinguishes_compiled_from_correct_and_unknown():
    from src.task3.prompts import build_messages
    for status in ('compiled','compile_error','unavailable'):
        r=replace(record(),provenance={'_task3_compile_check':{'status':status}})
        text=build_messages(r,[],prompt_policy_version=7)[-1]['content']
        payload=json.loads(text.split('UNTRUSTED_SUBMISSION_JSON\n')[1].split('\nEND_SUBMISSION_JSON')[0])
        assert payload['compiler_check_status']==status
        if status=='compiled':assert 'logic correctness is unknown' in payload['compile_log_note']


def test_uncertain_is_not_a_known_empty_taxonomy_prediction():
    from src.task3.diagnosis import diagnosis_states, require_resolved_taxonomy, UnresolvedTaxonomyError
    audit={'TEST-U':{'status':'validated','diagnosis':{'status':'uncertain','taxonomy_error':[]}},
           'TEST-X':{'status':'diagnosis_unavailable','diagnosis':{'status':'uncertain','taxonomy_error':[]}}}
    assert diagnosis_states(audit)=={'TEST-U':'uncertain','TEST-X':'unavailable'}
    with pytest.raises(UnresolvedTaxonomyError):require_resolved_taxonomy(audit,['TEST-U','TEST-X'])


def test_real_cli_refuses_full_export_of_uncertain_diagnosis(tmp_path,monkeypatch):
    from src.task3.cli import run_main
    from tests.test_task3_cli import fixture_prepared
    _,config=fixture_prepared(tmp_path)
    monkeypatch.setattr('src.task3.cli.load_tokenizer',lambda cfg:MockTokenizer())
    monkeypatch.setattr('src.task3.cli.HFBackend',lambda *args:MockBackend())
    out=tmp_path/'prediction.json'
    with pytest.raises(RuntimeError,match='unresolved taxonomy'):
        run_main(['--config',str(config),'--split','real-val','--taxonomy-source','self-diagnosis','--output',str(out)])
    assert not out.exists()
    assert json.loads(out.with_suffix('.run.json').read_text())['status']=='blocked_uncertain_taxonomy'


def test_noncompile_rediagnosis_runs_once_after_rejected_compile_finding():
    from src.task3.diagnosis import diagnose_taxonomies
    class Backend:
        tokenizer=MockTokenizer()
        calls=[]
        def generate(self,messages,config):
            self.calls.append(messages)
            label='Lỗi biên dịch' if len(self.calls)==1 else 'Lỗi logic'
            return Generation(valid_diagnosis(label=label),100,0.01,'eos',True)
    b=Backend()
    pred,audit=diagnose_taxonomies([record('TEST-REDIAG')],b,{'context_limit':10000,'noncompile_rediagnosis':True})
    assert len(b.calls)==2
    assert pred['TEST-REDIAG']==['Lỗi logic']
    assert audit['TEST-REDIAG']['noncompile_rediagnosis']['status']=='accepted'
    assert 'non-compile' in b.calls[-1][-1]['content']
    assert 'gold_feedback' not in json.dumps(b.calls,ensure_ascii=False)


def test_noncompile_rediagnosis_never_relabels_another_compile_claim():
    from src.task3.diagnosis import diagnose_taxonomies, diagnosis_states
    class Backend:
        tokenizer=MockTokenizer()
        calls=0
        def generate(self,messages,config):
            self.calls+=1
            return Generation(valid_diagnosis(label='Lỗi biên dịch'),100,0.01,'eos',True)
    b=Backend()
    pred,audit=diagnose_taxonomies([record('TEST-REJECT')],b,{'context_limit':10000,'noncompile_rediagnosis':True})
    assert b.calls==2
    assert audit['TEST-REJECT']['noncompile_rediagnosis']['status']=='rejected'
    assert diagnosis_states(audit)['TEST-REJECT']=='uncertain'


def test_oracle_finding_loader_rejects_unapproved_and_wrong_source(tmp_path):
    from src.task3.oracle_findings import load_reviewed_findings
    r=record('TEST-ORACLE')
    p=tmp_path/'findings.json'
    p.write_text(json.dumps({'review_status':'draft_not_human_verified','samples':[]}))
    with pytest.raises(ValueError,match='review approval'):
        load_reviewed_findings(p,[r])


def test_oracle_context_persists_across_feedback_retry_and_never_runs_on_public(tmp_path):
    from src.task3.pipeline import infer
    from src.task3.oracle_findings import oracle_finding_message
    r=replace(record('TEST-ORACLE'),target_feedback_level='Level 2 - Chẩn đoán')
    findings={r.sample_id:[{'finding_id':'TEST-FACT','problem_id':None,'proposed_taxonomy_label':'Lỗi logic',
                          'source_quote':'return 17;','error':'TEST reviewed fact','cause':'TEST source evidence',
                          'permitted_repair_direction':'TEST direction must not be disclosed at Level 2'}]}
    class Backend:
        tokenizer=MockTokenizer()
        calls=[]
        def generate(self,messages,config):
            self.calls.append(messages)
            assert any('REVIEW_APPROVED_ORACLE_FINDINGS_JSON' in m['content'] for m in messages)
            text='Hãy thay return 17 bằng giá trị khác.' if len(self.calls)==1 else 'Vấn đề ở giá trị trả về cố định.'
            return Generation(text,30,0.01,'eos',True)
    b=Backend()
    out,_=infer([r],b,{'context_limit':20000,'guard_policy_version':2,'max_retries':1},'gold',oracle_findings=findings)
    assert len(b.calls)==2
    assert out[0]['output']['feedback']=='Vấn đề ở giá trị trả về cố định.'
    public=replace(r,source='public',split='public',gold_taxonomy=None,gold_feedback=None)
    with pytest.raises(ValueError,match='oracle'):
        infer([public],b,{'context_limit':20000},'gold',oracle_findings=findings)
    assert 'gold_feedback' not in oracle_finding_message(r,findings[r.sample_id])['content']


def test_reviewed_findings_bind_approval_to_exact_source_and_statement(tmp_path):
    import hashlib
    from src.task3.oracle_findings import load_reviewed_findings
    r=record('TEST-APPROVED')
    finding={'finding_id':'TEST-FACT','problem_id':None,'proposed_taxonomy_label':'Lỗi logic',
             'source_quote':'return 17;','error':'TEST observed fixed value','cause':'TEST fixed return',
             'permitted_repair_direction':'TEST direction','review_status':'approved_for_oracle_experiment'}
    value={'review_status':'approved_for_oracle_experiment','review_approval':{'reviewer':'TEST-ONLY','provenance':'artificial test fixture'},
           'samples':[{'sample_id':r.sample_id,'source_code_utf8_sha256':'WRONG',
                       'statement_utf8_sha256':hashlib.sha256(r.statement.encode()).hexdigest(),'findings':[finding]}]}
    p=tmp_path/'approved.json';p.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='source hash'):load_reviewed_findings(p,[r])
    value['samples'][0]['source_code_utf8_sha256']=hashlib.sha256(r.code.encode()).hexdigest()
    p.write_text(json.dumps(value))
    result=load_reviewed_findings(p,[r])
    assert result[r.sample_id][0]['source_quote']=='return 17;'
    assert 'gold_feedback' not in result[r.sample_id][0]


def test_level1_oracle_context_keeps_only_issue_flag_without_technical_finding():
    from src.task3.pipeline import infer
    r=replace(record('TEST-L1-ORACLE'),target_feedback_level='Level 1 - Gợi ý nhẹ')
    findings={r.sample_id:[{'finding_id':'TEST-SECRET-TECHNICAL','problem_id':None,'proposed_taxonomy_label':'Lỗi logic',
                          'source_quote':'return 17;','error':'SECRET_FINDING_CAUSE','cause':'SECRET_CAUSE',
                          'permitted_repair_direction':'SECRET_REPAIR'}]}
    class Backend:
        tokenizer=MockTokenizer()
        def generate(self,messages,config):
            context=[m for m in messages if m['content'].startswith('REVIEW_APPROVED_ORACLE_FINDINGS_JSON\n')]
            assert len(context)==1
            assert 'SECRET_' not in context[0]['content']
            assert 'approved_issue_present' in context[0]['content']
            return Generation('Bài cần được rà soát thêm.',12,0.01,'eos',True)
    out,_=infer([r],Backend(),{'context_limit':20000,'prompt_policy_version':7,'guard_policy_version':2},'gold',oracle_findings=findings)
    assert out[0]['output']['feedback']=='Bài cần được rà soát thêm.'
