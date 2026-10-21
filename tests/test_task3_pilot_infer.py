"""Artificial-only runner tests; no frozen sources or model loading."""
import json
from types import SimpleNamespace

import pytest

from src.task3.inference import Generation, MockTokenizer
from src.task3.pilot_training import _digest

PREPARED = {'version': 'artificial-pilot'}

def result_binding(frozen):
    return dict(config=frozen, config_sha256=_digest(frozen), manifest_sha256=_digest(PREPARED))


def task(code='int main(){return 0;}'):
    return dict(statement='Return zero.', problems=[], grading_policy='', student_code=code,
                compiler_evidence=dict(status='pass', diagnostic=''), allowed_labels=['Lỗi logic'])


def rows():
    return [dict(request_id='x-primary', sample_id='x', kind='primary', requested_level=3, task=task()),
            dict(request_id='x-cf', sample_id='x', kind='counterfactual', requested_level=1, task=task())]


def config():
    return dict(model_id='Qwen/Qwen2.5-Coder-7B-Instruct', revision='c03e6d358207e414f1eca0bb1891e29f1db0e242',
                seed=42, load_in_4bit=True, do_sample=False, context_limit=16384, diagnosis_max_tokens=2048,
                max_new_tokens=1024, level4_max_tokens=1536, max_time=60, max_attempts=3, prompt_variant='zero_shot')


def diagnosis():
    return dict(status='clean', taxonomy_error=[], findings=[], basis='No issue visible.', domain='C++11')


class Backend:
    tokenizer = MockTokenizer()

    def __init__(self, answers):
        self.answers = iter(answers)
        self.calls = []

    def generate(self, messages, cfg):
        self.calls.append((messages, cfg))
        answer = next(self.answers)
        if isinstance(answer, BaseException):
            raise answer
        return Generation(answer, 7, .001, 'eos', True)


@pytest.fixture
def protocol(monkeypatch):
    """Inject the parent-owned protocol API while it is developed independently."""
    import scripts.task3_pilot_infer as runner
    def parse_diagnosis(raw, value):
        parsed = json.loads(raw)
        if parsed.get('status') not in ('clean', 'defective', 'uncertain'):
            raise ValueError('diagnosis schema')
        return parsed
    def parse_feedback(raw, diagnostic):
        value = json.loads(raw)
        if not isinstance(value.get('feedback'), str):
            raise ValueError('feedback schema')
        return dict(taxonomy_error=list(diagnostic['taxonomy_error']), feedback=value['feedback'])
    value = SimpleNamespace(
        task_from_model_input=lambda value: value,
        diagnosis_messages=lambda value: [dict(role='user', content=json.dumps(value))],
        feedback_messages=lambda value, diagnostic, level: [dict(role='user', content=json.dumps(dict(task=value, diagnosis=diagnostic, requested_level=level)))],
        parse_diagnosis=parse_diagnosis, parse_feedback=parse_feedback)
    monkeypatch.setattr(runner, 'protocol', value)
    return runner


def test_one_diagnosis_for_primary_and_counterfactual_and_exact_taxonomy_copy(tmp_path, protocol):
    backend = Backend([json.dumps(diagnosis()), json.dumps(dict(feedback='Review requirements.', taxonomy_error=['invented'])),
                       json.dumps(dict(feedback='Try again.'))])
    result = protocol.run_arm(rows(), backend, config(), tmp_path, arm='B')
    assert len(backend.calls) == 3
    assert 'requested_level' not in backend.calls[0][0][0]['content']
    assert [row['request_id'] for row in result['predictions']] == ['x-primary', 'x-cf']
    assert all(row['output']['taxonomy_error'] == [] for row in result['predictions'])
    assert result['complete'] is True
    assert json.loads((tmp_path/'predictions.json').read_text()) == result['predictions']
    decisions = [json.loads(line) for line in (tmp_path/'decisions.jsonl').read_text().splitlines()]
    assert decisions[1]['diagnosis_cache_hit'] is True
    assert decisions[0]['diagnosis_key'] == decisions[1]['diagnosis_key']
    assert decisions[0]['feedback_key'] != decisions[1]['feedback_key']
    assert [call[1]['max_new_tokens'] for call in backend.calls] == [2048, 1024, 1024]


