"""Build the F-cls records (docs/task2_finetune_plan.md §4): synth v3 + gold + gold mutants + public.

With prompt.exec_summary every prompt also gets the summary of the submission's runs on its exam's test suite
(src/task2/exec_summary.py): gold, mutants and public on the suites generated from their statements
(scripts/gen_task2_tests.py, --suites), synth on the tests of the problem bank. Public records are never trained on.

Every submission is compiled (and, for stdin/stdout exams, run on the statement examples) with the same recipe as
the CoT pipeline, so the classifier sees at training time exactly what it sees at inference. Writes
<out>/records.jsonl (one row per submission, labels only for labelled sources) and <out>/summary.json.

    python scripts/build_task2_cls_data.py --config configs/task2/cls_qwen7b.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.synth_fetch import extract, find_root  # noqa: E402
from src.synth.dedup import max_similarity, signature  # noqa: E402
from src.task2.augment import augment, source_id  # noqa: E402
from src.task2.cls_data import read_jsonl, record, summary, write_jsonl  # noqa: E402
from src.task2.compile import attach_compile_logs  # noqa: E402
from src.task2.cot_runner import load_with_compile  # noqa: E402
from src.task2.exec_summary import summary_text  # noqa: E402
from src.task2.prompts_cot import prompt_lang  # noqa: E402
from src.utils.config import load_config  # noqa: E402


def synth_roots(zip_path: Path, dest: Path) -> list[Path]:
    """Extract the generated set once (dest/<zip stem>/) and return [silver root, heldout root (if any)]."""
    target = dest / zip_path.stem
    if not (target / ".extracted").exists():
        extract(zip_path, target)
        (target / ".extracted").write_text(str(zip_path), encoding="utf-8")
    root = find_root(target)
    return [root] + ([root / "heldout"] if (root / "heldout" / "exams.json").exists() else [])


def public_guard_corpus(public_samples, gold_samples, dup: float = 0.9):
    """Public signatures to guard against, minus the public files that ARE gold samples (the release ships the 32
    labelled samples too; mutating labelled gold code is allowed, mutating test code is not)."""
    gold_sigs = [signature(s.code) for s in gold_samples]
    out, dropped = [], 0
    for s in public_samples:
        sig = signature(s.code)
        if max_similarity(sig, gold_sigs) >= dup:
            dropped += 1
            continue
        out.append(sig)
    return out, dropped


def exec_signals(ccfg: dict, suites_path: Path, bank_dir: Path):
    """A function (dataset, samples, name) -> {sample_id: ExecResult} running the samples on their exam's suite:
    the generated suites of --suites (gold / public exams), the problem bank's tests for the synthetic exams."""
    from src.task2.exec_oracle import Oracle, env_compiler, run_with_probe_fallback
    from src.task2.exec_summary import bank_suites
    from src.task2.test_gen import Suite

    compiler = env_compiler(ccfg)
    if compiler is None:
        raise SystemExit("prompt.exec_summary needs a compiler (g++ or Docker)")
    index = json.loads(suites_path.read_text(encoding="utf-8")) if suites_path.exists() else {}
    if not index:
        print(f"[exec] WARNING: no generated suites at {suites_path}: gold / public prompts say 'no test suite'",
              flush=True)
    suites = {eid: Suite.from_json(v) for eid, v in index.items() if v}
    suites.update(bank_suites(bank_dir))
    oracle = Oracle(compiler)

    def run(ds, samples, name):
        res, dropped = run_with_probe_fallback(oracle, samples, ds.exams, suites)
        with_suite = sum(r.kind is not None for r in res.values())
        print(f"[exec] {name}: {with_suite}/{len(res)} samples ran on a suite"
              + (f"; suites not trusted: {dropped}" if dropped else ""), flush=True)
        return res
    return run


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/task2/cls_qwen7b.yaml")
    ap.add_argument("--synth-zip", help="generated dataset zip (default: data.synth_zip of the config)")
    ap.add_argument("--out", help="output folder (default: data.cls_dir of the config)")
    ap.add_argument("--no-compile", action="store_true", help="skip compile/run (compile_log None): smoke tests only")
    ap.add_argument("--no-public", action="store_true", help="do not build public records")
    ap.add_argument("--suites", default="outputs/task2/_testgen/index.json",
                    help="generated suites (scripts/gen_task2_tests.py), for prompt.exec_summary")
    a = ap.parse_args()

    cfg = load_config(ROOT / a.config)
    d, pcfg, ccfg = cfg["data"], cfg["prompt"], cfg.get("compile") or {}
    out = ROOT / (a.out or d["cls_dir"])
    synth_zip = ROOT / (a.synth_zip or d["synth_zip"])
    compile_on = not a.no_compile and ccfg.get("enabled", True)

    def load(root):
        return load_with_compile(root, ccfg, "self", compile_on, ROOT)

    lang = prompt_lang(pcfg)
    no_sig = summary_text(None, lang)
    signals = None
    if pcfg.get("exec_summary"):
        signals = exec_signals(ccfg, ROOT / a.suites, ROOT / "src" / "synth" / "problems")

    def texts(ds, samples, name):
        """sample_id -> summary text (None when prompt.exec_summary is off)."""
        if signals is None:
            return {}
        res = signals(ds, samples, name)
        return {sid: summary_text(r, lang) for sid, r in res.items()}

    rows = []
    gold, cid = load(ROOT / d["gold_root"])
    print(f"gold: {len(gold.samples)} samples, compiler={cid}", flush=True)
    gtext = texts(gold, gold.samples, "gold")
    for s in gold.samples:
        rows.append(record(gold.exams[s.exam_id], s, "gold", pcfg, fold=s.exam_id, exec_text=gtext.get(s.sample_id),
                           no_signal_text=no_sig))

    mut = augment(gold.samples, max_per_mutator=(cfg.get("augment") or {}).get("max_per_mutator"))
    mut = attach_compile_logs(ccfg, [mut], enabled=compile_on, root=ROOT, source="self", exams=gold.exams)[0][0]
    gold_exam = {s.sample_id: s.exam_id for s in gold.samples}
    mtext = texts(gold, mut, "gold mutants")
    mut_rows = [record(gold.exams[s.exam_id], s, "gold_mut", pcfg, fold=gold_exam[source_id(s.sample_id)],
                       exec_text=mtext.get(s.sample_id), no_signal_text=no_sig) for s in mut]
    print(f"gold mutants: {len(mut_rows)}", flush=True)

    synth_rows, codes = [], {s.sample_id: s.code for s in mut}
    for root in synth_roots(synth_zip, ROOT / d["synth_dir"]):
        ds, _ = load(root)
        codes.update({s.sample_id: s.code for s in ds.samples})
        stext = texts(ds, ds.samples, f"synth {root.name}")
        synth_rows += [record(ds.exams[s.exam_id], s, "synth", pcfg, fold=None, exec_text=stext.get(s.sample_id),
                              no_signal_text=no_sig) for s in ds.samples]
        print(f"synth {root.name}: {len(ds.samples)} samples", flush=True)

    public = None
    if not a.no_public and (ROOT / d["public_root"]).exists():
        public, _ = load(ROOT / d["public_root"])
        print(f"public: {len(public.samples)} samples", flush=True)

    # leakage guard: no training code may resemble a public-test file (MinHash Jaccard < 0.5)
    guard = {"threshold": float(d.get("public_guard", 0.5)), "dropped": [], "public_dupes_of_gold": 0}
    if public is not None:
        corpus, guard["public_dupes_of_gold"] = public_guard_corpus(public.samples, gold.samples)
        kept = []
        for r in mut_rows + synth_rows:
            sim = max_similarity(signature(codes[r["id"]]), corpus)
            (kept.append(r) if sim < guard["threshold"] else guard["dropped"].append({"id": r["id"], "sim": round(sim, 3)}))
        mut_rows = [r for r in kept if r["source"] == "gold_mut"]
        synth_rows = [r for r in kept if r["source"] == "synth"]
    rows += mut_rows + synth_rows
    if public is not None:
        ptext = texts(public, public.samples, "public")
        rows += [record(public.exams[s.exam_id], s, "public", pcfg, fold=None, exec_text=ptext.get(s.sample_id),
                        no_signal_text=no_sig) for s in public.samples]

    ids = [r["id"] for r in rows]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise SystemExit(f"duplicate sample ids across sources: {dup[:5]}")
    write_jsonl(out / "records.jsonl", rows)
    info = {**summary(rows), "compiler": cid, "synth_zip": str(synth_zip.relative_to(ROOT)), "guard": guard,
            "prompt": pcfg}
    (out / "summary.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: info[k] for k in ("n", "by_source", "folds", "empty")}, ensure_ascii=False))
    print(f"guard: dropped {len(guard['dropped'])} training rows (public dupes of gold ignored: "
          f"{guard['public_dupes_of_gold']}) -> {out / 'records.jsonl'}")
    assert len(read_jsonl(out / "records.jsonl")) == len(rows)


if __name__ == "__main__":
    main()
