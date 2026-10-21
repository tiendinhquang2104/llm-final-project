"""Archive-only, source-sealed training supplement. No compiler or model runtime.

The immutable evaluation-v2 guard is reused, never relaxed. Static evidence is
explicitly weaker than execution; review metadata is not a truth detector.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import zipfile

from src.task3.eval_snapshot import (
    LABEL_SPACE, ZIP_SHA256, _source_member, identity, json_bytes, sha_bytes,
    sha_file, verify_seal,
)
from src.task3.eval_v2 import (
    identity_conflicts, require_train_isolation, similarity, with_signature,
)

VERSION = 'train-supplement-v1'
TRAIN_FAMILIES = tuple('SYN-'+s for s in (
    'COUNT','COUNTEVEN','COUNTVOWEL','GEN','MAXARR','PALIN','POWER','RANGE','SUMPAIR','UPPER'))


def load_train_archive(path, *, expected_sha=ZIP_SHA256):
    """Filter root metadata BEFORE reading sources; never visit heldout members.

    task3_feedback.json is the archive's source index. Its teacher prose is never
    retained or used. Only the official labels are kept for comparison.
    """
    if sha_file(path) != expected_sha:
        raise ValueError('archive SHA mismatch')
    members = {}
    with zipfile.ZipFile(path) as z:
        if len(z.namelist()) != len(set(z.namelist())):
            raise ValueError('duplicate archive member')
        def read(name):
            raw=z.read(name);members[name]=sha_bytes(raw);return raw
        base='generate-dataset/'
        label_space=json.loads(read(base+'label_space.json'))
        if label_space['taxonomy_error'] != list(LABEL_SPACE):
            raise ValueError('official label space mismatch')
        exams=[e for e in json.loads(read(base+'exams.json'))['exams']
               if e['exam_id'] in TRAIN_FAMILIES]
        by={e['exam_id']:e for e in exams}
        if len(exams)!=10 or set(by)!=set(TRAIN_FAMILIES):
            raise ValueError('locked ten train contexts required')
        originals=[]
        for sample in json.loads(read(base+'task3_feedback.json'))['samples']:
            inp=sample['input'];family=inp['exam_id']
            if family not in by:
                continue
            member=_source_member(inp['code_file'],base)
            if '/heldout/' in member:
                raise ValueError('heldout source forbidden')
            raw=read(member);code=raw.decode('utf-8-sig')
            originals.append(dict(sample_id=sample['sample_id'],family=family,code=code,
                source_sha256=sha_bytes(raw),source_member=member,
                annotation_comparison_only=sample.get('output',{}).get('taxonomy_error')))
    return dict(archive_sha256=expected_sha,exams=exams,label_space=label_space,
                originals=originals,member_sha256=members)


def normalize_recipe(recipe, exam):
    r=deepcopy(recipe)
    if r.get('family') not in TRAIN_FAMILIES or r['family']!=exam['exam_id']:
        raise ValueError('source and context must belong to locked TRAIN family')
    required=('sample_id','architecture_id','mechanism_id','mechanism_summary','code')
    if any(not isinstance(r.get(k),str) or not r[k].strip() for k in required):
        raise ValueError('incomplete source provenance or domain')
    domain=r.get('domain')
    if not (isinstance(domain,str) and domain.strip() or isinstance(domain,dict) and domain
            and all(isinstance(v,str) and v.strip() for v in domain.values())):
        raise ValueError('explicit nonempty domain required')
    if not r['sample_id'].startswith('SUP1-'):
        raise ValueError('versioned supplement ID required')
    p=r.get('provenance',{})
    if (not p.get('generator') or not p.get('origin') or p.get('seed')!=42
            or p.get('not_human_verified') is not True):
        raise ValueError('missing assistant provenance')
    if r.get('expected_compile') not in ('valid_cpp11','compile_error'):
        raise ValueError('compile expectation is not compiler evidence')
    if type(r.get('clean')) is not bool or not isinstance(r.get('findings'),list):
        raise ValueError('explicit clean/finding state required')
    if r['clean']:
        if r['findings'] or not r.get('clean_basis') or r['expected_compile']!='valid_cpp11':
            raise ValueError('clean requires invariant and no findings')
    elif not r['findings']:
        raise ValueError('defect requires source evidence')
    spans=[]
    for f in r['findings']:
        if f.get('label') not in LABEL_SPACE or f['label']=='Lỗi style':
            raise ValueError('label unsupported by allowed train task contracts')
        for key in ('quote','cause_vi','impact_vi','repair_vi'):
            if not isinstance(f.get(key),str) or not f[key].strip():
                raise ValueError('incomplete finding')
        loc=f.get('location')
        if not (isinstance(loc,str) and loc.strip() or isinstance(loc,dict)
                and isinstance(loc.get('function'),str) and loc['function']
                and type(loc.get('line_start')) is int and loc['line_start']>0):
            raise ValueError('source location required')
        if f['quote'] not in r['code']:
            raise ValueError('quote absent from source')
        e=f.get('evidence',{})
        if e.get('kind') not in ('static_counterexample','static_grammar','static_reasoning'):
            raise ValueError('unsupported evidence claim')
        if any(not isinstance(e.get(k),str) or not e[k].strip()
               for k in ('input','expected','actual_derived','reasoning')):
            raise ValueError('concrete symbolic proof required')
        starts=[];start=0
        while (start:=r['code'].find(f['quote'],start))!=-1:
            starts.append(start);start+=max(1,len(f['quote']))
        spans.append(dict(quote=f['quote'],start=starts[0],end=starts[0]+len(f['quote']),
                          all_occurrences=starts))
    labels={f['label'] for f in r['findings']}
    if (r['expected_compile']=='compile_error') != ('Lỗi biên dịch' in labels):
        raise ValueError('compile declaration and findings disagree')
    r.update(identity(r))
    r.update(exam_id=exam['exam_id'],exam_type=exam['exam_type'],parent_exam=deepcopy(exam),
        parent_exam_sha256=sha_bytes(json_bytes(exam)),
        statement_sha256=sha_bytes(exam['statement'].encode()),
        problems_prototype_sha256=sha_bytes(json_bytes(exam.get('problems',[]))),
        policy_sha256=sha_bytes(json_bytes(exam.get('grading_policy'))),
        source_text_sha256=sha_bytes(r['code'].encode()),quote_spans=spans,
        compiler_diagnostic=None,compile_evidence='static_only',
        evidence_level='author static reasoning; independent review pending',human_verified=False)
    return r


def validate_reviews(recipes, reviews):
    by={x.get('sample_id'):x for x in reviews}
    if len(by)!=len(reviews) or set(by)!={r['sample_id'] for r in recipes}:
        raise ValueError('independent review missing/duplicate/extra IDs')
    for r in recipes:
        v=by[r['sample_id']]
        if (v.get('source_sha256')!=sha_bytes(r['code'].encode()) or
                v.get('recipe_sha256')!=sha_bytes(json_bytes(r))):
            raise ValueError('review source/recipe hash binding mismatch')
        if (not v.get('reviewer') or v['reviewer']==r['provenance']['generator']
                or not v.get('rationale') or v.get('decision') not in ('pass','reject','uncertain')):
            raise ValueError('independent reviewer/decision/rationale required')
        if v['decision']=='pass':
            if (v.get('finding_checks') != [True]*len(r['findings']) or
                    v.get('compile_checked') is not True or v.get('domain_checked') is not True
                    or v.get('level_text_checked') is not True
                    or (r['clean'] and v.get('clean_checked') is not True)):
                raise ValueError('pass without complete independent static checks')
    return by


def screen_sources(rows, protected):
    """Mandatory identity/.85 rejection; below-threshold pairs require review."""
    result=[];seen=[]
    for r in rows:
        sig=with_signature(r);reasons=[]
        conflicts=identity_conflicts(r,protected+seen)
        if conflicts:reasons.append(dict(kind='identity',matches=conflicts))
        near=[]
        for e in protected+seen:
            score=similarity(sig,e)
            if score>=.85:
                near.append(dict(sample_id=e['sample_id'],similarity=score))
        if near:reasons.append(dict(kind='near_duplicate',matches=near))
        result.append(dict(sample_id=r['sample_id'],decision='reject' if reasons else 'candidate',
                           reasons=reasons))
        seen.append(sig)
    return result


def require_supplement_isolation(rows, registry, *, stage):
    if registry.get('version')!=VERSION:
        raise ValueError('versioned supplement whitelist required')
    if not rows:
        raise ValueError('empty candidate batch')
    for key in ('sample_id','group','code_identity','renamed_identity'):
        vals=[identity(r)[key] for r in rows]
        if len(vals)!=len(set(vals)):
            raise ValueError('duplicate training batch '+key)
    return require_train_isolation(rows,registry,stage=stage)


def validate_pair_reviews(recipes, pairs, reviews):
    by={r['sample_id']:r for r in recipes}
    expected={(p['left'],p['right']):p for p in pairs}
    actual={(v.get('left'),v.get('right')):v for v in reviews}
    if len(actual)!=len(reviews) or set(actual)!=set(expected):
        raise ValueError('complete near-pair review required')
    for pair,v in actual.items():
        if (v.get('similarity')!=expected[pair]['similarity'] or not v.get('reviewer')
                or not v.get('rationale') or v.get('decision') not in ('distinct','reject_left','reject_right','uncertain')):
            raise ValueError('invalid source-pair review')
        for side,sid in zip(('left','right'),pair):
            r=by[sid]
            if v['reviewer']==r['provenance']['generator']:
                raise ValueError('pair reviewer must differ from source author')
            if (v.get(side+'_source_sha256')!=sha_bytes(r['code'].encode())
                    or v.get(side+'_recipe_sha256')!=sha_bytes(json_bytes(r))):
                raise ValueError('stale pair-review source/recipe binding')
    return actual


def validate_target_reviews(examples, ledger, sources):
    by={v.get('example_id'):v for v in ledger};source={r['sample_id']:r for r in sources}
    if len(by)!=len(ledger) or set(by)!={e['example_id'] for e in examples}:
        raise ValueError('target review incomplete')
    for e in examples:
        v=by[e['example_id']]
        if (v.get('example_sha256')!=sha_bytes(json_bytes(e)) or not v.get('reviewer')
                or v['reviewer']==source[e['sample_id']]['provenance']['generator']
                or not v.get('rationale') or v.get('pass') is not True
                or v.get('checks')!={k:True for k in ('source_grounded','level_contract','vietnamese','taxonomy_consistent')}):
            raise ValueError('independent hash-bound semantic target review required')
    return by


def validate_family_reviews(recipes, reviews):
    if len(reviews)!=10 or {v.get('family') for v in reviews}!=set(TRAIN_FAMILIES):
        raise ValueError('all ten family designs require semantic review')
    for v in reviews:
        rows=[r for r in recipes if r['family']==v['family']]
        expected=[dict({k:r[k] for k in ('sample_id','architecture_id','mechanism_id')},
                       source_sha256=sha_bytes(r['code'].encode()),
                       recipe_sha256=sha_bytes(json_bytes(r))) for r in rows]
        if (v.get('designs')!=expected or not v.get('assessment') or not v.get('reviewer')
                or any(v['reviewer']==r['provenance']['generator'] for r in rows)):
            raise ValueError('stale or non-independent family semantic audit')
    return reviews


def build_targets(rows):
    """Draft only: source review, never generated-model or teacher feedback."""
    targets=[]
    for r in rows:
        labels=[x for x in LABEL_SPACE if any(f['label']==x for f in r['findings'])]
        diagnosis=dict(status='clean' if r['clean'] else 'defective',taxonomy_error=labels,
            findings=[{k:f[k] for k in ('label','quote','location','cause_vi','evidence')} for f in r['findings']],
            basis=r.get('reviewed_clean_basis_vi',r['clean_basis']) if r['clean'] else 'Các finding đã được kiểm tra tĩnh độc lập trong miền đã nêu.',
            domain=r['domain'])
        meta=dict(sample_id=r['sample_id'],source_sha256=r['source_text_sha256'],draft=True,
                  human_verified=False,review_status='assistant-reviewed; static only')
        task=dict(exam=r['parent_exam'],code=r['code'],domain=r['domain'],
                  compiler_evidence=dict(available=False,diagnostic=None))
        targets.append(dict(meta,example_id=r['sample_id']+'-D',kind='diagnostic',
                            input=task,output=diagnosis))
        for level in (1,2,3):
            if r['clean']:
                text='Trong miền đầu vào đã nêu, chưa thấy lỗi làm sai yêu cầu.'
                if level>=2:text+=' '+r.get('reviewed_clean_basis_vi',r['clean_basis'])
            elif level==1:
                text='Bài làm còn vấn đề cần kiểm tra để đáp ứng đúng yêu cầu đề bài.'
            else:
                def location(f):
                    loc=f['location']
                    return (loc if isinstance(loc,str) else
                            loc['function']+' (dòng '+str(loc['line_start'])+')')
                text=' '.join('Ở '+location(f)+', '+f['cause_vi']+' '+f['impact_vi']+
                              (' '+f['repair_vi'] if level==3 else '') for f in r['findings'])
            targets.append(dict(meta,example_id=r['sample_id']+'-L'+str(level),kind='feedback',
                input=dict(task=task,diagnosis=deepcopy(diagnosis),requested_level=level),
                output=dict(feedback=text)))
    return targets


def verify_bound_snapshot(root, hashes):
    return verify_seal(Path(root)/'seal.json',expected_hashes=hashes)


def summarize(rows):
    return dict(sources=len(rows),families=dict(sorted(Counter(r['family'] for r in rows).items())),
        clean=sum(r['clean'] for r in rows),defective=sum(not r['clean'] for r in rows),
        exam_type=dict(Counter(r['exam_type'] for r in rows)),
        per_label={label:sum(any(f['label']==label for f in r['findings']) for r in rows) for label in LABEL_SPACE},
        expected_compile=dict(Counter(r['expected_compile'] for r in rows)),
        compiler_confirmed=0,counterexample_executed=0,
        evidence_levels=dict(Counter(r['evidence_level'] for r in rows)),
        evidence='Static only; assistant-reviewed, not human-verified. Uncertain sources are excluded from targets.')
