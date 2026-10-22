#!/usr/bin/env python3
"""Recompute paired-study metrics from native finals and independent bound reviews."""
from pathlib import Path
from collections import Counter
import csv,json,sys,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.task3.paired_review import taxonomy_metrics,validate_review
from src.task3.eval_snapshot import sha_file
from src.synth.taxonomy import LABEL_SPACE
W=ROOT/'outputs/task3/paired-review-20261022'
def read(p):return json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')



def output_digest(output):
    return hashlib.sha256(json.dumps(output,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def check_repeated(old,new):
    keys=['usefulness','level_violation','repair_leak','unsupported_or_false_claims','generic_feedback','feasible_L3_repair','important_errors_covered','important_errors_missed','taxonomy_feedback_contradiction']
    if old.get('material_unknown')!=new.get('material_unknown')or any(old['feedback_review'].get(k)!=new['feedback_review'].get(k)for k in keys):
        raise ValueError('unresolved repeated-output semantic review disagreement')
    if old.get('taxonomy_review')!=new.get('taxonomy_review'):raise ValueError('unresolved repeated-output taxonomy review disagreement')
    return True


def audit_evidence(review,pair,source,findings):
    if review['source_findings']!=findings:raise ValueError('review source findings differ from source-only freeze')
    if any(f['evidence']not in source['code']for f in findings):raise ValueError('frozen finding source quote mismatch')
    feedback=review['feedback_review'];evidence=feedback.get('claim_evidence',[])
    if feedback['unsupported_or_false_claims']and len(evidence)!=len(feedback['unsupported_or_false_claims']):raise ValueError('false claim evidence missing')
    for item in evidence:
        if item['output_quote']not in pair['output']['feedback']:raise ValueError('fabricated output quote')
        if not item['source_evidence']or any(q not in source['code']for q in item['source_evidence']):raise ValueError('fabricated or missing source evidence')
    return True


def summarize(rows,labels):
    def feedback(rs):
        fs=[r['review']['feedback_review']for r in rs];scores=[float(f['usefulness'])if r.get('output')is not None and not r['fallback']else 0 for r,f in zip(rs,fs)]
        return dict(n=len(rs),mean_proxy=sum(scores)/len(rs)if rs else None,raw_reviewer_mean_proxy=sum(float(f.get('raw_usefulness',f['usefulness']))for f in fs)/len(fs)if fs else None,
                    score_zero=sum(s==0 for s in scores),material_unknown=sum(bool(r['review'].get('material_unknown'))for r in rs),
                    false_or_unsupported_rows=sum(bool(f['unsupported_or_false_claims'])for f in fs),false_or_unsupported_claims=sum(len(f['unsupported_or_false_claims'])for f in fs),
                    level_violation_rows=sum(bool(f['level_violation'])for f in fs),repair_leak_rows=sum(f['repair_leak']for f in fs),
                    generic_rows=sum(f['generic_feedback']for f in fs),feasible_L3_repair=sum(f['feasible_L3_repair']and not r['fallback']for r,f in zip(rs,fs)),
                    main_error_covered_rows_L2_L3=sum(bool(f['important_errors_covered'])and r['requested_level']in (2,3)and r.get('output')is not None and not r['fallback']for r,f in zip(rs,fs)),
                    missed_important_rows=sum(bool(f['important_errors_missed'])for f in fs),contradiction_rows=sum(bool(f['taxonomy_feedback_contradiction'])for f in fs))
    clean=[r for r in rows if r['functional_status']=='clean'];defect=[r for r in rows if r['functional_status']=='defective']
    fa=sum(bool(set(r['output']['taxonomy_error'])-{'Lỗi style'})for r in clean if r.get('output'))
    return dict(taxonomy_delivered=taxonomy_metrics([{**r,'fallback':False}for r in rows],labels),taxonomy_no_fallback_credit=taxonomy_metrics(rows,labels),
                feedback=feedback(rows),feedback_by_level={str(l):feedback([r for r in rows if r['requested_level']==l])for l in (1,2,3,4)},
                feedback_by_source_status={s:feedback([r for r in rows if r['functional_status']==s])for s in ['clean','defective','unknown']},
                source_review=dict(clean_denominator=len(clean),defective_denominator=len(defect),unknown_denominator=sum(r['functional_status']=='unknown'for r in rows),
                                   false_accusation=fa,false_accusation_rate=fa/len(clean)if clean else None,
                                   false_clean=sum(not r['output']['taxonomy_error']for r in defect if r.get('output')),
                                   supported_label_assignments=sum(len(r['review']['taxonomy_review']['supported_labels'])for r in rows if r['functional_status']!='unknown'),
                                   unsupported_label_assignments=sum(len(r['review']['taxonomy_review']['unsupported_labels'])for r in rows if r['functional_status']!='unknown'),
                                   missed_label_assignments=sum(len(r['review']['taxonomy_review']['missed_labels'])for r in rows if r['functional_status']!='unknown'),
                                   disputed_label_assignments=sum(len(r['review']['taxonomy_review'].get('disputed_labels',[]))for r in rows)))


def main():
    from scripts.task3_paired_review import verify
    verify();sources={r['sample_id']:r for r in read(W/'sources.private.json')};findings={r['sample_id']:r['source_findings']for r in read(W/'source-findings.private.json')};ann=read(W/'annotations.private.json');overlay={r['sample_id']:r for r in read(W/'source-adjudication-overlay.private.json')};reviews={};repeated=[];review_hashes={}
    if sha_file(W/'source-findings.private.json')!=read(W/'candidate-freeze.private.json')['source_findings_sha256']:raise ValueError('original source-only freeze changed')
    att=read(W/'review-input-attestation.private.json')
    source_seal=read(W/'candidate-freeze.private.json')['source_findings_sha256']
    bound={'source-findings.private.json':'source_findings_original_sha256','source-adjudication-overlay.private.json':'source_adjudication_overlay_sha256','sources.private.json':'source_packet_sha256','annotations.private.json':'annotations_sha256','domain-adjudication.private.json':'domain_adjudication_sha256','domain-review-overlay.private.json':'domain_review_overlay_sha256'}
    if att['source_findings_original_sha256']!=source_seal:raise ValueError('review attestation differs from earlier source seal')
    for filename,key in bound.items():
        if sha_file(W/filename)!=att[key]:raise ValueError('attested reviewer input drift: '+filename)
    sup=read(W/'review-input-attestation-supplement.private.json')
    if sup['base_attestation_sha256']!=sha_file(W/'review-input-attestation.private.json')or sup['claim_evidence_overlay_sha256']!=sha_file(W/'claim-evidence-overlay.private.json'):raise ValueError('supplemental evidence drift')
    cs=read(W/'claim-status-attestation-supplement.private.json')
    if cs['base_attestation_sha256']!=sha_file(W/'review-input-attestation.private.json')or cs['prior_evidence_supplement_sha256']!=sha_file(W/'review-input-attestation-supplement.private.json')or cs['claim_status_overlay_sha256']!=sha_file(W/'claim-status-overlay.private.json'):raise ValueError('claim adjudication seal drift')
    evidence_extra=read(W/'claim-evidence-overlay.private.json')
    domain={(r['review_file'],r['sample_id'],r['candidate_id_blinded']):r for r in read(W/'domain-review-overlay.private.json')}
    domain_sources={r['sample_id']:r for r in read(W/'domain-adjudication.private.json')}
    claim_status={(r['review_file'],r['sample_id'],r['candidate_id_blinded']):r for r in read(W/'claim-status-overlay.private.json')}
    phases=[('development','baseline'),('development','candidate1'),('development','candidate2'),('validation','validation1'),('validation','candidate2')]
    for split,name in phases:
        stem=f'{split}-{name}';packet=read(W/f'{stem}-pairs.private.json');rs=read(W/f'{stem}-review.private.json');key=read(W/f'{stem}-key.private.json');validate_review(rs,packet)
        phase=next(p for p in att['phases']if p['packet_file']==f'{stem}-pairs.private.json')
        if phase['packet_sha256']!=sha_file(W/f'{stem}-pairs.private.json')or phase['review_sha256']!=sha_file(W/f'{stem}-review.private.json'):raise ValueError('review/packet changed since independent attestation')
        att_rows={(r['sample_id'],r['candidate_id_blinded']):r for r in phase['rows']}
        packet_by={(r['sample_id'],r['candidate_id_blinded']):r for r in packet};review_hashes[stem]=dict(packet=sha_file(W/f'{stem}-pairs.private.json'),review=sha_file(W/f'{stem}-review.private.json'))
        for r in rs:
            sid=r['sample_id'];arm=key[r['candidate_id_blinded']];k=(split,arm,sid);src=sources[sid];pair=packet_by[(sid,r['candidate_id_blinded'])]
            if src['source_sha256']!=r['source_sha256']or src['requested_level']!=r['requested_level']:raise ValueError('source review binding mismatch')
            feedback=r['feedback_review'];required={'correct_claims','unsupported_or_false_claims','important_errors_covered','important_errors_missed','taxonomy_feedback_contradiction','level_violation','repair_leak','usefulness','reason','generic_feedback','feasible_L3_repair'}
            if not required<=set(feedback):raise ValueError('incomplete feedback review')
            tax=r['taxonomy_review']
            if not {'supported_labels','unsupported_labels','missed_labels','gold_disagreement'}<=set(tax):raise ValueError('incomplete taxonomy review')
            for field in ['supported_labels','unsupported_labels','missed_labels','disputed_labels']:
                values=tax.get(field,[])
                if not isinstance(values,list)or len(values)!=len(set(values))or not set(values)<=set(LABEL_SPACE):raise ValueError('invalid reviewed taxonomy groups')
            original_review=json.loads(json.dumps(r));r=json.loads(json.dumps(r));feedback=r['feedback_review']
            stamp=att_rows[(sid,r['candidate_id_blinded'])]
            if stamp['output_sha256']!=output_digest(pair['output'])or any(stamp[k]!=r[k]for k in ['source_sha256','requested_level']):raise ValueError('review-to-output attestation mismatch')
            for extra in evidence_extra:
                if (extra['review_file'],extra['sample_id'],extra['candidate_id_blinded'])==(f'{stem}-review.private.json',sid,r['candidate_id_blinded']):
                    if extra['source_sha256']!=src['source_sha256']:raise ValueError('supplemental source drift')
                    for evidence in feedback.get('claim_evidence',[]):
                        if evidence['review_claim']==extra['review_claim']:evidence['source_evidence']=extra['source_evidence']
            audit_evidence(r,pair,src,findings[sid])
            native={v['sample_id']:v['output']for v in read(W/arm/split/'completed.predictions.json')}
            if native.get(sid)!=pair['output']:raise ValueError('blinded output does not match intact native pair')
            if k in reviews:
                old=reviews[k]['raw_review'];repeated.append(dict(split=split,arm=arm,sample_id=sid,same_proxy=old['feedback_review']['usefulness']==feedback['usefulness'],same_level=old['feedback_review']['level_violation']==feedback['level_violation']))
                check_repeated(old,original_review)
                continue
            trace=next(t for t in read(W/arm/split/'traces.json')if t['sample_id']==sid)
            d=domain[(f'{stem}-review.private.json',sid,r['candidate_id_blinded'])]
            if d['review_file_sha256']!=sha_file(W/f'{stem}-review.private.json')or d['source_sha256']!=src['source_sha256']:raise ValueError('domain adjudication source/review drift')
            feedback['raw_usefulness']=feedback['usefulness'];feedback['usefulness']=str(d['conservative_usefulness_no_unknown_credit']);r['material_unknown']=d['material_unknown']
            c=claim_status.get((f'{stem}-review.private.json',sid,r['candidate_id_blinded']))
            if c:
                if c['review_file_sha256']!=sha_file(W/f'{stem}-review.private.json')or c['source_sha256']!=src['source_sha256']or c['output_sha256']!=output_digest(pair['output']):raise ValueError('claim reclassification review/output drift')
                feedback['level_violation']+=c['additional_level_violation_adjudication']
                feedback['raw_unsupported_or_false_claims']=feedback['unsupported_or_false_claims'];feedback['unsupported_or_false_claims']=c['primary_false_or_unsupported_claims'];feedback['domain_unknown_claims']=c['domain_unknown_claims']
            reviews[k]=dict(sample_id=sid,split=split,arm=arm,source_sha256=src['source_sha256'],requested_level=src['requested_level'],functional_status=d['functional_status_primary_full_domain'],gold=ann[sid]['taxonomy_error'],output=native.get(sid),fallback=trace['fallback_used'],raw_review=original_review,review=r)
    labels=read(ROOT/'data/raw/round18-new/label_space.json')['taxonomy_error'];metrics={}
    for split in ['development','validation']:
        metrics[split]={}
        for arm in ['R15','SFT1','SFT2','C1','C2']:
            rows=[r for (s,a,_),r in reviews.items()if s==split and a==arm]
            if {r['sample_id']for r in rows}!={sid for sid,s in sources.items()if s['split']==split}:raise ValueError('not paired complete')
            result=summarize(rows,labels);run=read(W/arm/split/'run.json');traces=read(W/arm/split/'traces.json');decisions=[json.loads(s)for s in (W/arm/split/'decisions.jsonl').read_text().splitlines()]
            generations=[json.loads(s)for s in (W/arm/split/'generations.jsonl').read_text().splitlines()]
            result['operations']=dict(complete=run['completed'],requested=run['requested'],schema_valid_final=bool(run['schema']),retry_ids=sum(len(t['attempts'])>1 for t in traces),fallback_ids=sum(t['fallback_used']for t in traces),invalid_schema_attempts=sum(not d['schema_valid']for d in decisions),runtime_errors=sum(bool(a.get('runtime_error'))for t in traces for a in t['attempts']),finish_reasons=dict(Counter(g['finish_reason']for g in generations)),calls=len(generations),input_tokens=sum(g['input_tokens']or 0 for g in generations),output_tokens=sum(g['output_tokens']for g in generations),generation_latency_s=sum(g.get('latency_s',0)for g in generations),elapsed_s=run['elapsed_s'])
            # This sensitivity subset excludes all source uncertainty and category-boundary disputes.
            certain=[r for r in rows if r['functional_status']!='unknown'and not overlay[r['sample_id']]['disputed_overlap_labels']and all(f['confidence']=='supported'for f in r['review']['source_findings'])]
            result['agent_undisputed_subset']=taxonomy_metrics([{**r,'gold':overlay[r['sample_id']]['supported_taxonomy_groups'],'fallback':False}for r in certain],labels)
            metrics[split][arm]=result
    ordered=sorted(reviews.values(),key=lambda r:(r['split'],r['sample_id'],r['arm']))
    write(W/'id-metrics.private.json',ordered)
    with (W/'id-metrics.private.csv').open('w')as f:
        writer=csv.DictWriter(f,fieldnames=['sample_id','split','arm','source_sha256','requested_level','functional_status','fallback','usefulness','false_claims','level_violations']);writer.writeheader()
        for r in ordered:writer.writerow({k:r[k]for k in ['sample_id','split','arm','source_sha256','requested_level','functional_status','fallback']}|dict(usefulness=r['review']['feedback_review']['usefulness'],false_claims=len(r['review']['feedback_review']['unsupported_or_false_claims']),level_violations=len(r['review']['feedback_review']['level_violation'])))
    result=dict(selection_sha256=sha_file(W/'selection.private.json'),source_findings_sha256=sha_file(W/'source-findings.private.json'),review_hashes=review_hashes,private_artifact_hashes={str(p.relative_to(W)):sha_file(p)for p in W.rglob('*')if p.is_file()and (p.name in ['sources.private.json','annotations.private.json','source-findings.private.json','source-adjudication-overlay.private.json','domain-adjudication.private.json','review-input-attestation.private.json','domain-review-overlay.private.json','claim-status-overlay.private.json','claim-evidence-overlay.private.json','review-input-attestation-supplement.private.json','claim-status-attestation-supplement.private.json','predictions.json','completed.predictions.json','traces.json','run.json','started.json','generations.jsonl','attempts.jsonl','decisions.jsonl']or p.name.endswith('-key.private.json'))},repeated_output_checks=repeated,metrics=metrics,source_status=dict(Counter(domain_sources.get(sid,r)['functional_status']for sid,r in overlay.items())),human_verified_sources=0,proxy_is_official_score=False)
    write(W/'metrics.json',result);write(ROOT/'reports/task3/TASK3_PAIRED_REVIEW_RESULTS_20261022.json',result)
    print(json.dumps({'rows':len(ordered),'repeated':len(repeated),'metrics':{s:{a:{'F1':r['taxonomy_delivered']['micro_f1'],'proxy':r['feedback']['mean_proxy'],'false':r['feedback']['false_or_unsupported_rows'],'level':r['feedback']['level_violation_rows']}for a,r in arms.items()}for s,arms in metrics.items()}},ensure_ascii=False))
if __name__=='__main__':main()
