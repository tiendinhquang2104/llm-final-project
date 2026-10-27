"""Author/evidence integration for88 diagnostic pairs; no model load or training."""
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib,json,re,shutil,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.task3.sft_v1 import sha256,read_jsonl,native_prompt,encode_examples
from src.task3.sft_v1_experiment import write_json
from src.task3.sft_v1_runtime import digest
from scripts.task3_fresh_eval import import_file,isolated_syntax,TEMPLATE,LABELS,jsonl,text_sha
from src.task3.cpp_sandbox import CppSandbox
from scripts.task3_sft_v1_l4_audit import output_matches
OUT=ROOT/'outputs/task3/sft-v4-diagnostic-pairs-20261027-run1'


def load(p):return json.loads(Path(p).read_text())


def collect(out,owners=None):
    allocation=load(out/'family-allocation.json')['families'];expected={f['family_id']:f for f in allocation}
    families=[];checks={}
    owners=owners or ['a','b','c']
    for owner in owners:
        module=import_file('v4_author_'+owner,out/'authoring'/f'batch_{owner}.py')
        checks[owner]=module.self_check();ff=module.families()
        if {f['family_id'] for f in ff}!={r['family_id'] for r in allocation if r['owner']==owner}:raise ValueError('author allocation')
        families+=ff
    expected_count=sum(r['owner'] in owners for r in allocation)
    if len(families)!=expected_count:raise ValueError('exact author family population')
    labels=load(LABELS)['taxonomy_error']
    for f in families:
        eid=f['family_id'];a=expected[eid]
        if any(f[k]!=a[k] for k in ['split','category']):raise ValueError('split/category changed '+eid)
        mu=f['mutation'];clean=f['clean_code'];faulty=f['faulty_code']
        if mu['count']!=1 or clean.count(mu['before'])!=1 or clean.replace(mu['before'],mu['after'],1)!=faulty:raise ValueError('single root '+eid)
        if not f['taxonomy'] or not set(f['taxonomy'])<=set(labels):raise ValueError('official taxonomy '+eid)
        if not clean.endswith('\n') or not faulty.endswith('\n'):raise ValueError('source finalLF '+eid)
        if not f['tests'] or len(f['tests'])>200 or f['tests'][0]['input']!=f['witness_input']:raise ValueError('witness-first bounded tests '+eid)
        if eid in clean+faulty or re.search(r'\b(?:faulty|clean|mutation|DX\d{3}|CX\d{3}|SX\d{3}|FX\d{3}|MX\d{3}|IX\d{3})\b',clean+faulty,re.I):raise ValueError('author metadata source '+eid)
        if f['checker'] not in ['tokens','exact_bytes']:raise ValueError('checker')
        if not all(f.get(k) for k in ['defect','location','trigger_conditions','repair_direction','l2_feedback','l3_feedback','clean_invariant','test_design','novelty']):raise ValueError('missing evidence fields '+eid)
    if len(families)==88 and sum(f['multi_function'] for f in families)<24:raise ValueError('24 multifunction minimum')
    suffix='' if len(families)==88 else '.'+''.join(owners)
    write_json(out/f'audit/oracle-self-checks{suffix}.private.json',checks)
    write_json(out/f'families.authored{suffix}.private.json',sorted(families,key=lambda f:f['family_id']))
    return sorted(families,key=lambda f:f['family_id'])


