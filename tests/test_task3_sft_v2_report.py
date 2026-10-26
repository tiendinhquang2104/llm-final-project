"""Offline report evidence and denominator regression tests; no model/runtime calls."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('v2_report',ROOT/'scripts/task3_sft_v2_report.py')

class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(cls.mod)

    def fixture(self):
        examples=[];source=[];generations={'base':[],'v2':[]};quality={};audits={}
        for sid,faulty in [('C',False),('D',True)]:
            for level in range(1,5):
                eid=f'{sid}-L{level}';gold={'taxonomy_error':['Lỗi logic'] if faulty else [],'feedback':'Gold riêng'}
                examples.append(dict(example_id=eid,sample_id=sid,level=level,prompt=[{'role':'user','content':'native prompt'}],completion=json.dumps(gold)))
                source.append(dict(sample_id=eid,source_id=sid,input={'statement':'Đọc dữ liệu; không in lời nhắc.','code':'int main(){return 0;}','compile_log':'','exam_type':'single_problem'},output=gold))
                for state in generations:
                    valid=not(state=='base' and eid=='D-L4')
                    row=dict(example_id=eid,sample_id=sid,level=level,raw='<bad raw>' if not valid else 'Nội dung thực tế',parsed={'taxonomy_error':[],'feedback':'Phản hồi thực tế'} if valid else None,status='valid' if valid else 'malformed_json',finish_reason='eos',input_tokens=2,output_tokens=3,wall_s=0.1)
                    if state=='base' and sid=='C':row['parsed']['taxonomy_error']=['Lỗi logic']
                    generations[state].append(row)
                    dims={a:'pass' for a in self.mod.AXES}
                    if level!=3:dims['l3_repair_direction']='not_applicable'
                    if level!=4:dims['l4_explanation_quality']='not_applicable'
                    if level==1 or not faulty:dims['location_and_condition']='not_applicable'
                    if not valid:dims={a:'not_evaluable' for a in self.mod.AXES}
                    if state=='v2' and eid=='D-L4':dims['l4_explanation_quality']='fail'
                    quality[state,eid]=dict(state=state,example_id=eid,sample_id=sid,level=level,status=row['status'],dimensions=dims,evidence='Dẫn chứng <nguồn> và đoạn phản hồi đã đọc.')
                    if level==4:audits[state,eid]={'example_id':eid,'status':'all_authored_tests_passed' if valid else 'not_evaluable','tests':[{'passed':True}],'extraction':{'status':'extracted','code':'int main(){}'}}
        return examples,source,generations,quality,audits

    def test_casebook_embeds_completed_dimensions_evidence_raw_and_code(self):
        bundle=self.mod.assemble_split(*self.fixture())
        html=self.mod.render_casebook('Kiểm tra',bundle)
        self.assertIn('Dẫn chứng &lt;nguồn&gt;',html)
        self.assertIn('&lt;bad raw&gt;',html)
        self.assertIn('l4_explanation_quality',html)
        self.assertIn('all_authored_tests_passed',html)
        self.assertIn('int main(){}',html)
        self.assertIn('Gold riêng',html)
        self.assertNotIn('pending_source_grounded_review',html)
        self.assertEqual(html.count('class="response"'),16)
        self.assertIn('id="state-filter"',html)

    def test_counts_reconcile_reviews_and_l4_separately(self):
        b=self.mod.assemble_split(*self.fixture())
        self.assertEqual(b['states']['base']['metrics']['invalid_outputs'],1)
        self.assertEqual(b['states']['base']['metrics']['clean_false_alarms']['targets']['false_alarms'],4)
        self.assertEqual(b['states']['base']['metrics']['clean_false_alarms']['sources']['false_alarms'],1)
        self.assertEqual(b['states']['v2']['l4']['code_pass_explanation_nonpass'],1)
        for state,stats in b['states'].items():
            self.assertEqual(sum(stats['dimensions']['diagnosis_supported'].values()),8)
            self.mod.reconcile_saved(stats,{'targets':8,'joint_successful':stats['joint_successful'],'joint_ids':stats['joint_ids'],'faulty_l3_correct':stats['faulty_l3_correct'],'faulty_l3_ids':stats['faulty_l3_ids'],'dimensions':stats['dimensions'],'mean_loss':None,'clean_false_alarms':stats['metrics']['clean_false_alarms']['targets']['false_alarms'],'invalid':stats['metrics']['invalid_outputs']})
        saved={'targets':8,'joint_successful':stats['joint_successful'],'joint_ids':stats['joint_ids'],'faulty_l3_correct':stats['faulty_l3_correct'],'faulty_l3_ids':stats['faulty_l3_ids'],'dimensions':copy.deepcopy(stats['dimensions']),'clean_false_alarms':stats['metrics']['clean_false_alarms']['targets']['false_alarms'],'invalid':stats['metrics']['invalid_outputs']}
        saved['dimensions']['diagnosis_supported']['pass']+=1
        with self.assertRaisesRegex(ValueError,'dimensions'):self.mod.reconcile_saved(stats,saved)

    def test_incomplete_or_unreviewed_outputs_refused(self):
        f=self.fixture();f[3].pop(('v2','C-L1'))
        with self.assertRaises(ValueError):self.mod.assemble_split(*f)
        f=self.fixture();f[2]['v2'].pop()
        with self.assertRaises(ValueError):self.mod.assemble_split(*f)
        f=self.fixture();f[4].pop(('v2','D-L4'))
        with self.assertRaises(ValueError):self.mod.assemble_split(*f)
        f=self.fixture();f[3]['base','D-L4']['dimensions']['diagnosis_supported']='pass'
        with self.assertRaises(ValueError):self.mod.assemble_split(*f)

    def test_vietnamese_markdown_and_examples_render_without_missing_dimensions(self):
        base=self.mod.assemble_split(*self.fixture());bundles={}
        names={'dev':['ar15-dev','base-dev','v1-dev','step-120-dev','step-240-dev'],'final':['ar15-final','base-final','v1-final','v2-final'],'test':['base-regression','v1-regression','v2-regression']}
        for split,states in names.items():
            b=copy.deepcopy(base);b['states']={state:copy.deepcopy(base['states']['base' if state.startswith(('base','ar15')) else 'v2']) for state in states}
            for state in states:b['states'][state]['mean_loss']=None
            for i,t in enumerate(b['targets']):t['states']={state:copy.deepcopy(base['targets'][i]['states']['base' if state.startswith(('base','ar15')) else 'v2']) for state in states}
            bundles[split]=b
        examples=self.mod.choose_examples(bundles,120)
        self.assertIsNotNone(examples['clean_false_alarm_fixed'])
        self.assertIsNone(examples['clean_false_alarm_introduced'])
        self.assertIsNotNone(examples['l4_code_pass_explanation_fail'])
        analysis={'selection':{'step':120,'eligible_steps':[120],'passes_preliminary_conditions':True},'manifest':{'config':{'model_id':'pinned-model','revision':'pinned-revision','seed':42},'ar15_identity':{'policy':'historical'},'call_budget':{'physical_total':1442}},'dataset':{'sources':{'train':240},'targets':{'train':960},'train_clean':95,'train_faulty':145},'target_changes':{'count':101},'training':{'main':{'actual_optimizer_steps':240},'actual_arguments':{'seed':42},'memory_and_time_scope':{'peak_memory_scope':'whole main'}},'splits':bundles,'authoring_evidence':{'train':{'passed':True}},'costs':{'journal':{'reused_states':[]},'displayed_targets':96},'examples':examples}
        md=self.mod.markdown_report(analysis,Path('/tmp/synthetic-report'))
        self.assertIn('101 thay đổi target',md)
        self.assertIn('không phải điểm Task 3 chính thức',md)
        self.assertIn('Không có trường hợp thỏa điều kiện',md)
        self.assertIn('Dẫn chứng <nguồn>',md)
        self.assertIn('int main(){return 0;}',md)
        self.assertIn('Taxonomy false alarm clean đã sửa',md)
        self.assertIn('mù một phần',md)
        self.assertIn('51/80',md)

    def test_costs_distinguish_reservations_attempts_reuse_and_retries(self):
        events=[{'type':'generation_reserved','key':'base-final/C-L1'}, {'type':'generation_completed','key':'base-final/C-L1','result':{'wall_s':1,'output_tokens':4}}, {'type':'generation_reserved','key':'ar15-final/C-L1/1'}, {'type':'ar15_generation_completed','key':'ar15-final/C-L1/1','wall_s':2,'output_tokens':5}, {'type':'generation_reserved','key':'ar15-final/C-L1/2'}, {'type':'ar15_generation_completed','key':'ar15-final/C-L1/2','wall_s':3,'output_tokens':6}, {'type':'generation_reserved','key':'smoke-before'}, {'type':'generation_completed','key':'smoke-before','result':{'wall_s':1,'output_tokens':1}}]
        result=self.mod.journal_costs(events,{'base-dev':{'generated_in_this_experiment':False}},10)
        self.assertEqual(result['physical_reservations'],4)
        self.assertEqual(result['ar15_internal_retries_reserved'],1)
        self.assertEqual(result['fresh_native_primary_reservations'],1)
        self.assertEqual(result['smoke_reservations'],1)
        self.assertEqual(result['completed_generation_wall_s'],7)
        self.assertEqual(result['reused_states'],['base-dev'])
        self.assertFalse(result['whole_experiment_wall_s_available'])

    def test_report_uses_its_v2_checksum_manifest_instead_of_v1_default(self):
        from src.task3.sft_v1 import sha256
        with tempfile.TemporaryDirectory() as temp:
            run=Path(temp)/'run';root=Path(temp)/'dataset';run.mkdir();root.mkdir()
            payload=root/'payload.txt';payload.write_text('version two')
            (root/'SHA256SUMS').write_text(sha256(payload)+'  payload.txt\n')
            (run/'manifest.json').write_text(json.dumps({'config':{'dataset_root':str(root),
                'checksum_manifest_sha256':sha256(root/'SHA256SUMS')}}))
            for states in self.mod.STATES.values():
                for state in states:
                    directory=run/state;directory.mkdir()
                    for name in ('complete.json','generations.jsonl'):(directory/name).touch()
            # Integration reaches the next missing artifact only after checking
            # this independently versioned dataset with its actual manifest.
            with patch('src.task3.sft_v1_runtime.verify_frozen'),patch('src.task3.sft_v2_runtime.validated_selection'):
                with self.assertRaises(FileNotFoundError) as caught:self.mod.report(run)
            self.assertTrue(str(caught.exception.filename).endswith('dataset-manifest.json'))

if __name__=='__main__':unittest.main()
