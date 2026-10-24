#!/usr/bin/env python3
"""Offline casebook/comparison/gate after explicit qualitative reviews, no model."""
from pathlib import Path
import argparse
import json
import sys
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.task3.dataset import read_json,write_json
from src.task3.level_blind import digest,sha
from src.task3 import v15_evaluation as ev


def build(out):
    out=Path(out);units=read_json(out/'enriched-inputs.private.json')['units'];results=read_json(out/'results.private.json')
    by={r['sample_id']:r for r in results};reviews={r['sample_id']:r for r in read_json(out/'internal-reviews.private.json')}
    gold={g['sample_id']:g['taxonomy_error'] for g in read_json(out/'gold.private.json')}
    records=[]
    for u in units:
        r=by[u['sample_id']];rev=reviews[u['sample_id']];ev.validate_review(r,rev)
        records.append(dict(sample_id=u['sample_id'],family=u.get('family'),level=u['level'],original_source=u['task']['code'],
                            task_requirements={k:u['task'].get(k) for k in ('statement','problems','grading_policy','exam_metadata','input_metadata')},
                            local_compiler=u['local_compiler'],source_catalog=u['source_catalog'],
                            findings=r['stage1']['findings'] if r['stage1'] else None,output=r['output'],failure=r['failure'],
                            gold_taxonomy=gold[u['sample_id']],qualitative_review=rev))
    write_json(out/'casebook.private.json',records)
    text=['# Hồ sơ internal30 v1.5 (thứ tự input cố định)','Đánh giá định tính bằng automated agent; không phải đánh giá người độc lập.']
    for r in records:
        text += [f"\n## {r['sample_id']} — Level{r['level']}",'\nNguồn gốc:\n```cpp\n'+r['original_source']+'\n```',
                 '\nCompiler: '+json.dumps(r['local_compiler'],ensure_ascii=False),
                 '\nFindings và trích đoạn:\n```json\n'+json.dumps(r['findings'],ensure_ascii=False,indent=2)+'\n```',
                 '\nOutput: '+json.dumps(r['output'],ensure_ascii=False),'\nFailure: '+json.dumps(r['failure'],ensure_ascii=False),
                 '\nReview: '+json.dumps(r['qualitative_review'],ensure_ascii=False)]
    (out/'CASEBOOK.vi.private.md').write_text('\n'.join(text)+'\n')
    gate=ev.evaluate_gate(out)
    comp=read_json(out/'comparison.private.json')
    source_counts=Counter(u['local_compiler']['source_sha256'] for u in units);families=Counter(u.get('family') for u in units)
    write_json(out/'population-groups.private.json',dict(total_ids=len(units),distinct_sources=len(source_counts),
        distinct_families=len(families),source_counts=dict(source_counts),family_counts=dict(families),
        caveat='Repeated sources/Levels are not independent generalization evidence. Seen development data.'))
    summary=read_json(out/'run-summary.json');renderer=read_json(out/'renderer-eval/costs.json')
    lines=['# Task 3 D+ v1.5 — báo cáo đo thực tế','',
           f"Hoàn tất {summary['completed']}/30; gate public: **{gate['status']}**. Không sửa gold hoặc raw source.",
           '', '| Phương pháp (cùng30 ID) | micro-F1 | macro-F1 | TP/FP/FN | exact | false alarms clean |',
           '|---|---:|---:|---|---:|---:|']
    for name,m in comp['all'].items():lines.append(f"| {name} | {m['micro_f1']:.10f} | {m['macro_f1']:.10f} | {m['TP']}/{m['FP']}/{m['FN']} | {m['exact_count']} | {m['clean_false_alarms']} |")
    lines += ['',f"Gate checks: {json.dumps(gate['checks'],ensure_ascii=False)}. Lý do chặn: {json.dumps(gate['reasons'],ensure_ascii=False)}.",
              f"Known failure counts: {json.dumps(gate['known_failure_counts'],ensure_ascii=False)}. Đọc internal-reviews.private.json và CASEBOOK.vi.private.md cho toàn bộ bằng chứng.",
              f"Internal: normal {summary['normal_calls']}, correction {summary['repair_calls']}, constrained resolver {summary['resolver_calls']} ({summary['resolver_forward_passes']} forward passes); input/output tokens {summary['input_tokens']}/{summary['generated_output_tokens']}; call latency {summary['generation_and_resolver_latency_s']:.3f}s.",
              f"Renderer experiment riêng: {json.dumps(renderer,ensure_ascii=False)}. Hai prompt dùng cùng projection, không phải tái lập end-to-end v1.4.",
              f"Nguồn/family độc lập: {len(source_counts)}/{len(families)} trên30 ID. Các Level lặp nguồn không phải30 bằng chứng tổng quát hóa độc lập.",
              'Factual correctness, taxonomy và Level/style được đánh giá riêng. Automated-agent qualitative review không độc lập như đánh giá người; cấu trúc/range hợp lệ không chứng minh diagnosis đúng.',
              'Giữ BF16 thực tế, pinned revision, greedy seed42 và ngân sách cũ. config.resolved.json ghi dtype/device/revision/VRAM. Compiler syntax-only không link/chạy/test chương trình.',
              'comparison.private.json chứa all30, fixed26 v1.4-resolved và cùng tập resolved; per-label recall, F1, exact/invalid và clean false alarms. Không chọn subset thuận lợi để quyết định public.',
              'Đường dẫn root/branch không đổi: /workspace/llm-final-project-arm-d-plus, fix/task3-strict-feedback. Không push hoặc submit leaderboard.']
    (out/'REPORT.vi.md').write_text('\n\n'.join(lines)+'\n')
    return gate


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();print(json.dumps(build(a.out),ensure_ascii=False))
