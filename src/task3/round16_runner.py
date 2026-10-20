"""Durable raw-first generation with schema-only retry and evidence projection."""
import json
from pathlib import Path
from src.task3.dataset import write_json
from src.task3.inference import tokenizer_metadata
from src.task3.round14_runner import digest, repair_journal_tail
from src.task3.round15 import query_payload
from src.task3.round15_runner import _append, _read
from src.task3.round16 import VERSION, fitted_messages, parse_response


def run_records(records,backend,config,output_dir,*,examples=()):
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    binding=digest({'version':VERSION,'config':config,'examples':examples,'tokenizer':tokenizer_metadata(backend.tokenizer),
                    'inputs':[{'id':r.sample_id,'input':query_payload(r)} for r in records]})
    state_path=out/'progress.json';journal=out/'attempts.jsonl'
    maximum=config.get('max_attempts',3)
    if type(maximum) is not int or maximum not in (1,2,3):raise ValueError('max_attempts must be 1..3')
    if len({r.sample_id for r in records})!=len(records):raise ValueError('duplicate IDs')
    if state_path.exists():
        state=json.loads(state_path.read_text())
        if state['identity']!=binding:raise ValueError('resume identity mismatch')
    else:
        if any((out/name).exists() for name in ('attempts.jsonl','predictions.json')):raise ValueError('unbound output identity')
        state={'identity':binding,'completed':{},'errors':{}};write_json(state_path,state)
    repair_journal_tail(journal);journal.touch(mode=0o600,exist_ok=True);journal.chmod(0o600)
    all_rows=_read(journal);seen={};ids={r.sample_id for r in records}
    for row in all_rows:
        sid=row['sample_id'];number=row['attempt']
        if (sid not in ids or number!=seen.get(sid,0)+1 or number>maximum
                or row['attempt_id']!=digest([binding,sid,number]) or row['prompt_sha256']!=digest(row['prompt_messages'])):
            raise ValueError('attempt journal identity/order mismatch')
        seen[sid]=number
    if not set(state['completed'])<=ids:raise ValueError('checkpoint IDs mismatch')
    for record in records:
        sid=record.sample_id;level=int(record.target_feedback_level[6]);variant=config['prompt_variant']
        rows=[row for row in all_rows if row['sample_id']==sid]
        if sid in state['completed']:
            entry=state['completed'][sid]
            if entry['trace']['attempts']!=rows:raise ValueError('completed trace differs from journal')
            parsed=parse_response(rows[-1]['raw_text'],variant)
            if entry['output']!={k:parsed[k] for k in ('taxonomy_error','feedback')}:raise ValueError('completed output differs from journal')
            continue
        shots=[ex for ex in examples if ex['level']==level]
        if variant=='one_shot':shots=shots[:1]
        if variant=='evidence_cot':shots=[]
        accepted=None;last_error=None;index=0
        while index<maximum:
            newly_generated=index>=len(rows)
            if newly_generated:
                cap=config.get('level4_max_tokens',1536) if level==4 else config['max_new_tokens']
                call_config={**config,'max_new_tokens':cap}
                messages,budget=fitted_messages(record,shots,backend.tokenizer,call_config,retry=last_error)
                attempt={'sample_id':sid,'attempt':index+1,'attempt_id':digest([binding,sid,index+1]),
                         'capture_stage':'before_schema_projection','prompt_messages':messages,'prompt_sha256':digest(messages),
                         'retry_reason':last_error,**budget}
                try:
                    g=backend.generate(messages,call_config)
                    attempt.update(raw_text=g.text,output_tokens=g.output_tokens,latency_s=g.latency_s,
                                   finish_reason=g.finish_reason,eos_reached=g.eos_reached,runtime_error=None)
                except RuntimeError as exc:
                    attempt.update(raw_text=None,runtime_error=str(exc),output_tokens=None)
                _append(journal,attempt);all_rows.append(attempt);rows.append(attempt)
            attempt=rows[index];index+=1
            if attempt.get('runtime_error'):
                last_error=attempt['runtime_error']
                if newly_generated:break
                continue
            try:accepted=parse_response(attempt['raw_text'],variant)
            except (ValueError,TypeError,KeyError) as exc:last_error=str(exc);continue
            break
        trace={'sample_id':sid,'attempts':rows,'first_raw_text':rows[0]['raw_text'] if rows else None,
               'accepted_raw':accepted,'fallback_used':False,'final_origin':'qwen_initial' if index==1 else 'qwen_schema_retry'}
        if accepted is None:state['errors'][sid]={'reason':last_error,'trace':trace}
        else:
            state['completed'][sid]={'output':{k:accepted[k] for k in ('taxonomy_error','feedback')},'trace':trace}
            state['errors'].pop(sid,None)
        write_json(state_path,state)
        print(f'{variant}: {len(state["completed"])}/{len(records)}',flush=True)
    predictions=[{'sample_id':r.sample_id,'output':state['completed'][r.sample_id]['output']} for r in records if r.sample_id in state['completed']]
    traces=[state['completed'][r.sample_id]['trace'] for r in records if r.sample_id in state['completed']]
    write_json(out/'completed.predictions.json',predictions);write_json(out/'traces.json',traces)
    if len(predictions)==len(records):write_json(out/'predictions.json',predictions)
    return {'predictions':predictions,'traces':traces,'errors':state['errors'],'identity':binding}
