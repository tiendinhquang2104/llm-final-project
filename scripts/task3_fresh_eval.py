"""One frozen fresh-family experiment using the repository's existing pipelines."""
import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import gc
import importlib.util
from importlib.metadata import version
import json
import os
from pathlib import Path
import random
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time

REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from src.task3.fresh_eval import (AXES,POLICY,SYSTEMS,EvaluationJournal,build_targets,
    validate_dataset,text_sha)
from src.task3.sft_v1 import read_jsonl,sha256,native_prompt
from src.task3.sft_v1_experiment import write_json
from src.task3.sft_v1_runtime import digest,adapter_identity,tensor_digest
from src.task3.prompt_crossover import call_state,validate_runtime_profile
from src.task3.cpp_sandbox import CppSandbox

TEMPLATE=Path('/workspace/llm-final-project/outputs/task3/round23-20261022/sandbox-template')
LABELS=Path('/workspace/llm-final-project/data/raw/public_test_release/label_space.json')
R15=REPO/'outputs/task3/r15-abc-20261025'


def load(path):return json.loads(Path(path).read_text())


def jsonl(path,rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    with temp.open('w')as f:
        for row in rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        f.flush();os.fsync(f.fileno())
    temp.replace(path)


def import_file(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


def isolated_syntax(sandbox,code,parent):
    """Historical stdin/flags/3s/8000-char view, inside established confinement."""
    if len(code)>200000:raise ValueError('historical syntax input cap')
    jail=sandbox.create(parent)
    args=['/usr/bin/g++','-std=c++11','-fsyntax-only','-fno-diagnostics-color','-x','c++','-']
    try:
        with tempfile.TemporaryFile()as inp,tempfile.TemporaryFile()as out,tempfile.TemporaryFile()as err:
            inp.write(code.encode());inp.seek(0);start=time.monotonic()
            proc=subprocess.Popen(args,stdin=inp,stdout=out,stderr=err,
                env={'PATH':'/usr/bin','LC_ALL':'C','HOME':'/work','TMPDIR':'/work'},close_fds=True,
                preexec_fn=lambda:sandbox._enter(jail,True))
            timed_out=False
            try:proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                timed_out=True
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                proc.wait()
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            out.seek(0);err.seek(0);stdout=out.read(65536).decode(errors='replace');stderr=err.read(65536).decode(errors='replace')
        return dict(returncode=proc.returncode,stdout=stdout,stderr=stderr,timeout=timed_out,
            status='pass' if proc.returncode==0 and not timed_out else 'error',diagnostic=stderr[:8000],
            latency_s=time.monotonic()-start,isolation='chroot_uid_seccomp_rlimits',executed=True,
            command=args,diagnostic_cap=8000,wall_limit_s=3,source_sha256=text_sha(code))
    finally:shutil.rmtree(jail)


def verify_frozen(out):
    out=Path(out);m=load(out/'manifest.json')
    if sha256(out/'manifest.json')!=load(out/'manifest.sha256.json')['sha256']:raise ValueError('manifest changed')
    for name,expected in m['files'].items():
        path=Path(name) if Path(name).is_absolute() else out/name
        if not path.is_file() or sha256(path)!=expected:raise ValueError('frozen file changed: '+str(path))
    return dict(passed=True,files=len(m['files']))


def prepare(out):
    if (out/'manifest.json').exists() or (out/'dataset.private.jsonl').exists():raise FileExistsError('dataset already prepared/frozen')
    evidence=out/'evidence';evidence.mkdir(exist_ok=False)
    modules=[import_file('fresh_author_'+name,out/'authoring'/f'batch_{name}.py') for name in ('a','b')]
    families=[];oracle_checks={}
    for module in modules:
        oracle_checks[module.__name__]=module.self_check();families+=module.families()
    if len(families)!=20 or len({f['family_id'] for f in families})!=20:raise ValueError('family population')
    write_json(evidence/'oracle-self-checks.private.json',oracle_checks)
    labels=load(LABELS)['taxonomy_error'];sandbox=CppSandbox(TEMPLATE)
    sources=[];gold=[];cases=[];syntax={};validation=[]
    (out/'sources').mkdir(exist_ok=False)
    from scripts.task3_sft_v1_l4_audit import output_matches
    for family in sorted(families,key=lambda f:f['family_id']):
        tests=family['tests']
        if not tests or len(tests)>200 or tests[0]['input']!=family['witness_input']:
            raise ValueError('bounded witness-first test suite: '+family['family_id'])
        before,after=family['mutation']['before'],family['mutation']['after']
        if family['clean_code'].count(before)!=family['mutation']['count'] or family['clean_code'].replace(before,after,family['mutation']['count'])!=family['faulty_code']:
            raise ValueError('single mutation binding')
        for faulty in (False,True):
            code=family['faulty_code' if faulty else 'clean_code']
            sid='S'+text_sha(family['family_id']+('/right' if faulty else '/left'))[:12]
            source=dict(sample_id=sid,family_id=family['family_id'],statement=family['statement'],code=code,
                language='cpp11',exam_type='single_problem',checker=family['checker'])
            sources.append(source);codefile=out/'sources'/f'{sid}.cpp';codefile.write_text(code)
            syntax[sid]=isolated_syntax(sandbox,code,evidence/'jails')
            write_json(evidence/f'{sid}.syntax.json',syntax[sid])
            jail,compiled=sandbox.compile(code,evidence/'jails');runs=[]
            try:
                if compiled.get('returncode')!=0 or compiled.get('timeout'):raise ValueError('authored full program did not compile: '+sid)
                for i,test in enumerate(tests):
                    execution=sandbox.run(jail,stdin=test['input'],files=test.get('files'))
                    passed=execution['returncode']==0 and not execution['timeout'] and output_matches(execution['stdout'],test['expected'],family['checker'])
                    runs.append(dict(index=i,input=test['input'],expected=test['expected'],actual=execution,passed=passed))
                    if not faulty and not passed:raise ValueError('clean program failed: '+sid+' test '+str(i))
                    if faulty and (execution['timeout'] or execution['returncode']!=0):break
            finally:shutil.rmtree(jail)
            failures=[r for r in runs if not r['passed']]
            if faulty and (not failures or runs[0]['passed']):raise ValueError('fault lacks discriminating initial witness: '+sid)
            full=dict(sample_id=sid,family_id=family['family_id'],source_sha256=text_sha(code),
                statement_sha256=text_sha(family['statement']),faulty=faulty,compile=compiled,tests=runs,
                authored_tests=len(tests),executed_tests=len(runs),passed=sum(r['passed'] for r in runs),
                failures=len(failures),not_executed=len(tests)-len(runs),
                stop_reason='first abnormal termination/timeout; no repeated hanging executions' if len(runs)<len(tests) else None)
            ep=evidence/f'{sid}.execution.private.json';write_json(ep,full)
            validation.append(dict(sample_id=sid,family_id=family['family_id'],faulty=faulty,
                source_sha256=text_sha(code),evidence_path=str(ep.relative_to(out)),
                authored_tests=len(tests),executed_tests=len(runs),passed=full['passed'],failures=len(failures),
                compile=compiled,witness=runs[0]))
            g=dict(sample_id=sid,family_id=family['family_id'],title=family['title'],faulty=faulty,
                taxonomy=family['taxonomy'] if faulty else [],source_sha256=text_sha(code),statement_sha256=text_sha(family['statement']),
                defect=family['defect'] if faulty else None,location=family['location'] if faulty else None,
                trigger_conditions=family['trigger_conditions'] if faulty else [],expected_behavior=family['expected_behavior'],
                acceptable_l3=family['acceptable_l3'] if faulty else ['State that no defect/repair is required within the specification.'],
                unacceptable_l3=family['unacceptable_l3'] if faulty else ['Inventing an out-of-contract defect or changing a correct implementation.'],
                clean_invariant=family['clean_invariant'],alternative_interpretations=family['alternative_interpretations'],
                witness_input=family['witness_input'],witness_evidence_path=str(ep.relative_to(out)),
                test_design=family['test_design'],novelty=family['novelty'],mutation=family['mutation'] if faulty else None)
            gold.append(g)
            cases.append(dict(sample_id=sid,family_id=family['family_id'],statement=family['statement'],code_file=str(codefile),
                source_sha256=text_sha(code),harness='',checker=family['checker'],tests=tests,split='fresh',exam_type='single_problem'))
            write_json(evidence/'source-validation.private.json',validation)
            print(json.dumps(dict(stage='source_validation',family=family['family_id'],source=sid,faulty=faulty,tests=len(runs),failures=len(failures))),flush=True)
    validate_dataset(sources,gold,labels)
    jsonl(out/'dataset.private.jsonl',sources);jsonl(out/'gold.private.jsonl',gold)
    write_json(evidence/'cases.private.json',cases);write_json(out/'syntax.private.json',syntax)
    jsonl(out/'targets.private.jsonl',build_targets(sources,syntax))
    write_json(out/'dataset-manifest.json',dict(families=20,sources=40,targets_per_system=160,
        primary_targets_per_system=120,secondary_l4_targets_per_system=40,
        authored_inputs=sum(len(f['tests']) for f in families),executed_source_tests=sum(x['executed_tests'] for x in validation),
        source_sha256={s['sample_id']:text_sha(s['code']) for s in sources},
        limitation='Newly authored, not previously evaluated; finite tests and agent-authored/reviewed gold, not independent human gold or independence from pretraining.'))
    print(json.dumps(dict(stage='prepared',sources=40,targets=160,model_calls=0)),flush=True)


def A_records(out,targets):
    from src.task3.r15_abc_data import query_record
    syntax=load(out/'syntax.private.json')
    return [query_record(dict(sample_id=t['sample_id'],family=t['family_id'],
        statement=t['input']['statement'],code=t['input']['code'],exam_type=t['input']['exam_type'],
        compiler={k:syntax[t['source_id']][k] for k in ('status','diagnostic')}),t['input']['target_feedback_level']) for t in targets]


def offline(systems):
    for k,v in systems['A']['offline_environment'].items():
        if k!='ordering':os.environ[k]=v


def freeze(out):
    if (out/'manifest.json').exists():raise FileExistsError('already frozen')
    audit=load(out/'audit/systems-audit.private.json');offline(audit)
    if not audit['all_checks_passed'] or not load(out/'audit/actual-source-gold-novelty-review.private.json')['passed']:
        raise ValueError('independent pre-generation audits unresolved')
    from transformers import AutoTokenizer
    from src.task3 import r15_abc_experiment as abc
    from src.task3.prompt_crossover import prompt_examples
    from src.task3.sft_v1_evaluation import EVALUATION_POLICY
    from scripts.task3_fresh_eval_report import EXAMPLE_POLICY
    sources=read_jsonl(out/'dataset.private.jsonl');gold=read_jsonl(out/'gold.private.jsonl');targets=read_jsonl(out/'targets.private.jsonl')
    validate_dataset(sources,gold,load(LABELS)['taxonomy_error'])
    if build_targets(sources,load(out/'syntax.private.json'))!=targets:raise ValueError('target projection changed')
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=REPO,text=True).strip()
    initial=load(out/'initial-workspace-state.json')
    if branch!='fix/task3-strict-feedback' or subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()!=initial['head']:
        raise ValueError('workspace moved')
    common=audit['common_native_runtime']
    import torch
    hardware=dict(python=sys.version,torch=version('torch'),cuda_build=torch.version.cuda,
        visible_cuda_devices=torch.cuda.device_count(),
        gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv,noheader'],text=True).strip(),
        model_forward_calls=0)
    if hardware['visible_cuda_devices']!=1 or hardware['cuda_build']!='12.8' or hardware['gpu']!='NVIDIA GeForce RTX 5090, 32607 MiB, 590.48.01':
        raise ValueError('actual hardware differs from pinned runtime')
    write_json(out/'audit/hardware-pre-freeze.json',hardware)
    for package,v in common['versions'].items():
        if version(package)!=v:raise ValueError('pinned version changed: '+package)
    snapshot=Path(common['model_snapshot'])
    for name,h in common['loader_manifest']['model_files'].items():
        if sha256(snapshot/name)!=h:raise ValueError('physical model changed: '+name)
    for name,meta in common['tokenizer_files'].items():
        if sha256(snapshot/name)!=meta['expected']:raise ValueError('historical tokenizer changed: '+name)
    tokenizer=AutoTokenizer.from_pretrained(str(snapshot),local_files_only=True,trust_remote_code=False)
    runtime=abc.historical_module(R15,'task3.round15')
    Aconfig=audit['A']['config'];records=A_records(out,targets);labels=load(LABELS)['taxonomy_error']
    prompts={};token_counts={};token_hashes={};headroom={}
    for name,role in [('V2-old','v2'),('V3-v3','v3')]:
        root=Path(audit['native_systems'][role]['prompt_root'])
        prompts[name]=prompt_examples(targets,root,labels)
    prompts['A']=[]
    for t,r in zip(targets,records):
        cap=Aconfig['level4_max_tokens'] if t['input']['target_feedback_level']==4 else Aconfig['max_new_tokens']
        msgs,info=runtime.fitted_messages(r,[],tokenizer,{**Aconfig,'max_new_tokens':cap})
        if info['examples_dropped'] or info['examples_used']:raise ValueError('unexpected A examples')
        # A retry error is capped at500 Unicode characters. A byte-level BPE
        # has no more tokens than UTF8 bytes: reserve2000 tokens for any such
        # reason, plus exact fixed retry suffix and chat framing, plus32 margin.
        retry=runtime.build_messages(r,[],retry='x')[-1]
        retry_fixed=retry['content'].replace('x','',1)
        retry_tokens_bound=2000+len(retry_fixed.encode())+32
        ids=tokenizer.apply_chat_template(msgs,tokenize=True,add_generation_prompt=True)
        if len(ids)+retry_tokens_bound+cap>Aconfig['context_limit']:raise ValueError('A retry full-context allowance')
        headroom[t['sample_id']]=dict(initial_tokens=len(ids),retry_suffix_token_upper_bound=retry_tokens_bound,
            output_allowance=cap,total_bound=len(ids)+retry_tokens_bound+cap,context=Aconfig['context_limit'])
        prompts['A'].append(dict(example_id=t['sample_id'],sample_id=t['source_id'],level=t['input']['target_feedback_level'],prompt=msgs))
    if [e['prompt'][1] for e in prompts['V2-old']]!=[e['prompt'][1] for e in prompts['V3-v3']]:raise ValueError('native user payload mismatch')
    for name,examples in prompts.items():
        token_counts[name]={};token_hashes[name]={}
        for e in examples:
            ids=tokenizer.apply_chat_template(e['prompt'],tokenize=True,add_generation_prompt=True)
            cap=common['generation']['max_new_tokens'][str(e['level'])]
            context=16384 if name=='A' else 32768
            if len(ids)+cap>context:raise ValueError('prompt truncation would be required')
            token_counts[name][e['example_id']]=len(ids);token_hashes[name][e['example_id']]=digest(ids)
        write_json(out/'prompts'/f'{name}.private.json',examples)
    write_json(out/'prompts/token-counts.json',token_counts);write_json(out/'prompts/token-id-hashes.json',token_hashes)
    write_json(out/'prompts/A-retry-context-bounds.json',headroom)
    shutil.copyfile(LABELS,out/'prompts/label_space.json')
    write_json(out/'systems.json',audit)
    policy=dict(POLICY,example_selection=EXAMPLE_POLICY,native_parser=EVALUATION_POLICY['parser'],
        A_parser=audit['A']['parser_policy'],A_recovery=audit['A']['retries'],A_fallback=audit['A']['fallback_policy'],
        A_metric_compatibility='Canonical already-accepted A payload is projected only into inherited taxonomy aggregate helper; raw and true model finish reasons stay unchanged. No native EOS restriction imposed on A.',
        code_policy=dict(extractors='existing fenced/unfenced full-program extractors; partial snippets require source-grounded semantic review',
            runner='unchanged CppSandbox C++11 O0 and authored cases/checkers',compile_ceiling=480,runtime_ceiling=96000,
            stops='first confirmed failure/abnormal termination stops further tests for that supplied program; correct programs run all selected tests',
            absent='no full program extracted does not establish no visible code; reviewer must inspect snippets',
            invalid='not_evaluable, code uncertain; do not salvage malformed payloads'),
        blind=dict(method='per-response opaque random identifier; stable source/Level/spec/code/gold/evidence; no system/runtime/prompt metadata in packet',
            mapping='separate private file; reveal only after all480 verdicts are sealed',review='Codex source-grounded agent review, not independent human evaluation'),
        budget=dict(targets_per_system=160,systems=3,maximum_targets=480,maximum_calls=800,A=480,V2_old=160,V3_v3=160,
            warmups=0,teacher_forced_passes=0,training_steps=0,semantic_retries=0,reuse_generations=0),
        missing='retain missing/unknown reserved calls in denominator; never regenerate completed or uncertain calls')
    write_json(out/'frozen-policy.json',policy)
    # Bind concrete source, gold, settings, prompts, review/decision code and all
    # original scientific dependencies. Model snapshot symlinks are legitimate
    # pinned HF cache links: hash their physical contents, do not reject them.
    code=['src/task3/fresh_eval.py','scripts/task3_fresh_eval.py','scripts/task3_fresh_eval_report.py',
        'src/task3/prompt_crossover.py','src/task3/prompt_crossover_analysis.py','src/task3/sft_v3.py',
        'src/task3/sft_v1.py','src/task3/sft_v1_experiment.py','src/task3/sft_v1_runtime.py',
        'src/task3/sft_v1_evaluation.py','src/task3/sft_v2_runtime.py','src/task3/sft_v2_public.py',
        'src/task3/sft_v2_public_context.py','src/task3/cpp_sandbox.py','src/task3/r15_abc_experiment.py',
        'src/task3/r15_abc_data.py','scripts/task3_sft_v1_l4_audit.py','scripts/task3_sft_v1_l4_unfenced_audit.py']
    files=dict(audit['bindings'])
    for name in code:files[str(REPO/name)]=sha256(REPO/name)
    for folder in ('prompts','authoring','audit','sources','evidence'):
        for p in (out/folder).rglob('*'):
            if p.is_file() and '__pycache__'not in p.parts and p.suffix!='.log':files[str(p)]=sha256(p)
    for name in ('request.txt','systems.json','dataset-manifest.json','dataset.private.jsonl','gold.private.jsonl','targets.private.jsonl','syntax.private.json','frozen-policy.json'):
        files[str(out/name)]=sha256(out/name)
    for name,h in common['loader_manifest']['model_files'].items():files[str(snapshot/name)]=h
    for name,meta in common['tokenizer_files'].items():files[str(snapshot/name)]=meta['expected']
    for path,meta in common['dependency_source_files'].items():files[path]=meta['expected']
    for role in ('v2','v3'):
        for meta in audit['native_systems'][role]['adapter_files'].values():
            if isinstance(meta,dict):files[meta['path']]=meta['sha256']
    for p in (R15/'vendor/active').rglob('*.py'):files[str(p)]=sha256(p)
    files[str(TEMPLATE/'READY.json')]=sha256(TEMPLATE/'READY.json')
    write_json(out/'manifest.json',dict(version='fresh-eval-v2-v3-a-v1',created_utc=datetime.now(timezone.utc).isoformat(),
        created_Asia_Saigon=datetime.now(timezone(timedelta(hours=7),name='Asia/Saigon')).isoformat(),
        head=initial['head'],branch=branch,files=files,source_count=40,families=20,targets_per_system=160,
        primary_targets_per_system=120,maximum_targets=480,maximum_calls=800,systems=list(SYSTEMS),
        dataset_manifest_sha256=sha256(out/'dataset-manifest.json'),policy_sha256=sha256(out/'frozen-policy.json'),
        model_calls_before_freeze=0,systems_audit_sha256=sha256(out/'systems.json'),
        dependency_versions=common['versions'],context={'A':16384,'V2-old':32768,'V3-v3':32768}))
    write_json(out/'manifest.sha256.json',dict(sha256=sha256(out/'manifest.json')))
    print(json.dumps(dict(stage='frozen',verified=verify_frozen(out),token_ranges={n:[min(v.values()),max(v.values())] for n,v in token_counts.items()},maximum_calls=800)),flush=True)


def profile_native(model,bnb):
    identity=adapter_identity(model)
    q=[x for x in model.modules() if isinstance(x,bnb.nn.Linear4bit)]
    return dict(active_adapters=list(model.active_adapters),adapter_names=list(model.peft_config),
        all_modules_eval=not any(x.training for x in model.modules()),parameter_dtypes=dict(Counter(str(p.dtype) for p in model.parameters())),
        lora_dtypes=dict(Counter(str(p.dtype) for n,p in model.named_parameters() if 'lora_'in n)),attention=model.config._attn_implementation,
        model_config_use_cache=model.config.use_cache,generation_use_cache=True,gradient_checkpointing=model.is_gradient_checkpointing,
        gradient_checkpointing_active=False,generation_config=model.generation_config.to_dict(),adapter_identity=identity,
        quantization=dict(linear4bit_modules=len(q),compute_dtypes=dict(Counter(str(x.compute_dtype) for x in q)),
            storage_dtypes=dict(Counter(str(x.weight.dtype) for x in q)),quant_types=dict(Counter(x.weight.quant_type for x in q)),nested=all(x.weight.quant_state.nested for x in q)),
        compute_type_flags=dict(Counter(str(x.compute_type_is_set) for x in q)),
        observation_scope='Before and after inference only; no activation-dtype hook or teacher-forced pass. Constructor-set BF16 flags checked on all196 modules.')


def validate_prompts(tokenizer,examples,counts,hashes):
    for e in examples:
        ids=tokenizer.apply_chat_template(e['prompt'],tokenize=True,add_generation_prompt=True)
        if len(ids)!=counts[e['example_id']] or digest(ids)!=hashes[e['example_id']]:raise ValueError('actual tokenizer changes frozen input IDs')


def validate_native_rows(rows,examples,journal,name):
    expected={e['example_id']:e for e in examples};seen=set()
    for row in rows:
        eid=row['example_id'];state,result=call_state(journal,f'{name}/{eid}/1')
        if eid in seen or eid not in expected or (row['sample_id'],row['level'])!=(expected[eid]['sample_id'],expected[eid]['level']):
            raise ValueError('durable native ID/source/Level corruption')
        if state=='completed':
            if {k:v for k,v in row.items() if k!='utc'}!=result:raise ValueError('durable native result corruption')
        elif not (state=='uncertain' and row.get('call_count_uncertain')is True and row['status']=='missing'
                  and row['finish_reason']=='interrupted_unknown' and row['parsed']is None and row['raw']==''):
            raise ValueError('durable native result lacks completion or explicit unknown reservation')
        seen.add(eid)
    return seen


def run_A(out,systems,journal,prompts,counts,hashes):
    import torch
    from src.task3 import r15_abc_experiment as abc
    from src.task3.sft_v2_runtime import historical_payload
    from src.task3.sft_v1_experiment import Journal
    directory=out/'generations/A';directory.mkdir(parents=True,exist_ok=True)
    if (directory/'complete.json').exists():return
    config=systems['A']['config'];inference=abc.historical_module(R15,'task3.inference')
    runtime=abc.historical_module(R15,'task3.round15');runner=abc.historical_module(R15,'task3.round15_runner')
    targets=read_jsonl(out/'targets.private.jsonl');records=A_records(out,targets)
    journal.append(dict(type='base_model_load_started',profile='A'));start=time.perf_counter()
    backend=inference.HFBackend(config)
    journal.append(dict(type='base_model_load_completed',profile='A',wall_s=time.perf_counter()-start,precision=backend.precision_audit))
    backend.model.generation_config.max_time=45.0
    model=backend.model;q=[x for x in model.modules() if type(x).__name__=='Linear4bit'];gen=model.generation_config
    expected=systems['A']['historical_runtime']
    if (any('lora_'in n for n,p in model.named_parameters()) or any(x.training for x in model.modules())
        or backend.precision_audit['parameter_storage_elements_by_dtype']!=expected['parameter_storage_elements_by_dtype']
        or gen.repetition_penalty!=1.1 or gen.eos_token_id!=[151645,151643] or gen.pad_token_id!=151643
        or model.config.use_cache is not True or gen.num_beams!=1 or len(q)!=196
        or any(str(x.compute_dtype)!='torch.bfloat16' or x.weight.quant_type!='nf4' or not x.weight.quant_state.nested for x in q)):
        raise ValueError('authentic A load/precision/eval contract differs')
    validate_prompts(backend.tokenizer,prompts,counts,hashes)
    write_json(directory/'runtime-before.json',dict(precision=backend.precision_audit,generation_config=gen.to_dict(),
        load_runtime=backend.runtime_metadata(),
        adapter=None,all_modules_eval=True,parameter_count_dtypes=dict(Counter(str(p.dtype) for p in model.parameters())),
        compute_type_flags=dict(Counter(str(x.compute_type_is_set) for x in q)),
        effective_generation=dict(do_sample=False,num_beams=1,use_cache=True,repetition_penalty=1.1,eos=[151645,151643],max_time=45),
        observation_scope='actual loaded pre-call state; separate unprepared A base, no warmup'))
    by_id={r.sample_id:r for r in records};frozen={e['example_id']:e['prompt'] for e in prompts};original=abc.ReservedBackend
    class SharedReservation(original):
        def generate(self,messages,active):
            reservations=abc.jsonl(self.path);attempt=len(reservations)+1
            if attempt>3:raise ValueError('A physical cap')
            if messages[:2]!=frozen[self.sample_id] or len(messages)not in (2,3):raise ValueError('A query/gold input binding differs')
            tokens=self.tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True)
            if len(tokens)+active['max_new_tokens']>16384:raise ValueError('A actual retry budget')
            key='A/'+self.sample_id+'/'+str(attempt);journal.reserve(key)
            abc.append_event(self.path,dict(identity=self.identity,sample_id=self.sample_id,attempt=attempt,
                prompt_sha256=runner.digest(messages),input_tokens=len(tokens),reserved_unix=time.time()))
            journal.append(dict(type='input_binding',key=key,prompt_sha256=digest(messages),token_id_sha256=digest(tokens),input_tokens=len(tokens),manifest_sha256=sha256(out/'manifest.json')))
            generation_tick=time.perf_counter()
            try:result=self.backend.generate(messages,active)
            except RuntimeError as exc:
                if isinstance(exc,torch.cuda.OutOfMemoryError):raise ValueError('resource integrity: A CUDA OOM') from exc
                journal.append(dict(type='generation_completed',key=key,result=dict(raw=None,status='generation_error',finish_reason='runtime_error',
                    error=str(exc),input_tokens=len(tokens),output_tokens=0,output_tokens_unknown=True,wall_s=time.perf_counter()-generation_tick)))
                raise
            journal.append(dict(type='generation_completed',key=key,result=dict(raw=result.text,output_tokens=result.output_tokens,
                wall_s=result.latency_s,finish_reason=result.finish_reason,input_tokens=len(tokens))))
            return result
    abc.ReservedBackend=SharedReservation;tick=time.perf_counter();torch.cuda.reset_peak_memory_stats()
    try:result=abc.run_arm(records,'A',config,directory/'historical',examples=[],adapter=None,backend=backend)
    finally:abc.ReservedBackend=original
    predictions={r['sample_id']:r for r in result['predictions']};traces={r['sample_id']:r for r in result['traces']};final=[];first=[]
    for e in prompts:
        eid=e['example_id'];p=predictions.get(eid);trace=traces.get(eid,{})
        request=directory/'historical/requests'/abc.execution_identity(eid)[:24];attempts=abc.jsonl(request/'attempts.jsonl')
        decisions=abc.jsonl(request/'decisions.jsonl');base=dict(example_id=eid,sample_id=e['sample_id'],level=e['level'],payload_acceptance='historical_A')
        parsed=historical_payload(p)
        final.append(dict(base,status='valid' if p else 'missing',parsed=parsed,raw=json.dumps(parsed,ensure_ascii=False) if p else '',
            finish_reason='controller_export' if p else 'missing',raw_kind='controller_export',
            actual_attempt_finish_reasons=[a.get('finish_reason') for a in attempts],raw_attempts=[a.get('raw_text') for a in attempts],
            historical_final_origin=trace.get('final_origin'),fallback_used=trace.get('fallback_used',False),
            input_tokens=sum(a.get('input_tokens',0) for a in attempts),output_tokens=sum(a.get('output_tokens',0) for a in attempts),
            wall_s=sum(a.get('latency_s',0) for a in attempts),physical_calls=len(attempts)))
        a=attempts[0] if attempts else {};value=None;error=None
        try:
            if a.get('raw_text') is not None:value=runtime.parse_response(a['raw_text'])
        except (ValueError,TypeError,KeyError)as exc:error=str(exc)
        first.append(dict(base,status='valid' if value is not None else 'generation_error' if a.get('runtime_error') else 'malformed_json' if a else 'missing',
            raw=a.get('raw_text') or '',parsed=value,finish_reason=a.get('finish_reason','missing'),error=error,
            input_tokens=a.get('input_tokens',0),output_tokens=a.get('output_tokens',0),wall_s=a.get('latency_s',0),
            disclosure_guard=decisions[0] if decisions else None,semantic_review='not performed for first-attempt auxiliary view'))
    jsonl(directory/'final.jsonl',final);jsonl(directory/'first-attempts.jsonl',first)
    write_json(directory/'runtime-after.json',dict(runtime=backend.runtime_metadata(),all_modules_eval=not any(x.training for x in model.modules()),
        precision=inference.inspect_model_precision(model,load_in_4bit=True)))
    write_json(directory/'complete.json',dict(targets=len(final),physical_calls=sum(r['physical_calls'] for r in final),
        wall_s=time.perf_counter()-tick,input_tokens=sum(r['input_tokens'] for r in final),output_tokens=sum(r['output_tokens'] for r in final),
        generation_wall_s=sum(r['wall_s'] for r in final),peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),
        memory_scope='A generation phase only, load excluded; same invocation counters',first_valid=sum(r['status']=='valid' for r in first),
        final_valid=sum(r['status']=='valid' for r in final),fallbacks=sum(r['fallback_used'] for r in final)))
    del SharedReservation,backend,model,q;gc.collect();torch.cuda.empty_cache()


