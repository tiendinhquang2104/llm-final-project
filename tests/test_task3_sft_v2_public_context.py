import pytest
import torch
from src.task3.sft_v2_public_context import generate,preflight
from src.task3.sft_v2_public import PublicJournal
from src.task3.sft_v1_runtime import digest

SETTINGS=dict(max_new_tokens={'2':1024},max_time=45.,eos_token_id=9,pad_token_id=0,do_sample=False,concurrency=1)


class Tokenizer:
    def __init__(self,n):self.n=n;self.calls=[]
    def apply_chat_template(self,prompt,**kw):
        self.calls.append((prompt,kw))
        if kw.get('return_tensors'):return {'input_ids':torch.ones((1,self.n),dtype=torch.long)}
        return list(range(self.n))
    def decode(self,tail,**kw):return '{"taxonomy_error":[],"feedback":"Đúng."}'


def example():
    return dict(sample_id='official',example_id='official',level=2,prompt=[dict(role='system',content='Allowed taxonomy labels: ["Lỗi logic"]'),dict(role='user',content='full source and logs')])


@pytest.mark.parametrize('context,n,admit',[(8192,8192,False),(32768,18824,True),(32768,31744,True),(32768,31745,False)])
def test_actual_preflight_and_generation_share_configured_guard(tmp_path,monkeypatch,context,n,admit):
    t=Tokenizer(n);e=example();j=PublicJournal(tmp_path/'j.jsonl',{'official':digest(e['prompt'])})
    report=preflight(t,[e],SETTINGS,context)[0]
    assert (report['status']=='evaluable') is admit
    class StopBeforeWeights:
        def generate(self,**kw):raise AssertionError('model execution should be mocked at CUDA transfer')
    # Guard runs on actual token tensor before device transfer; no GPU/model needed.
    def transfer(self,*a,**kw):raise RuntimeError('ADMITTED_FULL_PROMPT')
    monkeypatch.setattr(torch.Tensor,'to',transfer)
    with pytest.raises((RuntimeError,ValueError)) as exc:generate(StopBeforeWeights(),t,e,SETTINGS,j,'official',context)
    assert ('ADMITTED_FULL_PROMPT' in str(exc.value)) is admit
    assert report['allowance']==1024 and report['prompt_tokens']==n
    assert all(p==e['prompt'] for p,kw in t.calls)
    assert all(not kw.get('truncation',False) for p,kw in t.calls)
    assert not j.reserved()


def test_public_context_must_be_explicit_and_positive(tmp_path):
    with pytest.raises(ValueError):preflight(Tokenizer(10),[example()],SETTINGS,0)


def test_context_change_retains_one_call_arguments_and_full_response(tmp_path,monkeypatch):
    from contextlib import nullcontext
    e=example();t=Tokenizer(18824);j=PublicJournal(tmp_path/'j.jsonl',{'official':digest(e['prompt'])})
    monkeypatch.setattr(torch.Tensor,'to',lambda self,*a,**kw:self)
    monkeypatch.setattr(torch.cuda,'synchronize',lambda:None)
    monkeypatch.setattr(torch,'autocast',lambda *a,**kw:nullcontext())
    seen=[]
    class Model:
        def generate(self,**kw):
            seen.append(kw)
            return torch.cat([kw['input_ids'],torch.tensor([[4,9]])],dim=1)
    r=generate(Model(),t,e,SETTINGS,j,'official',32768)
    assert r['status']=='valid' and r['finish_reason']=='eos'
    assert r['input_tokens']==18824 and r['output_tokens']==2
    assert len(seen)==1
    assert {k:v for k,v in seen[0].items() if k!='input_ids'}==dict(do_sample=False,num_beams=1,max_new_tokens=1024,max_time=45.,eos_token_id=9,pad_token_id=0,use_cache=True)
    assert len(j.reserved())==1
    # The caller recovers completed calls before invoking generate. Even direct
    # misuse cannot generate a second response under the strict public journal.
    with pytest.raises(ValueError,match='outstanding reservation'):
        generate(Model(),t,e,SETTINGS,j,'official',32768)
    assert len(seen)==1


def test_uncertain_reserved_primary_is_never_replayed(tmp_path):
    e=example();t=Tokenizer(18824);j=PublicJournal(tmp_path/'j.jsonl',{'official':digest(e['prompt'])});j.reserve('official')
    result=generate(None,t,e,SETTINGS,j,'official',32768)
    assert result['finish_reason']=='interrupted_unknown' and not t.calls


def test_resume_rejects_other_method_even_when_prompt_and_ids_match(tmp_path):
    from src.task3.sft_v2_public_context_runtime import BoundJournal
    e=example();allowed={'official':digest(e['prompt'])};path=tmp_path/'journal.jsonl'
    old=PublicJournal(path,allowed);old.reserve('official')
    with pytest.raises(ValueError,match='method identity'):BoundJournal(path,allowed,'a'*64)


def test_resume_binds_current_freeze_not_only_method_name(tmp_path):
    from src.task3.sft_v2_public_context_runtime import BoundJournal
    e=example();allowed={'official':digest(e['prompt'])};path=tmp_path/'journal.jsonl'
    j=BoundJournal(path,allowed,'a'*64);j.reserve('official')
    assert BoundJournal(path,allowed,'a'*64).reserved()=={'official'}
    with pytest.raises(ValueError,match='method identity'):BoundJournal(path,allowed,'b'*64)
