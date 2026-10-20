"""Per-ID resumable A/B controller. No exceptions become clean labels.

Completed outputs are persisted individually; an unresolved ID never discards
other IDs. Raw prompts/attempts are private and must stay under ignored outputs.
"""
from __future__ import annotations
import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from src.task3.dataset import write_json
from src.task3.inference import tokenizer_metadata
from src.task3.round14 import (VERSION,parse_assessment,finish_feedback,object_json,
                              fitted_messages,feedback_errors)
from src.task3.discovery import DiscoveryInput,discover
from src.task3.discovery_render import render as verified_render


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()


def identity(records,backend,config):
    return digest({'version':VERSION,'config':config,'tokenizer':tokenizer_metadata(backend.tokenizer),
        'records':[{'id':r.sample_id,'code':r.code,'statement':r.statement,'problems':r.problems,
                    'level':r.target_feedback_level,'grading_policy':r.grading_policy,'level_definitions':r.level_definitions,'compiler':{k:v for k,v in r.provenance.get('_task3_compile_check',{}).items() if k!='latency_s'}} for r in records]})


def verified_projection(record,assessment):
    e=record.provenance.get('_task3_compile_check',{})
    item=DiscoveryInput(record.code,record.statement,
        tuple({k:p[k] for k in ('pid','prototype') if k in p} for p in record.problems),
        e.get('status','unavailable'),e.get('diagnostic',''))
    result=discover(item)
    if not result['findings'] or {f['taxonomy_group'] for f in result['findings']}!=set(assessment['taxonomy_error']):return None
    out=verified_render(item,result['findings'],int(record.target_feedback_level[6]))
    if out['status']!='rendered':return None
    if feedback_errors(record,assessment['taxonomy_error'],out['feedback']):return None
    return {'feedback':out['feedback'],'origin':'verified_structured_projection','errors':[],
            'usefulness':'bounded_finding_only_not_complete_coverage','verified_findings':result['findings']}


