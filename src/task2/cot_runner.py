"""Shared plumbing for scripts/run_task2_cot.py and scripts/predict_task2_cot.py: log tee, data + compile_log
loading, and run_api followed by the debug report."""
from __future__ import annotations

import contextlib
import sys
import time
from pathlib import Path

from src.task1.experiment import REGISTRY
from src.task2.api_experiment import run_api
from src.task2.compile import attach_compile_logs
from src.task2.cot_report import write_debug_report
from src.task2.data import load_task2
from src.task2.pipeline import Task2ApiPipeline


class _Tee:
    """Loggers may keep this object after tee_log exits (vLLM logs its engine shutdown at interpreter exit):
    the closed log file is then skipped instead of raising "I/O operation on closed file"."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            if not st.closed:
                st.write(s)
        return len(s)

    def flush(self):
        for st in self.streams:
            if not st.closed:
                st.flush()

    def __getattr__(self, name):  # encoding, isatty, ... from the console stream
        return getattr(self.streams[0], name)


@contextlib.contextmanager
def tee_log(path):
    """Copy stdout and stderr into `path` (appended, one header per invocation)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} {' '.join(sys.argv)}\n")
        old = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = _Tee(old[0], f), _Tee(old[1], f)
        try:
            yield path
        finally:
            sys.stdout, sys.stderr = old


def load_with_compile(root, compile_cfg: dict | None, source: str, enabled: bool, project_root):
    """Task 2 dataset with self-compiled (source='self') or shipped (source='dataset') compile logs; with
    compile.run_examples also the test_report of the runs on the statement examples."""
    ds = load_task2(root, keep_empty_compile_log=source == "dataset")
    lists, compiler_id = attach_compile_logs(compile_cfg, [ds.samples], enabled=enabled, root=project_root,
                                             source=source, exams=ds.exams)
    ds.samples[:] = lists[0]
    return ds, compiler_id


def build_retriever(cfg: dict, root, compile_cfg: dict | None, source: str, compile_on: bool,
                    gold_root=None, silver_dir="data/synth/v1"):
    """DemoRetriever over the labelled pools named by cfg["demos"] (gold and/or silver, never public) when
    prompt.few_shot_k > 0; else None. Pools get the same compile_log treatment as the graded samples."""
    k = int((cfg.get("prompt") or {}).get("few_shot_k", 0))
    if k <= 0:
        return None
    from src.data.synth_fetch import silver_roots
    from src.task2.cot_demos import DemoRetriever
    from src.utils.config import load_config
    demos = cfg.get("demos") or {}
    root = Path(root)
    gold, silver = [], []
    if demos.get("gold", True):
        gold_root = gold_root or root / load_config(root / "configs" / "task2" / "base.yaml")["data"]["gold_root"]
        gold = load_with_compile(gold_root, compile_cfg, source, compile_on, root)[0].samples
    if demos.get("silver", True):
        silver = load_with_compile(silver_roots(root / silver_dir)["silver"], compile_cfg, source, compile_on,
                                   root)[0].samples
    retriever = DemoRetriever(gold, silver, k=k, min_gold_sim=float(demos.get("min_gold_sim", 0.3)))
    print(f"demos: {retriever.info()}", flush=True)
    return retriever


def run_and_report(cfg: dict, dataset, samples: list, backend, out_dir, use_cache: bool = True,
                   registry=REGISTRY, demo_pool=()) -> dict:
    """run_api (cached, resumable) then debug.jsonl + report.html in the same folder. The report is written even
    when the run stops early (Ctrl-C, OOM), from whatever was cached."""
    out_dir = Path(out_dir)
    try:
        return run_api(cfg, dataset, samples, backend, out_dir, demo_pool=demo_pool, use_cache=use_cache,
                       registry=registry)
    finally:
        if (out_dir / "raw_outputs.jsonl").exists():
            pipe = Task2ApiPipeline(dataset, None, cfg)
            report = write_debug_report(out_dir, samples, cfg.get("name"), postprocess=pipe.postprocess)
            print(f"report -> {report}")
