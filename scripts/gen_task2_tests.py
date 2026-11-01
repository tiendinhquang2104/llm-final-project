"""E2 step 1: generate the test suite of every exam from its statement with the local LLM (src/task2/test_gen.py).

    python scripts/gen_task2_tests.py --backend mlx            # Apple Silicon, Qwen2.5-Coder-7B 4-bit
    python scripts/gen_task2_tests.py --backend hf             # Kaggle GPU, Qwen2.5-Coder-7B fp16

One suite per exam, cached in --cache (generations and suites): a rerun only builds the missing ones. Exams are
those of the gold set and of the public release (--sets). The gold multi-problem exam ships no data file; for the
evaluation of the gold samples only, --gold-data-file gives it one (the file named in its statement).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.llm.local_backend import make_local_backend  # noqa: E402
from src.task2.data import load_task2  # noqa: E402
from src.task2.exec_oracle import env_compiler  # noqa: E402
from src.task2.test_gen import SuiteBuilder  # noqa: E402
from src.utils.config import load_config  # noqa: E402

BACKENDS = {"mlx": {"mlx": {"model": "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"}},
            "hf": {"hf": {"model": "Qwen/Qwen2.5-Coder-7B-Instruct", "dtype": "float16"}}}


def suites_for(sets, cfg, builder, gold_data_file=None, exams_filter=None) -> dict:
    d = cfg["data"]
    out = {}
    for name in sets:
        root = ROOT / d[f"{name}_root"]
        ds = load_task2(root)
        data_dir = root / "data_files"
        for eid, exam in ds.exams.items():
            if exams_filter and eid not in exams_filter:
                continue
            if name == "gold" and exam.get("exam_type") == "multi_problem" and not exam.get("data_file") and gold_data_file:
                exam = {**exam, "data_file": Path(gold_data_file).name}
                data_dir = Path(gold_data_file).parent
            out[eid] = builder.build(exam, data_dir)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/task2/base.yaml")
    ap.add_argument("--backend", choices=list(BACKENDS), default="mlx")
    ap.add_argument("--model", help="override the model id")
    ap.add_argument("--sets", nargs="+", default=["gold", "public"], choices=["gold", "public"])
    ap.add_argument("--exams", nargs="*", help="only these exam ids")
    ap.add_argument("--gold-data-file", help="data file of the gold multi-problem exam (evaluation of gold only)")
    ap.add_argument("--cache", default="outputs/task2/_testgen")
    ap.add_argument("--k", type=int, default=6, help="reference solutions sampled per exam")
    a = ap.parse_args()
    cfg = load_config(ROOT / a.config)
    compiler = env_compiler(cfg.get("compile") or {})
    if compiler is None:
        raise SystemExit("no C++ compiler: test generation needs g++ (Linux) or Docker (macOS)")
    settings = json.loads(json.dumps(BACKENDS[a.backend]))
    if a.model:
        settings[a.backend]["model"] = a.model
    llm = make_local_backend(a.backend, settings)
    builder = SuiteBuilder(llm, compiler, ROOT / a.cache, k=a.k)
    suites = suites_for(a.sets, cfg, builder, a.gold_data_file, set(a.exams or []))
    index_path = ROOT / a.cache / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    for eid, s in suites.items():
        index[eid] = s.to_json() if s else None
        print(f"[testgen] {eid}: " + ("no suite" if s is None else f"{len(s.tests)} tests {s.stats}"), flush=True)
    index_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")  # read by run_task2_exec.py
    print(f"[testgen] model {getattr(llm, 'model', '?')} revision {getattr(llm, 'revision', None)}", flush=True)


if __name__ == "__main__":
    main()
