#!/usr/bin/env python3
"""Offline diagnostic replay; never emits predictions or repairs model coordinates.

No model/backend imports, training, compilation, code execution, or feedback.
Only one Markdown JSON fence is admitted. Lexical quote/function facts are not
semantic, active-path, call-graph, or compiler verification.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src.task3.diagnosis_contract_v1 import LABEL_SPACE, _cpp_regions, _strict_json, _location_line_claims

STAGES = ('parse', 'shape', 'labels_status', 'quote', 'location')
ORIGINAL = REPO/'outputs/task3/diagnosis-contract-v1-20261021'
DEST = REPO/'outputs/task3/diagnosis-contract-v1-replay-v1-20261021'
FUNCTION_KEYS = {'function', 'function_name'}
START_KEYS = {'line', 'start_line', 'line_start'}
END_KEYS = {'end_line', 'line_end'}
LOCATION_KEYS = FUNCTION_KEYS | START_KEYS | END_KEYS


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return sha_bytes(Path(path).read_bytes())


def read(path):
    return json.loads(Path(path).read_bytes())


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)+'\n').encode())
    path.chmod(0o600)


def parse_fenced_object(raw):
    """Exact lowercase json fence on separate lines; outside whitespace only.

    JSON decoder consumes the whole body and rejects duplicate keys/NaN. A
    fence-looking sequence inside a JSON string remains data. Multiple fence
    lines or JSON objects are rejected, with no extraction or repair.
    """
    if not isinstance(raw, str):
        raise ValueError('not_text')
    match = re.fullmatch(r'\s*```json[ \t]*\r?\n([\s\S]*?)\r?\n```[ \t]*\s*', raw)
    if not match or re.search(r'^\s*```', match.group(1), re.MULTILINE):
        raise ValueError('exact_single_json_fence_required')
    try:
        value = _strict_json(match.group(1))
    except (ValueError, TypeError) as exc:
        raise ValueError('invalid_inner_json') from exc
    if not isinstance(value, dict):
        raise ValueError('inner_object_required')
    return value


def _shape(value):
    if set(value) != {'status', 'taxonomy_error', 'findings'}:
        return ['top_level_keys']
    if not isinstance(value['status'], str) or not isinstance(value['taxonomy_error'], list) or not isinstance(value['findings'], list):
        return ['top_level_types']
    errors = []
    for finding in value['findings']:
        if not isinstance(finding, dict) or not {'label','quote','location','cause_vi'} <= set(finding) or set(finding)-{'label','quote','location','cause_vi','line'}:
            errors.append('finding_keys'); continue
        if any(not isinstance(finding[k], str) or not finding[k].strip() for k in ('label','quote','cause_vi')):
            errors.append('finding_strings')
        if 'line' in finding and (type(finding['line']) is not int or finding['line'] < 1):
            errors.append('line_type')
        location = finding['location']
        if isinstance(location, str):
            if not location.strip(): errors.append('empty_location')
        elif isinstance(location, dict):
            if not location or set(location)-LOCATION_KEYS:
                errors.append('location_keys')
            for key, claim in location.items():
                if key in FUNCTION_KEYS and (not isinstance(claim, str) or not claim.strip()):
                    errors.append('function_type')
                if key in START_KEYS | END_KEYS and (type(claim) is not int or claim < 1):
                    errors.append('location_line_type')
        else:
            errors.append('location_type')
    return errors


def _labels_status(value):
    errors = []
    labels = value['taxonomy_error']
    if any(not isinstance(label,str) or label not in LABEL_SPACE for label in labels):
        errors.append('taxonomy_label')
    if len(set(map(str,labels))) != len(labels): errors.append('duplicate_labels')
    finding_labels = [f['label'] for f in value['findings']]
    if any(label not in LABEL_SPACE for label in finding_labels): errors.append('finding_label')
    if set(map(str,labels)) != set(finding_labels): errors.append('finding_taxonomy_disagreement')
    status = value['status']
    if status not in {'clean','defective','uncertain'}: errors.append('status_value')
    if status == 'clean' and (labels or value['findings']): errors.append('clean_has_findings')
    if status == 'defective' and not value['findings']: errors.append('defective_without_findings')
    return errors


def _function_spans(code, kinds):
    """Conservative lexical function scopes, NOT a C++ parser or call graph.

    Recognizes simple named definitions only. Unknown/malformed syntax cannot
    establish scope. Conditional compilation, macros, overloads and runtime
    reachability remain unverified regardless of a lexical scope match.
    """
    masked = ''.join(c if k == 'A' else ('\n' if c == '\n' else ' ') for c,k in zip(code,kinds))
    spans = []
    for match in re.finditer(r'\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*(?:const\s*)?\{', masked):
        name = match.group(1)
        if name in {'if','for','while','switch','catch'}: continue
        opening = match.end()-1
        depth = 1
        ending = opening+1
        while ending < len(masked) and depth:
            depth += (masked[ending]=='{') - (masked[ending]=='}')
            ending += 1
        if depth == 0:
            spans.append((match.start(), ending, name))
    return spans


def _quote_facts(code, findings):
    kinds, warnings = _cpp_regions(code)
    spans = _function_spans(code,kinds)
    facts, errors = [], []
    for finding in findings:
        quote = finding['quote']; occurrences=[]; start=0
        while True:
            pos=code.find(quote,start)
            if pos < 0: break
            meaningful=[kinds[i] for i in range(pos,pos+len(quote)) if not code[i].isspace()]
            names=sorted({name for a,b,name in spans if a <= pos and pos+len(quote) <= b})
            occurrences.append(dict(offset=pos,line_start=code.count('\n',0,pos)+1,
                line_end=code.count('\n',0,pos+len(quote.rstrip('\r\n')))+1,
                lexical_classes=sorted(set(meaningful)),lexical_functions=names))
            start=pos+1
        if not occurrences: errors.append('not_found')
        elif all(o['lexical_classes']==['C'] for o in occurrences): errors.append('comment_only')
        facts.append(dict(occurrences=occurrences,reachability='unverified',semantic_correctness='unverified'))
    return facts, errors, warnings


def _location(finding, fact, known_functions):
    starts=[]; ends=[]; functions=[]; ambiguous=False; errors=[]; prose_unverified=False
    if 'line' in finding: starts.append(finding['line'])
    location=finding['location']
    if isinstance(location,dict):
        starts.extend(value for key,value in location.items() if key in START_KEYS)
        ends.extend(value for key,value in location.items() if key in END_KEYS)
        functions.extend(value for key,value in location.items() if key in FUNCTION_KEYS)
        text=finding['cause_vi']
    else:
        numeric=re.fullmatch(r'\s*(\d+)(?:\s*[-–:]\s*(\d+))?\s*',location)
        if numeric:
            starts.append(int(numeric.group(1)))
            if numeric.group(2): ends.append(int(numeric.group(2)))
        text=location+'\n'+finding['cause_vi']
        # Recognize original names explicitly present in location; never infer
        # a corrected function from the source and substitute it in prediction.
        functions.extend(name for name in known_functions if re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',location))
        functions.extend(re.findall(r'(?:hàm|function)\s+`([A-Za-z_]\w*)`',location,re.I))
        controls={'if','for','while','switch','catch','sizeof','decltype','alignof','static_cast','dynamic_cast','reinterpret_cast','const_cast'}
        functions.extend(name for name in re.findall(r'\b([A-Za-z_]\w*)\s*\(\s*\)',location) if name not in controls)
    # In prose, only explicit known function names or backticked names are
    # machine-readable location claims. Ordinary Vietnamese nouns after 'hàm'
    # cannot be treated as invented identifiers.
    for name in known_functions:
        if re.search(r'(?:hàm|function)\s+`?'+re.escape(name)+r'(?!\w)',finding['cause_vi'],re.I):
            functions.append(name)
    functions.extend(re.findall(r'(?:hàm|function)\s+`([A-Za-z_]\w*)`',finding['cause_vi'],re.I))
    prose=(location if isinstance(location,str) else '')+'\n'+finding['cause_vi']
    # A bare unknown word after 'hàm' could be a natural-language noun.
    # Preserve uncertainty instead of manufacturing a function claim.
    for name in re.findall(r'(?:hàm|function)\s+([A-Za-z_][A-Za-z_0-9]*)(?!\w)',prose,re.I):
        if name not in known_functions: prose_unverified=True
    lines,ambiguous=_location_line_claims(text); starts.extend(lines)
    occurrences=fact['occurrences']
    line_ok=[o for o in occurrences if all(x==o['line_start'] for x in starts) and all(x==o['line_end'] for x in ends)]
    if (starts or ends) and not line_ok: errors.append('line_mismatch')
    if line_ok and (starts or ends) and all(o['lexical_classes']==['C'] for o in line_ok):
        errors.append('comment_only_at_claimed_location')
    if ambiguous: errors.append('ambiguous_line_claim')
    function_ok=[o for o in occurrences if o['lexical_functions'] and all(x in o['lexical_functions'] for x in functions)]
    scope_known=any(o['lexical_functions'] for o in occurrences)
    if functions and scope_known and not function_ok: errors.append('function_mismatch')
    if functions and scope_known and (starts or ends) and line_ok and function_ok and not any(o in function_ok for o in line_ok):
        errors.append('inconsistent_claims')
    unverified=prose_unverified or (not starts and not ends) or bool(functions and not scope_known)
    return dict(errors=errors,claimed_start_lines=starts,claimed_end_lines=ends,
                claimed_functions=functions,verification='unverified' if unverified else 'lexical_claims_match' if not errors else 'mismatch')


def replay(raw, code):
    row=dict(passed={s:False for s in STAGES},first_reject_reason=None,errors={},diagnosis=None,
             quote_bearing=False,quote_facts=[],location_facts=[],lexical_warnings=[],
             location_verification='not_reached',reachability='unverified',semantic_correctness='unverified')
    def fail(stage,errors):
        row['errors'][stage]=errors
        row['first_reject_reason']=stage+':'+errors[0]
        return row
    try: value=parse_fenced_object(raw)
    except ValueError as exc: return fail('parse',[str(exc)])
    row['diagnosis']=value;row['passed']['parse']=True
    errors=_shape(value)
    if errors: return fail('shape',errors)
    row['passed']['shape']=True
    errors=_labels_status(value)
    if errors: return fail('labels_status',errors)
    row['passed']['labels_status']=True
    row['quote_bearing']=bool(value['findings'])
    facts,errors,warnings=_quote_facts(code,value['findings'])
    row['quote_facts']=facts;row['lexical_warnings']=warnings
    if errors: return fail('quote',errors)
    row['passed']['quote']=True
    kinds,_=_cpp_regions(code);known={name for _,_,name in _function_spans(code,kinds)}
    locations=[_location(f,fact,known) for f,fact in zip(value['findings'],facts)]
    row['location_facts']=locations
    errors=[error for loc in locations for error in loc['errors']]
    if errors:
        row['location_verification']='mismatch'
        return fail('location',errors)
    row['passed']['location']=True
    row['location_verification']='vacuous_no_findings' if not locations else 'unverified' if any(loc['verification']=='unverified' for loc in locations) else 'lexical_claims_match'
    return row


def summarize(rows):
    return dict(total=len(rows),cumulative_pass={stage:sum(row['passed'][stage] for row in rows) for stage in STAGES},
        first_reject_reasons=dict(Counter(row['first_reject_reason'] for row in rows if row['first_reject_reason'])),
        quote_bearing=sum(row['quote_bearing'] for row in rows),
        location_verification=dict(Counter(row['location_verification'] for row in rows)))


def taxonomy_match(predicted, reference):
    return None if reference is None else set(predicted)==set(reference)


def inventory():
    """Hash original artifacts and tracked files without interpreting excluded data."""
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=REPO).decode().split('\0')
    paths={REPO/p for p in tracked if p and (REPO/p).is_file()}
    paths.update(p for p in ORIGINAL.rglob('*') if p.is_file())
    bundle=REPO/'outputs/task3/pilot-v1-20261021/review/analysis-bundle.tar.gz'
    if bundle.is_file(): paths.add(bundle)
    paths.update(p for p in (REPO/'outputs/task3').rglob('*seal*.json') if p.is_file())
    return {str(p.relative_to(REPO)):sha(p) for p in sorted(paths)}


def load_original():
    frozen=ORIGINAL/'frozen'
    for name,expected in read(frozen/'seal.json')['files_sha256'].items():
        if Path(name).name!=name or sha(frozen/name)!=expected: raise ValueError('original seal mismatch')
    inputs=read(frozen/'inputs.private.json'); refs=read(frozen/'reference.private.json')['records']
    selected=read(frozen/'selection.private.json')['selected']
    generations=[json.loads(line) for line in (ORIGINAL/'inference/arm-SHORT/generations.jsonl').read_text().splitlines()]
    if len(inputs)!=30 or len(refs)!=30 or len(selected)!=30 or len(generations)!=30: raise ValueError('not exactly thirty')
    if len({r['sample_id'] for r in inputs})!=30 or [r['sample_id'] for r in inputs]!=[r['sample_id'] for r in selected]: raise ValueError('selection membership/order drift')
    by_ref={r['sample_id']:r for r in refs}; by_raw={r['request_id']:r for r in generations}
    if len(by_raw)!=30 or set(by_raw)!={r['request_id'] for r in inputs}: raise ValueError('raw request binding')
    cases=[]
    for item in inputs:
        ref=by_ref[item['sample_id']];generation=by_raw[item['request_id']];code=item['task']['code'];raw=generation['raw_text']
        if generation['stage']!='diagnosis' or sha_bytes(raw.encode())!=generation['raw_sha256']: raise ValueError('raw binding/hash drift')
        if code!=ref['code'] or sha_bytes(code.encode())!=ref['source_sha256']: raise ValueError('source binding/hash drift')
        row=replay(raw,code)
        diagnosis=row['diagnosis']
        labels=diagnosis.get('taxonomy_error') if isinstance(diagnosis,dict) else None
        labels=labels if isinstance(labels,list) and all(isinstance(x,str) for x in labels) else None
        row.update(sample_id=item['sample_id'],request_id=item['request_id'],requested_level=item['requested_level'],source_sha256=ref['source_sha256'],raw_sha256=generation['raw_sha256'],
            raw_taxonomy_annotation_match=None if labels is None else taxonomy_match(labels,ref['taxonomy_annotation']),
            raw_taxonomy_source_match=None if labels is None else taxonomy_match(labels,ref['source_reference']))
        cases.append(row)
    return cases


def run():
    before=inventory();cases=load_original()
    result=dict(version='contract-v1-retrospective-replay-v1',diagnostic_only=True,original_results_unchanged=True,
        head_before=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO).decode().strip(),
        script_sha256=sha(Path(__file__)),summary=summarize(cases),cases=cases,
        originals_sha256={str(p.relative_to(REPO)):sha(p) for p in [ORIGINAL/'frozen/seal.json',ORIGINAL/'frozen/inputs.private.json',ORIGINAL/'frozen/reference.private.json',ORIGINAL/'inference/arm-SHORT/generations.jsonl']})
    if inventory()!=before: raise ValueError('original artifacts changed during replay')
    baseline=DEST/'preservation-before.private.json'
    if baseline.exists():
        if any(not (REPO/name).is_file() or sha(REPO/name)!=h for name,h in read(baseline).items()):
            raise ValueError('original preservation baseline drift')
    else: write_new(baseline,before)
    write_new(DEST/'preservation-final.private.json',before)
    write_new(DEST/'protocol-replay-v1.1.private.json',result)
    print(json.dumps(result['summary'],ensure_ascii=False,indent=2))


def verify():
    baseline=read(DEST/'preservation-final.private.json')
    drift=[name for name,h in baseline.items() if not (REPO/name).is_file() or sha(REPO/name)!=h]
    if drift: raise ValueError('preservation mismatch: '+str(drift))
    result=read(DEST/'protocol-replay-v1.1.private.json')
    if result['script_sha256']!=sha(Path(__file__)): raise ValueError('replay script changed')
    cases=load_original()
    if result['cases']!=cases or result['summary']!=summarize(cases): raise ValueError('nonreproducible offline replay')
    print(json.dumps(dict(verified_original_files=len(baseline),cases=len(cases),summary=result['summary']),ensure_ascii=False,indent=2))


def combine_reviews(reviews, cases, references, adjudications=()):
    """Bind manual static judgments to original source/raw; no semantic auto-judge."""
    by={r['sample_id']:r for r in reviews}
    refs={r['sample_id']:r for r in references}
    ids=[c['sample_id'] for c in cases]
    if len(by)!=len(reviews) or set(by)!=set(ids) or len(refs)!=len(cases) or set(refs)!=set(ids):
        raise ValueError('review membership mismatch')
    changes={r['sample_id']:r for r in adjudications}
    if len(changes)!=len(adjudications) or set(changes)-set(ids): raise ValueError('adjudication membership mismatch')
    result=[]
    for case in cases:
        row=json.loads(json.dumps(by[case['sample_id']]))
        ref=refs[case['sample_id']]
        if any(row.get(key)!=case[key] for key in ('request_id','source_sha256','raw_sha256')):
            raise ValueError('review hash/request mismatch')
        if row.get('human_verified') is not False: raise ValueError('not a human-verified review')
        for key,expected in [('taxonomy_annotation_match',case['raw_taxonomy_annotation_match']),('taxonomy_source_review_match',case['raw_taxonomy_source_match'])]:
            if row.get(key) is not expected: raise ValueError('review taxonomy mismatch')
        if case['sample_id'] in changes:
            change=changes[case['sample_id']]
            allowed={'main_mechanism','main_error_omitted','correct_mechanism_wrong_coordinate_or_format','quote_active'}
            if set(change['changes'])-allowed or not change.get('rationale'): raise ValueError('invalid adjudication')
            row['adjudication']={**change,'before':{k:row[k] for k in change['changes']}}
            row.update(change['changes'])
        if row.get('main_mechanism') not in {'correct','partial','wrong','none','uncertain'}: raise ValueError('mechanism category')
        for key in ('status_correct','quote_active','location_correct','fabricated_data_or_arithmetic','main_error_omitted'):
            if row.get(key) is not None and type(row[key]) is not bool: raise ValueError('invalid semantic bool')
        if ref['defect_status']=='scoped_clean' and row.get('main_error_omitted') is not None:
            raise ValueError('clean has defect omission verdict')
        row['defect_status']=ref['defect_status']
        row['requested_level']=case['requested_level']
        row['protocol_passed']=case['passed']
        row['source_reference_unresolved']=ref['source_reference'] is None
        row['taxonomy_annotation']=ref['taxonomy_annotation']
        row['taxonomy_source_review']=ref['source_reference']
        row['original_model_location']=[f['location'] for f in case['diagnosis']['findings']]
        row['quote_sha256']=[sha_bytes(f['quote'].encode()) for f in case['diagnosis']['findings']]
        result.append(row)
    return result


def semantic_summary(rows):
    def counts(key, selected=rows):
        return {name:sum(r.get(key) is value for r in selected) for name,value in [('true',True),('false',False),('null',None)]}
    clean=[r for r in rows if r['defect_status']=='scoped_clean']
    defect=[r for r in rows if r['defect_status']=='defect']
    return dict(total=len(rows),scoped_clean=len(clean),defective=len(defect),
        mechanisms=dict(Counter(r['main_mechanism'] for r in rows)),status_correct=counts('status_correct'),
        raw_status=dict(Counter(r['raw_status'] for r in rows)),
        quote_active_static=counts('quote_active'),location_correct=counts('location_correct'),
        taxonomy_annotation_exact=counts('taxonomy_annotation_match'),taxonomy_source_exact=counts('taxonomy_source_review_match'),
        fabricated_data_or_arithmetic=counts('fabricated_data_or_arithmetic'),
        scoped_clean_false_positive=sum(r['false_positive_on_scoped_clean'] for r in clean),
        defect_core_omission=counts('main_error_omitted',defect),
        correct_mechanism_wrong_coordinate_or_format=sum(r['correct_mechanism_wrong_coordinate_or_format'] for r in rows),
        false_clean_status_on_defects=sum(r['raw_status']=='clean' for r in defect),
        unresolved_source_taxonomy_ids=[r['sample_id'] for r in rows if r['source_reference_unresolved']])


def review():
    verify()
    protocol=read(DEST/'protocol-replay-v1.1.private.json')
    refs=read(ORIGINAL/'frozen/reference.private.json')['records']
    reviews=read(DEST/'semantic-a.private.json')+read(DEST/'semantic-b.private.json')
    adjudications=read(DEST/'adjudications-v2.private.json')
    raw_by={r['request_id']:r['raw_text'] for r in map(json.loads,(ORIGINAL/'inference/arm-SHORT/generations.jsonl').read_text().splitlines())}
    if any(not r.get('short_quote') or r['short_quote'] not in raw_by[r['request_id']] for r in reviews):
        raise ValueError('manual raw excerpt mismatch')
    rows=combine_reviews(reviews,protocol['cases'],refs,adjudications)
    result=dict(version='contract-v1-retrospective-replay-v1',human_verified=False,
        review_method='agent static source review; no compilation/execution; protocol and semantics separate',
        inputs_sha256={name:sha(DEST/name) for name in ['protocol-replay-v1.1.private.json','semantic-a.private.json','semantic-b.private.json','adjudications-v2.private.json']},
        summary=semantic_summary(rows),rows=rows)
    write_new(DEST/'semantic-final.private.json',result)
    # Full quote table is PRIVATE. The committed handoff uses hashes and prose.
    import html
    def cell(value): return html.escape(str(value)).replace('|','&#124;').replace('\n','<br>')
    lines=['# Replay v1 — đủ 30 raw SHORT (PRIVATE)', '',
        'Agent static review, không human-verified; không compile/run source. Quote rút gọn để hiển thị, nguyên văn và tọa độ model giữ trong protocol JSON. Tọa độ quan sát không thay prediction.', '',
        '| ID | L | Status đúng | Cơ chế | Quote source trong raw (tối đa 120 ký tự) | Claim raw (tối đa 120 ký tự) | Vị trí đúng | Annotation / source-review | Bịa dữ liệu/số học | Bỏ lõi defect | Rationale |',
        '|---|---:|---|---|---|---|---|---|---|---|---|']
    for row,case in zip(rows,protocol['cases']):
        quotes=[f['quote'][:120] for f in case['diagnosis']['findings']]
        rationale=row['rationale']
        if row.get('adjudication'): rationale+=' Root adjudication: '+row['adjudication']['rationale']
        fields=[row['sample_id'],row['requested_level'],row['status_correct'],row['main_mechanism'],' / '.join(quotes) or 'Không có finding',row['short_quote'],row['location_correct'],str(row['taxonomy_annotation_match'])+' / '+str(row['taxonomy_source_review_match']),row['fabricated_data_or_arithmetic'],row['main_error_omitted'],rationale]
        lines.append('| '+' | '.join(cell(f) for f in fields)+' |')
    path=DEST/'30-ID-analysis-final.private.md'
    with path.open('x') as stream: stream.write('\n'.join(lines)+'\n')
    path.chmod(0o600)
    print(json.dumps(result['summary'],ensure_ascii=False,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['run','verify','review'])
    args=parser.parse_args()
    {'run':run,'verify':verify,'review':review}[args.command]()


if __name__=='__main__': main()
