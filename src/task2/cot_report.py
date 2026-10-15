"""Debug artefacts for a Task 2 prompting run: one JSON row per sample (`debug.jsonl`) and a self-contained
`report.html` (no network) with per-label scores, gold-vs-predicted counts and every sample's reasoning.

Reads only what `run_api` already wrote (predictions_full.json, raw_outputs.jsonl, usage.jsonl, metrics.json,
resources.json, config.json) plus the samples themselves (code, compile_log, gold labels)."""
from __future__ import annotations

import html
import json
from pathlib import Path

from src.llm.local_backend import OOM_MARK
from src.task2.evaluator import f1_scores
from src.task2.labels import LABELS
from src.task2.pipeline import parse_cot_labels
from src.task2.prompts_cot import FINAL_MARKER

MIN_REASONING_CHARS = 80  # less text before KẾT LUẬN = the model skipped the step-by-step part


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _json(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def build_rows(out_dir, samples: list, postprocess=None) -> list[dict]:
    """One row per sample, in `samples` order. Later cache/usage lines win (a rerun replaces older ones).
    `postprocess` (Task2ApiPipeline.postprocess) re-parses raw outputs, so an interrupted run (no
    predictions_full.json yet) still gets a report; without it predictions_full.json is used."""
    out_dir = Path(out_dir)
    preds = {p["sample_id"]: p for p in _json(out_dir / "predictions_full.json", [])}
    raw = {r["sample_id"]: r["record"] for r in _jsonl(out_dir / "raw_outputs.jsonl")}
    usage: dict[str, dict[int, dict]] = {}
    for u in _jsonl(out_dir / "usage.jsonl"):
        if "sample_id" in u:
            usage.setdefault(u["sample_id"], {})[int(u.get("vote", 0))] = u
    rows = []
    for s in samples:
        rec = raw.get(s.sample_id) or {}
        p = postprocess(rec) if (postprocess and rec) else preds.get(s.sample_id)
        p = p or {"labels": [], "probs": {}, "parse_ok": False, "n_parsed": 0}
        votes = list((usage.get(s.sample_id) or {}).values())
        reasoning = min((len(o.rsplit(FINAL_MARKER, 1)[0].strip()) for o in rec.get("outputs", [])), default=None)
        gold = list(s.labels) if s.has_gold else None
        pred = list(p["labels"])
        row = {"sample_id": s.sample_id, "exam_id": s.exam_id, "gold": gold, "pred": pred,
               "probs": {k: v for k, v in (p.get("probs") or {}).items() if v}, "parse_ok": p["parse_ok"],
               "n_parsed": p.get("n_parsed", 0), "outputs": rec.get("outputs", []),
               "retry_outputs": rec.get("retry_outputs", []),
               "prompt_tokens": max((v["prompt_tokens"] for v in votes), default=None),
               "output_tokens": sum(v["output_tokens"] for v in votes) if votes else None,
               "seconds": round(sum(v["seconds"] for v in votes), 2) if votes else None,
               "hit_max_tokens": any(v.get("hit_max_tokens") for v in votes),
               "reasoning_chars": reasoning,
               "output_labels": [parse_cot_labels(o) for o in rec.get("outputs", [])],  # per vote; None = unparsed
               "split_labels": [lab for lab, v in (p.get("probs") or {}).items() if 0 < v < 1],
               "demos": rec.get("demos", []),
               "compile_rule": bool(p.get("compile_rule")), "model_compile_vote": p.get("model_compile_vote"),
               "no_reasoning": reasoning is not None and reasoning < MIN_REASONING_CHARS,
               "oom": any(o.startswith(OOM_MARK) for o in rec.get("outputs", []) + rec.get("retry_outputs", [])),
               "compile_log": s.compile_log, "code": s.code}
        if gold is not None:
            row.update(tp=[x for x in pred if x in gold], fp=[x for x in pred if x not in gold],
                       fn=[x for x in gold if x not in pred], exact=set(gold) == set(pred))
        rows.append(row)
    return rows


def summarize(rows: list[dict], metrics: dict | None, resources: dict | None) -> dict:
    gold = {r["sample_id"]: r["gold"] for r in rows if r["gold"] is not None}
    pred = {r["sample_id"]: r["pred"] for r in rows}
    scores = f1_scores(gold, pred) if gold else None
    secs = [r["seconds"] for r in rows if r["seconds"] is not None]
    return {
        "n": len(rows), "has_gold": bool(gold), "scores": scores,
        "parse_failures": sum(not r["parse_ok"] for r in rows),
        "hit_max_tokens": sum(r["hit_max_tokens"] for r in rows),
        "retried": sum(bool(r["retry_outputs"]) for r in rows),
        "no_reasoning": sum(r["no_reasoning"] for r in rows),
        "oom": sum(r["oom"] for r in rows),
        "split_samples": sum(bool(r["split_labels"]) for r in rows),
        "votes_per_sample": max((len(r["outputs"]) for r in rows), default=0),
        "pred_count": {lab: sum(lab in r["pred"] for r in rows) for lab in LABELS},
        "gold_count": {lab: sum(lab in r["gold"] for r in rows if r["gold"] is not None) for lab in LABELS},
        "labels_per_sample_pred": [len(r["pred"]) for r in rows],
        "labels_per_sample_gold": [len(r["gold"]) for r in rows if r["gold"] is not None],
        "mean_seconds": sum(secs) / len(secs) if secs else None,
        "metrics": metrics or {}, "resources": resources or {},
    }


def write_debug_report(out_dir, samples: list, title: str | None = None, postprocess=None) -> Path:
    """Write debug.jsonl + report.html into `out_dir`; returns the report path."""
    out_dir = Path(out_dir)
    rows = build_rows(out_dir, samples, postprocess)
    with (out_dir / "debug.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    cfg = _json(out_dir / "config.json", {}) or {}
    summary = summarize(rows, _json(out_dir / "metrics.json"), _json(out_dir / "resources.json"))
    summary["config"] = {"name": (cfg.get("config") or {}).get("name"),
                         "generation": (cfg.get("config") or {}).get("generation"),
                         "prompt": (cfg.get("config") or {}).get("prompt"),
                         "model_info": {k: v for k, v in (cfg.get("model_info") or {}).items()
                                        if k in ("backend", "model", "revision", "hardware")},
                         "timestamp": cfg.get("timestamp")}
    data = json.dumps({"labels": list(LABELS), "summary": summary, "rows": rows}, ensure_ascii=False)
    data = data.replace("</", "<\\/")  # keep </script> inside strings from closing the tag
    page = _TEMPLATE.replace("__TITLE__", html.escape(title or summary["config"]["name"] or out_dir.name))
    page = page.replace("__DATA__", data)
    path = out_dir / "report.html"
    path.write_text(page, encoding="utf-8")
    return path


_TEMPLATE = r"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1b;--mute:#6b6b66;--line:#e2e2dc;--tp:#1f8a4c;--fp:#c23b2b;--fn:#b7791f;
--gold:#3d5a99;--pred:#8a5a99;--code:#f1f1ec}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161615;--card:#20201e;--ink:#ecece6;
--mute:#9a9a93;--line:#34342f;--tp:#4cc27f;--fp:#ff6b5a;--fn:#e3a743;--gold:#7c9be0;--pred:#c193d6;--code:#2a2a27}}
:root[data-theme="dark"]{--bg:#161615;--card:#20201e;--ink:#ecece6;--mute:#9a9a93;--line:#34342f;--tp:#4cc27f;
--fp:#ff6b5a;--fn:#e3a743;--gold:#7c9be0;--pred:#c193d6;--code:#2a2a27}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:1200px;margin:0 auto;padding:24px 16px 64px}h1{font-size:20px;margin:0 0 4px}
h2{font-size:15px;margin:28px 0 10px}.sub{color:var(--mute);font-size:12px;word-break:break-all}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-top:16px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px}
.tile b{display:block;font-size:20px;font-variant-numeric:tabular-nums}.tile span{color:var(--mute);font-size:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;overflow-x:auto}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);
vertical-align:top}th{font-size:12px;color:var(--mute);font-weight:600}td.num{font-variant-numeric:tabular-nums;
text-align:right}.bar{height:8px;border-radius:2px;display:block}.bars{display:flex;flex-direction:column;gap:2px;
min-width:140px}.legend{display:flex;gap:14px;font-size:12px;color:var(--mute);margin-bottom:8px;flex-wrap:wrap}
.sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:-1px}
.chip{display:inline-block;padding:1px 7px;border-radius:10px;font-size:12px;margin:1px 2px;border:1px solid}
.tp{color:var(--tp);border-color:var(--tp)}.fp{color:var(--fp);border-color:var(--fp)}
.fn{color:var(--fn);border-color:var(--fn);border-style:dashed}.nt{color:var(--mute);border-color:var(--line)}
.controls{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
button,input{font:inherit;color:inherit;background:var(--card);border:1px solid var(--line);border-radius:6px;
padding:4px 10px}button.on{border-color:var(--ink);font-weight:600}input{min-width:200px}
tr.row{cursor:pointer}tr.row:hover{background:var(--code)}tr.detail td{background:var(--code)}
pre{white-space:pre-wrap;word-break:break-word;margin:6px 0 12px;font:12px/1.45 ui-monospace,Menlo,monospace;
background:var(--card);border:1px solid var(--line);border-radius:6px;padding:8px;max-height:480px;overflow:auto}
.warn{color:var(--fp);font-weight:600}.hist{display:flex;align-items:flex-end;gap:6px;height:120px}
.hist div{display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;flex:1}
.hist .pair{display:flex;gap:2px;align-items:flex-end;height:100px}.hist .pair i{width:12px;display:block;
border-radius:2px 2px 0 0}.hist small{color:var(--mute);font-size:11px}
</style></head><body><main>
<h1>__TITLE__</h1><div class="sub" id="meta"></div>
<div class="tiles" id="tiles"></div>
<h2>Theo nhãn</h2><div class="card"><div class="legend"><span><i class="sw" style="background:var(--gold)"></i>gold
</span><span><i class="sw" style="background:var(--pred)"></i>dự đoán</span><span><i class="sw"
style="background:var(--tp)"></i>F1</span></div><table id="labels"></table></div>
<h2>Số nhãn mỗi bài</h2><div class="card"><div class="hist" id="hist"></div></div>
<h2>Từng bài</h2><div class="card">
<div class="legend"><span class="chip tp">đúng (TP)</span><span class="chip fp">thừa (FP)</span>
<span class="chip fn">thiếu (FN)</span><span>Bấm một dòng để xem lời chấm, code và compile_log.</span></div>
<div class="controls" id="filters"></div><table id="rows"></table></div>
</main>
<script type="application/json" id="data">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent),S=D.summary,R=D.rows,L=D.labels;
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const f=(x,d=3)=>x==null||Number.isNaN(x)?'—':Number(x).toFixed(d);
const mi=S.config.model_info||{};
document.getElementById('meta').textContent=[mi.model,mi.revision&&('rev '+String(mi.revision).slice(0,10)),
mi.backend,mi.hardware,S.config.timestamp,'gen '+JSON.stringify(S.config.generation||{})].filter(Boolean).join(' · ');
const sc=S.scores,res=S.resources||{};
const tiles=[];
if(sc){tiles.push(['macro-F1',f(sc.macro_f1)],['micro-F1',f(sc.micro_f1)],['exact match',f(sc.exact_match)]);}
tiles.push(['số bài',S.n],['phiếu mỗi bài',S.votes_per_sample],['bài có phiếu chia rẽ',S.split_samples],
['parse lỗi',S.parse_failures],['GPU hết bộ nhớ (OOM)',S.oom],['thiếu suy luận',S.no_reasoning],['phải retry',S.retried],['chạm max token',S.hit_max_tokens],
['giây/bài',f(S.mean_seconds,1)],['token vào',res.tokens_in??'—'],['token ra',res.tokens_out??'—'],
['bộ nhớ đỉnh (GB)',f(res.peak_memory_gb,2)]);
document.getElementById('tiles').innerHTML=tiles.map(([k,v])=>`<div class="tile"><b>${esc(v)}</b><span>${esc(k)}
</span></div>`).join('');
const maxC=Math.max(1,...L.map(l=>Math.max(S.gold_count[l]||0,S.pred_count[l]||0)));
let lh='<tr><th>Nhãn</th><th>gold / dự đoán</th><th class="num">gold</th><th class="num">dự đoán</th>'+
(sc?'<th class="num">P</th><th class="num">R</th><th class="num">F1</th><th>F1</th>':'')+'</tr>';
for(const l of L){const g=S.gold_count[l]||0,p=S.pred_count[l]||0,pl=sc?sc.per_label[l]:null;
lh+=`<tr><td>${esc(l)}</td><td><div class="bars">${S.has_gold?`<span class="bar" style="width:${g/maxC*100}%;
background:var(--gold)"></span>`:''}<span class="bar" style="width:${p/maxC*100}%;background:var(--pred)"></span>
</div></td><td class="num">${S.has_gold?g:'—'}</td><td class="num">${p}</td>`+(pl?`<td class="num">${f(pl.precision,2)}
</td><td class="num">${f(pl.recall,2)}</td><td class="num">${f(pl.f1,2)}</td><td style="min-width:140px"><span class="bar" style="width:
${(pl.f1||0)*100}%;background:var(--tp);min-width:${pl.f1?2:0}px"></span></td>`:'')+'</tr>';}
document.getElementById('labels').innerHTML=lh;
const kmax=Math.max(0,...S.labels_per_sample_pred,...S.labels_per_sample_gold);
const cnt=a=>{const c=Array(kmax+1).fill(0);a.forEach(x=>c[x]++);return c};
const cg=cnt(S.labels_per_sample_gold),cp=cnt(S.labels_per_sample_pred),hm=Math.max(1,...cg,...cp);
document.getElementById('hist').innerHTML=cp.map((_,k)=>`<div><div class="pair">${S.has_gold?`<i title="gold: ${cg[k]}"
style="height:${cg[k]/hm*100}%;background:var(--gold)"></i>`:''}<i title="dự đoán: ${cp[k]}" style="height:
${cp[k]/hm*100}%;background:var(--pred)"></i></div><small>${k} nhãn</small></div>`).join('');
const FILTERS=[['all','Tất cả',r=>true]];
if(S.has_gold)FILTERS.push(['wrong','Sai',r=>!r.exact],['fp','Có FP',r=>r.fp.length],['fn','Có FN',r=>r.fn.length]);
FILTERS.push(['split','Phiếu chia rẽ',r=>r.split_labels.length],['parse','Parse lỗi',r=>!r.parse_ok],['oom','OOM',r=>r.oom],['noreason','Thiếu suy luận',r=>r.no_reasoning],['max','Chạm max token',r=>r.hit_max_tokens],
['retry','Phải retry',r=>r.retry_outputs.length]);
let cur='all',q='',open=new Set();
const fe=document.getElementById('filters');
fe.innerHTML=FILTERS.map(([k,t])=>`<button data-k="${k}">${t} (${R.filter(FILTERS.find(x=>x[0]==k)[2]).length})
</button>`).join('')+'<input id="q" placeholder="Tìm sample_id / exam / nhãn">';
fe.onclick=e=>{const k=e.target.dataset&&e.target.dataset.k;if(k){cur=k;draw()}};
document.getElementById('q').oninput=e=>{q=e.target.value.toLowerCase();draw()};
const chips=r=>{if(r.gold==null)return r.pred.map(x=>`<span class="chip nt">${esc(x)}</span>`).join('')||
'<span class="chip nt">[]</span>';return r.tp.map(x=>`<span class="chip tp">${esc(x)}</span>`).join('')+
r.fp.map(x=>`<span class="chip fp">${esc(x)}</span>`).join('')+r.fn.map(x=>`<span class="chip fn">${esc(x)}</span>`)
.join('')||'<span class="chip nt">[] đúng</span>'};
const numbered=c=>String(c||'').split('\n').map((l,i)=>String(i+1).padStart(3)+'  '+l).join('\n');
function detail(r){let h='';const nv=r.outputs.length;
if(nv>1){const np=Math.max(1,r.n_parsed);h+='<b>Phiếu bầu</b> (giữ nhãn có ≥ 50% phiếu)<table style="width:auto">';
for(const l of L){const v=r.probs[l]||0;if(!v&&!(r.gold||[]).includes(l))continue;const k=Math.round(v*np);
const g=(r.gold||[]).includes(l)?' <span class="chip tp">gold</span>':'';h+=`<tr><td>${esc(l)}${g}</td><td class="num">
${k}/${np}</td><td style="min-width:140px"><span class="bar" style="width:${v*100}%;min-width:${v?2:0}px;background:
${v>=0.5?'var(--tp)':'var(--fn)'}"></span></td></tr>`}h+='</table>'}
r.outputs.forEach((o,i)=>{const ol=(r.output_labels||[])[i];h+=`<b>Lời chấm${nv>1?' #'+(i+1):''}</b> ${ol==null?
'<span class="warn">không parse được</span>':ol.map(x=>`<span class="chip nt">${esc(x)}</span>`).join('')||
'<span class="chip nt">[]</span>'}<pre>${esc(o)}</pre>`});r.retry_outputs.forEach((o,i)=>{h+=`<b class="warn">Retry #${i+1}</b><pre>${esc(o)}</pre>`});
if(r.compile_rule)h+=`<b>Lỗi biên dịch</b> lấy từ compile_log (quy tắc), phiếu của model: ${r.model_compile_vote==null?
'—':f(r.model_compile_vote,2)}<br>`;
if(r.demos&&r.demos.length)h+=`<b>Demo few-shot</b> (nguồn:sample_id:độ giống) <span class="sub">${esc(r.demos.join(' · '))}</span><br>`;
h+=`<b>compile_log</b><pre>${r.compile_log==null?'(không có)':esc(r.compile_log)||'(rỗng — compile sạch)'}</pre>`;
h+=`<b>Code</b><pre>${esc(numbered(r.code))}</pre>`;return h}
function draw(){[...fe.querySelectorAll('button')].forEach(b=>b.classList.toggle('on',b.dataset.k==cur));
const pass=FILTERS.find(x=>x[0]==cur)[2];
let h='<tr><th>sample_id</th><th>exam</th><th>nhãn</th><th class="num">token ra</th><th class="num">giây</th><th>'+
'ghi chú</th></tr>';
for(const r of R){if(!pass(r))continue;const hay=(r.sample_id+' '+r.exam_id+' '+r.pred.join(' ')+' '+(r.gold||[])
.join(' ')).toLowerCase();if(q&&!hay.includes(q))continue;
const notes=[r.oom&&'<span class="warn">OOM</span>',!r.parse_ok&&'<span class="warn">parse lỗi</span>',r.no_reasoning&&'<span class="warn">thiếu suy luận</span>',r.hit_max_tokens&&'<span class="warn">chạm max</span>',
r.retry_outputs.length&&'retry',r.split_labels.length&&('chia rẽ: '+esc(r.split_labels.join(', ')))].filter(Boolean)
.join(' · ');
h+=`<tr class="row" data-id="${esc(r.sample_id)}"><td>${esc(r.sample_id)}</td><td>${esc(r.exam_id)}</td><td>
${chips(r)}</td><td class="num">${r.output_tokens??'—'}</td><td class="num">${f(r.seconds,1)}</td><td>${notes}</td></tr>`;
if(open.has(r.sample_id))h+=`<tr class="detail"><td colspan="6">${detail(r)}</td></tr>`;}
document.getElementById('rows').innerHTML=h}
document.getElementById('rows').onclick=e=>{const tr=e.target.closest('tr.row');if(!tr)return;const id=tr.dataset.id;
open.has(id)?open.delete(id):open.add(id);draw()};
draw();
</script></body></html>
"""
