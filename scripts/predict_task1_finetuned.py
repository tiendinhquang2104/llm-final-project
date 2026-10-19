"""Run public Task 1 on the gold-validation-selected QLoRA adapter (Colab GPU)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.loader import load_task1  # noqa: E402
from src.task1.finetune_public import (  # noqa: E402
    predict_finetuned_public,
    prepare_public,
    select_adapter,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-run", type=Path, required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--preflight", action="store_true", help="Tokenizer and data checks; no model weights loaded")
    parser.add_argument("--max-length", type=int, help="Explicit context budget override; never truncate code")
    parser.add_argument("--predict-ids", help="Comma-separated public IDs for a partial run")
    parser.add_argument("--smoke-first", action="store_true", help="Check one sample per exam and empty-code inputs before full run")
    args = parser.parse_args()

    from transformers import AutoConfig, AutoTokenizer

    selection = select_adapter(args.training_run)
    cfg = selection["training_config"]
    max_length = args.max_length or int(cfg["training"]["max_length"])
    max_new_tokens = int(cfg["generation"]["max_new_tokens"])
    model_config = AutoConfig.from_pretrained(selection["model"])
    if max_length > model_config.max_position_embeddings:
        raise ValueError("--max-length exceeds the base model context limit")
    tokenizer = AutoTokenizer.from_pretrained(selection["adapter_dir"])
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    dataset = load_task1(args.public_root)
    inputs, preflight = prepare_public(dataset, tokenizer, max_length, max_new_tokens)
    print(json.dumps({"selection": selection, "public": preflight}, ensure_ascii=False, indent=2), flush=True)
    if args.preflight:
        return

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig

    if not torch.cuda.is_available():
        raise RuntimeError("Choose a Colab GPU runtime before inference")
    torch.manual_seed(int(cfg["seed"]))
    quantization = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16,
    )
    base = AutoModelForCausalLM.from_pretrained(
        selection["model"], quantization_config=quantization, device_map="auto", torch_dtype=torch.float16,
    )
    model = PeftModel.from_pretrained(base, selection["adapter_dir"], is_trainable=False)
    model.eval()
    model.config.use_cache = True

    def generate(ids):
        input_ids = torch.tensor([ids], device=model.get_input_embeddings().weight.device)
        with torch.inference_mode():
            output = model.generate(
                input_ids=input_ids, attention_mask=torch.ones_like(input_ids),
                do_sample=False, max_new_tokens=max_new_tokens,
                pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id,
            )
        completion = output[0][len(ids):]
        return tokenizer.decode(completion, skip_special_tokens=True), len(completion)

    generation = {"max_length": max_length, "max_new_tokens": max_new_tokens,
                  "do_sample": False, "quantization": "nf4_double_float16",
                  "seed": int(cfg["seed"])}
    if args.smoke_first:
        first = {}
        for sample in sorted(dataset.samples, key=lambda s: s.sample_id):
            first.setdefault(sample.exam_id, sample.sample_id)
        smoke_ids = sorted(set(first.values()) | {s.sample_id for s in dataset.samples if not s.code.strip()})
        smoke = predict_finetuned_public(dataset, inputs, selection, generate, args.output_root, generation, smoke_ids)
        print(json.dumps(smoke, ensure_ascii=False, indent=2), flush=True)
        if smoke["selected_completed"] != len(smoke_ids) or smoke["stopped"]:
            raise RuntimeError("Smoke test incomplete; inspect invalid_outputs/ and progress.json before full run")
    ids = [sid.strip() for sid in args.predict_ids.split(",") if sid.strip()] if args.predict_ids else None
    result = predict_finetuned_public(dataset, inputs, selection, generate, args.output_root, generation, ids)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    expected = len(ids) if ids else result["expected"]
    if result["selected_completed"] != expected or result["stopped"]:
        raise RuntimeError(f"Incomplete public inference; inspect {result['run_dir']}/progress.json")


if __name__ == "__main__":
    main()
