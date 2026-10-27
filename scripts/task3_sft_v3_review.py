"""Source-grounded blinded packets, bounded code evidence, and sealed dev selection."""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import random
import re
import secrets
import shutil
import sys
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from src.task3.sft_v1 import read_jsonl,sha256
from src.task3.sft_v1_experiment import write_json,Journal
from src.task3.sft_v1_runtime import digest
from src.task3.sft_v3 import AXES,REVIEW_POLICY,CODE_POLICY,SELECTION_POLICY,joint_success,summarize,select_checkpoint
from src.task3.sft_v3_runtime import verify,validate_selection
from scripts.task3_sft_v3_prepare import records

STATES={'dev':[f'{state}-{mode}' for state in ('base','v2','v3-epoch1','v3-epoch2') for mode in ('dev','oracle-dev')],
        'final':['base-final','v2-final','v3-selected-final']}


def executable_verdict(detail):
    if detail['status']=='all_authored_tests_passed':return 'pass'
    if detail['status'] in ('started_no_retry','audit_error','not_evaluable','not_extractable'):return 'uncertain'
    return 'fail'


def code_checks(out,split):
    """Reuse the historical exact code extractor and bounded audit, never Qwen."""
    import scripts.task3_sft_v1_l4_audit as audit
    from scripts.task3_sft_v1_l4_unfenced_audit import extract_unfenced
    from src.task3.cpp_sandbox import CppSandbox
    if json.loads((out/'code-policy.json').read_text())!=CODE_POLICY:raise ValueError('code policy changed')
    if split=='final':validate_selection(REPO,out,json.loads((out/'manifest.json').read_text()))
    cases_path=REPO/('data/raw/task3-sft-v1/cases.private.json' if split=='dev' else 'data/raw/task3-sft-v2/cases.private.json')
    cases={c['sample_id']:c for c in json.loads(cases_path.read_text()) if c['split']==split}
    original=audit.extract_cpp
    def extract(feedback):
        found=original(feedback)
        return found if found['status']=='extracted' or '```' in feedback else extract_unfenced(feedback)
    directory=out/'code-evidence';directory.mkdir(exist_ok=True)
    provenance=dict(policy=CODE_POLICY,template=str(audit.TEMPLATE),template_ready_sha256=sha256(audit.TEMPLATE/'READY.json'),
        compiler_sha256=sha256(audit.TEMPLATE/'usr/bin/g++'),sandbox_sha256=sha256(REPO/'src/task3/cpp_sandbox.py'),
        extractor_sha256=sha256(REPO/'scripts/task3_sft_v1_l4_audit.py'),unfenced_extractor_sha256=sha256(REPO/'scripts/task3_sft_v1_l4_unfenced_audit.py'))
    provenance_path=directory/'runner-provenance.json'
    if provenance_path.exists() and json.loads(provenance_path.read_text())!=provenance:raise ValueError('bounded runner provenance differs')
    if not provenance_path.exists():write_json(provenance_path,provenance)
    sandbox=CppSandbox(audit.TEMPLATE);summary=[]
    try:
        audit.extract_cpp=extract
        for state in STATES[split]:
            if not (out/state/'complete.json').exists():raise ValueError('generation state incomplete '+state)
            for row in read_jsonl(out/state/'generations.jsonl'):
                target=directory/state/(row['example_id']+'.json')
                binding=dict(state=state,example_id=row['example_id'],generation_sha256=digest(row),case_sha256=digest(cases[row['sample_id']]))
                if target.exists():
                    result=json.loads(target.read_text())
                    if any(result.get(k)!=v for k,v in binding.items()):raise ValueError('existing code evidence changed')
                    summary.append(result);continue
                if row['status']!='valid':result=dict(**binding,status='not_evaluable',code_verdict='uncertain',compile_calls=0,runtime_calls=0)
                else:
                    feedback=row['parsed']['feedback'];extracted=extract(feedback)
                    if extracted['status']!='extracted':
                        present=('```' in feedback or bool(re.search(r'(?m)^\s*#include\b',feedback)))
                        result=dict(**binding,status='partial_or_unextractable' if present else 'absent',
                            code_verdict='uncertain' if present else 'absent',compile_calls=0,runtime_calls=0,
                            reason=extracted['reason'],semantic_review_required=present)
                    else:
                        # A result path is reserved durably by the existing audit before compilation.
                        existing_compile=sum(r.get('compile_calls',0) for p in directory.glob('*/*.json') for r in [json.loads(p.read_text())])
                        existing_runtime=sum(r.get('runtime_calls',0) for p in directory.glob('*/*.json') for r in [json.loads(p.read_text())])
                        if existing_compile>=1120 or existing_runtime+len(cases[row['sample_id']]['tests'])>25000:raise ValueError('bounded code call ceiling')
                        detail=audit.audit_target(row,cases[row['sample_id']],directory/'details'/state,sandbox)
                        if detail.get('jail') and Path(detail['jail']).exists():shutil.rmtree(detail['jail'])
                        cv=executable_verdict(detail)
                        result=dict(**binding,status=detail['status'],code_verdict=cv,
                            compile_calls=int(detail.get('compile') is not None),runtime_calls=sum(t.get('executed',False) for t in detail['tests']),
                            detail_path=str((directory/'details'/state/row['example_id']/'result.json').relative_to(out)),
                            failure_test_indices=[t['test_index'] for t in detail['tests'] if t.get('status') not in ('pass','not_run')])
                write_json(target,result);summary.append(result)
                if result['compile_calls']:print(json.dumps(dict(state=state,eid=row['example_id'],code=result['status'])),flush=True)
    finally:audit.extract_cpp=original
    write_json(directory/f'{split}-summary.json',dict(targets=len(summary),counts=dict(Counter(r['status'] for r in summary)),
        compile_calls=sum(r['compile_calls'] for r in summary),runtime_calls=sum(r['runtime_calls'] for r in summary),policy=CODE_POLICY))


