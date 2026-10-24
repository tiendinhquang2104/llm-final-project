#!/usr/bin/env python3
"""Bound offline qualitative ratings, paired contrasts and private evidence exports."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.task3.dataset import write_json
from src.task3.level_blind import read, sha
from scripts.task3_language_precision_ablation import OUT, verify, preserve, require, report as base_report
from scripts.task3_two_pass_findings import verify_seal, seal_files

GOOD=['factual','faithful','main_covered','level_ok','natural_role']
BAD=['addresses_ban','self_reference','meta','generic_placeholder','disputed']
SPECIAL=['l1_detail_leak','l2_repair_leak','l3_actionable']
COUNTS=['inherited_false_claims','new_false_claims','new_diagnoses']


def valid_indices(indices,n):
    return isinstance(indices,list) and len(indices)==len(set(indices)) and all(type(i)is int and 0<=i<n for i in indices)


def validate_rating(r,u,o,nrefs):
    require(r['output_id']==o['output_id'],'rating output identity mismatch')
    for k in GOOD+BAD+['main_detected']:require(type(r[k])is bool,'boolean required '+k)
    for k in SPECIAL:require(r[k]is None or type(r[k])is bool,'bool/null required '+k)
    require((r['l1_detail_leak']is not None)==(u['level']==1),'L1 applicability')
    require((r['l2_repair_leak']is not None)==(u['level']==2),'L2 applicability')
    require(u['level']==3 or r['l3_actionable']is None,'L3 applicability')
    for k in COUNTS:require(type(r[k])is int and r[k]>=0,'nonnegative claim count required')
    require(valid_indices(r['detected_reference_indices'],nrefs),'invalid reference indices')
    fs=(o.get('stage1')or{}).get('findings',[])
    if u['level']==3 and fs and o['output']is not None:require(type(r['l3_actionable'])is bool,'L3 actionability must be assessed')
    require(not(r['inherited_false_claims']or r['new_false_claims'])or not r['factual'],'false claims contradict factual pass')
    require(not r['new_diagnoses']or not r['faithful'],'new diagnosis contradicts faithfulness')
    require(len(r['findings'])==len(fs) and [f['index']for f in r['findings']]==list(range(len(fs))),'finding denominator/index mismatch')
    source='\n'.join(str(u['task'].get(k,''))for k in ['code','statement','grading_policy','problems'])
    for f in r['findings']:
        require(f['verdict']in ['correct','false','unsupported','disputed'],'unknown verdict')
        require(type(f['label_correct'])is bool and valid_indices(f['reference_indices'],nrefs),'finding label/reference type')
        require(isinstance(f['reason'],str) and bool(f['reason'].strip()),'finding explanation required')
        require(isinstance(f['source_quote'],str) and bool(f['source_quote']) and f['source_quote']in source,'finding evidence not verbatim source')
    require(r['finding_prose_language']in ['vi','en','mixed','none'],'finding language enum')
    require(isinstance(r['reason'],str) and bool(r['reason'].strip()),'reason required')
    require(isinstance(r['disputes'],list),'disputes must be list')
    if o['output']is None:
        require(not any(r[k]for k in GOOD) and all(r[k]==0 for k in COUNTS),'unresolved feedback cannot receive credit/claims')
        require(not r['evidence'],'unresolved feedback has no text evidence')
    for e in r['evidence']:
        require(bool(e['source_quote']) and e['source_quote']in source and bool(e['feedback_quote']) and e['feedback_quote']in o['output']['feedback'],'feedback evidence binding mismatch')


def compare_values(per,lower=False):
    require(set(per)==set('ABCD') and len({len(v)for v in per.values()})==1,'paired denominator mismatch')
    result={}
    for name,a,b in [('B-A','A','B'),('D-C','C','D'),('C-A','A','C'),('D-B','B','D')]:
        pairs=list(zip(per[a],per[b]));diff=[float(y)-float(x)for x,y in pairs]
        result[name]={'delta_sum':sum(diff),'delta_mean':sum(diff)/len(diff),'wins':sum(d<0 if lower else d>0 for d in diff),'losses':sum(d>0 if lower else d<0 for d in diff),'ties':sum(d==0 for d in diff)}
    result['interaction_sum']=result['D-C']['delta_sum']-result['B-A']['delta_sum']
    result['interaction_mean']=result['D-C']['delta_mean']-result['B-A']['delta_mean']
    result['lower_is_better']=lower
    return result


def material_dispute(source_a,source_b,ratings):
    return bool(source_a['source_disputed']or source_a.get('disputes')or
                (source_b and(source_b['source_disputed']or source_b.get('disputes')or set(source_b['source_taxonomy'])!=set(source_a['source_taxonomy'])))or
                any(r['disputed']or r['disputes']or any(f['verdict']=='disputed'for f in r['findings'])for r in ratings))


def score(out):
    require(not(out/'review/ratings-seal.json').exists(),'ratings already scored/sealed; refuse overwrite')
    verify(out);verify_seal(out/'review','packet-seal.json');base_report(out)
    packet=read(out/'review/packet.private.json');key=read(out/'review/key.private.json');units=read(out/'units.private.json')
    source_a={r['sample_id']:r for r in read(out/'review/source-a.private.json')['cases']}
    source_b={r['sample_id']:r for r in read(out/'review/source-b.private.json')['cases']}
    gold={r['sample_id']:r['taxonomy_error']for r in read(out/'gold.private.json')}
    primary=read(out/'review/ratings-primary.private.json');secondary=read(out/'review/ratings-secondary.private.json')
    ratings={}
    packetby={c['sample_id']:c for c in packet['cases']}
    expected_primary=set(packetby)
    subset=set(read(out/'review/second-review-subset.private.json')['sample_ids'])
    covered={}
    for who,doc in [('primary',primary),('secondary',secondary)]:
        require('reviewer'in doc,'reviewer identifier required');seen=set()
        for c in doc['cases']:
            sid=c['sample_id'];require(sid not in seen and sid in packetby,'duplicate/unknown rated ID');seen.add(sid)
            u=packetby[sid];observed={o['output_id']:o for o in u['outputs']}
            require(len(c['outputs'])==4 and {r['output_id']for r in c['outputs']}==set(observed),'reviewed four-arm coverage required')
            for r in c['outputs']:
                o=observed[r['output_id']];validate_rating(r,u,o,len(source_a[sid]['findings']))
                k=key[r['output_id']];require(k['sample_id']==sid,'key source binding')
                actual=next(x for x in read(out/k['arm']/'results.private.json')if x['sample_id']==sid)
                require(all(o.get(f)==actual.get(f)for f in ['status','stage1','output','failure']),'reviewed prediction drift')
                ratings[(sid,k['arm'],who)]=r
        covered[who]=seen
    require(covered['primary']==expected_primary,'primary must cover30 IDs')
    disputes={sid for sid in expected_primary if material_dispute(source_a[sid],source_b.get(sid),[ratings[(sid,a,'primary')]for a in'ABCD'])}
    require(subset|disputes<=covered['secondary'],'secondary must cover preselected12 and all material disputed cases')
    require(primary['reviewer']!=secondary['reviewer'],'distinct reviewers required')
    rows=[];summary=read(out/'metrics.private.json')
    summary.update(review={'primary_IDs':len(covered['primary']),'secondary_IDs':len(covered['secondary']),'preselected_secondary_IDs':len(subset),'material_dispute_IDs':len(disputes),'independence':'Two separate blinded Codex agent reviews, source references sealed before outputs; not human validated. Secondary covers preselected balanced subset and all material disputes; prose language cannot be fully hidden.','packet_sha256':sha(out/'review/packet.private.json')},content_convention='Conservative reviewed subset combination: good requires both, bad/claims uses either/max; per-reviewer preserved. A false finding faithfully rendered is still factually false. Disputed no joint credit. Main reference inventory from sealed primary source; secondary source conflicts remain disputes.')
    for u in units:
        sid=u['sample_id'];refs=source_a[sid]
        source_dispute=refs['source_disputed']or(sid in source_b and(source_b[sid]['source_disputed']or set(source_b[sid]['source_taxonomy'])!=set(refs['source_taxonomy'])))
        item={'sample_id':sid,'level':u['level'],'family':u['family'],'code_sha256':u['provenance']['code_sha256'],'gold':gold[sid],'source_reference':refs,'secondary_source_reference':source_b.get(sid),'source_disputed':source_dispute,'arms':{}}
        for a in 'ABCD':
            o=next(o for o in packetby[sid]['outputs']if key[o['output_id']]['arm']==a)
            rs=[ratings[(sid,a,w)]for w in ['primary','secondary']if(sid,a,w)in ratings]
            r={k:all(x[k]for x in rs)for k in GOOD+['main_detected']}
            r.update({k:any(x[k]for x in rs)for k in BAD})
            for k in SPECIAL:
                vs=[x[k]for x in rs if x[k]is not None];r[k]=(all(vs)if k=='l3_actionable'else any(vs))if vs else None
            r.update({k:max(x[k]for x in rs)for k in COUNTS})
            r['disputed']=any(x['disputed']or x['disputes']or any(f['verdict']=='disputed'for f in x['findings'])for x in rs)
            stage1=o.get('stage1');final=o.get('output');findings=(stage1 or{}).get('findings',[])
            correctness=[]
            for index in range(len(findings)):
                fs=[x['findings'][index]for x in rs];verdicts={f['verdict']for f in fs}
                verdict='false'if'false'in verdicts else'unsupported'if'unsupported'in verdicts else'disputed'if'disputed'in verdicts else'correct'
                correctness.append({'index':index,'verdict':verdict,'label_correct':all(f['label_correct']for f in fs),'reviewer_disagreement':len(verdicts)>1,'reviews':fs})
            detected=set.intersection(*(set(x['detected_reference_indices'])for x in rs))
            r.update(status=o['status'],taxonomy=(final or{}).get('taxonomy_error'),stage1_taxonomy=(stage1 or{}).get('taxonomy_error'),findings=correctness,detected_reference_indices=sorted(detected),reference_count=len(refs['findings']),reference_detected=len(detected),missed_reference_findings=len(refs['findings'])-len(detected),predicted_findings=len(findings))
            for verdict in ['correct','false','unsupported','disputed']:
                r['finding_'+verdict]=sum(f['verdict']==verdict for f in correctness)
            r['finding_label_correct']=sum(f['label_correct']for f in correctness)
            r['correct_finding_wrong_label']=sum(f['verdict']=='correct'and not f['label_correct']for f in correctness)
            r['source_clean_assigned_errors']=not refs['findings'] and bool(findings)
            r['gold_clean_assigned_errors']=not gold[sid] and bool(findings)
            r['placeholder_exact']=bool(final and final['feedback'].strip()=='Chương trình cần được kiểm tra lại.')
            r['placeholder_literal_present']=bool(final and 'Chương trình cần được kiểm tra lại.'in final['feedback'])
            r['has_em_token']=bool(final and 'em'in final['feedback'].lower().split())
            r['feedback_pass']=bool(final and all(r[k]for k in GOOD) and not any(r[k]for k in BAD) and not r['l1_detail_leak'] and not r['l2_repair_leak'] and r['l3_actionable']is not False and not any(r[k]for k in COUNTS))
            r['joint_gold']=bool(r['feedback_pass'] and set(final['taxonomy_error'])==set(gold[sid]))
            r['joint_source']=bool(r['feedback_pass'] and not source_dispute and set(final['taxonomy_error'])==set(refs['source_taxonomy']))
            r['taxonomy_exact']=bool(final and set(final['taxonomy_error'])==set(gold[sid]))
            r['stage1_exact']=bool(stage1 is not None and set(stage1['taxonomy_error'])==set(gold[sid]))
            r['reviewer_disagreements']=[k for k in GOOD+BAD+SPECIAL+COUNTS+['main_detected','detected_reference_indices','finding_prose_language']if len({json.dumps(x[k],sort_keys=True)for x in rs})>1]
            r['reviewer_ratings']=rs;r['original_stage1']=stage1;r['original_output']=final;r['failure']=o.get('failure')
            item['arms'][a]=r
        rows.append(item)
    count_keys=GOOD+BAD+SPECIAL+COUNTS+['main_detected','reference_count','reference_detected','missed_reference_findings','predicted_findings','finding_correct','finding_false','finding_unsupported','finding_disputed','finding_label_correct','correct_finding_wrong_label','source_clean_assigned_errors','gold_clean_assigned_errors','placeholder_exact','placeholder_literal_present','has_em_token','feedback_pass','joint_gold','joint_source','taxonomy_exact','stage1_exact']
    for a in 'ABCD':
        rr=[r['arms'][a]for r in rows];content={k:sum(x[k]or 0 for x in rr)for k in count_keys}
        content['reference_recall']=content['reference_detected']/content['reference_count']if content['reference_count']else 0
        content['finding_label_accuracy']=content['finding_label_correct']/content['predicted_findings']if content['predicted_findings']else 0
        content['prose_language_IDs']=dict(Counter(r['reviewer_ratings'][0]['finding_prose_language']for r in rr))
        content['reviewer_disagreement_IDs']=sum(bool(r['reviewer_disagreements'])for r in rr)
        content['inherited_false_claim_IDs']=sum(r['inherited_false_claims']>0 for r in rr);content['new_false_claim_IDs']=sum(r['new_false_claims']>0 for r in rr)
        content['by_level']={str(i):{'n':sum(r['level']==i for r in rows),**{k:sum(r['arms'][a][k]or 0 for r in rows if r['level']==i)for k in count_keys}}for i in [1,2,3]}
        summary['arms'][a]['content']=content
    paired_keys=['taxonomy_exact','stage1_exact','finding_correct','finding_false','finding_unsupported','main_detected','factual','faithful','level_ok','natural_role','placeholder_exact','generic_placeholder','l1_detail_leak','l2_repair_leak','l3_actionable','feedback_pass','joint_gold','joint_source','inherited_false_claims','new_false_claims','new_diagnoses']
    lower={'finding_false','finding_unsupported','placeholder_exact','generic_placeholder','l1_detail_leak','l2_repair_leak','inherited_false_claims','new_false_claims','new_diagnoses'}
    summary['paired']={k:compare_values({a:[r['arms'][a][k]or 0 for r in rows]for a in 'ABCD'},k in lower)for k in paired_keys}
    summary['aggregate_deltas']={}
    for stage in ['taxonomy','stage1_taxonomy']:
        summary['aggregate_deltas'][stage]={}
        for field in ['micro_f1','macro_f1','exact_match','precision','recall']:
            x={a:summary['arms'][a][stage][field]for a in'ABCD'}
            d={'B-A':x['B']-x['A'],'D-C':x['D']-x['C'],'C-A':x['C']-x['A'],'D-B':x['D']-x['B']};d['interaction']=(x['D']-x['C'])-(x['B']-x['A'])
            summary['aggregate_deltas'][stage][field]=d
    write_json(out/'per-ID-review.private.json',rows);write_json(out/'metrics-reviewed.private.json',summary)
    # No source, gold, per-ID output or reviewer text is committed.
    public={k:v for k,v in summary.items()if k not in ['run']}
    public['runtime']={a:read(out/a/'runtime-after.json')for a in'ABCD'}
    public['load_runtime']=summary['run']['loads'];public['wall_time_s']=summary['run']['wall_time_s']
    public['freeze_sha256']=sha(out/'freeze.json')
    write_json(ROOT/'reports/task3/TASK3_LANGUAGE_PRECISION_ABLATION_METRICS_20261024.json',public)
    seal_files(out/'review','ratings-seal.json',['ratings-primary.private.json','ratings-secondary.private.json','packet-seal.json'])
    lines=['# Private per-ID table','', '|ID|Level|Family|Code hash|Arm|Gold|Taxonomy|Status|Findings correct/false/unsupported|Feedback factual/faithful/Level/voice|Placeholder|Inherited/new|Joint gold/source|Dispute|','|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        for a,x in r['arms'].items():
            lines.append('|'+ '|'.join(map(str,[r['sample_id'],r['level'],r['family'],r['code_sha256'][:8],a,','.join(r['gold']),','.join(x['taxonomy']or[]),x['status'],f"{x['finding_correct']}/{x['finding_false']}/{x['finding_unsupported']}",'/'.join(str(int(x[k]))for k in ['factual','faithful','level_ok','natural_role']),int(x['placeholder_exact']),f"{x['inherited_false_claims']}/{x['new_false_claims']}",f"{int(x['joint_gold'])}/{int(x['joint_source'])}",bool(x['disputed']or r['source_disputed'])]))+'|')
    (out/'per-ID-table.private.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({a:summary['arms'][a]['content']for a in'ABCD'},ensure_ascii=False))


def handoff(out):
    preserve(out);verify_seal(out/'review','ratings-seal.json')
    # All evidence, including failures and placeholders, is included for this small set.
    archive=out.parent/(out.name+'-internal-private.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED)as z:
        for p in sorted(out.rglob('*')):
            if p.is_file()and p.name!='handoff.private.json':z.write(p,str(p.relative_to(out)))
    archive.chmod(0o600)
    write_json(out/'handoff.private.json',{'archive':str(archive),'sha256':sha(archive),'private':True,'includes':'all frozen source/config/manifest; all raw/rendered/findings/status/journal/runtime/review/per-ID evidence'})
    print(str(archive),sha(archive))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['score','handoff']);p.add_argument('--out',type=Path,default=OUT);args=p.parse_args();globals()[args.phase](args.out.resolve())
