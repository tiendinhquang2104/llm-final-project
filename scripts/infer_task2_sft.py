"""Run inference on Public Test using fine-tuned QLoRA adapter for Task 2.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.task2.data import load_task2
from src.task2.labels import normalize_labels
from src.task2.evaluator import validate_predictions, write_submission, f1_scores
from scripts.prepare_task2_sft import SYSTEM_PROMPT, format_user_prompt


def extract_taxonomy_labels(gen: str) -> list[str]:
    # 1. Direct JSON parse
    try:
        obj = json.loads(gen.strip())
        if isinstance(obj, dict) and "taxonomy_error" in obj:
            return normalize_labels(obj["taxonomy_error"])
    except Exception:
        pass

    # 2. Regex for {"taxonomy_error": [...]}
    m = re.search(r'"taxonomy_error"\s*:\s*\[(.*?)\]', gen, flags=re.DOTALL)
    if m:
        content = m.group(1)
        items = re.findall(r'["\'](.*?)["\']', content)
        if items:
            return normalize_labels(items)
        try:
            return normalize_labels(json.loads(f"[{content}]"))
        except Exception:
            pass

    # 3. Fallback: Search for any canonical labels in generated text
    from src.task2.labels import LABELS
    found = [lab for lab in LABELS if lab in gen]
    return normalize_labels(found)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_id", default="Qwen/Qwen2.5-Coder-7B-Instruct")
    parser.add_argument("--adapter_dir", default="outputs/task2/qlora_adapter")
    parser.add_argument("--data_dir", default="data/public_test_release")
    parser.add_argument("--output_file", default="outputs/task2/task2_predictions_lora.json")
    args = parser.parse_args()

    import os
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from tqdm import tqdm

    print("==> Loading tokenizer and 4-bit model...")
    tokenizer = AutoTokenizer.from_pretrained(args.model_id, trust_remote_code=True)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
    )
    device_map = {"": 0} if torch.cuda.is_available() else None
    base_model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        quantization_config=bnb_config,
        device_map=device_map,
        attn_implementation="sdpa",
        trust_remote_code=True,
    )

    adapter_path = Path(args.adapter_dir)
    if not (adapter_path / "adapter_config.json").exists():
        checkpoints = sorted(
            adapter_path.glob("checkpoint-*"),
            key=lambda p: int(p.name.split("-")[-1]) if p.name.split("-")[-1].isdigit() else 0,
        )
        if checkpoints and (checkpoints[-1] / "adapter_config.json").exists():
            adapter_path = checkpoints[-1]
            print(f"==> Auto-detected latest checkpoint adapter at: {adapter_path}")

    print(f"==> Loading LoRA adapter from {adapter_path}...")
    model = PeftModel.from_pretrained(base_model, str(adapter_path))
    model.eval()

    data_path = Path(args.data_dir)
    if not data_path.exists():
        import glob
        matches = glob.glob("/kaggle/input/**/public_test_release", recursive=True)
        if matches:
            data_path = Path(matches[0])
            print(f"Auto-detected data_dir in /kaggle/input: {data_path}")
        else:
            raise FileNotFoundError(f"Data directory not found: {args.data_dir}")

    ds = load_task2(data_path)
    exams = ds.exams
    print(f"Loaded {len(ds.samples)} samples from {data_path}")

    preds = {}
    for s in tqdm(ds.samples, desc="Predicting Task 2"):
        stmt = exams.get(s.exam_id, {}).get("statement", "")
        prompt = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": format_user_prompt(stmt, s.code, s.compile_log)},
        ]
        inputs = tokenizer.apply_chat_template(
            prompt,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
        )
        if inputs["input_ids"].shape[-1] > 2048:
            inputs["input_ids"] = inputs["input_ids"][:, -2048:]
            inputs["attention_mask"] = inputs["attention_mask"][:, -2048:]
        inputs = {k: v.to(model.device) for k, v in inputs.items()}

        with torch.inference_mode():
            out_ids = model.generate(
                **inputs,
                max_new_tokens=128,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )

        gen = tokenizer.decode(out_ids[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=True).strip()
        preds[s.sample_id] = extract_taxonomy_labels(gen)

    # Evaluate if dataset has ground truth labels
    if any(s.has_gold for s in ds.samples):
        gold = {s.sample_id: s.labels for s in ds.samples if s.has_gold}
        scores = f1_scores(gold, preds)
        print("\n" + "=" * 60)
        print(f"📊 EVALUATION REPORT ({len(gold)} samples with ground truth)")
        print(f"  Macro-F1 (competition metric): {scores['macro_f1']:.4f}")
        print(f"  Micro-F1                     : {scores['micro_f1']:.4f}")
        print(f"  Exact Match                  : {scores['exact_match']:.4f}")
        print("\nDetail by error label:")
        for lab, stats in scores["per_label"].items():
            f1_val = f"{stats['f1']:.4f}" if stats['f1'] is not None else "   N/A"
            p_val = f"{stats['precision']:.4f}" if stats['precision'] is not None else "   N/A"
            r_val = f"{stats['recall']:.4f}" if stats['recall'] is not None else "   N/A"
            print(f"  - {lab:<18}: F1={f1_val} | P={p_val} | R={r_val} (Support={stats['support']})")
        print("=" * 60 + "\n")

    out_path = Path(args.output_file)
    write_submission(out_path, preds, [s.sample_id for s in ds.samples])
    print(f"[OK] Saved predictions to {out_path}")


if __name__ == "__main__":
    main()
