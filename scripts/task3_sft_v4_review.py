"""Opaque source-grounded review packets and verified verdict joins. No semantic guessing."""
import argparse,json,hashlib,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.task3.sft_v1 import read_jsonl,sha256
from src.task3.sft_v1_experiment import write_json
from src.task3.prompt_crossover import AXES,validate_population
from src.task3.sft_v4 import metrics
from scripts.task3_sft_v4 import OUT,load,verify
from scripts.task3_fresh_eval import jsonl


def packets(out,split):
    verify(out)
    cells=['base','V3','step48','step96'] if split=='dev' else ['base','V3','selected']
    folder=out/'blind'/split
    if folder.exists():raise FileExistsError('review packets already created')
    folder.mkdir(parents=True)
    sources={r['sample_id']:r for r in read_jsonl(out/'dataset/sources.private.jsonl') if r['split']==split}
    gold={r['sample_id']:r for r in read_jsonl(out/'dataset/gold.private.jsonl') if r['split']==split}
    examples=read_jsonl(out/f'dataset/{split}.examples.private.jsonl');ei={e['example_id']:e for e in examples}
    families=sorted({r['family_id'] for r in sources.values()},key=lambda f:hashlib.sha256(f.encode()).hexdigest())
    group={f:i%3+1 for i,f in enumerate(families)};packets={i:[] for i in range(1,4)};identity={}
    for cell in cells:
        if not (out/split/cell/'complete.json').exists():raise ValueError('complete cell first')
        rows=read_jsonl(out/split/cell/'generations.jsonl');validate_population(rows,examples)
        for r in rows:
            e=ei[r['example_id']];s=sources[r['sample_id']];g=gold[r['sample_id']]
            rid=hashlib.sha256(f'v4-review-42/{split}/{cell}/{r["example_id"]}'.encode()).hexdigest()[:24]
            identity[rid]=dict(cell=cell,example_id=r['example_id'],generation_sha256=sha256(out/split/cell/'generations.jsonl'))
            evidence=load(out/g['evidence_path'])
            packet=dict(review_id=rid,example_id=r['example_id'],sample_id=r['sample_id'],family_id=s['family_id'],level=r['level'],
                specification=s['statement'],source=s['code'],allowed_syntax_diagnostics=load(out/'dataset/syntax.private.json')[r['sample_id']]['diagnostic'],
                response=dict(raw=r['raw'],parsed=r['parsed'],status=r['status'],finish_reason=r['finish_reason']),
                gold=g,private_evidence=evidence,
                review_notice='Source/spec/evidence private; model never received gold/witness/reference. Agent-authored observed synthetic data, no independent human claim.')
            packets[group[s['family_id']]].append(packet)
    for i,rows in packets.items():
        random.Random(42+i).shuffle(rows);write_json(folder/f'packet-{i}.private.json',rows)
    write_json(folder/'identity-map.private.json',identity)
    write_json(folder/'instructions.json',dict(axes=list(AXES),verdict_values=['pass','fail','uncertain','not_applicable','not_evaluable'],
        required_fields=['review_id','axes','correct_status','unsupported_claims','taxonomy_feedback_contradiction','code_verdict','evidence'],
        method='Read complete source/spec/gold/evidence and each response. Do not open identity map or generation directories until verdicts are fixed; no keyword/length/exact-gold judging. Explain concrete claims and conditions.',
        invalid='All nine semantic axes not_evaluable, correct_status not_evaluable; code uncertain, contradiction not_evaluable, unsupported_claims not_evaluable.',
        status='Separate textual overall status from taxonomy presence. Empty labels do not prove clean. Syntax-only/neutral behavior statements may leave status not_evaluable. A wrong mechanism can still correctly say a faulty program has a problem, but supported diagnosis must fail.',
        clean='Truthful clean assertion and no invented extra facts/defect. No repair needed. Material extra false explanation fails factual_fidelity, independently of clean label correctness.',
        L1='Status/praise only; no location/cause/repair. Do not require prohibited detail.',
        L2='Precise location/cause/trigger conditions permitted; no concrete repair/replacement/code. Multiple sentences allowed. Merely contrasting wrong expression vs required semantics can be diagnosis, do not over-penalize precision.',
        L3='Diagnosis+actionable useful correct repair; no full solution. Generic check logic fails useful repair. Keep ambiguous meaning uncertain; do not supply missing structure for the model.',
        evidence='One explicit per-response reason grounded in actual source, conditions and response; false praise not success; nonempty wrong diagnosis not detection.',
        additional_tests='Only concrete new unresolved repair claims need existing CppSandbox tests; request parent if needed. Do not run C++ directly.',
        no_prohibited_actions='Review only: no model calls, training, git operations or other artifact edits.'))
    write_json(folder/'packet-seal.json',{f'packet-{i}.private.json':sha256(folder/f'packet-{i}.private.json') for i in packets})
    print(json.dumps(dict(stage='review_packets',split=split,sizes={i:len(r) for i,r in packets.items()})))