def validate(out,owners=None):
    families=collect(out,owners);sandbox=CppSandbox(TEMPLATE)
    data=out/'dataset';data.mkdir(exist_ok=True);(data/'sources').mkdir(exist_ok=True)
    shutil.copyfile(LABELS,data/'label_space.json')
    shutil.copyfile(ROOT/'data/raw/task3-sft-v3/SYSTEM_PROMPT.txt',data/'SYSTEM_PROMPT.txt')
    shutil.copyfile(ROOT/'data/raw/task3-sft-v1/output.schema.json',data/'output.schema.json')
    sources=[];gold=[];syntax={};all_details=[];tick=time.perf_counter()
    evid=out/'evidence';evid.mkdir(exist_ok=True)
    for f in families:
        fid=f['family_id'];ref=f['clean_code']
        # Evidence is durable by family. Resume only exact authored hashes, never silently overwrite changed pairs.
        path=evid/f'{fid}.private.json';binding=digest(f)
        if path.exists():
            detail=load(path)
            if detail['family_sha256']!=binding:raise ValueError('authored family changed after evidence '+fid)
        else:
            detail=dict(family_id=fid,family_sha256=binding,versions={})
            for kind,code in [('left',f['clean_code']),('right',f['faulty_code']),('repair',ref)]:
                if kind!='repair':syn=isolated_syntax(sandbox,code,evid/'jails')
                else:syn=None
                jail,compiled=sandbox.compile(code,evid/'jails');runs=[]
                try:
                    intended_compile=(f['category']=='compile_interface' and kind=='right')
                    if intended_compile:
                        if compiled['returncode']==0 or compiled['timeout']:raise ValueError('compile defect not demonstrated '+fid)
                        diagnostic=f.get('diagnostic_expectation')
                        if diagnostic and diagnostic.lower() not in compiled['stderr'].lower():raise ValueError('wrong intended compiler diagnostic '+fid+' '+str(diagnostic))
                    else:
                        if compiled['returncode']!=0 or compiled['timeout']:raise ValueError('unexpected compile failure '+fid+' '+kind+' '+compiled['stderr'])
                        for n,test in enumerate(f['tests']):
                            actual=sandbox.run(jail,stdin=test['input']);passed=actual['returncode']==0 and not actual['timeout'] and output_matches(actual['stdout'],test['expected'],f['checker'])
                            runs.append(dict(index=n,input=test['input'],expected=test['expected'],actual=actual,passed=passed))
                            if kind!='right' and not passed:raise ValueError('clean/reference test failure '+fid+' '+kind+' '+str(n)+' '+repr(runs[-1]))
                            if kind=='right' and (actual['timeout'] or actual['returncode']!=0):break
                        if kind=='right' and (not runs or runs[0]['passed']):raise ValueError('witness not discriminating '+fid)
                finally:shutil.rmtree(jail)
                detail['versions'][kind]=dict(source_sha256=text_sha(code),syntax=syn,compile=compiled,tests=runs,
                    authored_tests=len(f['tests']),executed_tests=len(runs),passes=sum(r['passed'] for r in runs),not_executed=len(f['tests'])-len(runs),
                    reason_no_runtime='intended compile failure' if intended_compile else None)
            write_json(path,detail)
        all_details.append(detail)
        for faulty,kind in [(False,'left'),(True,'right')]:
            sid='S'+text_sha(fid+'/'+kind)[:12];code=f['faulty_code' if faulty else 'clean_code'];(data/'sources'/f'{sid}.cpp').write_text(code)
            source=dict(sample_id=sid,family_id=fid,split=f['split'],category=f['category'],statement=f['statement'],code=code,language='cpp11',exam_type='single_problem',checker=f['checker'])
            sources.append(source);syntax[sid]=detail['versions'][kind]['syntax']
            g=dict(sample_id=sid,family_id=fid,split=f['split'],faulty=faulty,taxonomy=f['taxonomy'] if faulty else [],
                title=f['title'],source_sha256=text_sha(code),statement_sha256=text_sha(f['statement']),defect=f['defect'] if faulty else None,
                location=f['location'] if faulty else None,trigger_conditions=f['trigger_conditions'] if faulty else [],repair_direction=f['repair_direction'] if faulty else None,
                clean_invariant=f['clean_invariant'],witness_input=f['witness_input'],evidence_path=str(path.relative_to(out)),reference_repair_sha256=text_sha(ref),
                expected_witness=f['tests'][0]['expected'],test_design=f['test_design'],novelty=f['novelty'])
            gold.append(g)
        print(json.dumps(dict(stage='evidence',family=fid,done=len(all_details),total=88)),flush=True)
    if len(families)!=88:
        print(json.dumps(dict(stage='partial_evidence_complete',owners=owners,families=len(families))),flush=True)
        return
    jsonl(data/'sources.private.jsonl',sources);jsonl(data/'gold.private.jsonl',gold);write_json(data/'syntax.private.json',syntax)
    labels=load(data/'label_space.json')['taxonomy_error'];fi={f['family_id']:f for f in families};records=[];all_examples=[];consistency=[]
    for source,g in zip(sources,gold):
        f=fi[source['family_id']];output_labels=g['taxonomy']
        for level in [1,2,3]:
            feedback='Bài làm đáp ứng đúng yêu cầu đề bài.' if not g['faulty'] else 'Bài làm còn có lỗi cần kiểm tra.' if level==1 else f['l2_feedback'] if level==2 else f['l3_feedback']
            payload=dict(taxonomy_error=output_labels,feedback=feedback)
            x={k:source[k] for k in ['statement','exam_type','language','code']};x.update(compile_log=syntax[source['sample_id']]['diagnostic'],target_feedback_level=level)
            eid=source['sample_id']+f'-L{level}';prompt=native_prompt(data,x,labels)
            records.append(dict(sample_id=eid,source_id=source['sample_id'],family_id=source['family_id'],split=source['split'],input=x,output=payload))
            all_examples.append(dict(example_id=eid,sample_id=source['sample_id'],family_id=source['family_id'],split=source['split'],level=level,prompt=prompt,completion=json.dumps(payload,ensure_ascii=False),loss_weight=1.))
        consistency.append(dict(sample_id=source['sample_id'],taxonomy_identical_L123=True,clean=not g['faulty'],L1_status_only=True,
            L2_L3_source_grounded_targets='explicit author targets, inverse mutation reference verified; every pair reviewed before freeze'))
    for split,n in [('train',384),('dev',72),('test',72)]:
        ee=[e for e in all_examples if e['split']==split]
        if len(ee)!=n:raise ValueError('split population')
        jsonl(data/f'{split}.examples.private.jsonl',ee);jsonl(data/f'{split}.records.jsonl',[r for r in records if r['split']==split])
        jsonl(data/f'{split}.sft.jsonl',[dict(prompt=e['prompt'],completion=[dict(role='assistant',content=e['completion'])]) for e in ee])
    write_json(data/'target-consistency-audit.json',dict(passed=True,sources=176,targets=528,checks=consistency,
        limitation='Automated checks establish identities/schema, not semantic truth. Source/target review and sandbox evidence are separate.'))
    write_json(data/'split-manifest.json',dict(allocation_sha256=sha256(out/'family-allocation.json'),families=load(out/'family-allocation.json')['families'],
        counts={split:dict(families=sum(f['split']==split for f in families),sources=sum(s['split']==split for s in sources),targets=sum(e['split']==split for e in all_examples)) for split in ['train','dev','test']},
        primary_mechanisms=dict(Counter(f['category'] for f in families)),multi_function=sum(f['multi_function'] for f in families)))
    write_json(out/'evidence-summary.json',dict(families=88,sources=176,reference_repairs=88,
        syntax_compiler_calls=176,compiler_calls=264,runtime_calls=sum(v['executed_tests'] for d in all_details for v in d['versions'].values()),
        compiler_wall_s=sum(v['compile']['latency_s']+(v['syntax']['latency_s'] if v['syntax'] else 0) for d in all_details for v in d['versions'].values()),
        runtime_wall_s=sum(r['actual']['latency_s'] for d in all_details for v in d['versions'].values() for r in v['tests']),
        invocation_wall_s=time.perf_counter()-tick,resume_scope='metadata totals across durable families; invocation wall only current call',
        finite_tests_not_universal_proof=True))


