#!/usr/bin/env python3
"""Small C-only experiment adapter using existing journals, metrics and review rubric."""
from __future__ import annotations
import argparse,json,os,random,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.task3 import c_feedback_v3 as c,two_pass as v1
from src.task3.dataset import write_json
from src.task3.level_blind import read,sha,digest
from src.task3.grounded_metrics import taxonomy_metrics
from scripts import task3_two_pass_v2_audit as review

OUT=ROOT/'outputs/task3/c-feedback-v3-20261023'
OLD=ROOT/'outputs/task3/two-pass-v2-20261023'
ARMS=['A','B','C-old','C-new']
FILES=['src/task3/c_feedback_v3.py','scripts/task3_c_feedback_v3.py','configs/task3/c_feedback_v3_20261023.json',
 'src/task3/two_pass.py','src/task3/two_pass_v2.py','src/task3/inference.py','src/task3/grounded.py',
 'src/task3/grounded_metrics.py','src/task3/schema.py','src/task3/dataset.py','src/task3/level_blind.py',
 'src/synth/taxonomy.py','src/synth/feedback.py','scripts/task3_two_pass_v2_audit.py','configs/task3/two_pass_20261023.json']
require=c.require


def freeze():
    require(not(OUT/'frozen').exists(),'one candidate freeze only')
    for n,h in read(OUT/'selection-seal.json').items():require(sha(OUT/n)==h,n)
    for n,h in read(OUT/'review/source-seal.json').items():require(sha(OUT/'review'/n)==h,n)
    cfg=read(ROOT/'configs/task3/c_feedback_v3_20261023.json');runtime=read(ROOT/cfg['runtime_config'])
    old=read(ROOT/'outputs/task3/two-pass-20261023/frozen/freeze.json')
    require(runtime==old['config'],'unchanged complete v1 runtime config')
    labels=read(ROOT/'data/raw/sample_dataset/label_space.json');units=read(OUT/'units.private.json')
    for u in units:c.safe_input(u,labels['feedback_level'])
    d=OUT/'frozen';d.mkdir();write_json(d/'level-definitions.json',labels['feedback_level'])
    inputs=[OUT/n for n in ['selection-seal.json','units.private.json','selection.private.json','control.private.json','control-runtime.private.json','casebook-analysis.private.json','review/source-seal.json']]
    inputs += [ROOT/'outputs/task3/eval-freeze-v2-20261021/frozen/reference.private.json',OLD/'review/packet-CD.private.json']
    for n in FILES:
        p=d/'code'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/n).read_bytes())
    m={'initial_HEAD':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'config':cfg,'runtime':runtime,'tokenizer':old['tokenizer'],
       'prompt_sha256':digest([c.COMMON,c.LEVEL,c.FORMAT]),'stage1_v1_sha256':sha(ROOT/'src/task3/two_pass.py'),
       'code_sha256':{n:sha(ROOT/n)for n in FILES},'input_sha256':{str(p.relative_to(ROOT)):sha(p)for p in inputs},'definitions_sha256':sha(d/'level-definitions.json')}
    write_json(d/'freeze.json',m);(d/'freeze.sha256').write_text(sha(d/'freeze.json')+'\n');print(json.dumps({'freeze':sha(d/'freeze.json'),'prompt':m['prompt_sha256']}))


def verify():
    d=OUT/'frozen';m=read(d/'freeze.json');require(sha(d/'freeze.json')==(d/'freeze.sha256').read_text().strip(),'freeze seal')
    for n,h in {**m['code_sha256'],**m['input_sha256']}.items():require(sha(ROOT/n)==h,n)
    for n,h in read(OUT/'review/source-seal.json').items():require(sha(OUT/'review'/n)==h,n)
    require(sha(d/'level-definitions.json')==m['definitions_sha256'],'Level rules')
    return m


