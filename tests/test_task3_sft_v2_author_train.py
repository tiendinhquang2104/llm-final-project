"""Regression checks for private, specification-derived v2 training authoring."""
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/task3_sft_v2_author_train.py'

class AuthorTrainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('v2_author_train', SCRIPT)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        cls.cases = cls.mod.build_cases(ROOT)

    def test_exact_counts_schema_and_train_binding(self):
        families = {x['family_id']: x for x in json.loads((ROOT/'data/raw/task3-sft-v1/families.json').read_text())}
        keys = {'sample_id','pair_id','family_id','cluster','split','statement','exam_type','checker','code','harness','labels','intended_defective','expected_failure_kind','solution_source_id','mechanism','mutation','invariant','targets','tests','oracle_provenance'}
        self.assertEqual(len(self.cases), 80)
        self.assertEqual(sum(c['intended_defective'] for c in self.cases),40)
        self.assertEqual({c['family_id'] for c in self.cases},{f for f,x in families.items() if x['split']=='train'})
        for c in self.cases:
            self.assertEqual(set(c),keys)
            self.assertEqual(c['split'],'train')
            self.assertEqual(c['cluster'],families[c['family_id']]['cluster'])
            self.assertEqual(c['statement'],families[c['family_id']]['statement'])
            self.assertEqual(set(c['targets']),{'1','2','3','4'})
            self.assertEqual(c['expected_failure_kind']=='none',not c['intended_defective'])
            for target in c['targets'].values():
                self.assertEqual(set(target),{'taxonomy_error','feedback'})
                self.assertEqual(target['taxonomy_error'],c['labels'])

    def test_paired_mutation_and_full_repair(self):
        for idx in range(0,80,2):
            clean,bad=self.cases[idx:idx+2]
            self.assertEqual(clean['pair_id'],f'V2T{idx//2+1:02}')
            self.assertEqual([clean['sample_id'],bad['sample_id']],[clean['pair_id']+'-C',clean['pair_id']+'-D'])
            self.assertEqual(bad['solution_source_id'],clean['sample_id'])
            m=bad['mutation']
            self.assertEqual(clean['code'].count(m['before']),1)
            self.assertEqual(clean['code'].replace(m['before'],m['after'],1),bad['code'])
            for c in (clean,bad):
                repair=re.search(r'```cpp\n(.*?)\n```',c['targets']['4']['feedback'],re.S)
                self.assertIsNotNone(repair)
                self.assertEqual(repair.group(1)+'\n',clean['code'])
                self.assertNotIn('```',c['targets']['3']['feedback'])
                self.assertNotIn('```',c['targets']['2']['feedback'])
                self.assertEqual(c['targets']['1']['feedback'],'Bài làm có lỗi cần sửa.' if c['intended_defective'] else 'Bài làm đáp ứng yêu cầu của đề.')

    def test_independent_oracles(self):
        for c in self.cases:
            self.assertGreaterEqual(len(c['tests']),8)
            for t in c['tests']:
                self.assertEqual(t['expected'],self.mod.oracle(c['family_id'],t['input']))
        # Independently hand-computed checks exercise inclusive/empty/sign behavior.
        examples=[('F01','0\n','0\n'),('F02','3 2\n0 -4 3\n','2\n'),('F07','-1 1 1 4\n','1\n'),('F10','3 -2\n-2 -5 -2\n','-2 -5 -2\n2\n-2\n-5\n'),('F12','-3 2\n','-1 -6\n'),('F48','2 4\n1 2\n','3\n'),('F49','3\n1 3\n3 7\n2 2\n','1 7\n')]
        for f,x,y in examples:self.assertEqual(self.mod.oracle(f,x),y)

    def test_no_exact_or_normalized_old_duplicates(self):
        old=json.loads((ROOT/'data/raw/task3-sft-v1/cases.private.json').read_text())
        sources=[(ROOT/'data/raw/task3-sft-v1'/c['code_file']).read_text() for c in old]
        oldnorm={self.mod.normalized_source(s) for s in sources}
        newnorm=[]
        for c in self.cases:
            self.assertNotIn(c['code'],sources)
            n=self.mod.normalized_source(c['code']);self.assertNotIn(n,oldnorm);newnorm.append(n)
        self.assertEqual(len(set(newnorm)),80)

if __name__=='__main__':unittest.main()