def test_failed_diagnosis_cached_once_and_never_converted_to_clean(tmp_path, protocol):
    backend = Backend(['not json'])
    result = protocol.run_arm(rows(), backend, config(), tmp_path, arm='C')
    assert len(backend.calls) == 1
    assert all(row['status'] == 'schema_error' and 'output' not in row for row in result['predictions'])
    assert len(result['predictions']) == 2
    decisions = [json.loads(line) for line in (tmp_path/'decisions.jsonl').read_text().splitlines()]
    assert decisions[1]['diagnosis_cache_hit'] is True
    assert all(row['diagnosis_raw'] == 'not json' for row in decisions)


def test_feedback_schema_failure_has_one_attempt_and_no_fallback(tmp_path, protocol):
    backend = Backend([json.dumps(diagnosis()), 'bad feedback', json.dumps(dict(feedback='Try again.'))])
    result = protocol.run_arm(rows(), backend, config(), tmp_path, arm='B')
    assert result['predictions'][0]['status'] == 'schema_error'
    assert 'output' not in result['predictions'][0]
    assert result['predictions'][1]['status'] == 'completed'
    assert len(backend.calls) == 3


def test_raw_capture_fsynced_before_parse(tmp_path, protocol, monkeypatch):
    original = protocol.protocol.parse_diagnosis
    def parse(raw, value):
        captured = [json.loads(line) for line in (tmp_path/'generations.jsonl').read_text().splitlines()]
        assert captured[-1]['raw_text'] == raw
        assert captured[-1]['prompt_sha256']
        assert captured[-1]['elapsed_s'] >= 0
        return original(raw, value)
    monkeypatch.setattr(protocol.protocol, 'parse_diagnosis', parse)
    protocol.run_arm(rows()[:1], Backend([json.dumps(diagnosis()), '{"feedback":"Review."}']), config(), tmp_path, arm='B')


def test_arm_started_marker_forbids_second_pass(tmp_path, protocol):
    protocol.run_arm(rows()[:1], Backend([json.dumps(diagnosis()), '{"feedback":"Review."}']), config(), tmp_path, arm='B')
    with pytest.raises(FileExistsError, match='started'):
        protocol.run_arm(rows(), Backend([]), config(), tmp_path, arm='B')


def test_interruption_keeps_snapshot_and_marks_incomplete(tmp_path, protocol):
    backend = Backend([json.dumps(diagnosis()), '{"feedback":"Review."}', KeyboardInterrupt()])
    with pytest.raises(KeyboardInterrupt):
        protocol.run_arm(rows(), backend, config(), tmp_path, arm='B')
    status = json.loads((tmp_path/'status.json').read_text())
    assert status['complete'] is False and status['processed_requests'] == 1
    assert not (tmp_path/'predictions.json').exists()
    assert len(json.loads((tmp_path/'predictions.partial.json').read_text())) == 1


def test_input_order_duplicates_metadata_and_full_task_binding(tmp_path, protocol):
    requests = [dict(request_id=r['request_id'], sample_id=r['sample_id'], level=r['requested_level'], kind=r['kind']) for r in rows()]
    with pytest.raises(ValueError, match='order'):
        protocol.run_arm(list(reversed(rows())), Backend([]), config(), tmp_path/'order', arm='B', expected_requests=requests)
    changed = rows(); changed[1]['task'] = task('different')
    with pytest.raises(ValueError, match='same source'):
        protocol.run_arm(changed, Backend([]), config(), tmp_path/'changed', arm='B')
    bad = rows(); bad[0]['task']['reference'] = {'labels': []}
    with pytest.raises(ValueError, match='model input'):
        protocol.run_arm(bad, Backend([]), config(), tmp_path/'unsafe', arm='B')


def test_oversize_full_source_errors_without_model_call_or_truncation(tmp_path, protocol):
    value = rows()[:1]; value[0]['task'] = task('x'*18000)
    backend = Backend([])
    result = protocol.run_arm(value, backend, config(), tmp_path, arm='B')
    assert not backend.calls
    assert result['predictions'][0]['status'] == 'unresolved'
    captured = [json.loads(line) for line in (tmp_path/'generations.jsonl').read_text().splitlines()]
    assert 'x'*18000 in captured[0]['prompt_messages'][0]['content']
    assert 'context' in captured[0]['error']