def run(out):
    verify_frozen(out);systems=load(out/'systems.json');offline(systems)
    import torch
    import bitsandbytes as bnb
    from peft import PeftModel
    from transformers import set_seed
    from src.task3.sft_v2_runtime import load_native
    from src.task3.sft_v2_public_context import generate
    from src.task3.sft_v1_experiment import Journal
    targets=read_jsonl(out/'targets.private.jsonl');ids=[t['sample_id'] for t in targets]
    journal=EvaluationJournal(out/'journal.jsonl',{'A':3,'V2-old':1,'V3-v3':1},ids)
    prompts={n:load(out/'prompts'/f'{n}.private.json') for n in SYSTEMS}
    counts=load(out/'prompts/token-counts.json');hashes=load(out/'prompts/token-id-hashes.json')
    run_A(out,systems,journal,prompts['A'],counts['A'],hashes['A'])
    pending=[n for n in ('V2-old','V3-v3') if not (out/'generations'/n/'complete.json').exists()]
    if pending:
        torch.cuda.reset_peak_memory_stats()
        base,tokenizer=load_native(systems['common_native_runtime']['loader_manifest'],journal)
        write_json(out/'native-load-runtime.json',dict(peak_allocated_bytes=torch.cuda.max_memory_allocated(),
            peak_reserved_bytes=torch.cuda.max_memory_reserved(),scope='Native loader/preparation only, reset before load; before adapter attach/inference.'))
        for name in pending:
            role='v2' if name=='V2-old' else 'v3';native=systems['native_systems'][role]
            set_seed(42);model=PeftModel.from_pretrained(base,native['checkpoint'],is_trainable=False);model.eval()
            profile=profile_native(model,bnb);validate_runtime_profile(profile)
            if profile['adapter_identity']!=native['tensor_identity']:raise ValueError('selected adapter actual tensor bytes differ')
            if any(not str(p.device).startswith('cuda:') for p in model.parameters()):raise ValueError('CPU offload')
            examples=prompts[name];validate_prompts(tokenizer,examples,counts[name],hashes[name])
            directory=out/'generations'/name;directory.mkdir(parents=True,exist_ok=True)
            if (directory/'runtime-before.json').exists() and load(directory/'runtime-before.json')!=profile:raise ValueError('resume runtime changed')
            write_json(directory/'runtime-before.json',profile)
            rows=read_jsonl(directory/'final.jsonl') if (directory/'final.jsonl').exists() else []
            seen=validate_native_rows(rows,examples,journal,name)
            tick=time.perf_counter();torch.cuda.reset_peak_memory_stats()
            for e in examples:
                if e['example_id']in seen:continue
                key=f"{name}/{e['example_id']}/1";action,result=call_state(journal,key)
                binding=dict(type='input_binding',key=key,prompt_sha256=digest(e['prompt']),token_id_sha256=hashes[name][e['example_id']],
                    input_tokens=counts[name][e['example_id']],manifest_sha256=sha256(out/'manifest.json'))
                prior=[{k:v for k,v in ev.items() if k!='utc'} for ev in journal.events() if ev.get('type')=='input_binding' and ev.get('key')==key]
                if prior and prior!=[binding]:raise ValueError('native input binding changed')
                if action!='completed':
                    if not prior:journal.append(binding)
                    result=generate(model,tokenizer,e,systems['common_native_runtime']['generation'],journal,key,32768)
                if not result.get('call_count_uncertain') and result['input_tokens']!=counts[name][e['example_id']]:raise ValueError('actual token count changed')
                Journal(directory/'final.jsonl').append(result);rows.append(result);seen.add(e['example_id'])
                print(json.dumps(dict(stage='native',system=name,completed=len(rows),id=e['example_id'],status=result['status'],action=action)),flush=True)
            after=profile_native(model,bnb);validate_runtime_profile(after)
            if after['adapter_identity']!=native['tensor_identity']:raise ValueError('adapter changed during inference')
            write_json(directory/'runtime-after.json',after)
            write_json(directory/'complete.json',dict(targets=len(rows),physical_calls=sum(not r.get('call_count_uncertain') for r in rows),
                wall_s=time.perf_counter()-tick,generation_wall_s=sum(r['wall_s'] for r in rows),
                input_tokens=sum(r['input_tokens'] for r in rows),output_tokens=sum(r['output_tokens'] for r in rows),
                valid=sum(r['status']=='valid' for r in rows),unknown=sum(bool(r.get('call_count_uncertain')) for r in rows),
                peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                memory_scope='current system inference phase, load excluded; allocator cache may persist',resume_scope='wall and peak current invocation; durable calls may span exact resume'))
            base=model.unload();del model;gc.collect();torch.cuda.empty_cache()
        del base,tokenizer;gc.collect();torch.cuda.empty_cache()
    journal.append(dict(type='fresh_generation_complete',targets=480,reservations=len(journal.reserved())))
    print(json.dumps(dict(stage='all_generation_complete',targets=480,reservations=len(journal.reserved()))),flush=True)