def packets(out,split):
    root=REPO/'data/raw/task3-sft-v3';source_records=read_jsonl(root/f'{split}.records.jsonl')
    by_source={}
    for r in source_records:by_source.setdefault(r['source_id'],r)
    generations={state:{r['example_id']:r for r in read_jsonl(out/state/'generations.jsonl')} for state in STATES[split]}
    for state in STATES[split]:
        if len(generations[state])!=len(source_records) or not (out/state/'complete.json').exists():raise ValueError('incomplete state '+state)
    oracle={r['source_id']:r for r in records(root/'oracle-dev.private.json')} if split=='dev' else {}
    directory=out/'review-packets';directory.mkdir(exist_ok=True)
    salt_path=directory/f'{split}-blinding-salt.private.txt'
    if not salt_path.exists():
        with salt_path.open('x') as stream:stream.write(secrets.token_hex(32))
    salt=salt_path.read_text()
    binding={};pack=[];rng=random.Random(20261026)
    for sid,record in by_source.items():
        x=record['input'];groups={}
        for state in STATES[split]:
            for level in (1,2,3,4):
                eid=f'{sid}-L{level}';row=generations[state][eid]
                rid=hashlib.sha256((salt+'|'+split+'|'+state+'|'+eid).encode()).hexdigest()[:24]
                evidence=json.loads((out/'code-evidence'/state/(eid+'.json')).read_text())
                binding[rid]=dict(state=state,example_id=eid,sample_id=sid,level=level,status=row['status'],generation_sha256=digest(row))
                key=digest(dict(level=level,status=row['status'],raw=row['raw']))
                if key not in groups:
                    groups[key]=dict(review_ids=[],level=level,status=row['status'],raw=row['raw'],parsed=row['parsed'],
                        code_evidence={k:v for k,v in evidence.items() if k not in ('state','example_id','generation_sha256','case_sha256','detail_path')})
                groups[key]['review_ids'].append(rid)
        panels=list(groups.values());rng.shuffle(panels)
        for i,p in enumerate(panels):p['panel']=i+1
        pack.append(dict(sample_id=sid,statement=x['statement'],code=x['code'],syntax_only=x['compile_log'],
            reviewed_findings=oracle.get(sid),responses=panels,
            historical_taxonomy=record['output']['taxonomy_error'],review_caution='Historical taxonomy alone is not evidence; read source and specification.'))
    directory=out/'review-packets';directory.mkdir(exist_ok=True)
    write_json(directory/f'{split}-binding.private.json',binding)
    for i in range(3):write_json(directory/f'{split}-{i}.private.json',pack[i::3])
    write_json(directory/f'{split}-instructions.json',dict(policy=REVIEW_POLICY,axes=list(AXES),
        record_schema='{review_ids:[all exact duplicated response IDs],axes:{each named axis: verdict},code_verdict:pass|fail|absent|uncertain,evidence:source+spec+response evidence}',
        invalid='every semantic axis not_evaluable; code uncertain; keep invalid target in denominators',
        calibration='L2 may use multiple sentences and diagnostic identifiers/defective expressions; no replacement instructions/code. A precise cause that implies the fix is allowed. L3 localized actionable hints allowed; reject full standalone solution. Wrong hint fails repair, not automatically disclosure. Clean may be truthfully praised at every Level without fictitious location/repair. L4 absence of code alone is permitted. Unsupported praise on faulty source fails supported assessment/coverage. Any supplied incorrect code fails joint. Verify essential conditions, avoid inferring semantics from taxonomy, keywords, length, target wording or test success alone.',
        method='Read every source, requirements and actual response; blind state and probe identity where practical. Exact same source/Level/raw is adjudicated once and expanded to all listed IDs with provenance; do not edit responses. Agent review, not independent human gold.'))
    print(json.dumps(dict(split=split,sources=len(pack),targets=len(binding),unique_response_panels=sum(len(p['responses']) for p in pack))),flush=True)


