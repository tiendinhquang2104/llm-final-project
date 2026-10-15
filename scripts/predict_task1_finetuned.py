"""Predict an unlabelled Task 1 release (public / private test) with the selected QLoRA adapter.

    python scripts/predict_task1_finetuned.py --adapter <run>/best_adapter --public-root <public_test_release> \
        --processed-dir <gold_processed> --splits-dir <gold_splits> --output-dir <out> --preflight
    ... same without --preflight (GPU), add --limit-per-exam 1 for a smoke run.

Same prompt (src/data/prompts.build_task1_prompt), greedy decoding and parser (finetune.parse_generated_score)
as the gold-validation evaluation in scripts/train_task1.py. Raw outputs are checkpointed per batch, so an
interrupted run resumes. An unparseable output gets the median gold rubric of its exam type (flagged
`fallback_used`) so the submission always covers every sample_id; nothing is written unless the file passes
src.task1.evaluator.validate_predictions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.task1.evaluator import validate_predictions  # noqa: E402
from src.task1.finetune import (  # noqa: E402
    fallback_score, load_task1_splits, load_unlabelled_prompts, parse_generated_score,
)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=ROOT / "configs/task1/lora_7b.yaml")
    ap.add_argument("--adapter", type=Path, required=True, help="best_adapter/ written by scripts/train_task1.py")
    ap.add_argument("--public-root", type=Path, required=True, help="release with exams.json + task1_grading.json")
    ap.add_argument("--task-file", default="task1_grading.json")
    ap.add_argument("--processed-dir", type=Path, required=True, help="gold task1_{train,val}.jsonl (fallback)")
    ap.add_argument("--splits-dir", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--limit-per-exam", type=int, help="first N samples of each exam (smoke test)")
    ap.add_argument("--preflight", action="store_true", help="prompts + token lengths only, no model")
    return ap.parse_args()


def _write(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def adapter_digest(adapter: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(adapter.glob("adapter_model.*")):
        h.update(f.read_bytes())
    return h.hexdigest()[:16]


def main() -> None:
    import yaml
    from transformers import AutoTokenizer

    a = parse_args()
    cfg = yaml.safe_load(a.config.read_text(encoding="utf-8"))
    max_length = int(cfg["training"]["max_length"])
    max_new_tokens = int(cfg["generation"]["max_new_tokens"])
    if not (a.adapter / "adapter_config.json").is_file():
        sys.exit(f"No LoRA adapter in {a.adapter}")
    gold_train, gold_val = load_task1_splits(a.processed_dir, a.splits_dir, expected_train=cfg["data"]["expected_train"],
                                             expected_val=cfg["data"]["expected_val"])
    prompts = load_unlabelled_prompts(a.public_root, a.task_file)
    expected_ids = [p["sample_id"] for p in prompts]
    if a.limit_per_exam:
        seen: dict[str, int] = {}
        kept = []
        for p in prompts:
            if seen.get(p["exam_id"], 0) < a.limit_per_exam:
                kept.append(p)
                seen[p["exam_id"]] = seen.get(p["exam_id"], 0) + 1
        prompts, expected_ids = kept, [p["sample_id"] for p in kept]

    tok = AutoTokenizer.from_pretrained(str(a.adapter), use_fast=True)  # saved with the adapter by train_task1.py
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "left"  # batched generation for a decoder-only model
    for p in prompts:
        p["ids"] = tok.apply_chat_template(p["messages"], tokenize=True, add_generation_prompt=True)
    too_long = [p["sample_id"] for p in prompts if len(p["ids"]) + max_new_tokens > max_length]
    lengths = sorted(len(p["ids"]) for p in prompts)
    preflight = {"model": cfg["model"], "adapter": str(a.adapter), "adapter_sha256_16": adapter_digest(a.adapter),
                 "n_prompts": len(prompts), "n_exams": len({p["exam_id"] for p in prompts}),
                 "prompt_tokens_p50": lengths[len(lengths) // 2], "prompt_tokens_max": lengths[-1],
                 "too_long_for_max_length": too_long, "max_length": max_length}
    print(json.dumps(preflight, ensure_ascii=False, indent=2), flush=True)
    if a.preflight:
        return

    import peft
    import torch
    import transformers
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig

    if not torch.cuda.is_available():
        sys.exit("A CUDA GPU is required for 4-bit inference")
    torch.manual_seed(int(cfg["seed"]))
    a.output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = a.output_dir / "raw_outputs.jsonl"
    key = preflight["adapter_sha256_16"]
    done: dict[str, str] = {}
    if raw_path.exists():  # resume: keep outputs of the same adapter only
        for line in raw_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("adapter") == key:
                done[row["sample_id"]] = row["raw_output"]
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                               bnb_4bit_compute_dtype=torch.float16)
    base = AutoModelForCausalLM.from_pretrained(cfg["model"], quantization_config=quant, device_map="auto",
                                                torch_dtype=torch.float16)
    model = PeftModel.from_pretrained(base, str(a.adapter), is_trainable=False).eval()
    todo = [p for p in prompts if p["sample_id"] not in done and p["sample_id"] not in too_long]
    print(f"generate {len(todo)} (resumed {len(done)}, too long {len(too_long)})", flush=True)
    t0, new_tokens = time.time(), 0
    with raw_path.open("a", encoding="utf-8") as raw_file:
        for k in range(0, len(todo), a.batch_size):
            batch = todo[k:k + a.batch_size]
            width = max(len(p["ids"]) for p in batch)
            input_ids = torch.tensor([[tok.pad_token_id] * (width - len(p["ids"])) + p["ids"] for p in batch],
                                     device=model.device)
            attention = torch.tensor([[0] * (width - len(p["ids"])) + [1] * len(p["ids"]) for p in batch],
                                     device=model.device)
            with torch.inference_mode():
                out = model.generate(input_ids=input_ids, attention_mask=attention, do_sample=False,
                                     max_new_tokens=max_new_tokens, pad_token_id=tok.pad_token_id,
                                     eos_token_id=tok.eos_token_id)
            for p, row in zip(batch, out[:, width:]):
                text = tok.decode(row, skip_special_tokens=True)
                new_tokens += int((row != tok.pad_token_id).sum())
                done[p["sample_id"]] = text
                raw_file.write(json.dumps({"sample_id": p["sample_id"], "adapter": key, "raw_output": text},
                                          ensure_ascii=False) + "\n")
            raw_file.flush()
            print(f"[predict] {min(k + a.batch_size, len(todo))}/{len(todo)}  {time.time() - t0:.0f}s", flush=True)
    seconds = time.time() - t0

    submission, details = [], []
    for p in prompts:
        raw = done.get(p["sample_id"])
        pred, json_ok, strict_ok = parse_generated_score(raw) if raw is not None else (None, False, False)
        fallback = pred is None
        if fallback:
            pred = fallback_score(gold_train + gold_val, p["exam_type"])
        submission.append({"sample_id": p["sample_id"], "output": pred})
        details.append({"sample_id": p["sample_id"], "exam_id": p["exam_id"], "raw_output": raw,
                        "json_ok": json_ok, "strict_output_ok": strict_ok, "fallback_used": fallback,
                        "reason": "prompt_too_long" if p["sample_id"] in too_long else None, "prediction": pred})
    errors = validate_predictions(submission, expected_ids)
    if errors:
        raise RuntimeError(f"Submission failed format validation: {errors[:5]}")
    _write(a.output_dir / "task1_predictions.json", submission)
    _write(a.output_dir / "predictions_full.json", details)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    info = {**{k: v for k, v in preflight.items() if k != "too_long_for_max_length"},
            "n_too_long": len(too_long), "n_fallback": sum(d["fallback_used"] for d in details),
            "valid_output_rate": sum(d["strict_output_ok"] for d in details) / len(details),
            "generate_seconds": round(seconds, 1), "new_tokens": new_tokens,
            "gpu": torch.cuda.get_device_name(0), "peak_gpu_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
            "versions": {"python": platform.python_version(), "torch": torch.__version__,
                         "transformers": transformers.__version__, "peft": peft.__version__},
            "git_commit": commit, "decoding": "greedy", "seed": cfg["seed"]}
    _write(a.output_dir / "run_info.json", info)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    print(f"submission -> {a.output_dir / 'task1_predictions.json'}")


if __name__ == "__main__":
    main()