def final_rows(out):
    from src.task3.prompt_crossover import validate_population
    rows={}
    for name in SYSTEMS:
        if not (out/'generations'/name/'complete.json').exists():raise ValueError('incomplete system: '+name)
        rows[name]=read_jsonl(out/'generations'/name/'final.jsonl')
        validate_population(rows[name],load(out/'prompts'/f'{name}.private.json'))
    return rows


def code(out):
    verify_frozen(out);rows=final_rows(out)
    from scripts.task3_sft_v1_l4_audit import extract_cpp,output_matches
    from scripts.task3_sft_v1_l4_unfenced_audit import extract_unfenced
    sandbox=CppSandbox(TEMPLATE);cases={c['sample_id']:c for c in load(out/'evidence/cases.private.json')};results=[]
    for name,values in rows.items():
        for row in values:
            case=cases[row['sample_id']];path=out/'code-evidence'/name/(row['example_id']+'.json')
            path.parent.mkdir(parents=True,exist_ok=True)
            binding=dict(system_id=name,example_id=row['example_id'],generation_sha256=digest(row),case_sha256=digest(case),generation_status=row['status'])
            if path.exists():
                result=load(path)
                if any(result.get(k)!=v for k,v in binding.items()):raise ValueError('code evidence binding changed')
                results.append(result);continue
            result=dict(binding,status='started_no_retry',code_verdict='uncertain',compile_calls=0,runtime_calls=0)
            write_json(path,result)
            if row['status']!='valid':result.update(status='not_evaluable',reason='invalid schema/termination; no salvage')
            else:
                feedback=row['parsed']['feedback'];extracted=extract_cpp(feedback)
                if extracted['status']!='extracted' and '```'not in feedback:extracted=extract_unfenced(feedback)
                result['extraction']=extracted
                if extracted['status']!='extracted':
                    result.update(status='absent',code_verdict='absent',reason='no complete extractable program; reviewer must inspect visible snippets')
                elif not re.search(r'\bmain\s*\(',extracted['code']):
                    result.update(status='partial_snippet',code_verdict='uncertain',reason='localized code requires source-grounded review; do not compile it as a full program')
                else:
                    jail,compiled=sandbox.compile(extracted['code'],out/'code-evidence/jails')
                    result.update(compile_calls=1,compile=compiled,tests=[],authored_tests=len(case['tests']))
                    try:
                        if compiled['returncode']!=0 or compiled['timeout']:result.update(status='compile_failed',code_verdict='fail')
                        else:
                            for i,test in enumerate(case['tests']):
                                actual=sandbox.run(jail,stdin=test['input'],files=test.get('files'))
                                passed=actual['returncode']==0 and not actual['timeout'] and output_matches(actual['stdout'],test['expected'],case['checker'])
                                result['tests'].append(dict(index=i,input=test['input'],expected=test['expected'],actual=actual,passed=passed));result['runtime_calls']+=1
                                write_json(path,result)
                                if not passed:break
                            passed=len(result['tests'])==len(case['tests']) and all(t['passed'] for t in result['tests'])
                            result.update(status='all_authored_tests_passed' if passed else 'execution_failed',code_verdict='pass' if passed else 'fail',
                                not_executed=len(case['tests'])-len(result['tests']),
                                limitation='Finite authored tests, not universal correctness; stop after first proven failure.')
                    finally:shutil.rmtree(jail)
            write_json(path,result);results.append(result)
            if len(results)%20==0:print(json.dumps(dict(stage='code_evidence',completed=len(results))),flush=True)
    if sum(r['compile_calls'] for r in results)>480 or sum(r['runtime_calls'] for r in results)>96000:raise ValueError('code budget integrity')
    jsonl(out/'code-evidence.private.jsonl',results)
    print(json.dumps(dict(stage='code_complete',targets=len(results),compile_calls=sum(r['compile_calls'] for r in results),runtime_calls=sum(r['runtime_calls'] for r in results))),flush=True)


