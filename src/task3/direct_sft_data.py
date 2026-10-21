"""New identity-only DIRECT pilot policy; previous family gates remain untouched.

Public source bytes are used only for opaque leakage fingerprints. No public
context, labels, requested levels, targets, or predictions enter this module's
returned source rows. Lexical screening cannot establish semantic independence.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
import zipfile

from src.task3.dataset import decode_code, load_task3, safe_code_path
from src.task3.eval_snapshot import (IDENTITY_KEYS, ZIP_SHA256, _source_member,
    identity, json_bytes, sha_bytes, sha_file, structural_shingles)
from src.task3.schema import code_hash, validate_taxonomy

VERSION = 'direct-sft-v1-20261021'
NEAR_THRESHOLD = 0.85
MATCH_KEYS = tuple(k for k in IDENTITY_KEYS if k != 'family') + ('source_text_sha256',)
POLICY = dict(version=VERSION, near_threshold=NEAR_THRESHOLD,
    family_policy='Identity-level exclusion only; family exposure alone is not a training ban.',
    evaluation_status='Evalv2 is development evaluation; this DIRECT pilot is not family-disjoint, blind, or a new heldout benchmark.',
    near_method='Identifier-erased five-token shingle Jaccard >= 0.85; threshold fixed before source counts/output.',
    near_limitations='Lexical detector is conservative but incomplete: low scores do not prove semantic independence; no claim of exhaustive semantic duplicate detection.',
    public_access='Only ID/code-file references and source bytes for protected hashes/shingles; no source text retained or displayed, no statements, levels, feedback or predictions consumed.',
    historical_exposure='Historical TRAIN exposure remains descriptive and does not itself prohibit legitimate current TRAIN membership.')


def signature(row):
    """Compute source identities when source exists, otherwise require complete metadata."""
    if 'code' in row:
        if not isinstance(row['code'],str):
            raise ValueError('actual source text required')
        out=identity(row)
        out['source_text_sha256']=sha_bytes(row['code'].encode())
        out['structural_shingles']=sorted(structural_shingles(row['code']))
    else:
        out={k:row.get(k) for k in IDENTITY_KEYS}
        out['source_text_sha256']=row.get('source_text_sha256')
        out['structural_shingles']=row.get('structural_shingles')
    if any(not isinstance(out.get(k),str) or not out[k] for k in IDENTITY_KEYS):
        raise ValueError('incomplete protected identity/signature')
    if not isinstance(out.get('structural_shingles'),list) or not out['structural_shingles']:
        raise ValueError('missing source shingle signature; fail closed')
    # Older metadata may lack decoded-text SHA but retains raw SHA and token hashes.
    out['reason']=row.get('reason','protected source identity')
    return out


def _score(a,b):
    x,y=set(a['structural_shingles']),set(b['structural_shingles'])
    return len(x&y)/len(x|y) if x|y else 1.0


def _conflicts(actual, protected):
    reasons=[];matches=[]
    for old in protected:
        keys=[k for k in MATCH_KEYS if actual.get(k) and actual[k]==old.get(k)]
        score=_score(actual,old)
        if score>=NEAR_THRESHOLD:keys.append('near_duplicate>=0.85')
        if keys:
            reasons.extend(keys);matches.append(dict(sample_id=old['sample_id'],keys=keys,similarity=score))
    return sorted(set(reasons)),matches


def select_candidates(rows, protected):
    """Deterministically deduplicate the complete candidate pool, including splits."""
    protected=[signature(r) for r in protected]
    eligible=[];excluded=[];seen=[]
    for row in sorted(rows,key=lambda r:(r.get('origin')!='real-train',r['sample_id'])):
        try:
            if not isinstance(row.get('code'),str) or not row['code'].strip():raise ValueError('nonempty actual candidate source required')
            sig=signature(row)
        except ValueError as exc:
            excluded.append(dict(sample_id=row.get('sample_id'),origin=row.get('origin'),reasons=[str(exc)],matches=[]));continue
        reasons,matches=_conflicts(sig,protected)
        duplicate,other=_conflicts(sig,seen)
        reasons += ['candidate_duplicate:'+r for r in duplicate]
        matches += [dict(m,scope='candidate_pool') for m in other]
        if reasons:
            excluded.append(dict(sample_id=row['sample_id'],family=row['family'],origin=row.get('origin'),reasons=sorted(set(reasons)),matches=matches))
        else:
            eligible.append(dict(row,**{k:v for k,v in sig.items() if k!='reason'}));seen.append(sig)
    return eligible,excluded


def make_registry(eligible, protected):
    return dict(version=VERSION,near_threshold=NEAR_THRESHOLD,policy=POLICY,
                eligible=[signature(r) for r in eligible],protected=[signature(r) for r in protected])


def require_direct_isolation(rows,registry,*,stage):
    """Verify actual frozen sources again immediately before targets and optimizer."""
    if stage not in ('before_targets','before_optimizer'):raise ValueError('invalid guard stage')
    if registry.get('version')!=VERSION:raise ValueError('wrong DIRECT registry version')
    if registry.get('near_threshold')!=NEAR_THRESHOLD:raise ValueError('near threshold drift')
    allowed={e['sample_id']:e for e in registry['eligible']}
    if len(allowed)!=len(registry['eligible']):raise ValueError('duplicate eligible registry ID')
    protected=[signature(r) for r in registry['protected']];seen=[];checked=[]
    for row in rows:
        if not isinstance(row.get('code'),str) or not row['code'].strip():raise ValueError('actual source required at both boundaries')
        sig=signature(row);frozen=allowed.get(row['sample_id'])
        if frozen is None:raise ValueError('source outside frozen eligible membership')
        for k in IDENTITY_KEYS+('source_text_sha256',):
            if not sig.get(k) or sig[k]!=frozen.get(k):raise ValueError('source identity drift: '+k)
            if k in row and row[k]!=sig[k]:raise ValueError('declared source identity mismatch: '+k)
        if sig['structural_shingles']!=frozen['structural_shingles']:raise ValueError('source signature drift')
        reasons,_=_conflicts(sig,protected)
        if reasons:raise ValueError('protected source leakage: '+','.join(reasons))
        duplicate,_=_conflicts(sig,seen)
        if duplicate:raise ValueError('duplicate candidate source across train/validation: '+','.join(duplicate))
        checked.append(row['sample_id']);seen.append(sig)
    return dict(stage=stage,checked=len(checked),unique_sources=len(checked),eligible=True,
                identity_only=True,near_threshold=NEAR_THRESHOLD)


require_direct_sft_isolation = require_direct_isolation


def public_fingerprints(root, *, expected_count=328):
    """One-way protected fingerprints only; deliberately never load public context."""
    root=Path(root);metadata=root/'task3_feedback.json';samples=json.loads(metadata.read_bytes())['samples']
    if len(samples)!=expected_count:raise ValueError('public protection count mismatch')
    entries=[];members={};seen=set()
    for sample in samples:
        sid=sample['sample_id'];inp=sample['input']
        if sid in seen:raise ValueError('duplicate public identity')
        seen.add(sid)
        path=safe_code_path(root,inp['code_file']);raw=path.read_bytes();code=decode_code(path)
        entry=signature(dict(sample_id=sid,family=inp['exam_id'],group=code_hash(code),
            code=code,source_sha256=sha_bytes(raw),reason='public protected fingerprint only'))
        # Store opaque signatures only; no public source or contextual payload.
        entries.append(entry);members[path.relative_to(root).as_posix()]=sha_bytes(raw)
    return dict(entries=entries,count=len(entries),metadata_sha256=sha_file(metadata),source_members_sha256=members)


def _prepared(repo, split):
    path=repo/f'data/processed/task3/{split}.jsonl'
    return [json.loads(line)['record'] for line in path.read_text().splitlines() if line],sha_file(path)


def inventory_sources(repo):
    """Fresh actual ZIP bytes inventory and fixed current valid TRAIN membership."""
    repo=Path(repo);archive=repo/'generate-dataset_v2.zip'
    actual_sha=sha_file(archive)
    if actual_sha!=ZIP_SHA256:raise ValueError('archive SHA mismatch')
    prepared={};inputs={}
    for split in ('real-train','synthetic-train'):
        rows,digest=_prepared(repo,split);prepared[split]={r['sample_id']:r for r in rows}
        inputs[f'data/processed/task3/{split}.jsonl']=digest
    train_path=repo/'data/splits/train_ids.json';fixed_real=set(json.loads(train_path.read_text()));inputs['data/splits/train_ids.json']=sha_file(train_path)
    candidates=[];unavailable=[];all_synthetic=[];heldout=[]
    with zipfile.ZipFile(archive) as z:
        if len(z.namelist())!=len(set(z.namelist())):raise ValueError('duplicate archive member')
        members={i.filename:sha_bytes(z.read(i.filename)) for i in z.infolist() if not i.is_dir()}
        if not z.testzip() is None:raise ValueError('ZIP CRC failure')
        for prefix,origin in [('generate-dataset/','synthetic-train'),('generate-dataset/heldout/','original-heldout')]:
            exams={e['exam_id']:e for e in json.loads(z.read(prefix+'exams.json'))['exams']}
            samples=json.loads(z.read(prefix+'task3_feedback.json'))['samples'];seen=set()
            for s in samples:
                sid=s['sample_id']
                if sid in seen:raise ValueError('duplicate archive sample ID')
                seen.add(sid);i=s['input'];e=exams[i['exam_id']];member=_source_member(i['code_file'],prefix)
                raw=z.read(member);code=raw.decode('utf-8-sig');prior=prepared['synthetic-train'].get(sid,{})
                r=dict(sample_id=sid,family=e['exam_id'],exam_id=e['exam_id'],exam_type=e['exam_type'],
                    group=prior.get('group_key') or code_hash(code),original_submission_id=prior.get('original_submission_id') or Path(i['code_file']).stem,
                    code=code,source_sha256=sha_bytes(raw),statement=e['statement'],problems=e.get('problems',[]),grading_policy=e.get('grading_policy'),
                    requested_level=i.get('target_feedback_level'),taxonomy_annotation=validate_taxonomy(s['output']['taxonomy_error']),
                    teacher_feedback=s['output'].get('feedback'),origin=origin,split='unassigned',
                    source_member=member,provenance=dict(kind='synthetic',archive_sha256=actual_sha,source_member=member,
                        prepared_membership=sid in prepared['synthetic-train'],previous_provenance=prior.get('provenance',{})))
                r.update({k:v for k,v in signature(r).items() if k!='reason'})
                if origin=='original-heldout':heldout.append(r)
                else:
                    all_synthetic.append(r)
                    if sid in prepared['synthetic-train']:candidates.append(r)
                    else:unavailable.append(dict(sample_id=sid,family=r['family'],origin=origin,reasons=['not current valid synthetic-train membership'],matches=[]))
    present={r['sample_id'] for r in all_synthetic}
    for sid in sorted(set(prepared['synthetic-train'])-present):
        unavailable.append(dict(sample_id=sid,origin='synthetic-train',reasons=['prepared ID absent from current ZIP root'],matches=[]))
    real_root=repo/'data/raw/sample_dataset'
    for record in load_task3(real_root,'real'):
        if record.sample_id not in fixed_real or record.sample_id not in prepared['real-train']:continue
        p=Path(record.code_path);raw=p.read_bytes();prior=prepared['real-train'][record.sample_id]
        r=dict(sample_id=record.sample_id,family=record.exam_id,exam_id=record.exam_id,exam_type=record.exam_type,
            group=prior['group_key'],original_submission_id=record.original_submission_id,code=record.code,source_sha256=sha_bytes(raw),
            statement=record.statement,problems=record.problems,grading_policy=record.grading_policy,
            requested_level=record.target_feedback_level,taxonomy_annotation=record.gold_taxonomy,teacher_feedback=record.gold_feedback,
            origin='real-train',split='unassigned',source_member=str(p.relative_to(repo)),
            provenance=dict(kind='real',prepared_membership=True,fixed_train_membership=True,source_member=str(p.relative_to(repo))))
        r.update({k:v for k,v in signature(r).items() if k!='reason'});candidates.append(r)
        inputs[str(p.relative_to(repo))]=sha_bytes(raw)
    for name in ('exams.json','label_space.json','task3_feedback.json'):inputs[str((real_root/name).relative_to(repo))]=sha_file(real_root/name)
    return dict(archive_sha256=actual_sha,archive_members_sha256=members,archive_records=len(all_synthetic),
        archive_heldout_records=len(heldout),candidates=candidates,heldout=heldout,unavailable=unavailable,
        inputs_sha256=inputs,current_membership_counts={k:len(v) for k,v in prepared.items()})


def protection_registry(repo, archive_heldout):
    """Selected Evalv2 plus reserved original heldout and real-val; no family pool."""
    repo=Path(repo);inputs={};protected=[]
    for relative in ('reports/task3/TASK3_EVAL_V2_FREEZE_20261021.json',
                     'outputs/task3/eval-freeze-v2-20261021/frozen/guard-registry.private.json',
                     'outputs/task3/eval-freeze-v1-20261021/frozen/historical-inventory.private.json'):
        inputs[relative]=sha_file(repo/relative)
    manifest=json.loads((repo/'reports/task3/TASK3_EVAL_V2_FREEZE_20261021.json').read_text())
    old=json.loads((repo/'outputs/task3/eval-freeze-v2-20261021/frozen/guard-registry.private.json').read_text())
    history=json.loads((repo/'outputs/task3/eval-freeze-v1-20261021/frozen/historical-inventory.private.json').read_text())
    for entry in manifest['evaluation_selection']:
        matches=[r for r in old['protected'] if all(r[k]==entry[k] for k in IDENTITY_KEYS)]
        if not matches:raise ValueError('missing selected Evalv2 signature')
        protected.append(dict(signature(matches[0]),reason='selected Evalv2 source identity'))
    for r in archive_heldout:protected.append(dict(signature(r),reason='current ZIP original heldout reserved'))
    for r in history['entries']:
        if any('heldout' in x or 'real-val' in x for x in r['exposures']):
            protected.append(dict(signature(r),reason='historical original heldout or real-val reserved'))
    public=public_fingerprints(repo/'data/raw/public_test_release')
    protected.extend(public['entries'])
    inputs['data/raw/public_test_release/task3_feedback.json']=public['metadata_sha256']
    inputs.update({'data/raw/public_test_release/'+k:v for k,v in public['source_members_sha256'].items()})
    unique={}
    for r in protected:
        key=tuple(r[k] for k in IDENTITY_KEYS)
        if key in unique:unique[key]['reason']+='; '+r['reason']
        else:unique[key]=r
    return dict(entries=list(unique.values()),input_hashes=inputs,public_protected_count=public['count'],
                evalv2_protected_count=len(manifest['evaluation_selection']))


def summarize(rows):
    return dict(sources=len(rows),groups=len({r['group'] for r in rows}),families=len({r['family'] for r in rows}),
        by_origin=dict(sorted(Counter(r['origin'] for r in rows).items())),
        by_family=dict(sorted(Counter(r['family'] for r in rows).items())),
        groups_by_origin={k:len({r['group'] for r in rows if r['origin']==k}) for k in sorted({r['origin'] for r in rows})})


def normalize_supplement(source):
    """Use the original supplemental source task/scope, never previous target prose."""
    code=source['code'];digest=sha_bytes(code.encode())
    if source.get('source_sha256',digest)!=digest:raise ValueError('supplement source hash mismatch')
    exam=source['parent_exam']
    if not source.get('domain') or not isinstance(source.get('clean'),bool):raise ValueError('supplement original scope/clean metadata required')
    r=dict(sample_id=source['sample_id'],family=source['family'],exam_id=exam['exam_id'],exam_type=exam['exam_type'],
        group=source['group'],original_submission_id=source['sample_id'],code=code,source_sha256=digest,
        statement=exam['statement'],problems=exam.get('problems',[]),grading_policy=exam.get('grading_policy'),
        requested_level=None,taxonomy_annotation=[] if source['clean'] else sorted({f['label'] for f in source.get('findings',[])}),
        teacher_feedback=None,origin='synth-supplement',split='unassigned',original_scoped_domain=source['domain'],
        original_clean=source['clean'],original_clean_basis=source.get('clean_basis'),
        provenance=dict(kind='synth-supplement',source_artifact='outputs/task3/train-supplement-v1-20261021/source-frozen/approved.private.json',
            original_scope_preserved=True,not_in_current_zip=True,prior_provenance=source.get('provenance',{})))
    r.update({k:v for k,v in signature(r).items() if k!='reason'})
    return r