def canonical(code):
    code=re.sub(r'//[^\n]*|/\*[\s\S]*?\*/','',code)
    keywords=set('int long unsigned signed float double char bool void const return if else for while do switch case break continue struct class public private using namespace std vector string cin cout size_t true false auto sizeof static include'.split())
    tokens=re.findall(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_]\w*|\d+|[^\s]',code)
    return ['ID' if re.fullmatch(r'[A-Za-z_]\w*',t) and t not in keywords else 'NUM' if t.isdigit() else t for t in tokens]


def shingles(tokens,n=7):return set(tuple(tokens[i:i+n]) for i in range(max(0,len(tokens)-n+1)))


def overlap(out):
    reference=load(out/'audit/prior-source-index-reference.json');prior=load(reference['path'])['sources']
    # Add the complete actual native/fresh source files, including current previously observed FE01–FE20.
    entries=list(prior)
    for path in [ROOT/'data/raw/task3-sft-v1/sources',ROOT/'data/raw/task3-sft-v2/sources',ROOT/'data/raw/task3-sft-v3/sources',ROOT/'outputs/task3/fresh-eval-v2-v3-a-20261027-run1/sources']:
        if path.exists():
            for q in path.glob('*.cpp'):
                code=q.read_text();entries.append(dict(code=code,exact_sha256=text_sha(code),whitespace_sha256=text_sha(''.join(code.split())),provenance=[dict(path=str(q))]))
    unique={text_sha(e['code']):e for e in entries};entries=list(unique.values());prior_sets=[shingles(canonical(e['code'])) for e in entries]
    exact={text_sha(e['code']) for e in entries};space={text_sha(''.join(e['code'].split())) for e in entries}
    sources=read_jsonl(out/'dataset/sources.private.jsonl');matches=[]
    new_sets={s['sample_id']:shingles(canonical(s['code'])) for s in sources}
    for s in sources:
        tokens=new_sets[s['sample_id']];scored=[]
        for i,ss in enumerate(prior_sets):
            shared=len(tokens&ss);j=shared/len(tokens|ss) if tokens|ss else 1
            scored.append((j,i))
        top=sorted(scored,reverse=True)[:3]
        matches.append(dict(sample_id=s['sample_id'],family_id=s['family_id'],split=s['split'],exact_match=text_sha(s['code']) in exact,whitespace_match=text_sha(''.join(s['code'].split())) in space,
            candidates=[dict(canonical_token_7gram_jaccard=score,source_sha256=text_sha(entries[i]['code']),provenance=entries[i].get('provenance'),excerpt=entries[i]['code'][:2400]) for score,i in top]))
    cross=[]
    for i,a in enumerate(sources):
        for b in sources[i+1:]:
            if a['family_id']==b['family_id']:continue
            x,y=new_sets[a['sample_id']],new_sets[b['sample_id']];score=len(x&y)/len(x|y) if x|y else 1
            if score>=.6:cross.append(dict(left=a['sample_id'],left_family=a['family_id'],left_split=a['split'],right=b['sample_id'],right_family=b['family_id'],right_split=b['split'],jaccard=score))
    write_json(out/'audit/overlap-candidates.private.json',dict(prior_unique_sources=len(entries),reference=reference,
        method='Exact UTF8/whitespace hashes; identifier/number-normalized7-token-shingle Jaccard candidates, plus explicit author semantic/template review. Similarity is screening, never semantic ground truth.',
        matches=matches,new_family_candidates=sorted(cross,key=lambda x:-x['jaccard']),
        limitation='Available local inventories/files only; does not prove pretraining independence or exhaustively establish semantic uniqueness. Public source code read solely for exclusion screening, never copied to training.'))
    if any(r['exact_match'] or r['whitespace_match'] for r in matches):raise ValueError('historical exact/whitespace overlap')
    print(json.dumps(dict(stage='overlap_screen',sources=len(sources),prior_unique_sources=len(entries),cross_candidates=len(cross))),flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('stage',choices=['collect','validate','overlap']);a.add_argument('--out',type=Path,default=OUT);a.add_argument('--owner',choices=['a','b','c']);args=a.parse_args()
    if args.stage in ['collect','validate']:{'collect':collect,'validate':validate}[args.stage](args.out.resolve(),[args.owner] if args.owner else None)
    else:overlap(args.out.resolve())
