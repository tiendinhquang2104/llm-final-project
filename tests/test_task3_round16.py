"""Prompt experiment contracts using artificial source only."""
import json
from dataclasses import replace
import pytest
from tests.test_task3_round14 import sample
from src.task3.inference import Generation, MockTokenizer


def test_shot_counts_level_match_no_query_gold_or_truncation():
    from src.task3.round16 import fitted_messages
    r=replace(sample(3),code='// FULL HEAD\nint main(){return 0;}\n// FULL TAIL')
    ex={'id':'example','level':3,'statement':'Uppercase','code':'int chuyenHoa(){return 1;}',
        'compiler':{},'output':{'taxonomy_error':[],'feedback':'Ví dụ.'}}
    cfg={'prompt_variant':'one_shot','max_new_tokens':50,'context_limit':20000}
    messages,info=fitted_messages(r,[ex],MockTokenizer(),cfg)
    assert info['examples_used']==1
    assert messages[-1]['content'].count('### Ví dụ minh họa')==1
    assert r.code in messages[-1]['content']
    assert 'gold_taxonomy' not in str(messages) and r.sample_id not in str(messages)
    with pytest.raises(ValueError,match='Level'):
        fitted_messages(r,[{**ex,'level':2}],MockTokenizer(),cfg)
    with pytest.raises(ValueError,match='budget'):
        fitted_messages(r,[ex],MockTokenizer(),{**cfg,'context_limit':10})
    with pytest.raises(ValueError,match='example'):
        fitted_messages(r,[],MockTokenizer(),cfg)


def test_evidence_is_only_projected_not_factually_gated():
    from src.task3.round16 import parse_response
    raw={'evidence':[{'location':'wrong','source_excerpt':'invented',
        'requirement_or_diagnostic':'unsupported','defect':'false'}],
        'taxonomy_error':['Lỗi logic'],'feedback':'Hãy sửa.'}
    assert parse_response(json.dumps(raw),'evidence_cot')==raw
    with pytest.raises(ValueError,match='two'):
        parse_response(json.dumps({**raw,'evidence':raw['evidence']*3}),'evidence_cot')


def test_raw_preserved_before_schema_retry_and_resume_bound(tmp_path):
    from src.task3.round16_runner import run_records
    class Backend:
        tokenizer=MockTokenizer()
        calls=0
        def generate(self,messages,config):
            self.calls+=1
            raw='broken' if self.calls==1 else json.dumps({'evidence':[], 'taxonomy_error':[], 'feedback':'Không thấy lỗi.'})
            return Generation(raw,12,0.1,'eos',True)
    cfg={'prompt_variant':'evidence_cot','max_new_tokens':100,'context_limit':20000,'max_attempts':3}
    backend=Backend()
    result=run_records([sample(3)],backend,cfg,tmp_path)
    assert backend.calls==2
    assert set(result['predictions'][0]['output'])=={'taxonomy_error','feedback'}
    attempts=[json.loads(s) for s in (tmp_path/'attempts.jsonl').read_text().splitlines()]
    assert attempts[0]['raw_text']=='broken' and attempts[0]['retry_reason'] is None
    assert attempts[1]['retry_reason']
    run_records([sample(3)],backend,cfg,tmp_path)
    assert backend.calls==2
    with pytest.raises(ValueError,match='identity'):
        run_records([replace(sample(3),code='changed')],backend,cfg,tmp_path)


def test_metrics_report_invalid_raw_coverage_without_fabricating_empty_labels():
    from scripts.task3_round16 import available_taxonomy_metrics
    records=[replace(sample(2),gold_taxonomy=[]),replace(sample(3),sample_id='second',gold_taxonomy=[])]
    result=available_taxonomy_metrics(records,[{'sample_id':records[0].sample_id,'output':{'taxonomy_error':[],'feedback':'x'}}])
    assert result['count']==1 and result['requested']==2 and result['missing_ids']==['second']
    with pytest.raises(ValueError):
        available_taxonomy_metrics(records,[{'sample_id':'unknown','output':{'taxonomy_error':[]}}])


def test_resume_can_use_remaining_attempt_after_transient_runtime_error(tmp_path):
    from src.task3.round16_runner import run_records
    class Backend:
        tokenizer=MockTokenizer()
        calls=0
        def generate(self,messages,config):
            self.calls+=1
            if self.calls==1:raise RuntimeError('transient')
            return Generation(json.dumps({'evidence':[], 'taxonomy_error':[], 'feedback':'Đối chiếu lại đề.'}),10,0.1)
    cfg={'prompt_variant':'evidence_cot','max_new_tokens':100,'context_limit':20000,'max_attempts':3}
    backend=Backend()
    assert run_records([sample(3)],backend,cfg,tmp_path)['errors']
    result=run_records([sample(3)],backend,cfg,tmp_path)
    assert backend.calls==2 and len(result['predictions'])==1
    assert len(result['traces'][0]['attempts'])==2


def test_failed_ids_remain_in_raw_attempt_accounting():
    from scripts.task3_round16 import all_traces
    result={'traces':[{'sample_id':'done','attempts':[{'raw_text':'valid'}]}],
            'errors':{'failed':{'trace':{'sample_id':'failed','attempts':[{'raw_text':'bad'}]*3}}}}
    traces=all_traces(result)
    assert {t['sample_id'] for t in traces}=={'done','failed'}
    assert sum(len(t['attempts']) for t in traces)==4


def test_manual_audit_cannot_be_reused_for_changed_model_responses():
    from scripts.task3_round16_review import verify_review_binding
    from src.task3.round14_runner import digest
    attempts=[{'raw_text':'original raw'}];final={'taxonomy_error':[],'feedback':'original'}
    note={'reviewed_raw_sha256':digest(['original raw']),'reviewed_final_sha256':digest(final)}
    verify_review_binding(note,attempts,final)
    with pytest.raises(ValueError,match='review'):
        verify_review_binding(note,[{'raw_text':'changed response'}],final)
