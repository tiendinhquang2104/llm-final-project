"""Frozen four-cell dev crossover: no training, public inference or semantic retries."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import difflib
import gc
from importlib.metadata import version
import json
from pathlib import Path
import random
import re
import secrets
import shutil
import sys
import time

REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from src.task3.prompt_crossover import (AXES,CELL_IDS,REVIEW_POLICY,CrossoverJournal,call_state,
    prompt_examples,validate_population,verify_hashes,verify_run,preserve)
from src.task3.prompt_crossover import validate_durable_rows,validate_runtime_profile
from src.task3.sft_v1 import read_jsonl,sha256
from src.task3.sft_v1_experiment import Journal,write_json
from src.task3.sft_v1_runtime import digest,adapter_identity,tensor_digest
from src.task3.sft_v1_evaluation import EVALUATION_POLICY,parse_response
from src.task3.sft_v2_runtime import load_native,validated_selection
from src.task3.sft_v3_runtime import validate_selection
from src.task3.sft_v2_public_context import generate as native_generate
from scripts.task3_sft_v3_review import validate_review_ids,resolved_code_verdict,executable_verdict

V2=REPO/'outputs/task3/sft-v2-qlora-20261026-run1'
V3=REPO/'outputs/task3/sft-v3-qlora-20261026-run1'
COMPARISONS={'v2_prompt':('v2-old','v2-v3'),'v3_prompt':('v3-old','v3-v3'),
             'old_adapter':('v2-old','v3-old'),'v3_adapter':('v2-v3','v3-v3')}


def load(path):return json.loads(Path(path).read_text())


def freeze(out):
    import bitsandbytes,transformers,peft
    from safetensors.torch import load_file
    from transformers import AutoTokenizer
    if (out/'manifest.json').exists():raise FileExistsError('crossover already frozen')
    preserve(out)
    audit=load(out/'audit/runtime-reuse.private.json');prompt_audit=load(out/'audit/prompt-input.private.json')
    old=load(V2/'manifest.json');new=load(V3/'manifest.json')
    selections={'v2':validated_selection(REPO,V2,old),'v3':validate_selection(REPO,V3,new)}
    if selections['v2']['step']!=240 or selections['v3']['step']!=480:raise ValueError('unexpected selected adapters')
    hardware=load(out/'audit/hardware.json')
    if not hardware['versions_match_v3'] or hardware['cuda_build']!='12.8' or hardware['python']!='3.12.3':raise ValueError('runtime environment differs')
    if 'NVIDIA GeForce RTX 5090, 32607 MiB, 590.48.01' not in hardware['gpu']:raise ValueError('hardware mismatch')
    for name,v in new['versions'].items():
        if version(name)!=v:raise ValueError('dependency changed: '+name)
    roots={'old':REPO/'data/raw/task3-sft-v2','v3':REPO/'data/raw/task3-sft-v3'}
    if (roots['old']/'dev.records.jsonl').read_bytes()!=(roots['v3']/'dev.records.jsonl').read_bytes():raise ValueError('dev source/spec/gold changed')
    records=read_jsonl(roots['old']/'dev.records.jsonl')
    if len(records)!=80 or len({r['source_id'] for r in records})!=20:raise ValueError('dev population')
    authoritative=Path('/workspace/llm-final-project/data/raw/public_test_release/label_space.json')
    labels=load(authoritative)['taxonomy_error']
    for root in roots.values():
        if load(root/'label_space.json')['taxonomy_error']!=labels:raise ValueError('authoritative labels differ')
    tokenizer=AutoTokenizer.from_pretrained(new['config']['tokenizer_local'],local_files_only=True,trust_remote_code=False)
    model_config=load(Path(new['config']['tokenizer_local'])/'config.json')
    if model_config['max_position_embeddings']!=32768 or model_config.get('rope_scaling') is not None:raise ValueError('context profile changed')
    examples={};tokens={};token_hashes={}
    for arm,root in roots.items():
        examples[arm]=prompt_examples(records,root,labels)
        tokens[arm]={e['example_id']:len(tokenizer.apply_chat_template(e['prompt'],tokenize=True,add_generation_prompt=True)) for e in examples[arm]}
        token_hashes[arm]={e['example_id']:digest(tokenizer.apply_chat_template(e['prompt'],tokenize=True,add_generation_prompt=True)) for e in examples[arm]}
        for e in examples[arm]:
            if tokens[arm][e['example_id']]+new['generation']['max_new_tokens'][str(e['level'])]>32768:raise ValueError('nontruncating inference context exceeded')
        write_json(out/'inputs'/f'{arm}.examples.private.json',examples[arm])
        target=out/'prompts'/f'P_{arm}_SYSTEM_PROMPT.txt';target.parent.mkdir(exist_ok=True);shutil.copyfile(root/'SYSTEM_PROMPT.txt',target)
    if [e['prompt'][1] for e in examples['old']]!=[e['prompt'][1] for e in examples['v3']]:raise ValueError('user-message input corruption')
    write_json(out/'inputs/token-counts.json',tokens)
    write_json(out/'inputs/token-id-hashes.json',token_hashes)
    shutil.copyfile(authoritative,out/'inputs/label_space.json')
    (out/'evaluation').mkdir(exist_ok=True);shutil.copyfile(roots['old']/'dev.records.jsonl',out/'evaluation/dev.records.private.jsonl')
    (out/'prompts/system-prompt.diff').write_text(''.join(difflib.unified_diff(
        (roots['old']/'SYSTEM_PROMPT.txt').read_text().splitlines(True),(roots['v3']/'SYSTEM_PROMPT.txt').read_text().splitlines(True),fromfile='P_old',tofile='P_v3')))
    write_json(out/'review-policy.json',REVIEW_POLICY);write_json(out/'parser-policy.json',EVALUATION_POLICY['parser'])
    reuse=dict(audit,technical_matching=True,planned_new_calls=160,reused_outputs=160,
        planned_cells={'v2-old':'fresh','v2-v3':'reused','v3-old':'fresh','v3-v3':'reused'},
        matching_limit='Reused v3 cells match recorded hardware/build/code/input/tensor contracts; do not claim bitwise reproducibility across unmeasured device microstate.')
    if audit['cells']['v2-old']['reusable'] or not all(audit['cells'][c]['reusable'] for c in ('v2-v3','v3-v3')):raise ValueError('reuse plan differs from audited decision')
    write_json(out/'reuse-audit.json',reuse)
    cells={};historical_bindings={}
    for base in (V2,V3):
        for name in ('manifest.json','selection.json','selection.sha256.json'):
            historical_bindings[str((base/name).relative_to(REPO))]=sha256(base/name)
    identities={}
    for role,selection in selections.items():
        adapter=Path(selection['checkpoint']).resolve()
        identities[role]={k:tensor_digest(v) for k,v in load_file(str(adapter/'adapter_model.safetensors'),device='cpu').items()}
        if len(identities[role])!=392:raise ValueError('adapter tensor count')
    for cell in CELL_IDS:
        role,arm=cell.split('-');adapter=Path(selections[role]['checkpoint']).resolve()
        historical=None if cell=='v3-old' else Path(audit['cells'][cell]['historical_dir'])
        mode='reused' if cell in ('v2-v3','v3-v3') else 'fresh'
        cells[cell]=dict(adapter_role=role,adapter_path=str(adapter),prompt_arm=arm,mode=mode,
            historical_dir=str(historical) if historical else None,
            adapter_files={str((adapter/n).relative_to(REPO)):sha256(adapter/n) for n in ('adapter_model.safetensors','adapter_config.json','checkpoint-identity.json')},
            expected_adapter_tensor_identity=identities[role],prompt_hashes={e['example_id']:digest(e['prompt']) for e in examples[arm]})
        if historical:
            for name in ('generations.jsonl','complete.json')+ (('state-binding.json',) if mode=='reused' else ()):
                historical_bindings[str((historical/name).relative_to(REPO))]=sha256(historical/name)
        cells[cell]['method_identity']=digest(dict(cell=cell,adapter_files=cells[cell]['adapter_files'],prompts=cells[cell]['prompt_hashes'],
            context=32768,generation=new['generation'],parser=EVALUATION_POLICY['parser'],runtime=audit['common_runtime']))
    code_names=['src/task3/prompt_crossover.py','src/task3/prompt_crossover_analysis.py','scripts/task3_prompt_crossover.py',
        'scripts/task3_prompt_crossover_report.py','src/task3/sft_v1.py','src/task3/sft_v1_runtime.py','src/task3/sft_v1_experiment.py',
        'src/task3/sft_v1_evaluation.py','src/task3/sft_v2_runtime.py','src/task3/sft_v2_public_context.py','src/task3/sft_v2_public.py',
        'src/task3/sft_v3.py','scripts/task3_sft_v3_review.py','scripts/task3_sft_v1_l4_audit.py','scripts/task3_sft_v1_l4_unfenced_audit.py','src/task3/cpp_sandbox.py']
    code={name:sha256(REPO/name) for name in code_names}
    for name in code:
        target=out/'source-snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(REPO/name,target)
    input_paths=[out/n for n in ('request.txt','reuse-audit.json','review-policy.json','parser-policy.json','audit/runtime-reuse.private.json','audit/prompt-input.private.json','audit/hardware.json','audit/compute-dtype-addendum.json','preflight-failures.json')]
    for name in ('inputs','evaluation','prompts'):input_paths += [p for p in (out/name).rglob('*') if p.is_file()]
    initial=load(out/'initial-workspace-state.json')
    runtime=dict(loader_manifest={k:new[k] for k in ('config','model_files','tokenizer','versions')},common_profile=audit['common_runtime'],context=32768,
        generation=new['generation'],parser=EVALUATION_POLICY['parser'],seed=42,
        effective_repetition_penalty=1.1,hardware=hardware,training=False,teacher_forced_evaluation=False)
    dependencies=[Path(bitsandbytes.__file__).parent/'nn/modules.py',Path(transformers.__file__).parent/'integrations/bitsandbytes.py',
        Path(transformers.__file__).parent/'models/qwen2/modeling_qwen2.py',Path(transformers.__file__).parent/'integrations/sdpa_attention.py',Path(peft.__file__).parent/'utils/other.py']
    runtime['dependency_source_files']={str(p):sha256(p) for p in dependencies}
    runtime['linear4bit_compute_dtype_proof']=load(out/'audit/compute-dtype-addendum.json')
    manifest=dict(version='task3-prompt-crossover-v1',created_utc=datetime.now(timezone.utc).isoformat(),head=initial['head'],branch=initial['branch'],
        planned_new_calls=160,maximum_new_calls=320,cell_call_ceiling=80,targets_per_cell=80,sources=20,cells=cells,runtime=runtime,
        technical_matching=True,code_files=code,historical_bindings=historical_bindings,
        input_files={str(p.relative_to(out)):sha256(p) for p in input_paths},review_policy=REVIEW_POLICY,
        code_policy=dict(extractor='unchanged historical fenced+unfenced',runner='unchanged CppSandbox/harness/tests/checker',new_compile_ceiling=320,new_runtime_ceiling=25000,semantic_retries=0),
        analysis_policy=dict(comparisons=COMPARISONS,selection='no winner chosen by disclosure or overall joint',examples='deterministic family-diverse sorted source+Level; publish all cases'))
    write_json(out/'manifest.json',manifest);write_json(out/'manifest.sha256.json',dict(sha256=sha256(out/'manifest.json')))
    verify_run(out,preserve=True)
    print(json.dumps(dict(status='frozen',new_calls=160,reused_outputs=160,cells=reuse['planned_cells'])),flush=True)


def run(out):
    import torch
    import bitsandbytes as bnb
    from peft import PeftModel
    from transformers import set_seed
    verify_run(out);m=load(out/'manifest.json');fresh=[c for c in CELL_IDS if m['cells'][c]['mode']=='fresh']
    examples={arm:load(out/'inputs'/f'{arm}.examples.private.json') for arm in ('old','v3')};tokens=load(out/'inputs/token-counts.json')
    token_hashes=load(out/'inputs/token-id-hashes.json')
    journal=CrossoverJournal(out/'journal.jsonl',fresh,[e['example_id'] for e in examples['old']])
    def input_binding(cell,e):
        cm=m['cells'][cell]
        return dict(type='crossover_input_binding',key=cell+'/'+e['example_id'],cell=cell,method_identity=cm['method_identity'],sample_id=e['sample_id'],level=e['level'],
            prompt_sha256=digest(e['prompt']),input_tokens=tokens[cm['prompt_arm']][e['example_id']],manifest_sha256=sha256(out/'manifest.json'))
    for cell in fresh:
        directory=out/'cells'/cell;ex=examples[m['cells'][cell]['prompt_arm']]
        rows=read_jsonl(directory/'generations.jsonl') if (directory/'generations.jsonl').exists() else []
        validate_durable_rows(rows,ex,journal,cell)
        for e in ex:
            key=cell+'/'+e['example_id']
            prior=[{k:v for k,v in x.items() if k!='utc'} for x in journal.events() if x.get('type')=='crossover_input_binding' and x.get('key')==key]
            if (prior and (len(prior)!=1 or prior[0]!=input_binding(cell,e))) or (key in journal.reserved() and not prior):raise ValueError('prior call input binding changed/missing')
        if (directory/'complete.json').exists():
            validate_population(rows,ex);complete=load(directory/'complete.json')
            if complete['targets']!=80 or complete['generation']['calls']+complete['unknown']!=80:raise ValueError('completed cell coverage changed')
    for cell in CELL_IDS:
        cm=m['cells'][cell];directory=out/'cells'/cell
        if cm['mode']!='reused':continue
        directory.mkdir(parents=True,exist_ok=True);historical=Path(cm['historical_dir'])
        target=directory/'generations.jsonl'
        if target.exists():
            if sha256(target)!=sha256(historical/'generations.jsonl'):raise ValueError('copied historical raw changed')
        else:shutil.copyfile(historical/'generations.jsonl',target)
        validate_population(read_jsonl(target),examples[cm['prompt_arm']])
        write_json(directory/'cell-provenance.json',dict(cell=cell,mode='reused',method_identity=cm['method_identity'],
            source_files={str(historical/'generations.jsonl'):sha256(historical/'generations.jsonl'),str(historical/'complete.json'):sha256(historical/'complete.json')},
            historical_complete=load(historical/'complete.json'),historical_binding=load(historical/'state-binding.json'),new_model_calls=0))
        write_json(directory/'complete.json',dict(mode='reused',targets=80,new_generation_calls=0,historical_generation_calls=80,
            historical_generation_wall_s=load(historical/'complete.json')['generation']['wall_s'],
            memory_scope='historical phase only; no new model load/generation charged to reused cell'))
    pending=[c for c in fresh if not (out/'cells'/c/'complete.json').exists()]
    if not pending:return
    base,tokenizer=load_native(m['runtime']['loader_manifest'],journal)
    if float(base.generation_config.repetition_penalty)!=m['runtime']['effective_repetition_penalty']:raise ValueError('effective decoding config changed')
    for cell in pending:
        cm=m['cells'][cell];directory=out/'cells'/cell;directory.mkdir(parents=True,exist_ok=True)
        set_seed(m['runtime']['seed']);model=PeftModel.from_pretrained(base,cm['adapter_path'],is_trainable=False);model.eval()
        if set(model.peft_config)!={'default'} or list(model.active_adapters)!=['default'] or any(x.training for x in model.modules()):raise ValueError('active adapter/eval mismatch')
        identity=adapter_identity(model)
        if identity!=cm['expected_adapter_tensor_identity']:raise ValueError('actual adapter differs from saved selected tensors')
        profile=dict(active_adapters=list(model.active_adapters),adapter_names=list(model.peft_config),all_modules_eval=True,
            parameter_dtypes=dict(Counter(str(p.dtype) for p in model.parameters())),lora_dtypes=dict(Counter(str(p.dtype) for n,p in model.named_parameters() if 'lora_' in n)),
            attention=model.config._attn_implementation,model_config_use_cache=model.config.use_cache,generation_use_cache=True,
            gradient_checkpointing=model.is_gradient_checkpointing,gradient_checkpointing_active=False,
            generation_config=model.generation_config.to_dict(),adapter_identity=identity)
        quant=[x for x in model.modules() if isinstance(x,bnb.nn.Linear4bit)]
        profile['quantization']=dict(linear4bit_modules=len(quant),compute_dtypes=dict(Counter(str(x.compute_dtype) for x in quant)),
            storage_dtypes=dict(Counter(str(x.weight.dtype) for x in quant)),quant_types=dict(Counter(x.weight.quant_type for x in quant)),nested=all(x.weight.quant_state.nested for x in quant))
        profile['compute_type_flags']=dict(Counter(str(x.compute_type_is_set) for x in quant))
        validate_runtime_profile(profile)
        for e in examples[cm['prompt_arm']]:
            ids=tokenizer.apply_chat_template(e['prompt'],tokenize=True,add_generation_prompt=True)
            if len(ids)!=tokens[cm['prompt_arm']][e['example_id']] or digest(ids)!=token_hashes[cm['prompt_arm']][e['example_id']]:raise ValueError('loaded tokenizer changes frozen input IDs')
        provenance=dict(cell=cell,mode='fresh',method_identity=cm['method_identity'],adapter_path=cm['adapter_path'],runtime=profile,source_files=cm['adapter_files'])
        existing=directory/'cell-provenance.json'
        if existing.exists() and load(existing)!=provenance:raise ValueError('resume runtime identity changed')
        if not existing.exists():write_json(existing,provenance)
        rows=read_jsonl(directory/'generations.jsonl') if (directory/'generations.jsonl').exists() else [];seen={r['example_id'] for r in rows}
        if len(seen)!=len(rows):raise ValueError('duplicate durable generation')
        tick=time.perf_counter();torch.cuda.reset_peak_memory_stats()
        for e in examples[cm['prompt_arm']]:
            if e['example_id'] in seen:continue
            key=cell+'/'+e['example_id'];action,result=call_state(journal,key)
            binding=input_binding(cell,e)
            prior=[{k:v for k,v in x.items() if k!='utc'} for x in journal.events() if x.get('type')=='crossover_input_binding' and x.get('key')==key]
            if prior and (len(prior)!=1 or prior[0]!=binding):raise ValueError('call input binding changed')
            if action=='completed':pass
            else:
                if not prior:journal.append(binding)
                result=native_generate(model,tokenizer,e,m['runtime']['generation'],journal,key,m['runtime']['context'])
            if not result.get('call_count_uncertain') and result['input_tokens']!=binding['input_tokens']:raise ValueError('actual token count differs from frozen input')
            Journal(directory/'generations.jsonl').append(result);rows.append(result);seen.add(e['example_id'])
            print(json.dumps(dict(cell=cell,generated=len(rows),id=e['example_id'],status=result['status'],action=action)),flush=True)
        validate_population(rows,examples[cm['prompt_arm']])
        write_json(directory/'complete.json',dict(mode='fresh',targets=80,wall_s=time.perf_counter()-tick,
            generation=dict(calls=sum(not r.get('call_count_uncertain') for r in rows),wall_s=sum(r['wall_s'] for r in rows)),
            input_tokens=sum(r['input_tokens'] for r in rows),output_tokens=sum(r['output_tokens'] for r in rows),
            unknown=sum(bool(r.get('call_count_uncertain')) for r in rows),peak_allocated_bytes=torch.cuda.max_memory_allocated(),
            peak_reserved_bytes=torch.cuda.max_memory_reserved(),memory_scope='this fresh inference cell only; load excluded, allocator cache may persist; no teacher forcing',
            resume_scope='wall/peak covers current invocation; durable rows include prior completed calls if resumed'))
        base=model.unload();del model;gc.collect();torch.cuda.empty_cache()
    journal.append(dict(type='crossover_generation_complete',fresh_cells=fresh,new_reservations=len(journal.reserved())))


def code_checks(out):
    import scripts.task3_sft_v1_l4_audit as audit
    from scripts.task3_sft_v1_l4_unfenced_audit import extract_unfenced
    from src.task3.cpp_sandbox import CppSandbox
    verify_run(out);m=load(out/'manifest.json');cases={c['sample_id']:c for c in load(REPO/'data/raw/task3-sft-v1/cases.private.json') if c['split']=='dev'}
    original=audit.extract_cpp
    def extract(feedback):
        found=original(feedback)
        return found if found['status']=='extracted' or '```' in feedback else extract_unfenced(feedback)
    evidence=out/'code-evidence';evidence.mkdir(exist_ok=True);sandbox=CppSandbox(audit.TEMPLATE);all_results=[]
    try:
        audit.extract_cpp=extract
        for cell in CELL_IDS:
            cm=m['cells'][cell]
            if not (out/'cells'/cell/'complete.json').exists():raise ValueError('incomplete cell '+cell)
            for row in read_jsonl(out/'cells'/cell/'generations.jsonl'):
                target=evidence/cell/(row['example_id']+'.json');binding=dict(cell=cell,example_id=row['example_id'],generation_sha256=digest(row),case_sha256=digest(cases[row['sample_id']]))
                if target.exists():
                    result=load(target)
                    if any(result.get(k)!=v for k,v in binding.items()):raise ValueError('code-evidence binding changed')
                    all_results.append(result);continue
                if cm['mode']=='reused':
                    oldpath=V3/'code-evidence'/Path(cm['historical_dir']).name/(row['example_id']+'.json');old=load(oldpath)
                    if any(old[k]!=binding[k] for k in ('example_id','generation_sha256','case_sha256')):raise ValueError('historical code evidence not exactly reusable')
                    result=dict(old,**binding,reused=True,reused_source=str(oldpath),reused_source_sha256=sha256(oldpath),new_compile_calls=0,new_runtime_calls=0)
                    if old.get('detail_path'):
                        detail_dir=evidence/'details'/cell/row['example_id'];shutil.copytree((V3/old['detail_path']).parent,detail_dir,dirs_exist_ok=True)
                        result['detail_path']=str((detail_dir/'result.json').relative_to(out))
                elif row['status']!='valid':result=dict(**binding,status='not_evaluable',code_verdict='uncertain',new_compile_calls=0,new_runtime_calls=0,reused=False)
                else:
                    found=extract(row['parsed']['feedback'])
                    if found['status']!='extracted':
                        present='```' in row['parsed']['feedback'] or bool(re.search(r'(?m)^\s*#include\b',row['parsed']['feedback']))
                        result=dict(**binding,status='partial_or_unextractable' if present else 'absent',code_verdict='uncertain' if present else 'absent',new_compile_calls=0,new_runtime_calls=0,reused=False,reason=found['reason'])
                    else:
                        if sum(r.get('new_compile_calls',0) for r in all_results)>=320 or sum(r.get('new_runtime_calls',0) for r in all_results)+len(cases[row['sample_id']]['tests'])>25000:raise ValueError('code ceiling')
                        detail=audit.audit_target(row,cases[row['sample_id']],evidence/'details'/cell,sandbox)
                        if detail.get('jail') and Path(detail['jail']).exists():shutil.rmtree(detail['jail'])
                        result=dict(**binding,status=detail['status'],code_verdict=executable_verdict(detail),reused=False,
                            new_compile_calls=int(detail.get('compile') is not None),new_runtime_calls=sum(t.get('executed',False) for t in detail['tests']),
                            detail_path=str((evidence/'details'/cell/row['example_id']/'result.json').relative_to(out)))
                write_json(target,result);all_results.append(result)
    finally:audit.extract_cpp=original
    write_json(evidence/'summary.json',dict(targets=len(all_results),counts=dict(Counter(r['status'] for r in all_results)),new_compile_calls=sum(r.get('new_compile_calls',0) for r in all_results),new_runtime_calls=sum(r.get('new_runtime_calls',0) for r in all_results),reused_targets=sum(r.get('reused',False) for r in all_results)))


def packets(out):
    verify_run(out);records=read_jsonl(out/'evaluation/dev.records.private.jsonl');sources={}
    for r in records:sources.setdefault(r['source_id'],r)
    generations={c:{r['example_id']:r for r in read_jsonl(out/'cells'/c/'generations.jsonl')} for c in CELL_IDS}
    directory=out/'review-packets';directory.mkdir(exist_ok=True);salt=directory/'blinding-salt.private.txt'
    if not salt.exists():salt.write_text(secrets.token_hex(32))
    binding={};pack=[];rng=random.Random(20261027)
    for sid,record in sources.items():
        groups={}
        for cell in CELL_IDS:
            for level in (1,2,3,4):
                eid=f'{sid}-L{level}';r=generations[cell][eid];rid=digest([salt.read_text(),cell,eid])[:24]
                evidence=load(out/'code-evidence'/cell/(eid+'.json'))
                binding[rid]=dict(cell=cell,example_id=eid,sample_id=sid,level=level,status=r['status'],generation_sha256=digest(r))
                key=digest(dict(level=level,status=r['status'],raw=r['raw']))
                if key not in groups:groups[key]=dict(review_ids=[],level=level,status=r['status'],raw=r['raw'],parsed=r['parsed'],
                    code_evidence={k:evidence[k] for k in ('status','code_verdict')})
                elif groups[key]['code_evidence']['code_verdict']!=evidence['code_verdict']:raise ValueError('identical response has conflicting executable code evidence')
                groups[key]['review_ids'].append(rid)
        panels=list(groups.values());rng.shuffle(panels)
        for i,p in enumerate(panels):p['panel']=i+1
        pack.append(dict(sample_id=sid,family_id=record['family_id'],statement=record['input']['statement'],code=record['input']['code'],
            syntax_only=record['input']['compile_log'],historical_taxonomy=record['output']['taxonomy_error'],responses=panels,
            caution='Read actual source/spec and all responses; historical taxonomy alone is not evidence. Same rubric for every cell; identities hidden where practical.'))
    write_json(directory/'binding.private.json',binding)
    for i in range(3):write_json(directory/f'crossover-{i}.private.json',pack[i::3])
    write_json(directory/'instructions.json',dict(policy=REVIEW_POLICY,axes=list(AXES),schema='review_ids exact whole panel group; axes9; code_verdict pass/fail/absent/uncertain; substantive evidence; code_resolution_evidence for uncertain supplied code resolved pass',
        taxonomy_feedback_contradiction='Required explicit boolean on valid panels, null on invalid: only internally contradictory taxonomy versus feedback; being jointly wrong about the source is not by itself an internal contradiction.',
        method='Source-grounded agent review, not independent human gold. All320 records adjudicated anew; no copying historical verdicts. Invalid axes all not_evaluable, code uncertain. L2 sentence count unrestricted; L4 code optional; wrong L3 advice correctness independent from disclosure.'))
    print(json.dumps(dict(targets=len(binding),sources=len(pack),panels=sum(len(s['responses']) for s in pack))))


def reviewed_rows(out):
    binding=load(out/'review-packets/binding.private.json');groups={};seen={};raw={c:{r['example_id']:r for r in read_jsonl(out/'cells'/c/'generations.jsonl')} for c in CELL_IDS}
    for i in range(3):
        for source in load(out/'review-packets'/f'crossover-{i}.private.json'):
            for panel in source['responses']:
                for rid in panel['review_ids']:groups[rid]=frozenset(panel['review_ids'])
    records={r['sample_id']:r for r in read_jsonl(out/'evaluation/dev.records.private.jsonl')}
    for path in sorted((out/'quality').glob('crossover-*.json')):
        content=load(path);content=content if isinstance(content,list) else content.get('records',content.get('reviews'))
        for verdict in content:
            validate_review_ids(verdict['review_ids'],groups);axes=verdict['axes']
            if set(axes)!=set(AXES) or not set(axes.values())<={'pass','fail','uncertain','not_applicable','not_evaluable'} or not verdict.get('evidence','').strip():raise ValueError('review schema')
            for rid in verdict['review_ids']:
                if rid in seen or rid not in binding:raise ValueError('duplicate/foreign review')
                b=binding[rid];r=raw[b['cell']][b['example_id']];record=records[b['example_id']]
                if digest(r)!=b['generation_sha256']:raise ValueError('reviewed response changed')
                if r['status']!='valid' and (set(axes.values())!={'not_evaluable'} or verdict['code_verdict']!='uncertain'):raise ValueError('invalid semantic verdicts')
                contradiction=verdict.get('taxonomy_feedback_contradiction')
                if (r['status']=='valid' and type(contradiction)is not bool) or (r['status']!='valid' and contradiction is not None):raise ValueError('explicit taxonomy/feedback contradiction verdict required')
                evidence=load(out/'code-evidence'/b['cell']/(b['example_id']+'.json'));cv=resolved_code_verdict(evidence['code_verdict'],verdict)
                seen[rid]=dict(**b,review_id=rid,axes=axes,code_verdict=cv,evidence=verdict['evidence'],raw=r['raw'],parsed=r['parsed'],finish_reason=r['finish_reason'],
                    faulty=bool(record['output']['taxonomy_error']),gold_taxonomy=record['output']['taxonomy_error'],family_id=record['family_id'],
                    taxonomy_feedback_contradiction=contradiction,
                    code_resolution_evidence=verdict.get('code_resolution_evidence',''),completed_review_record=dict(file=str(path.relative_to(out)),verdict=verdict))
    if set(seen)!=set(binding) or len(seen)!=320:raise ValueError(f'completed review coverage {len(seen)}/320')
    return list(seen.values())


def metrics(out):
    from src.task3.prompt_crossover_analysis import summarize,paired_analysis
    verify_run(out);rows=reviewed_rows(out);result={}
    for cell in CELL_IDS:
        subset=[r for r in rows if r['cell']==cell]
        result[cell]=dict(overall=summarize(subset),by_level={str(l):summarize([r for r in subset if r['level']==l]) for l in (1,2,3,4)},
            by_status={n:summarize([r for r in subset if r['faulty']==f]) for n,f in [('clean',False),('faulty',True)]},
            by_level_status={str(l):{n:summarize([r for r in subset if r['level']==l and r['faulty']==f]) for n,f in [('clean',False),('faulty',True)]} for l in (1,2,3,4)})
    paired={name:paired_analysis([r for r in rows if r['cell']==a],[r for r in rows if r['cell']==b]) for name,(a,b) in COMPARISONS.items()}
    write_json(out/'reviewed/verdicts.private.json',rows);write_json(out/'metrics.json',result);write_json(out/'paired-differences.json',paired)
    print(json.dumps({c:{k:v for k,v in x['overall'].items() if k in ('targets','invalid','clean_false_alarms','faulty_misses_with_invalid','supported_faulty_diagnosis','faulty_l3_correct','disclosure_compliant','successful_feedback')} for c,x in result.items()}))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['freeze','run','code','packets','metrics','verify']);parser.add_argument('--out',type=Path,required=True);a=parser.parse_args();out=a.out.resolve()
    if not out.is_relative_to(REPO/'outputs/task3'):raise ValueError('output must remain in repo')
    if a.stage=='freeze':freeze(out)
    elif a.stage=='run':run(out)
    elif a.stage=='code':code_checks(out)
    elif a.stage=='packets':packets(out)
    elif a.stage=='metrics':metrics(out)
    else:
        result=verify_run(out,preserve=True);m=load(out/'manifest.json');examples={arm:load(out/'inputs'/f'{arm}.examples.private.json') for arm in ('old','v3')}
        fresh=[c for c in CELL_IDS if m['cells'][c]['mode']=='fresh'];journal=CrossoverJournal(out/'journal.jsonl',fresh,[e['example_id'] for e in examples['old']]);labels=load(out/'inputs/label_space.json')['taxonomy_error']
        for cell in CELL_IDS:
            cm=m['cells'][cell];rows=read_jsonl(out/'cells'/cell/'generations.jsonl');validate_population(rows,examples[cm['prompt_arm']])
            if cm['mode']=='fresh':validate_durable_rows(rows,examples[cm['prompt_arm']],journal,cell)
            elif sha256(out/'cells'/cell/'generations.jsonl')!=sha256(Path(cm['historical_dir'])/'generations.jsonl'):raise ValueError('reused raw outputs changed')
            for row in rows:
                if row.get('call_count_uncertain'):continue
                parsed=parse_response(row['raw'],labels,row['finish_reason'])
                if parsed['status']!=row['status'] or parsed['parsed']!=row['parsed']:raise ValueError('frozen parser recomputation mismatch')
        events=journal.events();reservations=[e['key'] for e in events if e.get('type')=='generation_reserved'];completions=[e['key'] for e in events if e.get('type')=='generation_completed']
        if len(reservations)!=len(set(reservations)) or len(completions)!=len(set(completions)) or not set(completions)<=set(reservations) or len(reservations)>m['planned_new_calls']:raise ValueError('call journal identity/budget')
        result['generation']=dict(targets=320,sources=20,new_reservations=len(reservations),new_completed=len(completions),uncertain=len(set(reservations)-set(completions)),reused_outputs=160,parser_recomputed=True)
        write_json(out/'generation-integrity.json',result['generation']);write_json(out/'preservation-after.json',result['preservation']);print(json.dumps(result))


if __name__=='__main__':main()
