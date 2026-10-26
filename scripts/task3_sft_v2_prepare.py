"""Export/freeze SFT v2 without model weights or generation."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from src.task3.sft_v1 import sha256,read_jsonl,native_prompt,verify_checksums,encode_examples
from src.task3.sft_v1_experiment import write_json,smoke_ids
from src.task3.sft_v2 import load_split,CALL_BUDGET,SELECTION_POLICY


def write_jsonl(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in rows))


def overlap_screen(old,new):
    from src.task3.eval_snapshot import structural_shingles
    corpus={};read_files=[];skipped=[]
    def add(code,origin):
        if isinstance(code,str) and code.strip():
            key=hashlib.sha256(code.encode()).hexdigest()
            if key not in corpus: corpus[key]=dict(code=code,origin=origin)
    def nested(obj,origin):
        if isinstance(obj,dict):
            for k,v in obj.items():
                if (k in ('code','source_code','student_code','solution','source') and isinstance(v,str) and
                    ('#include' in v or 'int main' in v or 'std::' in v)): add(v,origin+':'+k)
                elif isinstance(v,(dict,list)): nested(v,origin)
        elif isinstance(obj,list):
            for v in obj: nested(v,origin)
    for case in old:
        code=(REPO/'data/raw/task3-sft-v1'/case['code_file']).read_text()
        add(code,'v1:'+case['split']+':'+case['sample_id'])
    roots=[Path('/workspace/llm-final-project/data'),REPO/'data',
           Path('/workspace/llm-final-project-ablation/data')]
    for root in roots:
        if not root.exists(): continue
        for p in root.rglob('*'):
            if not p.is_file() or 'task3-sft-v2' in str(p) or p.suffix.lower() not in ('.cpp','.cc','.cxx','.json','.jsonl','.zip'): continue
            try:
                if p.suffix in ('.cpp','.cc','.cxx'): add(p.read_text(errors='replace'),str(p))
                elif p.suffix in ('.json','.jsonl'):
                    if p.stat().st_size>64<<20: skipped.append(dict(path=str(p),reason='over64MiB'));continue
                    text=p.read_text(errors='replace')
                    objects=[json.loads(line) for line in text.splitlines() if line.strip()] if p.suffix=='.jsonl' else [json.loads(text)]
                    for obj in objects:nested(obj,str(p))
                else: continue
                read_files.append(str(p))
            except (ValueError,OSError) as e: skipped.append(dict(path=str(p),reason=str(e)))
    # Historical source catalogues include real internal data not retained under data/.
    for name in ('inventory.json','source-inventory.private.json','original-data-inventory.private.json'):
        p=REPO/'outputs/task3/r15-abc-20261025'/name
        if p.exists():nested(json.loads(p.read_text()),str(p));read_files.append(str(p))
    archives=list(Path('/workspace').glob('*.zip'))
    archives += [p for root in roots if root.exists() for p in root.rglob('*.zip')]
    for p in sorted(set(archives)):
        if 'task3-sft-v1' in p.name or 'audit.private' in p.name or 'partial' in p.name:continue
        with zipfile.ZipFile(p) as z:
            for member in z.infolist():
                if member.file_size>4<<20:continue
                if Path(member.filename).suffix.lower() in ('.cpp','.cc','.cxx'):
                    add(z.read(member).decode(errors='replace'),str(p)+':'+member.filename)
        read_files.append(str(p))
    values=list(corpus.values())
    for v in values:
        v['normalized']=''.join(v['code'].split());v['shingles']=structural_shingles(v['code'])
    results=[]
    for c in new:
        sh=structural_shingles(c['code']);norm=''.join(c['code'].split())
        # New final also screens against every newly authored training source.
        pool=values+[dict(code=x['code'],origin='v2-new-train:'+x['sample_id'],normalized=''.join(x['code'].split()),
                         shingles=structural_shingles(x['code'])) for x in new if x['split']=='train'] if c['split']=='final' else values
        scores=[];exact=[]
        for v in pool:
            if c['code']==v['code'] or norm==v['normalized']:exact.append(v['origin'])
            score=len(sh&v['shingles'])/max(1,len(sh|v['shingles']))
            scores.append((score,v['origin']))
        results.append(dict(sample_id=c['sample_id'],split=c['split'],exact_or_whitespace_matches=exact,
            nearest=[dict(similarity=s,origin=o) for s,o in sorted(scores,reverse=True)[:5]]))
    return dict(method='exact bytes + whitespace removal + identifier-erased five-token shingle Jaccard',
        threshold_for_review=.85,unique_existing_sources=len(values),read_files=read_files,skipped=skipped,
        results=results,limitations='Lexical/structural and author family review cannot prove semantic independence; common IO/container idioms remain. Existing disclosed v1 cross-split similarities are unchanged.')


def export(out):
    oldroot=REPO/'data/raw/task3-sft-v1';author=REPO/'data/raw/task3-sft-v2-authoring'
    verify_checksums(oldroot)
    train=json.loads((author/'train-new.private.json').read_text());final=json.loads((author/'final-new.private.json').read_text())
    audit=json.loads((author/'original-target-audit.private.json').read_text())
    if len(train)!=80 or len(final)!=40:raise ValueError('new source counts')
    if sum(not c['intended_defective'] for c in train)!=40 or sum(not c['intended_defective'] for c in final)!=20:raise ValueError('balance')
    for name in ('train','final'):
        if not json.loads((author/f'{name}-verification/summary.json').read_text())['passed']:raise ValueError('authoring checks failed')
    root=REPO/'data/raw/task3-sft-v2'
    if root.exists():raise FileExistsError('v2 export already exists; no overwrite')
    root.mkdir();(root/'sources').mkdir()
    for name in ('SYSTEM_PROMPT.txt','label_space.json'):shutil.copyfile(oldroot/name,root/name)
    labels=json.loads((root/'label_space.json').read_text())['taxonomy_error']
    parts=json.loads((oldroot/'split-manifest.json').read_text())['partitions'];parts['final']=[]
    oldcases=json.loads((oldroot/'cases.private.json').read_text())
    changes={(x['source_id'],int(x['level'])):x for x in audit['changes']}
    if len(changes)!=len(audit['changes']):raise ValueError('duplicate target changes')
    for c in oldcases:shutil.copyfile(oldroot/c['code_file'],root/c['code_file'])
    for split in ('train','dev','test'):
        records=read_jsonl(oldroot/f'{split}.records.jsonl')
        for r in records:
            change=changes.get((r['source_id'],r['input']['target_feedback_level']))
            if change:
                if split!='train' or r['output']!=change['original']:raise ValueError('annotation ledger binding')
                r['output']=change['revised']
        if split in ('dev','test'):
            for suffix in ('records.jsonl','sft.jsonl'):shutil.copyfile(oldroot/f'{split}.{suffix}',root/f'{split}.{suffix}')
        else:
            write_jsonl(root/f'{split}.records.jsonl',records)
            write_jsonl(root/f'{split}.sft.jsonl',[dict(prompt=native_prompt(root,r['input'],labels),
                completion=[dict(role='assistant',content=json.dumps(r['output'],ensure_ascii=False))]) for r in records])
    allnew=train+final;cases=oldcases.copy()
    for case in cases:
        if case['split']!='train':continue
        for level in range(1,5):
            change=changes.get((case['sample_id'],level))
            if change:
                if case['targets'][str(level)]!=change['original']:raise ValueError('case annotation ledger binding')
                case['targets'][str(level)]=change['revised']
                if 'feedback_prose' in case:case['feedback_prose'][str(level)]=change['revised']['feedback'].split('```')[0].rstrip()
                case['annotation_version']='v2.0'
    for split,items in [('train',train),('final',final)]:
        records=read_jsonl(root/f'{split}.records.jsonl') if split=='train' else []
        sft=read_jsonl(root/f'{split}.sft.jsonl') if split=='train' else []
        evidence=json.loads((author/f'{split}-verification/execution.private.json').read_text())
        for c in items:
            sid=c['sample_id'];source=root/'sources'/f'{sid}.cpp';source.write_text(c['code'])
            syntax=evidence[sid]['syntax_only'];log=syntax['stderr']
            # No linker/runtime/witness fields enter native input.
            parts[split].append(dict(source_id=sid,family_id=c['family_id'],cluster=c['cluster'],source_sha256=sha256(source)))
            cases.append(dict(c,code_file=f'sources/{sid}.cpp',source_sha256=sha256(source)))
            for level in range(1,5):
                x=dict(statement=c['statement'],exam_type=c['exam_type'],language='cpp11',code=c['code'],compile_log=log,target_feedback_level=level)
                output=c['targets'][str(level)]
                records.append(dict(sample_id=f'{sid}-L{level}',source_id=sid,family_id=c['family_id'],group_id=c['cluster'],split=split,input=x,output=output))
                sft.append(dict(prompt=native_prompt(root,x,labels),completion=[dict(role='assistant',content=json.dumps(output,ensure_ascii=False))]))
        write_jsonl(root/f'{split}.records.jsonl',records);write_jsonl(root/f'{split}.sft.jsonl',sft)
    write_json(root/'split-manifest.json',dict(partitions=parts,policy='Family/cluster/source fixed; original dev unchanged, old test observed regression, final synthetic frozen before any generation.'))
    write_json(root/'cases.private.json',cases)
    write_json(root/'target-changes.private.json',audit)
    overlap=overlap_screen(oldcases,allnew);write_json(root/'overlap.private.json',overlap)
    if any(r['exact_or_whitespace_matches'] for r in overlap['results']):raise ValueError('new source duplicate existing data')
    # Persist authoring evidence without sandbox files.
    for p in author.rglob('*.json'):
        if 'jails' not in p.parts:
            target=root/'authoring'/p.relative_to(author);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    for split,count in [('train',960),('dev',80),('test',80),('final',160)]:
        if len(load_split(root,split))!=count:raise ValueError('split loader count')
    write_json(root/'dataset-manifest.json',dict(version='task3-sft-v2.0',targets=dict(train=960,dev=80,test=80,final=160),
        sources=dict(train=240,dev=20,test=20,final=40),train_clean=95,train_faulty=145,
        old_dataset_manifest_sha256=sha256(oldroot/'SHA256SUMS'),target_changes=len(changes),
        new_final_status='synthetic agent authored/reviewed; not independent human gold',new_final_used_for_selection=False))
    files={str(p.relative_to(root)):sha256(p) for p in root.rglob('*') if p.is_file()}
    (root/'SHA256SUMS').write_text(''.join(f'{v}  {k}\n' for k,v in sorted(files.items())))
    write_json(out/'dataset-export.json',dict(root=str(root),checksum_manifest_sha256=sha256(root/'SHA256SUMS'),files=len(files),target_changes=len(changes)))
    return root


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True);export(args.out)