def validate_review_ids(ids,groups):
    if not ids or len(ids)!=len(set(ids)) or ids[0] not in groups or frozenset(ids)!=groups[ids[0]]:
        raise ValueError('verdict must cover exactly one complete identical-source/Level/raw response group')
    if any(groups.get(rid)!=groups[ids[0]] for rid in ids):raise ValueError('response group mismatch')
    return True


def resolved_code_verdict(observed,verdict):
    value=verdict.get('code_verdict',observed)
    if value not in ('pass','fail','absent','uncertain'):raise ValueError('code verdict')
    if observed=='fail':return 'fail'
    if observed in ('pass','uncertain') and value=='absent':raise ValueError('supplied code cannot be declared absent')
    if observed=='uncertain' and value=='pass' and not verdict.get('code_resolution_evidence','').strip():
        raise ValueError('resolving uncertain supplied code needs explicit source-grounded evidence')
    return value


def oracle_fidelity_level(row):
    if row['status']!='valid':return False
    axes=row['axes']
    if any(axes.get(k)!='pass' for k in ('diagnosis_supported','coverage','factual_fidelity','level_compliance','vietnamese_compliance')):return False
    if row['faulty'] and row['level']>1 and axes.get('location_and_condition')!='pass':return False
    return row['code_verdict'] in ('pass','absent')


def reviewed_rows(out,split):
    binding=json.loads((out/'review-packets'/f'{split}-binding.private.json').read_text());found={}
    groups={}
    for i in range(3):
        for source in json.loads((out/'review-packets'/f'{split}-{i}.private.json').read_text()):
            for panel in source['responses']:
                for rid in panel['review_ids']:groups[rid]=frozenset(panel['review_ids'])
    allowed={'pass','fail','uncertain','not_applicable','not_evaluable'}
    for path in sorted((out/'quality').glob(f'{split}-*.json')):
        content=json.loads(path.read_text());content=content if isinstance(content,list) else content.get('records',content.get('reviews'))
        for verdict in content:
            ids=verdict.get('review_ids',[verdict.get('review_id')]);axes=verdict.get('axes',verdict.get('dimensions'))
            validate_review_ids(ids,groups)
            if set(axes)!=set(AXES) or not set(axes.values())<=allowed or not isinstance(verdict.get('evidence'),str) or not verdict['evidence'].strip():raise ValueError('review schema '+str(path))
            for rid in ids:
                if rid not in binding or rid in found:raise ValueError('duplicate/foreign review id '+str(rid))
                b=binding[rid];row={r['example_id']:r for r in read_jsonl(out/b['state']/'generations.jsonl')}[b['example_id']]
                if digest(row)!=b['generation_sha256']:raise ValueError('reviewed output changed')
                if b['status']!='valid' and set(axes.values())!={'not_evaluable'}:raise ValueError('invalid semantic verdicts')
                code=json.loads((out/'code-evidence'/b['state']/(b['example_id']+'.json')).read_text())
                cv=resolved_code_verdict(code['code_verdict'],verdict)
                found[rid]=dict(**b,review_id=rid,axes=axes,code_verdict=cv,evidence=verdict['evidence'],parsed=row['parsed'],raw=row['raw'],
                    code_resolution_evidence=verdict.get('code_resolution_evidence',''),review_type='source-grounded agent review; not independent human gold')
    if set(found)!=set(binding):raise ValueError(f'review coverage {len(found)}/{len(binding)}')
    source_rows=read_jsonl(REPO/'data/raw/task3-sft-v3'/f'{split}.records.jsonl')
    faulty={r['source_id']:bool(r['output']['taxonomy_error']) for r in source_rows}
    for r in found.values():r['faulty']=faulty[r['sample_id']]
    return list(found.values())


