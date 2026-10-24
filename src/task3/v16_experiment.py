"""Offline replay, frozen diagnostic pairs and measurement helpers for v1.6."""
from __future__ import annotations
import copy
from collections import Counter
import json
from pathlib import Path

from src.task3 import arm_d_plus_v15 as old
from src.task3 import arm_d_plus_v16 as method
from src.task3.dataset import read_json,write_json
from src.task3.grounded_metrics import taxonomy_metrics
from src.task3.level_blind import digest,sha
from src.task3.source_refs import source_sha


def jsonl(path):
    path=Path(path)
    return [json.loads(s) for s in path.read_text().splitlines()] if path.exists() else []


def stable(path,value):
    path=Path(path)
    if path.exists() and read_json(path)!=value:raise ValueError('frozen artifact drift: '+str(path))
    if not path.exists():write_json(path,value)


def metrics(gold,results,stage1=True):
    by={r['sample_id']:r for r in results}
    if len(by)!=len(results) or set(by)!={g['sample_id'] for g in gold}:raise ValueError('metrics exact population mismatch')
    predictions=[]
    for g in gold:
        r=by[g['sample_id']];s=r.get('stage1') if stage1 else r.get('output')
        predictions.append(s['taxonomy_error'] if s is not None else None)
    m=taxonomy_metrics([g['taxonomy_error'] for g in gold],predictions)
    m.update(ids=[g['sample_id'] for g in gold],invalid_ids=[g['sample_id'] for g,p in zip(gold,predictions) if p is None],
             clean_ids=[g['sample_id'] for g in gold if not g['taxonomy_error']],
             clean_false_alarms=sum(not g['taxonomy_error'] and bool(p) for g,p in zip(gold,predictions)),
             clean_invalid=sum(not g['taxonomy_error'] and p is None for g,p in zip(gold,predictions)))
    for p in m['per_label'].values():p['recall']=p['TP']/p['support'] if p['support'] else 0.
    valid=[(g,p) for g,p in zip(gold,predictions) if p is not None]
    m['valid_only_secondary']=dict(ids=[g['sample_id'] for g,p in valid],denominator=len(valid),
        metrics=taxonomy_metrics([g['taxonomy_error'] for g,p in valid],[p for g,p in valid]) if valid else None)
    return m


