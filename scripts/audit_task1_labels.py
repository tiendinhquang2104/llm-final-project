"""Audit the Task 1 labels for internal inconsistencies (data-quality evidence for the report).

Uses the teacher feedback ONLY to audit labels — never as model input (that would be leakage).
Checks:
  1. total_score == sum(rubric)
  2. compile_log says "error" but compilable = 1 (and vice versa)
  3. multi_problem: feedback says the prerequisite failed, yet dependent dimensions got credit
  4. single_problem: 0 public tests passed but logic >= 2 (or all passed but logic < 4)
  5. exam metadata: problem weights in exams.json vs. weights written in the statement
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Windows consoles/pipes default to cp1252; logs contain Vietnamese.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from src.data.loader import load_task1  # noqa: E402
from src.task1.prerequisite_rules import policy_from_exam  # noqa: E402
from src.utils.config import load_config  # noqa: E402

base = load_config(ROOT / "configs" / "task1" / "base.yaml")
ap = argparse.ArgumentParser()
ap.add_argument("--data-root", default=str(ROOT / base["data"]["root"]))
ap.add_argument("--out", default=str(ROOT / "outputs" / "task1" / "label_audit.json"))
a = ap.parse_args()

ds = load_task1(a.data_root)
fb_path = Path(a.data_root) / "task3_feedback.json"
feedback = {}
if fb_path.exists():
    feedback = {s["sample_id"]: s["output"].get("feedback", "")
                for s in json.loads(fb_path.read_text(encoding="utf-8"))["samples"]}

PREREQ_FAIL_RE = re.compile(r"(câu 1 là (câu )?tiên quyết|P1 (đọc file )?sai|P1 SV hardcode|P1 gán cứng|P1:? lỗi)", re.I)
issues = {k: [] for k in ("total_mismatch", "compile_log_vs_label", "prereq_violation", "tests_vs_logic", "exam_weights")}

for s in ds.samples:
    g = s.gold_rubric
    if s.gold_total != sum(g.values()):
        issues["total_mismatch"].append(s.sample_id)
    log = s.compile_log or ""
    has_err = any(" error:" in ln or "fatal error" in ln for ln in log.splitlines())
    if has_err != (g["compilable"] == 0):
        issues["compile_log_vs_label"].append({"sample_id": s.sample_id, "log_error": has_err,
                                               "compilable": g["compilable"], "log_head": log[:160]})
    pol = policy_from_exam(ds.exams[s.exam_id])
    fb = feedback.get(s.sample_id, "")
    if pol.prerequisites and PREREQ_FAIL_RE.search(fb):
        credited = {d: g[d] for d in pol.zero_on_prereq_fail if g[d] > 0}
        if credited:
            issues["prereq_violation"].append({"sample_id": s.sample_id, "total": s.gold_total,
                                               "credited_dims": credited, "feedback": fb[:200]})
    if s.test_report:
        rate = sum(t["passed"] for t in s.test_report) / len(s.test_report)
        if (rate == 0 and g["logic"] >= 2) or (rate == 1 and g["logic"] < 4):
            issues["tests_vs_logic"].append({"sample_id": s.sample_id, "pass_rate": rate, "logic": g["logic"],
                                             "io_format": g["io_format"]})

for eid, e in ds.exams.items():
    stated = [float(x) for x in re.findall(r"\*\*Problem \d+ \((\d+(?:\.\d+)?) điểm\)", e.get("statement", ""))]
    meta = [p.get("max_score") for p in e.get("problems", [])]
    if stated and stated != meta:
        issues["exam_weights"].append({"exam_id": eid, "statement_weights": stated, "exams_json_max_score": meta})

summary = {k: len(v) for k, v in issues.items()}
print(json.dumps(summary, indent=1))
for k, v in issues.items():
    for item in v:
        print(f"[{k}] {json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else item}")
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Path(a.out).write_text(json.dumps({"summary": summary, "issues": issues}, ensure_ascii=False, indent=2), encoding="utf-8")
