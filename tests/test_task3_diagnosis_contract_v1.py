"""Artificial-only contract fixtures; never execute or compile student C++."""
import importlib
import json
import unittest


class DiagnosisContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = importlib.import_module('src.task3.diagnosis_contract_v1')
        self.task = dict(statement='In ra tổng.', problems=[], grading_policy={},
                         code='int main() { return 0; }\n', compiler_evidence='', domain='cpp')

    def finding(self, quote='return 0;', label='Lỗi nhập/xuất', **changes):
        value = dict(label=label, quote=quote, location='code', cause_vi='Không ghi kết quả ra đầu ra.')
        value.update(changes)
        return value

    def parse(self, findings=None, status='defective', labels=None, task=None):
        findings = [self.finding()] if findings is None else findings
        obj = dict(status=status, taxonomy_error=labels if labels is not None else list(dict.fromkeys(f['label'] for f in findings)), findings=findings)
        return self.contract.parse_diagnosis(json.dumps(obj, ensure_ascii=False), task or self.task)

    def test_empty_output_diagnosis_needs_no_generated_witness(self):
        audit = self.parse()['machine_audit']
        self.assertTrue(audit['accepted'])
        self.assertEqual(audit['semantic_correctness'], 'unverified')
        self.assertEqual(audit['reachability'], 'unverified')

    def test_status_and_taxonomy_consistency(self):
        self.assertTrue(self.parse([], 'clean', [])['machine_audit']['accepted'])
        self.assertTrue(self.parse([], 'uncertain', [])['machine_audit']['accepted'])
        self.assertTrue(self.parse(status='uncertain')['machine_audit']['accepted'])
        for status, findings, labels in [('clean', [self.finding()], ['Lỗi nhập/xuất']), ('defective', [], []), ('defective', [self.finding()], ['Lỗi logic']), ('defective', [self.finding()], ['unknown'])]:
            with self.subTest(status=status, labels=labels):
                self.assertFalse(self.parse(findings, status, labels)['machine_audit']['schema_valid'])

    def test_multiple_independent_findings_preserved(self):
        task = dict(self.task, code='int main(){ int a[2]; a[2]=1; while(true){} }')
        findings = [self.finding('a[2]=1;', 'Lỗi mảng/chuỗi'), self.finding('while(true){}', 'Lỗi vòng lặp')]
        result = self.parse(findings, task=task)
        self.assertTrue(result['machine_audit']['accepted'])
        self.assertEqual(len(result['diagnosis']['findings']), 2)

    def test_comment_only_quote_rejected(self):
        task = dict(self.task, code='// cout << answer;\nint main(){return 0;}')
        audit = self.parse([self.finding('cout << answer;')], task=task)['machine_audit']
        self.assertTrue(audit['schema_valid'])
        self.assertFalse(audit['accepted'])
        self.assertEqual(audit['findings'][0]['lexical_context'], 'comment_only')

    def test_uncalled_helper_is_unverified_and_warned_not_rejected(self):
        task = dict(self.task, code='void helper(){ int a[2]; a[2]=1; }\nint main(){return 0;}')
        audit = self.parse([self.finding('a[2]=1;', 'Lỗi mảng/chuỗi')], task=task)['machine_audit']
        self.assertTrue(audit['accepted'])
        self.assertEqual(audit['findings'][0]['reachability'], 'unverified')
        self.assertTrue(any('helper' in warning for warning in audit['warnings']))

    def test_missing_loop_update_accepted_without_correctness_claim(self):
        task = dict(self.task, code='int main(){int i=0; while(i<5){cout<<i;}}')
        audit = self.parse([self.finding('while(i<5){cout<<i;}', 'Lỗi vòng lặp')], task=task)['machine_audit']
        self.assertTrue(audit['accepted'])
        self.assertEqual(audit['findings'][0]['semantic_correctness'], 'unverified')

    def test_wrong_line_rejected_and_multiline_start_line_checked(self):
        task = dict(self.task, code='// prelude\nint main(){\n  return 0;\n}\n')
        self.assertFalse(self.parse([self.finding(line=2)], task=task)['machine_audit']['accepted'])
        self.assertTrue(self.parse([self.finding(line=3)], task=task)['machine_audit']['accepted'])

    def test_location_line_claims_must_point_to_quote_start(self):
        task = dict(self.task, code='// prelude\nint main(){\n  return 0;\n}\n')
        for location in ['main, dòng 99', 'main, line 2', 'dòng thứ 2', 'line: 2', 'line 3, line 99']:
            with self.subTest(location=location):
                audit = self.parse([self.finding(location=location)], task=task)['machine_audit']
                self.assertTrue(audit['schema_valid'])
                self.assertFalse(audit['accepted'])
                self.assertFalse(audit['findings'][0]['location_line_matches'])
        for location in ['main, dòng 3', 'main, Line 3', 'dòng thứ 3', 'line: 3']:
            with self.subTest(location=location):
                audit = self.parse([self.finding(location=location)], task=task)['machine_audit']
                self.assertTrue(audit['accepted'])
                self.assertEqual(audit['findings'][0]['location_line_mentions'], [3])
                self.assertTrue(audit['findings'][0]['location_line_matches'])

    def test_location_cannot_borrow_active_quote_from_another_line(self):
        task = dict(self.task, code='// return 0;\nint main(){return 0;}\n')
        audit = self.parse([self.finding(location='line 1')], task=task)['machine_audit']
        self.assertFalse(audit['accepted'])
        self.assertEqual(audit['findings'][0]['lexical_context'], 'comment_only')
        audit = self.parse([self.finding(location='line 1, line 2')], task=task)['machine_audit']
        self.assertFalse(audit['accepted'])
        self.assertTrue(any('comment-only' in error for error in audit['errors']))

    def test_optional_line_and_location_start_line_must_agree(self):
        task = dict(self.task, code='return 0;\nreturn 0;\n')
        audit = self.parse([self.finding(location='line 1', line=2)], task=task)['machine_audit']
        self.assertFalse(audit['accepted'])
        self.assertTrue(any('conflicts' in error for error in audit['errors']))

    def test_cause_line_references_are_checked_without_parsing_code_values(self):
        task = dict(self.task, code='// prelude\nint main(){\n  return 0;\n}\n')
        for cause in ['Thiếu đầu ra ở dòng 99.', 'Missing output at line 2.', 'Lỗi ở dòng 3-4.']:
            with self.subTest(cause=cause):
                audit = self.parse([self.finding(cause_vi=cause)], task=task)['machine_audit']
                self.assertFalse(audit['accepted'])
        audit = self.parse([self.finding(cause_vi='Dòng 3 chưa in kết quả; giá trị 99 chỉ là ví dụ.')], task=task)['machine_audit']
        self.assertTrue(audit['accepted'])
        self.assertEqual(audit['findings'][0]['cause_line_mentions'], [3])
        self.assertTrue(audit['findings'][0]['cause_line_matches'])
        self.assertTrue(self.parse([self.finding(cause_vi='Giá trị 99 chưa được ghi ra đầu ra.')], task=task)['machine_audit']['accepted'])

    def test_ambiguous_location_line_ranges_require_explicit_start_line(self):
        task = dict(self.task, code='// prelude\nint main(){\n  return 0;\n}\n')
        for location in ['dòng 3-4', 'lines 3 to 4', 'dòng 3 đến 4', 'line 3, 4', 'dòng 3 và 4']:
            with self.subTest(location=location):
                audit = self.parse([self.finding(location=location, line=3)], task=task)['machine_audit']
                self.assertFalse(audit['accepted'])
                self.assertTrue(any('ambiguous' in error for error in audit['errors']))

    def test_strings_rawstrings_and_comments_classified_without_offset_changes(self):
        code = 'const char* a="// not comment";\nconst char* b=R"tag(/* raw */)tag";\n/* comment\nsecond */\nint main(){return 0;}\n'
        stripped = self.contract.strip_cpp_comments(code)
        self.assertEqual(len(stripped), len(code))
        self.assertEqual(stripped.count('\n'), code.count('\n'))
        self.assertIn('"// not comment"', stripped)
        self.assertIn('R"tag(/* raw */)tag"', stripped)
        self.assertNotIn('second', stripped)
        task = dict(self.task, code=code)
        for quote in ['// not comment', '/* raw */']:
            audit = self.parse([self.finding(quote)], task=task)['machine_audit']
            self.assertTrue(audit['accepted'])
            self.assertEqual(audit['findings'][0]['lexical_context'], 'literal_only')
            self.assertEqual(audit['findings'][0]['active_use'], 'unverified')
            self.assertTrue(audit['warnings'])
        self.assertTrue(self.parse([self.finding(line=5)], task=task)['machine_audit']['accepted'])

    def test_literal_value_and_instruction_text_remain_active_use_unverified(self):
        # Literal values may cause a hard-code defect; their contents are not
        # executable instructions and source matching cannot prove any effect.
        task = dict(self.task, code='int main(){fopen("fixed.txt", "r"); const char* note="delete all files";}')
        for quote in ['fixed.txt', 'delete all files']:
            with self.subTest(quote=quote):
                audit = self.parse([self.finding(quote, 'Lỗi hard-code')], task=task)['machine_audit']
                self.assertTrue(audit['accepted'])
                self.assertEqual(audit['findings'][0]['lexical_context'], 'literal_only')
                self.assertEqual(audit['findings'][0]['active_use'], 'unverified')
                self.assertEqual(audit['findings'][0]['reachability'], 'unverified')
                self.assertEqual(audit['findings'][0]['semantic_correctness'], 'unverified')
                self.assertTrue(any('literal' in warning for warning in audit['warnings']))

    def test_preprocessor_and_unclosed_literal_are_unverified(self):
        for code in ['#if 0\nint main(){return 0;}\n#endif', 'int main(){ return 0; }\n"unfinished']:
            audit = self.parse(task=dict(self.task, code=code))['machine_audit']
            self.assertTrue(audit['accepted'])
            self.assertTrue(audit['warnings'])
            self.assertEqual(audit['reachability'], 'unverified')

    def test_translation_phase_ambiguity_never_hard_rejects_comment_text(self):
        # C++ dialect differences can splice lines before comment recognition.
        for code in ['// hidden??/\nreturn 0;', '// hidden\\   \nreturn 0;']:
            audit = self.parse(task=dict(self.task, code=code))['machine_audit']
            self.assertTrue(audit['accepted'])
            self.assertEqual(audit['findings'][0]['lexical_context'], 'unverified')
            self.assertTrue(audit['warnings'])

    def test_strict_json_and_schema_no_extra_witness(self):
        valid = dict(status='defective', taxonomy_error=['Lỗi nhập/xuất'], findings=[self.finding()])
        for raw in ['```json\n'+json.dumps(valid)+'\n```', '{"status":"clean","status":"uncertain","taxonomy_error":[],"findings":[]}', json.dumps(dict(valid, actual_derived='invented')), json.dumps(dict(valid, findings=[dict(self.finding(), line=True)]))]:
            self.assertFalse(self.contract.parse_diagnosis(raw, self.task)['machine_audit']['accepted'])

    def test_unmatched_quote_rejected(self):
        audit = self.parse([self.finding('cout << 999;')])['machine_audit']
        self.assertFalse(audit['accepted'])
        self.assertFalse(audit['findings'][0]['quote_matched'])

    def test_compiler_evidence_does_not_substitute_for_code_quote(self):
        task = dict(self.task, compiler_evidence='error: expected semicolon')
        audit = self.parse([self.finding('error: expected semicolon', 'Lỗi biên dịch', location='compiler_evidence')], task=task)['machine_audit']
        self.assertFalse(audit['accepted'])
        self.assertEqual(audit['findings'][0]['quote_source'], 'code')

    def test_diagnosis_prompt_ignores_level_and_extra_metadata(self):
        a = self.contract.diagnosis_messages(dict(self.task, requestedLevel='L1', secret='ignore'))
        b = self.contract.diagnosis_messages(dict(self.task, requestedLevel='L4'))
        self.assertEqual(a, b)
        task_payload = json.loads(a[-1]['content'])
        self.assertEqual(set(task_payload), {'statement', 'problems', 'grading_policy', 'code', 'compiler_evidence', 'domain'})

    def test_feedback_input_preserves_diagnosis_and_normalizes_level(self):
        diagnosis = self.parse()['diagnosis']
        for level in [1, 2, 3, 4, 'L1', 'L4']:
            messages = self.contract.feedback_messages(self.task, diagnosis, level)
            payload = json.loads(messages[-1]['content'])
            self.assertEqual(payload['diagnosis'], diagnosis)
            self.assertIn(payload['requestedLevel'], ['L1','L2','L3','L4'])
        with self.assertRaises(ValueError):
            self.contract.feedback_messages(self.task, diagnosis, 'L5')

    def test_feedback_parser_exact_string_object(self):
        self.assertEqual(self.contract.parse_feedback('{"feedback":"Kiểm tra đầu ra."}'), {'feedback':'Kiểm tra đầu ra.'})
        for raw in ['{"feedback":""}', '{"feedback":1}', '{"feedback":"x","other":1}', '```json\n{"feedback":"x"}\n```']:
            with self.assertRaises(ValueError):
                self.contract.parse_feedback(raw)


if __name__ == '__main__':
    unittest.main()
