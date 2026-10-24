#!/usr/bin/env python3
"""Private internal 2×2 experiment. No public data, submissions, retries or repairs."""
from __future__ import annotations
import argparse
from collections import Counter
import gc
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.task3 import language_precision_ablation as lp
from src.task3 import two_pass_findings as v1
from src.task3.dataset import write_json, load_task3
from src.task3.level_blind import read, sha, digest
from src.task3.inference import load_tokenizer, tokenizer_metadata
from src.task3.grounded_metrics import taxonomy_metrics
from src.task3.submission import validate_submission
from src.task3.two_pass import append
from scripts.task3_two_pass_findings import verify_seal, seal_files
OLD=ROOT/'outputs/task3/two-pass-findings-v1-20261023'
OUT=ROOT/'outputs/task3/language-precision-ablation-20261024'
OUTER='8c04e4e01be73952cb255fb5efd707c758205c19457fa651d944fc02780a3e1e'
NESTED='88eff95f2841efd061ab0203907f9142ad6a2a2b72e266a4d55043a50aedac9c'


def require(ok,reason):
    if not ok: raise ValueError(reason)


def environment():
    import torch
    free,total=torch.cuda.mem_get_info()
    return {'packages':{p:importlib.metadata.version(p) for p in ['torch','transformers','tokenizers','bitsandbytes','accelerate']},
            'cuda':torch.version.cuda,'cudnn':torch.backends.cudnn.version(),
            'gpu':torch.cuda.get_device_name(),'total_gpu_bytes':total,'free_gpu_bytes':free,
            'bf16_supported':torch.cuda.is_bf16_supported(),
            'tf32_matmul':torch.backends.cuda.matmul.allow_tf32,'tf32_cudnn':torch.backends.cudnn.allow_tf32,
            'float32_matmul_precision':torch.get_float32_matmul_precision(),
            'cudnn_benchmark':torch.backends.cudnn.benchmark,'cudnn_deterministic':torch.backends.cudnn.deterministic,
            'deterministic_algorithms':torch.are_deterministic_algorithms_enabled(),
            'sdpa_flash':torch.backends.cuda.flash_sdp_enabled(),'sdpa_mem_efficient':torch.backends.cuda.mem_efficient_sdp_enabled(),
            'sdpa_math':torch.backends.cuda.math_sdp_enabled(),
            'nvidia_smi':subprocess.check_output(['nvidia-smi'],text=True)}


