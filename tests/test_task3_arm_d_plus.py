"""Synthetic regression fixtures only; never special-case public samples."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unicodedata

import pytest

from src.task3 import arm_d_plus as plus
from src.task3.dataset import load_task3, write_json
from src.task3.inference import Generation, MockTokenizer
from src.synth.taxonomy import LABEL_SPACE
from src.synth.feedback import FEEDBACK_LEVELS

LABELS = list(LABEL_SPACE)
SPACE = {'taxonomy_error': LABELS, 'feedback_level': [
    {'level': name, 'định nghĩa': 'Quy định mức phản hồi.', 'cấm': 'Giới hạn của mức.'}
    for name in FEEDBACK_LEVELS]}


def finding(label='Lỗi vòng lặp', **fields):
    return dict(problem_id='P1', location='while (i < n)', evidence='i += 0;',
                error='The traversal does not progress for n > 0.', label=label, **fields)


def unit():
    return {'sample_id': 'fixture', 'level': 2, 'task': {
        'statement': 'Read n; visit each element.', 'exam_type': 'single_problem',
        'problems': [{'pid': 'P1', 'constraints': '1 <= n <= 20.', 'io_mode': 'stdin/stdout'}],
        'code': 'int main() { int i=0; i += 0; }',
        'compiler': {'status': 'unavailable', 'diagnostic': ''},
        'tests': {'status': 'not_run', 'cases': []}}}


def config():
    return {'model_id': 'fixture-model', 'revision': 'fixture-revision', 'load_in_4bit': False,
            'seed': 42, 'do_sample': False, 'max_new_tokens': 1024,
            'findings_max_new_tokens': 1536, 'context_limit': 30000,
            'generation_max_time_s': 45, 'version': 'fixture-arm-d-plus'}


class Backend:
    tokenizer = MockTokenizer()
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.resolver_messages = []
    def generate(self, messages, cfg):
        self.calls.append(copy.deepcopy(messages))
        value = next(self.responses)
        if isinstance(value, Exception):
            raise value
        return Generation(value, 15, .1, 'eos', True)
    def choose(self, messages, labels):
        self.resolver_messages.append(messages)
        # Fixture chooses from finding content, not the ambiguous name.
        content = json.loads(messages[-1]['content'])['finding']['error']
        index = 4 if 'array' in content else 3
        return {'code': chr(65 + index), 'label': labels[index], 'scores': [0.] * 10,
                'token_ids': list(range(10)), 'finish_reason': 'constrained_choice',
                'status': 'selected', 'forward_passes': 1, 'latency_s': .01}


@pytest.mark.parametrize('label,canonical,method', [
    ('Lỗi vòng lặp', 'Lỗi vòng lặp', 'exact'),
    ('  Lỗi\u00a0vòng   lặp\n', 'Lỗi vòng lặp', 'normalized'),
    (unicodedata.normalize('NFD', 'Lỗi biên dịch'), 'Lỗi biên dịch', 'normalized'),
    ('syntax error', 'Lỗi biên dịch', 'alias'),
    (' compilation error ', 'Lỗi biên dịch', 'alias'),
    ('I/O error', 'Lỗi nhập/xuất', 'alias'),
    ('input-output error', 'Lỗi nhập/xuất', 'alias'),
    ('loop error', 'Lỗi vòng lặp', 'alias'),
    ('infinite loop', 'Lỗi vòng lặp', 'alias'),
    ('hardcoded value', 'Lỗi hard-code', 'alias'),
    ('hard-coding', 'Lỗi hard-code', 'alias'),
])
def test_label_mapping_preserves_finding_fields(label, canonical, method):
    original = finding(label)
    def forbidden(*args):
        pytest.fail('valid/alias label must not call model')
    mapped, audit = plus.normalize_findings([original], LABELS, forbidden, 'fixture')
    assert mapped == [{**{k: v for k, v in original.items() if k != 'label'}, 'labels': [canonical]}]
    assert original == finding(label)
    assert audit[0]['mapping_method'] == method
    assert audit[0]['original_label'] == label
    assert audit[0]['canonical_labels'] == [canonical]


def test_ambiguous_labels_use_finding_context_and_preserve_other_findings():
    originals = [finding(), finding('runtime error'),
                 {**finding('runtime error'), 'error': 'The array is indexed beyond its allocated bound.'}]
    seen = []
    def resolve(f, label, fi, li):
        seen.append((f, label, fi, li))
        return {'label': LABELS[4 if 'array' in f['error'] else 3], 'code': 'E', 'scores': [0.] * 10}
    mapped, audit = plus.normalize_findings(originals, LABELS, resolve, 'fixture')
    assert [f['labels'] for f in mapped] == [[LABELS[3]], [LABELS[3]], [LABELS[4]]]
    assert len(seen) == 2
    assert all(f['error'] == originals[i]['error'] for i, f in enumerate(mapped))
    assert [a['mapping_method'] for a in audit] == ['exact', 'constrained_choice', 'constrained_choice']


def test_multilabel_legacy_adapter_and_ordered_union():
    raw = {'findings': [finding(), {**{k:v for k,v in finding().items() if k!='label'},
                                  'labels': [LABELS[6], LABELS[3], LABELS[6]]}]}
    parsed = plus.parse_findings(json.dumps(raw))
    normalized, _ = plus.normalize_findings(parsed, LABELS, None, 'fixture')
    assert len(normalized) == 2
    assert normalized[1]['labels'] == [LABELS[3], LABELS[6]]
    assert plus.taxonomy(normalized, LABELS) == [LABELS[3], LABELS[6]]
    assert plus.parse_findings('{"findings": []}') == []
    assert plus.normalize_findings([], LABELS, None, 'fixture') == ([], [])
    assert plus.taxonomy([], LABELS) == []


def test_classifier_result_must_be_official():
    with pytest.raises(ValueError, match='official'):
        plus.normalize_findings([finding('overflow')], LABELS, lambda *a: {'label': 'unknown'}, 'fixture')


@pytest.mark.parametrize('bad', [[], [''], [5], 'Lỗi logic'])
def test_real_finding_requires_nonempty_label_list(bad):
    f = {k:v for k,v in finding().items() if k!='label'}
    f['labels'] = bad
    with pytest.raises(ValueError):
        plus.parse_findings(json.dumps({'findings':[f]}))


def dataset_fixture(tmp_path):
    root = tmp_path/'data';root.mkdir()
    write_json(root/'label_space.json', SPACE)
    write_json(root/'exams.json', {'exams':[{
        'exam_id':'exam-fixture', 'exam_type':'single_problem', 'statement':'Read n.', 'language':'cpp11',
        'problems':[{'pid':'P1', 'constraints':{'domain':'1 <= n <= 20.', 'taxonomy_error':['LEAK']},
                     'io_mode':'stdin/stdout', 'prototype':'int f(int n)', 'feedback':'LEAK'}],
        'grading_policy':{'prerequisites':{'P1':['P0']}, 'rubric':'LEAK'},
        'constraints':['positive n'], 'forbidden_functions':['pow'], 'feedback':'LEAK'}]})
    (root/'answer.cpp').write_text('int main() {}\n')
    write_json(root/'task3_feedback.json', {'n_samples':1, 'output_fields':['taxonomy_error','feedback'],
        'samples':[{'sample_id':'fixture-L99', 'input':{'exam_id':'exam-fixture','code_file':'answer.cpp',
            'language':'cpp11','compile_log':'','test_report':None,'target_feedback_level':FEEDBACK_LEVELS[1]}}]})
    write_json(root/'task3_requested_levels.json', {'fixture-L99':FEEDBACK_LEVELS[1]})
    return root


def test_loader_to_rendered_prompt_preserves_constraints_io_language_and_evidence(tmp_path):
    record = load_task3(dataset_fixture(tmp_path), 'public')[0]
    u = plus.record_unit(record)
    messages = plus.messages_findings(u, LABELS)
    rendered = MockTokenizer().apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    body = json.loads(messages[1]['content'])
    assert body['problems'][0]['constraints'] == {'domain':'1 <= n <= 20.'}
    assert body['problems'][0]['io_mode'] == 'stdin/stdout'
    assert body['language'] == 'cpp11'
    assert body['exam_metadata']['forbidden_functions'] == ['pow']
    assert body['grading_policy'] == {'prerequisites':{'P1':['P0']}}
    assert body['compile_log'] == ''
    assert body['compiler']['status'] == 'unavailable'
    assert body['tests']['status'] == 'not_run'
    assert 'LEAK' not in rendered
    assert 'target_feedback_level' not in body and 'requested_level' not in body
    assert u['level'] == 2  # input Level, never the misleading ID suffix
    assert u['task']['code'] == 'int main() {}\n'


def test_feedback_receives_only_own_findings_and_official_requested_level():
    normalized, _ = plus.normalize_findings([finding()], LABELS, None, 'fixture')
    body = json.loads(plus.messages_feedback(unit(), normalized, LABELS, SPACE['feedback_level'])[1]['content'])
    assert body['findings'] == normalized
    assert body['taxonomy_error'] == [LABELS[3]]
    assert body['requested_level'] == 2
    assert body['level_rule'] == SPACE['feedback_level'][1]


def test_unknown_label_runs_resolver_without_eos_requirement(tmp_path):
    backend = Backend([json.dumps({'findings':[finding('runtime error')]}), '{"feedback":"Vòng lặp không tiến triển."}'])
    rows = plus.run_units([unit()], backend, config(), tmp_path, SPACE)
    assert rows[0]['status'] == 'resolved'
    assert rows[0]['output']['taxonomy_error'] == [LABELS[3]]
    attempts = [json.loads(line) for line in (tmp_path/'attempts.jsonl').read_text().splitlines()]
    assert [r['kind'] for r in attempts] == ['normal','resolver','normal']
    assert attempts[1]['finish_reason'] == 'constrained_choice'
    assert attempts[1]['forward_passes'] == 1
    assert len(backend.calls) == 2
    assert json.loads((tmp_path/'label-mapping-audit.jsonl').read_text())['mapping_method'] == 'constrained_choice'


def test_one_schema_retry_each_stage_and_feedback_never_reruns_detector(tmp_path):
    backend = Backend(['not json', json.dumps({'findings':[finding()]}), '{"wrong":"x"}',
                       '{"feedback":"Điều kiện lặp khiến chỉ số không tiến triển."}'])
    rows = plus.run_units([unit()], backend, config(), tmp_path, SPACE)
    assert rows[0]['status'] == 'resolved'
    assert len(backend.calls) == 4
    attempts = [json.loads(x) for x in (tmp_path/'attempts.jsonl').read_text().splitlines()]
    assert [(r['stage'],r['attempt'],r['kind']) for r in attempts] == [
        ('taxonomy',0,'normal'),('taxonomy',1,'repair'),('feedback',0,'normal'),('feedback',1,'repair')]
    first = json.loads(backend.calls[2][1]['content'])['findings']
    retry = json.loads(backend.calls[3][1]['content'])['findings']
    assert first == retry
    assert 'failure' in backend.calls[3][-1]['content'].lower()


def test_unrepaired_schema_failure_continues_other_samples_without_fake_output(tmp_path):
    second = unit();second['sample_id']='fixture-2'
    backend=Backend(['bad','still bad','{"findings":[]}', '{"feedback":"Chưa phát hiện lỗi có căn cứ từ phần mã đã xem."}'])
    rows=plus.run_units([unit(),second],backend,config(),tmp_path,SPACE)
    assert [r['status'] for r in rows] == ['unresolved','resolved']
    assert rows[0]['output'] is None
    assert not (tmp_path/'predictions.json').exists()
    assert len(json.loads((tmp_path/'partial.predictions.json').read_text())) == 1


def test_resolver_backend_failure_is_infrastructure_not_enum(tmp_path):
    backend=Backend([json.dumps({'findings':[finding('memory error')]})])
    def broken(*a): raise RuntimeError('CUDA out of memory')
    backend.choose=broken
    rows=plus.run_units([unit()],backend,config(),tmp_path,SPACE)
    assert rows[0]['status']=='unresolved'
    assert rows[0]['failure']['category']=='infrastructure'
    assert 'CUDA out of memory' in rows[0]['failure']['reason']
    assert len(backend.calls)==1


def test_resume_skips_completed_only_and_rejects_config_input_or_policy_drift(tmp_path, monkeypatch):
    b=Backend(['{"findings":[]}','{"feedback":"Chưa thấy vấn đề có căn cứ trong phần đã xem."}'])
    plus.run_units([unit()],b,config(),tmp_path,SPACE)
    resumed=Backend([])
    rows=plus.run_units([unit()],resumed,config(),tmp_path,SPACE)
    assert rows[0]['status']=='resolved' and not resumed.calls
    for changed in ({**config(),'max_new_tokens':1000},{**config(),'revision':'changed'}):
        with pytest.raises(ValueError,match='identity'):
            plus.run_units([unit()],Backend([]),changed,tmp_path,SPACE)
    changed=unit();changed['task']['code']+=' // changed'
    with pytest.raises(ValueError,match='identity'):
        plus.run_units([changed],Backend([]),config(),tmp_path,SPACE)
    monkeypatch.setattr(plus,'MAPPING_VERSION','changed')
    with pytest.raises(ValueError,match='identity'):
        plus.run_units([unit()],Backend([]),config(),tmp_path,SPACE)


def test_preflight_counts_input_plus_output_and_never_truncates(tmp_path):
    b=Backend([])
    cfg={**config(),'context_limit':1536}
    rows=plus.run_units([unit()],b,cfg,tmp_path,SPACE)
    assert rows[0]['status']=='unresolved'
    assert rows[0]['failure']['category']=='context'
    assert not b.calls


def test_real_constrained_logits_excludes_invalid_tokens_and_ties_by_enum_order():
    import torch
    class Tokenizer(MockTokenizer):
        def encode(self,text,**kw): return [30+ord(text)-65]
        def apply_chat_template(self,*args,**kwargs):
            class Inputs(dict):
                def to(self,device): return self
            return Inputs(input_ids=torch.tensor([[1,2,3]]), attention_mask=torch.tensor([[1,1,1]]))
    class Model:
        device='cpu'
        def __call__(self, **kw):
            assert kw['logits_to_keep']==1 and kw['use_cache'] is False
            logits=torch.full((1,1,100),-20.)
            logits[0,0,0]=1000.  # invalid code must never win
            logits[0,0,34]=10.;logits[0,0,35]=10.
            return SimpleNamespace(logits=logits)
    backend=SimpleNamespace(torch=torch,tokenizer=Tokenizer(),model=Model())
    result=plus.constrained_choice(backend,[{'role':'user','content':'classify finding'}],LABELS)
    assert result['label']==LABELS[4] and result['code']=='E'
    assert result['finish_reason']=='constrained_choice'
    assert result['token_ids']==list(range(30,40))
    assert result['forward_passes']==1


def test_loader_preserves_function_only_and_syntax_only_compiler_note(tmp_path):
    root=dataset_fixture(tmp_path)
    payload=json.loads((root/'exams.json').read_text())
    note='Functions only; no main required. compile_log generated with g++ -std=c++11 -fsyntax-only.'
    payload['exams'][0]['note']=note
    write_json(root/'exams.json',payload)
    u=plus.record_unit(load_task3(root,'public')[0])
    body=json.loads(plus.messages_findings(u,LABELS)[1]['content'])
    assert body['exam_metadata']['note']==note


def test_test_report_preserves_actual_output_but_excludes_teacher_annotations():
    u=unit()
    u['task']['test_report']={'status':'failed','cases':[{'input':'3','output':'False',
                                'expected':'True','feedback':'DO NOT INCLUDE'}]}
    body=plus.task_payload(u)
    assert body['test_report']['cases']==[{'input':'3','output':'False','expected':'True'}]


def test_generation_timeout_is_infrastructure_without_json_retry(tmp_path):
    backend=Backend([])
    def timed_out(*a): return Generation('{',3,45.1,'timeout',False)
    backend.generate=timed_out
    rows=plus.run_units([unit()],backend,config(),tmp_path,SPACE)
    assert rows[0]['failure']['category']=='infrastructure'
    assert 'timeout' in rows[0]['failure']['reason']
    attempts=(tmp_path/'attempts.jsonl').read_text().splitlines()
    assert len(attempts)==1 and json.loads(attempts[0])['finish_reason']=='timeout'


def test_full_compile_log_has_one_lossless_payload_location():
    u=unit();log='compiler.cpp:7: error: invalid operands\n'*400
    u['task']['compile_log']=log
    u['task']['compiler']={'status':'provided_log','diagnostic':log}
    body=plus.task_payload(u)
    assert body['compile_log']==log
    assert body['compiler']=={'status':'provided_log','diagnostic_source':'compile_log'}
    assert u['task']['compiler']['diagnostic']==log


def test_native_extended_context_preserves_long_evidence_and_full_source():
    from scripts.task3_arm_d_plus import preflight
    u=unit();log='compiler error detail\n'*800
    u['task']['compile_log']=log
    u['task']['compiler']={'status':'provided_log','diagnostic':log}
    cfg={**config(),'context_limit':32768}
    result=preflight([u],MockTokenizer(),cfg,SPACE)
    assert result['records']==1
    assert result['max_detector_input']+1536<=32768
    payload=json.loads(plus.messages_findings(u,LABELS)[1]['content'])
    assert payload['compile_log']==log and payload['code']==u['task']['code']
