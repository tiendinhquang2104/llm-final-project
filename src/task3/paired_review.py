"""Small offline paired-study helpers; no model judge or public data access."""
import hashlib
import random
from src.task3.schema import code_hash
from src.task3.eval_snapshot import structural_shingles


def leakage_matches(row, protected, threshold=0.85):
    code=row['code'];tokens=code_hash(code);renamed=code_hash(code,renamed=True)
    shingles=structural_shingles(code);matches=[]
    for old in protected:
        other=structural_shingles(old['code']);union=shingles|other
        score=len(shingles&other)/len(union) if union else 1.0
        reasons=[]
        if row['sample_id']==old['sample_id']:reasons.append('sample_id')
        if hashlib.sha256(code.encode()).digest()==hashlib.sha256(old['code'].encode()).digest():reasons.append('source_text_sha256')
        if tokens==code_hash(old['code']):reasons.append('token_identity')
        if renamed==code_hash(old['code'],renamed=True):reasons.append('renamed_identity')
        if score>=threshold:reasons.append('near>=0.85')
        if reasons:matches.append({'sample_id':old['sample_id'],'reasons':reasons,'jaccard':score})
    return matches


def taxonomy_metrics(rows,labels):
    counts={label:dict(support=0,TP=0,FP=0,FN=0)for label in labels}
    exact=complete=eligible=0
    for row in rows:
        gold=set(row['gold']);output=row.get('output');complete+=output is not None
        valid=output is not None and not row.get('fallback',False)
        eligible+=valid;pred=set(output['taxonomy_error'])if valid else set()
        if not gold<=set(labels)or not pred<=set(labels):raise ValueError('unknown taxonomy label')
        exact+=valid and pred==gold
        for label,c in counts.items():
            c['support']+=label in gold;c['TP']+=label in gold&pred
            c['FP']+=label in pred-gold;c['FN']+=label in gold-pred
    tp=sum(c['TP']for c in counts.values());fp=sum(c['FP']for c in counts.values());fn=sum(c['FN']for c in counts.values())
    f1=lambda c:2*c['TP']/(2*c['TP']+c['FP']+c['FN'])if 2*c['TP']+c['FP']+c['FN']else 0.0
    supported=[c for c in counts.values()if c['support']]
    return dict(n=len(rows),complete=complete,eligible=eligible,exact=int(exact),exact_rate=exact/len(rows)if rows else None,
                micro_precision=tp/(tp+fp)if tp+fp else 0.0,micro_recall=tp/(tp+fn)if tp+fn else 0.0,
                micro_f1=2*tp/(2*tp+fp+fn)if 2*tp+fp+fn else 0.0,
                macro_f1_all=sum(map(f1,counts.values()))/len(labels),
                macro_f1_supported=sum(map(f1,supported))/len(supported)if supported else None,
                zero_support_labels=[l for l,c in counts.items()if not c['support']],per_label=counts)


def blind_pairs(sources, outputs, seed=42):
    rng=random.Random(seed);names=list(outputs);rng.shuffle(names)
    key={f'B{i+1:02d}':name for i,name in enumerate(names)};packet=[]
    for source in sources:
        for blind,name in key.items():
            packet.append({k:source[k]for k in ['sample_id','source_sha256','requested_level']}|
                          dict(candidate_id_blinded=blind,output=outputs[name].get(source['sample_id'])))
    rng.shuffle(packet)
    return packet,key


def validate_review(rows,pairs):
    fields=['sample_id','candidate_id_blinded','source_sha256','requested_level']
    identity=lambda r:tuple(r[k]for k in fields)
    if len(rows)!=len(pairs)or len({identity(r)for r in rows})!=len(rows)or {identity(r)for r in rows}!={identity(r)for r in pairs}:
        raise ValueError('review rows missing, duplicate, or bound to different sources')
    for r in rows:
        if not all(k in r for k in ['source_findings','taxonomy_review','feedback_review']):raise ValueError('incomplete review')
        if str(r['feedback_review'].get('usefulness'))not in ['0','0.5','1']:raise ValueError('invalid feedback proxy')
    return True
