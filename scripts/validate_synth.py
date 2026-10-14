"""Validate a generated synthetic dataset against docs/synth_plan.md.

Checks structure, label consistency (rulebook templates), plan quotas (Task 1 buckets, Task 2
per-label minimums, Task 3 level shares), Task 3 level compliance, label leakage in ``exec_report``,
provenance (verification, fold, style_ref, pairs, traps), generation artefacts, identical code with
different labels, and similarity to the public test (must stay < 0.5). With ``--compile`` every
file is recompiled to confirm the ``compilable`` label.

Exit code 1 when any FAIL is found, so it can gate a build.

Usage:
    python scripts/validate_synth.py --data data/synth/v1 [--compile] [--json report.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.synth import quota  # noqa: E402
from src.synth.compliance import check as compliance_check  # noqa: E402

DIMS = {"compilable": 1, "io_format": 1, "logic": 4, "edge_case": 2, "complexity": 1, "code_quality": 1}
LABELS = ["Lỗi biên dịch", "Lỗi nhập/xuất", "Lỗi logic", "Lỗi vòng lặp", "Lỗi mảng/chuỗi", "Lỗi hàm",
          "Lỗi edge case", "Lỗi thuật toán", "Lỗi hard-code", "Lỗi style"]
TEMPLATES = {  # rulebook decision-list templates (C IO L E X Q)
    "S0": (0, 0, 0, 0, 0, 0), "S1": (0, 0, 0, 0, 0, 1), "S2": (1, 0, 0, 0, 0, 1), "S3": (1, 0, 0, 0, 1, 1),
    "S7": (1, 1, 1, 0, 0, 1), "S8": (1, 1, 2, 0, 0, 1), "S9": (1, 0, 2, 1, 1, 1), "S4": (1, 1, 2, 1, 1, 1),
    "S10": (1, 1, 4, 0, 1, 1), "S11": (1, 1, 4, 1, 1, 1), "S5": (1, 0, 4, 2, 1, 1), "S12": (1, 1, 4, 2, 1, 0),
    "S6": (1, 1, 4, 2, 1, 1), "M0": (0, 0, 0, 0, 0, 0), "M1": (0, 0, 0, 0, 0, 0), "M2": (1, 1, 0, 0, 0, 0),
    "M3": (1, 0, 0, 0, 0, 0)}
M4 = {10: [(1, 1, 4, 2, 1, 1)], 9: [(1, 1, 3, 2, 1, 1), (1, 1, 4, 1, 1, 1)], 8: [(1, 1, 2, 2, 1, 1), (1, 1, 3, 1, 1, 1)],
      7: [(1, 1, 2, 1, 1, 1)], 6: [(1, 1, 1, 1, 1, 1)], 5: [(1, 1, 1, 0, 1, 1)], 4: [(1, 1, 1, 0, 0, 1)],
      3: [(1, 1, 0, 0, 0, 1)], 2: [(1, 1, 0, 0, 0, 0)], 1: [(1, 0, 0, 0, 0, 0)], 0: [(0, 0, 0, 0, 0, 0)]}
LEAK_RE = re.compile(r"^\s*(defect|rule|label|bucket|taxonomy)\s*:", re.MULTILINE | re.IGNORECASE)
ARTEFACT_RES = {"_vN suffix": re.compile(r"\b[A-Za-z]+_v\d+\b"), "#include <x..>": re.compile(r"#include\s*<x\d"),
                "#include <=": re.compile(r"#include\s*<=")}


class Report:
    def __init__(self):
        self.rows: list[tuple[str, str, str]] = []

    def add(self, sev: str, check: str, detail) -> None:
        self.rows.append((sev, check, detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)))

    @property
    def failed(self) -> bool:
        return any(sev == "FAIL" for sev, _, _ in self.rows)

    def print(self) -> None:
        for sev, check, detail in self.rows:
            print(f"[{sev:4}] {check}: {detail}")


def _load(d: Path, name: str):
    return json.loads((d / name).read_text(encoding="utf-8"))


def _jl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []


def _split(d: Path):
    t1 = _load(d, "task1_grading.json")["samples"]
    t2 = _load(d, "task2_error_taxonomy.json")["samples"]
    t3 = _load(d, "task3_feedback.json")["samples"]
    ex = _load(d, "exams.json")
    ex = ex["exams"] if isinstance(ex, dict) else ex
    prov = {p["sample_id"]: p for p in _jl(d / "provenance.jsonl")}
    xr = {x["sample_id"]: x["exec_report"] for x in _jl(d / "exec_reports.jsonl")}
    return t1, t2, t3, {e["exam_id"]: e for e in ex}, prov, xr


def _shingles(code: str, k: int = 5) -> set[str]:
    code = re.sub(r"//[^\n]*|/\*.*?\*/", " ", code, flags=re.S)
    toks = re.findall(r"[A-Za-z_]\w*|\d+|\S", code)
    if not toks:
        return set()  # empty / fully commented: no content, cannot leak anything
    return {" ".join(toks[i:i + k]) for i in range(max(1, len(toks) - k + 1))}


def _jacc(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def check_split(rep: Report, d: Path, name: str, *, is_train: bool) -> dict:
    t1, t2, t3, exams, prov, xr = _split(d)
    tag = f"{name}:"
    rep.add("info", tag + "counts", f"t1={len(t1)} t2={len(t2)} t3={len(t3)} exams={len(exams)} prov={len(prov)}")
    ids = [s["sample_id"] for s in t1]
    if len(set(ids)) != len(ids):
        rep.add("FAIL", tag + "dup-id", "sample_id trùng trong task1")
    if set(ids) != {s["sample_id"] for s in t2}:
        rep.add("FAIL", tag + "id-align", "task1 và task2 khác tập sample_id")
    base3 = {re.sub(r"-L\d$", "", s["sample_id"]) for s in t3}
    if not base3 <= set(ids):
        rep.add("FAIL", tag + "id-align", f"{len(base3 - set(ids))} id Task3 không có trong Task1")
    missing = [s["sample_id"] for s in t1 if not (d / s["input"]["code_file"]).exists()]
    if missing:
        rep.add("FAIL", tag + "code-file", f"{len(missing)} code_file không tồn tại trong {d}, vd {missing[:3]}")
    if any(s["input"]["exam_id"] not in exams for s in t1):
        rep.add("FAIL", tag + "exam-ref", "có exam_id không nằm trong exams.json của split")
    nprov = [i for i in ids if i not in prov]
    if nprov:
        rep.add("FAIL", tag + "provenance", f"{len(nprov)} record thiếu provenance")

    # ---- Task 1 ----
    bad_tpl = []
    for s in t1:
        r, T = s["output"]["rubric"], s["output"]["total_score"]
        vec = tuple(r[k] for k in DIMS)
        if any(not 0 <= r[k] <= m for k, m in DIMS.items()) or sum(vec) != T:
            bad_tpl.append((s["sample_id"], "range/sum"))
            continue
        rule = prov.get(s["sample_id"], {}).get("rule")
        ok = TEMPLATES.get(rule) == vec if rule in TEMPLATES else (rule == "M4" and vec in M4.get(T, []))
        if not ok:
            bad_tpl.append((s["sample_id"], rule, vec))
    rep.add("FAIL" if bad_tpl else "ok", tag + "t1-template", f"{len(bad_tpl)} sai template" + (f": {bad_tpl[:3]}" if bad_tpl else ""))
    tot = Counter(s["output"]["total_score"] for s in t1)
    rep.add("info", tag + "t1-total", dict(sorted(tot.items())))
    unverified = [i for i in ids if not prov.get(i, {}).get("verified")]
    if unverified:
        rep.add("FAIL", tag + "verified", f"{len(unverified)} record chưa được kiểm chứng bằng chạy code")

    # identical code, different label
    t2_of = {s["sample_id"]: s["output"]["taxonomy_error"] for s in t2}
    groups = defaultdict(set)
    for s in t1:
        src = (d / s["input"]["code_file"]).read_text(encoding="utf-8", errors="replace") if (d / s["input"]["code_file"]).exists() else ""
        groups[hashlib.sha1(src.encode()).hexdigest()].add((s["output"]["total_score"], tuple(sorted(t2_of[s["sample_id"]]))))
    conflict = sum(1 for v in groups.values() if len(v) > 1)
    rep.add("FAIL" if conflict else "ok", tag + "same-code-diff-label", f"{conflict} nhóm code giống hệt nhưng nhãn khác")

    if is_train:
        singles = [s for s in t1 if s["input"]["exam_type"] == "single_problem"]
        multis = [s for s in t1 if s["input"]["exam_type"] == "multi_problem"]
        rep.add("info", tag + "split", f"single {len(singles)} (plan {quota.TOTAL_SINGLE}), multi {len(multis)} (plan {quota.TOTAL_MULTI})")
        plan_s = Counter()
        for rule, count, _ in quota.SINGLE_BUCKETS:
            plan_s[rule] += count
        got_s = Counter(prov[s["sample_id"]]["rule"] for s in singles)
        diff = {k: (got_s.get(k, 0), v) for k, v in plan_s.items() if abs(got_s.get(k, 0) - v) > max(3, 0.15 * v)}
        rep.add("WARN" if diff else "ok", tag + "single-buckets", f"(thực tế, plan) lệch: {diff}" if diff else "khớp plan")
        plan_m = dict(quota.MULTI_BUCKETS)
        got_m = Counter(s["output"]["total_score"] for s in multis)
        diff = {k: (got_m.get(k, 0), v) for k, v in plan_m.items() if abs(got_m.get(k, 0) - v) > max(3, 0.15 * v)}
        rep.add("WARN" if diff else "ok", tag + "multi-buckets", f"(thực tế, plan) lệch: {diff}" if diff else "khớp plan")
        if any(tot.get(k, 0) == 0 for k in range(11)):
            rep.add("WARN", tag + "t1-coverage", f"thiếu mức điểm {[k for k in range(11) if not tot.get(k)]}")

    # ---- Task 2 ----
    lab, nlab, empty = Counter(), [], 0
    for s in t2:
        L = s["output"]["taxonomy_error"]
        if any(l not in LABELS for l in L) or len(set(L)) != len(L):
            rep.add("FAIL", tag + "t2-labels", f"{s['sample_id']}: nhãn lạ/trùng {L}")
        lab.update(L)
        nlab.append(len(L))
        empty += not L
    rep.add("info", tag + "t2-dist", f"[]={empty}, {sum(nlab) / max(1, len(nlab)):.2f} nhãn/bài, {dict(lab.most_common())}")
    t2m = {s["sample_id"]: s["output"]["taxonomy_error"] for s in t2}
    incons = [s["sample_id"] for s in t1 if (s["output"]["total_score"] == 10) != (t2m[s["sample_id"]] == [])
              and prov.get(s["sample_id"], {}).get("rule") != "S12"]
    if incons:
        rep.add("FAIL", tag + "t1-t2", f"{len(incons)} bài 10 điểm có nhãn lỗi hoặc <10 điểm mà nhãn rỗng: {incons[:4]}")
    ce = [s["sample_id"] for s in t1
          if s["output"]["rubric"]["compilable"] == 0 and "Lỗi biên dịch" not in t2m[s["sample_id"]]]
    if ce:
        rep.add("WARN", tag + "t1-t2", f"{len(ce)} bài C=0 thiếu nhãn 'Lỗi biên dịch'")
    if is_train:
        low = [(l, lab[l]) for l in LABELS if lab[l] < 45]
        rep.add("WARN" if low else "ok", tag + "t2-quota", f"dưới 45: {low}" if low else "mọi nhãn ≥ 45")
        for l, cap in (("Lỗi logic", 130), ("Lỗi edge case", 100)):
            if lab[l] > cap:
                rep.add("WARN", tag + "t2-cap", f"{l} = {lab[l]} > trần {cap}")

    # ---- Task 3 ----
    if any("taxonomy_error" in s["input"] for s in t3):
        rep.add("FAIL", tag + "t3-input", "Task3 input chứa taxonomy_error")
    mis = [s["sample_id"] for s in t3 if s["output"]["taxonomy_error"] != t2m.get(re.sub(r"-L\d$", "", s["sample_id"]))]
    if mis:
        rep.add("FAIL", tag + "t3-t2", f"{len(mis)} record Task3 có taxonomy khác Task2")
    viol = [(s["sample_id"], compliance_check(s["output"]["feedback"], s["input"]["target_feedback_level"]).violations)
            for s in t3 if not compliance_check(s["output"]["feedback"], s["input"]["target_feedback_level"]).ok]
    rep.add("FAIL" if viol else "ok", tag + "t3-compliance", f"{len(viol)} vi phạm mức: {viol[:3]}" if viol else "không vi phạm")
    lv = Counter(s["input"]["target_feedback_level"][:7] for s in t3)
    rep.add("info", tag + "t3-levels", {k: f"{v} ({v / max(1, len(t3)):.0%})" for k, v in sorted(lv.items())})
    fbs = Counter(s["output"]["feedback"] for s in t3)
    uniq = len(fbs) / max(1, len(t3))
    rep.add("WARN" if uniq < 0.5 else "info", tag + "t3-diversity", f"{len(fbs)}/{len(t3)} feedback khác nhau ({uniq:.0%})")
    gpp = sum(1 for s in t3 if s["input"]["target_feedback_level"].startswith("Level 2")
              and re.search(r"\.cpp:\d+:\d+: (?:fatal )?error:", s["output"]["feedback"]))
    rep.add("info", tag + "t3-gpp-log", f"{gpp} feedback L2 dán log g++")

    # ---- exec_report ----
    leak = [i for i, x in xr.items() if LEAK_RE.search(x)]
    if leak:
        rep.add("FAIL", tag + "exec-leak", f"{len(leak)} exec_report chứa defect/rule/label")
    std = [i for i, x in xr.items() if "labeling only" in x or "standard" in x]
    if std:
        rep.add("FAIL", tag + "exec-source", f"{len(std)} exec_report lấy từ test chuẩn dùng để gán nhãn")
    mismatch = [s["sample_id"] for s in t1 if s["input"].get("exec_report") != xr.get(s["sample_id"])]
    if mismatch:
        rep.add("WARN", tag + "exec-align", f"{len(mismatch)} input.exec_report khác exec_reports.jsonl")

    # ---- provenance ----
    if is_train:
        missing_fields = {"fold", "style_ref", "base_id"} - {k for p in prov.values() for k in p}
        if missing_fields:
            rep.add("FAIL", tag + "prov-fields", f"thiếu {missing_fields}")
        bases = defaultdict(set)
        for p in prov.values():
            bases[p.get("exam_id")].add(p.get("base_id"))
        few = {e: len(b) for e, b in bases.items() if len(b) < 4}
        rep.add("WARN" if few else "ok", tag + "bases", f"đề có < 4 bài gốc: {few}" if few else "mọi đề ≥ 4 bài gốc")
        pairs = defaultdict(list)
        for i in ids:
            if prov[i].get("pair_id"):
                pairs[prov[i]["pair_id"]].append(i)
        t1m = {s["sample_id"]: s["output"]["total_score"] for s in t1}
        same = [p for p, v in pairs.items() if len(v) == 2 and t1m[v[0]] == t1m[v[1]]]
        bad_size = [p for p, v in pairs.items() if len(v) != 2]
        rep.add("FAIL" if same or bad_size else "info", tag + "pairs",
                f"{len(pairs)} cặp (plan 50); cùng nhãn: {len(same)}; sai kích thước: {len(bad_size)}")
        traps = Counter(prov[i].get("trap") for i in ids if prov[i].get("trap"))
        rep.add("info" if 40 <= sum(traps.values()) <= 60 else "WARN", tag + "traps", f"{sum(traps.values())} bẫy (plan ≈50): {dict(traps)}")

    # ---- artefacts & stats ----
    codes = {s["sample_id"]: (d / s["input"]["code_file"]).read_text(encoding="utf-8", errors="replace")
             for s in t1 if (d / s["input"]["code_file"]).exists()}
    for nm, rx in ARTEFACT_RES.items():
        n = sum(1 for c in codes.values() if rx.search(c))
        if n:
            rep.add("FAIL", tag + "artefact", f"{nm}: {n} file")
    lines = [len(c.splitlines()) for c in codes.values()]
    if lines:
        rep.add("info", tag + "code-lines", f"median {statistics.median(lines)}, p10 {sorted(lines)[len(lines) // 10]}, p90 {sorted(lines)[9 * len(lines) // 10]}")
    return {"codes": codes, "labels": {s["sample_id"]: (s["output"]["rubric"]["compilable"], prov.get(s["sample_id"], {}).get("trap"),
                                                         s["input"]["code_file"], s["input"]["exam_type"]) for s in t1}}


def check_public_similarity(rep: Report, codes: dict[str, str], public_root: Path | None) -> None:
    if public_root is None or not public_root.exists():
        rep.add("WARN", "public-sim", "không tìm thấy public test, bỏ qua kiểm tra độ giống")
        return
    pub = [_shingles(p.read_text(encoding="utf-8", errors="replace")) for p in public_root.rglob("*.cpp")]
    sims = {sid: max((_jacc(_shingles(c), p) for p in pub), default=0.0) for sid, c in codes.items()}
    worst = max(sims.values(), default=0.0)
    over = [s for s, v in sims.items() if v >= 0.5]
    rep.add("FAIL" if over else "ok", "public-sim", f"max Jaccard {worst:.2f} so với {len(pub)} bài public; ≥0.5: {len(over)}")


def check_compile(rep: Report, d: Path, info: dict, tag: str) -> None:
    def comp(item):
        sid, (c_label, trap, code_file, exam_type) = item
        src = (d / code_file).read_text(encoding="utf-8", errors="replace")
        if exam_type == "multi_problem":
            # functions only: syntax check with a stub main
            if "main" not in src:
                src += "\nint main() { return 0; }\n"
            cmd = ["g++", "-std=c++11", "-w", "-fsyntax-only", "-x", "c++", "-"]
        else:
            # a stdin/stdout program must build into an executable (an all-comment file has no main)
            cmd = ["g++", "-std=c++11", "-w", "-x", "c++", "-", "-o", "/dev/null"]
        p = subprocess.run(cmd, input=src, capture_output=True, text=True)
        return sid, c_label, trap, p.returncode == 0
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(comp, info["labels"].items()))
    bad = [(sid, c, ok) for sid, c, trap, ok in res if trap != "msvc_style" and bool(c) != ok]
    dead_trap = [sid for sid, c, trap, ok in res if trap == "msvc_style" and ok]
    rep.add("FAIL" if bad else "ok", tag + "compile", f"{len(bad)}/{len(res)} nhãn compilable khác kết quả g++: {bad[:3]}")
    if dead_trap:
        rep.add("WARN", tag + "msvc-trap", f"{len(dead_trap)} bẫy msvc vẫn biên dịch được với g++")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(ROOT / "data" / "synth" / "v1"))
    ap.add_argument("--public-root", default=None)
    ap.add_argument("--compile", action="store_true", help="recompile every file to confirm `compilable`")
    ap.add_argument("--json", default=None, help="write the report rows as JSON")
    a = ap.parse_args()
    d = Path(a.data)
    rep = Report()
    info = check_split(rep, d, "train", is_train=True)
    held = d / "heldout"
    held_info = check_split(rep, held, "heldout", is_train=False) if (held / "task1_grading.json").exists() else None
    if held_info is None:
        rep.add("FAIL", "heldout", "không có heldout/")
    elif not (held / "submissions").exists():
        rep.add("FAIL", "heldout-layout", "code của đề giữ riêng không nằm trong heldout/submissions")
    train_exams = set(_load(d, "exams.json")["exams"] and [e["exam_id"] for e in _load(d, "exams.json")["exams"]])
    if held_info is not None:
        held_exams = {e["exam_id"] for e in _load(held, "exams.json")["exams"]}
        if train_exams & held_exams:
            rep.add("FAIL", "heldout-overlap", f"đề vừa train vừa giữ riêng: {train_exams & held_exams}")
        stray = [p.name for p in (d / "submissions").iterdir() if p.name in held_exams] if (d / "submissions").exists() else []
        if stray:
            rep.add("FAIL", "heldout-layout", f"code đề giữ riêng nằm trong submissions/ của train: {stray}")
    public_root = Path(a.public_root) if a.public_root else next(
        (p for p in (ROOT / "data" / "public-test" / "public_test_release", ROOT / "data" / "raw" / "public_test_release")
         if p.exists()), None)
    check_public_similarity(rep, {**info["codes"], **(held_info["codes"] if held_info else {})}, public_root)
    if a.compile:
        check_compile(rep, d, info, "train:")
        if held_info:
            check_compile(rep, held, held_info, "heldout:")
    rep.print()
    if a.json:
        Path(a.json).write_text(json.dumps(rep.rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nRESULT:", "FAIL" if rep.failed else "PASS")
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
