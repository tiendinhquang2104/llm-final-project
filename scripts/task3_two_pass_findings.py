#!/usr/bin/env python3
"""Internal-only findings experiment: select, freeze, verify, run, packets, score."""
from __future__ import annotations

import argparse
from collections import Counter
import io
import json
import os
from pathlib import Path
import random
import subprocess
import sys
from types import SimpleNamespace
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.task3 import two_pass_findings as new
from src.task3.dataset import load_prepared, load_task3, write_json
from src.task3.level_blind import read, sha, digest
from src.task3.grounded_metrics import taxonomy_metrics as taxonomy_summary
from src.utils.config import load_config

OUT = ROOT / 'outputs/task3/two-pass-findings-v1-20261023'
CONFIG = 'configs/task3/two_pass_findings_v1_20261023.json'
OLD_RUNS = ['two-pass-20261023', 'c-feedback-v3-20261023']
FILES = ['src/synth/taxonomy.py', 'src/synth/feedback.py', 'src/utils/json_extractor.py', 'src/utils/config.py',
         'scripts/task3_two_pass_findings_report.py', CONFIG, 'src/task3/two_pass_findings.py', 'scripts/task3_two_pass_findings.py',
         'src/task3/two_pass.py', 'src/task3/two_pass_v2.py', 'src/task3/c_feedback_v3.py',
         'src/task3/inference.py', 'src/task3/dataset.py', 'src/task3/schema.py', 'src/task3/grounded.py',
         'src/task3/level_blind.py', 'src/task3/grounded_metrics.py', 'src/task3/round15.py',
         'src/task3/round15_runner.py', 'src/task3/round15_disclosure.py', 'src/task3/round14.py',
         'src/task3/round14_runner.py', 'configs/task3/r15_selected.yaml', 'configs/task3/r15_zero_shot.yaml',
         'configs/task3/r15_common.yaml', 'configs/task3/two_pass_20261023.json']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def seal_files(root, name, paths):
    target = root / name
    require(not target.exists(), 'seal exists: ' + name)
    write_json(target, {str(p): sha(root / p) for p in paths})


def verify_seal(root, name):
    for p, h in read(root / name).items():
        require(sha(root / p) == h, 'sealed file drift: ' + p)


def index_results(units, rows):
    index = {r['sample_id']: r for r in rows}
    require(len(index) == len(rows) == len(units) and set(index) == {u['sample_id'] for u in units}, 'full ID denominator required')
    for row in rows:
        require(row.get('status') in ['resolved', 'unresolved'] and (row['status'] == 'resolved') == (row.get('output') is not None), 'status/output contradiction')
    return index


def renderer_adapter(stage1):
    return {'taxonomy_error': stage1['taxonomy_error'],
            'issues': [{'label': f['label'], 'note': f['error']} for f in stage1['findings']]}


def validate_prepared(prepared, original):
    fields = ('sample_id', 'code', 'gold_taxonomy', 'target_feedback_level', 'statement',
              'problems', 'grading_policy', 'exam_type', 'exam_id', 'source')
    require(prepared.source == 'synthetic' and prepared.split == 'synthetic-train', 'internal train source required')
    require(all(getattr(prepared, k) == getattr(original, k) for k in fields),
            'prepared/raw source or exam metadata mismatch: ' + prepared.sample_id)


