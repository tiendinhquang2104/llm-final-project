"""Fresh synthetic fixtures only; no dataset or previous prediction reads."""
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def runner():
    return importlib.import_module('scripts.task3_contract_v1_infer')


def config():
    return dict(model_id='Qwen/Qwen2.5-Coder-7B-Instruct', revision='c03e6d358207e414f1eca0bb1891e29f1db0e242',
                seed=42, load_in_4bit=True, do_sample=False, context_limit=16384,
                diagnosis_max_tokens=1536, max_new_tokens=1024, level4_max_tokens=1536,
                max_time=60, max_attempts=3, prompt_variant='zero_shot', few_shot_k=0,
                prompt_policy='round15-short-direct-v1',
                completion_policy='preserve_qwen_content_with_schema_and_explicit_l1_l2_only')


def rows():
    return [dict(request_id=f'fixture:{i}@L{1+i%4}', sample_id=f'fixture:{i}', kind='primary',
                 requested_level=1+i%4, task=dict(statement='Artificial task: print zero. Domain: no input.',
                 problems=[], grading_policy='', code='int main(){return 0;}',
                 compiler_evidence={'status':'pass','diagnostic':''}, domain={'input':'none'})) for i in range(30)]


class Tokenizer:
    chat_template='synthetic tokenizer'
    _task3_revision='synthetic'
    def apply_chat_template(self, messages, **kwargs):
        return [0] * 100


class Backend:
    tokenizer=Tokenizer()
    def __init__(self, texts):
        self.texts=iter(texts)
        self.calls=[]
    def generate(self, messages, conf):
        self.calls.append((messages, dict(conf)))
        value=next(self.texts)
        if isinstance(value, BaseException):
            raise value
        return SimpleNamespace(text=value, output_tokens=7, latency_s=0.01, finish_reason='eos', eos_reached=True)


def read_lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def test_short_invalid_diagnosis_is_captured_once_without_feedback_or_retry(tmp_path):
    backend=Backend(['not json']*30)
    result=runner().run_arm(rows(), backend, config(), tmp_path, arm='SHORT')
    assert len(backend.calls)==30
    assert len(result['predictions'])==30
    assert {p['status'] for p in result['predictions']}=={'schema_error'}
    generations=read_lines(tmp_path/'generations.jsonl')
    assert len(generations)==30
    assert all(g['raw_text']=='not json' and g['raw_sha256'] and g['prompt_sha256'] for g in generations)
    assert all(g['input_tokens']==100 and g['output_tokens']==7 for g in generations)
    assert json.loads((tmp_path/'status.json').read_text())['complete'] is True
    assert len(read_lines(tmp_path/'decisions.jsonl'))==30
    assert (tmp_path/'predictions.json').exists()


def test_one_pass_marker_blocks_second_run_without_generation(tmp_path):
    backend=Backend(['not json']*30)
    runner().run_arm(rows(), backend, config(), tmp_path, arm='SHORT')
    before=(tmp_path/'generations.jsonl').read_bytes()
    with pytest.raises(FileExistsError):
        runner().run_arm(rows(), backend, config(), tmp_path, arm='SHORT')
    assert (tmp_path/'generations.jsonl').read_bytes()==before
    assert len(backend.calls)==30


@pytest.mark.parametrize('mutate',[lambda r:r.pop(), lambda r:r.append(r[0]),
    lambda r:r[0]['task'].update(reference='forbidden'),
    lambda r:r[0].update(kind='counterfactual'), lambda r:r[1].update(sample_id=r[0]['sample_id'])])
def test_rejects_partial_or_unsafe_inputs_before_marker(tmp_path,mutate):
    data=rows(); mutate(data)
    with pytest.raises(ValueError):
        runner().run_arm(data, Backend([]), config(), tmp_path, arm='SHORT')
    assert not (tmp_path/'started.json').exists()


@pytest.mark.parametrize('change',[{'adapter':'anything'}, {'do_sample':True}, {'diagnosis_max_tokens':2048}, {'few_shot_k':1}])
def test_rejects_unfrozen_generation_options_before_marker(tmp_path,change):
    with pytest.raises(ValueError):
        runner().run_arm(rows(), Backend([]), {**config(),**change}, tmp_path, arm='SHORT')
    assert not (tmp_path/'started.json').exists()


def test_r15_preserves_actual_input_and_raw_capture(tmp_path):
    output=json.dumps({'taxonomy_error':[],'feedback':'Em hãy đối chiếu bài làm với yêu cầu.'},ensure_ascii=False)
    backend=Backend([output]*30)
    result=runner().run_arm(rows(), backend, config(), tmp_path, arm='R15')
    assert len(result['predictions'])==30
    assert all(p['status']=='completed' for p in result['predictions'])
    payload=json.loads(backend.calls[0][0][1]['content'])
    assert payload['code']=='int main(){return 0;}'
    assert payload['statement']=='Artificial task: print zero. Domain: no input.'
    assert payload['compiler']=={'status':'pass','diagnostic':''}
    captures=read_lines(tmp_path/'generations.jsonl')
    assert len(captures)==30
    assert all(g['raw_text']==output and g['raw_sha256'] for g in captures)


