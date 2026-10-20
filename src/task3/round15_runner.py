"""Direct prompt experiment: raw-before-guard capture and bounded per-ID resume."""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from src.task3.dataset import write_json
from src.task3.inference import tokenizer_metadata
from src.task3.round14_runner import digest,repair_journal_tail
from src.task3.round15 import VERSION,query_payload,fitted_messages,parse_response
from src.task3.round15_disclosure import disclosure_violations,audit_flags


def identity(records,backend,config,examples):
    return digest({'version':VERSION,'config':config,'examples':examples,'tokenizer':tokenizer_metadata(backend.tokenizer),
                   'inputs':[{'sample_id':r.sample_id,'payload':query_payload(r)} for r in records]})


def _append(path,value):
    with path.open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(value,ensure_ascii=False)+'\n');stream.flush();os.fsync(stream.fileno())


def _read(path):
    return [json.loads(line) for line in path.read_text().split('\n') if line] if path.exists() else []


def run_records(records,backend,config,output_dir,*,examples=()):
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    binding=identity(records,backend,config,examples);state_path=out/'progress.json'
    maximum=config.get('max_attempts',3)
    if type(maximum) is not int or maximum not in (1,2,3):raise ValueError('max_attempts must be bounded1..3')
    if state_path.exists():
        state=json.loads(state_path.read_text())
        if state['identity']!=binding:raise ValueError('resume identity mismatch')
    else:
        if (out/'predictions.json').exists() or any((out/name).exists() and (out/name).stat().st_size for name in ('attempts.jsonl','decisions.jsonl')):
            raise ValueError('unbound final artifact or attempt journal')
        state={'identity':binding,'completed':{},'errors':{}};write_json(state_path,state)
    journal=out/'attempts.jsonl';decisions=out/'decisions.jsonl'
    for path in (journal,decisions):
        repair_journal_tail(path);path.touch(mode=0o600,exist_ok=True);path.chmod(0o600)
    all_rows=_read(journal);decision_rows=_read(decisions)
    ids={r.sample_id for r in records};seen={}
    if len(ids)!=len(records) or not set(state['completed'])<=ids or not set(state['errors'])<=ids or set(state['completed'])&set(state['errors']):
        raise ValueError('checkpoint IDs mismatch')
    for row in all_rows:
        sid=row.get('sample_id');number=row.get('attempt')
        expected=seen.get(sid,0)+1
        if sid not in ids or type(number) is not int or number!=expected or number>maximum or row.get('attempt_id')!=digest([binding,sid,number]) or row.get('prompt_sha256')!=digest(row.get('prompt_messages')):
            raise ValueError('attempt journal identity/order/prompt mismatch')
        seen[sid]=number
    outcomes={row['attempt_id']:row for row in decision_rows}
    if len(outcomes)!=len(decision_rows) or not set(outcomes)<={row['attempt_id'] for row in all_rows}:
        raise ValueError('decision journal does not match captured attempts')
    for sid,entry in state['completed'].items():
        try:parsed=parse_response(json.dumps(entry['output'],ensure_ascii=False))
        except (ValueError,TypeError,KeyError) as exc:raise ValueError('invalid completed schema') from exc
        level=int(next(r for r in records if r.sample_id==sid).target_feedback_level[6])
        if disclosure_violations(parsed['feedback'],level):raise ValueError('invalid completed disclosure')
        if entry.get('trace',{}).get('attempts')!=[row for row in all_rows if row['sample_id']==sid]:
            raise ValueError('completed trace differs from captured journal')
    for record in records:
        sid=record.sample_id
        if sid in state['completed']:continue
        level=int(record.target_feedback_level[6])
        shots=[ex for ex in examples if ex['level']==level] if config['prompt_variant']=='few_shot' else []
        rows=[row for row in all_rows if row['sample_id']==sid]
        accepted=None;latest_schema=None;last_error=None;infrastructure_failure=False
        index=0
        while index<maximum:
            newly_generated=index>=len(rows)
            if newly_generated:
                cap=config.get('level4_max_tokens',1536) if level==4 else config.get('max_new_tokens',1024)
                call_config={**config,'max_new_tokens':cap}
                try:messages,budget=fitted_messages(record,shots,backend.tokenizer,call_config,retry=last_error)
                except ValueError as exc:last_error=str(exc);break
                attempt={'sample_id':sid,'attempt':index+1,'attempt_id':digest([binding,sid,index+1]),
                    'capture_stage':'before_parse_and_guard','prompt_messages':messages,'prompt_sha256':digest(messages),**budget}
                started=time.perf_counter()
                try:
                    generation=backend.generate(messages,call_config)
                    attempt.update(raw_text=generation.text,output_tokens=generation.output_tokens,latency_s=generation.latency_s,
                        finish_reason=generation.finish_reason,eos_reached=generation.eos_reached,runtime_error=None)
                except RuntimeError as exc:
                    attempt.update(raw_text=None,output_tokens=0,token_count_unknown=True,
                        latency_s=time.perf_counter()-started,finish_reason='runtime_error',runtime_error=str(exc))
                # This write MUST precede all JSON parsing and disclosure screens.
                _append(journal,attempt);all_rows.append(attempt);rows.append(attempt)
            attempt=rows[index];index+=1
            if attempt.get('runtime_error'):
                last_error=attempt['runtime_error'];infrastructure_failure=True
                if newly_generated:break
                continue
            infrastructure_failure=False
            try:
                parsed=parse_response(attempt['raw_text']);latest_schema=parsed
                violations=disclosure_violations(parsed['feedback'],level)
                decision={'attempt_id':attempt['attempt_id'],'schema_valid':True,'disclosure_violations':violations,
                          'audit_flags':audit_flags(parsed['feedback'],level),'accepted':not violations}
                if not violations:accepted=parsed
                else:last_error='disclosure: '+','.join(violations)
            except (ValueError,TypeError,KeyError) as exc:
                last_error=str(exc)
                decision={'attempt_id':attempt['attempt_id'],'schema_valid':False,'accepted':False,'error':last_error}
            if attempt['attempt_id'] not in outcomes:
                _append(decisions,decision);outcomes[attempt['attempt_id']]=decision
            elif outcomes[attempt['attempt_id']]!=decision:raise ValueError('processing outcome changed under same identity')
            if accepted is not None:break
        fallback=False
        if accepted is None and latest_schema is not None and not infrastructure_failure and level<=2 and index>=maximum:
            feedback={1:'Em hãy tự đối chiếu bài làm với yêu cầu đề.',
                      2:'Chưa đủ căn cứ để nêu chính xác vị trí và nguyên nhân trong bài làm này.'}[level]
            accepted={**latest_schema,'feedback':feedback};fallback=True
        trace={'sample_id':sid,'attempts':rows,'fallback_used':fallback,'first_raw_text':rows[0]['raw_text'] if rows else None,
               'usefulness':'not_established_epistemic_fallback' if fallback else 'not_assessed_by_postprocessor',
               'first_raw_schema_output':None,'first_raw_disclosure_violations':[],
               'final_origin':'disclosure_fallback' if fallback else 'qwen_initial' if index==1 else 'qwen_retry'}
        if rows and rows[0].get('raw_text') is not None:
            try:
                first=parse_response(rows[0]['raw_text']);trace['first_raw_schema_output']=first
                trace['first_raw_disclosure_violations']=disclosure_violations(first['feedback'],level)
            except ValueError:pass
        if accepted is not None:
            trace.update(final_audit_flags=audit_flags(accepted['feedback'],level),
                raw_to_final_changed=accepted!=trace['first_raw_schema_output'],
                model_clean_is_unverified=not accepted['taxonomy_error'])
            state['completed'][sid]={'output':accepted,'trace':trace};state['errors'].pop(sid,None)
        else:
            state['errors'][sid]={'reason':last_error or 'schema_unresolved_after_bounded_attempts','trace':trace}
        write_json(state_path,state)
        print(json.dumps({'completed':len(state['completed']),'total':len(records),'unresolved':len(state['errors'])}),flush=True)
    predictions=[{'sample_id':r.sample_id,'output':state['completed'][r.sample_id]['output']} for r in records if r.sample_id in state['completed']]
    traces=[state['completed'][r.sample_id]['trace'] for r in records if r.sample_id in state['completed']]
    write_json(out/'completed.predictions.json',predictions);write_json(out/'traces.json',traces)
    if len(predictions)==len(records):write_json(out/'predictions.json',predictions)
    return {'predictions':predictions,'traces':traces,'errors':state['errors'],'identity':binding}


class RawCaptureBackend:
    """Capture the legacy controller's unmodified model return before it parses."""
    def __init__(self,backend,path):
        self.backend=backend;self.tokenizer=backend.tokenizer;self.path=Path(path)
        self.path.touch(mode=0o600,exist_ok=True);self.path.chmod(0o600)
    def generate(self,messages,config):
        generated=self.backend.generate(messages,config)
        _append(self.path,{'capture_stage':'before_legacy_parser_and_guard','prompt_messages':messages,
            'prompt_sha256':digest(messages),'raw_text':generated.text,'output_tokens':generated.output_tokens,
            'latency_s':generated.latency_s,'finish_reason':generated.finish_reason})
        return generated
