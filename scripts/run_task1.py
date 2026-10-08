"""Task 1 entry point: run the prompt experiments + final pipeline through the Gemini API.

Settings: configs/task1/run.yaml (model, throttling, test mode, experiments). API key: GEMINI_API_KEY in .env.

python scripts/run_task1.py
python scripts/run_task1.py --run-config configs/task1/run.yaml
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

from src.data.loader import load_split, load_task1  # noqa: E402
from src.llm.api_client import QuotaExhausted, make_backend  # noqa: E402
from src.task1.evaluator import validate_predictions  # noqa: E402
from src.task1.experiment import predict, run_experiment  # noqa: E402
from src.utils.config import load_config, load_dotenv  # noqa: E402

CONFIG_DIR = ROOT / "configs" / "task1"


def prepare(name: str, settings: dict) -> dict:
    """Load configs/task1/<name>.yaml; run dir = <config>[_test]__<model> so models never overwrite each other."""
    path = CONFIG_DIR / f"{name}.yaml"
    cfg = load_config(path)
    cfg["_config_path"] = str(path.relative_to(ROOT)).replace("\\", "/")
    if settings["run"].get("test_mode"):
        cfg["data"]["sample_ids"] = settings["run"]["test_sample_ids"]
        cfg["name"] += "_test"
    cfg["name"] += "__" + re.sub(r"[^A-Za-z0-9._-]+", "-", settings["gemini"]["model"])
    return cfg


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-config", default=str(CONFIG_DIR / "run.yaml"))
    a = ap.parse_args()
    load_dotenv()
    settings = load_config(a.run_config)
    run = settings["run"]
    out = ROOT / settings.get("output_dir", "outputs/task1")

    base = load_config(CONFIG_DIR / "base.yaml")
    data_root = ROOT / base["data"]["root"]
    if not (data_root / "exams.json").exists():
        sys.exit(f"Không thấy dữ liệu ở {data_root}. Giải nén bộ dữ liệu vào đó (xem data/README.md).")
    ds = load_task1(data_root, base["data"].get("task_file", "task1_grading.json"))
    split = load_split(ROOT / base["data"]["splits_dir"])
    try:
        backend = make_backend(settings["gemini"])
    except RuntimeError as e:
        sys.exit(str(e))

    names = list(run.get("experiments", []))
    if run.get("run_final"):
        names.append("final")
    n_samples = len(run["test_sample_ids"]) if run.get("test_mode") else len(split["val"])
    print(f"model={backend.model} | test_mode={run.get('test_mode')} | configs={names} | "
          f"~{n_samples} bài/run | request cap={backend.max_requests}")

    results = {}
    try:
        for name in names:
            cfg = prepare(name, settings)
            results[cfg["name"]] = run_experiment(cfg, ds, split, backend, out, use_cache=run.get("use_cache", True))

        if run.get("predict_file") and not run.get("test_mode"):
            cfg = prepare("final", settings)
            dest = out / "predictions" / "task1_predictions.json"
            # dev/test sets ship with their own exams.json + submissions/ -> predict_root (default: training data)
            pred_root = ROOT / run["predict_root"] if run.get("predict_root") else data_root
            preds = predict(cfg, pred_root, run["predict_file"], ds, split["train"] + split["val"], backend, dest)
            expected = [p["sample_id"] for p in preds]
            errs = validate_predictions(json.loads(dest.read_text(encoding="utf-8")), expected)
            print(f"predictions -> {dest}  format: {'OK' if not errs else errs[:5]}")
    except QuotaExhausted as e:
        print(f"\nDỪNG: {e}. Các run đã xong vẫn được lưu trong {out}; chạy lại sau sẽ dùng cache.")

    print("\n===== Tóm tắt =====")
    print(f"{'run':56} {'n':>3} {'QWK':>7} {'MAE':>6} {'exact':>6} {'EM6':>6} {'QWK_llm':>8} {'parse_fail':>10}")
    for name, m in results.items():
        mm, lo = m["main"], m["llm_only"]
        print(f"{name:56} {mm['n']:>3} {mm['qwk']:>7.3f} {mm['mae']:>6.2f} {mm['exact_total']:>6.2f} "
              f"{mm['exact_match_mean']:>6.2f} {lo['qwk']:>8.3f} {m['parse_failures']:>10}")
    print("(exact = đúng tổng điểm, EM6 = exact-match trung bình 6 chiều, QWK_llm = trước khi áp rule)")
    usage = backend.info()["usage"]
    if usage["requests"] or usage["failed_requests"]:
        print(f"\nGemini usage: {json.dumps(usage)} | served: {backend.info()['served_models']}")
    else:
        print("\nGemini usage: 0 request (tất cả lấy từ cache)")


if __name__ == "__main__":
    main()
