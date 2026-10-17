"""Export / load a zero-shot CoT "model bundle": nothing is trained, so the model is (backbone id + exact revision,
prompt, generation settings, compile recipe). Optionally the backbone weights themselves (HF backend) so the
bundle runs offline. `scripts/predict_task2_cot.py --bundle DIR` rebuilds the same pipeline from it."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from src.task1.experiment import _git_commit
from src.task2.prompts_cot import cot_instruction, prompt_lang, system_prompt

FORMAT = "task2-cot-bundle/1"


def prompt_sha256(lang: str = "vi") -> str:
    return hashlib.sha256((system_prompt(lang) + "\n" + cot_instruction(lang)).encode("utf-8")).hexdigest()


def _lang(cfg: dict) -> str:
    return prompt_lang(cfg.get("prompt"))


def export_bundle(bundle_dir, cfg: dict, kind: str, backend_info: dict, compile_cfg: dict | None,
                  metrics: dict | None = None, weights_saver=None, demo_pools: dict | None = None,
                  run_dir=None, partial: bool = False) -> Path:
    """Write bundle.json, the rendered prompts and a README. `weights_saver(path)` (e.g. HFChatBackend.save)
    also writes the backbone weights into `<bundle>/model`. `demo_pools` (DemoRetriever.fingerprint) pins the
    few-shot pools; `run_dir` adds demos.json (demos used per graded sample, from raw_outputs.jsonl); `partial`
    marks gold metrics computed on a subset (--ids / --limit / --smoke)."""
    bundle = Path(bundle_dir)
    bundle.mkdir(parents=True, exist_ok=True)
    weights = None
    if weights_saver is not None:
        weights_saver(bundle / "model")
        weights = "model"
    api = ((metrics or {}).get("systems") or {}).get("api") or {}
    meta = {
        "format": FORMAT, "created": time.strftime("%Y-%m-%d %H:%M:%S"), "git_commit": _git_commit(),
        "backend": kind, "model": backend_info.get("model"), "revision": backend_info.get("revision"),
        "weights": weights, "hardware_used": backend_info.get("hardware"),
        "experiment": {k: cfg[k] for k in ("name", "description", "prompt", "generation", "retry_on_parse_fail",
                                           "checkpoint_every", "seed", "demos") if k in cfg},
        "compile": compile_cfg, "prompt_sha256": prompt_sha256(_lang(cfg)),
        "gold_metrics": ({**{k: api.get(k) for k in ("n", "macro_f1", "micro_f1", "exact_match")},
                          "partial": partial} if api else None),
        "demo_pools": demo_pools,
    }
    demos = _demos_used(run_dir)
    if demos:
        (bundle / "demos.json").write_text(json.dumps(demos, ensure_ascii=False, indent=1), encoding="utf-8")
        meta["demos_file"] = "demos.json"
    (bundle / "bundle.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (bundle / "prompt_system.txt").write_text(system_prompt(_lang(cfg)), encoding="utf-8")
    (bundle / "prompt_instruction.txt").write_text(cot_instruction(_lang(cfg)), encoding="utf-8")
    (bundle / "README.md").write_text(_readme(meta), encoding="utf-8")
    return bundle


def _demos_used(run_dir) -> dict:
    path = Path(run_dir) / "raw_outputs.jsonl" if run_dir else None
    if not path or not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)["record"]
        except (json.JSONDecodeError, KeyError):
            continue
        if rec.get("demos"):
            out[rec["sample_id"]] = rec["demos"]  # later lines (reruns) win
    return dict(sorted(out.items()))


def check_demo_pools(meta: dict, fingerprint: dict | None) -> list[str]:
    """Differences between the bundle's few-shot pools and the current ones (empty = same demos possible)."""
    want = meta.get("demo_pools")
    if not want:
        return []
    if not fingerprint:
        return ["bundle dùng few-shot nhưng lần chạy này không có demo pool"]
    return [f"{src}: bundle n={want[src]['n']} sha256={want[src]['sha256'][:12]} | hiện tại n={fingerprint[src]['n']} "
            f"sha256={fingerprint[src]['sha256'][:12]}"
            for src in want if want[src] != fingerprint.get(src)]


def load_bundle(bundle_dir) -> dict:
    bundle = Path(bundle_dir)
    meta = json.loads((bundle / "bundle.json").read_text(encoding="utf-8"))
    if meta.get("format") != FORMAT:
        raise ValueError(f"{bundle}: unknown bundle format {meta.get('format')!r}")
    meta["prompt_matches_code"] = meta.get("prompt_sha256") == prompt_sha256(_lang(meta.get("experiment") or {}))
    if meta.get("weights"):
        meta["weights_path"] = str(bundle / meta["weights"])
    return meta


def backend_settings(meta: dict, kind: str | None = None) -> tuple[str, dict]:
    """(kind, settings for make_local_backend) reproducing the bundle's backbone."""
    kind = kind or meta["backend"]
    if kind == "hf":
        if meta.get("weights_path"):
            return kind, {"hf": {"model": meta["weights_path"]}}
        model = meta["model"] if meta["backend"] == "hf" else "Qwen/Qwen2.5-Coder-7B-Instruct"
        rev = meta.get("revision") if meta["backend"] == "hf" else None
        return kind, {"hf": {"model": model, "revision": rev}}
    model = meta["model"] if meta["backend"] == "mlx" else "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"
    return kind, {"mlx": {"model": model}}


def _readme(meta: dict) -> str:
    gm = meta.get("gold_metrics") or {}
    pools = meta.get("demo_pools")
    pools_txt = ("Few-shot: demo lấy từ " + ", ".join(f"{k} ({v['n']} bài, sha256 {v['sha256'][:12]})"
                                                       for k, v in pools.items())
                 + "; `demos.json` = demo đã dùng cho từng bài lúc export. Chạy lại với gold/silver khác hash thì "
                 "script cảnh báo (demo có thể khác)." if pools else "Không dùng few-shot.")
    note = " (chỉ một phần bài: kiểm tra pipeline, không phải điểm chính thức)" if gm.get("partial") else ""
    return f"""# Task 2 CoT bundle: {meta['experiment'].get('name')}

Không có trọng số được train: "model" = backbone `{meta['model']}` (revision `{meta.get('revision')}`)
+ prompt giảng viên (`prompt_system.txt`, `prompt_instruction.txt`) + cấu hình sinh trong `bundle.json`.
Trọng số kèm theo: {'có, thư mục `model/`' if meta.get('weights') else 'không (tải lại theo model id + revision)'}.

Điểm trên gold lúc export{note}: macro-F1 = {gm.get('macro_f1')}, micro-F1 = {gm.get('micro_f1')}, n = {gm.get('n')}.

{pools_txt}

## Chạy lại

```bash
python scripts/predict_task2_cot.py --bundle <thư mục bundle> --data-root <thư mục có exams.json + task2_error_taxonomy.json>
```

- `--backend hf|mlx` để đổi backend (mặc định: `{meta['backend']}`).
- Kết quả: `predictions.json` (định dạng nộp bài), `predictions_full.json`, `debug.jsonl`, `report.html`, `run.log`.
- Prompt lấy từ code của repo (git `{meta.get('git_commit')}`); script cảnh báo nếu prompt trong code khác
  `prompt_sha256` của bundle.
"""