def run_records(records,backend,config,output_dir,*,oracle_labels=None,assessment_cache=None):
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    binding=identity(records,backend,dict(config,oracle_labels=oracle_labels,assessment_cache=assessment_cache))
    state_path=out/'progress.json'
    if not state_path.exists() and (out/'predictions.json').exists():raise ValueError('unbound existing final prediction artifact')
    if state_path.exists():
        state=json.loads(state_path.read_text())
        if state.get('identity')!=binding:raise ValueError('resume identity mismatch')
        if (out/'predictions.json').exists() and set(state['completed'])!={r.sample_id for r in records}:raise ValueError('incomplete progress cannot own a final predictions artifact')
    else:
        state={'identity':binding,'completed':{},'errors':{}}
        write_json(state_path,state)
    methods={'direct','two_stage'}
    if config.get('method') not in methods:raise ValueError('Round14 method required')
    journal=out/'attempts.jsonl';repair_journal_tail(journal);journal.touch(mode=0o600,exist_ok=True);journal.chmod(0o600);traces=[];predictions=[]
    max_retries=int(config.get('max_retries',1))
    if max_retries not in (0,1,2):raise ValueError('bounded max_retries must be 0..2')
    for record in records:
        sid=record.sample_id
        if sid in state['completed']:
            item=state['completed'][sid]
            from src.task3.schema import validate_taxonomy
            validate_taxonomy(item['output']['taxonomy_error'])
            if not item['output']['feedback'].strip():raise ValueError('invalid completed feedback')
            predictions.append({'sample_id':sid,'output':item['output']});traces.append(item['trace']);continue
        trace={'sample_id':sid,'attempts':[],'classification_fallback':False,'fallback_used':False}
        def request(stage,assessment=None):
            error=None
            cap=int(config.get('classification_max_tokens',768)) if stage in {'classify','classifier_fallback'} else int(config.get('direct_max_tokens',1024)) if stage=='direct' else int(config.get('feedback_max_tokens',640))
            if int(record.target_feedback_level[6])==4 and stage in {'direct','feedback'}:cap=int(config.get('level4_max_tokens',1536))
            for number in range(max_retries+1):
                call_config={**config,'max_new_tokens':cap}
                messages,count=fitted_messages(record,stage,backend.tokenizer,call_config,assessment=assessment,retry=error)
                generation_started=time.perf_counter()
                try:generation=backend.generate(messages,call_config)
                except RuntimeError as exc:
                    failed={'sample_id':sid,'stage':stage,'attempt':number+1,'input_tokens':count,'output_tokens':0,
                            'token_count_unknown':True,'latency_s':time.perf_counter()-generation_started,'finish_reason':'runtime_error',
                            'prompt_sha256':digest(messages),'prompt_messages':messages,'raw_text':None,'error':str(exc)}
                    trace['attempts'].append(failed)
                    with journal.open('a',encoding='utf-8') as f:f.write(json.dumps(failed,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
                    raise
                row={'sample_id':sid,'stage':stage,'attempt':number+1,'input_tokens':count,'output_tokens':generation.output_tokens,
                     'latency_s':generation.latency_s,'finish_reason':generation.finish_reason,'eos_reached':generation.eos_reached,
                     'prompt_sha256':digest(messages),'prompt_messages':messages,'raw_text':generation.text}
                try:
                    if stage=='feedback':
                        v=object_json(generation.text)
                        if set(v)!={'feedback'}:raise ValueError('feedback response must contain exactly feedback')
                        parsed=finish_feedback(record,assessment,v['feedback'])
                    else:parsed=parse_assessment(generation.text,record,direct=stage=='direct')
                    row['error']=None;trace['attempts'].append(row)
                    with journal.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
                    return parsed
                except (ValueError,TypeError,KeyError) as exc:
                    error=str(exc);row['error']=error;trace['attempts'].append(row)
                    with journal.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
            return None
        try:
            # Explicit oracle labels are available only in a development diagnostic CLI path.
            # Classification is still predicted; the oracle controls only feedback labels.
            primary='direct' if config['method']=='direct' else 'classify'
            assessment=assessment_cache[sid] if assessment_cache is not None else request(primary)
            if assessment is None and config['method']=='two_stage':
                trace['classification_fallback']=True;assessment=request('direct')
            if assessment is None:
                trace['classification_fallback']=True;assessment=request('classifier_fallback')
            if assessment is None:raise ValueError('classification_unresolved_after_bounded_independent_fallback')
            trace['assessment']=assessment
            feedback_assessment=assessment
            if oracle_labels is not None:
                labels=oracle_labels[sid]
                feedback_assessment={**assessment,'taxonomy_error':labels}
            if int(record.target_feedback_level[6])==1:
                final=finish_feedback(record,feedback_assessment,assessment.get('feedback',''))
            else:
                final=verified_projection(record,feedback_assessment)
                if final is None and config['method']=='direct' and oracle_labels is None and assessment.get('feedback'):
                    try:final=finish_feedback(record,feedback_assessment,assessment['feedback'])
                    except ValueError as exc:trace['direct_feedback_rejection']=str(exc)
                if final is None:final=request('feedback',feedback_assessment)
                if final is None:
                    # Truthful epistemic fallback, explicitly inadequate as a diagnosis/action.
                    text={2:'Chưa đủ căn cứ để nêu chính xác vị trí và nguyên nhân trong bài làm này.',
                          3:'Chưa đủ căn cứ để chỉ ra chính xác vị trí, nguyên nhân và hướng sửa phù hợp trong bài này.',
                          4:'Chưa đủ căn cứ để đưa ra lời giải mẫu đáng tin cậy cho bài làm này.'}[int(record.target_feedback_level[6])]
                    final={'feedback':text,'origin':'epistemic_feedback_fallback','usefulness':'insufficient_for_requested_level'}
                    trace['fallback_used']=True
            output={'taxonomy_error':feedback_assessment['taxonomy_error'],'feedback':final['feedback']}
            trace.update(feedback_origin=final['origin'],usefulness=final['usefulness'],
                         feedback_level_errors=feedback_errors(record,output['taxonomy_error'],output['feedback']),
                         semantic_quality='unverified_unless_independently_reviewed',
                         unknown_is_not_verified_clean=True)
            state['completed'][sid]={'output':output,'trace':trace};state['errors'].pop(sid,None)
            predictions.append({'sample_id':sid,'output':output});traces.append(trace)
        except (ValueError,TypeError,RuntimeError,KeyError) as exc:
            state['errors'][sid]={'type':type(exc).__name__,'reason':str(exc),'trace':trace}
        write_json(state_path,state)
        print(json.dumps({'completed':len(state['completed']),'total':len(records),'unresolved':len(state['errors'])}),flush=True)
    write_json(out/'completed.predictions.json',predictions)
    write_json(out/'traces.json',traces)
    if len(predictions)==len(records):write_json(out/'predictions.json',predictions)
    return {'predictions':predictions,'traces':traces,'errors':state['errors'],'identity':binding}


def journal_totals(path):
    rows=[];incomplete_tail=False
    raw=Path(path).read_text().splitlines() if Path(path).exists() else []
    for index,line in enumerate(raw):
        try:rows.append(json.loads(line))
        except json.JSONDecodeError:
            if index!=len(raw)-1:raise ValueError('corrupt attempt journal before final line')
            incomplete_tail=True
    return {'attempts':len(rows),'output_tokens':sum(r.get('output_tokens',0) for r in rows),
            'input_tokens':sum(r.get('input_tokens',0) for r in rows),
            'latency_s':sum(r.get('latency_s',0) for r in rows),'incomplete_tail':incomplete_tail,
            'unknown_token_attempts':sum(r.get('token_count_unknown',False) for r in rows)}


def repair_journal_tail(path):
    if not path.exists():return
    raw=path.read_bytes();lines=raw.splitlines(keepends=True)
    for i,line in enumerate(lines):
        try:json.loads(line)
        except (json.JSONDecodeError,UnicodeDecodeError):
            if i!=len(lines)-1:raise ValueError('corrupt journal before final attempt; preserve and inspect')
            backup=path.with_name(path.name+'.interrupted-'+uuid.uuid4().hex+'.raw')
            backup.write_bytes(raw);backup.chmod(0o600)
            path.write_bytes(b''.join(lines[:i]));return
    if raw and not raw.endswith(b'\n'):path.write_bytes(raw+b'\n')
