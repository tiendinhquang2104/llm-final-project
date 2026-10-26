"""Pure public-run integrity tests; no model, compiler or network calls."""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from src.synth.feedback import FEEDBACK_LEVELS
from src.synth.taxonomy import LABEL_SPACE
from src.task3.sft_v2_public import (map_input,fixed_review_slice,context_preflight,PublicJournal,export_submission)


def record(**changes):
    values=dict(sample_id='secret-ID',statement='Original statement\n',code='int main(){return 0;}\n',
        requested_level=FEEDBACK_LEVELS[1],exam_type='multi_problem',compile_log=None,
        problems=[{'pid':'P1','statement':'First requirement','prototype':'int first();','gold_feedback':'SECRET'},
                  {'pid':'P2','statement':'Second requirement','prototype':'int second();','prerequisites':['P1']}],
        grading_policy={'description':'exact-byte output comparison','prerequisites':{'P2':['P1']},'feedback':'SECRET'},
        exam_metadata={'restrictions':['No sort'],'gold_taxonomy':['SECRET']},input_metadata={'note':'Functions only'},
        gold_taxonomy=['SECRET'],gold_feedback='SECRET')
    values.update(changes);return SimpleNamespace(**values)


def result(sid,raw=None,**changes):
    r=dict(sample_id=sid,level=1,raw=raw if raw is not None else json.dumps({'taxonomy_error':[],'feedback':'Bài làm đúng.'},ensure_ascii=False),finish_reason='eos')
    r.update(changes);return r


