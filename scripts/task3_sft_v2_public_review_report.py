"""Bind the completed blinded source reviews and render an offline casebook."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.task3.sft_v1 import read_jsonl,sha256
from src.task3.sft_v1_runtime import digest
from src.task3.sft_v1_experiment import write_json

DIMENSIONS=['diagnosis_supported','essential_location_condition','taxonomy_feedback_consistency',
            'Level_compliance','Vietnamese','useful_l3_hint']
VERDICTS={'pass','fail','uncertain','not_applicable','not_evaluable'}


def run(out):
    out=Path(out); packets=read_jsonl(out/'public-comparison/blinded-review-packets.jsonl')
    by_id={p['sample_id']:p for p in packets}
    keys=json.loads((out/'public-comparison/blinding-key.private.json').read_text())
    paths=[out/'review-progress'/n for n in ['fixed-single.review.jsonl','fixed-multi-and-risk.review.jsonl']]
    reviews=[x for path in paths for x in read_jsonl(path)]
    ids=[r['sample_id'] for r in reviews]
    if len(set(ids))!=len(ids) or set(ids)!=set(by_id):raise ValueError('review coverage differs from frozen selected union')
    normalized=[]
    for r in reviews:
        p=by_id[r['sample_id']]
        if r['review_id']!=p['review_id'] or r['level']!=p['level']:raise ValueError('review ID/Level binding')
        outputs={}
        for label in ['A','B']:
            verdict=r['outputs'][label]; original=p['outputs'][label]['payload']
            if verdict['original_payload_sha256']!=digest(original):raise ValueError('review payload hash differs')
            if set(verdict['verdicts'])!=set(DIMENSIONS) or not set(verdict['verdicts'].values())<=VERDICTS:
                raise ValueError('review dimensions invalid')
            if not verdict.get('evidence'):raise ValueError('review evidence absent')
            method=keys[r['review_id']]['methods'][label]
            outputs[method]=dict(verdict,opaque_label=label,structural_status=p['outputs'][label]['status'])
        normalized.append(dict(sample_id=r['sample_id'],review_id=r['review_id'],level=r['level'],
            review_groups=p['review_groups'],source_sha256=p['input']['source_sha256'],
            source_findings=r['source_findings'],outputs=outputs))
    groups={name:[r for r in normalized if name in r['review_groups']] for name in ['fixed','additional_risk','all_invalid']}
    technical={r['sample_id'] for r in json.loads((out/'context-preflight.json').read_text()) if r['status']!='evaluable'}
    summary=dict(review_kind='blinded agent source-grounded review; not independent public gold',
        payload_bindings_verified=len(reviews)*2,unique_selected_ids=len(reviews),
        technical_preflight_ids=len(technical),technical_overlap_with_selected=len(technical & set(ids)),
        total_unique_reviewed_ids=len(technical | set(ids)),
        original_reviews_preserved=True,generated_payloads_unchanged=True,
        risk_sample_representative=False,no_public_accuracy_f1_or_leaderboard_score=True,
        review_file_sha256={str(p.relative_to(out)):sha256(p) for p in paths},groups={})
    for group,rows in groups.items():
        summary['groups'][group]=dict(ids=len(rows),sources=len({r['source_sha256'] for r in rows}),
            by_level=dict(Counter(r['level'] for r in rows)),
            methods={method:{d:dict(Counter(r['outputs'][method]['verdicts'][d] for r in rows)) for d in DIMENSIONS}
                     for method in ['v2','comparator']})
    dest=out/'semantic-review'
    if dest.exists():raise FileExistsError('review report already exists')
    dest.mkdir()
    (dest/'review.rows.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in normalized))
    write_json(dest/'summary.json',summary)
    esc=lambda x:html.escape(x if isinstance(x,str) else json.dumps(x,ensure_ascii=False,indent=2))
    body=['<!doctype html><html lang="vi"><meta charset="utf-8"><title>Task3 V2 public: source-grounded review</title>',
        '<style>body{font:16px system-ui;max-width:1200px;margin:2em auto;padding:1em}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f4f6;padding:1em}article{border-top:2px solid #888;margin-top:2em}section{border:1px solid #ccc;padding:1em;margin:1em 0}a{color:#164e9a}</style>',
        '<h1>Task3 V2 public: casebook đã review</h1><p>36 fixed +24 risk; agent review, không phải public gold. Một fixed case không có phản hồi V2 vì context. Method được mở sau review; payload giữ nguyên. Risk slice không đại diện accuracy. Tám lỗi preflight có sidecar riêng.</p>',
        '<p><a href="../public-comparison/casebook.html">Toàn328 input và output</a> · <a href="../preflight-failure-review.json">Tám context failures</a> · <a href="summary.json">Mẫu số và verdict counts</a></p>']
    for r in normalized:
        p=by_id[r['sample_id']]; x=p['input']['mapped_input']
        body.extend([f'<article id="{esc(r["sample_id"])}"><h2>{esc(r["sample_id"])} — L{r["level"]}</h2>',
            '<p>'+esc(r['review_groups'])+'</p><h3>Phân tích source/spec</h3><pre>'+esc(r['source_findings'])+'</pre>',
            '<details><summary>Full yêu cầu, source và syntax logs</summary><h3>Yêu cầu</h3><pre>'+esc(x['statement'])+'</pre><h3>Source</h3><pre>'+esc(x['code'])+'</pre><h3>Syntax logs, phân biệt nguồn</h3><pre>'+esc(x['compile_log'])+'</pre></details>'])
        for method,o in r['outputs'].items():
            raw=p['outputs'][o['opaque_label']]['raw']
            body.extend(['<section><h3>'+esc(method)+' (review dưới nhãn '+o['opaque_label']+')</h3><h4>Nguyên output</h4><pre>'+esc(raw or '(không có phản hồi model)')+'</pre><h4>Verdict và evidence</h4><pre>'+esc(o)+'</pre></section>'])
        body.append('</article>')
    body.append('</html>'); (dest/'reviewed-casebook.html').write_text('\n'.join(body))
    write_json(dest/'artifact-sha256.json',{p.name:sha256(p) for p in dest.iterdir() if p.is_file()})
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='outputs/task3/sft-v2-public-20261026-run1');a=p.parse_args()
    print(json.dumps(run(a.out),ensure_ascii=False))