def select():
    require(not (OUT / 'selection-seal.json').exists(), 'selection already locked')
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = read(ROOT / CONFIG)
    old = [u for n in OLD_RUNS for u in read(ROOT / 'outputs/task3' / n / 'units.private.json')]
    old_ids, old_families = {u['sample_id'] for u in old}, {u['family'] for u in old}
    prepared = load_prepared(ROOT / 'data/processed/task3', 'synthetic-train')
    raw_root = ROOT / 'data/synth/generate-dataset'
    raw = {r.sample_id: r for r in load_task3(raw_root, 'synthetic')}
    pool = [r for r in prepared if r.sample_id not in old_ids and r.exam_id not in old_families and int(r.target_feedback_level[6]) <= 3]
    require(len(pool) >= 30, 'insufficient family-disjoint internal train data')
    rng = random.Random(cfg['selection_seed']); rng.shuffle(pool)
    chosen = []; used = Counter(); families = Counter(); quota = Counter()
    # Fixed non-output-based allocation: 3 original-clean L1, then rare-label coverage/balanced families.
    for r in [r for r in pool if int(r.target_feedback_level[6]) == 1 and not r.gold_taxonomy][:3]:
        chosen.append(r); families[r.exam_id] += 1; quota[1] += 1
    support = Counter(t for r in pool for t in r.gold_taxonomy)
    while len(chosen) < 30:
        candidates = [r for r in pool if r not in chosen and quota[int(r.target_feedback_level[6])] < 10]
        require(bool(candidates), 'quota cannot be filled without synthetic labels')
        def priority(r):
            return (sum(1 / ((1 + used[t]) * support[t]) for t in r.gold_taxonomy), -families[r.exam_id])
        r = max(candidates, key=priority)
        chosen.append(r); used.update(r.gold_taxonomy); families[r.exam_id] += 1; quota[int(r.target_feedback_level[6])] += 1
    chosen.sort(key=lambda r: (int(r.target_feedback_level[6]), r.exam_id, r.sample_id))
    outer = ROOT / 'data-20261017T044357Z-1-001.zip'
    with zipfile.ZipFile(outer) as archive:
        nested = archive.read('data/generate-dataset.zip')
    import hashlib
    with zipfile.ZipFile(io.BytesIO(nested)) as archive:
        for name in ['exams.json', 'task3_feedback.json', 'label_space.json']:
            require(archive.read('generate-dataset/' + name) == (raw_root / name).read_bytes(), 'archive metadata mismatch: ' + name)
        units = []; selection = []; gold = []
        for r in chosen:
            original = raw[r.sample_id]
            validate_prepared(r, original)
            path = Path(original.code_path); relative = path.relative_to(raw_root)
            require(archive.read('generate-dataset/' + str(relative)) == path.read_bytes(), 'archive code mismatch')
            task = dict(statement=r.statement, exam_type=r.exam_type, problems=r.problems, grading_policy=r.grading_policy,
                        code=r.code, compiler={'status': 'unavailable', 'diagnostic': ''}, tests={'status': 'not_run', 'cases': []})
            provenance = {'archive_sha256': sha(outer), 'nested_archive_sha256': hashlib.sha256(nested).hexdigest(),
                          'code_sha256': sha(path), 'exam_sha256': digest({'statement':r.statement,'problems':r.problems,'grading_policy':r.grading_policy,'exam_type':r.exam_type}),
                          'evidence_sha256': digest([task['compiler'], task['tests']])}
            units.append({'sample_id': r.sample_id, 'level': int(r.target_feedback_level[6]), 'family': r.exam_id, 'task': task, 'provenance': provenance})
            selection.append({'sample_id': r.sample_id, 'family': r.exam_id, 'level': int(r.target_feedback_level[6]), 'exam_type': r.exam_type,
                              'split': r.split, 'source': r.source, 'code_path': str(relative), **provenance,
                              'ID_exposure': 'unknown', 'family_exposure': 'unknown', 'old16_12_ID': 'disjoint', 'old16_12_family': 'disjoint'})
            gold.append({'sample_id': r.sample_id, 'taxonomy_error': r.gold_taxonomy})
    # Positive evidence of prior use only; absence of a hit never proves unseen.
    history = []
    for run in (ROOT / 'outputs/task3').iterdir():
        if not run.is_dir() or run == OUT or run.name == 'hf-cache':
            continue
        for p in run.rglob('*'):
            if p.is_file() and p.suffix in {'.json', '.jsonl', '.txt', '.md', '.yaml'} and p.stat().st_size < 5_000_000:
                history.append(p)
    for item in selection:
        hits = [str(p.relative_to(ROOT)) for p in history if item['sample_id'] in p.read_text(errors='replace')]
        if hits: item['ID_exposure'] = 'seen'; item['history_hits'] = hits[:8]
        family_hits = [str(p.relative_to(ROOT)) for p in history if item['family'] in p.read_text(errors='replace')]
        if family_hits: item['family_exposure'] = 'seen'; item['family_history_hits'] = family_hits[:8]
    write_json(OUT / 'units.private.json', units)
    write_json(OUT / 'gold.private.json', gold)
    write_json(OUT / 'selection.private.json', {'seed': cfg['selection_seed'], 'rule': 'synthetic-train only; 30 IDs, 10 per L1/L2/L3; old16+12 family-disjoint; 3 L1 clean then rare-label inverse-frequency priority, family balance tiebreak, seeded ties',
                'pool': len(pool), 'clean_by_level': dict(Counter(u['level'] for u,g in zip(units,gold) if not g['taxonomy_error'])), 'cases': selection})
    write_json(OUT / 'label-space.private.json', read(raw_root / 'label_space.json'))
    write_json(OUT / 'requested-levels.private.json', {u['sample_id']:u['level'] for u in units})
    review = OUT / 'review'; review.mkdir(exist_ok=True)
    # All cases are source-only here: no annotations or teacher feedback.
    packet = {'policy': 'Read source/statement statically before any predictions/gold. Do not execute student code or read other experiment files. Record short independent source-grounded defects, labels and uncertainty; no speculation from compile/test status. SINGLE is adapter ID for a single problem. Label boundaries may be disputed. Compiler unavailable/tests not_run. This is synthetic internal train.',
              'labels': read(OUT / 'label-space.private.json')['taxonomy_error'], 'cases': units}
    write_json(review / 'source-packet.private.json', packet)
    write_json(review / 'source-schema.private.json', {'reviewer': 'name', 'cases': [{'sample_id':'ID', 'source_taxonomy':[], 'findings':[{'problem_id':'SINGLE or Pn','location':'...', 'evidence':'exact short source quote','error':'defect and consequence','label':'official label','repair':'feasible direction'}], 'source_disputed':False,'main_error':'description or none','clean_basis':'scope of correctness or empty','disputes':[]}]})
    seal_files(OUT, 'selection-seal.json', ['units.private.json','gold.private.json','selection.private.json','label-space.private.json','requested-levels.private.json','review/source-packet.private.json','review/source-schema.private.json'])
    write_json(OUT/'prepared-binding-audit.private.json', {'checked':len(units),'all_task_fields_match_archive_verified_raw':True,'selection_seal_sha256':sha(OUT/'selection-seal.json')})
    # Preserve pre-existing tracked content and historical output artifacts; omit model cache/weights.
    paths = subprocess.check_output(['git','ls-files'], cwd=ROOT, text=True).splitlines()
    paths += [str(p.relative_to(ROOT)) for run in (ROOT/'outputs/task3').iterdir() if run.is_dir() and run != OUT and run.name != 'hf-cache'
              for p in run.rglob('*') if p.is_file() and p.suffix not in {'.safetensors','.bin','.pt'}]
    write_json(OUT/'preservation.private.json', {p:sha(ROOT/p) for p in sorted(set(paths))})
    print(json.dumps({'selected':len(units),'levels':dict(quota),'families':dict(families),'support':dict(used),'selection_seal_sha256':sha(OUT/'selection-seal.json')}))