class PublicTests(unittest.TestCase):
    def test_map_preserves_scope_prototypes_prerequisite_and_excludes_gold_ids(self):
        r=record();x=map_input(r,{'status':'passed','stdout':'','stderr':''})
        self.assertEqual(set(x),{'statement','exam_type','language','code','compile_log','target_feedback_level'})
        self.assertTrue(x['statement'].startswith(r.statement));self.assertEqual(x['code'],r.code)
        for text in ['int first();','int second();','P1','P2','exact-byte','No sort','Functions only']:self.assertIn(text,x['statement'])
        self.assertNotIn('SECRET',json.dumps(x));self.assertNotIn('secret-ID',json.dumps(x))
        self.assertEqual(x['language'],'cpp11');self.assertEqual(x['target_feedback_level'],2)
        self.assertEqual(x['compile_log'],'')

    def test_log_attribution_preserves_supplied_bytes_and_local_failure(self):
        supplied='dataset log\r\n  untouched\n';x=map_input(record(compile_log=supplied),{'status':'syntax_error','stdout':'local stdout','stderr':'local stderr'})
        self.assertIn(supplied,x['compile_log']);self.assertIn('local stdout',x['compile_log']);self.assertIn('local stderr',x['compile_log'])
        self.assertIn('supplied',x['compile_log'].lower());self.assertIn('local',x['compile_log'].lower())
        self.assertIn('syntax_error',x['compile_log'])

    def test_requested_level_authoritative_fallback_and_policy_string(self):
        r=record(grading_policy='Preserve every output byte',requested_level=FEEDBACK_LEVELS[2],target_feedback_level=FEEDBACK_LEVELS[0])
        x=map_input(r,{'status':'passed','stdout':'','stderr':''});self.assertEqual(x['target_feedback_level'],3)
        self.assertIn('Preserve every output byte',x['statement'])
        del r.requested_level;r.target_feedback_level=FEEDBACK_LEVELS[1]
        self.assertEqual(map_input(r,{'status':'passed','stdout':'','stderr':''})['target_feedback_level'],2)
        r.target_feedback_level='Level 2';self.assertRaises(ValueError,map_input,r,{})

    def test_slice_deterministic_stratified36_and_ignores_outputs(self):
        rows=[dict(sample_id=f'{l}-{i}',level=l,exam_id='F'+str(i%4),output='ignored') for l in (1,2,3) for i in range(20)]
        chosen=fixed_review_slice(rows);self.assertEqual(len(chosen),36)
        self.assertEqual({l:sum(x['level']==l for x in chosen) for l in (1,2,3)},{1:12,2:12,3:12})
        again=fixed_review_slice(list(reversed(rows)))
        self.assertEqual([x['sample_id'] for x in chosen],[x['sample_id'] for x in again])
        self.assertEqual(len({x['exam_id'] for x in chosen[:12]}),4)
        self.assertRaises(ValueError,fixed_review_slice,rows+[rows[0]])

    def test_context_uses_real_template_no_truncation_and_exact_boundary(self):
        class Tokenizer:
            def apply_chat_template(self,prompt,**kwargs):
                self.kwargs=kwargs;return list(range(prompt[0]['n']))
        tokenizer=Tokenizer();prompt=[{'n':7168}];settings={'max_new_tokens':{'1':1024,'2':1024}}
        rows=context_preflight(tokenizer,[{'sample_id':'x','level':1,'prompt':prompt},{'sample_id':'y','level':2,'prompt':[{'n':7169}]}],settings)
        self.assertEqual(rows[0]['status'],'evaluable');self.assertEqual(rows[0]['total_tokens'],8192)
        self.assertEqual(rows[1]['status'],'context_preflight_failure')
        self.assertEqual(tokenizer.kwargs,{'tokenize':True,'add_generation_prompt':True})
        self.assertEqual(rows[0]['prompt_sha256'],hashlib.sha256(json.dumps(prompt,ensure_ascii=False,sort_keys=True).encode()).hexdigest())

    def test_journal_resume_single_attempt_and_prompt_binding(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'journal.jsonl';allowed={'x':'a'*64,'y':'b'*64};j=PublicJournal(p,allowed)
            j.reserve('x',9999);self.assertEqual(j.events()[0]['prompt_sha256'],'a'*64)
            self.assertRaises(ValueError,j.reserve,'x',9999);self.assertRaises(ValueError,j.reserve,'alien',9999)
            j=PublicJournal(p,allowed);self.assertRaises(ValueError,j.reserve,'x',9999)
            j.append({'type':'generation_completed','key':'x','result':result('x')})
            self.assertRaises(ValueError,j.append,{'type':'generation_completed','key':'x','result':result('x')})
            self.assertRaises(ValueError,PublicJournal,p,{'x':'c'*64,'y':'b'*64})

    def test_journal_refuses_corrupt_completion_or_reservation(self):
        cases=[ [{'type':'generation_completed','key':'x'}],
                [{'type':'generation_reserved','key':'alien','prompt_sha256':'a'*64}],
                [{'type':'generation_reserved','key':'x','prompt_sha256':'a'*64}]*2 ]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'j'
            for events in cases:
                p.write_text('\n'.join(json.dumps(e) for e in events)+'\n')
                self.assertRaises(ValueError,PublicJournal,p,{'x':'a'*64})
            p.write_text('{interrupted json');self.assertRaises(ValueError,PublicJournal,p,{'x':'a'*64})

    def test_complete_export_actual_bytes_order_and_official_wrapper(self):
        with tempfile.TemporaryDirectory() as d:
            requested={'b':FEEDBACK_LEVELS[0],'a':FEEDBACK_LEVELS[0]}
            v=export_submission(Path(d),requested,[result('a'),result('b')],list(LABEL_SPACE))
            p=Path(d)/'predictions.json';self.assertTrue(v['complete_export'])
            saved=json.loads(p.read_text());self.assertEqual([x['sample_id'] for x in saved],['b','a'])
            self.assertEqual(set(saved[0]),{'sample_id','output'})
            self.assertEqual(v['sha256'],hashlib.sha256(p.read_bytes()).hexdigest())
            self.assertEqual(json.loads((Path(d)/'validation.json').read_text())['sha256'],v['sha256'])

    def test_partial_export_reparses_raw_invalid_never_clean(self):
        with tempfile.TemporaryDirectory() as d:
            fake=result('bad','oops',status='valid',parsed={'taxonomy_error':[],'feedback':'invented'})
            v=export_submission(Path(d),{'ok':FEEDBACK_LEVELS[0],'bad':FEEDBACK_LEVELS[0],'absent':FEEDBACK_LEVELS[0]},[fake,result('ok')],list(LABEL_SPACE))
            self.assertFalse(v['complete_export']);self.assertFalse((Path(d)/'predictions.json').exists())
            self.assertEqual([r['sample_id'] for r in json.loads((Path(d)/'partial.predictions.json').read_text())],['ok'])
            unresolved=json.loads((Path(d)/'unresolved.json').read_text());self.assertEqual(len(unresolved),2)
            self.assertEqual(unresolved[0]['status'],'malformed_json');self.assertEqual(unresolved[0]['raw_history'][0]['raw'],'oops')

    def test_export_checks_saved_bytes_before_claiming_success(self):
        from src.task3 import sft_v2_public as module
        original=module.write_json
        def corrupt_saved(path,value):
            original(path,value)
            if Path(path).name=='predictions.json':
                Path(path).write_text('[]')
        with tempfile.TemporaryDirectory() as d:
            with patch.object(module,'write_json',side_effect=corrupt_saved):
                self.assertRaisesRegex(ValueError,'saved prediction bytes',export_submission,
                    Path(d),{'x':FEEDBACK_LEVELS[0]},[result('x')],list(LABEL_SPACE))
            self.assertFalse((Path(d)/'validation.json').exists())

    def test_export_rejects_duplicate_extra_level_mismatch_and_non_eos(self):
        for rows in ([result('x'),result('x')],[result('alien')],[result('x',level=2)]):
            with tempfile.TemporaryDirectory() as d:self.assertRaises(ValueError,export_submission,Path(d),{'x':FEEDBACK_LEVELS[0]},rows,list(LABEL_SPACE))
        with tempfile.TemporaryDirectory() as d:
            v=export_submission(Path(d),{'x':FEEDBACK_LEVELS[0]},[result('x',finish_reason='length')],list(LABEL_SPACE))
            self.assertFalse(v['complete_export']);self.assertEqual(json.loads((Path(d)/'partial.predictions.json').read_text()),[])

if __name__=='__main__':unittest.main()
