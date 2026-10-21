#!/usr/bin/env python3
"""Freeze archive-only sources, then draft targets; never train or run C++."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))

from scripts.task3_freeze_eval_v2 import verify as verify_v2
from src.task3.eval_snapshot import identity, json_bytes, sha_bytes, sha_file, write_new, write_seal
from src.task3.eval_v2 import make_guard_registry, similarity, with_signature
from src.task3.train_supplement import (
    VERSION, TRAIN_FAMILIES, load_train_archive, normalize_recipe, validate_reviews,
    screen_sources, require_supplement_isolation, build_targets, summarize, verify_bound_snapshot,
    validate_pair_reviews, validate_target_reviews, validate_family_reviews,
)

WORK=REPO/'outputs/task3/train-supplement-v1-20261021'
SOURCE=WORK/'source-frozen'
TARGET=WORK/'target-frozen'
REPORTS=REPO/'reports/task3'
MANIFEST=REPORTS/'TASK3_TRAIN_SUPPLEMENT_V1_FREEZE_20261021.json'
TARGET_MANIFEST=REPORTS/'TASK3_TRAIN_SUPPLEMENT_V1_TARGETS_20261021.json'
V2=REPORTS/'TASK3_EVAL_V2_FREEZE_20261021.json'
BATCHES=('single-a','single-b','multi')
IMPLEMENTATION=('src/task3/train_supplement.py','scripts/task3_train_supplement.py',
                'src/task3/eval_v2.py','src/task3/eval_snapshot.py','src/task3/schema.py')


def read(path):
    return json.loads(Path(path).read_text())


def parent():
    m=verify_v2()
    p=Path(m['private_root'])
    partition=read(p/'family-partition.json')
    if partition['train_families']!=list(TRAIN_FAMILIES):
        raise ValueError('locked train partition changed')
    return m,partition,read(p/'guard-registry.private.json')


def prepare_data():
    _,partition,old=parent()
    a=load_train_archive(REPO/'generate-dataset_v2.zip')
    ex={e['exam_id']:e for e in a['exams']}
    recipes=[r for batch in BATCHES for r in read(WORK/f'recipes-{batch}.private.json')]
    if len({r['sample_id'] for r in recipes})!=len(recipes):
        raise ValueError('duplicate recipe ID')
    rows=[normalize_recipe(r,ex[r['family']]) for r in recipes]
    protected=old['protected']+[with_signature(r) for r in a['originals']]
    pairs=[];external=[]
    for i,r in enumerate(rows):
        rs=with_signature(r)
        for other in rows[i+1:]:
            score=similarity(rs,with_signature(other))
            if score>=.45:
                pairs.append(dict(left=r['sample_id'],right=other['sample_id'],similarity=score))
        closest=max(((similarity(rs,e),e['sample_id']) for e in protected),default=(0,None))
        if closest[0]>=.45:
            external.append(dict(sample_id=r['sample_id'],protected_id=closest[1],similarity=closest[0],
                decision='uncertain',reason='Conservative quarantine: protected core logic is opaque; lexical overlap cannot establish semantic independence. No protected source/reference was opened.'))
    return a,partition,old,recipes,rows,protected,pairs,external


def inventory():
    _,partition,old=parent();a=load_train_archive(REPO/'generate-dataset_v2.zip')
    return dict(archive_sha256=a['archive_sha256'],train_families=partition['train_families'],
        original_sources_by_family=dict(Counter(r['family'] for r in a['originals'])),
        prior_eligible_sources=len(old['eligible']),prior_eligible_families=len({r['family'] for r in old['eligible']}),
        exams=a['exams'],no_sources_or_teacher_feedback=True)


def inspect():
    a,partition,old,recipes,rows,protected,pairs,external=prepare_data()
    return dict(authored=summarize(rows),hard_screen=screen_sources(rows,protected),
                pairs=pairs,external_quarantine=external)


def freeze_sources(*, dry_run=False):
    if SOURCE.exists() or MANIFEST.exists():
        raise FileExistsError('source freeze already exists; never overwrite')
    a,partition,old,recipes,rows,protected,pairs,external=prepare_data()
    review_files=('review-single-a.private.json','review-single-b.private.json','review-multi-v2.private.json')
    reviews=[r for name in review_files for r in read(WORK/name)]
    by=validate_reviews(recipes,reviews)
    pair_review=read(WORK/'pair-review.private.json')
    actual=validate_pair_reviews(recipes,pairs,pair_review)
    extra=read(WORK/'pair-review-extra.private.json')
    recipe_by={r['sample_id']:r for r in recipes}
    extra_pairs=[];extra_reviews=[]
    for v in extra['extra_records']:
        score=similarity(recipe_by[v['left']],recipe_by[v['right']])
        if score>=.45:raise ValueError('extra pair belongs to mandatory near-pair review')
        extra_pairs.append(dict(left=v['left'],right=v['right'],similarity=score))
        extra_reviews.append(dict(v,similarity=score))
    extra_actual=validate_pair_reviews(recipes,extra_pairs,extra_reviews)
    if set(actual)&set(extra_actual):raise ValueError('duplicate semantic pair decision')
    actual.update(extra_actual)
    family_reviews=read(WORK/'family-review-single-b.private.json')+read(WORK/'family-review-other.private.json')
    validate_family_reviews(recipes,family_reviews)
    decisions={r['sample_id']:dict(sample_id=r['sample_id'],decision=by[r['sample_id']]['decision'],
        reasons=[by[r['sample_id']]['rationale']]) for r in rows}
    for pair,v in actual.items():
        if v['decision']!='distinct':
            affected=list(pair) if v['decision']=='uncertain' else [pair[0 if v['decision']=='reject_left' else 1]]
            for sid in affected:
                decisions[sid]['decision']='uncertain' if v['decision']=='uncertain' else 'reject'
                decisions[sid]['reasons'].append(v['rationale'])
    for d in screen_sources(rows,protected):
        if d['decision']=='reject':
            decisions[d['sample_id']]['decision']='reject';decisions[d['sample_id']]['reasons'].append(d['reasons'])
    for d in external:
        if decisions[d['sample_id']]['decision']!='reject':
            decisions[d['sample_id']]['decision']='uncertain'
        decisions[d['sample_id']]['reasons'].append(d['reason'])
    approved=[]
    for r in rows:
        r['reviewer']=by[r['sample_id']]['reviewer']
        r['evidence_level']='uncertain'
        if decisions[r['sample_id']]['decision']=='pass':
            r['evidence_level']='independently-checked static reasoning'
            if r['clean']:
                basis=by[r['sample_id']].get('clean_basis_vi')
                if not isinstance(basis,str) or not basis.strip():
                    raise ValueError('reviewed Vietnamese clean invariant required')
                r['reviewed_clean_basis_vi']=basis
            approved.append(r)
    if not approved:
        raise ValueError('no approved independent sources')
    reg=make_guard_registry(approved,protected,partition['train_families'],partition['evaluation_families'])
    reg.update(version=VERSION,parent_v2_manifest_sha256=sha_file(V2),
               family_exposure=old.get('family_exposure'),supplement_only=True)
    # Both dry checks here; before_targets is rechecked in the actual writer.
    gates={s:require_supplement_isolation(approved,reg,stage=s)
           for s in ('before_targets','before_optimizer')}
    if dry_run:
        return dict(authored=summarize(rows),approved=summarize(approved),
                    decisions=dict(Counter(d['decision'] for d in decisions.values())),
                    excluded=[d for d in decisions.values() if d['decision']!='pass'],
                    gates=gates,targets_written=False)
    inputs={f'recipes-{b}.private.json':sha_file(WORK/f'recipes-{b}.private.json') for b in BATCHES}
    inputs.update({f'review-{b}.private.json':sha_file(WORK/f'review-{b}.private.json') for b in BATCHES})
    for name in ('review-multi-v2.private.json','review-multi-errata.private.json'):
        inputs[name]=sha_file(WORK/name)
    inputs['pair-review.private.json']=sha_file(WORK/'pair-review.private.json')
    inputs['pair-review-extra.private.json']=sha_file(WORK/'pair-review-extra.private.json')
    inputs['isolation-probe.private.json']=sha_file(WORK/'isolation-probe.private.json')
    for name in ('family-review-single-b.private.json','family-review-other.private.json'):
        inputs[name]=sha_file(WORK/name)
    for f in WORK.glob('*author*.py'):inputs[f.name]=sha_file(f)
    data={'approved.private.json':approved,'candidates.private.json':rows,
          'guard-registry.private.json':reg,'independent-review.private.json':reviews,
          'exclusion-ledger.private.json':list(decisions.values()),'pair-review.private.json':pair_review,
          'semantic-family-review.private.json':extra,'isolation-probe.private.json':read(WORK/'isolation-probe.private.json'),
          'independent-family-review.private.json':family_reviews,
          'external-quarantine.private.json':external,'archive-member-hashes.json':a['member_sha256'],
          'family-partition.json':partition,'input-hashes.json':inputs}
    hashes={name:sha_bytes(json_bytes(value)) for name,value in data.items()}
    manifest=dict(version=VERSION,private_root=str(SOURCE),archive_sha256=a['archive_sha256'],
        parent_v2_manifest_sha256=sha_file(V2),family_partition_sha256=sha_file(Path(verify_v2()['private_root'])/'family-partition.json'),
        policy='Archive-only TRAIN supplement; controlled holdout with prior exposure remains unchanged. No family exposure blanket ban. No inference/training/config selection.',
        source_frozen_before_targets=True,authored=summarize(rows),approved=summarize(approved),
        decisions=dict(Counter(d['decision'] for d in decisions.values())),
        hard_leakage_rejections=sum(d['decision']=='reject' for d in screen_sources(rows,protected)),
        near_pair_count=len(pairs),below_threshold_semantic_pairs=len(extra_pairs),external_quarantine_count=len(external),gate_dry_checks=gates,
        private_files_sha256=hashes,implementation_sha256={f:sha_file(REPO/f) for f in IMPLEMENTATION},
        input_hashes=inputs,
        candidate_inventory=[dict(identity(r),decision=decisions[r['sample_id']]['decision'],
                                  parent_exam_sha256=r['parent_exam_sha256']) for r in rows],
        selection=[dict(with_signature(r),architecture_id=r['architecture_id'],mechanism_id=r['mechanism_id'],
                        parent_exam_sha256=r['parent_exam_sha256'],statement_sha256=r['statement_sha256'],
                        problems_prototype_sha256=r['problems_prototype_sha256'],policy_sha256=r['policy_sha256'],
                        clean=r['clean'],taxonomy_error=[x for x in a['label_space']['taxonomy_error'] if any(f['label']==x for f in r['findings'])]) for r in approved])
    # No source shingles in Git: these can expose source structure and belong only in the private whitelist.
    for entry in manifest['selection']:entry.pop('structural_shingles',None)
    # Construct and serialize everything before the first write. Publish the
    # public manifest only after the complete private inventory has its seal.
    manifest_hash=sha_bytes(json_bytes(manifest))
    for name,value in data.items():write_new(SOURCE/name,value)
    write_new(SOURCE/'public-manifest.json',manifest)
    write_seal(SOURCE/'seal.json',{**hashes,'public-manifest.json':manifest_hash})
    write_new(MANIFEST,manifest)
    return dict(manifest_sha256=sha_file(MANIFEST),seal_sha256=sha_file(SOURCE/'seal.json'),
                approved=manifest['approved'],decisions=manifest['decisions'])


def verify_sources():
    parent();m=read(MANIFEST)
    if m['parent_v2_manifest_sha256']!=sha_file(V2):raise ValueError('parent v2 drift')
    verify_bound_snapshot(SOURCE,{**m['private_files_sha256'],'public-manifest.json':sha_file(MANIFEST)})
    for f,h in m['implementation_sha256'].items():
        if sha_file(REPO/f)!=h:raise ValueError('implementation drift: '+f)
    for f,h in m['input_hashes'].items():
        if sha_file(WORK/f)!=h:raise ValueError('author/review drift: '+f)
    rows=read(SOURCE/'approved.private.json');reg=read(SOURCE/'guard-registry.private.json')
    return m,rows,reg


def plan():
    return freeze_sources(dry_run=True)


def targets():
    if TARGET.exists() or TARGET_MANIFEST.exists():raise FileExistsError('target draft already exists')
    _,rows,reg=verify_sources()
    gate=require_supplement_isolation(rows,reg,stage='before_targets')
    examples=build_targets(rows)
    write_new(TARGET/'draft-targets.private.json',examples)
    write_new(TARGET/'before-targets-gate.json',dict(gate,source_manifest_sha256=sha_file(MANIFEST)))
    # Review these exact bytes before a separate targets seal. No optimizer/config exists.
    return dict(draft_examples=len(examples),unique_sources=len(rows),
                targets_sha256=sha_file(TARGET/'draft-targets.private.json'),semantic_review='pending')


def seal_targets():
    if TARGET_MANIFEST.exists() or (TARGET/'seal.json').exists():raise FileExistsError('target freeze exists')
    _,rows,reg=verify_sources();examples=read(TARGET/'draft-targets.private.json')
    if examples!=build_targets(rows):raise ValueError('target render differs from source freeze')
    ledger=read(WORK/'target-review.private.json')
    validate_target_reviews(examples,ledger,rows)
    write_new(TARGET/'semantic-review.private.json',ledger)
    gate=require_supplement_isolation(rows,reg,stage='before_optimizer')
    write_new(TARGET/'before-optimizer-gate-dry-check.json',gate)
    names=('draft-targets.private.json','before-targets-gate.json','semantic-review.private.json',
           'before-optimizer-gate-dry-check.json')
    hashes={name:sha_file(TARGET/name) for name in names}
    m=dict(version=VERSION+'-draft-targets',source_manifest_sha256=sha_file(MANIFEST),
        source_seal_sha256=sha_file(SOURCE/'seal.json'),target_seal_files_sha256=hashes,
        examples=len(examples),unique_sources=len(rows),examples_by_kind=dict(Counter(r['kind'] for r in examples)),
        level_counts={str(level):sum(r['input'].get('requested_level')==level for r in examples) for level in (1,2,3)},
        taxonomy_level_blind=True,human_verified=False,review='assistant-reviewed static drafts',
        no_training=True,no_model_loading=True,no_inference=True,training_configuration='not selected or frozen; future separate authorization')
    write_new(TARGET_MANIFEST,m);write_new(TARGET/'public-manifest.json',m)
    write_seal(TARGET/'seal.json',{**hashes,'public-manifest.json':sha_file(TARGET_MANIFEST)})
    return dict(target_manifest_sha256=sha_file(TARGET_MANIFEST),target_seal_sha256=sha_file(TARGET/'seal.json'),examples=len(examples))


def verify():
    m,rows,reg=verify_sources();t=read(TARGET_MANIFEST)
    if (t['source_manifest_sha256']!=sha_file(MANIFEST) or t['source_seal_sha256']!=sha_file(SOURCE/'seal.json')):
        raise ValueError('source/target freeze binding mismatch')
    verify_bound_snapshot(TARGET,{**t['target_seal_files_sha256'],'public-manifest.json':sha_file(TARGET_MANIFEST)})
    if read(TARGET/'draft-targets.private.json')!=build_targets(rows):raise ValueError('target render drift')
    gates={s:require_supplement_isolation(rows,reg,stage=s) for s in ('before_targets','before_optimizer')}
    return dict(verified=True,sources=len(rows),examples=t['examples'],gates=gates)


def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='command',required=True)
    for name in ('inventory','inspect','plan','freeze-sources','targets','seal-targets','verify'):sub.add_parser(name)
    p=sub.add_parser('train-gate');p.add_argument('--candidates',type=Path,required=True)
    p.add_argument('--stage',choices=('before_targets','before_optimizer'),required=True)
    args=ap.parse_args()
    if args.command=='train-gate':
        verify();_,_,reg=verify_sources()
        out=require_supplement_isolation(read(args.candidates),reg,stage=args.stage)
    else:out=globals()[args.command.replace('-','_')]()
    print(json.dumps(out,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