def freeze():
    verify_seal(OUT, 'selection-seal.json')
    require(not (OUT / 'frozen').exists(), 'one candidate only')
    require((OUT/'review/source-seal.json').exists(), 'source references must be sealed before model outputs')
    verify_seal(OUT/'review', 'source-seal.json')
    cfg = read(ROOT / CONFIG); r15 = load_config(ROOT/'configs/task3/r15_selected.yaml'); old = read(ROOT/'configs/task3/two_pass_20261023.json')
    for k in ('model_id','revision','load_in_4bit','seed','do_sample','max_new_tokens','context_limit','generation_max_time_s'):
        require(cfg[k] == r15[k] == old[k], 'runtime mismatch: '+k)
    os.environ.update(HF_HOME=str(ROOT/'outputs/task3/hf-cache'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    from src.task3.inference import load_tokenizer, tokenizer_metadata
    tok = load_tokenizer(cfg)
    frozen=OUT/'frozen';frozen.mkdir()
    for name in FILES:
        p=frozen/'code'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/name).read_bytes())
    inputs=['selection-seal.json','review/source-seal.json','preservation.private.json','prepared-binding-audit.private.json']
    write_json(frozen/'freeze.json', {'config':cfg,'R15_config':r15,'C_old_config':old,'tokenizer':tokenizer_metadata(tok),
        'initial_HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'code_sha256':{p:sha(ROOT/p) for p in FILES},'input_sha256':{p:sha(OUT/p)for p in inputs},
        'prompt_sha256':digest([new.FINDINGS_SYSTEM,new.FEEDBACK_SYSTEM,new.GUIDANCE]),'label_space_sha256':sha(OUT/'label-space.private.json')})
    (frozen/'freeze.sha256').write_text(sha(frozen/'freeze.json')+'\n')
    print(json.dumps({'frozen':sha(frozen/'freeze.json')}))


