#!/usr/bin/env python3
"""Offline all-attempt cost accounting for the frozen SFT v2 public run.

Never loads a model, queries CUDA, runs a compiler or changes inference outputs.
A costs.json is emitted only after generation-complete.json exists. Unknown
costs remain explicit nulls alongside known subtotals, never invented zeros.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from src.task3.sft_v2_public import PublicJournal
from src.task3.sft_v1_experiment import write_json

DEFAULT_OUT=REPO/'outputs/task3/sft-v2-public-20261026-run1'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def lines(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def numeric(value):
    return type(value) in (int,float) and math.isfinite(value) and value>=0


def measurement(values):
    known=[v for v in values if numeric(v)]
    return dict(known_sum=sum(known),known_count=len(known),unknown_count=len(values)-len(known),
                total=sum(known) if len(known)==len(values) else None)


def aggregate(freeze,preflight,events,normalized,compiler_records,inputs=None):
    requested=freeze['ordered_requested_ids'];expected=len(requested)
    if len(set(requested))!=expected:raise ValueError('duplicate frozen requested ID')
    by_pre={r['sample_id']:r for r in preflight}
    if len(by_pre)!=len(preflight) or set(by_pre)!=set(requested):raise ValueError('preflight ID coverage mismatch')
    by_result={r['sample_id']:r for r in normalized}
    if len(by_result)!=len(normalized) or not set(by_result)<=set(requested):raise ValueError('normalized ID coverage mismatch')
    allowed={sid:r['prompt_sha256'] for sid,r in by_pre.items() if r['status']=='evaluable'}
    reservations={};completed={};allocation={}
    for event in events:
        kind=event.get('type');sid=event.get('key')
        if kind=='generation_reserved':
            if sid not in allowed or sid in reservations:raise ValueError('unknown/duplicate physical reservation')
            if event.get('prompt_sha256')!=allowed[sid]:raise ValueError('reservation prompt binding mismatch')
            reservations[sid]=event
        elif kind=='generation_completed':
            if sid not in reservations or sid in completed:raise ValueError('orphan/duplicate generation completion')
            if event['result'].get('sample_id')!=sid:raise ValueError('generation completion ID mismatch')
            completed[sid]=event['result']
        elif kind=='public_input_allocation_failed':
            if sid not in allowed or sid in reservations or sid in allocation:raise ValueError('invalid unreserved allocation failure')
            allocation[sid]=event['result']
    maximum=freeze['maximum_physical_calls']
    if len(reservations)>maximum or len(reservations)>len(allowed):raise ValueError('physical generation ceiling exceeded')
    uncertain=sorted(set(reservations)-set(completed))
    not_called=sorted(set(requested)-set(reservations))
    preflight_failed=sorted(set(requested)-set(allowed))
    for sid in preflight_failed:
        if sid in reservations:raise ValueError('preflight failure was physically called')
    for sid,row in completed.items():
        saved=by_result.get(sid)
        if saved is not None and any(saved.get(k)!=v for k,v in row.items()):raise ValueError('normalized/completed cost mismatch: '+sid)
    statuses=Counter(r.get('status','unknown') for r in normalized)
    finish=Counter(r.get('finish_reason','unknown') for r in normalized)
    def costs(ids):
        ids=set(ids);done=[(sid,r) for sid,r in completed.items() if sid in ids]
        unknown_ids=sorted(set(uncertain)&ids)
        input_values=[r.get('input_tokens') for _,r in done]+[None]*len(unknown_ids)
        # Native exception rows may persist output_tokens=0 when generation
        # raised. That zero is not a measured generated-token count.
        output_values=[None if r.get('output_cost_unknown') or r.get('call_count_uncertain') or
            (r.get('status')=='generation_error' and r.get('output_tokens')==0) else r.get('output_tokens') for _,r in done]+[None]*len(unknown_ids)
        wall_values=[r.get('wall_s') for _,r in done]+[None]*len(unknown_ids)
        return dict(physical_reservations=len(set(reservations)&ids),completed_calls=len(done),
            reservations_without_saved_completion=len(unknown_ids),uncertain_ids=unknown_ids,
            input_tokens=measurement(input_values),output_tokens=measurement(output_values),
            completed_call_wall_s=measurement(wall_values),
            completed_status_counts=dict(Counter(r.get('status','unknown') for _,r in done)),
            completed_finish_reason_counts=dict(Counter(r.get('finish_reason','unknown') for _,r in done)))
    levels={}
    for level in (1,2,3,4):
        ids=[sid for sid,r in by_pre.items() if r['level']==level]
        subset=[r for r in normalized if r['sample_id'] in set(ids)]
        levels[str(level)]=dict(requested=len(ids),preflight_evaluable=sum(sid in allowed for sid in ids),
            preflight_failure=sum(sid not in allowed for sid in ids),normalized=len(subset),
            status_counts=dict(Counter(r.get('status','unknown') for r in subset)),
            finish_reason_counts=dict(Counter(r.get('finish_reason','unknown') for r in subset)),**costs(ids))
    base_load=[e for e in events if e.get('type')=='base_model_load_completed']
    combined_load=[e for e in events if e.get('type')=='public_model_and_adapter_load_completed']
    phases=[];open_phase=None
    for e in events:
        if e.get('type')=='public_generation_phase_started':
            if open_phase is not None:phases.append(dict(start=open_phase,completed=False,end=None))
            open_phase=e
        elif e.get('type')=='public_generation_phase_completed':
            if open_phase is None:raise ValueError('generation phase completion without start')
            phases.append(dict(start=open_phase,completed=True,end=e));open_phase=None
    if open_phase is not None:phases.append(dict(start=open_phase,completed=False,end=None))
    phase_ends=[p['end'] for p in phases if p['completed']]
    incomplete=sum(not p['completed'] for p in phases)
    phase_wall=measurement([p['end'].get('wall_s') if p['completed'] else None for p in phases])
    def measured_peak(field):
        values=[p.get(field) for p in phase_ends];known=[v for v in values if numeric(v)]
        return dict(maximum_completed_phase_bytes=max(known) if known else None,
            whole_trajectory_peak_bytes=max(known) if known and not incomplete and len(known)==len(phases) else None,
            unmeasured_or_incomplete_phases=len(phases)-len(known))
    flags=Counter();syntax_status=Counter();compiler_unknown_latency=0
    for item in compiler_records:
        if item.get('syntax_only') is not True or item.get('linked') is not False or item.get('public_program_executed') is not False:
            raise ValueError('compiler evidence is not strictly syntax-only')
        command=item['identity']['flags']
        if '-fsyntax-only' not in command:raise ValueError('compiler command omitted syntax-only flag')
        flags[json.dumps(command,ensure_ascii=False)]+=1;syntax_status[item.get('status','unknown')]+=1
    return dict(version='task3-sft-v2-public-offline-costs-v1',method=freeze['method'],
        policy='All physical reservations, including invalid/failure/interrupted calls, are included. No monetary price inferred.',
        requested=expected,normalized=len(normalized),preflight_evaluable=len(allowed),preflight_failure=len(preflight_failed),
        preflight_failed_ids=preflight_failed,preflight_failure_physical_calls=0,
        maximum_physical_calls=maximum,allowed_evaluable_reservation_keys=len(allowed),
        physical_calls=len(reservations),physical_call_definition='Durable generation reservations; interrupted reservations retain uncertain actual execution/cost.',
        uncertain_physical_execution_count=len(uncertain),reserved_without_completion_ids=uncertain,
        no_reservation_count=len(not_called),no_reservation_ids=not_called,
        unreserved_input_allocation_failures=len(allocation),input_allocation_wall_s=measurement([r.get('wall_s') for r in allocation.values()]),
        status_counts=dict(statuses),finish_reason_counts=dict(finish),all_calls=costs(requested),by_level=levels,
        loading=dict(base_model_loads=len(base_load),base_model_wall_s=measurement([e.get('wall_s') for e in base_load]),
            combined_model_adapter_loads=len(combined_load),combined_model_adapter_wall_s=measurement([e.get('wall_s') for e in combined_load]),
            combined_includes_base=True,non_double_counted_load_wall_s=measurement([e.get('wall_s') for e in combined_load]),
            adapter_only_wall_s=None,adapter_only_reason='Combined measurement includes base, tokenizer, preparation, adapter attachment and instrumentation; residual is not a separately measured adapter load.',
            base_events=base_load,combined_events=combined_load),
        generation_phase=dict(phases=len(phases),completed_phases=len(phase_ends),incomplete_phases=incomplete,
            all_phases_completed=bool(phases) and not incomplete,wall_s=phase_wall,
            peak_allocated=measured_peak('peak_allocated_bytes'),peak_reserved=measured_peak('peak_reserved_bytes'),
            measurement_scope='Whole public generation phase after model/adapter load, including all success/failure calls and persistence overhead; one reset at phase start, no per-case resets. CUDA allocated/reserved counters, not whole-system NVML VRAM.',
            phase_events=phases),
        compiler=dict(unique_cached_syntax_invocations=len(compiler_records),status_counts=dict(syntax_status),
            flags=[dict(command=json.loads(command),invocations=count) for command,count in sorted(flags.items())],
            latency_s=measurement([r.get('latency_s') for r in compiler_records]),
            public_inputs=len(inputs) if inputs is not None else None,
            unique_cache_reuse_count=len(inputs)-len(compiler_records) if inputs is not None else None,
            linked_calls=0,public_program_runtime_calls=0,
            compiler_processes_executed=sum(r.get('executed') is True for r in compiler_records),
            capture_limit_reached=sum(r.get('capture_limit_reached') is True for r in compiler_records),
            scope='Unique compiler cache records: syntax-only g++ processes; executed flag describes compiler process, never a public student program.'),
        known_cost_limit='Known token subtotals sum all completed calls, not just valid outputs. Null total means at least one token/latency cost is unknown. Preflight failures have no model call. Interrupted normalized zero placeholders are not used as measured costs.')


def report(out):
    out=Path(out).resolve();destination=out/'costs.json'
    if destination.exists():raise FileExistsError('costs.json already exists; never overwrite')
    marker_path=out/'generation-complete.json'
    if not marker_path.is_file():raise FileNotFoundError('generation-complete.json absent; do not write final costs before generation completes')
    names=['public-freeze.json','context-preflight.json','generation-journal.jsonl','generations.jsonl','generation-complete.json','public-inputs.private.jsonl']
    hashes={name:sha(out/name) for name in names}
    freeze=read(out/'public-freeze.json');preflight=read(out/'context-preflight.json');events=lines(out/'generation-journal.jsonl');normalized=lines(out/'generations.jsonl');marker=read(marker_path)
    if marker['journal_sha256']!=hashes['generation-journal.jsonl'] or marker['freeze_sha256']!=hashes['public-freeze.json']:raise ValueError('completion marker hash mismatch')
    allowed={r['sample_id']:r['prompt_sha256'] for r in preflight if r['status']=='evaluable'}
    PublicJournal(out/'generation-journal.jsonl',allowed)
    compilers=[]
    for path in sorted((out/'compiler').glob('*.json')):
        hashes[str(path.relative_to(out))]=sha(path);compilers.append(read(path))
    result=aggregate(freeze,preflight,events,normalized,compilers,lines(out/'public-inputs.private.jsonl'))
    for key,actual in [('expected',result['requested']),('normalized',result['normalized']),('physical_reservations',result['physical_calls']),('status_counts',result['status_counts'])]:
        if marker[key]!=actual:raise ValueError('completion marker disagrees: '+key)
    if result['requested']!=328 or result['preflight_evaluable']!=320 or result['preflight_failure']!=8 or result['maximum_physical_calls']!=328:
        raise ValueError('frozen public denominator/budget differs from verified expected 328/320/8/328')
    if result['normalized']!=result['requested']:raise ValueError('final normalized coverage is incomplete')
    if any(sha(out/name)!=value for name,value in hashes.items()):raise ValueError('input evidence changed during accounting')
    result.update(generation_complete_marker_verified=True,input_sha256=hashes,accounting_script_sha256=sha(__file__),
                  output=str(destination),generation_marker_means='Processing completed, including explicit preflight/invalid/uncertain outcomes; not proof every target yielded a valid payload.')
    write_json(destination,result)
    print(json.dumps(dict(costs=str(destination),physical_calls=result['physical_calls'],preflight_failures=result['preflight_failure'],
        input_tokens=result['all_calls']['input_tokens'],output_tokens=result['all_calls']['output_tokens'],
        loading=result['loading']['non_double_counted_load_wall_s'],generation_phase_wall_s=result['generation_phase']['wall_s']),ensure_ascii=False))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=DEFAULT_OUT)
    report(parser.parse_args().out)

if __name__=='__main__':main()
