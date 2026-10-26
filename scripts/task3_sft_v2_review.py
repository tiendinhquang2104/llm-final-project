"""Offline review packets, bounded L4 checks and immutable dev selection."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import shutil
import sys
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from src.task3.sft_v1 import read_jsonl,sha256
from src.task3.sft_v1_experiment import write_json
from src.task3.sft_v2 import load_split,joint_success,select_checkpoint,SELECTION_POLICY
from src.task3.sft_v1_runtime import verify_frozen

STATES={'dev':['ar15-dev','base-dev','v1-dev','step-120-dev','step-240-dev'],
        'final':['ar15-final','base-final','v1-final','v2-final'],
        'test':['base-regression','v1-regression','v2-regression']}
AXES=['diagnosis_supported','location_and_condition','unsupported_defects','level_compliance',
      'vietnamese_compliance','l3_repair_direction','l4_explanation_quality']
L4_POLICY=dict(version='v2-l4-frozen-v1',extraction='Exactly one complete cpp/c++/cxx/bare fence; otherwise zero backticks and exact substring from first line-start #include through original end, ending in closing brace. No repair.',
    checker='Original case tokens or exact_bytes; original harness appended unchanged',
    scope='finite authored specification cases; no proof of full correctness',
    max_targets=320,max_compile_calls=320,max_runtime_calls=12000,retries=0,
    runner='existing CppSandbox with existing CPU/time/memory/output/process limits',
    explanation='separate source-grounded agent verdict; passing code never overrides wrong prose')


def packets(out,split):
    root=REPO/'data/raw/task3-sft-v2';records=read_jsonl(root/f'{split}.records.jsonl')
    examples=load_split(root,split);by_sid={}
    generations={state:{r['example_id']:r for r in read_jsonl(out/state/'generations.jsonl')} for state in STATES[split]}
    binding={};rng=random.Random(20261026);pack=[]
    for r in records:
        sid=r['source_id']
        if sid in by_sid:continue
        x=r['input'];entries=[];arms=STATES[split].copy();rng.shuffle(arms)
        for state in arms:
            for level in range(1,5):
                eid=f'{sid}-L{level}';row=generations[state][eid]
                rid=hashlib.sha256((split+'|'+state+'|'+eid).encode()).hexdigest()[:20]
                binding[rid]=dict(state=state,example_id=eid,sample_id=sid,level=level,status=row['status'])
                entries.append(dict(review_id=rid,arm='Panel '+str(arms.index(state)+1),level=level,status=row['status'],
                    feedback=row['parsed']['feedback'] if row['status']=='valid' else None,
                    taxonomy=row['parsed']['taxonomy_error'] if row['status']=='valid' else None))
        by_sid[sid]=True;pack.append(dict(sample_id=sid,statement=x['statement'],code=x['code'],
            syntax_only=x['compile_log'],gold_taxonomy=r['output']['taxonomy_error'],responses=entries))
    directory=out/'review-packets';directory.mkdir(exist_ok=True)
    write_json(directory/f'{split}-binding.private.json',binding)
    for i in range(3):write_json(directory/f'{split}-{i}.private.json',pack[i::3])
    write_json(directory/f'{split}-instructions.json',dict(axes=AXES,selection_policy=SELECTION_POLICY,
        verdicts=['pass','fail','uncertain','not_applicable','not_evaluable'],
        method='Read every source/specification and actual response. Each output row {review_id,dimensions:{all axes},evidence: concrete source/spec/feedback evidence}. Invalid all not_evaluable. No keywords/exact gold wording grader. Identity hidden. Explanation and executable code checked separately.',
        calibration='Clean L3 status-only: diagnosis pass, Level fail, repair N/A. Faulty L3 generic check-again is not concrete repair. L1 location N/A; true clean status location N/A. A diagnosis may imply a repair without violating L2. A supported taxonomy does not excuse false prose. L4 explanation pass only accurate relevant prose; code may independently pass or fail.'))


def l4(out,split):
    import scripts.task3_sft_v1_l4_audit as old
    from scripts.task3_sft_v1_l4_unfenced_audit import extract_unfenced
    root=REPO/'data/raw/task3-sft-v2';cases={c['sample_id']:c for c in json.loads((root/'cases.private.json').read_text())}
    destination=out/'l4';destination.mkdir(exist_ok=True)
    frozen=out/'l4-policy.json'
    if not frozen.exists():raise ValueError('L4 extraction policy must be frozen before inference')
    if json.loads(frozen.read_text())!=L4_POLICY:raise ValueError('L4 frozen policy changed')
    original=old.extract_cpp
    def combined(feedback):
        result=original(feedback)
        return result if result['status']=='extracted' or '```' in feedback else extract_unfenced(feedback)
    old.extract_cpp=combined;sandbox=old.CppSandbox(old.TEMPLATE)
    try:
        for state in STATES[split]:
            results=[]
            for row in read_jsonl(out/state/'generations.jsonl'):
                if row['level']!=4:continue
                result=old.audit_target(row,cases[row['sample_id']],destination/state,sandbox)
                if result.get('jail') and Path(result['jail']).exists():shutil.rmtree(result['jail'])
                results.append(result)
            write_json(destination/f'{state}.summary.json',dict(targets=len(results),status_counts=dict(Counter(r['status'] for r in results)),
                compile_calls=sum(r['compile'] is not None for r in results),runtime_calls=sum(t.get('executed',False) for r in results for t in r['tests']),
                scope=L4_POLICY))
    finally:old.extract_cpp=original


def reviews(out,split):
    binding=json.loads((out/'review-packets'/f'{split}-binding.private.json').read_text());found={}
    allowed={'pass','fail','uncertain','not_applicable','not_evaluable'}
    for path in sorted((out/'quality').glob(f'{split}-*.json')):
        for row in json.loads(path.read_text()):
            rid=row['review_id']
            if rid not in binding or rid in found:raise ValueError('duplicate/foreign review ID '+rid)
            if set(row['dimensions'])!=set(AXES) or not set(row['dimensions'].values())<=allowed or not row['evidence'].strip():raise ValueError('review schema')
            source=binding[rid]
            if source['status']!='valid' and set(row['dimensions'].values())!={'not_evaluable'}:raise ValueError('invalid semantic verdict')
            found[rid]=dict(row,**source,review_type='agent_review_not_independent_gold')
    if set(found)!=set(binding):raise ValueError(f'review coverage {len(found)}/{len(binding)}')
    return {(r['state'],r['example_id']):r for r in found.values()}


def summarize(out,split):
    examples=load_split(REPO/'data/raw/task3-sft-v2',split);quality=reviews(out,split);result={}
    for state in STATES[split]:
        generated={r['example_id']:r for r in read_jsonl(out/state/'generations.jsonl')}
        summary=json.loads((out/state/'complete.json').read_text());joint=[];repairs=[];verdicts={a:Counter() for a in AXES}
        for e in examples:
            row=generated[e['example_id']];q=quality[state,e['example_id']];faulty=bool(json.loads(e['completion'])['taxonomy_error'])
            for a,v in q['dimensions'].items():verdicts[a][v]+=1
            code=None
            if e['level']==4:
                audit=json.loads((out/'l4'/state/e['example_id']/'result.json').read_text())
                code='pass' if audit['status']=='all_authored_tests_passed' else 'fail'
            success=joint_success(row['status'],e['level'],faulty,q['dimensions'],code)
            if success:joint.append(e['example_id'])
            if faulty and e['level']==3 and q['dimensions']['l3_repair_direction']=='pass' and row['status']=='valid':repairs.append(e['example_id'])
        result[state]=dict(targets=len(examples),joint_successful=len(joint),joint_ids=joint,faulty_l3_correct=len(repairs),faulty_l3_ids=repairs,
            dimensions={a:dict(c) for a,c in verdicts.items()},mean_loss=summary.get('mean_loss'),
            clean_false_alarms=summary['metrics']['clean_false_alarms']['targets']['false_alarms'],invalid=summary['metrics']['invalid_outputs'])
    write_json(out/f'{split}-semantic-summary.json',result);return result


def select(out):
    if (out/'selection.json').exists():raise FileExistsError('selection already persisted')
    if any((out/state/'generations.jsonl').exists() for state in STATES['final']):raise ValueError('final outputs existed before selection')
    manifest=json.loads((out/'manifest.json').read_text());verify_frozen(REPO,out,manifest)
    summary=summarize(out,'dev')
    candidates=[dict(summary[f'step-{step}-dev'],step=step) for step in (120,240)]
    decision=select_checkpoint(candidates,summary['base-dev']['clean_false_alarms'],summary['base-dev']['invalid'])
    decision.update(checkpoint=str(out/'main'/f"checkpoint-{decision['step']}"),dev_only=True,
        review_files={str(p.relative_to(out)):sha256(p) for p in (out/'quality').glob('dev-*.json')},
        dev_artifacts={str(p.relative_to(out)):sha256(p) for state in STATES['dev'] for p in (out/state).glob('*.json*')},
        l4_files={str(p.relative_to(out)):sha256(p) for state in STATES['dev'] for p in (out/'l4'/state).glob('*/result.json')},
        final_outputs_absent_at_selection=True,manifest_sha256=sha256(out/'manifest.json'))
    write_json(out/'selection.json',decision)
    write_json(out/'selection.sha256.json',dict(sha256=sha256(out/'selection.json')))
    from src.task3.sft_v2 import BudgetJournal
    BudgetJournal(out/'journal.jsonl').append(dict(type='selection_persisted',step=decision['step'],sha256=sha256(out/'selection.json')))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['packets','l4','summarize','select']);ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--split',choices=STATES,default='dev');args=ap.parse_args()
    if args.stage=='select':select(args.out.resolve())
    else:globals()[args.stage](args.out.resolve(),args.split)
