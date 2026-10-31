"""Task 2, hướng E: run every submission on tests built from its statement, label with the teacher rules.

    python scripts/run_task2_exec.py [--model-preds outputs/task2/<system>/predictions.json] [--out outputs/task2/exec]

Steps: self-compile (src/task2/compile.py), run the execution oracle (src/task2/exec_oracle.py), turn the signals
into labels (src/task2/exec_rules.py). Where the rules only know that the answer is wrong (not why), the cause labels
of another system's predictions are added (--model-preds, e.g. the F-cls predictions.json); where there is no signal
at all (unknown exam, a harness that does not build with the submission) that system's labels are used as they are.

Writes predictions.json (the public ids of --ids, default: every public sample), signals.jsonl, report.md with the
32 gold samples scored (rules only: the rules were read off these samples, so the number is optimistic) and the
label rates on public. --reference scores the public predictions against LLM reference labels: trial evaluation
only (instructor ruling 2026-10-16), never used to choose anything here.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.task2.cot_runner import load_with_compile  # noqa: E402
from src.task2.evaluator import f1_scores, validate_predictions, write_submission  # noqa: E402
from src.task2.exec_oracle import Oracle, env_compiler, write_results  # noqa: E402
from src.task2.exec_rules import combine, rule_labels  # noqa: E402
from src.task2.labels import LABELS  # noqa: E402
from src.utils.config import load_config  # noqa: E402


def _preds(path) -> dict[str, list[str]]:
    return {x["sample_id"]: x["output"]["taxonomy_error"] for x in json.loads(Path(path).read_text(encoding="utf-8"))}


def _row(name: str, m: dict) -> str:
    per = " | ".join("-" if m["per_label"][lab]["f1"] is None else f"{m['per_label'][lab]['f1']:.2f}" for lab in LABELS)
    return f"| {name} | {m['macro_f1']:.3f} | {m['micro_f1']:.3f} | {per} |"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/task2/base.yaml")
    ap.add_argument("--model-preds", help="predictions.json of another system: causes of wrong answers + fallback")
    ap.add_argument("--ids", help="a predictions.json whose sample_ids are the ones to submit (default: all public)")
    ap.add_argument("--reference", help="reference labels (predictions.json format) for a trial score on public")
    ap.add_argument("--out", default="outputs/task2/exec")
    a = ap.parse_args()
    cfg = load_config(ROOT / a.config)
    ccfg, d = cfg.get("compile") or {}, cfg["data"]
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    compiler = env_compiler(ccfg)
    if compiler is None:
        raise SystemExit("no C++ compiler: the oracle needs g++ (Linux) or Docker (macOS)")
    oracle = Oracle(compiler)

    model = _preds(a.model_preds) if a.model_preds else {}
    sets = {}
    for name, root in (("gold", d["gold_root"]), ("public", d["public_root"])):
        ds, cid = load_with_compile(ROOT / root, ccfg, "self", True, ROOT)
        res = oracle.run(ds.samples, ds.exams)
        sets[name] = (ds, res)
        write_results(res, out / f"signals_{name}.jsonl")
        print(f"[exec] {name}: {len(res)} samples, compiler={cid}", flush=True)

    lines = ["# Task 2 — hướng E (execution oracle + teacher rules)", ""]
    gds, gres = sets["gold"]
    gold = {s.sample_id: s.labels for s in gds.samples}
    codes = {s.sample_id: s.code for s in gds.samples}
    rules_gold = {}
    for sid, r in gres.items():
        rl = rule_labels(r, codes[sid])
        rules_gold[sid] = rl.labels if rl else ["Lỗi logic"]
    m_gold = f1_scores(gold, rules_gold)
    head = "| system | macro-F1 | micro-F1 | " + " | ".join(lab.replace("Lỗi ", "") for lab in LABELS) + " |"
    lines += ["## Gold (32, rules only — optimistic: the rules come from these samples)", "", head,
              "|" + "---|" * (3 + len(LABELS)), _row("rules", m_gold), ""]

    pds, pres = sets["public"]
    pcodes = {s.sample_id: s.code for s in pds.samples}
    ids = list(_preds(a.ids)) if a.ids else [s.sample_id for s in pds.samples]
    pred, reasons = {}, Counter()
    for sid in ids:
        rl = rule_labels(pres[sid], pcodes[sid])
        pred[sid] = combine(rl, model.get(sid))
        reasons[("no signal" if rl is None else rl.reason.split(" (")[0], "model" if model.get(sid) is not None else "-")] += 1
    sub = write_submission(out / "predictions.json", pred, ids)
    errs = validate_predictions(sub, ids)
    rate = {lab: round(sum(lab in v for v in pred.values()) / len(pred), 3) for lab in LABELS}
    lines += [f"## Public ({len(ids)} predictions, format errors: {len(errs)})", "",
              f"model preds: {a.model_preds or 'none'}", "",
              "| label | rate |", "|---|---|"] + [f"| {lab} | {rate[lab]:.3f} |" for lab in LABELS]
    lines += ["", "| rule | source of causes | n |", "|---|---|---|"]
    lines += [f"| {r} | {s} | {n} |" for (r, s), n in reasons.most_common()]
    if a.reference:
        ref = {k: v for k, v in _preds(a.reference).items() if k in pred}
        m_ref = f1_scores(ref, {k: pred[k] for k in ref})
        lines += ["", f"## Trial score vs reference labels ({len(ref)}, NOT ground truth)", "", head,
                  "|" + "---|" * (3 + len(LABELS)), _row("this run", m_ref)]
        print(f"[exec] vs reference: macro-F1 {m_ref['macro_f1']:.3f}", flush=True)
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[exec] gold (rules, optimistic): macro-F1 {m_gold['macro_f1']:.3f}; public: {len(sub)} predictions "
          f"-> {out / 'predictions.json'}", flush=True)


if __name__ == "__main__":
    main()