def offline_replay(prior,out):
    prior=Path(prior);out=Path(out);summary={};cache={}
    for phase in ('internal','public'):
        source=prior/phase;units=read_json(source/'enriched-inputs.private.json')['units']
        labels=read_json(source/'label-space.private.json')['taxonomy_error'];all_rows=jsonl(source/'attempts.jsonl')
        indexed={}
        for index,r in enumerate(all_rows,1):
            if r['prompt_sha256']!=digest(r['messages']):raise ValueError('historical row prompt hash mismatch')
            if r['stage']=='taxonomy':
                key=(r['sample_id'],r['attempt'])
                if key in indexed:raise ValueError('duplicate historical detector attempt')
                indexed[key]=(index,r)
        records=[];cached={};replay_results=[]
        for u in units:
            sid=u['sample_id'];first=indexed.get((sid,0));second=indexed.get((sid,1))
            if first:
                if first[1]['messages']!=old.messages_findings(u,labels):raise ValueError('historical detector input/prompt mismatch: '+sid)
                cached[sid]={**first[1],**dict(original_run=str(source.resolve()),original_row=first[0],original_key=first[1]['key'],
                    raw_sha256=source_sha(first[1]['raw_text'] or ''),input_identity=digest(u),new_parser_identity=method.PARSER_VERSION)}
            record=method.select_replay(first[1] if first else None,second[1] if second else None,u,labels)
            record.update(sample_id=sid,input_identity=digest(u),original_run=str(source.resolve()),original_input_sha256=sha(source/'enriched-inputs.private.json'),
                          original_attempts_sha256=sha(source/'attempts.jsonl'),new_parser_identity=method.PARSER_VERSION)
            for name,indexed_row in (('baseline',first),('historical_correction',second)):
                a=record[name]
                if indexed_row:
                    r=indexed_row[1]
                    a['provenance']=dict(original_row=indexed_row[0],original_key=r['key'],prompt_sha256=r['prompt_sha256'],
                        raw_sha256=source_sha(r['raw_text'] or ''),original_run=str(source.resolve()),input_identity=digest(u),new_parser_identity=method.PARSER_VERSION)
                    method.persist_audit(out/'replay'/phase,digest([sid,name]),r,a)
            stage1=None;mapping=[]
            if record['baseline']['schema_reference_success']:
                try:
                    findings,mapping=old.normalize_findings(old.extract_findings(record['baseline']['findings'],u),labels,None,sid)
                    stage1=dict(findings=findings,taxonomy_error=old.taxonomy(findings,labels))
                except ValueError:
                    record['pending_mapping']=True
            replay_results.append(dict(sample_id=sid,level=u['level'],stage1=stage1,output=None,status='replay_only',mapping_audit=mapping))
            records.append(record)
        counts={}
        for name in ('baseline','historical_correction'):
            selected=[r[name] for r in records if r[name] is not None]
            counts[name]=dict(population=len(units),available=sum(a['status']!='not_generated' for a in selected),
                raw_json_compliance=sum(a.get('raw_format_compliant',False) for a in selected),
                transport_success=sum(a.get('transport_normalized_success',False) for a in selected),
                schema_reference_success=sum(a.get('schema_reference_success',False) for a in selected),
                direct_official_success=sum(a.get('schema_reference_success',False) and a.get('direct_official_labels',False) for a in selected),
                pending_mapping=sum(a.get('schema_reference_success',False) and not a.get('direct_official_labels',False) for a in selected),
                failures=[dict(sample_id=r['sample_id'],failure=r[name].get('failure')) for r in records if r[name] and not r[name].get('schema_reference_success',False)])
        identical=[u['sample_id'] for u in units if (u['sample_id'],0) in indexed and (u['sample_id'],1) in indexed and
                   indexed[(u['sample_id'],0)][1]['raw_text']==indexed[(u['sample_id'],1)][1]['raw_text']]
        counts['byte_identical_historical_corrections']=dict(count=len(identical),ids=identical)
        # Exact historical row accounting; no hypothetical measured speedup.
        avoided=[r['sample_id'] for r in records if r['baseline'].get('schema_reference_success') and (r['sample_id'],1) in indexed]
        counts['historical_avoided_correction_rows']=dict(count=len(avoided),ids=avoided,note='historical avoided-call accounting, not measured fresh-run speedup')
        counts['replay_mapped_coverage']=sum(r['stage1'] is not None for r in replay_results)
        if phase=='internal':counts['detector_metrics']=metrics(read_json(source/'gold.private.json'),replay_results)
        write_json(out/'replay'/phase/'per-id.private.json',records)
        write_json(out/'replay'/phase/'replay-results.private.json',replay_results)
        write_json(out/'replay'/phase/'original-attempt0.private.json',list(cached.values()))
        write_json(out/'replay'/phase/'summary.json',counts)
        summary[phase]=counts;cache[phase]=cached
    write_json(out/'offline-replay-summary.json',summary)
    return summary,cache