def blind(out):
    verify_frozen(out);rows=final_rows(out)
    directory=out/'blind';directory.mkdir(exist_ok=False)
    sources=read_jsonl(out/'dataset.private.jsonl');gold={g['sample_id']:g for g in read_jsonl(out/'gold.private.jsonl')}
    mechanical={(r['system_id'],r['example_id']):r for r in read_jsonl(out/'code-evidence.private.jsonl')}
    salt=secrets.token_hex(32);mapping={};groups={s['sample_id']:dict(source=s,gold=gold[s['sample_id']],
        source_evidence=load(out/gold[s['sample_id']]['witness_evidence_path']),outputs=[]) for s in sources}
    for name,values in rows.items():
        for row in values:
            bid=digest([salt,name,row['example_id']])[:24]
            mapping[bid]=dict(system_id=name,example_id=row['example_id'],sample_id=row['sample_id'],level=row['level'],generation_sha256=digest(row))
            ev=mechanical[(name,row['example_id'])]
            visible={k:v for k,v in ev.items() if k not in ('system_id','generation_sha256')}
            # Actual termination/raw attempts remain in generation artifacts,
            # but model/pipeline metadata must not identify an arm to reviewers.
            groups[row['sample_id']]['outputs'].append(dict(blind_id=bid,example_id=row['example_id'],level=row['level'],
                status=row['status'],raw=row['raw'],parsed=row['parsed'],code_evidence=visible))
    write_json(out/'blind-identity-map.private.json',dict(salt_sha256=text_sha(salt),mapping=mapping))
    for group in groups.values():group['outputs'].sort(key=lambda r:r['blind_id'])
    ordered=sorted(groups.values(),key=lambda g:(g['source']['family_id'],g['source']['sample_id']))
    for i in range(3):write_json(directory/f'packet-{i+1}.private.json',ordered[i::3])
    write_json(directory/'instructions.json',dict(axes=list(AXES),verdicts=['pass','fail','uncertain','not_applicable','not_evaluable'],
        policy=load(out/'frozen-policy.json'),response_format=dict(blind_id='exact ID',axes='all9',code_verdict='pass/fail/absent/uncertain',
            taxonomy_feedback_contradiction='true/false/uncertain',evidence='specific source/spec/response reason for failures/disputes',
            code_resolution_evidence='required if resolving mechanical code verdict'),
        invalid='all semantic axes not_evaluable; code uncertain; contradiction uncertain',
        rule='Do not read identity map, systems, prompts, runtime, or generation directories until every verdict is fixed. No exact-gold/keyword/length judging. Agent review, not independent human gold.'))
    write_json(directory/'packet-seal.json',{p.name:sha256(p) for p in directory.glob('*.private.json')})
    print(json.dumps(dict(stage='blinded',targets=len(mapping),packets=3)),flush=True)