def prepare(out):
    require(not out.exists(),'new output directory required')
    verify_seal(OLD,'selection-seal.json');verify_seal(OLD/'review','source-seal.json')
    units=read(OLD/'units.private.json');gold=read(OLD/'gold.private.json');selection=read(OLD/'selection.private.json')['cases']
    require(len(units)==30 and len({u['sample_id']for u in units})==30,'locked30 distinct IDs required')
    require(len({u['provenance']['code_sha256']for u in units})==27,'expected27 code hashes')
    raw={r.sample_id:r for r in load_task3(ROOT/'data/synth/generate-dataset','synthetic')}
    gold_by={r['sample_id']:r['taxonomy_error']for r in gold};sel={r['sample_id']:r for r in selection}
    archive=ROOT/'data-20261017T044357Z-1-001.zip';require(sha(archive)==OUTER,'wrong outer archive')
    with zipfile.ZipFile(archive)as z: nested=z.read('data/generate-dataset.zip')
    require(hashlib.sha256(nested).hexdigest()==NESTED,'wrong nested archive')
    with zipfile.ZipFile(io.BytesIO(nested))as z:
        for name in ['exams.json','task3_feedback.json','label_space.json']:
            require(z.read('generate-dataset/'+name)==(ROOT/'data/synth/generate-dataset'/name).read_bytes(),'archive metadata mismatch')
        for u in units:
            sid=u['sample_id'];r=raw[sid];p=u['provenance'];task=u['task']
            require(r.code==task['code'] and r.statement==task['statement'] and r.problems==task['problems'] and r.grading_policy==task['grading_policy'] and r.exam_type==task['exam_type'],'task provenance mismatch '+sid)
            require(r.gold_taxonomy==gold_by[sid] and int(r.target_feedback_level[6])==u['level'] and r.exam_id==u['family'],'gold/Level/family mismatch '+sid)
            code=z.read('generate-dataset/'+sel[sid]['code_path'])
            require(code==Path(r.code_path).read_bytes() and hashlib.sha256(code).hexdigest()==p['code_sha256'],'source archive hash mismatch '+sid)
            require(p['archive_sha256']==OUTER and p['nested_archive_sha256']==NESTED,'archive binding mismatch')
            require(digest({k:task[k]for k in ['statement','problems','grading_policy','exam_type']})==p['exam_sha256'],'semantic exam hash mismatch')
            require(task['compiler']=={'status':'unavailable','diagnostic':''} and task['tests']=={'status':'not_run','cases':[]},'old evidence required')
            require(digest([task['compiler'],task['tests']])==p['evidence_sha256'],'evidence hash mismatch')
    out.mkdir(parents=True)
    for name in ['units.private.json','gold.private.json','label-space.private.json','requested-levels.private.json']:
        shutil.copyfile(OLD/name,out/name)
    (out/'review').mkdir()
    for name in ['source-a.private.json','source-b.private.json','source-packet.private.json','source-schema.private.json','source-seal.json']:
        shutil.copyfile(OLD/'review'/name,out/'review'/name)
    write_json(out/'manifest.private.json',[{'sample_id':u['sample_id'],'family':u['family'],'requested_level':u['level'],**u['provenance'],'exposure':'seen internal development; not holdout'}for u in units])
    write_json(out/'historical-preservation.private.json',{str(p.relative_to(OLD)):sha(p)for p in OLD.rglob('*')if p.is_file()})
    seed=lp.arm_config('A')['review_seed'];rng=random.Random(seed)
    subset=[]
    for level in [1,2,3]:
        ids=[u['sample_id']for u in units if u['level']==level];rng.shuffle(ids);subset+=ids[:4]
    write_json(out/'review/second-review-subset.private.json',{'seed':seed,'selected_before_new_outputs':True,'sample_ids':subset,'all_material_disputes_additionally_required':True})
    write_json(out/'provenance-audit.private.json',{'IDs':30,'code_hashes':27,'outer_sha256':OUTER,'nested_sha256':NESTED,'archive_metadata_source_gold_Level_verified':True,'historical_selection_seal_sha256':sha(OLD/'selection-seal.json'),'historical_source_seal_sha256':sha(OLD/'review/source-seal.json'),'gold_clean_levels':dict(Counter(u['level']for u in units if not gold_by[u['sample_id']]))})
    print('Prepared30 IDs,27 code hashes; complete archive/source/gold/Level binding verified.')