def paired_cases():
    """Six reviewed minimal pairs; unsafe variants are never executed."""
    pairs=[]
    def add(name,clean,bad,requirement,location,line,why,invariance=False):
        cases=[]
        for variant,code,present in (('a',clean,False),('b',bad,not invariance)):
            cases.append(dict(sample_id=f'PAIR-{name}-{variant}',pair=name,variant=variant,code=code,requirement=requirement,
                expected=dict(defect_present=present,location=location,line=line if present else None,reason=why,
                              invariance=invariance,review='source-reviewed by Codex; not independent human grading'),
                code_sha256=source_sha(code)))
        pairs.extend(cases)
    accumulator='#include <iostream>\nint main(){\n int n; std::cin >> n;\n int sum=0;\n for(int i=0;i<n;++i){ int x; std::cin >> x; sum+=x; }\n std::cout << sum;\n return 0;\n}\n'
    add('accumulator',accumulator,accumulator.replace('int sum=0;','int sum;'),
        'Input extraction succeeds: first n, 1 <= n <= 10, then exactly n integers in [-100,100]. Output their sum. No further input is valid.',
        'main, sum accumulation',4,'a initializes automatic sum before every read; b reads uninitialized automatic sum in sum+=x. Sum remains within int range.')
    glob='#include <iostream>\nint count;\nint main(){\n std::cout << count;\n return 0;\n}\n'
    local='#include <iostream>\n\nint main(){ int count;\n std::cout << count;\n return 0;\n}\n'
    add('storage',glob,local,'No input. Output integer zero. This is a complete C++11 program.',
        'main, count read',3,'a global count has static storage and is zero-initialized; b moves the same declaration to automatic local scope without initialization.')
    loop='#include <iostream>\nint main(){\n int i=0;\n while(i<3){ ++i; }\n std::cout << i;\n return 0;\n}\n'
    add('progress',loop,loop.replace(' ++i; ',' '),'No input. Terminate and output integer three.',
        'main, while loop',4,'a increments i to3 and terminates; b leaves i=0 and its condition remains true.')
    array='#include <iostream>\nint main(){\n int a[3]={2,4,6};\n std::cout << a[2];\n return 0;\n}\n'
    add('bounds',array,array.replace('a[2]','a[3]'),'No input. Output the last element of the array of exactly three elements initialized to 2,4,6.',
        'main, array access',4,'a reads last valid index2; b reads one-past-end index3. Every allocated element is initialized.')
    capacity='#include <iostream>\nint main(){\n int n; std::cin >> n;\n int* a=new int[n];\n for(int i=0;i<n;++i) a[i]=i+1;\n int sum=0;\n for(int i=0;i<n;++i) sum+=a[i];\n std::cout << sum;\n delete[] a;\n return 0;\n}\n'
    add('capacity',capacity,capacity.replace('new int[n]','new int[n+1]'),
        'Input extraction succeeds with one integer n, 1 <= n <= 10. Output the sum of integers1 through n. Extra unused capacity is allowed. No further input is valid.',
        'main, allocated capacity',4,'Both variants initialize and access exactly indices0..n-1. Allocation n+1 adds unused capacity and is correct.',True)
    semi='#include <iostream>\nint main(){\n int value=1;\n std::cout << value;\n return 0;\n}\n'
    add('semicolon',semi,semi.replace('int value=1;','int value=1'),'No input. Compile as C++11 and output integer one.',
        'main, value declaration',3,'a has a valid declaration; b lacks its terminating semicolon. Subsequent diagnostics are not independent root defects.')
    return pairs


def pair_units(cases):
    return [dict(sample_id=c['sample_id'],level=2,family='paired-'+c['pair'],provenance=dict(fixture_code_sha256=c['code_sha256']),
        task=dict(statement=c['requirement'],exam_type='single_problem',code=c['code'],problems=[dict(pid='P1')],language='C++11',
                  compiler=dict(status='unavailable'),tests=dict(status='not_run',cases=[]))) for c in cases]


def public_sample(units):
    selected=set();groups={}
    for u in units:groups.setdefault((u['family'],u['level']),[]).append(u)
    buckets=[sorted(v,key=lambda u:digest(['v16-public-review-preselected-v1',u['sample_id']])) for k,v in sorted(groups.items())]
    depth=0
    while len(selected)<24:
        progress=False
        for bucket in buckets:
            if depth<len(bucket) and len(selected)<24:selected.add(bucket[depth]['sample_id']);progress=True
        if not progress:break
        depth+=1
    return dict(rule='hash-ranked round-robin across sorted (family, authoritative Level) cells; fixed before model calls',
        ids=[u['sample_id'] for u in units if u['sample_id'] in selected],
        distribution=dict(Counter(f'{u["family"]}/L{u["level"]}' for u in units if u['sample_id'] in selected)),
        risk_review='separate: all failed and flagged cases; signals never reject semantically valid schema outputs')