def metrics(out,split):
    rows=reviewed_rows(out,split);result={}
    for state in STATES[split]:
        subset=[r for r in rows if r['state']==state]
        result[state]=dict(overall=summarize(subset),by_level={str(l):summarize([r for r in subset if r['level']==l]) for l in (1,2,3,4)},
            by_level_status={str(l):{name:summarize([r for r in subset if r['level']==l and r['faulty']==flag]) for name,flag in [('clean',False),('faulty',True)]} for l in (1,2,3,4)},
            by_status={name:summarize([r for r in subset if r['faulty']==flag]) for name,flag in [('clean',False),('faulty',True)]})
    for state in STATES[split]:
        subset=[r for r in rows if r['state']==state]
        result[state]['overall']['oracle_fidelity_level_successful']=sum(oracle_fidelity_level(r) for r in subset)
        for level in (1,2,3,4):result[state]['by_level'][str(level)]['oracle_fidelity_level_successful']=sum(oracle_fidelity_level(r) for r in subset if r['level']==level)
    directory=out/'reviewed';directory.mkdir(exist_ok=True)
    write_json(directory/f'{split}-verdicts.private.json',rows);write_json(directory/f'{split}-metrics.json',result)
    return result


def select(out):
    manifest=json.loads((out/'manifest.json').read_text());verify(REPO,out,manifest)
    if (out/'selection.json').exists():raise FileExistsError('selection already persisted')
    if any((out/state).exists() for state in STATES['final']):raise ValueError('final outputs existed before selection')
    values=metrics(out,'dev');candidates=[]
    for epoch,step in enumerate(manifest['steps']['checkpoints'],1):
        state=f'v3-epoch{epoch}';c=dict(step=step,**values[state+'-dev']['overall'])
        c['oracle_joint']=values[state+'-oracle-dev']['overall']['oracle_fidelity_level_successful']
        c['mean_loss']=json.loads((out/(state+'-dev')/'complete.json').read_text())['mean_loss'];candidates.append(c)
    result=select_checkpoint(candidates,values['v2-dev']['overall'])
    evidence={}
    for state in STATES['dev']:
        for name in ('complete.json','generations.jsonl','losses.jsonl','state-binding.json'):evidence[f'{state}/{name}']=sha256(out/state/name)
    for folder,pattern in [('quality','dev-*.json'),('review-packets','dev-*.json'),('reviewed','dev-*.json'),('code-evidence','**/*')]:
        for p in (out/folder).glob(pattern):
            if not p.is_file():continue
            evidence[str(p.relative_to(out))]=sha256(p)
    evidence['oracle-metric-definition.json']=sha256(out/'oracle-metric-definition.json')
    evidence['review-code-identity.json']=sha256(out/'review-code-identity.json')
    evidence['review-packets/dev-blinding-salt.private.txt']=sha256(out/'review-packets/dev-blinding-salt.private.txt')
    result.update(dev_only=True,manifest_sha256=sha256(out/'manifest.json'),final_outputs_absent_at_selection=True,
        checkpoint=str(out/'main'/f"checkpoint-{result['step']}"),dev_evidence=evidence)
    write_json(out/'selection.json',result);write_json(out/'selection.sha256.json',dict(sha256=sha256(out/'selection.json')))
    validate_selection(REPO,out,manifest)
    Journal(out/'journal.jsonl').append(dict(type='dev_selection_persisted',step=result['step'],selection_sha256=sha256(out/'selection.json'),eligible=result['passes_preliminary_conditions']))
    print(json.dumps(dict(step=result['step'],eligible=result['passes_preliminary_conditions'],failures=result['eligibility_failures'])),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['code','packets','metrics','select']);ap.add_argument('--split',choices=['dev','final'],default='dev');ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();out=a.out.resolve()
    if a.split=='final':validate_selection(REPO,out,json.loads((out/'manifest.json').read_text()))
    if a.stage=='code':code_checks(out,a.split)
    elif a.stage=='packets':packets(out,a.split)
    elif a.stage=='metrics':metrics(out,a.split)
    else:select(out)
