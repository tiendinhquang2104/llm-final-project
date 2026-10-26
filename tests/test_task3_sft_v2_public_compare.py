"""Offline comparator tests: no public outputs, model or compiler required."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from src.synth.feedback import FEEDBACK_LEVELS
from scripts.task3_sft_v2_public_compare import compare, run, prepare_fixed_packets

LABELS = ['Lỗi logic', 'Lỗi vòng lặp']


def payload(labels=None, feedback='Bài làm đáp ứng yêu cầu.'):
    return {'taxonomy_error': labels or [], 'feedback': feedback}


def generation(sid, labels=None, **changes):
    row = {'sample_id': sid, 'level': 2, 'raw': json.dumps(payload(labels), ensure_ascii=False), 'finish_reason': 'eos'}
    row.update(changes)
    return row


def binding(sid):
    return {'sample_id': sid, 'level': 2, 'mapped_input': {'statement': 'FULL <statement>\nP2 prototype: int f();', 'code': '<source>\n', 'compile_log': 'attributed log', 'exam_type': 'multi_problem'}, 'supplied_log': 'dataset-log', 'local_syntax': {'stderr': 'local-log'}}


def selection(ids=None):
    return {'seed': 'fixture-seed', 'ids': ids or [], 'additional_risk_policy': {'maximum': 24, 'exclude_fixed_slice': True, 'rank': ['empty_nonempty_taxonomy_transition', 'different_label_set', 'language_flag', 'feedback_length_over_800'], 'tie': 'sha256(seed + | + sample_id)', 'invalid_review': 'all separately'}}


class PublicCompareTests(unittest.TestCase):
    def compare_fixture(self, requested, gens, historical, selected=None):
        return compare(requested, [binding(s) for s in requested], gens, historical, LABELS, selected or selection())

    def test_transitions_require_two_valid_payloads_and_keep_invalid_separate(self):
        ids = ['suffix-L1', 'second', 'missing', 'historical-invalid']
        req = dict.fromkeys(ids, FEEDBACK_LEVELS[1])
        gens = [generation(ids[0], ['Lỗi logic']), generation(ids[1], raw='{bad'), generation(ids[3])]
        old = [{'sample_id': ids[0], 'output': payload()}, {'sample_id': ids[1], 'output': payload(['Lỗi logic'])}, {'sample_id': ids[2], 'output': payload()}, {'sample_id': ids[3], 'output': payload(['foreign-label'])}]
        result = self.compare_fixture(req, gens, old)
        rows = {r['sample_id']: r for r in result['rows']}
        self.assertEqual(rows[ids[0]]['level'], 2)  # Never infer from suffix-L1.
        self.assertEqual(rows[ids[0]]['taxonomy_transition'], 'empty_to_nonempty')
        self.assertEqual(rows[ids[1]]['taxonomy_transition'], None)
        self.assertEqual(rows[ids[2]]['v2']['status'], 'missing')
        self.assertEqual(rows[ids[3]]['comparator']['status'], 'invalid')
        self.assertEqual(result['summary']['methods']['v2'], {'valid': 2, 'invalid': 1, 'missing': 1, 'incompatible': 0})
        self.assertEqual(set(result['risk_selection']['all_invalid_ids']), {'second', 'historical-invalid'})
        self.assertEqual(result['summary']['taxonomy_transitions'], {'empty_to_nonempty': 1})

    def test_rejects_ambiguous_v2_identity_or_authoritative_level(self):
        req = {'exact': FEEDBACK_LEVELS[1]}
        for gens in [[generation('exact'), generation('exact')], [generation('exact-L2')], [generation('exact', level=1)]]:
            with self.subTest(gens=gens), self.assertRaises(ValueError):
                self.compare_fixture(req, gens, [])

    def test_duplicate_comparator_is_incompatible_not_first_wins(self):
        result = self.compare_fixture({'id': FEEDBACK_LEVELS[1]}, [generation('id')], [{'sample_id': 'id', 'output': payload()}, {'sample_id': 'id', 'output': payload(['Lỗi logic'])}])
        self.assertEqual(result['rows'][0]['comparator']['status'], 'incompatible')
        self.assertIsNone(result['rows'][0]['taxonomy_transition'])

    def test_risk_selection_is_stable_excludes_fixed_and_caps_at_24(self):
        ids = ['id%02d' % i for i in range(31)]
        req = dict.fromkeys(ids, FEEDBACK_LEVELS[1])
        gens = [generation(s, ['Lỗi logic']) for s in ids]
        old = [{'sample_id': s, 'output': payload()} for s in ids]
        a = self.compare_fixture(req, gens, old, selection(['id00']))
        b = self.compare_fixture(dict(reversed(list(req.items()))), list(reversed(gens)), list(reversed(old)), selection(['id00']))
        chosen = a['risk_selection']['additional_ids']
        self.assertEqual(len(chosen), 24)
        self.assertNotIn('id00', chosen)
        self.assertEqual(chosen, b['risk_selection']['additional_ids'])
        expected_first = min(ids[1:], key=lambda sid: hashlib.sha256(('fixture-seed|' + sid).encode()).hexdigest())
        self.assertEqual(chosen[0], expected_first)

    def test_blind_packet_retains_full_input_exact_raw_and_hides_method_names(self):
        raw = '<invalid & response>'
        result = self.compare_fixture({'id': FEEDBACK_LEVELS[1]}, [generation('id', raw=raw)], [{'sample_id': 'id', 'output': payload()}], selection(['id']))
        packet = result['packets'][0]
        self.assertEqual(packet['input']['mapped_input']['code'], '<source>\n')
        self.assertIn('P2 prototype', packet['input']['mapped_input']['statement'])
        self.assertEqual(set(packet['outputs']), {'A', 'B'})
        self.assertNotIn('v2', json.dumps(packet))
        self.assertIn(raw, [o.get('raw') for o in packet['outputs'].values()])
        self.assertEqual(result['blind_key'][packet['review_id']]['sample_id'], 'id')

    def test_preflight_failure_preserves_original_status_and_is_not_invalid_response(self):
        result = self.compare_fixture({'id': FEEDBACK_LEVELS[1]}, [generation('id', raw=None, finish_reason='not_called', status='context_preflight_failure', context_preflight={'prompt_tokens': 8000, 'allowance': 1000})], [{'sample_id': 'id', 'output': payload()}])
        output = result['rows'][0]['v2']
        self.assertEqual(output['original_generation_status'], 'context_preflight_failure')
        self.assertEqual(output['failure_phase'], 'preflight')
        self.assertFalse(output['response_invalid'])
        self.assertEqual(output['generation_diagnostics']['context_preflight']['prompt_tokens'], 8000)
        self.assertEqual(result['summary']['v2_failure_breakdown']['preflight'], 1)

    def test_fixed_progress_packets_do_not_select_risk_and_skip_unfinished(self):
        req = dict.fromkeys(['ready', 'unfinished', 'risk'], FEEDBACK_LEVELS[1])
        old = [{'sample_id': s, 'output': payload()} for s in req]
        result = prepare_fixed_packets(req, [binding(s) for s in req], [generation('ready'), generation('risk', ['Lỗi logic'])], old, LABELS, selection(['ready', 'unfinished']))
        self.assertEqual(result['selection_type'], 'fixed_only_inference_progress')
        self.assertEqual([p['sample_id'] for p in result['packets']], ['ready'])
        self.assertEqual(result['pending_fixed_ids'], ['unfinished'])
        self.assertEqual(len(result['blind_key']), 1)
        self.assertNotIn('risk_selection', result)

    def test_native_termination_overrules_cached_valid_payload(self):
        result = self.compare_fixture({'id': FEEDBACK_LEVELS[1]}, [generation('id', finish_reason='length', status='valid', parsed=payload())], [{'sample_id': 'id', 'output': payload()}])
        self.assertEqual(result['rows'][0]['v2']['status'], 'invalid')
        self.assertEqual(result['rows'][0]['v2']['parse_status'], 'length')
        self.assertIsNone(result['rows'][0]['v2']['payload'])
        self.assertEqual(result['summary']['transition_denominator_two_valid'], 0)

    def test_label_sets_ignore_order_and_language_is_only_a_flag(self):
        old = [{'sample_id': 'same', 'output': payload(['Lỗi logic', 'Lỗi vòng lặp'])}, {'sample_id': 'change', 'output': payload(['Lỗi logic'])}]
        gens = [generation('same', ['Lỗi vòng lặp', 'Lỗi logic']), generation('change', ['Lỗi vòng lặp'], raw=json.dumps(payload(['Lỗi vòng lặp'], 'Please inspect the loop.')))]
        result = self.compare_fixture(dict.fromkeys(['same', 'change'], FEEDBACK_LEVELS[1]), gens, old)
        self.assertFalse(result['rows'][0]['label_set_changed'])
        changed = result['rows'][1]
        self.assertTrue(changed['label_set_changed'])
        self.assertEqual(changed['v2']['status'], 'valid')
        self.assertEqual(changed['v2']['feedback']['characters'], 24)
        self.assertEqual(changed['v2']['feedback']['words'], 4)
        self.assertEqual(changed['v2']['feedback']['language_flag_heuristic'], 'no_vietnamese_specific_letters')
        self.assertFalse(result['summary']['semantic_review_performed'])

    def test_risk_priority_and_strict_long_feedback_cutoff(self):
        req = dict.fromkeys(['long', 'edge', 'transition'], FEEDBACK_LEVELS[1])
        gens = [generation('long', raw=json.dumps(payload([], 'đ' * 801))), generation('edge', raw=json.dumps(payload([], 'đ' * 800))), generation('transition', ['Lỗi logic'])]
        result = self.compare_fixture(req, gens, [{'sample_id': s, 'output': payload()} for s in req])
        self.assertEqual(result['risk_selection']['additional_ids'], ['transition', 'long'])
        self.assertEqual(result['rows'][1]['risk_reasons'], [])

    def test_run_verifies_candidate_hash_and_writes_escaped_casebook(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def dump(name, value):
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, ensure_ascii=False)); return path
            old = dump('old.json', [{'sample_id': 'id', 'output': payload()}])
            dump('requested-levels.private.json', {'id': FEEDBACK_LEVELS[1]})
            dump('official-contract.json', {'taxonomy_labels': LABELS})
            dump('review-selection.json', selection(['id']))
            (root / 'public-inputs.private.jsonl').write_text(json.dumps(binding('id')) + '\n')
            (root / 'generations.jsonl').write_text(json.dumps(generation('id', raw='<script>bad</script>')) + '\n')
            manifest = {'selected': {'candidate_path': str(old), 'sha256': 'wrong', 'provenance_confidence': 'fixture'}}
            dump('ar15-audit/comparator-manifest.json', manifest)
            with self.assertRaisesRegex(ValueError, 'hash'):
                run(root)
            self.assertFalse((root / 'public-comparison').exists())
            manifest['selected']['sha256'] = hashlib.sha256(old.read_bytes()).hexdigest()
            dump('ar15-audit/comparator-manifest.json', manifest)
            run(root)
            report = json.loads((root / 'public-comparison/comparison.json').read_text())
            self.assertEqual(report['targets'], 1)
            html = (root / 'public-comparison/casebook.html').read_text()
            self.assertIn('&lt;script&gt;bad&lt;/script&gt;', html)
            self.assertNotIn('<script>bad</script>', html)
            self.assertEqual(json.loads((root / 'public-comparison/comparison.jsonl').read_text())['sample_id'], 'id')
