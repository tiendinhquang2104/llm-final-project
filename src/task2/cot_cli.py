"""Command line shared by scripts/run_task2_cot.py (zero-shot CoT) and scripts/run_task2_cot_sc.py
(CoT + self-consistency): only the default experiment config and the comparison baseline differ.

Scores the labelled set (32 gold by default), optionally labels the public set (--predict, --public-shard K/N to
split it over several Kaggle sessions), writes run.log, debug.jsonl and report.html next to the predictions, and can
export a reusable bundle (--export-bundle). --preflight builds prompts and prints the first one; it never loads a
model or compiles."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from src.data.synth_fetch import silver_roots
from src.llm.local_backend import make_local_backend
from src.task1.experiment import REGISTRY
from src.task2.cot_bundle import export_bundle
from src.task2.cot_runner import build_retriever, load_with_compile, run_and_report, tee_log
from src.task2.labels import LABELS
from src.task2.pipeline import Task2ApiPipeline
from src.utils.config import load_config, load_dotenv


def run_name(config_dir: Path, experiment: str, kind: str, model: str, smoke: bool = False,
             data_tag: str = "") -> str:
    """`data_tag`: "" (32 gold), "silver", "silver_heldout" or "custom" (--gold-root)."""
    tag = re.sub(r"[^A-Za-z0-9._-]+", "-", model)
    return load_config(config_dir / f"{experiment}.yaml")["name"] + ("_smoke" if smoke else "") \
        + (f"_{data_tag}" if data_tag else "") + f"__{kind}__{tag}"


def parse_shard(text: str | None) -> tuple[int, int] | None:
    if not text:
        return None
    k, n = (int(x) for x in text.split("/"))
    if not 1 <= k <= n:
        raise SystemExit(f"--public-shard {text}: cần 1 <= K <= N")
    return k, n


def compare(run_dir: Path, base_dir: Path) -> dict | None:
    """Print and save (compare.json) gold metrics of this run vs a baseline run on the same sample ids."""
    try:
        cur, base = (json.loads((d / "metrics.json").read_text(encoding="utf-8")) for d in (run_dir, base_dir))
        ids = [json.loads((d / "config.json").read_text(encoding="utf-8"))["ids"] for d in (run_dir, base_dir)]
    except FileNotFoundError:
        print(f"so sánh: chưa có kết quả baseline ở {base_dir}")
        return None
    a, b = (m["systems"].get("api") or {} for m in (cur, base))
    if not a or not b:
        return None
    if sorted(ids[0]) != sorted(ids[1]):
        print(f"so sánh: CẢNH BÁO hai lần chạy khác tập bài ({len(ids[0])} vs {len(ids[1])}), số không so trực tiếp")
    out = {"run": run_dir.name, "baseline": base_dir.name, "same_ids": sorted(ids[0]) == sorted(ids[1]),
           "overall": {k: {"run": a.get(k), "baseline": b.get(k)} for k in ("macro_f1", "micro_f1", "exact_match")},
           "per_label_f1": {lab: {"run": a["per_label"][lab]["f1"], "baseline": b["per_label"][lab]["f1"]}
                            for lab in LABELS}}
    fmt = lambda x: "  —  " if x is None else f"{x:.3f}"  # noqa: E731
    print(f"\nso sánh với {base_dir.name}:")
    print(f"{'':<18}{'run':>8}{'baseline':>10}")
    for k, v in out["overall"].items():
        print(f"{k:<18}{fmt(v['run']):>8}{fmt(v['baseline']):>10}")
    for lab, v in out["per_label_f1"].items():
        print(f"  {lab:<16}{fmt(v['run']):>8}{fmt(v['baseline']):>10}")
    (run_dir / "compare.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def main(root: Path, experiment: str, baseline: str | None = None, argv=None, doc: str = "") -> None:
    config_dir = root / "configs" / "task2"
    ap = argparse.ArgumentParser(description=doc)
    ap.add_argument("--run-config", default=str(config_dir / "run_cot.yaml"))
    ap.add_argument("--experiment", default=experiment, help=f"Config in configs/task2 (default: {experiment})")
    ap.add_argument("--backend", choices=("mlx", "hf"))
    ap.add_argument("--gold-root", help="Labelled set to score instead of the 32 gold")
    ap.add_argument("--silver", action="store_true", help="Score the synthetic silver set (data/synth/v1, fetched "
                    "from Drive via SILVER_DRIVE_ID if missing) to tune the prompt")
    ap.add_argument("--silver-heldout", action="store_true", help="Score the silver heldout/ split (4 unseen exams)")
    ap.add_argument("--silver-dir", default="data/synth/v1", help="Where generate-dataset.zip lives / is extracted")
    ap.add_argument("--public-root")
    ap.add_argument("--output-dir")
    ap.add_argument("--preflight", action="store_true", help="Build prompts, print the first one; no model")
    ap.add_argument("--smoke", action="store_true", help="Only run.smoke_sample_ids, no public run")
    ap.add_argument("--ids", nargs="+", help="Only these labelled sample_ids")
    ap.add_argument("--limit", type=int, help="Only the first N labelled samples")
    ap.add_argument("--skip-gold", action="store_true", help="Do not score the labelled set (public run only)")
    ap.add_argument("--predict", action="store_true", help="Also label the public set (same as run.predict: true)")
    ap.add_argument("--public-shard", metavar="K/N", help="Only every N-th public sample starting at K (1-based); "
                    "rerun without it (all cached) to write the full predictions.json")
    ap.add_argument("--no-compile", action="store_true", help="No compile_log (ablation / fallback)")
    ap.add_argument("--compile-source", choices=("self", "dataset"),
                    help="self: compile every sample; dataset: keep compile_log shipped in the data")
    ap.add_argument("--export-bundle", metavar="DIR", help="Write a reusable bundle (config + prompt + model id)")
    ap.add_argument("--save-weights", action="store_true", help="With --export-bundle (hf only): copy weights too")
    a = ap.parse_args(argv)
    load_dotenv()
    if sum(map(bool, (a.gold_root, a.silver, a.silver_heldout))) > 1:
        raise SystemExit("chọn một trong --gold-root / --silver / --silver-heldout")
    data_tag = "silver" if a.silver else "silver_heldout" if a.silver_heldout else "custom" if a.gold_root else ""
    settings = load_config(a.run_config)
    kind = a.backend or settings.get("backend", "mlx")
    run = settings["run"]
    base = load_config(config_dir / "base.yaml")
    compile_cfg = base.get("compile")
    source = a.compile_source or (compile_cfg or {}).get("source", "self")
    compile_on = not (a.no_compile or a.preflight)
    shard = parse_shard(a.public_shard)

    if a.silver or a.silver_heldout:
        labelled_root = silver_roots(root / a.silver_dir)["silver" if a.silver else "heldout"]
    else:
        labelled_root = root / (a.gold_root or base["data"]["gold_root"])
    gold, compiler_id = load_with_compile(labelled_root, compile_cfg, source, compile_on, root)
    public = None
    if (run.get("predict") or a.predict or shard) and not (a.smoke or a.preflight):
        public, _ = load_with_compile(root / (a.public_root or base["data"]["public_root"]), compile_cfg, source,
                                      compile_on, root)
    by_id = gold.by_id()
    if a.smoke:
        samples = [by_id[i] for i in run["smoke_sample_ids"]]
    elif a.ids:
        samples = [by_id[i] for i in a.ids]
    else:
        samples = gold.samples[:a.limit]
    public_samples = public.samples if public else []
    if shard:
        public_samples = public_samples[shard[0] - 1::shard[1]]

    path = config_dir / f"{a.experiment}.yaml"
    cfg = load_config(path)
    cfg["_config_path"] = str(path.relative_to(root))
    cfg["name"] = run_name(config_dir, a.experiment, kind, settings[kind]["model"], a.smoke, data_tag)

    if (cfg.get("prompt") or {}).get("compile_rule") and compile_on and source == "self" and not compiler_id:
        print("CẢNH BÁO: không có compiler (Docker tắt? g++ thiếu?) -> compile_log = None, quy tắc 'Lỗi biên dịch' "
              "theo compile_log KHÔNG được áp dụng và prompt không có compile_log. Bật Docker / cài g++, hoặc dùng "
              "--compile-source dataset.", flush=True)
    retriever = build_retriever(cfg, root, compile_cfg, source, compile_on, silver_dir=a.silver_dir)
    pipe = Task2ApiPipeline(gold, None, cfg, retriever or ())
    first_req = pipe.build_request(samples[0])
    first = first_req["messages"]
    chars = sum(len(m["content"]) for s in samples for m in pipe.build_request(s)["messages"])
    gen = cfg.get("generation", {})
    print(json.dumps({"experiment": a.experiment, "labelled_set": str(labelled_root), "backend": kind, "model": settings[kind]["model"],
                      "generation": gen, "compile_source": source, "compiler": compiler_id,
                      "n_labelled": 0 if a.skip_gold else len(samples), "n_public": len(public_samples),
                      "public_shard": a.public_shard, "completions_per_sample": int(gen.get("n", 1)),
                      "approx_input_tokens": chars // 3, "demos_first_sample": first_req["demos"]},
                     ensure_ascii=False, indent=2))
    if a.preflight:
        print("\n=== SYSTEM ===\n" + first[0]["content"] + "\n\n=== USER ===\n" + first[1]["content"])
        return

    out = Path(a.output_dir) if a.output_dir else root / settings.get("output_dir", "outputs/task2")
    run_dir = out / cfg["name"]
    log_dir = run_dir if not a.skip_gold else out / (cfg["name"] + "_predict")
    with tee_log(log_dir / "run.log"):
        print(f"compile: source={source} compiler={compiler_id}")
        backend = make_local_backend(kind, settings)
        print(f"model: {json.dumps({k: v for k, v in backend.info().items() if k != 'usage'}, ensure_ascii=False)}")
        m = None
        partial = bool(a.smoke or a.ids or a.limit)  # quick checks stay out of experiments/registry.csv
        if not a.skip_gold:
            m = run_and_report(cfg, gold, samples, backend, run_dir, use_cache=run.get("use_cache", True),
                               registry=None if partial else REGISTRY, demo_pool=retriever or ())
            api = m["systems"].get("api") or {}
            print(f"{cfg['name']}: macro-F1={api.get('macro_f1')} micro-F1={api.get('micro_f1')} "
                  f"parse_fail={m['parse_failures']}")
            if baseline:
                compare(run_dir, out / run_name(config_dir, baseline, kind, settings[kind]["model"], a.smoke,
                                                data_tag))
        if public_samples:
            pcfg = {**cfg, "name": cfg["name"] + "_predict"}
            run_and_report(pcfg, public, public_samples, backend, out / pcfg["name"],
                           use_cache=run.get("use_cache", True), registry=None, demo_pool=retriever or ())
            where = out / pcfg["name"] / "predictions.json"
            if shard:
                print(f"predictions (CHỈ shard {a.public_shard}, {len(public_samples)} bài) -> {where}; "
                      "chạy lại không có --public-shard (dùng cache) để có file đủ 360 bài")
            else:
                print(f"predictions -> {where}")
        if a.export_bundle:
            saver = getattr(backend, "save", None) if a.save_weights else None
            if a.save_weights and saver is None:
                print(f"--save-weights: backend {kind} không hỗ trợ lưu trọng số, bundle chỉ ghi model id")
            bundle = export_bundle(a.export_bundle, cfg, kind, backend.info(), {**(compile_cfg or {}),
                                   "source": source, "compiler_id": compiler_id}, m, saver,
                                   demo_pools=retriever.fingerprint() if retriever else None,
                                   run_dir=None if a.skip_gold else run_dir, partial=partial)
            print(f"bundle -> {bundle}")
        print(f"{kind} usage: {json.dumps(backend.info().get('usage'))}")
