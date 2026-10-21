#!/usr/bin/env python3
"""Create-only private inventory and new identity-only DIRECT source gate."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from src.task3.direct_sft_data import (POLICY, VERSION, inventory_sources, make_registry,
    protection_registry, require_direct_isolation, select_candidates, summarize, normalize_supplement)
from src.task3.eval_snapshot import sha_file, write_new

DATA=REPO/'outputs/task3/direct-sft-v1-20261021/data'


def inventory():
    if DATA.exists():raise FileExistsError('DIRECT data inventory exists; never overwrite')
    sources=inventory_sources(REPO)
    protection=protection_registry(REPO,sources['heldout'])
    eligible,excluded=select_candidates(sources['candidates'],protection['entries'])
    excluded=sources['unavailable']+excluded
    registry=make_registry(eligible,protection['entries'])
    gates={s:require_direct_isolation(eligible,registry,stage=s) for s in ('before_targets','before_optimizer')}
    inventory={k:v for k,v in sources.items() if k not in ('candidates','heldout','unavailable')}
    inventory['inputs_sha256'].update(protection['input_hashes'])
    audit=dict(version=VERSION,policy=POLICY,candidates=summarize(sources['candidates']),eligible=summarize(eligible),
        excluded_records=len(excluded),exclusion_reason_counts=dict(sorted(Counter(reason for r in excluded for reason in r['reasons']).items())),
        public_protected_count=protection['public_protected_count'],evalv2_protected_count=protection['evalv2_protected_count'],
        protected_entries=len(protection['entries']),gates=gates,targets_written=False,model_calls=False,
        candidates_written_before_target_audit=True,archive_sha256=sources['archive_sha256'])
    # The complete source candidate inventory is persisted before any target audit.
    artifacts={'candidates.private.json':sources['candidates'],'inventory.private.json':inventory,
        'protected.private.json':protection,'eligible.private.json':eligible,
        'excluded.private.json':excluded,'registry.private.json':registry,'audit.private.json':audit}
    for name,value in artifacts.items():write_new(DATA/name,value)
    manifest=dict(version=VERSION,private_root=str(DATA),files_sha256={name:sha_file(DATA/name) for name in artifacts},
        implementation_sha256={rel:sha_file(REPO/rel) for rel in ('src/task3/direct_sft_data.py','scripts/task3_direct_sft_inventory.py')})
    write_new(DATA/'manifest.private.json',manifest)
    return audit


def supplement():
    """Add separately attributed, already-scoped clean TRAIN sources only."""
    extension_path=DATA/'supplement-manifest.private.json'
    if extension_path.exists():raise FileExistsError('supplement extension exists; never overwrite')
    parent=json.loads((DATA/'manifest.private.json').read_text())
    for name,digest in parent['files_sha256'].items():
        if sha_file(DATA/name)!=digest:raise ValueError('base data artifact drift')
    base=json.loads((DATA/'eligible.private.json').read_text())
    protected=json.loads((DATA/'registry.private.json').read_text())['protected']
    rel='outputs/task3/train-supplement-v1-20261021/source-frozen/approved.private.json'
    source=json.loads((REPO/rel).read_text())
    rows=[normalize_supplement(r) for r in source]
    # Existing archive/real candidates take precedence. Include only independently
    # re-reviewed clean sources in the extended whitelist; defective supplement
    # sources remain inventoried, never silently imported as additional targets.
    clean=[r for r in rows if r['original_clean']]
    eligible,excluded=select_candidates(clean,protected+base)
    registry=make_registry(base+eligible,protected)
    gates={s:require_direct_isolation(base+eligible,registry,stage=s) for s in ('before_targets','before_optimizer')}
    audit=dict(supplement_input_sources=len(rows),supplement_clean_candidates=len(clean),
        eligible=summarize(eligible),excluded=excluded,base_eligible=summarize(base),
        combined_eligible=summarize(base+eligible),gates=gates,not_in_current_zip=True,
        original_scope_preserved=True,old_targets_consumed=False,
        policy='Preexisting scoped-clean supplemental TRAIN sources; require fresh target review; no post hoc change to original scope.')
    artifacts={'supplemental-candidates.private.json':clean,'supplemental-eligible.private.json':eligible,
        'supplemental-excluded.private.json':excluded,'registry-with-supplement.private.json':registry,
        'supplement-audit.private.json':audit}
    for name,value in artifacts.items():write_new(DATA/name,value)
    extension=dict(version=VERSION+'-supplement-extension',parent_manifest_sha256=sha_file(DATA/'manifest.private.json'),
        files_sha256={name:sha_file(DATA/name) for name in artifacts},inputs_sha256={rel:sha_file(REPO/rel)},
        implementation_sha256={r:sha_file(REPO/r) for r in ('src/task3/direct_sft_data.py','scripts/task3_direct_sft_inventory.py')})
    write_new(extension_path,extension)
    return audit


def verify_inventory():
    manifest=json.loads((DATA/'manifest.private.json').read_text())
    extension_path=DATA/'supplement-manifest.private.json'
    extension=json.loads(extension_path.read_text()) if extension_path.exists() else None
    if extension and extension['parent_manifest_sha256']!=sha_file(DATA/'manifest.private.json'):raise ValueError('supplement parent drift')
    for name,digest in manifest['files_sha256'].items():
        if sha_file(DATA/name)!=digest:raise ValueError('DIRECT data artifact drift: '+name)
    for rel,digest in (extension or manifest)['implementation_sha256'].items():
        if sha_file(REPO/rel)!=digest:raise ValueError('DIRECT data implementation drift: '+rel)
    inventory=json.loads((DATA/'inventory.private.json').read_text())
    for rel,digest in inventory['inputs_sha256'].items():
        if sha_file(REPO/rel)!=digest:raise ValueError('DIRECT data input drift: '+rel)
    if sha_file(REPO/'generate-dataset_v2.zip')!=inventory['archive_sha256']:raise ValueError('DIRECT archive drift')
    if extension:
        for name,digest in extension['files_sha256'].items():
            if sha_file(DATA/name)!=digest:raise ValueError('supplement artifact drift')
        for rel,digest in extension['inputs_sha256'].items():
            if sha_file(REPO/rel)!=digest:raise ValueError('supplement input drift')
    rows=json.loads((DATA/'eligible.private.json').read_text());registry=json.loads((DATA/('registry-with-supplement.private.json' if extension else 'registry.private.json')).read_text())
    if extension:rows+=json.loads((DATA/'supplemental-eligible.private.json').read_text())
    return manifest,rows,registry


def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='command',required=True)
    sub.add_parser('inventory');sub.add_parser('verify');sub.add_parser('supplement')
    gate=sub.add_parser('train-gate');gate.add_argument('--candidates',type=Path,required=True)
    gate.add_argument('--stage',choices=('before_targets','before_optimizer'),required=True)
    args=ap.parse_args()
    if args.command=='inventory':out=inventory()
    elif args.command=='supplement':out=supplement()
    else:
        _,rows,registry=verify_inventory()
        if args.command=='verify':out=dict(verified=True,sources=len(rows),gates={s:require_direct_isolation(rows,registry,stage=s) for s in ('before_targets','before_optimizer')})
        else:out=require_direct_isolation(json.loads(args.candidates.read_text()),registry,stage=args.stage)
    print(json.dumps(out,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
