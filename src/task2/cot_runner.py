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
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)
        return len(s)

    def flush(self):
        for st in self.streams:
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
    """Task 2 dataset with self-compiled (source='self') or shipped (source='dataset') compile logs."""
    ds = load_task2(root, keep_empty_compile_log=source == "dataset")
    lists, compiler_id = attach_compile_logs(compile_cfg, [ds.samples], enabled=enabled, root=project_root,
                                             source=source)
    ds.samples[:] = lists[0]
    return ds, compiler_id


def run_and_report(cfg: dict, dataset, samples: list, backend, out_dir, use_cache: bool = True,
                   registry=REGISTRY) -> dict:
    """run_api (cached, resumable) then debug.jsonl + report.html in the same folder. The report is written even
    when the run stops early (Ctrl-C, OOM), from whatever was cached."""
    out_dir = Path(out_dir)
    try:
        return run_api(cfg, dataset, samples, backend, out_dir, use_cache=use_cache, registry=registry)
    finally:
        if (out_dir / "raw_outputs.jsonl").exists():
            pipe = Task2ApiPipeline(dataset, None, cfg)
            report = write_debug_report(out_dir, samples, cfg.get("name"), postprocess=pipe.postprocess)
            print(f"report -> {report}")
