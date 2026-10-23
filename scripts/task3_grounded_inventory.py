#!/usr/bin/env python3
"""Read-only corpus inventory and immutable selection; no public source analysis."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.task3.dataset import load_task3, write_json
from src.task3.schema import code_hash

DEFAULT = ROOT/'outputs/task3/grounded-20261023'
PARENT = ROOT/'outputs/task3/eval-freeze-v2-20261021/frozen'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def read(path): return json.loads(Path(path).read_bytes())


def duplicates(rows, key):
    by = defaultdict(list)
    for r in rows: by[r[key]].append(r['sample_id'])
    return [ids for ids in by.values() if len(ids)>1]


def archive_inventory(path, data=None, depth=0):
    data = Path(path).read_bytes() if data is None else data
    result = dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        result['members'] = len(z.namelist())
        result['docx'] = [n for n in z.namelist() if n.endswith('.docx')]
        result['task3'] = []
        for n in z.namelist():
            if n.endswith('/task3_feedback.json') and '__MACOSX' not in n:
                raw=z.read(n); value=json.loads(raw)
                result['task3'].append(dict(member=n,sha256=hashlib.sha256(raw).hexdigest(),
                                            records=len(value['samples'])))
        if depth<1:
            result['nested'] = [archive_inventory(str(path)+'!'+n,z.read(n),depth+1)
                                for n in z.namelist() if n.endswith('.zip')]
    return result


def protected_hashes():
    paths = {ROOT/p for p in subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()}
    for base in ['data','outputs/task3/round15','outputs/task3/direct-sft-v1-20261021',
                 'outputs/task3/submission-r15-20261020','outputs/task3/eval-freeze-v1-20261021',
                 'outputs/task3/eval-freeze-v2-20261021']:
        paths.update(p for p in (ROOT/base).rglob('*') if p.is_file())
    # Other experiments' seals/configs are protected without ingesting attempts.
    for p in (ROOT/'outputs/task3').glob('*/*'):
        if p.is_file() and any(s in p.name for s in ['freeze','manifest','seal','config']): paths.add(p)
    paths.update(ROOT.glob('*.zip'))
    if (ROOT/'predictions.json').exists(): paths.add(ROOT/'predictions.json')
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths) if p.is_file()}


def inventory(out):
    if out.exists(): raise ValueError('exclusive inventory directory already exists')
    out.mkdir(parents=True)
    write_json(out/'preservation.private.json',protected_hashes())
    datasets=[]
    for relative,source in [('data/raw/sample_dataset','real'),
                            ('data/synth/generate-dataset','synthetic'),
                            ('data/synth/generate-dataset/heldout','synthetic-heldout'),
                            ('data/raw/round18-new','synthetic'),
                            ('data/raw/round18-new/heldout','synthetic-heldout')]:
        base=ROOT/relative
        if not (base/'task3_feedback.json').exists(): continue
        records=load_task3(base,source)
        rows=[dict(sample_id=r.sample_id, family=r.exam_id, code_sha256=sha(r.code_path),
                   token_sha256=code_hash(r.code),renamed_sha256=code_hash(r.code,renamed=True))for r in records]
        datasets.append(dict(path=relative,records=len(rows),families=dict(Counter(r.exam_id for r in records)),
                             json_sha256=sha(base/'task3_feedback.json'),ids_and_hashes=rows,
                             duplicates={k:duplicates(rows,k) for k in ['sample_id','code_sha256','token_sha256','renamed_sha256']}))
    # Metadata only: never open public C++ or public attempts for development.
    p=ROOT/'data/raw/public_test_release/task3_feedback.json'; public=read(p)
    pubids=[x['sample_id'] for x in public['samples']]
    public_meta=dict(path=str(p.relative_to(ROOT)),sha256=sha(p),records=len(pubids),
                     duplicate_ids=len(pubids)-len(set(pubids)),
                     families=dict(Counter(x['input']['exam_id'] for x in public['samples'])),
                     taxonomy_in_input=any('taxonomy_error' in x['input'] for x in public['samples']),
                     inspected_fields='metadata/sample_id/exam_id/Level only; no public code opened')
    evalrows=[r for r in read(PARENT/'model-inputs.private.json') if r['kind']=='primary']
    train=read(PARENT/'train-eligible.private.json')
    if len(evalrows)!=60 or len(train)!=8: raise ValueError('parent counts changed')
    selection=dict(parent_sha256=sha(PARENT/'seal.json'),
                   parent_manifest_sha256=sha(ROOT/'reports/task3/TASK3_EVAL_V2_FREEZE_20261021.json'),
                   development=[dict(sample_id=r['sample_id'],family=r['family'],source_sha256=r['source_sha256']) for r in train],
                   evaluation=[dict(sample_id=r['sample_id'],request_id=r['request_id'],level=r['requested_level'],
                                    source_text_sha256=hashlib.sha256(r['task']['student_code'].encode()).hexdigest())for r in evalrows],
                   selection_policy='ALL parent primary requests and ALL parent eligible train; no output-based selection',
                   exposure='Prior source/template and prior experiment exposure. Prospective current-method freeze only; NOT blind.')
    archives=[archive_inventory(p)for p in sorted(ROOT.glob('*.zip'))]
    external=Path('/workspace/public-test-cham-diem-phan-hoi-files.zip')
    if external.exists(): archives.append(archive_inventory(external))
    write_json(out/'selection.private.json',selection)
    write_json(out/'inventory.private.json',dict(initial_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                    datasets=datasets,public_metadata=public_meta,archives=archives,
                    docx_original='unavailable; searched workspace, attachments and archive member lists; read DoAn-LLM-Challenge.docx.md',
                    protected_count=len(read(out/'preservation.private.json'))))
    write_json(out/'selection-seal.json',{n:sha(out/n)for n in ['inventory.private.json','selection.private.json','preservation.private.json']})
    print(json.dumps(dict(inventory=str(out),datasets=[dict(path=d['path'],records=d['records'])for d in datasets],
                          evaluation=len(evalrows),development=len(train),selection_sha256=sha(out/'selection.private.json')),ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=DEFAULT)
    inventory(p.parse_args().output.resolve())
