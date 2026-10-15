import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.task2.data import load_task2
from src.task2.compile import attach_compile_logs
from src.task2.evaluator import f1_scores
from src.task2.expert_classifier import diagnose_submission

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ds_gold = load_task2("data/sample_dataset")
    [samples], _ = attach_compile_logs({}, [ds_gold.samples])

    gold_map = {s.sample_id: s.labels for s in samples}
    pred_map = {s.sample_id: diagnose_submission(s) for s in samples}

    res = f1_scores(gold_map, pred_map)
    print("Gold 32 Benchmark:")
    print("  Macro-F1:", round(res["macro_f1"], 4))
    print("  Micro-F1:", round(res["micro_f1"], 4))
    print("  Exact Match:", round(res["exact_match"], 4))
    for lab, metrics in res["per_label"].items():
        if metrics["support"] > 0 or metrics["n_pred"] > 0:
            p = round(metrics["precision"], 3) if metrics["precision"] else 0
            r = round(metrics["recall"], 3) if metrics["recall"] else 0
            f = round(metrics["f1"], 3) if metrics["f1"] else 0
            print(f"  {lab:15}: P={p} R={r} F1={f} Supp={metrics['support']} Pred={metrics['n_pred']}")

if __name__ == "__main__":
    main()
