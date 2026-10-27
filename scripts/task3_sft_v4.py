"""One fixed V4 training run and504 single-attempt L1–L3 evaluations."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime,timezone
from importlib.metadata import version
import gc,hashlib,json,os,platform,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.task3.sft_v1 import read_jsonl,sha256,encode_examples
from src.task3.sft_v1_experiment import Journal,write_json
from src.task3.sft_v1_runtime import digest,adapter_identity,verify_frozen as verify_native,gpu_cost
from src.task3.sft_v4 import EvaluationJournal,SELECTION_POLICY,choose_checkpoint,metrics
from src.task3.sft_v4_training import main_training_arguments,validate_start,CHECKPOINT_FILES
from scripts.task3_base_pv3_control import weight_identity,verify_files
from scripts.task3_fresh_eval import profile_native,validate_prompts
from src.task3.prompt_crossover import call_state,validate_runtime_profile
OUT=ROOT/'outputs/task3/sft-v4-diagnostic-pairs-20261027-run1'
CONTROL=ROOT/'outputs/task3/base-pv3-control-20261027-run1'

def load(p):return json.loads(Path(p).read_text())
def offline(m):
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    os.environ['HF_HOME']=str(Path(m['config']['tokenizer_local']).parents[3])


def freeze(out):
    from transformers import AutoTokenizer
    from src.task3.sft_v1_evaluation import EVALUATION_POLICY
    from src.task3.prompt_crossover import REVIEW_POLICY
    if (out/'manifest.json').exists():raise FileExistsError('already frozen')
    data=out/'dataset';review=load(out/'audit/pair-review.private.json')
    if not review['passed'] or review['families_reviewed']!=88:raise ValueError('all88 pairs must be reviewed before freeze')
    allocation=load(out/'family-allocation.json');families=load(out/'families.authored.private.json')
    if any(review['family_sha256'][f['family_id']]!=digest(f) for f in families):raise ValueError('review source changed')
    old=load(CONTROL/'manifest.json');runtime=old['runtime'];cfg=deepcopy(runtime['loader_manifest']['config'])
    cfg.update(experiment='task3-sft-v4-diagnostic-pairs',dataset_root=str(data.relative_to(ROOT)),expected_rows=dict(train=384,dev=72,test=72))
    cfg['training'].update(epochs=1,sampling='one_seeded_shuffle_of_train_rows_without_replacement',checkpoint_selection='diagnostic_pair_lexicographic_dev_only')
    cfg['checksum_manifest_sha256']=digest({str(p.relative_to(data)):sha256(p) for p in data.rglob('*') if p.is_file()})
    tok=AutoTokenizer.from_pretrained(cfg['tokenizer_local'],local_files_only=True,trust_remote_code=False)
    if hashlib.sha256(tok.chat_template.encode()).hexdigest()!=runtime['loader_manifest']['tokenizer']['chat_template_sha256']:raise ValueError('template changed')
    if sha256(data/'SYSTEM_PROMPT.txt')!=sha256(ROOT/'data/raw/task3-sft-v3/SYSTEM_PROMPT.txt'):raise ValueError('P_v3 changed')
    examples={s:read_jsonl(data/f'{s}.examples.private.jsonl') for s in ['train','dev','test']}
    if {s:len(x) for s,x in examples.items()}!={'train':384,'dev':72,'test':72}:raise ValueError('target counts')
    parts={s:{e['family_id'] for e in ee} for s,ee in examples.items()}
    if any(parts[a]&parts[b] for a,b in [('train','dev'),('train','test'),('dev','test')]):raise ValueError('family split leakage')
    pre=out/'preflight';pre.mkdir(exist_ok=False);encoded={};stats={};tokenids=[]
    from scripts.task3_fresh_eval import jsonl
    for split,ee in examples.items():
        rows,stats[split]=encode_examples(tok,ee,8192);jsonl(pre/f'{split}.encoded.private.jsonl',rows);encoded[split]=sha256(pre/f'{split}.encoded.private.jsonl')
        for e in ee:
            ids=tok.apply_chat_template(e['prompt'],tokenize=True,add_generation_prompt=True)
            if len(ids)+1024>32768:raise ValueError('context guard')
            tokenids.append(dict(example_id=e['example_id'],split=split,prompt_sha256=digest(e['prompt']),input_ids=ids,token_id_sha256=digest(ids),input_tokens=len(ids)))
    jsonl(pre/'input-ids.private.jsonl',tokenids)
    policy=deepcopy(REVIEW_POLICY);policy.update(version='v4-discrimination-review-v1',
        primary='For each family L2/L3 clean valid empty taxonomy truthful assessment; faulty valid actual supported diagnosis/location/conditions without material unsupported accusation. /24 dev/test. Disclosure/repair separate.',
        status='Never infer clean assessment from empty labels or a syntax-only statement. Record explicit correct_status separately. Additional claims, contradictions, Vietnamese and required useful content separate.',
        historical_reviews='Every V4 dataset output reviewed anew; no historical score copying; opaque panels where practical; authored synthetic agent review, not independent humans.',
        novel_repairs='Only additional concrete disputed claims need new CppSandbox tests; count separately.',uncertainty='Every uncertain/not_evaluable retained, never quietly a pass.')
    write_json(out/'review-policy.json',policy);write_json(out/'parser-policy.json',EVALUATION_POLICY['parser'])
    write_json(out/'metric-definitions.json',dict(selection=SELECTION_POLICY,pair_success=policy['primary'],
        useful_repair='valid faulty L3 with supported diagnosis/location/conditions and useful correct repair/code pass or absent; /12',
        clean_alarm='valid nonempty taxonomy on clean /36; text-only unsupported claims and contradictions separate',
        faulty_miss='valid empty taxonomy on faulty /36, invalid separate; supported diagnosis not inferred from nonempty',
        joint='existing rubric joint_successful plus required content, explicit supported textual correct_status and status/taxonomy consistency /72',
        taxonomy_consistency='exact set equality across three Levels for each source, any invalid => unknown; not equivalent to correctness',
        unit='12 families24 sources repeated at3 Levels, not72 independent programs',
        recommendation='Research evidence only; further deployment testing only if pair discrimination improves vs V3 without lower useful repair or truthful clean success; no official score claim.'))
    write_json(out/'selection-policy.json',SELECTION_POLICY)
    write_json(out/'example-policy.json',dict(categories=['correct_clean_faulty_discrimination','both_treated_alike','new_adapter_improvement','new_adapter_regression','correct_L3_repair','incorrect_or_missing_L3_repair','cross_Level_taxonomy','compile_interface_behavior'],
        order='sha256(split/family/source/Level), then ID; prefer unused target then family; all raw cases published',
        criteria='Known source-grounded diagnostic/repair/joint transitions, not response length/keyword. Missing category explicit; fill with further hashed distinct cases to show at least8 real targets.',
        extrema='No model identity favourable sampling; include improvement and regression if present; compile/interface example selected independently of scores.'))
    code_names=['scripts/task3_sft_v4.py','scripts/task3_sft_v4_prepare.py','scripts/task3_sft_v4_review.py','src/task3/sft_v4.py','src/task3/sft_v4_training.py','src/task3/sft_v1.py','src/task3/sft_v1_experiment.py','src/task3/sft_v1_runtime.py','src/task3/sft_v1_training.py','src/task3/sft_v2_runtime.py','src/task3/sft_v2_public_context.py','src/task3/sft_v1_evaluation.py','src/task3/pilot_training.py','src/task3/train.py','scripts/task3_sft_v1_prepare.py','src/task3/cpp_sandbox.py','scripts/task3_fresh_eval.py','src/task3/prompt_crossover.py','src/task3/prompt_crossover_analysis.py','scripts/task3_base_pv3_control.py']
    code={n:sha256(ROOT/n) for n in code_names}
    for n in code_names:
        dest=out/'source-snapshot'/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,dest)
    frozen={str(p):sha256(p) for folder in [out/'authoring',out/'evidence',out/'audit'] for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.log']}
    frozen.update({str(out/n):sha256(out/n) for n in ['request.txt','family-allocation.json','families.authored.private.json','initial-workspace-state.json','review-policy.json','parser-policy.json','metric-definitions.json','selection-policy.json','example-policy.json']})
    m=dict(version='task3-v4-diagnostic-pairs-v1',created_utc=datetime.now(timezone.utc).isoformat(),branch='fix/task3-strict-feedback',head=load(out/'initial-workspace-state.json')['head'],
        config=cfg,code=code,dataset={str(p.relative_to(data)):sha256(p) for p in data.rglob('*') if p.is_file()},
        preflight=str(pre),encoded=encoded,token_statistics=stats,tokenizer=runtime['loader_manifest']['tokenizer'],model_files=runtime['loader_manifest']['model_files'],versions=runtime['versions'],
        runtime=runtime,generation=runtime['generation'],frozen_files=frozen,v3=old['v3'],steps=dict(train_rows=384,main=96,checkpoints=[48,96],smoke=0),
        training_arguments=main_training_arguments(cfg,out/'main',384),adapter_configuration=dict(r=16,alpha=32,dropout=.05,target_modules=cfg['training']['target_modules'],bias='none'),
        evaluation_budget=dict(dev=dict(base=72,V3=72,step48=72,step96=72),test=dict(base=72,V3=72,selected=72),total=504,semantic_retries=0,smoke_generations=0),
        loss='mean assistant-token CE per example, mean across examples, loss_weight1; native Trainer accumulation4',
        sampling='Existing Trainer seeded random sampler; actual example traversal logged, each384 exactly once. No pair or family IDs in model.forward.',
        proposal_differences=dict(learning_rate='2e-5 requested, proposal1e-5',comparators='V3 also evaluated on dev/test',evaluation_budget='504 not360',primary='diagnostic pair discrimination',eligibility='relative V3 dev, not absolute proposal thresholds'),
        privacy='No gold/witness/reference/author metadata in model inputs; exact P_v3 native allowed fields only.')
    write_json(out/'manifest.json',m);write_json(out/'manifest.sha256.json',dict(sha256=sha256(out/'manifest.json')))
    verify(out);print(json.dumps(dict(status='frozen',stats=stats,budget=504)),flush=True)


def verify(out):
    m=load(out/'manifest.json');verify_native(ROOT,out,m);verify_files(m['frozen_files'])
    state=load(out/'initial-workspace-state.json');verify_files(state['files'])
    if subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()!=m['branch'] or subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=m['head']:raise ValueError('workspace moved')
    verify_files({d['path']:d['sha256'] for d in m['v3']['adapter_files'].values()})
    return m


def train(out,resume=False):
    m=verify(out);offline(m)
    if (out/'main/training-result.json').exists():print('main already complete; no optimizer replay');return
    import torch
    from src.task3.sft_v2_runtime import load_native
    from src.task3.sft_v1_training import new_adapter
    from src.task3.sft_v4_training import audited_train
    journal=Journal(out/'journal.jsonl');base,tok=load_native(m,journal);base.eval();before=weight_identity(base)
    if hasattr(base,'peft_config'):raise ValueError('main base has adapter')
    model=new_adapter(base,m['config']);fresh=adapter_identity(model)
    write_json(out/'main-initialization.json',dict(from_pinned_base=True,loaded_V3=False,merged=False,stacked=False,seed=42,initial_adapter_identity=fresh,optimizer_smoke_steps=0))
    rows=read_jsonl(Path(m['preflight'])/'train.encoded.private.jsonl');examples=read_jsonl(out/'dataset/train.examples.private.jsonl');dev=read_jsonl(Path(m['preflight'])/'dev.encoded.private.jsonl')
    checkpoint=None
    if (out/'main/started.json').exists():
        if not resume:raise ValueError('explicit safe resume required')
        choices=[p for p in (out/'main').glob('checkpoint-*') if (p/'checkpoint-identity.json').exists()]
        if not choices:raise ValueError('no sealed checkpoint; refuse replay')
        checkpoint=max(choices,key=lambda p:int(p.name.split('-')[-1]));validate_start(out/'main',checkpoint,journal,[48,96])
    trainer,result=audited_train(ROOT,out,model,tok,rows,dev,examples,m,journal,resume=checkpoint)
    after={n.removeprefix('base_model.model.'):h for n,h in weight_identity(model).items()}
    if before!=after:raise ValueError('base parameters changed by optimizer')
    write_json(out/'main-base-weight-audit.json',dict(all_non_adapter_parameter_bytes_unchanged=True,parameters=len(before),hashes=before,scope='full byte hashes before fresh LoRA attachment and after96 optimizer steps'))
    write_json(out/'status.json',dict(status='training_complete_pending_dev',optimizer_steps=result['actual_optimizer_steps'],smoke_steps=0))


def cell_map(out):
    ids={s:[e['example_id'] for e in read_jsonl(out/f'dataset/{s}.examples.private.jsonl')] for s in ['dev','test']}
    return {f'{s}/{c}':ids[s] for s,cc in [('dev',['base','V3','step48','step96']),('test',['base','V3','selected'])] for c in cc}


def evaluate(out,split):
    m=verify(out);offline(m)
    selection=None
    if split=='test':
        selection=load(out/'selection.json')
        if sha256(out/'selection.json')!=load(out/'selection.sha256.json')['sha256'] or not selection['dev_only']:raise ValueError('test requires sealed dev-only selection')
        verify_files(selection['dev_evidence'])
    cells=['base','V3','step48','step96'] if split=='dev' else ['base','V3','selected']
    examples=read_jsonl(out/f'dataset/{split}.examples.private.jsonl');fullids=read_jsonl(Path(m['preflight'])/'input-ids.private.jsonl')
    counts={r['example_id']:r['input_tokens'] for r in fullids if r['split']==split};hashes={r['example_id']:r['token_id_sha256'] for r in fullids if r['split']==split}
    journal=EvaluationJournal(out/'journal.jsonl',cell_map(out))
    pending=[c for c in cells if not (out/f'{split}/{c}/complete.json').exists()]
    if not pending:print(json.dumps(dict(status='evaluation_resume_noop',split=split,new_calls=0)));return
    import torch,bitsandbytes as bnb
    from peft import PeftModel
    from transformers import set_seed
    from src.task3.sft_v2_runtime import load_native
    from src.task3.sft_v2_public_context import generate
    torch.cuda.reset_peak_memory_stats();tick=time.perf_counter();base,tok=load_native(m,journal);base.eval();basehash=weight_identity(base)
    write_json(out/f'{split}/load-runtime.json',dict(wall_s=time.perf_counter()-tick,peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),scope='load/preparation and initial full weight hash; no evaluated forward'))
    validate_prompts(tok,examples,counts,hashes)
    for c in pending:
        set_seed(42)
        if c=='base':model=base;path=None
        else:
            path=Path(m['v3']['checkpoint']) if c=='V3' else out/'main'/f"checkpoint-{selection['step'] if c=='selected' else c.removeprefix('step')}"
            if c!='V3':verify_files({str(path/n):h for n,h in load(path/'checkpoint-identity.json').items()})
            model=PeftModel.from_pretrained(base,str(path),is_trainable=False)
        model.eval()
        if any(x.training for x in model.modules()) or any(p.requires_grad for p in model.parameters()):raise ValueError('evaluation not frozen/eval')
        if path:
            profile=profile_native(model,bnb);validate_runtime_profile(profile)
            if c=='V3' and profile['adapter_identity']!=m['v3']['tensor_identity']:raise ValueError('wrong V3 tensor identity')
            if any(getattr(x,'merged_adapters',[]) for x in model.modules()):raise ValueError('merged evaluation adapter')
        else:
            q=[x for x in model.modules() if isinstance(x,bnb.nn.Linear4bit)]
            profile=dict(no_adapter=True,parameter_dtypes=dict(Counter(str(p.dtype) for p in model.parameters())),attention=model.config._attn_implementation,
                quantization=dict(modules=len(q),compute=dict(Counter(str(x.compute_dtype) for x in q)),nested=all(x.weight.quant_state.nested for x in q)),generation_config=model.generation_config.to_dict())
            if hasattr(model,'peft_config') or len(q)!=196 or profile['quantization']['compute']!={'torch.bfloat16':196} or profile['attention']!='sdpa':raise ValueError('base evaluation runtime mismatch')
        if model.generation_config.to_dict()!=load(CONTROL/'matching-audit.json')['enabled_profile']['generation_config']:raise ValueError('decoding defaults changed')
        d=out/split/c;d.mkdir(parents=True,exist_ok=True);write_json(d/'runtime-before.json',dict(profile=profile,checkpoint=str(path) if path else None,context=32768,generation=m['generation'],seed=42))
        rows=read_jsonl(d/'generations.jsonl') if (d/'generations.jsonl').exists() else [];seen=set();ei={e['example_id']:e for e in examples}
        for r in rows:
            eid=r['example_id'];action,res=call_state(journal,f'{split}/{c}/{eid}')
            if eid in seen or eid not in ei or (r['sample_id'],r['level'])!=(ei[eid]['sample_id'],ei[eid]['level']):raise ValueError('durable binding corruption')
            if action=='completed':
                if {k:v for k,v in r.items() if k!='utc'}!=res:raise ValueError('durable output differs')
            elif not (action=='uncertain' and r.get('call_count_uncertain') and r['raw']=='' and r['parsed'] is None and r['status']=='missing' and r['finish_reason']=='interrupted_unknown'):raise ValueError('unbound durable result')
            seen.add(eid)
        torch.cuda.reset_peak_memory_stats();start=time.perf_counter();initial_reservations=len(journal.reserved())
        for e in examples:
            eid=e['example_id'];key=f'{split}/{c}/{eid}'
            if eid in seen:continue
            action,res=call_state(journal,key)
            if action!='completed':
                oldbindings=[ev for ev in journal.events() if ev.get('type')=='input_binding' and ev.get('key')==key]
                binding=dict(type='input_binding',key=key,prompt_sha256=digest(e['prompt']),token_id_sha256=hashes[eid],input_tokens=counts[eid],manifest_sha256=sha256(out/'manifest.json'))
                if oldbindings and any({k:v for k,v in ev.items() if k!='utc'}!=binding for ev in oldbindings):raise ValueError('input journal mismatch')
                if not oldbindings:journal.append(binding)
                res=generate(model,tok,e,m['generation'],journal,key,32768)
            if not res.get('call_count_uncertain') and res['input_tokens']!=counts[eid]:raise ValueError('runtime tokens differ')
            Journal(d/'generations.jsonl').append(res);rows.append(res);seen.add(eid)
            print(json.dumps(dict(stage='generation',split=split,system=c,completed=len(rows),status=res['status'],id=eid,action=action)),flush=True)
        actual=weight_identity(model);actual={n.removeprefix('base_model.model.'):h for n,h in actual.items()} if path else actual
        if actual!=basehash:raise ValueError('base parameters changed during evaluation')
        write_json(d/'complete.json',dict(targets=len(rows),new_calls_this_invocation=len(journal.reserved())-initial_reservations,known_completed=sum(not r.get('call_count_uncertain') for r in rows),unknown=sum(bool(r.get('call_count_uncertain')) for r in rows),
            generation_wall_s=sum(r['wall_s'] for r in rows),input_tokens=sum(r['input_tokens'] for r in rows if not r.get('call_count_uncertain')),output_tokens=sum(r['output_tokens'] for r in rows if not r.get('call_count_uncertain')),
            valid=sum(r['status']=='valid' for r in rows),finish_reasons=dict(Counter(r['finish_reason'] for r in rows)),base_bytes_unchanged=True,
            phase_wall_s=time.perf_counter()-start,peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),scope='current invocation inference phase plus post-weight hash; durable tokens/time across all rows; unknown token counts not treated as knownzero'))
        if path:base=model.unload()
        del model;gc.collect();torch.cuda.empty_cache()
    write_json(out/'status.json',dict(status=split+'_generations_complete_pending_review',reserved_calls=len(journal.reserved())))


def select(out):
    m=verify(out)
    if (out/'selection.json').exists():raise FileExistsError('selection immutable; never choose using test')
    journal=EvaluationJournal(out/'journal.jsonl',cell_map(out))
    if any(k.startswith('test/') for k in journal.reserved()):raise ValueError('test already observed before selection')
    result={c:metrics(read_jsonl(out/f'dev/{c}/reviews.private.jsonl')) for c in ['base','V3','step48','step96']}
    if any(x['targets']!=72 for x in result.values()):raise ValueError('complete dev reviews required')
    candidates=[dict(step=step,**result[f'step{step}']['selection_counts']) for step in [48,96]]
    chosen=choose_checkpoint(candidates,result['V3']['selection_counts'])
    evidence={str(p):sha256(p) for c in result for p in (out/'dev'/c).glob('*') if p.is_file()}
    chosen.update(created_utc=datetime.now(timezone.utc).isoformat(),dev_only=True,test_reservations_before_selection=0,manifest_sha256=sha256(out/'manifest.json'),dev_evidence=evidence,checkpoint=str(out/'main'/f"checkpoint-{chosen['step']}"))
    write_json(out/'dev-metrics.json',result);write_json(out/'selection.json',chosen);write_json(out/'selection.sha256.json',dict(sha256=sha256(out/'selection.json')))
    print(json.dumps(chosen,ensure_ascii=False)[:5000],flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('stage',choices=['freeze','train','dev','select','test','verify']);a.add_argument('--out',type=Path,default=OUT);a.add_argument('--resume',action='store_true');args=a.parse_args();out=args.out.resolve()
    if args.stage=='freeze':freeze(out)
    elif args.stage=='train':train(out,args.resume)
    elif args.stage in ['dev','test']:evaluate(out,args.stage)
    elif args.stage=='select':select(out)
    else:verify(out);print('frozen experiment and preserved workspace verified')