def test_uncertain_diagnosis_still_gets_real_feedback_and_explicit_abstention(tmp_path):
    diagnosis='{"status":"uncertain","taxonomy_error":[],"findings":[]}'
    feedback='{"feedback":"Chưa đủ căn cứ để kết luận."}'
    backend=Backend([text for _ in range(30) for text in (diagnosis,feedback)])
    result=runner().run_arm(rows(), backend, config(), tmp_path, arm='SHORT')
    assert len(backend.calls)==60
    assert all(p['status']=='abstained' and p['diagnosis_status']=='uncertain' for p in result['predictions'])
    assert all(p['output']=={'taxonomy_error':[],'feedback':'Chưa đủ căn cứ để kết luận.'} for p in result['predictions'])
    status=json.loads((tmp_path/'status.json').read_text())
    assert status['feedback_available']==30
    assert status['completed']==0
    assert status['abstained']==30
    decisions=read_lines(tmp_path/'decisions.jsonl')
    assert all(d['machine_audit']['accepted'] and d['machine_audit']['semantic_correctness']=='unverified' for d in decisions)
    assert all(c[1]['max_new_tokens']==1536 for c in backend.calls[::2])
    assert backend.calls[7][1]['max_new_tokens']==1536
    assert backend.calls[1][1]['max_new_tokens']==1024


def test_defective_taxonomy_copied_from_diagnosis_and_raw_written_before_parser(tmp_path,monkeypatch):
    from src.task3 import diagnosis_contract_v1 as protocol
    original=protocol.parse_diagnosis
    def checked(raw, task):
        assert read_lines(tmp_path/'generations.jsonl')[-1]['raw_text']==raw
        return original(raw, task)
    monkeypatch.setattr(protocol,'parse_diagnosis',checked)
    diagnosis=json.dumps({'status':'defective','taxonomy_error':['Lỗi nhập/xuất'], 'findings':[
        {'label':'Lỗi nhập/xuất','quote':'return 0;','location':'main','cause_vi':'Không ghi kết quả.'}]},ensure_ascii=False)
    backend=Backend([text for _ in range(30) for text in (diagnosis,'{"feedback":"Phản hồi thật."}')])
    result=runner().run_arm(rows(),backend,config(),tmp_path,arm='SHORT')
    assert all(p['status']=='completed' and p['output']['taxonomy_error']==['Lỗi nhập/xuất'] for p in result['predictions'])


def test_runtime_failures_keep_full_thirty_source_accounting(tmp_path):
    backend=Backend([RuntimeError('synthetic failure')]*30)
    result=runner().run_arm(rows(),backend,config(),tmp_path,arm='SHORT')
    assert len(result['predictions'])==30
    assert all(p['status']=='runtime_error' for p in result['predictions'])
    assert len(read_lines(tmp_path/'generations.jsonl'))==30


def test_no_start_flag_has_no_preparation_or_model_side_effects(monkeypatch):
    module=runner()
    monkeypatch.setattr(module,'load_backend',lambda *a,**k:pytest.fail('model loaded'))
    with pytest.raises(SystemExit):
        module.main(['--arm','SHORT'])


def test_r15_uses_native_thirty_record_controller_in_one_call(tmp_path,monkeypatch):
    from src.task3 import round15_runner
    original=round15_runner.run_records
    seen=[]
    def observe(records,*args,**kwargs):
        seen.append(len(records))
        return original(records,*args,**kwargs)
    monkeypatch.setattr(round15_runner,'run_records',observe)
    output='{"taxonomy_error":[],"feedback":"Em hãy đối chiếu bài làm."}'
    runner().run_arm(rows(),Backend([output]*30),config(),tmp_path,arm='R15')
    assert seen==[30]
    captures=read_lines(tmp_path/'generations.jsonl')
    assert [c['generation_index'] for c in captures]==list(range(1,31))
    native=read_lines(tmp_path/'legacy'/'attempts.jsonl')
    assert len(native)==len(captures)
    assert all(a['raw_text']==b['raw_text'] and a['prompt_sha256']==b['legacy_prompt_sha256'] for a,b in zip(native,captures))


def test_loaded_adapter_flag_is_rejected_before_generation():
    # A model can retain PEFT's loaded-adapter flag without a visible wrapper.
    model=SimpleNamespace(_hf_peft_config_loaded=True, peft_config=None)
    with pytest.raises(RuntimeError,match='PEFT'):
        runner().assert_base_only(model)


def test_base_model_adapter_audit_accepts_plain_modules():
    model=SimpleNamespace(modules=lambda:iter([object()]), _hf_peft_config_loaded=False)
    runner().assert_base_only(model)