def offline():
    os.environ.update(HF_HOME=str(ROOT/'outputs/task3/hf-cache'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')


def freeze(out):
    require(not(out/'freeze.json').exists(),'freeze already exists')
    offline();tok=load_tokenizer(lp.arm_config('A'))
    require(tokenizer_metadata(tok)==read(OLD/'frozen/freeze.json')['tokenizer'],'historical tokenizer mismatch')
    frozen=out/'frozen';frozen.mkdir()
    prompts={lang:lp.bundle(lang)for lang in ['vi','en']}
    write_json(out/'prompts.json',prompts)
    # Paragraph-level alignment preserves order; each Level guidance is a separate paired row.
    alignment=[]
    for stage in ['findings','feedback']:
        vi=prompts['vi'][stage].splitlines();en=prompts['en'][stage].splitlines()
        require(len(vi)==len(en),'translation paragraph count mismatch')
        alignment += [{'section':stage,'paragraph':i+1,'vi':v,'en':e,'review':'same ordered requirements; prose-only translation'}for i,(v,e)in enumerate(zip(vi,en))]
    alignment += [{'section':'guidance','Level':i,'vi':prompts['vi']['guidance'][i],'en':prompts['en']['guidance'][i],'review':'same Level boundary'}for i in [1,2,3,4]]
    write_json(out/'translation-alignment.json',alignment)
    configs={a:lp.arm_config(a)for a in lp.ARMS};write_json(out/'configs.json',configs)
    deps=environment();write_json(out/'environment-freeze.json',deps)
    files=sorted([str(p.relative_to(ROOT))for p in (ROOT/'src').rglob('*.py')]+['scripts/task3_language_precision_ablation.py','scripts/task3_two_pass_findings.py','configs/task3/language_precision_ablation_v1.json','configs/task3/two_pass_findings_v1_20261023.json','tests/test_task3_language_precision_ablation.py'])
    for name in files:
        target=frozen/'code'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    inputs=['units.private.json','gold.private.json','label-space.private.json','requested-levels.private.json','manifest.private.json','historical-preservation.private.json','provenance-audit.private.json','prompts.json','translation-alignment.json','configs.json','environment-freeze.json']+[str(p.relative_to(out))for p in (out/'review').glob('*.json')]
    tokenbytes=tok.backend_tokenizer.to_str().encode()
    write_json(out/'freeze.json',{'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'code_sha256':{p:sha(ROOT/p)for p in files},'inputs_sha256':{p:sha(out/p)for p in inputs},'tokenizer':tokenizer_metadata(tok),'tokenizer_full_sha256':hashlib.sha256(tokenbytes).hexdigest(),'config':configs,'order':'arm-major A30 then B30; release NF4; C30 then D30','planned_loads':2,'main_max_calls':240,'extra_model_calls':0,'patch':subprocess.check_output(['git','diff','HEAD'],cwd=ROOT,text=True)})
    (out/'freeze.sha256').write_text(sha(out/'freeze.json')+'\n')
    print('FROZEN '+sha(out/'freeze.json'))


def verify(out):
    m=read(out/'freeze.json');require(sha(out/'freeze.json')==(out/'freeze.sha256').read_text().strip(),'freeze changed')
    for name,h in m['code_sha256'].items():require(sha(ROOT/name)==h,'code drift '+name)
    for name,h in m['inputs_sha256'].items():require(sha(out/name)==h,'input drift '+name)
    return m


def run(out):
    m=verify(out);require(not(out/'run.json').exists(),'completed run cannot resample')
    offline();tok=load_tokenizer(lp.arm_config('A'))
    require(tokenizer_metadata(tok)==m['tokenizer'] and hashlib.sha256(tok.backend_tokenizer.to_str().encode()).hexdigest()==m['tokenizer_full_sha256'],'tokenizer drift')
    units=read(out/'units.private.json');space=read(out/'label-space.private.json');started=time.perf_counter()
    runinfo={'loads':[],'extra_model_calls':0,'warmup_calls':0,'freeze_sha256':sha(out/'freeze.json')}
    for group in ['AB','CD']:
        cfg=lp.arm_config(group[0]);before=environment()
        frozen=read(out/'environment-freeze.json')
        require(all(before[k]==frozen[k]for k in frozen if k not in ['free_gpu_bytes','nvidia_smi']),'dependency/backend drift')
        require(before['bf16_supported'],'native BF16 required for all arms')
        load_dir=out/('NF4'if cfg['load_in_4bit']else'BF16');load_dir.mkdir(exist_ok=True)
        write_json(load_dir/'preflight.json',before)
        if not cfg['load_in_4bit'] and before['free_gpu_bytes']<20*1024**3:
            write_json(out/'blocked.json',{'reason':'BF16 chưa chạy được trên tài nguyên hiện tại','free_bytes':before['free_gpu_bytes']});break
        append(out/'model-loads.jsonl',{'group':group,'time_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'kind':'original checkpoint','precision':'nf4'if cfg['load_in_4bit']else'bf16'})
        try:backend=lp.AuditedBackend(cfg,tok,load_dir)
        except RuntimeError as exc:
            write_json(out/'blocked.json',{'reason':'BF16 chưa chạy được trên tài nguyên hiện tại'if group=='CD'else'NF4 load failed','error':str(exc)});break
        write_json(load_dir/'runtime-before.json',backend.runtime_metadata())
        for a in group:
            armout=out/a;armout.mkdir(exist_ok=True);cfg=lp.arm_config(a)
            cfg['freeze_sha256']=sha(out/'freeze.json');write_json(armout/'config.json',cfg)
            for stage in ['taxonomy','feedback']:shutil.copyfile(load_dir/f'generation-{stage}.json',armout/f'generation-{stage}.json')
            write_json(armout/'runtime-before.json',backend.runtime_metadata())
            lp.run_arm(units,backend,cfg,armout,space)
            write_json(armout/'runtime-after.json',backend.runtime_metadata())
        runinfo['loads'].append({'group':group,**backend.runtime_metadata()})
        write_json(load_dir/'runtime-after.json',backend.runtime_metadata())
        del backend;gc.collect()
        import torch
        torch.cuda.empty_cache();torch.cuda.synchronize()
    verify(out);runinfo['wall_time_s']=time.perf_counter()-started
    write_json(out/'run.json',runinfo)


def packets(out):
    verify(out);review=out/'review';require(not(review/'packet.private.json').exists(),'one packet only')
    rng=random.Random(lp.arm_config('A')['review_seed']);key={};cases=[]
    for u in read(out/'units.private.json'):
        order=list(lp.ARMS);rng.shuffle(order);outputs=[]
        for a in order:
            rows=read(out/a/'results.private.json')if(out/a/'results.private.json').exists()else[]
            r=next((r for r in rows if r['sample_id']==u['sample_id']),{'status':'unresolved','stage1':None,'output':None,'failure':{'stage':'load','reason':'not_run'}})
            oid=f'{rng.getrandbits(96):024x}';key[oid]={'sample_id':u['sample_id'],'arm':a}
            outputs.append({'output_id':oid,**{k:r.get(k)for k in ['status','stage1','output','failure']}})
        cases.append({'sample_id':u['sample_id'],'level':u['level'],'task':u['task'],'outputs':outputs})
    # Reuse historical explicit rubric, add finding attribution required by this spec.
    from scripts.task3_two_pass_findings_report import GOOD,BAD,SPECIAL
    rubric=read(OLD/'review/packet.private.json')['rubric']
    write_json(review/'packet.private.json',{'policy':'Blinded arm/precision/prompt language. Read sealed source-a/source-b first. No gold/key/raw or new model calls. Inspect each finding, its evidence and label, match reference inventory, then review feedback factuality, faithfulness, inherited/new claims, requested Level and voice. Preserve conditional domain/capacity/style/label disputes. Finding prose cannot be fully blinded. Unresolved has no output credit.','rubric':rubric,'official_levels':read(out/'label-space.private.json')['feedback_level'],'cases':cases})
    write_json(review/'key.private.json',key)
    seal_files(review,'packet-seal.json',['packet.private.json','key.private.json'])
    print('Blinded120 output slots prepared.')


def arm_metrics(rows,gold,path):
    require(len(rows)==len(gold) and {r['sample_id']for r in rows}==set(gold),'full denominator required')
    def tax(stage1=False):
        pred=[(r.get('stage1')or{}).get('taxonomy_error')if stage1 else (r.get('output')or{}).get('taxonomy_error')for r in rows]
        result=taxonomy_metrics([gold[r['sample_id']]for r in rows],pred)
        for item in [result,*result['per_label'].values()]:
            tp,fp,fn=item['TP'],item['FP'],item['FN'];item.update(precision=tp/(tp+fp)if tp+fp else 0,recall=tp/(tp+fn)if tp+fn else 0)
        return result
    attempts=[json.loads(s)for s in (path/'attempts.jsonl').read_text().splitlines()]if(path/'attempts.jsonl').exists()else[]
    reserves=[json.loads(s)for s in(path/'reservations.jsonl').read_text().splitlines()]if(path/'reservations.jsonl').exists()else[]
    return {'samples':len(rows),'completed':sum(r['status']=='resolved'for r in rows),'unresolved':sum(r['status']!='resolved'for r in rows),'retry':0,'fallback':0,
            'taxonomy':tax(),'stage1_taxonomy':tax(True),'failure_reasons':dict(Counter((r.get('failure')or{}).get('reason')for r in rows if r.get('failure'))),
            'failure_stages':dict(Counter((r.get('failure')or{}).get('stage')for r in rows if r.get('failure'))),
            'cost':{'fresh_calls':len(attempts),'reservations':len(reserves),'reserved_without_response':len({r['key']for r in reserves}-{r['key']for r in attempts}),'calls_skipped':2*len(rows)-len(attempts),
                    **{k:sum(r.get(k)or 0 for r in attempts)for k in ['input_tokens','output_tokens','latency_s']},
                    'by_stage':{s:{'calls':sum(r['stage']==s for r in attempts),**{k:sum(r.get(k)or 0 for r in attempts if r['stage']==s)for k in ['input_tokens','output_tokens','latency_s']}}for s in ['taxonomy','feedback']}},
            'empty_findings_IDs':sum(r.get('stage1')is not None and r['stage1']['findings']==[]for r in rows),
            'literal_placeholder_by_level':{str(i):sum((r.get('output')or{}).get('feedback','').strip()=='Chương trình cần được kiểm tra lại.'for r in rows if r['level']==i)for i in [1,2,3]}if all('level'in r for r in rows)else{}}


def report(out):
    verify(out);units=read(out/'units.private.json');gold={r['sample_id']:r['taxonomy_error']for r in read(out/'gold.private.json')}
    metrics={'samples':len(units),'unique_code_hashes':len({u['provenance']['code_sha256']for u in units}),'data_role':'seen internal development, not holdout','unresolved_policy':'None is empty for F1 TP/FP/FN; unresolved fails exact/joint, never fake output','zero_division':0,'arms':{},'run':read(out/'run.json')}
    validation={}
    for a in lp.ARMS:
        path=out/a
        rows=read(path/'results.private.json')if(path/'results.private.json').exists()else[{'sample_id':u['sample_id'],'level':u['level'],'status':'unresolved','stage1':None,'output':None,'failure':{'stage':'load','reason':'not_run'}}for u in units]
        write_json(path/'status.private.json',rows)
        metrics['arms'][a]=arm_metrics(rows,gold,path)
        complete={r['sample_id']for r in rows if r['status']=='resolved'}
        levels={u['sample_id']:v1.FEEDBACK_LEVELS[u['level']-1]for u in units if u['sample_id']in complete}
        if complete:
            validate_submission(path/'completed.predictions.json',levels)
            validation[a]={'scope':'full'if len(complete)==30 else'completed-subset','records':len(complete),'valid':True}
        else:validation[a]={'scope':'empty','records':0,'valid':False}
        if len(complete)<30:require(not(path/'predictions.json').exists(),'partial predictions cannot be full')
    write_json(out/'validation.private.json',validation);write_json(out/'metrics.private.json',metrics)
    print(json.dumps({a:{k:m[k]for k in ['completed','unresolved','empty_findings_IDs']}for a,m in metrics['arms'].items()}))


def preserve(out):
    verify(out)
    for name,h in read(out/'historical-preservation.private.json').items():require(sha(OLD/name)==h,'historical artifact changed '+name)
    print('All historical artifact hashes preserved.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['prepare','freeze','verify','run','packets','report','preserve']);p.add_argument('--out',type=Path,default=OUT);args=p.parse_args()
    globals()[args.phase](args.out.resolve())
