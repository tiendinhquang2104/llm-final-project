"""Write a Markdown statistics report for a generated synthetic dataset.

Reads the dataset (task files, provenance, build_stats.json, validation.json if present) and writes
counts and distributions for all three tasks, the problem bank, code shape, quality checks and the
plan-vs-actual comparison. Contains no code, only aggregates.

Usage:
    python scripts/synth_stats.py --data data/synth/v1 --out docs/synth_v1_stats.md
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from datetime import date
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.synth import quota  # noqa: E402

DIMS = ("compilable", "io_format", "logic", "edge_case", "complexity", "code_quality")
DIM_MAX = {"compilable": 1, "io_format": 1, "logic": 4, "edge_case": 2, "complexity": 1, "code_quality": 1}
LABELS = ["Lỗi biên dịch", "Lỗi nhập/xuất", "Lỗi logic", "Lỗi vòng lặp", "Lỗi mảng/chuỗi", "Lỗi hàm",
          "Lỗi edge case", "Lỗi thuật toán", "Lỗi hard-code", "Lỗi style"]
LEVELS = ["Level 1 - Gợi ý nhẹ", "Level 2 - Chẩn đoán", "Level 3 - Gợi ý sửa", "Level 4 - Lời giải mẫu"]
RULE_DESC = {
    "S0": "rỗng / comment hết", "S1": "không biên dịch được", "S2": "lặp vô hạn / bỏ dở",
    "S3": "sai token + sai hết", "S4": "logic sai", "S5": "thừa ký tự output", "S6": "đúng hết",
    "S7": "hard-code đáp án", "S8": "brute force + sai biên", "S9": "sai token + sai một phần",
    "S10": "sai ≥2 nhóm biên", "S11": "sai 1 nhóm biên", "S12": "đúng nhưng style kém",
    "M1": "không biên dịch được", "M2": "lặp vô hạn", "M3": "P1 hỏng (tiên quyết)", "M4": "cộng điểm theo câu",
}


def load(d: Path):
    j = lambda n: json.loads((d / n).read_text(encoding="utf-8"))
    t1, t2, t3 = j("task1_grading.json")["samples"], j("task2_error_taxonomy.json")["samples"], j("task3_feedback.json")["samples"]
    exams = j("exams.json")["exams"]
    prov = {}
    pf = d / "provenance.jsonl"
    if pf.exists():
        for line in pf.read_text(encoding="utf-8").splitlines():
            if line.strip():
                p = json.loads(line)
                prov[p["sample_id"]] = p
    return t1, t2, t3, exams, prov


def pct(n: int, total: int) -> str:
    return f"{n} ({n / total:.0%})" if total else str(n)


def table(header: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def bar(n: int, scale: int) -> str:
    return "█" * max(1, round(n / scale)) if n else ""


def code_lines(d: Path, samples: list[dict]) -> list[int]:
    out = []
    for s in samples:
        f = d / s["input"]["code_file"]
        if f.exists():
            out.append(len(f.read_text(encoding="utf-8", errors="replace").splitlines()))
    return out


def q(xs: list[int], p: float) -> int:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * (len(xs) - 1)))] if xs else 0


def split_section(d: Path, name: str, is_train: bool) -> list[str]:
    t1, t2, t3, exams, prov = load(d)
    n = len(t1)
    single = [s for s in t1 if s["input"]["exam_type"] == "single_problem"]
    multi = [s for s in t1 if s["input"]["exam_type"] == "multi_problem"]
    L = []
    L.append(f"## {name}\n")
    L.append(table(["Mục", "Số lượng"], [
        ["Đề", f"{len(exams)} ({sum(e['exam_type'] == 'single_problem' for e in exams)} single, "
               f"{sum(e['exam_type'] == 'multi_problem' for e in exams)} multi)"],
        ["Bài nộp (Task 1 = Task 2)", f"{n} ({len(single)} single, {len(multi)} multi)"],
        ["Record Task 3", f"{len(t3)} ({len(t3) - n} bản nhân bản mức khác)"],
    ]))
    L.append("")

    # ---- Task 1
    L.append("### Task 1 — chấm điểm rubric\n")
    tot = Counter(s["output"]["total_score"] for s in t1)
    tot_s = Counter(s["output"]["total_score"] for s in single)
    tot_m = Counter(s["output"]["total_score"] for s in multi)
    scale = max(1, max(tot.values()) // 30)
    L.append("**Phân bố tổng điểm**\n")
    L.append(table(["Tổng", "Single", "Multi", "Tất cả", ""],
                   [[k, tot_s.get(k, 0), tot_m.get(k, 0), pct(tot.get(k, 0), n), bar(tot.get(k, 0), scale)] for k in range(11)]))
    if n:
        totals = [s["output"]["total_score"] for s in t1]
        L.append(f"\nTrung bình {statistics.mean(totals):.2f} · trung vị {statistics.median(totals)} · "
                 f"độ lệch chuẩn {statistics.pstdev(totals):.2f}\n")
    rules = Counter(prov.get(s["sample_id"], {}).get("rule", "?") for s in t1)
    if prov:
        L.append("**Theo rule của rulebook** (rule quan sát được khi chạy code)\n")
        rows = []
        for r in sorted(rules, key=lambda x: (x[0], int(x[1:]) if x[1:].isdigit() else 99)):
            vec = next((tuple(s["output"]["rubric"][k] for k in DIMS) for s in t1
                        if prov.get(s["sample_id"], {}).get("rule") == r), ())
            rows.append([r, RULE_DESC.get(r, ""), rules[r], " ".join(map(str, vec)) if r != "M4" else "theo câu"])
        L.append(table(["Rule", "Ý nghĩa", "Số bài", "C IO L E X Q"], rows))
        L.append("")
    L.append("**Phân bố từng chiều rubric**\n")
    rows = []
    for d_ in DIMS:
        c = Counter(s["output"]["rubric"][d_] for s in t1)
        rows.append([f"{d_} (0–{DIM_MAX[d_]})"] + [c.get(v, 0) if v <= DIM_MAX[d_] else "" for v in range(5)])
    L.append(table(["Chiều", "=0", "=1", "=2", "=3", "=4"], rows))
    if multi and prov:
        states = Counter(tuple((prov[s["sample_id"]].get("observed_states") or {}).values())
                         for s in multi if prov.get(s["sample_id"], {}).get("observed_states"))
        L.append("\n**Đề nhiều câu — trạng thái P1..P4 quan sát được (top 10)**\n")
        L.append(table(["P1 / P2 / P3 / P4", "Số bài"], [[" / ".join(k), v] for k, v in states.most_common(10)]))
    L.append("")

    # ---- Task 2
    L.append("### Task 2 — phân loại lỗi đa nhãn\n")
    lab = Counter(l for s in t2 for l in s["output"]["taxonomy_error"])
    card = Counter(len(s["output"]["taxonomy_error"]) for s in t2)
    scale = max(1, max(lab.values(), default=1) // 30)
    L.append(table(["Nhãn", "Số bài", "Tỉ lệ", ""],
                   [[l, lab.get(l, 0), f"{lab.get(l, 0) / n:.0%}" if n else "", bar(lab.get(l, 0), scale)] for l in LABELS]
                   + [["`[]` (không lỗi)", card.get(0, 0), f"{card.get(0, 0) / n:.0%}" if n else "", bar(card.get(0, 0), scale)]]))
    if n:
        L.append(f"\nSố nhãn/bài: trung bình {sum(k * v for k, v in card.items()) / n:.2f} · "
                 + " · ".join(f"{k} nhãn: {v}" for k, v in sorted(card.items())) + "\n")
    pairs = Counter(p for s in t2 for p in combinations(sorted(s["output"]["taxonomy_error"], key=LABELS.index), 2))
    if pairs:
        L.append("**Cặp nhãn hay đi cùng nhau (top 8)**\n")
        L.append(table(["Cặp nhãn", "Số bài"], [[f"{a} + {b}", v] for (a, b), v in pairs.most_common(8)]))
    L.append("")

    # ---- Task 3
    L.append("### Task 3 — phản hồi theo mức\n")
    lv = Counter(s["input"]["target_feedback_level"] for s in t3)
    L.append(table(["Mức", "Số record", "Tỉ lệ"], [[l, lv.get(l, 0), f"{lv.get(l, 0) / len(t3):.0%}" if t3 else ""] for l in LEVELS]))
    lens = [len(s["output"]["feedback"]) for s in t3]
    by_lv = {l: [len(s["output"]["feedback"]) for s in t3 if s["input"]["target_feedback_level"] == l] for l in LEVELS}
    uniq = len({s["output"]["feedback"] for s in t3})
    gpp = sum(1 for s in t3 if s["input"]["target_feedback_level"].startswith("Level 2") and ".cpp:" in s["output"]["feedback"])
    fence = sum(1 for s in t3 if "```" in s["output"]["feedback"])
    L.append("")
    L.append(table(["Chỉ số", "Giá trị"], [
        ["Độ dài feedback (ký tự)", f"trung vị {statistics.median(lens) if lens else 0}, p90 {q(lens, .9)}"],
        ["Độ dài theo mức (trung vị)", " · ".join(f"L{i + 1}: {statistics.median(v) if v else 0}" for i, v in enumerate(by_lv.values()))],
        ["Feedback khác nhau", f"{uniq}/{len(t3)} ({uniq / len(t3):.0%})" if t3 else "0"],
        ["L2 dán log g++", gpp],
        ["Có khối code (chỉ hợp lệ ở L4)", fence],
        ["Input có `taxonomy_error`", sum("taxonomy_error" in s["input"] for s in t3)],
    ]))
    L.append("")

    # ---- per exam
    L.append("### Theo đề\n")
    per = Counter(s["input"]["exam_id"] for s in t1)
    rows = []
    for e in exams:
        eid = e["exam_id"]
        recs = [s for s in t1 if s["input"]["exam_id"] == eid]
        bases = {prov.get(s["sample_id"], {}).get("base_id") for s in recs} - {None}
        totals = Counter(s["output"]["total_score"] for s in recs)
        rows.append([eid, "single" if e["exam_type"] == "single_problem" else "multi", per.get(eid, 0), len(bases),
                     " ".join(f"{k}:{v}" for k, v in sorted(totals.items()))])
    L.append(table(["Đề", "Loại", "Bài", "Bài gốc dùng", "Tổng điểm (điểm:số bài)"], rows))
    L.append("")

    # ---- code + provenance
    L.append("### Code và nguồn gốc\n")
    ls, lm = code_lines(d, single), code_lines(d, multi)
    rows = [["Số dòng code — single", f"trung vị {statistics.median(ls) if ls else 0}, p10 {q(ls, .1)}, p90 {q(ls, .9)}"],
            ["Số dòng code — multi", f"trung vị {statistics.median(lm) if lm else 0}, p10 {q(lm, .1)}, p90 {q(lm, .9)}"]]
    if prov:
        P = [prov[s["sample_id"]] for s in t1 if s["sample_id"] in prov]
        rows += [
            ["Đã kiểm chứng bằng chạy code", pct(sum(bool(p.get("verified")) for p in P), len(P))],
            ["Bài gốc (style_ref)", ", ".join(f"{k}: {v}" for k, v in Counter(
                (p.get("style_ref") or "?").split("+")[-1].split("-pool")[0] for p in P).most_common())],
            ["Fold", ", ".join(f"{k}: {v}" for k, v in Counter(p.get("fold") for p in P).items())],
            ["Cặp đối chứng", len({p.get("pair_id") for p in P if p.get("pair_id")})],
            ["Bẫy", ", ".join(f"{k}: {v}" for k, v in Counter(p.get("trap") for p in P if p.get("trap")).most_common())
             or "0"],
            ["Bài chồng nhiều lỗi (≥2 defect)", sum(len(p.get("defects") or []) >= 2 for p in P)],
        ]
        dfc = Counter(d_ for p in P for d_ in (p.get("defects") or ["CLEAN"]))
        rows.append(["Defect được dùng", ", ".join(f"{k}: {v}" for k, v in dfc.most_common())])
    L.append(table(["Mục", "Giá trị"], rows))
    L.append("")
    return L


def plan_section(d: Path) -> list[str]:
    t1, t2, _, _, prov = load(d)
    L = ["## So với plan (`docs/synth_plan.md`)\n"]
    want = Counter()
    for rule, cnt, _ in quota.SINGLE_BUCKETS:
        want[rule] += cnt
    got = Counter(prov[s["sample_id"]]["rule"] for s in t1 if s["input"]["exam_type"] == "single_problem" and s["sample_id"] in prov)
    rows = [[r, RULE_DESC.get(r, ""), v, got.get(r, 0), "✓" if got.get(r, 0) >= v else f"thiếu {v - got.get(r, 0)}"]
            for r, v in want.items()]
    L.append("**Single — bucket theo rule**\n")
    L.append(table(["Rule", "Ý nghĩa", "Plan", "Thực tế", ""], rows))
    gotm = Counter(s["output"]["total_score"] for s in t1 if s["input"]["exam_type"] == "multi_problem")
    rows = [[t, v, gotm.get(t, 0), "✓" if gotm.get(t, 0) >= v else f"thiếu {v - gotm.get(t, 0)}"] for t, v in quota.MULTI_BUCKETS]
    L.append("\n**Multi — bucket theo tổng điểm** (tổng 3 không đạt được với 2.5 điểm/câu, 15 slot chuyển sang 4–6)\n")
    L.append(table(["Tổng", "Plan", "Thực tế", ""], rows))
    lab = Counter(l for s in t2 for l in s["output"]["taxonomy_error"])
    caps = {"Lỗi logic": 130, "Lỗi edge case": 100}
    rows = [[l, lab.get(l, 0), "✓" if lab.get(l, 0) >= 45 else "thiếu",
             (f"vượt trần {caps[l]}" if lab.get(l, 0) > caps[l] else "✓") if l in caps else "—"] for l in LABELS]
    L.append("\n**Task 2 — chỉ tiêu tối thiểu 45/nhãn và trần**\n")
    L.append(table(["Nhãn", "Số bài", "≥ 45", "Trần"], rows))
    L.append("")
    return L


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(ROOT / "data" / "synth" / "v1"))
    ap.add_argument("--out", default=str(ROOT / "docs" / "synth_v1_stats.md"))
    a = ap.parse_args()
    d = Path(a.data)
    stats = json.loads((d / "build_stats.json").read_text(encoding="utf-8")) if (d / "build_stats.json").exists() else {}
    val = json.loads((d / "validation.json").read_text(encoding="utf-8")) if (d / "validation.json").exists() else []
    L = [f"# Thống kê tập dữ liệu tổng hợp `{d.relative_to(ROOT) if d.is_relative_to(ROOT) else d}`\n",
         f"Sinh ngày {date.today().isoformat()} bằng `scripts/synth_stats.py` (chỉ số liệu tổng hợp, không chứa code).\n"]
    if stats:
        cache = stats.get("run_cache") or {}
        L.append(table(["Thông tin build", "Giá trị"], [
            ["Runner", stats.get("runner", "?")],
            ["Oracle (`exec_report`)", stats.get("oracle_mode", "?")],
            ["Bài gốc / đề (đã chuẩn bị)", ", ".join(sorted({str(v) for v in stats.get("bases_per_exam", {}).values()}))],
            ["Guard public (train)", f"loại {stats.get('guards', {}).get('train', {}).get('dropped_public', '?')}, "
                                     f"Jaccard tối đa {stats.get('guards', {}).get('train', {}).get('max_public_similarity', '?')}"],
            ["Guard trùng lặp (train)", f"loại {stats.get('guards', {}).get('train', {}).get('dropped_dup', '?')}, "
                                        f"bù thêm {stats.get('guards', {}).get('train', {}).get('top_up_added', '?')}"],
            ["Run cache", f"{cache.get('hits', 0)} hit / {cache.get('misses', 0)} miss" if cache else "—"],
            ["Slot chưa lấp được", ", ".join(f"{k}: {v}" for k, v in stats.get("shortfall", {}).items()) or "0"],
        ]))
        L.append("")
    if val:
        fails = [r for r in val if r[0] == "FAIL"]
        warns = [r for r in val if r[0] == "WARN"]
        L.append(f"**Validator (`scripts/validate_synth.py --compile`): {'FAIL' if fails else 'PASS'}** — "
                 f"{len(fails)} FAIL, {len(warns)} WARN\n")
        if fails or warns:
            L.append(table(["Mức", "Kiểm tra", "Chi tiết"], [[s, c, x[:160]] for s, c, x in fails + warns]))
            L.append("")
    L += split_section(d, "Tập train", True)
    if (d / "heldout" / "task1_grading.json").exists():
        L += split_section(d / "heldout", "Tập giữ riêng (heldout, chỉ để đánh giá)", False)
    L += plan_section(d)
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