def test_a_preserves_frozen_round15_retries_and_level2_fallback(tmp_path, protocol):
    value = rows()[:1]; value[0]['requested_level'] = 2
    answer = json.dumps(dict(taxonomy_error=['Lỗi logic'], feedback='Hãy thay x bằng 0.'), ensure_ascii=False)
    result = protocol.run_arm(value, Backend([answer]*3), config(), tmp_path, arm='A')
    assert result['predictions'][0]['status'] == 'completed'
    assert result['predictions'][0]['output']['taxonomy_error'] == ['Lỗi logic']
    traces = json.loads((tmp_path/'legacy'/'traces.json').read_text())
    assert traces[0]['fallback_used'] is True


def test_config_is_locked_before_attempts(tmp_path, protocol):
    with pytest.raises(ValueError, match='locked'):
        protocol.run_arm(rows(), Backend([]), dict(config(), seed=1), tmp_path, arm='B')
    assert not (tmp_path/'started.json').exists()


def test_uncertain_valid_schema_is_cached_unresolved_not_empty_clean_output(tmp_path, protocol):
    value = diagnosis(); value['status'] = 'uncertain'
    backend = Backend([json.dumps(value)])
    result = protocol.run_arm(rows(), backend, config(), tmp_path, arm='B')
    assert len(backend.calls) == 1
    assert all(row['status'] == 'unresolved' and 'output' not in row for row in result['predictions'])
    decisions = [json.loads(line) for line in (tmp_path/'decisions.jsonl').read_text().splitlines()]
    assert decisions[0]['diagnosis_schema_valid'] is True
    assert decisions[0]['diagnosis_resolved'] is False
    status = json.loads((tmp_path/'status.json').read_text())
    assert status['diagnosis_schema_valid_sources'] == 1
    assert status['diagnosis_resolved_sources'] == 0


def test_normalize_frozen_inference_config_uses_parent_declared_key_names(protocol):
    frozen = dict(config())
    frozen['diagnosis_max_new_tokens'] = frozen.pop('diagnosis_max_tokens')
    frozen['generation_max_time_s'] = frozen.pop('max_time')
    frozen.pop('max_attempts'); frozen.pop('prompt_variant')
    got = protocol.normalize_inference_config(dict(model_id=config()['model_id'], revision=config()['revision'], inference=frozen))
    assert got['diagnosis_max_tokens'] == 2048 and got['max_time'] == 60
    assert got['prompt_variant'] == 'zero_shot' and got['max_attempts'] == 3
    with pytest.raises(ValueError, match='locked'):
        protocol.normalize_inference_config(dict(model_id=config()['model_id'], revision=config()['revision'], inference=dict(frozen, seed=0)))


