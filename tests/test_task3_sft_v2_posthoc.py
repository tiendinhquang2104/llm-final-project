"""Offline regression fixtures for separate clean/faulty post-hoc denominators."""
import unittest
from scripts.task3_sft_v2_posthoc import aggregate_state, balanced_joint

AXES = ('diagnosis_supported', 'location_and_condition', 'unsupported_defects',
        'level_compliance', 'vietnamese_compliance', 'l3_repair_direction', 'l4_explanation_quality')

def reference(eid, faulty=False, source=None, level=1):
    return {'sample_id': eid, 'source_id': source or eid, 'input': {'target_feedback_level': level},
            'output': {'taxonomy_error': ['logic'] if faulty else [], 'feedback': 'gold'}}

def generation(eid, labels=(), status='valid', level=1, source=None):
    return {'example_id': eid, 'sample_id': source or eid, 'level': level, 'status': status,
            'parsed': {'taxonomy_error': list(labels), 'feedback': 'Phản hồi'} if status=='valid' else None,
            'finish_reason': 'eos'}

def review(eid):
    return {('state', eid): {'dimensions': {a: 'pass' for a in AXES}}}

class PosthocTests(unittest.TestCase):
    def test_invalid_missing_duplicate_and_extra_cannot_be_clean_predictions(self):
        refs=[reference('bad'), reference('missing'), reference('dup'), reference('ok')]
        gens=[generation('bad',status='malformed_json'),generation('dup'),generation('dup'),generation('ok'),generation('extra')]
        result=aggregate_state(refs,gens,{}, {},'state')
        self.assertEqual(result['coverage']['valid'],1)
        self.assertEqual(result['coverage']['invalid'],1)
        self.assertEqual(result['coverage']['missing'],1)
        self.assertEqual(result['coverage']['duplicate_ids'],['dup'])
        self.assertEqual(result['coverage']['extra_ids'],['extra'])
        self.assertEqual(result['clean']['empty_taxonomy'],1)
        self.assertEqual(result['clean']['joint_success'],0)
        self.assertEqual(result['clean']['targets'],4)
        self.assertEqual(result['taxonomy']['exact_match_all']['correct'],1)

    def test_faulty_presence_does_not_imply_taxonomy_or_supported_joint(self):
        refs=[reference('c'),reference('d',True),reference('e',True)]
        gens=[generation('c',['logic']),generation('d',['other']),generation('e',status='malformed_json')]
        result=aggregate_state(refs,gens,review('d'),{},'state')
        self.assertEqual(result['clean']['nonempty_taxonomy'],1)
        self.assertEqual(result['faulty']['nonempty_taxonomy'],1)
        self.assertEqual(result['taxonomy']['all_targets_conservative']['tp'],0)
        self.assertEqual(result['taxonomy']['all_targets_conservative']['fp'],2)
        self.assertEqual(result['taxonomy']['all_targets_conservative']['fn'],2)
        # Joint deliberately preserves existing semantic verdicts, independent of taxonomy exact-match.
        self.assertEqual(result['faulty']['joint_success'],1)

    def test_balanced_joint_uses_class_denominators_and_handles_absent_class(self):
        self.assertAlmostEqual(balanced_joint(15,20,8,60),.5*(15/20)+.5*(8/60))
        self.assertIsNone(balanced_joint(1,1,0,0))
        refs=[reference('clean')]+[reference('d'+str(i),True) for i in range(3)]
        gens=[generation('clean')]+[generation('d'+str(i),['logic']) for i in range(3)]
        q=review('clean');q.update(review('d0'))
        result=aggregate_state(refs,gens,q,{},'state')
        self.assertEqual(result['joint']['successful'],2)
        self.assertAlmostEqual(result['balanced_joint_success'],2/3)
        self.assertEqual(result['clean']['sources'],1)
        self.assertEqual(result['faulty']['sources'],3)

    def test_l4_code_pass_never_overrides_failed_explanation(self):
        refs=[reference('d',True,level=4)];gens=[generation('d',['logic'],level=4)]
        q=review('d');q['state','d']['dimensions']['l4_explanation_quality']='fail'
        result=aggregate_state(refs,gens,q,{('state','d'):{'status':'all_authored_tests_passed'}},'state')
        self.assertEqual(result['l4']['code_pass'],1)
        self.assertEqual(result['l4']['code_pass_explanation_nonpass'],1)
        self.assertEqual(result['joint']['successful'],0)

    def test_valid_status_without_actual_payload_is_invalid_not_empty(self):
        g=generation('x');g['parsed']=None
        result=aggregate_state([reference('x')],[g],review('x'),{},'state')
        self.assertEqual(result['coverage']['invalid'],1)
        self.assertEqual(result['clean']['empty_taxonomy'],0)
        self.assertEqual(result['clean']['joint_success'],0)

    def test_missing_and_duplicate_faulty_gold_contribute_conservative_fn(self):
        refs=[reference('missing',True),reference('dup',True)]
        gens=[generation('dup',['logic']),generation('dup',['logic'])]
        result=aggregate_state(refs,gens,review('dup'),{},'state')
        self.assertEqual(result['faulty']['missing'],1)
        self.assertEqual(result['faulty']['duplicate'],1)
        self.assertEqual(result['faulty']['nonempty_taxonomy'],0)
        self.assertEqual(result['faulty']['empty_taxonomy'],0)
        self.assertEqual(result['taxonomy']['all_targets_conservative']['fn'],2)
        self.assertEqual(result['faulty']['joint_success'],0)

    def test_saved_missing_export_status_is_invalid_not_absent_generation_id(self):
        refs=[reference('x')];gens=[generation('x',status='missing')]
        result=aggregate_state(refs,gens,{}, {},'state')
        self.assertEqual(result['coverage']['missing'],0)
        self.assertEqual(result['coverage']['invalid'],1)
        self.assertEqual(result['clean']['invalid'],1)
        self.assertEqual(result['clean']['missing'],0)
        self.assertEqual(result['clean']['empty_taxonomy'],0)

    def test_binding_mismatch_refused(self):
        with self.assertRaisesRegex(ValueError,'binding'):
            aggregate_state([reference('x')],[generation('x',source='wrong')],{}, {},'state')

if __name__=='__main__':unittest.main()
