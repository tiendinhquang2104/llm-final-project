#!/usr/bin/env python3
"""Offline comparison, evidence packets and costs for fresh context32768 outputs.

No model, CUDA, compiler or semantic grader is invoked. Prior responses are read
only for descriptive comparison and narrowly bound semantic-review reuse; they
are never copied into new generation/submission payloads.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from src.synth.feedback import FEEDBACK_LEVELS
from src.task3.sft_v1_evaluation import parse_response
from src.task3.sft_v1_experiment import write_json
from src.task3.sft_v2_public import PublicJournal
from scripts.task3_sft_v2_public_costs import aggregate as aggregate_costs

DEFAULT_OUT=REPO/'outputs/task3/sft-v2-public-context32768-20261026-run1'
DEFAULT_PREVIOUS=REPO/'outputs/task3/sft-v2-public-20261026-run1'
CANONICALIZATION='UTF-8 bytes of json.dumps(parsed_payload, ensure_ascii=False, sort_keys=True, separators=(comma,colon), allow_nan=False); object keys sorted; array order and all feedback characters/whitespace preserved; no Unicode normalization. JSON syntax whitespace and object key order excluded. Raw-response UTF-8 byte equality is separately reported.'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def lines(path):return [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines()]
def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical_payload(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def object_sha(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def byte_sha(value):return hashlib.sha256(value).hexdigest()


def level(value):
    if type(value) is int and 1<=value<=4:return value
    if isinstance(value,str) and value in FEEDBACK_LEVELS:return FEEDBACK_LEVELS.index(value)+1
    raise ValueError('invalid authoritative Level')


def indexed(rows,requested,role,complete=False):
    found={}
    for row in rows:
        sid=row.get('sample_id')
        if sid not in requested or sid in found:raise ValueError(role+' duplicate/extra exact ID')
        if level(row.get('level',row.get('requested_level')))!=level(requested[sid]):raise ValueError(role+' authoritative Level mismatch: '+sid)
        found[sid]=row
    if complete and set(found)!=set(requested):raise ValueError(role+' missing ID')
    return found


def binding_identity(binding):
    """Source, complete rendered native input and authoritative Level binding."""
    return {name:binding.get(name) for name in ('source_sha256','decoded_source_sha256','original_statement_sha256','mapped_input','level','requested_level')}


def compare_runs(requested,old_rows,new_rows,old_bindings,new_bindings,labels,old_reviews):
    old=indexed(old_rows,requested,'previous generation',True);new=indexed(new_rows,requested,'new generation')
    ob=indexed(old_bindings,requested,'previous input',True);nb=indexed(new_bindings,requested,'new input',True)
    reviews=indexed(old_reviews,requested,'previous semantic review')
    output=[];reuse=[]
    for sid,requested_level in requested.items():
        prior=old[sid];fresh=new.get(sid)
        a=parse_response(prior.get('raw'),labels,prior.get('finish_reason','missing'))
        b=parse_response(fresh.get('raw') if fresh else None,labels,fresh.get('finish_reason','missing') if fresh else 'missing')
        both=a['status']==b['status']=='valid'
        payload_equal=both and canonical_payload(a['parsed'])==canonical_payload(b['parsed'])
        raw_equal=isinstance(prior.get('raw'),str) and fresh is not None and isinstance(fresh.get('raw'),str) and prior['raw'].encode('utf-8')==fresh['raw'].encode('utf-8')
        same_binding=canonical_payload(binding_identity(ob[sid]))==canonical_payload(binding_identity(nb[sid]))
        transition=None
        if both:transition=('nonempty' if a['parsed']['taxonomy_error'] else 'empty')+'_to_'+('nonempty' if b['parsed']['taxonomy_error'] else 'empty')
        row=dict(sample_id=sid,level=level(requested_level),requested_level=requested_level,
            previous_status=a['status'],new_status=b['status'],previous_original_status=prior.get('status'),new_original_status=fresh.get('status') if fresh else 'missing',
            previous_finish_reason=prior.get('finish_reason'),new_finish_reason=fresh.get('finish_reason') if fresh else 'missing',
            prior_valid=a['status']=='valid',new_valid=b['status']=='valid',two_valid=both,
            canonical_payload_byte_identical=payload_equal,raw_response_byte_identical=raw_equal,
            previous_canonical_payload_sha256=byte_sha(canonical_payload(a['parsed'])) if a['status']=='valid' else None,
            new_canonical_payload_sha256=byte_sha(canonical_payload(b['parsed'])) if b['status']=='valid' else None,
            label_set_changed=set(a['parsed']['taxonomy_error'])!=set(b['parsed']['taxonomy_error']) if both else None,
            feedback_exact_changed=a['parsed']['feedback']!=b['parsed']['feedback'] if both else None,
            previous_taxonomy_empty=not a['parsed']['taxonomy_error'] if a['status']=='valid' else None,
            new_taxonomy_empty=not b['parsed']['taxonomy_error'] if b['status']=='valid' else None,
            empty_nonempty_transition=transition,new_structural_failure=a['status']=='valid' and b['status']!='valid',
            input_binding_identical=same_binding,previous_binding_sha256=object_sha(binding_identity(ob[sid])),new_binding_sha256=object_sha(binding_identity(nb[sid])))
        output.append(row)
        q=reviews.get(sid);v2=q.get('outputs',{}).get('v2') if q else None
        reuse_row=dict(sample_id=sid,level=level(requested_level),payload_byte_identical=payload_equal,input_binding_identical=same_binding,
            previous_payload_sha256=row['previous_canonical_payload_sha256'],new_payload_sha256=row['new_canonical_payload_sha256'],
            previous_binding_sha256=row['previous_binding_sha256'],new_binding_sha256=row['new_binding_sha256'])
        if not v2 or not v2.get('verdicts'):
            reuse_row.update(status='not_reviewed',reason='No previous V2 semantic verdict exists; no verdict transferred.')
        elif a['status']!='valid':
            reuse_row.update(status='not_eligible_prior_null',reason='Previous response had no valid payload; null/not-evaluable review cannot transfer.')
        else:
            if v2.get('original_payload_sha256')!=object_sha(a['parsed']):raise ValueError('previous review payload hash mismatch: '+sid)
            if q.get('source_sha256')!=ob[sid].get('source_sha256'):raise ValueError('previous review source binding mismatch: '+sid)
            if payload_equal and same_binding:
                reuse_row.update(status='reused',reason='Identical canonical UTF-8 payload and unchanged full mapped input/source binding.',
                    prior_review_id=q.get('review_id'),transferred_v2_review=v2)
            else:reuse_row.update(status='requires_new_review',reason='Changed payload, invalid/missing new output or changed full input/source binding; no old verdict transferred.')
        reuse.append(reuse_row)
    eligible=[x for x in output if x['prior_valid']]
    summary=dict(requested=len(requested),prior_valid_targets=len(eligible),new_valid_targets=sum(x['new_valid'] for x in output),
        two_valid=sum(x['two_valid'] for x in eligible),payload_byte_identical=sum(x['canonical_payload_byte_identical'] for x in eligible),
        payload_not_byte_identical=sum(not x['canonical_payload_byte_identical'] for x in eligible),
        raw_response_byte_identical=sum(x['raw_response_byte_identical'] for x in eligible),
        raw_response_not_byte_identical=sum(not x['raw_response_byte_identical'] for x in eligible),
        label_set_changed=sum(x['label_set_changed'] is True for x in eligible),feedback_exact_changed=sum(x['feedback_exact_changed'] is True for x in eligible),
        empty_nonempty_transitions=dict(Counter(x['empty_nonempty_transition'] for x in eligible if x['empty_nonempty_transition'] is not None)),
        new_structural_failures=sum(x['new_structural_failure'] for x in eligible),new_structural_failure_ids=[x['sample_id'] for x in eligible if x['new_structural_failure']],
        input_binding_changes=sum(not x['input_binding_identical'] for x in output),
        invalid_policy='Invalid taxonomy/payload/termination stays invalid; it never becomes an empty/clean prediction. Label/feedback changes and taxonomy transitions require two valid payloads.',
        canonicalization=CANONICALIZATION,public_gold_available=False,semantic_performance_inferred=False)
    return dict(summary=summary,rows=output,reuse=dict(policy='Transfer only previous V2 verdicts with identical canonical payload bytes plus identical full source/mapped-input bindings; no new semantic grading.',
        canonicalization=CANONICALIZATION,counts=dict(Counter(x['status'] for x in reuse)),rows=reuse))


def eight_casebook(cases):
    text=['<!doctype html><html lang="vi"><meta charset="utf-8"><title>Tám ca trước đây vượt context</title>',
        '<style>body{font:15px system-ui;max-width:1300px;margin:2rem auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f5f6;padding:1rem}article{border-top:2px solid #888;margin:2rem 0}</style>',
        '<h1>Tám ca trước đây vượt context8192</h1><p>Phản hồi được sinh mới, giữ nguyên. Đây là gói bằng chứng; chưa thêm verdict ngữ nghĩa. Hợp lệ cấu trúc không chứng minh chẩn đoán đúng.</p>']
    block=lambda value:'<pre>'+html.escape(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2))+'</pre>'
    for c in cases:
        x=c['input']['mapped_input']
        text+=['<article><h2>'+html.escape(c['sample_id'])+' · Level '+str(c['level'])+'</h2>',block({k:v for k,v in c.items() if k not in ('raw','parsed_output','input')}),
            '<h3>Toàn bộ yêu cầu/đặc tả đã đưa vào model</h3>'+block(x['statement']),'<h3>Toàn bộ source gốc</h3>'+block(x['code']),
            '<h3>Logs được quy nguồn</h3>'+block(x.get('compile_log')),'<h3>Toàn bộ raw response</h3>'+block(c['raw']),
            '<h3>Parsed payload</h3>'+block(c['parsed_output']),'<h3>Toàn bộ binding/provenance input</h3>'+block(c['input']),'</article>']
    return '\n'.join(text)+'</html>\n'


def report(out,previous):
    out=Path(out).resolve();previous=Path(previous).resolve();dest=out/'analysis'
    marker_path=out/'generation-complete.json'
    if not marker_path.exists():raise FileNotFoundError('generation-complete.json absent; no final analysis written')
    if out==previous or previous in out.parents:raise ValueError('analysis cannot write into prior run')
    if dest.exists():raise FileExistsError('analysis already exists; preserve completed analysis')
    f=read(out/'freeze.json');marker=read(marker_path);pf=read(out/'context-preflight.json');requested=read(out/'requested-levels.private.json');labels=read(out/'official-contract.json')['taxonomy_labels']
    events=lines(out/'generation-journal.jsonl');new=lines(out/'generations.jsonl');old=lines(previous/'generations.jsonl');nb=lines(out/'public-inputs.private.jsonl');ob=lines(previous/'public-inputs.private.jsonl');oldpf=read(previous/'context-preflight.json');reviews=lines(previous/'semantic-review/review.rows.jsonl')
    input_paths=[out/name for name in ('freeze.json','freeze.sha256.json','generation-complete.json','context-preflight.json','generation-journal.jsonl','generations.jsonl','public-inputs.private.jsonl','requested-levels.private.json','official-contract.json','generation-order.json','prompt-equivalence.json')]
    input_paths += [previous/name for name in ('public-freeze.json','artifact-sha256.json','generations.jsonl','context-preflight.json','public-inputs.private.jsonl','semantic-review/review.rows.jsonl')]
    inputs={str(p):file_sha(p) for p in input_paths}
    if file_sha(out/'freeze.json')!=read(out/'freeze.sha256.json')['sha256']:raise ValueError('new runtime freeze seal mismatch')
    if marker['journal_sha256']!=file_sha(out/'generation-journal.jsonl'):raise ValueError('completion journal seal mismatch')
    if f['prior_public_freeze_sha256']!=file_sha(previous/'public-freeze.json') or f['prior_public_index_sha256']!=file_sha(previous/'artifact-sha256.json'):raise ValueError('previous run identity mismatch')
    for name,expected in f['files'].items():
        if file_sha(out/name)!=expected:raise ValueError('new frozen input changed: '+name)
    for name,expected in f['code'].items():
        if file_sha(REPO/name)!=expected:raise ValueError('new frozen runtime code changed: '+name)
    allowed={x['sample_id']:x['prompt_sha256'] for x in pf if x['status']=='evaluable'};journal=PublicJournal(out/'generation-journal.jsonl',allowed)
    completed={e['key']:e['result'] for e in events if e.get('type')=='generation_completed'}
    new_index=indexed(new,requested,'new generation');newbindings=indexed(nb,requested,'new input',True)
    if [x['sample_id'] for x in new]!=[sid for sid in requested if sid in new_index]:raise ValueError('new normalized outputs not in authoritative order')
    for sid,r in new_index.items():
        if r.get('method')!=f['method'] or r.get('runtime_identity_sha256')!=file_sha(out/'freeze.json'):raise ValueError('new generation method/freeze binding')
        if r.get('prompt_sha256')!=newbindings[sid]['prompt_sha256']:raise ValueError('new generation prompt binding')
    for sid,r in completed.items():
        if sid not in new_index or any(new_index[sid].get(k)!=v for k,v in r.items()):raise ValueError('fresh journal/normalized output mismatch: '+sid)
    if marker['physical_reservations']!=len(journal.reserved()) or marker['normalized']!=len(new):raise ValueError('generation marker count mismatch')
    result=compare_runs(requested,old,new,ob,nb,labels,reviews)
    if result['summary']['prior_valid_targets']!=320:raise ValueError('previous valid count is not verified320')
    old_blocked=[r for r in oldpf if r['status']!='evaluable']
    if len(old_blocked)!=8:raise ValueError('expected eight verified former context failures')
    newpf={x['sample_id']:x for x in pf};cases=[]
    for prior in old_blocked:
        sid=prior['sample_id'];r=new_index.get(sid);parsed=parse_response(r.get('raw') if r else None,labels,r.get('finish_reason','missing') if r else 'missing')
        cases.append(dict(sample_id=sid,requested_level=requested[sid],level=level(requested[sid]),prompt_tokens=newpf[sid]['prompt_tokens'],
            previous_prompt_tokens=prior['prompt_tokens'],allowance=newpf[sid]['allowance'],total_tokens=newpf[sid]['total_tokens'],context_limit=f['context_limit'],
            actual_input_tokens=r.get('input_tokens') if r else None,status=parsed['status'],original_generation_status=r.get('status') if r else 'missing',
            finish_reason=r.get('finish_reason') if r else 'missing',raw=r.get('raw') if r else None,parsed_output=parsed['parsed'],
            generation_reference=str(out/'generations.jsonl'),input_reference=str(out/'public-inputs.private.jsonl'),input=newbindings[sid],semantic_review_status='pending_separate_source_grounded_review'))
    costs=aggregate_costs(f,pf,events,new,[],nb)
    identities={object_sha(x['local_syntax']['identity']) for x in nb}
    compiler_refs=[]
    for identity in sorted(identities):
        p=previous/'compiler'/(identity+'.json')
        if not p.is_file():raise ValueError('reused compiler evidence missing')
        compiler_refs.append(dict(path=str(p),sha256=file_sha(p)));inputs[str(p)]=file_sha(p)
    costs['compiler'].update(new_compile_calls=0,new_link_calls=0,new_public_program_runtime_calls=0,
        reused_input_evidence_bindings=len(nb),unique_reused_compiler_evidence=len(identities),reused_compiler_references=compiler_refs,
        unique_cache_reuse_count=None,scope='This context32768 run performs zero new compiler/link/runtime calls. Prior syntax evidence is referenced for all328 inputs (326 unique cached invocations); historical compiler latency is not charged again.')
    costs.update(freeze_sha256=file_sha(out/'freeze.json'),new_runtime_code_hashes=f['code'],prior_run_fresh_generation_calls=0,
        fresh_generation_only=True,comparison_does_not_reuse_previous_outputs=True,generation_marker=marker,
        generation_cost_scope='Fresh context32768 journal reservations/completions only; previous320 generations are not included or reused.')
    summary=dict(result['summary'],method=f['method'],context_limit=f['context_limit'],freeze_sha256=file_sha(out/'freeze.json'),input_sha256=inputs,
        implementation_sha256=file_sha(__file__),new_outputs_origin='Only fresh generation journal under new method identity; old responses are comparison evidence only.',
        new_runtime_code_hashes=f['code'],formerly_blocked_valid=sum(c['status']=='valid' for c in cases),formerly_blocked_count=len(cases),
        semantic_reuse_counts=result['reuse']['counts'])
    if any(file_sha(path)!=expected for path,expected in inputs.items()):raise ValueError('evidence changed during offline postprocessing')
    dest.mkdir()
    write_json(dest/'comparison.json',summary)
    (dest/'comparison.rows.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n' for x in result['rows']),encoding='utf-8')
    write_json(dest/'eight-formerly-blocked.json',dict(cases=cases,count=len(cases),semantic_review_performed=False,raw_and_payload_unchanged=True))
    (dest/'eight-formerly-blocked.html').write_text(eight_casebook(cases),encoding='utf-8')
    write_json(dest/'semantic-review-reuse.json',dict(result['reuse'],previous_review_path=str(previous/'semantic-review/review.rows.jsonl'),previous_review_sha256=file_sha(previous/'semantic-review/review.rows.jsonl')))
    write_json(dest/'costs.json',costs)
    write_json(dest/'artifact-sha256.json',{p.name:file_sha(p) for p in sorted(dest.iterdir()) if p.is_file()})
    answer=dict(analysis=str(dest),prior_valid=summary['prior_valid_targets'],payload_identical=summary['payload_byte_identical'],raw_identical=summary['raw_response_byte_identical'],
        label_set_changed=summary['label_set_changed'],feedback_changed=summary['feedback_exact_changed'],new_structural_failures=summary['new_structural_failures'],
        formerly_blocked_valid=summary['formerly_blocked_valid'],review_reuse=summary['semantic_reuse_counts'],physical_calls=costs['physical_calls'])
    print(json.dumps(answer,ensure_ascii=False));return answer


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=DEFAULT_OUT);p.add_argument('--previous',type=Path,default=DEFAULT_PREVIOUS)
    args=p.parse_args();report(args.out,args.previous)

if __name__=='__main__':main()