def combine(out):
    verify_frozen(out);rows=final_rows(out);directory=out/'blind'
    for name,h in load(directory/'packet-seal.json').items():
        if sha256(directory/name)!=h:raise ValueError('review packet changed')
    # Seal all verdicts BEFORE opening the identity mapping.
    verdict_paths=[directory/f'verdicts-{i}.private.json' for i in (1,2,3)]
    verdicts=[]
    for path in verdict_paths:
        value=load(path);verdicts+=value['reviews'] if isinstance(value,dict) else value
    expected={o['blind_id'] for i in (1,2,3) for g in load(directory/f'packet-{i}.private.json') for o in g['outputs']}
    if len(verdicts)!=480 or {v['blind_id'] for v in verdicts}!=expected or len({v['blind_id'] for v in verdicts})!=480:raise ValueError('blind review coverage')
    allowed={'pass','fail','uncertain','not_applicable','not_evaluable'}
    for v in verdicts:
        if set(v['axes'])!=set(AXES) or not set(v['axes'].values())<=allowed or not v.get('evidence') or v.get('code_verdict')not in ('pass','fail','absent','uncertain') or v.get('taxonomy_feedback_contradiction')not in (True,False,'uncertain'):
            raise ValueError('review schema/axes/explicit uncertainty')
    seal={str(p.relative_to(out)):sha256(p) for p in verdict_paths};sealpath=directory/'verdict-seal.json'
    if sealpath.exists() and load(sealpath)!=seal:raise ValueError('fixed blind verdicts changed')
    write_json(sealpath,seal)
    mapping=load(out/'blind-identity-map.private.json')['mapping']
    original={(name,r['example_id']):r for name,values in rows.items() for r in values}
    gold={g['sample_id']:g for g in read_jsonl(out/'gold.private.jsonl')}
    code_rows=read_jsonl(out/'code-evidence.private.jsonl');mechanical={(r['system_id'],r['example_id']):r for r in code_rows};reviewed=[]
    for v in verdicts:
        binding=mapping[v['blind_id']];name=binding['system_id'];row=original[(name,binding['example_id'])]
        if digest(row)!=binding['generation_sha256']:raise ValueError('generation changed since blinding')
        if row['status']!='valid' and (set(v['axes'].values())!={'not_evaluable'} or v['code_verdict']!='uncertain'):raise ValueError('invalid response semantic salvage')
        ev=mechanical[(name,row['example_id'])];old_verdict=ev['code_verdict']
        if old_verdict!=v['code_verdict']:
            if old_verdict=='fail' or not v.get('code_resolution_evidence'):raise ValueError('unsupported code verdict resolution')
            ev.update(mechanical_code_verdict=old_verdict,code_verdict=v['code_verdict'],code_resolution_evidence=v['code_resolution_evidence'])
        g=gold[row['sample_id']]
        reviewed.append(dict(row,system_id=name,family_id=g['family_id'],faulty=g['faulty'],gold_taxonomy=g['taxonomy'],
            axes=v['axes'],code_verdict=v['code_verdict'],taxonomy_feedback_contradiction=v['taxonomy_feedback_contradiction'],
            evidence=v['evidence'],review_id=v['blind_id'],review_type='source-grounded Codex agent review; not independent human evaluation',
            **({k:v[k] for k in ('code_resolution_evidence',) if k in v})))
    jsonl(out/'reviews.private.jsonl',sorted(reviewed,key=lambda r:(SYSTEMS.index(r['system_id']),r['example_id'])))
    jsonl(out/'code-evidence.private.jsonl',code_rows)
    costs(out)
    print(json.dumps(dict(stage='reviews_fixed_and_revealed',targets=len(reviewed))),flush=True)


