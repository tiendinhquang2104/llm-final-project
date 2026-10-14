"""Task 2 Local Generative Causal LM runner using Qwen2.5-Coder-7B-Instruct.

Runs 100% locally on Kaggle 2x T4 GPUs (or local CUDA GPU) with zero API calls.
Uses ChatML prompt with problem statement, C++ code with line numbers, self-compiled
compile log, 10 error taxonomy descriptions, and gold few-shot demonstrations.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from src.data.loader import unpack
from src.task2.compile import attach_compile_logs
from src.task2.data import load_task2
from src.task2.evaluator import f1_scores, validate_predictions, write_submission
from src.task2.labels import LABELS, normalize_labels
from src.task2.pipeline import parse_labels
from src.task2.prompts import build_messages, select_demos
from src.utils.config import load_config
from src.utils.json_extractor import extract_json_objects

COMPILE_LABEL = "Lỗi biên dịch"


def ensure_data(gold_path: Path, public_path: Path) -> None:
    if (not gold_path.exists() or not public_path.exists()) and Path("/kaggle/input").exists():
        dest = gold_path.parent
        print(f"[data] Auto-unpacking datasets from /kaggle/input -> {dest}")
        unpack(Path("/kaggle/input"), dest)


def robust_parse_labels(text: str) -> list[str]:
    parsed = parse_labels(text)
    if parsed is not None:
        return parsed
    # Fallback 1: check extract_json_objects for any list
    for obj in extract_json_objects(text or ""):
        for k, v in obj.items():
            if isinstance(v, list):
                return normalize_labels(v)
    # Fallback 2: direct label mention
    return [lab for lab in LABELS if lab in text]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="Qwen/Qwen2.5-Coder-7B-Instruct")
    ap.add_argument("--gold-root", default=str(ROOT / "data" / "raw" / "sample_dataset"))
    ap.add_argument("--public-root", default=str(ROOT / "data" / "raw" / "public_test_release"))
    ap.add_argument("--output-dir", default=str(ROOT / "outputs" / "task2" / "task2_coder_local"))
    ap.add_argument("--few-shot-k", type=int, default=2, help="Number of gold few-shot demonstrations (0 for zero-shot)")
    ap.add_argument("--max-code-chars", type=int, default=6000)
    ap.add_argument("--max-new-tokens", type=int, default=128)
    ap.add_argument("--load-in-4bit", action="store_true", help="Load model in 4-bit NF4 to save VRAM")
    ap.add_argument("--load-in-8bit", action="store_true", help="Load model in 8-bit to save VRAM")
    ap.add_argument("--no-compile", action="store_true", help="Skip self-compiling g++ logs")
    ap.add_argument("--eval-gold", action="store_true", help="Also evaluate on the 32 gold samples")
    a = ap.parse_args()

    gold_root, public_root = Path(a.gold_root), Path(a.public_root)
    ensure_data(gold_root, public_root)
    out_dir = Path(a.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("==> Loading datasets...")
    gold = load_task2(gold_root)
    public = load_task2(public_root)
    print(f"Loaded {len(gold.samples)} gold samples, {len(public.samples)} public test samples.")

    # Self-compiled compile logs
    base_cfg = load_config(ROOT / "configs" / "task2" / "base.yaml")
    compile_cfg = base_cfg.get("compile")
    lists, compiler_id = attach_compile_logs(compile_cfg, [gold.samples, public.samples],
                                             enabled=not a.no_compile, root=ROOT)
    gold.samples[:], public.samples[:] = lists[0], lists[1]
    print(f"compiler: {compiler_id or 'off'}")

    print(f"==> Loading Causal LM: {a.model} ...")
    tokenizer = AutoTokenizer.from_pretrained(a.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    kw = {"device_map": "auto", "trust_remote_code": True}
    if a.load_in_4bit:
        kw["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
    elif a.load_in_8bit:
        kw["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
    else:
        kw["torch_dtype"] = torch.float16 if torch.cuda.is_available() else torch.float32

    model = AutoModelForCausalLM.from_pretrained(a.model, **kw).eval()
    print("Model loaded successfully onto:", {p.device for p in model.parameters()})

    prompt_cfg = {
        "max_code_chars": a.max_code_chars,
        "demo_max_code_chars": 2000,
        "use_aux_signals": not a.no_compile,
    }

    # Optional Evaluation on Gold
    if a.eval_gold:
        print("\n==> Evaluating on 32 Gold samples...")
        gold_preds = {}
        for idx, sample in enumerate(gold.samples, 1):
            exam = gold.exams[sample.exam_id]
            demos = select_demos(gold.samples, sample, a.few_shot_k)
            messages = build_messages(exam, sample, demos, prompt_cfg)
            prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
            with torch.no_grad():
                out_ids = model.generate(
                    **inputs,
                    max_new_tokens=a.max_new_tokens,
                    do_sample=False,
                    pad_token_id=tokenizer.pad_token_id,
                )
            gen_text = tokenizer.decode(out_ids[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
            labs = robust_parse_labels(gen_text)
            if sample.compile_log and ("error:" in sample.compile_log.lower()):
                if COMPILE_LABEL not in labs:
                    labs.append(COMPILE_LABEL)
            gold_preds[sample.sample_id] = labs
            if idx % 8 == 0 or idx == len(gold.samples):
                print(f"  [gold {idx}/{len(gold.samples)}] {sample.sample_id} -> {labs}")

        gold_map = {s.sample_id: s.labels for s in gold.samples}
        metrics = f1_scores(gold_map, gold_preds)
        print("\n--- Gold In-Context Results ---")
        print(f"Macro-F1: {metrics['macro_f1']:.4f} | Micro-F1: {metrics['micro_f1']:.4f} | Exact: {metrics['exact_match']:.4f}")

    # Generate on Public Test (328 samples)
    print(f"\n==> Generating predictions on {len(public.samples)} Public Test samples (k={a.few_shot_k})...")
    test_preds = {}
    full_records = []
    t0 = time.time()
    for idx, sample in enumerate(public.samples, 1):
        exam = public.exams[sample.exam_id]
        demos = select_demos(gold.samples, sample, a.few_shot_k)
        messages = build_messages(exam, sample, demos, prompt_cfg)
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out_ids = model.generate(
                **inputs,
                max_new_tokens=a.max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )
        gen_text = tokenizer.decode(out_ids[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        labs = robust_parse_labels(gen_text)
        if sample.compile_log and ("error:" in sample.compile_log.lower()):
            if COMPILE_LABEL not in labs:
                labs.append(COMPILE_LABEL)
        test_preds[sample.sample_id] = labs
        full_records.append({
            "sample_id": sample.sample_id,
            "exam_id": sample.exam_id,
            "labels": labs,
            "raw_output": gen_text,
            "has_compile_error": bool(sample.compile_log and "error:" in sample.compile_log.lower()),
        })
        if idx % 20 == 0 or idx == len(public.samples):
            elapsed = time.time() - t0
            sec_per_sample = elapsed / idx
            remain = (len(public.samples) - idx) * sec_per_sample
            print(f"  [{idx:3d}/{len(public.samples)}] {sample.sample_id:25s} -> {labs} (ETA: {remain/60:.1f}m)")

    # Save outputs
    sub_path = out_dir / "predictions.json"
    full_path = out_dir / "predictions_full.json"
    write_submission(sub_path, test_preds, [s.sample_id for s in public.samples])
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(full_records, f, ensure_ascii=False, indent=2)

    # Validate predictions
    errs = validate_predictions(json.loads(sub_path.read_text(encoding="utf-8")))
    print(f"\n==> Predictions saved to {sub_path}")
    print(f"Validation: {len(test_preds)} samples, errors: {errs}")


if __name__ == "__main__":
    main()