def test_cli_missing_start_flag_never_verifies_or_loads(protocol, monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError('model loading forbidden')
    monkeypatch.setattr(protocol, 'load_backend', forbidden)
    with pytest.raises(SystemExit):
        protocol.main(['--arm', 'B'])


def test_prepared_cli_settings_require_complete_training_and_bind_frozen_config(tmp_path, protocol):
    frozen_inference = dict(config())
    frozen_inference['diagnosis_max_new_tokens'] = frozen_inference.pop('diagnosis_max_tokens')
    frozen_inference['generation_max_time_s'] = frozen_inference.pop('max_time')
    frozen = dict(model_id=config()['model_id'], revision=config()['revision'], inference=frozen_inference, work_dir=str(tmp_path))
    with pytest.raises(ValueError, match='complete training'):
        protocol.prepared_settings(frozen, 'B', prepared_manifest=PREPARED)
    training = tmp_path/'training'; training.mkdir()
    (training/'training-result.json').write_text(json.dumps(dict(status='incomplete')))
    with pytest.raises(ValueError, match='complete training'):
        protocol.prepared_settings(frozen, 'B', prepared_manifest=PREPARED)
    (training/'training-result.json').write_text(json.dumps(dict(status='complete', selected_adapter_sha256='unbound', **result_binding(frozen))))
    with pytest.raises(ValueError, match='adapter'):
        protocol.prepared_settings(frozen, 'C', prepared_manifest=PREPARED)


def test_real_parent_protocol_roundtrip_and_no_added_feedback_labels(tmp_path, monkeypatch):
    import scripts.task3_pilot_infer as runner
    from src.task3 import pilot_protocol
    monkeypatch.setattr(runner, 'protocol', pilot_protocol)
    backend = Backend([json.dumps(diagnosis()), '{"feedback":"Em hãy đối chiếu bài với đề."}'])
    result = runner.run_arm(rows()[:1], backend, config(), tmp_path, arm='B')
    assert result['predictions'][0]['status'] == 'completed'
    assert result['predictions'][0]['output']['taxonomy_error'] == []


def test_generation_journal_keeps_raw_hash_and_effective_stage_cap(tmp_path, protocol):
    value = rows()[:1]; value[0]['requested_level'] = 4
    raw = json.dumps(diagnosis())
    protocol.run_arm(value, Backend([raw, '{"feedback":"Review."}']), config(), tmp_path, arm='B')
    import hashlib
    captured = [json.loads(line) for line in (tmp_path/'generations.jsonl').read_text().splitlines()]
    assert captured[0]['raw_sha256'] == hashlib.sha256(raw.encode()).hexdigest()
    assert captured[0]['generation_config']['max_new_tokens'] == 2048
    assert captured[1]['generation_config']['max_new_tokens'] == 1536


def test_prepared_settings_verify_all_adapter_files_for_base_arm_as_well(tmp_path, protocol):
    import hashlib
    frozen_inference = dict(config())
    frozen_inference['diagnosis_max_new_tokens'] = frozen_inference.pop('diagnosis_max_tokens')
    frozen_inference['generation_max_time_s'] = frozen_inference.pop('max_time')
    frozen = dict(model_id=config()['model_id'], revision=config()['revision'], inference=frozen_inference, work_dir=str(tmp_path))
    adapter = tmp_path/'training'/'adapter'; adapter.mkdir(parents=True)
    (adapter/'adapter_model.safetensors').write_bytes(b'artificial tensor')
    (adapter/'adapter_config.json').write_text('{}')
    hashes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in adapter.iterdir()}
    (adapter.parent/'training-result.json').write_text(json.dumps(dict(status='complete', **result_binding(frozen),
        selected_adapter_sha256=hashes['adapter_model.safetensors'], selected_adapter_files_sha256=hashes)))
    settings, work, selected = protocol.prepared_settings(frozen, 'B', prepared_manifest=PREPARED)
    assert selected is None and work == tmp_path and settings['max_time'] == 60
    assert protocol.prepared_settings(frozen, 'C', prepared_manifest=PREPARED)[2] == adapter
    (adapter/'adapter_config.json').write_text('{"changed":true}')
    with pytest.raises(ValueError, match='file map'):
        protocol.prepared_settings(frozen, 'B', prepared_manifest=PREPARED)


def test_loader_attaches_adapter_after_base_audit_and_inspects_actual_quantized_modules(monkeypatch, protocol):
    import sys
    from types import ModuleType
    fake_torch = ModuleType('torch')
    fake_torch.bfloat16 = object()
    fake_torch.cuda = SimpleNamespace(is_bf16_supported=lambda: True)
    monkeypatch.setitem(sys.modules, 'torch', fake_torch)
    class Linear4bit:
        compute_dtype = fake_torch.bfloat16
    class Wrapper:
        @property
        def compute_dtype(self):
            raise AssertionError('PEFT wrapper compute_dtype must never be inspected')
    Wrapper.__name__ = 'Linear4bit'
    bnb_nn = ModuleType('bitsandbytes.nn'); bnb_nn.Linear4bit = Linear4bit
    monkeypatch.setitem(sys.modules, 'bitsandbytes.nn', bnb_nn)
    model = SimpleNamespace(generation_config=SimpleNamespace(max_time=None),
                            modules=lambda: iter([Wrapper(), Linear4bit()]), eval=lambda: None)
    backend = SimpleNamespace(model=model, precision_audit={})
    seen = []
    monkeypatch.setattr(protocol, 'HFBackend', lambda cfg: seen.append(cfg) or backend)
    peft = ModuleType('peft')
    peft.PeftModel = SimpleNamespace(from_pretrained=lambda base, path, is_trainable: base)
    monkeypatch.setitem(sys.modules, 'peft', peft)
    got = protocol.load_backend(dict(config(), adapter='must-be-stripped'), adapter='selected')
    assert 'adapter' not in seen[0]
    assert got.model.generation_config.max_time == 60
    assert got.precision_audit['pilot_quantized_compute_dtypes']