def costs(out):
    rows=final_rows(out);events=read_jsonl(out/'journal.jsonl');source_validation=load(out/'evidence/source-validation.private.json')
    syntax=load(out/'syntax.private.json');code_rows=read_jsonl(out/'code-evidence.private.jsonl')
    source_details=[load(out/r['evidence_path']) for r in source_validation]
    by_system={}
    for name,values in rows.items():
        c=load(out/'generations'/name/'complete.json')
        completed=[e['result'] for e in events if e.get('type')=='generation_completed' and e['key'].startswith(name+'/')]
        reserved=sum(e.get('type')=='generation_reserved' and e['key'].startswith(name+'/') for e in events)
        by_system[name]=dict(c,fresh_targets=len(values),reused_targets=0,
            physical_calls=len(completed),reserved_calls=reserved,unknown_reserved_calls=reserved-len(completed),
            historical_controller_captured_calls=c['physical_calls'] if name=='A' else None,
            completed_calls_without_controller_capture=max(0,len(completed)-c['physical_calls']) if name=='A' else 0,
            input_tokens=sum(r.get('input_tokens',0) for r in completed),output_tokens=sum(r.get('output_tokens',0) for r in completed),
            generation_wall_s=sum(r.get('wall_s',0) for r in completed),
            failed_model_calls=sum(r.get('status')=='generation_error' for r in completed),
            finish_reasons=dict(Counter(r.get('finish_reason','unknown') for r in completed)),
            invalid=sum(r['status']!='valid' for r in values),
            recovery_calls=max(0,reserved-len(values)),
            load_wall_s=sum(e['wall_s'] for e in events if e.get('type')=='base_model_load_completed' and e.get('profile')==('A' if name=='A' else 'native')) if name!='V3-v3' else 0,
            load_scope='A separate base; native base loaded once and reused between V2/V3 with unload/attach, charged to V2-old; no simultaneous adapter composition')
    source_runtime=[t['actual'] for d in source_details for t in d['tests']]
    generated_runtime=[t['actual'] for d in code_rows for t in d.get('tests',[])]
    write_json(out/'costs-and-runtime.json',dict(systems=by_system,fresh_targets=sum(len(v) for v in rows.values()),reused_targets=0,
        actual_model_calls=sum(e.get('type')=='generation_completed' for e in events),reserved_model_calls=sum(e.get('type')=='generation_reserved' for e in events),
        unknown_reserved_calls=sum(e.get('type')=='generation_reserved' for e in events)-sum(e.get('type')=='generation_completed' for e in events),
        actual_model_call_count_scope='Completed calls from global pre-controller ledger; reserved but uncompleted calls have unknown execution, retained separately. Completed calls lost before controller capture remain charged.',
        maximum_model_calls=800,training_steps=0,warmup_model_calls=0,teacher_forced_calls=0,
        input_tokens=sum(c['input_tokens'] for c in by_system.values()),output_tokens=sum(c['output_tokens'] for c in by_system.values()),
        inference_wall_s=sum(c['generation_wall_s'] for c in by_system.values()),
        model_load_wall_s=sum(e['wall_s'] for e in events if e.get('type')=='base_model_load_completed'),
        authored_cpp=dict(syntax_calls=len(syntax),syntax_wall_s=sum(e['latency_s'] for e in syntax.values()),
            compile_calls=len(source_details),compile_wall_s=sum(d['compile']['latency_s'] for d in source_details),
            runtime_calls=len(source_runtime),runtime_wall_s=sum(t['latency_s'] for t in source_runtime)),
        generated_code=dict(compile_calls=sum(r['compile_calls'] for r in code_rows),
            compile_wall_s=sum(r.get('compile',{}).get('latency_s',0) for r in code_rows),runtime_calls=len(generated_runtime),runtime_wall_s=sum(t['latency_s'] for t in generated_runtime)),
        vram_scope='Per-system reset peak during actual inference; load peaks separately in runtime logs; no first-activation dtype measurements.',
        accounting='Measured returned tokens and wall times from global generation events, not a monetary bill. Tokens lost in runtime errors/unknown calls are not estimated as known zero. Review-agent token use not instrumented in model-call budget.'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','freeze','run','code','blind','combine','verify']);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve()
    if args.command=='prepare':prepare(out)
    elif args.command=='verify':print(json.dumps(verify_frozen(out)))
    else:globals()[args.command](out)


if __name__=='__main__':main()
