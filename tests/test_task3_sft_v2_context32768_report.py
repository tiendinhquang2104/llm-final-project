"""Offline context-run comparison/review-reuse regression tests."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from scripts.task3_sft_v2_context32768_report import canonical_payload,compare_runs,report,eight_casebook
from src.synth.feedback import FEEDBACK_LEVELS

LABELS=['Lỗi logic']

def row(sid='x',feedback='Bài làm đúng.',labels=None,**changes):
    value=dict(sample_id=sid,level=2,raw=json.dumps({'taxonomy_error':labels or [],'feedback':feedback},ensure_ascii=False),finish_reason='eos')
    value.update(changes);return value

def binding(sid='x'):
    return dict(sample_id=sid,level=2,source_sha256='sourcehash',original_statement_sha256='spechash',
                mapped_input=dict(statement='FULL <spec> P1; P2 depends on P1',code='int f(){return 1;}\r\n',compile_log='log',target_feedback_level=2))

def review(r):
    payload=json.loads(r['raw']);sha=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return dict(sample_id=r['sample_id'],level=2,source_sha256='sourcehash',outputs={'v2':dict(original_payload_sha256=sha,structural_status='valid',verdicts={'diagnosis_supported':'pass'},evidence={'source':'read'})})

class ContextReportTests(unittest.TestCase):
    def compare(self,old,new,oldbinding=None,newbinding=None,reviews=None):
        return compare_runs({'x':FEEDBACK_LEVELS[1]},[old],[new],[oldbinding or binding()],[newbinding or binding()],LABELS,reviews if reviews is not None else [review(old)])

    def test_canonical_payload_equal_ignores_object_spacing_but_raw_equality_separate(self):
        old=row();new=row(raw=' { "feedback": "Bài làm đúng.", "taxonomy_error": [] } ')
        result=self.compare(old,new);s=result['summary'];self.assertEqual(s['payload_byte_identical'],1);self.assertEqual(s['raw_response_byte_identical'],0)
        self.assertEqual(result['reuse']['rows'][0]['status'],'reused')
        self.assertEqual(canonical_payload(json.loads(old['raw'])),canonical_payload(json.loads(new['raw'])))

    def test_changed_feedback_requires_new_review_even_same_taxonomy(self):
        result=self.compare(row(),row(feedback='Bài làm đúng. '))
        self.assertEqual(result['summary']['feedback_exact_changed'],1);self.assertEqual(result['summary']['label_set_changed'],0)
        reuse=result['reuse']['rows'][0];self.assertEqual(reuse['status'],'requires_new_review');self.assertNotIn('transferred_v2_review',reuse)

    def test_source_or_full_mapped_input_change_prevents_review_transfer(self):
        for change in ('source','statement','log'):
            b=binding()
            if change=='source':b['source_sha256']='changed'
            elif change=='statement':b['mapped_input']['statement']+=' extra'
            else:b['mapped_input']['compile_log']+=' changed'
            result=self.compare(row(),row(),newbinding=b)
            self.assertEqual(result['summary']['payload_byte_identical'],1)
            self.assertEqual(result['reuse']['rows'][0]['status'],'requires_new_review')

    def test_invalid_taxonomy_is_not_empty_and_new_structural_failure_retained(self):
        old=row(labels=['Lỗi logic']);new=row(raw='{"taxonomy_error":["unknown"],"feedback":"nội dung"}')
        result=self.compare(old,new)
        self.assertEqual(result['summary']['new_structural_failures'],1)
        self.assertEqual(result['summary']['empty_nonempty_transitions'],{})
        self.assertIsNone(result['rows'][0]['new_taxonomy_empty'])
        self.assertEqual(result['reuse']['rows'][0]['status'],'requires_new_review')

    def test_prior_null_and_unreviewed_cannot_create_reused_verdict(self):
        old=row(raw='',finish_reason='not_called');result=self.compare(old,row(),reviews=[])
        self.assertEqual(result['reuse']['rows'][0]['status'],'not_reviewed')
        q=dict(sample_id='x',level=2,source_sha256='sourcehash',outputs={'v2':{'original_payload_sha256':'irrelevant','verdicts':{'diagnosis_supported':'not_evaluable'}}})
        result=self.compare(old,row(),reviews=[q]);self.assertEqual(result['reuse']['rows'][0]['status'],'not_eligible_prior_null')
        self.assertEqual(result['summary']['prior_valid_targets'],0)

    def test_exact_id_level_join_and_review_hash_binding(self):
        self.assertRaises(ValueError,self.compare,row(),row(level=1))
        self.assertRaises(ValueError,compare_runs,{'x':FEEDBACK_LEVELS[1]},[row(),row()],[row()],[binding()],[binding()],LABELS,[])
        q=review(row());q['outputs']['v2']['original_payload_sha256']='wrong'
        self.assertRaisesRegex(ValueError,'review payload',self.compare,row(),row(),reviews=[q])

    def test_casebook_escapes_full_input_and_raw_output(self):
        cases=[dict(sample_id='x',level=2,prompt_tokens=12,status='malformed_json',finish_reason='eos',raw='<script>bad</script>',parsed_output=None,input=binding())]
        text=eight_casebook(cases)
        self.assertIn('FULL &lt;spec&gt; P1; P2 depends on P1',text);self.assertIn('&lt;script&gt;bad&lt;/script&gt;',text)
        self.assertIn('int f(){return 1;}\r\n',text);self.assertNotIn('<script>bad</script>',text)

    def test_no_final_analysis_before_complete_marker(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.assertRaises(FileNotFoundError,report,p,p/'prior')
            self.assertFalse((p/'analysis').exists())

if __name__=='__main__':unittest.main()
