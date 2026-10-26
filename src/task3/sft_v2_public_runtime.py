"""One frozen public pass using the existing native V2 generation implementation."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from src.task3.sft_v1 import sha256, native_prompt
from src.task3.sft_v1_experiment import write_json
from src.task3.sft_v1_runtime import digest, verify_frozen, generate
from src.task3.sft_v2_runtime import validated_selection

PUBLIC = Path('/workspace/llm-final-project/data/raw/public_test_release')
V2 = 'outputs/task3/sft-v2-qlora-20261026-run1'
METHOD = 'task3-sft-v2-step240-native-public-primary-v1'
CONTEXT = 8192  # Actual guard in frozen sft_v1_runtime.generate, not inferred from train config.
TEMPLATE = Path('/workspace/llm-final-project/outputs/task3/round23-20261022/sandbox-template')
FLAGS = ['/usr/bin/g++','-std=c++11','-fsyntax-only','-fmax-errors=3','/work/source.cpp']


def load(path):
    return json.loads(Path(path).read_text())


def jsonl(path, rows):
    path=Path(path); tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w') as f:
        for row in rows: f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
        f.flush(); os.fsync(f.fileno())
    tmp.replace(path)


def verify_hashes(root, hashes):
    root=Path(root).resolve()
    for name, expected in hashes.items():
        p=(root/name).resolve()
        if not p.is_relative_to(root): raise ValueError('frozen path escape: '+name)
        if not p.is_file() or sha256(p)!=expected: raise ValueError('frozen bytes changed: '+name)


def preserve(repo, out):
    initial=load(out/'initial-workspace-state.json')
    verify_hashes(repo,initial['files'])
    if sha256(repo/'predictions.json')!=initial['root_predictions_sha256']: raise ValueError('root predictions changed')
    for command,key in [(['git','rev-parse','HEAD'],'head'),(['git','branch','--show-current'],'branch')]:
        if subprocess.check_output(command,cwd=repo,text=True).strip()!=initial[key]: raise ValueError('workspace identity changed')
    historical={}
    for name in [V2,'outputs/task3/sft-v1-qlora-20261026-run1']:
        root=repo/name; index=root/'artifact-sha256.json'
        if not index.is_file(): raise ValueError('historical artifact index missing: '+name)
        if name==V2 and sha256(index)!=initial['v2_artifact_index_sha256']:
            raise ValueError('historical V2 artifact index changed')
        baseline=out/'historical-verification-before.json'
        if baseline.exists() and sha256(index)!=load(baseline)['historical'][name]['index_sha256']:
            raise ValueError('historical artifact index changed: '+name)
        hashes=load(index); verify_hashes(root,hashes)
        historical[name]=dict(files=len(hashes),index_sha256=sha256(index),verified=True)
    return dict(preexisting_files_verified=len(initial['files']),root_predictions_preserved=True,historical=historical)


def syntax_check(sandbox, out, record):
    original=sha256(Path(record.code_path)); decoded=hashlib.sha256(record.code.encode()).hexdigest()
    identity=dict(original_source_sha256=original,decoded_source_sha256=decoded,flags=FLAGS,
                  template_ready_sha256=sha256(TEMPLATE/'READY.json'),compiler_sha256=sha256(TEMPLATE/'usr/bin/g++'),
                  policy_sha256=sha256(Path(__file__).parent/'cpp_sandbox.py'))
    directory=out/'compiler'; directory.mkdir(exist_ok=True)
    path=directory/(digest(identity)+'.json')
    if path.exists():
        result=load(path)
        if result['identity']!=identity: raise ValueError('compiler cache provenance mismatch')
        return result
    jail=sandbox.create(out/'compiler-jails')
    try:
        source=jail/'work/source.cpp'; source.write_text(record.code); source.chmod(0o444)
        if sha256(source)!=decoded: raise ValueError('compiler source changed')
        result=sandbox._call(jail,FLAGS,'',compile_phase=True)
        result.update(status='timeout' if result['timeout'] else 'pass' if result['returncode']==0 else 'error',
                      identity=identity,syntax_only=True,linked=False,public_program_executed=False,
                      capture_limit_bytes_per_stream=65536,
                      capture_limit_reached=any(len(result[k].encode())>=65536 for k in ['stdout','stderr']))
        write_json(path,result)
        return result
    finally:
        # Only this newly created jail is removed; trusted template is untouched.
        for p in jail.rglob('*'):
            if p.is_dir(): p.chmod(0o700)
        jail.chmod(0o700); shutil.rmtree(jail)


def prepare(repo,out):
    from transformers import AutoTokenizer
    from src.task3.public_contract import verify_public_contract
    from src.task3.dataset import load_task3
    from src.task3.cpp_sandbox import CppSandbox
    from src.task3.sft_v2_public import map_input, context_preflight, fixed_review_slice
    if (out/'public-freeze.json').exists(): raise FileExistsError('public freeze already exists; use verify/infer/export')
    old=repo/V2; manifest=load(old/'manifest.json')
    verify_frozen(repo,old,manifest); selection=validated_selection(repo,old,manifest)
    if selection['step']!=240: raise ValueError('only persisted step240 authorized')
    preservation=preserve(repo,out); write_json(out/'historical-verification-before.json',preservation)
    contract=verify_public_contract(PUBLIC)
    write_json(out/'official-contract.json',contract)
    requested=contract['requested_levels']; write_json(out/'requested-levels.private.json',requested)
    records=load_task3(PUBLIC,'public',out/'requested-levels.private.json')
    by_id={r.sample_id:r for r in records}
    if set(by_id)!=set(requested): raise ValueError('public input IDs mismatch')
    sandbox=CppSandbox(TEMPLATE); examples=[]; bindings=[]
    root=repo/manifest['config']['dataset_root']; labels=contract['taxonomy_labels']
    for n,sid in enumerate(requested):
        r=by_id[sid]; syntax=syntax_check(sandbox,out,r); x=map_input(r,syntax)
        prompt=native_prompt(root,x,labels)
        example=dict(sample_id=sid,example_id=sid,level=x['target_feedback_level'],exam_id=r.exam_id,prompt=prompt)
        examples.append(example)
        bindings.append(dict(sample_id=sid,requested_level=requested[sid],level=example['level'],exam_id=r.exam_id,
                             exam_type=r.exam_type,source_file=r.code_path,source_sha256=sha256(Path(r.code_path)),
                             decoded_source_sha256=hashlib.sha256(r.code.encode()).hexdigest(),
                             original_statement_sha256=hashlib.sha256(r.statement.encode()).hexdigest(),
                             supplied_log=r.compile_log,local_syntax=syntax,prompt_sha256=digest(prompt),
                             mapped_input=x,structured_subproblem_count=len(r.problems)))
        if (n+1)%25==0: print(json.dumps(dict(prepared=n+1,total=len(requested))),flush=True)
    tokenizer=AutoTokenizer.from_pretrained(manifest['config']['tokenizer_local'],local_files_only=True,trust_remote_code=False)
    if hashlib.sha256(tokenizer.chat_template.encode()).hexdigest()!=manifest['tokenizer']['chat_template_sha256']:
        raise ValueError('chat template changed')
    preflight=context_preflight(tokenizer,examples,manifest['generation'],CONTEXT)
    for row,binding in zip(preflight,bindings):
        if binding['local_syntax']['capture_limit_reached']:
            row['status']='compiler_capture_preflight_failure'
    jsonl(out/'public-inputs.private.jsonl',bindings); jsonl(out/'examples.private.jsonl',examples)
    write_json(out/'context-preflight.json',preflight)
    review=fixed_review_slice(examples)
    write_json(out/'review-selection.json',dict(seed='task3-v2-public-review-20261026',
        metadata_only=True,selection='12 per Level, hash order and round-robin exam family',
        ids=[r['sample_id'] for r in review],strata=[{k:r[k] for k in ['sample_id','level','exam_id']} for r in review],
        additional_risk_policy=dict(maximum=24,exclude_fixed_slice=True,
            rank=['empty_nonempty_taxonomy_transition','different_label_set','language_flag','feedback_length_over_800'],
            tie='sha256(seed + | + sample_id)',invalid_review='all separately')))
    code_names=['src/task3/sft_v2_public.py','src/task3/sft_v2_public_runtime.py','scripts/task3_sft_v2_public.py',
                'src/task3/sft_v1.py','src/task3/sft_v1_runtime.py','src/task3/sft_v1_evaluation.py',
                'src/task3/sft_v2_runtime.py','src/task3/cpp_sandbox.py','src/task3/submission.py',
                'src/task3/dataset.py','src/task3/input_fields.py','src/task3/public_contract.py']
    sourcefiles={str(Path(r.code_path).relative_to(PUBLIC)):sha256(Path(r.code_path)) for r in records}
    sourcefiles.update({n:sha256(PUBLIC/n) for n in ['exams.json','task3_feedback.json','label_space.json']})
    frozen_files={p.name:sha256(p) for p in [out/n for n in ['public-inputs.private.jsonl','examples.private.jsonl',
        'requested-levels.private.json','context-preflight.json','review-selection.json','official-contract.json']]}
    freeze=dict(created_utc=datetime.now(timezone.utc).isoformat(),method=METHOD,old_manifest_sha256=sha256(old/'manifest.json'),
        selected_checkpoint=selection['checkpoint'],selection_sha256=sha256(old/'selection.json'),step=240,
        adapter_files=load(Path(selection['checkpoint'])/'checkpoint-identity.json'),
        code={n:sha256(repo/n) for n in code_names},inputs=sourcefiles,files=frozen_files,
        model=manifest['config']['model_id'],revision=manifest['config']['revision'],
        tokenizer=manifest['tokenizer'],quantization='native V2 NF4 double quant BF16 compute; prepare_model_for_kbit_training',
        generation=manifest['generation'],context_limit=CONTEXT,
        context_evidence='frozen src/task3/sft_v1_runtime.py generate explicit prompt+allowance guard8192',
        ordered_requested_ids=list(requested),requested_level_counts=contract['level_counts'],
        preflight_counts=dict(Counter(r['status'] for r in preflight)),
        one_attempt=True,maximum_physical_calls=len(requested),concurrency=1,
        resume='saved completed results replayed from durable journal; reserved without completion remains interrupted_unknown and never retried',
        prompt_mapping='full statement plus attributed official whitelisted structured requirements; unchanged native renderer/system; full source and separately attributed supplied/local syntax logs',
        no_gold=True,compiler_flags=FLAGS,compiler_limits='existing chroot/seccomp/uid rlimits; CPU4/5s, wall10s, AS512MiB, NPROC4, FSize8MiB, capture65536B/stream; syntax-only')
    write_json(out/'public-freeze.json',freeze)
    write_json(out/'public-freeze.sha256.json',dict(sha256=sha256(out/'public-freeze.json')))
    print(json.dumps(dict(frozen=True,counts=freeze['preflight_counts'],review=len(review))),flush=True)


def verify(repo,out):
    f=load(out/'public-freeze.json')
    if sha256(out/'public-freeze.json')!=load(out/'public-freeze.sha256.json')['sha256']: raise ValueError('freeze seal changed')
    verify_hashes(repo,f['code']); verify_hashes(out,f['files']); verify_hashes(PUBLIC,f['inputs'])
    old=repo/V2; manifest=load(old/'manifest.json'); verify_frozen(repo,old,manifest)
    if sha256(old/'manifest.json')!=f['old_manifest_sha256']: raise ValueError('old manifest changed')
    selection=validated_selection(repo,old,manifest)
    if selection['step']!=240 or selection['checkpoint']!=f['selected_checkpoint']: raise ValueError('selection changed')
    verify_hashes(Path(selection['checkpoint']),f['adapter_files'])
    return f,manifest


def recover_results(examples,events,preflight_failures):
    completed={e['key']:e['result'] for e in events if e.get('type') in ('generation_completed','public_input_allocation_failed')}
    reserved={e['key'] for e in events if e.get('type')=='generation_reserved'}
    result={}
    for e in examples:
        sid=e['sample_id']; base={k:e[k] for k in ['sample_id','example_id','level']}
        if sid in completed: result[sid]=completed[sid]
        elif sid in reserved: result[sid]=dict(base,status='missing',finish_reason='interrupted_unknown',raw='',parsed=None,
            input_tokens=0,output_tokens=0,wall_s=0.,call_count_uncertain=True)
        elif sid in preflight_failures: result[sid]=dict(base,status='context_preflight_failure',
            finish_reason='not_called',raw='',parsed=None,input_tokens=0,output_tokens=0,wall_s=0.)
    return result


def normalized_results(examples,results,out):
    return [dict(results[e['sample_id']],method=METHOD,prompt_sha256=digest(e['prompt']),
        runtime_identity_sha256=sha256(out/'public-freeze.json')) for e in examples if e['sample_id'] in results]


def verified_results(out):
    """Reconstruct from the validated durable journal; reject stale sidecars."""
    from src.task3.sft_v1 import read_jsonl
    from src.task3.sft_v2_public import PublicJournal
    examples=read_jsonl(out/'examples.private.jsonl')
    failures={r['sample_id'] for r in load(out/'context-preflight.json') if r['status']!='evaluable'}
    allowed={e['sample_id']:digest(e['prompt']) for e in examples if e['sample_id'] not in failures}
    journal=PublicJournal(out/'generation-journal.jsonl',allowed)
    events=journal.events()
    allocation_failures=[e for e in events if e.get('type')=='public_input_allocation_failed']
    seen=set()
    for event in allocation_failures:
        key=event['key']
        if key not in allowed or key in seen or key in journal.reserved() or event['result']['sample_id']!=key:
            raise ValueError('invalid pre-generation failure binding')
        seen.add(key)
    recovered=recover_results(examples,events,failures)
    rows=normalized_results(examples,recovered,out)
    if read_jsonl(out/'generations.jsonl')!=rows: raise ValueError('normalized outputs differ from durable journal')
    return rows


def infer(repo,out):
    import fcntl
    from src.task3.sft_v1 import read_jsonl
    from src.task3.sft_v2_public import PublicJournal
    from src.task3.sft_v2_runtime import load_native
    from peft import PeftModel
    import torch
    with (out/'inference.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        freeze,manifest=verify(repo,out)
        examples=read_jsonl(out/'examples.private.jsonl'); preflight=load(out/'context-preflight.json')
        failures={r['sample_id'] for r in preflight if r['status']!='evaluable'}
        allowed={e['sample_id']:digest(e['prompt']) for e in examples if e['sample_id'] not in failures}
        journal=PublicJournal(out/'generation-journal.jsonl',allowed)
        results=recover_results(examples,journal.events(),failures)
        pending=[e for e in examples if e['sample_id'] not in results]
        def save():
            jsonl(out/'generations.jsonl',normalized_results(examples,results,out))
        save()
        if not pending: print('No unreserved cases remain; no model loaded.'); return
        load_start=time.perf_counter(); base,tokenizer=load_native(manifest,journal)
        model=PeftModel.from_pretrained(base,freeze['selected_checkpoint'],is_trainable=False)
        for p in model.parameters(): p.requires_grad_(False)
        model.eval(); torch.cuda.synchronize()
        journal.append(dict(type='public_model_and_adapter_load_completed',wall_s=time.perf_counter()-load_start,
            adapter=freeze['adapter_files'],method=METHOD,peak_allocated_bytes=torch.cuda.max_memory_allocated(),
            peak_reserved_bytes=torch.cuda.max_memory_reserved()))
        torch.cuda.reset_peak_memory_stats(); generation_start=time.perf_counter()
        journal.append(dict(type='public_generation_phase_started',pending=len(pending),peak_scope='whole phase after load; never reset per case'))
        for e in pending:
            sid=e['sample_id']
            call_start=time.perf_counter()
            try: result=generate(model,tokenizer,e,freeze['generation'],journal,sid)
            except torch.cuda.OutOfMemoryError as exc:
                reserved=sid in journal.reserved()
                result=dict(sample_id=sid,example_id=sid,level=e['level'],status='generation_error',
                    finish_reason='generation_error',raw='',parsed=None,input_tokens=next(r['prompt_tokens'] for r in preflight if r['sample_id']==sid),
                    output_tokens=None if reserved else 0,wall_s=time.perf_counter()-call_start,
                    error='CUDA OutOfMemoryError: '+str(exc),output_cost_unknown=reserved,physical_call_reserved=reserved)
                journal.append(dict(type='generation_completed' if reserved else 'public_input_allocation_failed',key=sid,result=result))
                torch.cuda.empty_cache()
            results[sid]=result; save()
            print(json.dumps(dict(processed=len(results),expected=len(examples),sample_id=sid,status=result['status'])),flush=True)
        torch.cuda.synchronize()
        journal.append(dict(type='public_generation_phase_completed',wall_s=time.perf_counter()-generation_start,
            peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),
            scope='whole public generation phase after load; all success/failure calls; no per-case resets'))
        write_json(out/'generation-complete.json',dict(expected=len(examples),normalized=len(results),
            physical_reservations=len(journal.reserved()),status_counts=dict(Counter(r['status'] for r in results.values())),
            journal_sha256=sha256(journal.path),freeze_sha256=sha256(out/'public-freeze.json')))


def export(repo,out):
    from src.task3.sft_v1 import read_jsonl
    from src.task3.sft_v2_public import export_submission
    verify(repo,out)
    result=export_submission(out/'submission',load(out/'requested-levels.private.json'),
        verified_results(out),load(out/'official-contract.json')['taxonomy_labels'])
    print(json.dumps(result,ensure_ascii=False),flush=True)