def test_cli_full_manifest_order_and_global_one_pass_guard_with_fake_backend(tmp_path, protocol, monkeypatch):
    import hashlib
    import sys
    from types import ModuleType
    inputs = []
    for index in range(96):
        inputs.append(dict(request_id=f'artificial-{index}', sample_id=f'source-{index%60}',
            kind='primary' if index<60 else 'counterfactual', requested_level=1, task=task()))
    private = tmp_path/'safe'; private.mkdir()
    path = private/'model-inputs.private.json'; path.write_text(json.dumps(inputs))
    requests = [dict(request_id=r['request_id'], sample_id=r['sample_id'], kind=r['kind'], level=r['requested_level']) for r in inputs]
    manifest = dict(private_root=str(private), requests=requests,
                    private_files_sha256={'model-inputs.private.json': hashlib.sha256(path.read_bytes()).hexdigest()})
    frozen = dict(eval_inputs=str(path))
    prepare = ModuleType('scripts.task3_pilot_prepare')
    prepare.verify_pilot = lambda: ({}, frozen, [], [], [], {})
    monkeypatch.setitem(sys.modules, 'scripts.task3_pilot_prepare', prepare)
    freezer = ModuleType('scripts.task3_freeze_eval_v2'); freezer.verify = lambda: manifest
    monkeypatch.setitem(sys.modules, 'scripts.task3_freeze_eval_v2', freezer)
    monkeypatch.setattr(protocol, 'prepared_settings', lambda *a, **k: (config(), tmp_path, None))
    calls = []
    def load(cfg, **kwargs):
        assert (tmp_path/'inference'/'arm-B'/'started.json').exists()
        calls.append(cfg)
        return SimpleNamespace(runtime_metadata=lambda: {})
    monkeypatch.setattr(protocol, 'load_backend', load)
    def run(values, backend, cfg, output, **kwargs):
        assert values == inputs and kwargs['expected_requests'] == requests
        return dict(complete=True, predictions=[dict(request_id=r['request_id'], status='unresolved') for r in values])
    monkeypatch.setattr(protocol, 'run_arm', run)
    protocol.main(['--arm', 'B', '--start'])
    with pytest.raises(FileExistsError):
        protocol.main(['--arm', 'B', '--start', '--output', str(tmp_path/'alternate')])
    assert len(calls) == 1


@pytest.mark.parametrize('answers,expected', [
    ([json.dumps(diagnosis()), '{"feedback":"Review."}'], 'completed'),
    (['not JSON'], 'schema_error'),
    ([RuntimeError('CUDA failure')], 'runtime_error'),
    ([json.dumps(dict(diagnosis(), status='uncertain'))], 'unresolved'),
])
def test_predictions_use_frozen_evaluator_status_contract(tmp_path, protocol, answers, expected):
    from src.task3.frozen_eval import _output, _STATUSES
    result = protocol.run_arm(rows()[:1], Backend(answers), config(), tmp_path, arm='B')
    prediction = result['predictions'][0]
    assert prediction['status'] == expected and expected in _STATUSES
    assert (_output(prediction) is not None) is (expected == 'completed')
    status = json.loads((tmp_path/'status.json').read_text())
    assert status['unresolved'] == (expected != 'completed')
    assert status['statuses'][expected] == 1


@pytest.mark.parametrize('stale', ['config_sha256', 'manifest_sha256', 'config'])
def test_prepared_settings_rejects_stale_training_binding_before_adapter_reads(tmp_path, protocol, stale):
    inference = dict(config())
    inference['diagnosis_max_new_tokens'] = inference.pop('diagnosis_max_tokens')
    inference['generation_max_time_s'] = inference.pop('max_time')
    frozen = dict(model_id=config()['model_id'], revision=config()['revision'], inference=inference, work_dir=str(tmp_path))
    training = tmp_path/'training'; training.mkdir()
    result = dict(status='complete', **result_binding(frozen))
    result[stale] = {'model_id':'different'} if stale=='config' else 'stale'
    (training/'training-result.json').write_text(json.dumps(result))
    with pytest.raises(ValueError, match='training (config|manifest) binding'):
        protocol.prepared_settings(frozen, 'B', prepared_manifest=PREPARED)