def run():
    m=verify();require(not(OUT/'run.private.json').exists(),'completed run cannot resample')
    cfg=m['runtime'];os.environ.update(HF_HOME=str(ROOT/'outputs/task3/hf-cache'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    free=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip().splitlines()
    require(len(free)==1 and int(free[0])>=cfg['minimum_free_gpu_mib'],'insufficient GPU memory')
    from src.task3.inference import load_tokenizer,tokenizer_metadata,HFBackend
    tok=load_tokenizer(cfg);require(tokenizer_metadata(tok)==m['tokenizer'],'tokenizer changed')
    backend=HFBackend(cfg,tok);backend.model.generation_config.max_time=cfg['generation_max_time_s']
    units=read(OUT/'units.private.json');defs=read(OUT/'frozen/level-definitions.json')
    rows=v1.run_units(units,backend,cfg,OUT/'B',defs)
    frozen={r['sample_id']:r['stage1']for r in rows};write_json(OUT/'stage1-replay.private.json',frozen)
    for name,renderer in [('C-old','old'),('C-new','new')]:c.run_units(units,backend,cfg,OUT/name,defs,replay=frozen,renderer=renderer)
    verify();write_json(OUT/'run.private.json',{'model_loads':1,'runtime':backend.runtime_metadata(),'stage1_B_replay_sha256':sha(OUT/'stage1-replay.private.json'),'new_stage1_version':v1.VERSION,'D_or_E':False})
    write_json(OUT/'requested-levels.private.json',{u['sample_id']:u['level']for u in units})


def data():
    units=read(OUT/'units.private.json');ids={u['sample_id']for u in units};arms={}
    for a in ARMS:
        rows=[{**r,'status':'resolved'}for r in read(OUT/'control.private.json')]if a=='A'else read(OUT/a/'results.private.json')
        require(len(rows)==len(ids)and {r['sample_id']for r in rows}==ids,'full ID coverage '+a)
        arms[a]={r['sample_id']:{'status':r['status'],'output':r.get('output')}for r in rows}
    return units,arms


def review_policy():
    policy={k:v for k,v in read(OLD/'review/packet-CD.private.json').items()if k!='cases'}
    policy['official_levels']=read(OUT/'frozen/level-definitions.json')
    policy['rubric'].update(addresses_ban='Calls the student bạn; semantic assessment, not token matching in quoted code.',placeholder_only='Only check-program/general filler, without useful feedback appropriate to requested Level.')
    policy['schema']['cases'][0]['outputs'][0].update(addresses_ban=False,placeholder_only=False)
    return policy


def packets():
    verify();units,arms=data();r=OUT/'review';require(not(r/'packet-seal.json').exists(),'one blinded packet');policy=review_policy()
    key={};cases=[];rng=random.Random(2026102304)
    for u in units:
        outputs=[];order=list(ARMS);rng.shuffle(order)
        for a in order:
            oid=digest([u['sample_id'],a,'c3-blind'])[:20];key[oid]={'sample_id':u['sample_id'],'arm':a}
            outputs.append({'output_id':oid,**arms[a][u['sample_id']]})
        cases.append({'sample_id':u['sample_id'],'level':u['level'],'task':u['task'],'outputs':outputs})
    write_json(r/'packet.private.json',{**policy,'cases':cases});write_json(r/'key.private.json',key)
    paths=[r/'packet.private.json',r/'key.private.json',r/'source-seal.json',r/'source-a.private.json',r/'source-b.private.json',OUT/'control.private.json']+[OUT/a/'results.private.json'for a in ARMS[1:]]
    write_json(r/'packet-seal.json',{str(p.relative_to(ROOT)):sha(p)for p in paths});print(json.dumps({'IDs':len(units),'outputs':len(units)*4}))


def bound():
    verify();r=OUT/'review'
    for n,h in read(r/'packet-seal.json').items():require(sha(ROOT/n)==h,n)
    units,arms=data();key=read(r/'key.private.json');packet=read(r/'packet.private.json');review.bind(units,arms,key,packet)
    return units,arms,key,packet


def seal():
    units,arms,key,packet=bound();r=OUT/'review'
    for w in ['a','b']:
        source={x['sample_id']:x for x in read(r/f'source-{w}.private.json')['cases']};rows=read(r/f'paired-{w}.private.json')['cases'];by={x['sample_id']:x for x in rows}
        require(len(by)==len(rows)==len(units),'review coverage')
        for case in packet['cases']:
            rr=by[case['sample_id']]['outputs'];idx={x['output_id']:x for x in rr};require(len(idx)==len(rr)==4 and set(idx)=={x['output_id']for x in case['outputs']},'review arm coverage')
            text='\n'.join(str(case['task'].get(k,''))for k in ['statement','code','grading_policy'])
            for o in case['outputs']:
                x=idx[o['output_id']]
                for k in review.GOOD+review.BAD+['addresses_ban','placeholder_only']:require(type(x[k])is bool,'rubric boolean '+k)
                review.validate_level_fields(x,case['level'],bool(source[case['sample_id']]['source_taxonomy']))
                if o['output']is None:require(not any(x[k]for k in review.GOOD)and not x['evidence'],'no credit/evidence without output')
                for e in x['evidence']:require(e['source_quote']in text and o['output']is not None and e['feedback_quote']in o['output']['feedback'],'exact evidence')
    require(not(r/'paired-seal.json').exists(),'one paired seal')
    write_json(r/'paired-seal.json',{n:sha(r/n)for n in ['paired-a.private.json','paired-b.private.json','packet-seal.json']})


def score():
    units,arms,key,packet=bound();r=OUT/'review'
    for n,h in read(r/'paired-seal.json').items():require(sha(r/n)==h,n)
    refs={w:{x['sample_id']:x for x in read(r/f'source-{w}.private.json')['cases']}for w in ['a','b']}
    reviews={}
    for w in ['a','b']:
        for case in read(r/f'paired-{w}.private.json')['cases']:
            for x in case['outputs']:reviews[(case['sample_id'],key[x['output_id']]['arm'],w)]=x
    gold={x['sample_id']:x['annotation_v2']for x in read(ROOT/'outputs/task3/eval-freeze-v2-20261021/frozen/reference.private.json')['records']}
    b={x['sample_id']:x for x in read(OUT/'B/results.private.json')};rows=[]
    for u in units:
        sid=u['sample_id'];item={'sample_id':sid,'family':u['family'],'level':u['level'],'original_gold':gold[sid],
            'source_A':refs['a'][sid]['source_taxonomy'],'source_B':refs['b'][sid]['source_taxonomy'],'arms':{}}
        for a in ARMS:
            result=arms[a][sid];rr=[reviews[(sid,a,w)]for w in ['a','b']];x=review.combine(result['output'],rr,[refs[w][sid]for w in ['a','b']])
            x.update(status=result['status'],taxonomy=result['output']['taxonomy_error']if result['output']else None,
                     addresses_ban=any(y['addresses_ban']for y in rr),placeholder_only=any(y['placeholder_only']for y in rr))
            x['reviewer_disagreements'] += [k for k in ['addresses_ban','placeholder_only']if len({y[k]for y in rr})>1]
            x['feedback_pass']=x['feedback_pass']and not x['addresses_ban']and not x['placeholder_only'];x['strict_joint']=x['strict_joint']and x['feedback_pass']
            item['arms'][a]=x
        rows.append(item)
    summary={'IDs':len(units),'selection':read(OUT/'selection.private.json'),'arms':{},'per_ID':rows}
    stage1=[b[u['sample_id']]['stage1']['taxonomy_error']if b[u['sample_id']]['stage1']is not None else None for u in units]
    summary['unchanged_stage1_taxonomy']=taxonomy_metrics([gold[u['sample_id']]for u in units],stage1)
    for a in ARMS:
        rr=[x['arms'][a]for x in rows];counts={k:sum(x[k]is True for x in rr)for k in review.GOOD+review.BAD+review.SPECIAL+['addresses_ban','placeholder_only','feedback_pass','strict_joint','l2_repair_leak_confirmed']}
        levels={str(i):{'n':sum(u['level']==i for u in units),**{k:sum(x['arms'][a][k]is True for x in rows if x['level']==i)for k in ['level_ok','direct_em','false_claim','l1_detail_leak','l2_repair_leak','l3_actionable']}}for i in [1,2,3]}
        summary['arms'][a]={'completed':sum(x['status']=='resolved'for x in rr),'unresolved':sum(x['status']!='resolved'for x in rr),'fallback':0,**counts,'per_level':levels,
            'taxonomy_final':taxonomy_metrics([gold[u['sample_id']]for u in units],[x['taxonomy']for x in rr]),'strict_joint_rate':counts['strict_joint']/len(units),
            'clean_n':sum(not gold[u['sample_id']]for u in units),'clean_false_error_on_original_clean':sum(x['arms'][a]['clean_false_error']for x in rows if not x['original_gold'])}
        if a=='A':trace=read(OUT/'control-runtime.private.json');calls=sum(x['calls']for x in trace)
        else:
            path=OUT/a/'attempts.jsonl';trace=[json.loads(s)for s in path.read_text().splitlines()]if path.exists()else[];calls=len(trace)
        summary['arms'][a]['cost']={'calls':calls,'fresh_calls':0 if a=='A'else calls,**{k:sum(x.get(k)or 0 for x in trace)for k in ['input_tokens','output_tokens','latency_s']},'replayed_stage1_IDs':len(units)if a in ['C-old','C-new']else 0}
    for a in ['C-old','C-new']:
        result=read(OUT/a/'results.private.json')
        for x in result:require(x['stage1_observed']==b[x['sample_id']]['stage1'],'stage1 replay unchanged')
        summary['arms'][a]['stage1_inconsistent']=sum(x['stage1_inconsistent']for x in result)
    a,old,new=[summary['arms'][x]for x in ['A','C-old','C-new']]
    checks={'feedback_pass_gain':new['feedback_pass']>max(a['feedback_pass'],old['feedback_pass']),
        'false_claims_not_above_R15':new['false_claim']<=a['false_claim'],'L1_leaks_not_above_R15':new['l1_detail_leak']<=a['l1_detail_leak'],
        'L2_leaks_not_above_R15':new['l2_repair_leak']<=a['l2_repair_leak']}
    summary['continue_gate']={'checks':checks,'passed':all(checks.values())};summary['decision']='propose_separate_internal_evaluation_not_public'if all(checks.values())else'retain_R15_stop_C_new'
    summary['provenance']={'freeze_sha256':sha(OUT/'frozen/freeze.json'),'prompt_sha256':verify()['prompt_sha256'],'source_seal_sha256':sha(r/'source-seal.json'),'paired_seal_sha256':sha(r/'paired-seal.json'),'stage1_replay_sha256':sha(OUT/'stage1-replay.private.json')}
    write_json(ROOT/'reports/task3/TASK3_C_FEEDBACK_V3_METRICS_20261023.json',summary)
    print(json.dumps({'arms':{a:{k:v for k,v in x.items()if k not in ['taxonomy_final','per_level']}for a,x in summary['arms'].items()},'gate':summary['continue_gate'],'decision':summary['decision']},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['freeze','verify','run','packets','seal','score']);args=p.parse_args()
    if args.phase=='verify':verify();print(json.dumps({'verified':True}))
    else:globals()[args.phase]()