def combine(out,split):
    verify(out);folder=out/'blind'/split;identity=load(folder/'identity-map.private.json');seen={};verdicts=[]
    for i in range(1,4):
        packet=load(folder/f'packet-{i}.private.json');reviews=load(folder/f'verdicts-{i}.private.json')
        if {r['review_id'] for r in reviews}!={r['review_id'] for r in packet} or len(reviews)!=len(packet):raise ValueError('review packet exact coverage')
        for r in reviews:
            rid=r['review_id']
            if rid in seen or rid not in identity:raise ValueError('duplicate/foreign review')
            if set(r['axes'])!=set(AXES) or any(v not in ['pass','fail','uncertain','not_applicable','not_evaluable'] for v in r['axes'].values()):raise ValueError('unfinished semantic axes')
            if not isinstance(r['evidence'],str) or not r['evidence'].strip():raise ValueError('reason required')
            if r.get('correct_status') not in ['pass','fail','uncertain','not_evaluable']:raise ValueError('status required')
            if r.get('code_verdict') not in ['pass','fail','absent','uncertain']:raise ValueError('code verdict')
            seen[rid]=r;verdicts.append(r)
    gold={r['sample_id']:r for r in read_jsonl(out/'dataset/gold.private.jsonl')}
    allrows={}
    for cell in sorted({v['cell'] for v in identity.values()}):
        gen=read_jsonl(out/split/cell/'generations.jsonl');index={r['example_id']:r for r in gen};rows=[]
        for rid,binding in identity.items():
            if binding['cell']!=cell:continue
            r=seen[rid];g=index[binding['example_id']];gg=gold[g['sample_id']]
            if binding['generation_sha256']!=sha256(out/split/cell/'generations.jsonl'):raise ValueError('generation changed after blinding')
            if g['status']!='valid' and any(v!='not_evaluable' for v in r['axes'].values()):raise ValueError('invalid semantic outcome must not_evaluable')
            rows.append(dict(g,system_id=cell,family_id=gg['family_id'],faulty=gg['faulty'],gold_taxonomy=gg['taxonomy'],
                **{k:r[k] for k in ['axes','correct_status','unsupported_claims','taxonomy_feedback_contradiction','code_verdict','evidence','review_id']},
                review_type='source-grounded Codex agent review on authored synthetic dataset; opaque response panels; not independent human evaluation'))
        rows.sort(key=lambda r:r['example_id']);jsonl(out/split/cell/'reviews.private.jsonl',rows);allrows[cell]=metrics(rows)
    write_json(out/f'{split}-metrics.json',allrows)
    write_json(folder/'verdict-seal.json',{f'verdicts-{i}.private.json':sha256(folder/f'verdicts-{i}.private.json') for i in range(1,4)})
    print(json.dumps(dict(stage='reviews_joined',split=split,targets=sum(r['targets'] for r in allrows.values()),metrics={c:r['selection_counts'] for c,r in allrows.items()}),ensure_ascii=False))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('stage',choices=['packets','combine']);a.add_argument('split',choices=['dev','test']);a.add_argument('--out',type=Path,default=OUT);args=a.parse_args();{'packets':packets,'combine':combine}[args.stage](args.out.resolve(),args.split)
