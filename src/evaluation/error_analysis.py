"""Error analysis: cases where the model deviates strongly from the teacher."""
from __future__ import annotations

from collections import Counter, defaultdict

from src.data.loader import DIMENSIONS, Sample


def _compile_signal(s: Sample) -> str:
    log = s.compile_log or ""
    if any(" error:" in ln or "fatal error" in ln for ln in log.splitlines()):
        return "compile_error"
    return "warning" if log.strip() else "clean"


def _test_rate(s: Sample) -> str:
    if not s.test_report:
        return "-"
    return f"{sum(t['passed'] for t in s.test_report)}/{len(s.test_report)}"


def classify_error(s: Sample, p: dict) -> list[str]:
    """Heuristic tags explaining *why* a prediction is off (for grouping in the report)."""
    g, r = s.gold_rubric, p["rubric"]
    tags = []
    if not p["parse_ok"]:
        tags.append("parse_failure")
    if g["compilable"] != r["compilable"]:
        sig = _compile_signal(s)
        tags.append(f"compilable_mismatch(gold={g['compilable']},log={sig})")
    if p["rule_trace"] and any(t.startswith("prereq") for t in p["rule_trace"]):
        tags.append("prereq_rule_fired")
    if s.exam_type == "multi_problem" and g["logic"] == 0 and g["compilable"] == 1 and r["logic"] > 0:
        tags.append("missed_prereq_failure")
    if g["io_format"] != r["io_format"]:
        tags.append("io_format_mismatch")
    if abs(g["logic"] - r["logic"]) >= 2:
        tags.append("logic_off_by_>=2")
    if s.test_report and _test_rate(s).startswith("0/") and g["logic"] >= 2:
        tags.append("tests_fail_but_teacher_lenient")
    return tags or ["other"]


def error_analysis(preds: list[dict], samples: dict[str, Sample], threshold: int = 2) -> dict:
    rows = []
    for p in preds:
        s = samples[p["sample_id"]]
        if not s.has_gold:
            continue
        diff = p["total_score"] - s.gold_total
        rows.append({
            "sample_id": s.sample_id,
            "exam_id": s.exam_id,
            "gold_total": s.gold_total,
            "pred_total": p["total_score"],
            "llm_total": p["total_llm"],
            "diff": diff,
            "dim_diff": {d: p["rubric"][d] - s.gold_rubric[d] for d in DIMENSIONS if p["rubric"][d] != s.gold_rubric[d]},
            "compile": _compile_signal(s),
            "tests": _test_rate(s),
            "problems": p.get("problems", {}),
            "rule_trace": p.get("rule_trace", []),
            "rationale": (p.get("rationale") or "")[:300],
            "tags": classify_error(s, p),
        })
    big = sorted((r for r in rows if abs(r["diff"]) >= threshold), key=lambda r: -abs(r["diff"]))
    tag_counts = Counter(t.split("(")[0] for r in big for t in r["tags"])
    by_exam = defaultdict(lambda: {"n": 0, "n_big": 0, "over": 0, "under": 0})
    for r in rows:
        e = by_exam[r["exam_id"]]
        e["n"] += 1
        if abs(r["diff"]) >= threshold:
            e["n_big"] += 1
            e["over" if r["diff"] > 0 else "under"] += 1
    return {"threshold": threshold, "n": len(rows), "n_big": len(big), "tag_counts": dict(tag_counts),
            "by_exam": dict(by_exam), "cases": big, "all": rows}


def to_markdown(ea: dict, title: str = "Error analysis") -> str:
    lines = [f"# {title}", "",
             f"Samples: {ea['n']} — deviating by >= {ea['threshold']} points: **{ea['n_big']}**", ""]
    lines += ["## By exam", "", "| exam | n | big errors | over-scored | under-scored |", "|---|---|---|---|---|"]
    for e, v in sorted(ea["by_exam"].items()):
        lines.append(f"| {e} | {v['n']} | {v['n_big']} | {v['over']} | {v['under']} |")
    lines += ["", "## Error tags (big errors)", "", "| tag | count |", "|---|---|"]
    for t, c in sorted(ea["tag_counts"].items(), key=lambda x: -x[1]):
        lines.append(f"| {t} | {c} |")
    lines += ["", "## Cases", "",
              "| sample | gold | pred | llm(before rules) | Δ | dims Δ | compile | tests | problems | tags |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for r in ea["cases"]:
        dims = ", ".join(f"{d}{v:+d}" for d, v in r["dim_diff"].items())
        probs = " ".join(f"{k}:{v}" for k, v in r["problems"].items())
        lines.append(f"| {r['sample_id']} | {r['gold_total']} | {r['pred_total']} | {r['llm_total']} | "
                     f"{r['diff']:+d} | {dims} | {r['compile']} | {r['tests']} | {probs} | {'; '.join(r['tags'])} |")
    lines += ["", "### Model rationale for each case", ""]
    for r in ea["cases"]:
        lines.append(f"- **{r['sample_id']}** ({'; '.join(r['rule_trace']) or 'no rule fired'}): {r['rationale']}")
    return "\n".join(lines) + "\n"
