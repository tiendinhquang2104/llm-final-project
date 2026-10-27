"""Final offline evidence audit for the bounded V4 diagnostic experiment."""
import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.task3_sft_v4 import OUT, cell_map, load, verify
from src.task3.sft_v1 import read_jsonl, sha256
from src.task3.sft_v1_experiment import write_json
from src.task3.sft_v4 import EvaluationJournal, choose_checkpoint, metrics
from src.task3.prompt_crossover import validate_population, validate_durable_rows
from src.task3.sft_v1_runtime import digest


def run(out):
    m = verify(out)
    initial = load(out / 'initial-workspace-state.json')
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    assert branch == initial['branch'] == 'fix/task3-strict-feedback'
    assert head == initial['head']
    historical = load(out / 'audit/historical-preservation.json')['files']
    for name, expected in historical.items():
        assert sha256(Path(name)) == expected, ('historical file changed', name)
    tr = load(out / 'main/training-result.json')
    for key in ['actual_optimizer_steps', 'actual_scheduler_steps', 'actual_optimizer_state_steps']:
        assert tr[key] == 96
    assert tr['actual_train_forward_calls'] == 384 and tr['actual_epochs'] == 1
    assert tr['all_base_parameters_frozen'] and tr['changed_adapter_tensors'] > 0
    assert load(out / 'main-base-weight-audit.json')['all_non_adapter_parameter_bytes_unchanged']
    init = load(out / 'main-initialization.json')
    assert init['from_pinned_base'] and not init['loaded_V3'] and not init['merged'] and not init['stacked']
    assert init['optimizer_smoke_steps'] == 0
    actual_args = load(out / 'main/actual-training-arguments.json')
    assert all(actual_args[k] == v for k, v in m['training_arguments'].items())
    peft = load(out / 'main/peft-config.json')
    assert (peft['r'], peft['lora_alpha'], peft['lora_dropout'], peft['bias']) == (16, 32, .05, 'none')
    assert set(peft['target_modules']) == set(m['adapter_configuration']['target_modules'])
    for step in [48, 96]:
        cp = out / 'main' / f'checkpoint-{step}'
        for name, expected in load(cp / 'checkpoint-identity.json').items():
            assert sha256(cp / name) == expected, ('checkpoint changed', step, name)
        for name in ['optimizer.pt', 'scheduler.pt', 'rng_state.pth', 'adapter_model.safetensors']:
            assert (cp / name).is_file()
        assert load(cp / 'trainer_state.json')['global_step'] == step
    j = EvaluationJournal(out / 'journal.jsonl', cell_map(out))
    events = j.events()
    assert len(j.reserved()) == 504
    assert len([e for e in events if e.get('type') == 'optimizer_completed']) == 96
    forwards = [e for e in events if e.get('type') == 'train_forward']
    assert len(forwards) == 384
    train_ids = {r['example_id'] for r in read_jsonl(out / 'dataset/train.examples.private.jsonl')}
    assert Counter(e['example_id'] for e in forwards) == Counter({i: 1 for i in train_ids})
    counts = Counter(k.rsplit('/', 1)[0] for k in j.reserved())
    assert counts == Counter({k: 72 for k in cell_map(out)})
    inputs = {r['example_id']: r for r in read_jsonl(out / 'preflight/input-ids.private.jsonl')}
    examples_all = {r['example_id']: r for s in ['dev', 'test'] for r in read_jsonl(out / f'dataset/{s}.examples.private.jsonl')}
    bindings = [e for e in events if e.get('type') == 'input_binding']
    assert len(bindings) == 504 and {e['key'] for e in bindings} == j.reserved()
    for b in bindings:
        eid = b['key'].rsplit('/', 1)[1]
        assert b['prompt_sha256'] == digest(examples_all[eid]['prompt'])
        assert b['token_id_sha256'] == digest(inputs[eid]['input_ids']) == inputs[eid]['token_id_sha256']
        assert b['input_tokens'] == inputs[eid]['input_tokens']
        assert b['manifest_sha256'] == sha256(out / 'manifest.json')
    sel = load(out / 'selection.json')
    assert sha256(out / 'selection.json') == load(out / 'selection.sha256.json')['sha256']
    assert sel['dev_only'] and sel['test_reservations_before_selection'] == 0
    test_times = [e['utc'] for e in events if e.get('type') == 'generation_reserved' and e['key'].startswith('test/')]
    assert test_times and datetime.fromisoformat(sel['created_utc']) < min(datetime.fromisoformat(t) for t in test_times)
    for name, expected in sel['dev_evidence'].items():
        assert sha256(Path(name)) == expected, ('selected dev evidence changed', name)
    allmetrics = {}
    unknowns = []
    review_count = 0
    for split, cells in [('dev', ['base', 'V3', 'step48', 'step96']), ('test', ['base', 'V3', 'selected'])]:
        allmetrics[split] = {}
        examples = read_jsonl(out / f'dataset/{split}.examples.private.jsonl')
        expected_ids = {e['example_id'] for e in examples}
        for c in cells:
            d = out / split / c
            gg = read_jsonl(d / 'generations.jsonl')
            rr = read_jsonl(d / 'reviews.private.jsonl')
            assert len(gg) == len(rr) == 72
            assert {r['example_id'] for r in gg} == {r['example_id'] for r in rr} == expected_ids
            validate_population(gg, examples)
            validate_durable_rows(gg, examples, j, f'{split}/{c}')
            assert load(d / 'complete.json')['base_bytes_unchanged']
            gi = {r['example_id']: r for r in gg}
            for r in rr:
                assert all(r.get(k) == v for k, v in gi[r['example_id']].items())
                for key in ['unsupported_claims', 'taxonomy_feedback_contradiction']:
                    assert type(r[key]) is bool or r[key] in ['uncertain', 'not_evaluable']
                if r['status'] != 'valid':
                    assert all(v == 'not_evaluable' for v in r['axes'].values())
                    assert r['correct_status'] == 'not_evaluable' and r['code_verdict'] == 'uncertain'
                fields = {k: v for k, v in r['axes'].items() if v in ['uncertain', 'not_evaluable']}
                fields.update({k: r[k] for k in ['correct_status', 'unsupported_claims', 'taxonomy_feedback_contradiction', 'code_verdict'] if r[k] in ['uncertain', 'not_evaluable']})
                if fields or r.get('call_count_uncertain'):
                    unknowns.append(dict(split=split, system=c, example_id=r['example_id'], review_id=r['review_id'], status=r['status'], unresolved=fields, call_count_uncertain=r.get('call_count_uncertain', False), evidence=r['evidence']))
            allmetrics[split][c] = metrics(rr)
            review_count += len(rr)
        folder = out / 'blind' / split
        for seal_name in ['packet-seal.json', 'verdict-seal.json']:
            for name, expected in load(folder / seal_name).items():
                assert sha256(folder / name) == expected, ('blind artifact changed', split, name)
    assert allmetrics == load(out / 'metrics.json')
    assert allmetrics['dev'] == load(out / 'dev-metrics.json')
    candidates = [dict(step=step, **allmetrics['dev'][f'step{step}']['selection_counts']) for step in [48, 96]]
    replay = choose_checkpoint(candidates, allmetrics['dev']['V3']['selection_counts'])
    assert all(sel[k] == v for k, v in replay.items())
    examples = load(out / 'example-selection.json')['examples']
    assert len({(e['split'], e['family_id'], e['level']) for e in examples if e['split']}) >= 8
    if any(r['useful_l3_repair']['count'] > 0 for cc in allmetrics.values() for r in cc.values()):
        repair_example = next(e for e in examples if e['category'] == 'correct_L3_repair')
        assert repair_example['split'] and repair_example['correct_repair_systems']
    book = (out / 'paired-casebook.html').read_text()
    assert book.count('<section class="case"') == 144
    assert book.count('<article class="system-panel"') == 504
    costs = load(out / 'costs-and-runtime.json')
    assert costs['generations']['reservations'] == 504
    assert costs['training_steps'] == 96 and costs['optimizer_smoke_steps'] == 0
    assert costs['train_forward_calls'] == 384 and costs['teacher_forced_evaluation_forwards'] == 0
    for name in ['REPORT.vi.md', 'EXAMPLES.vi.md', 'reproduction-and-resume.json', 'dataset/DATA_CARD.md']:
        assert (out / name).is_file()
    write_json(out / 'uncertainty-records.private.json', dict(count=len(unknowns), records=unknowns, policy='Preserved as unresolved; never promoted to pass. Invalid not_evaluable outcomes remain in every primary denominator.'))
    result = dict(status='passed', created_utc=datetime.now(timezone.utc).isoformat(), branch=branch, head=head,
        historical_files_unchanged=len(historical), optimizer_steps=96, train_forwards=384, checkpoints=[48, 96],
        evaluation_reservations=504, reviewed_outputs=review_count, unique_targets=144, casebook_panels=504,
        selected_step=sel['step'], dev_only_selection_before_test=True, unresolved_records=len(unknowns),
        scope='Offline byte/binding/budget/metric/selection/preservation audit; semantic verdicts remain authored-agent judgments.')
    write_json(out / 'final-verification.json', result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, default=OUT)
    run(p.parse_args().out.resolve())
