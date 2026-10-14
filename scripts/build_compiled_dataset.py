"""Build data/public-test/compiled: the public test release with `compile_log` pre-filled (self-compiled, GCC)."""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.task2.compile import CompileCache, compile_args, has_compile_error, make_compiler  # noqa: E402
from src.task2.compiled_dataset import build_compiled_dataset  # noqa: E402
from src.task2.data import load_task2  # noqa: E402
from src.utils.config import load_config  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default=str(ROOT / "data" / "raw" / "public_test_release"))
    ap.add_argument("--out", default=str(ROOT / "data" / "public-test" / "compiled"))
    ap.add_argument("--config", default=str(ROOT / "configs" / "task2" / "clm_base.yaml"))
    ap.add_argument("--no-zip", action="store_true")
    a = ap.parse_args()
    cfg = (load_config(a.config).get("compile")) or {}
    ds = load_task2(a.src)
    comp = make_compiler(cfg.get("backend", "auto"), cfg.get("image", "gcc:13.3.0"),
                         ROOT / cfg.get("workdir", "outputs/task2/_compile_work"))
    if comp is None:
        sys.exit("error: no compiler available (need Docker gcc image on macOS or g++ on Linux); "
                 "refusing to write a dataset with missing compile logs")
    logs = CompileCache(comp, ROOT / cfg.get("cache_dir", "outputs/task2/_compile_cache")).logs(ds.samples)
    out = Path(a.out)
    dst = build_compiled_dataset(a.src, out, logs, make_zip=not a.no_zip)
    recipe = {t: " ".join(compile_args(t)) for t in ("single_problem", "multi_problem")}
    out.joinpath("COMPILE_INFO.txt").write_text(
        f"compiler_id: {comp.compiler_id}\nrecipe: {recipe}\ndate: {datetime.date.today().isoformat()}\n"
        f"samples: {len(ds.samples)}\n", encoding="utf-8")
    n_err = sum(has_compile_error(logs[s.sample_id]) for s in ds.samples)
    print(f"samples: {len(ds.samples)}  with compile errors: {n_err}  compiler: {comp.compiler_id}")
    print(f"folder: {dst}")
    if not a.no_zip:
        print(f"zip: {out / 'public_test_release.zip'}")
    print(f"info: {out / 'COMPILE_INFO.txt'}")


if __name__ == "__main__":
    main()