def verify():
    frozen=OUT/'frozen';m=read(frozen/'freeze.json')
    require(sha(frozen/'freeze.json')==(frozen/'freeze.sha256').read_text().strip(),'freeze drift')
    verify_seal(OUT,'selection-seal.json');verify_seal(OUT/'review','source-seal.json')
    for p,h in m['code_sha256'].items():require(sha(ROOT/p)==h,'runtime code drift: '+p)
    for p,h in m['input_sha256'].items():require(sha(OUT/p)==h,'frozen input drift: '+p)
    return m


def run():
    m=verify();require(not (OUT/'run.private.json').exists(),'completed experiment cannot resample')
    cfg=m['config'];os.environ.update(HF_HOME=str(ROOT/'outputs/task3/hf-cache'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    free=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip().splitlines()
    require(len(free)==1 and int(free[0])>=cfg['minimum_free_gpu_mib'],'insufficient GPU memory')
    from src.task3.inference import load_tokenizer,tokenizer_metadata,HFBackend
    from src.task3 import round15_runner, c_feedback_v3
    tok=load_tokenizer(cfg);require(tokenizer_metadata(tok)==m['tokenizer'],'tokenizer drift')
    backend=HFBackend(cfg,tok);backend.model.generation_config.max_time=cfg['generation_max_time_s']
    write_json(OUT/'runtime-before.private.json',backend.runtime_metadata())
    units=read(OUT/'units.private.json');space=read(OUT/'label-space.private.json')
    records=[SimpleNamespace(sample_id=u['sample_id'],statement=u['task']['statement'],problems=u['task']['problems'],
                grading_policy=u['task']['grading_policy'],code=u['task']['code'],target_feedback_level=space['feedback_level'][u['level']-1]['level'],
                provenance={'_task3_compile_check':u['task']['compiler']})for u in units]
    a=round15_runner.run_records(records,backend,m['R15_config'],OUT/'A')
    ar=[{'sample_id':u['sample_id'],'status':'resolved'if u['sample_id']not in a['errors']else'unresolved',
         'output':next((p['output']for p in a['predictions']if p['sample_id']==u['sample_id']),None)}for u in units]
    write_json(OUT/'A/results.private.json',ar)
    c_feedback_v3.run_units(units,backend,m['C_old_config'],OUT/'C-old',space['feedback_level'],renderer='old')
    rows=new.run_units(units,backend,cfg,OUT/'C',space)
    # Pure structural projection; renderer receives unchanged error text and labels.
    replay={r['sample_id']:renderer_adapter(r['stage1'])if r['stage1']is not None else None for r in rows}
    write_json(OUT/'ablation-replay.private.json',replay)
    c_feedback_v3.run_units(units,backend,m['C_old_config'],OUT/'renderer-ablation',space['feedback_level'],renderer='old',replay=replay)
    verify()
    write_json(OUT/'run.private.json',{'model_loads':1,'runtime':backend.runtime_metadata(),'new_arm_fallback':0,
        'new_arm_completed':sum(r['status']=='resolved'for r in rows),'new_arm_unresolved':sum(r['status']!='resolved'for r in rows),
        'freeze_sha256':sha(OUT/'frozen/freeze.json'),'ablation':'renderer replay, not end-to-end'})
    print(json.dumps(read(OUT/'run.private.json')))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['select','freeze','verify','run','packets','score','preserve'])
    parser.add_argument('--out',type=Path,default=OUT)
    args=parser.parse_args();OUT=args.out.resolve()
    if args.phase in ['packets','score']:
        from scripts import task3_two_pass_findings_report as report
        getattr(report,args.phase)(OUT)
    elif args.phase=='preserve':
        drift=[p for p,h in read(OUT/'preservation.private.json').items()if not(ROOT/p).exists()or sha(ROOT/p)!=h]
        require(not drift,'pre-existing artifacts changed: '+str(drift));print(json.dumps({'preserved':len(read(OUT/'preservation.private.json'))}))
    elif args.phase=='verify':verify();print('{"verified":true}')
    else:globals()[args.phase]()
