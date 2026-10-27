"""Matched, bounded prepared-base control. No training/public-inference entrypoints."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version
import hashlib
import inspect
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src.task3.sft_v1 import sha256, read_jsonl
from src.task3.sft_v1_experiment import Journal, write_json
from src.task3.sft_v1_runtime import digest, tensor_digest
from src.task3.prompt_crossover import call_state, validate_population, validate_runtime_profile
from src.task3.fresh_eval import validate_dataset
from scripts.task3_fresh_eval import profile_native, validate_prompts

PREVIOUS = REPO/'outputs/task3/fresh-eval-v2-v3-a-20261027-run1'
DEFAULT_OUT = REPO/'outputs/task3/base-pv3-control-20261027-run1'
REQUEST = Path('/root/.codex/attachments/9fbc5d40-f9e3-4525-a744-2b7259bb4baf/Pasted text.txt')


def load(p): return json.loads(Path(p).read_text())
def jsonl(p, rows):
    p = Path(p)
    if p.exists(): raise FileExistsError(p)
    j = Journal(p)
    for r in rows: j.append(r)


def matched_population(examples, rows):
    if any(e['level'] not in (1,2,3) for e in examples): raise ValueError('L1–L3 only')
    return validate_population(rows, examples)


class ControlJournal(Journal):
    def __init__(self, path, ids):
        super().__init__(path)
        self.ids = set(ids)
        if not self.ids or len(self.ids) != len(ids) or len(ids)>120: raise ValueError('budget population')
        reserved=set(); completed=set()
        for e in self.events():
            if e.get('type') not in ('generation_reserved','generation_completed'): continue
            self.parts(e['key'])
            if e['type']=='generation_reserved':
                if e['key'] in reserved: raise ValueError('duplicate reservation')
                reserved.add(e['key'])
            else:
                if e['key'] not in reserved or e['key'] in completed: raise ValueError('corrupt completion')
                completed.add(e['key'])

    def parts(self,key):
        p=key.split('/')
        if len(p)!=2 or p[0]!='base' or p[1] not in self.ids: raise ValueError('foreign target')

    def reserve(self,key,budget=None):
        self.parts(key)
        if key in self.reserved(): raise ValueError('never replay a reserved call')
        if len(self.reserved())>=len(self.ids): raise ValueError('120 single-attempt ceiling')
        self.append(dict(type='generation_reserved',key=key))


def workspace_state():
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=REPO).decode().split('\0')
    paths={REPO/n for n in names if n and (REPO/n).is_file()}
    paths.update(REPO.glob('predictions*.json'))
    paths.update(p for p in (REPO/'submission-candidates').rglob('*') if p.is_file())
    return dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=REPO,text=True).strip(),
        files={str(p):sha256(p) for p in sorted(paths)})


def verify_files(entries):
    for p,h in entries.items():
        if sha256(Path(p))!=h: raise ValueError('frozen file changed: '+p)


def prepare(out):
    if out.exists(): raise FileExistsError('choose a new suffix; never overwrite output directory')
    systems=load(PREVIOUS/'systems.json'); old=load(PREVIOUS/'manifest.json')
    verify_files(old['files'])
    if sha256(PREVIOUS/'manifest.json')!=load(PREVIOUS/'manifest.sha256.json')['sha256']: raise ValueError('historical manifest seal')
    c=systems['common_native_runtime']; lm=c['loader_manifest']; cfg=lm['config']
    if cfg['revision']!='c03e6d358207e414f1eca0bb1891e29f1db0e242' or cfg['model_id']!='Qwen/Qwen2.5-Coder-7B-Instruct': raise ValueError('wrong model')
    if platform.python_version()!='3.12.3' or {n:version(n) for n in c['versions']}!=c['versions']: raise ValueError('dependency versions differ')
    verify_files({p:d['expected'] for p,d in c['dependency_source_files'].items()})
    v3=systems['native_systems']['v3']
    if Path(v3['checkpoint'])!=REPO/'outputs/task3/sft-v3-qlora-20261026-run1/main/checkpoint-480': raise ValueError('wrong adapter')
    verify_files({d['path']:d['sha256'] for d in v3['adapter_files'].values()})
    sources=read_jsonl(PREVIOUS/'dataset.private.jsonl');gold=read_jsonl(PREVIOUS/'gold.private.jsonl')
    validate_dataset(sources,gold,load(PREVIOUS/'prompts/label_space.json')['taxonomy_error'])
    targets=[t for t in read_jsonl(PREVIOUS/'targets.private.jsonl') if t['input']['target_feedback_level']<=3]
    examples=[e for e in load(PREVIOUS/'prompts/V3-v3.private.json') if e['level']<=3]
    gens=[r for r in read_jsonl(PREVIOUS/'generations/V3-v3/final.jsonl') if r['level']<=3]
    reviews=[r for r in read_jsonl(PREVIOUS/'reviews.private.jsonl') if r['system_id']=='V3-v3' and r['level']<=3]
    matched_population(examples,gens);matched_population(examples,reviews)
    if len(examples)!=120 or Counter(e['level'] for e in examples)!={1:40,2:40,3:40}: raise ValueError('population')
    ti={t['sample_id']:t for t in targets};si={s['sample_id']:s for s in sources};gi={g['sample_id']:g for g in gold}
    ri={r['example_id']:r for r in reviews}; gr={r['example_id']:r for r in gens}
    historical=read_jsonl(PREVIOUS/'journal.jsonl')
    for e in examples:
        eid=e['example_id']; t=ti[eid]; s=si[e['sample_id']]; g=gi[e['sample_id']]
        if (t['source_id'],t['input']['target_feedback_level'])!=(e['sample_id'],e['level']): raise ValueError('target mismatch')
        if t['input']['code']!=s['code'] or t['input']['statement']!=s['statement']: raise ValueError('source/spec mismatch')
        if ri[eid]['faulty']!=g['faulty'] or ri[eid]['gold_taxonomy']!=g['taxonomy']: raise ValueError('review gold mismatch')
        if any(ri[eid].get(k)!=v for k,v in gr[eid].items()): raise ValueError('saved V3 review/generation differs')
        events=[ev for ev in historical if ev.get('key')==f'V3-v3/{eid}/1']
        if Counter(ev['type'] for ev in events)!=dict(input_binding=1,generation_reserved=1,generation_completed=1): raise ValueError('not single attempt')
        result=next(ev['result'] for ev in events if ev['type']=='generation_completed')
        if {k:v for k,v in gr[eid].items() if k!='utc'}!=result: raise ValueError('historical completion differs')
    out.mkdir(parents=True)
    shutil.copyfile(REQUEST,out/'request.txt')
    state=workspace_state()
    if state['branch']!='fix/task3-strict-feedback': raise ValueError('branch changed')
    write_json(out/'initial-workspace-state.json',state)
    for name in ['dataset.private.jsonl','gold.private.jsonl','syntax.private.json','frozen-policy.json']:
        shutil.copyfile(PREVIOUS/name,out/name)
    write_json(out/'prompts.private.json',examples)
    write_json(out/'targets.private.json',targets)
    # Reused rows are copied exactly as JSON objects, with historical timestamps intact.
    for name,rows in [('v3-generations.reused.jsonl',gens),('v3-reviews.reused.private.jsonl',reviews)]:
        (out/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    write_json(out/'review-rubric.json',dict(original=load(PREVIOUS/'frozen-policy.json'),
        historical_reviews='Reuse original V3 verdicts unchanged; disputes separately. Base reviewed by agent on observed dataset.',
        additional_axes=['correct_clean_faulty_assessment','unsupported_additional_claims','taxonomy_feedback_contradiction'],
        example_rule='Ordered categories base-better, V3-better, both-miss, clean, L3-repair, contradiction-or-invalid. Rank by sha256(family/source/L), prefer unused targets then families. Missing category explicit; fill distinct slots from same hash order. Complete outputs published for every target.'))
    write_json(out/'metric-definitions.json',dict(
        supported_faulty_diagnosis='Existing summarize_system: valid nonempty faulty L2/L3; diagnosis_supported, coverage, factual_fidelity and location_and_condition all pass. /40',
        repair='Existing faulty_l3_correct: valid, nonempty taxonomy, supported diagnosis, correct location/conditions, useful correct repair and code pass/absent. /20',
        assessment='Source/spec-grounded status verdict independent of empty/nonempty labels; diagnosis quality separate.',
        false_alarm='Valid clean with nonempty taxonomy /60. Text-only accusations and contradictions also reported separately.',
        empty_faulty='Valid faulty with empty taxonomy /60; invalid separate, not predicted clean.',
        nonempty_incorrect='Valid nonempty faulty L2/L3 without fully supported diagnosis; separate L1 status review, no prohibited-detail penalty.',
        joint='Reuse successful_feedback with status/taxonomy consistency, factual, disclosure, required-content, language, useful repair and code gates. /120',
        uncertainty='Retain uncertain/not_evaluable axes and original denominators; no conversion to clean.',
        unit='20 authored observed families,40 programs; three Levels are repeated views, no leaderboard inference.'))
    from transformers import AutoTokenizer
    tok=AutoTokenizer.from_pretrained(cfg['tokenizer_local'],local_files_only=True,trust_remote_code=False)
    counts=load(PREVIOUS/'prompts/token-counts.json')['V3-v3']; hashes=load(PREVIOUS/'prompts/token-id-hashes.json')['V3-v3']
    validate_prompts(tok,examples,counts,hashes)
    input_rows=[]
    for e in examples:
        eid=e['example_id'];ids=tok.apply_chat_template(e['prompt'],tokenize=True,add_generation_prompt=True)
        if len(ids)+c['generation']['max_new_tokens'][str(e['level'])]>32768: raise ValueError('context guard')
        binding=next(ev for ev in historical if ev.get('type')=='input_binding' and ev.get('key')==f'V3-v3/{eid}/1')
        if binding['token_id_sha256']!=digest(ids) or binding['prompt_sha256']!=digest(e['prompt']): raise ValueError('historical actual binding mismatch')
        input_rows.append(dict(example_id=eid,sample_id=e['sample_id'],level=e['level'],input_ids=ids,
            input_tokens=len(ids),token_id_sha256=digest(ids),prompt_sha256=digest(e['prompt']),
            historical_input_binding=binding,raw_v3_sha256=hashlib.sha256(gr[eid]['raw'].encode()).hexdigest()))
    jsonl(out/'input-ids.private.jsonl',input_rows)
    historical_files={str(p):sha256(p) for p in PREVIOUS.rglob('*') if p.is_file()}
    code_names=['scripts/task3_base_pv3_control.py','scripts/task3_fresh_eval.py','scripts/task3_fresh_eval_report.py','src/task3/sft_v2_runtime.py','src/task3/sft_v2_public_context.py','src/task3/sft_v1_evaluation.py','src/task3/prompt_crossover.py','src/task3/prompt_crossover_analysis.py','src/task3/fresh_eval.py','src/task3/sft_v1_experiment.py','src/task3/sft_v1_runtime.py','src/task3/sft_v1.py','src/task3/sft_v3.py']
    frozen={str(p):sha256(p) for p in out.iterdir() if p.is_file()}
    frozen.update({str(REPO/n):sha256(REPO/n) for n in code_names})
    for n in code_names:
        dest=out/'source-snapshot'/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(REPO/n,dest)
    m=dict(version='matched-base-pv3-control-v1',created_utc=datetime.now(timezone.utc).isoformat(),
        previous=str(PREVIOUS),branch=state['branch'],head=state['head'],files=frozen,historical_files=historical_files,
        runtime=c,v3=v3,versions=c['versions'],python=platform.python_version(),
        budget=dict(new_base_calls=120,reused_v3=120,semantic_retries=0,extra_sampling=0,training=0,public_inference=0),
        runtime_gate='matching-audit.json and runtime-seal.json must be written and verified before first reservation.',
        allowed_model_input='Exact historical system/user messages only; no gold, witnesses, review, or reference solutions.',
        compiler_log_projection='Unchanged historical syntax-only compiler projection in saved messages; input IDs prove identical.',
        no_recovery='One call per exact binding. Recover completed journal output. Unresolved reservations explicitly unknown and never replayed.')
    write_json(out/'manifest.json',m);write_json(out/'manifest.sha256.json',dict(sha256=sha256(out/'manifest.json')))
    write_json(out/'run-status.json',dict(status='frozen_pending_runtime_gate',calls=0))
    print(json.dumps(dict(status='frozen',out=str(out),targets=120)),flush=True)


def verify(out):
    m=load(out/'manifest.json')
    if sha256(out/'manifest.json')!=load(out/'manifest.sha256.json')['sha256']: raise ValueError('manifest seal')
    verify_files(m['files']);verify_files(m['historical_files'])
    state=load(out/'initial-workspace-state.json');verify_files(state['files'])
    if subprocess.check_output(['git','branch','--show-current'],cwd=REPO,text=True).strip()!=m['branch']: raise ValueError('branch')
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()!=m['head']: raise ValueError('HEAD')
    return m


def weight_identity(model):
    return {n.replace('.base_layer.','.'):tensor_digest(p) for n,p in model.named_parameters() if 'lora_' not in n}


def run(out):
    m=verify(out);examples=load(out/'prompts.private.json');ids=[e['example_id'] for e in examples]
    journal=ControlJournal(out/'journal.jsonl',ids)
    rows=read_jsonl(out/'base-generations.jsonl') if (out/'base-generations.jsonl').exists() else []
    seen=set()
    ei={e['example_id']:e for e in examples}
    for row in rows:
        eid=row['example_id'];state,result=call_state(journal,'base/'+eid)
        if eid in seen or eid not in ei or (row['sample_id'],row['level'])!=(ei[eid]['sample_id'],ei[eid]['level']): raise ValueError('durable binding corruption')
        if state=='completed':
            if {k:v for k,v in row.items() if k!='utc'}!=result: raise ValueError('durable completion corrupted')
        elif not (state=='uncertain' and row.get('call_count_uncertain') and row['finish_reason']=='interrupted_unknown'): raise ValueError('durable unbound output')
        seen.add(eid)
    if len(seen)==120:
        print(json.dumps(dict(status='resume_noop',completed=120,new_calls=0)),flush=True);return
    for k in ['HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE']:os.environ[k]='1'
    os.environ['HF_HOME']=str(Path(m['runtime']['loader_manifest']['config']['tokenizer_local']).parents[3])
    import torch
    import bitsandbytes as bnb
    from peft import PeftModel
    from peft.tuners.lora.layer import LoraLayer
    from transformers import set_seed
    from src.task3.sft_v2_runtime import load_native
    from src.task3.sft_v2_public_context import generate
    if torch.version.cuda!='12.8' or not torch.cuda.is_bf16_supported(): raise ValueError('CUDA/BF16 runtime mismatch')
    torch.cuda.reset_peak_memory_stats();tick=time.perf_counter()
    base,tok=load_native(m['runtime']['loader_manifest'],journal)
    base.eval();before=weight_identity(base)
    set_seed(42);model=PeftModel.from_pretrained(base,m['v3']['checkpoint'],is_trainable=False);model.eval()
    enabled=profile_native(model,bnb);validate_runtime_profile(enabled)
    hist=load(PREVIOUS/'generations/V3-v3/runtime-before.json')
    for k in hist:
        if k!='observation_scope' and enabled[k]!=hist[k]: raise ValueError('enabled runtime differs from saved V3: '+k)
    if before!={n.removeprefix('base_model.model.'):h for n,h in weight_identity(model).items()}: raise ValueError('adapter load modified base weights')
    layers=[x for x in model.modules() if isinstance(x,LoraLayer)]
    if len(layers)!=196 or any(x.merged_adapters for x in layers): raise ValueError('merged/incorrect LoRA')
    counts={r['example_id']:r['input_tokens'] for r in read_jsonl(out/'input-ids.private.jsonl')}
    hashes={r['example_id']:r['token_id_sha256'] for r in read_jsonl(out/'input-ids.private.jsonl')}
    validate_prompts(tok,examples,counts,hashes)
    load_cost=dict(wall_s=time.perf_counter()-tick,peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),scope='load, adapter attach and byte hashes; no model forward')
    with model.disable_adapter():
        if not all(x.disable_adapters and not x.merged_adapters for x in layers): raise ValueError('adapter active')
        if any(p.requires_grad for p in model.parameters()) or any(x.training for x in model.modules()): raise ValueError('eval/frozen failure')
        disabled=profile_native(model,bnb)
        for k in ['parameter_dtypes','lora_dtypes','attention','quantization','compute_type_flags','generation_config','model_config_use_cache','gradient_checkpointing']:
            if enabled[k]!=disabled[k]: raise ValueError('disable changed runtime: '+k)
        audit=dict(matched=True,matched_targets=120,historical_single_attempt=True,exact_input_ids_match_historical_hashes=True,
            model_revision=m['runtime']['loader_manifest']['config']['revision'],enabled_profile=enabled,disabled_profile=disabled,
            mechanism='PEFT 0.17.1 PeftModel.disable_adapter() context; all 196 LoraLayer.disable_adapters True; no merged_adapters; base_layer forward only.',
            disable_adapter_source_sha256=hashlib.sha256(inspect.getsource(PeftModel.disable_adapter).encode()).hexdigest(),
            lora_forward_source_sha256=hashlib.sha256(inspect.getsource(bnb.nn.Linear4bit.forward).encode()).hexdigest(),
            lora_layers=196,disabled_layers=196,merged_layers=0,all_modules_eval=True,trainable_parameters=0,
            base_weights_equal_before_after_attach=True,optimizer_created=False,optimizer_steps=0,
            non_adapter_parameter_hashes=before,load_cost=load_cost,
            comparison_scope='Same pinned prepared model/runtime and allowed inputs; adapter disabled vs historical enabled outputs. No claim about a training-data/optimizer causal mechanism.')
        if (out/'matching-audit.json').exists():
            prior=load(out/'matching-audit.json')
            for k in ['non_adapter_parameter_hashes','disabled_profile','enabled_profile','matched_targets']:
                if audit[k]!=prior[k]:raise ValueError('resume runtime mismatch')
        else:
            write_json(out/'matching-audit.json',audit)
            write_json(out/'runtime-seal.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),manifest_sha256=sha256(out/'manifest.json'),matching_audit_sha256=sha256(out/'matching-audit.json'),before_first_reservation=len(journal.reserved())==0))
        if sha256(out/'matching-audit.json')!=load(out/'runtime-seal.json')['matching_audit_sha256']:raise ValueError('runtime seal changed')
        start=time.perf_counter();torch.cuda.reset_peak_memory_stats()
        for e in examples:
            eid=e['example_id']
            if eid in seen: continue
            key='base/'+eid;action,result=call_state(journal,key)
            if action!='completed':
                journal.append(dict(type='input_binding',key=key,prompt_sha256=digest(e['prompt']),token_id_sha256=hashes[eid],input_tokens=counts[eid],manifest_sha256=sha256(out/'manifest.json')))
                result=generate(model,tok,e,m['runtime']['generation'],journal,key,32768)
            if not result.get('call_count_uncertain') and result['input_tokens']!=counts[eid]:raise ValueError('runtime input binding mismatch')
            Journal(out/'base-generations.jsonl').append(result);rows.append(result);seen.add(eid)
            write_json(out/'run-status.json',dict(status='running',completed=len(seen),reservations=len(journal.reserved()),unknown=sum(bool(r.get('call_count_uncertain')) for r in rows)))
            print(json.dumps(dict(completed=len(seen),id=eid,status=result['status'],action=action)),flush=True)
        after=weight_identity(model)
        if before!={n.removeprefix('base_model.model.'):h for n,h in after.items()}:raise ValueError('base weights changed during generation')
        if profile_native(model,bnb)['quantization']!=disabled['quantization']:raise ValueError('quantization changed')
        write_json(out/'runtime-after.json',dict(non_adapter_weights_unchanged=True,optimizer_steps=0,disabled_layers=sum(x.disable_adapters for x in layers),merged_layers=sum(bool(x.merged_adapters) for x in layers),all_modules_eval=not any(x.training for x in model.modules())))
        write_json(out/'base-runtime.json',dict(targets=len(rows),physical_calls=len(journal.reserved()),unknown=sum(bool(r.get('call_count_uncertain')) for r in rows),
            generation_wall_s=sum(r['wall_s'] for r in rows),phase_wall_s=time.perf_counter()-start,input_tokens=sum(r['input_tokens'] for r in rows),output_tokens=sum(r['output_tokens'] for r in rows),
            peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),load_cost=load_cost,
            memory_scope='peak allocated/reserved in this control generation phase; includes resident disabled adapter; load/hash peak separately; phase wall includes final weight hash'))
    matched_population(examples,rows)
    write_json(out/'run-status.json',dict(status='generations_complete_pending_review',completed=120,physical_calls=len(journal.reserved())))


def main():
    a=argparse.ArgumentParser();a.add_argument('stage',choices=['prepare','run','verify']);a.add_argument('--out',type=Path,default=DEFAULT_OUT);args=a.parse_args()
    if args.stage=='prepare':prepare(args.out.resolve())
    elif args.stage=='run':run(args.out.resolve())
    else:verify(args.out.resolve());print('frozen files and workspace preserved')

if __name__=='__main__': main()
