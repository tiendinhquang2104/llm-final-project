# LLM Grading Challenge - Task 3 Controlled Pedagogical Feedback

An end-to-end framework for fine-tuning, aligning, and deploying Large Language Models (`Qwen2.5-Coder-7B-Instruct`) to generate concise, teacher-standard pedagogical feedback for programming submissions in C++.

---

## 1. System Requirements & Environment Setup

### Prerequisites
- **Python**: 3.10 or higher
- **GPU**: NVIDIA GPU with CUDA support (e.g. RTX 3060 12GB, RTX 3090 24GB, RTX 4090, A4000, A100)
- **Compiler**: `g++` supporting C++11 (used for deterministic compiler error diagnosis)

### Dependency Installation
Install all required libraries via `pip`:

```bash
pip install --upgrade pip
pip install \
  torch \
  transformers \
  datasets \
  peft \
  accelerate \
  bitsandbytes \
  pydantic \
  scikit-learn \
  pyyaml \
  tqdm \
  gdown
```

---

## 2. Dataset Preparation

### Download Raw Dataset
The competition dataset is provided on Google Drive. You can download and unpack it directly via `gdown`:

- **Google Drive File ID**: `1iqkw6ZWUV6-I6rsVQdqHBOhiRgRkk_UZ`
- **Drive Link**: [Google Drive Dataset](https://drive.google.com/file/d/1iqkw6ZWUV6-I6rsVQdqHBOhiRgRkk_UZ/view?usp=sharing)

```bash
# 1. Download raw zip file into data/raw/
mkdir -p data/raw
gdown --id 1iqkw6ZWUV6-I6rsVQdqHBOhiRgRkk_UZ -O data/raw/sample_dataset.zip

# 2. Extract into data/raw/
unzip -q data/raw/sample_dataset.zip -d data/raw/
```

### Preprocess & Partition Splits
Normalize raw datasets, extract ground-truth splits, and build partitions:

```bash
python3 scripts/task3_prepare.py --filter-synthetic strict
```

- Raw splits stored in: `data/raw/` (`data/raw/sample_dataset`, etc.)
- Processed splits produced in: `data/processed/task3/` (`train.jsonl`, `real-val.jsonl`, etc.)
- Fixed Public Test Taxonomy Anchor: `outputs/task3/public_taxonomy.json`

---

## 3. Stage 1: SFT QLoRA Training

Stage 1 fine-tunes `Qwen/Qwen2.5-Coder-7B-Instruct` using 4-bit QLoRA with step-by-step validation monitoring (`eval_strategy: steps`, `load_best_model_at_end: true`).

### Option A: Using Pre-configured Profiles

We provide two production-grade profiles in `configs/task3/`:

1. **Conservative Anchor** (`configs/task3/stage1_conservative.yaml`):
   - `epochs: 2.0`, `lr: 2.0e-5`, `real_weight: 0.65`, `synth_weight: 0.35`
   - Strictly guards against memorization on small real splits:
   ```bash
   python3 scripts/train_task3.py --config configs/task3/stage1_conservative.yaml
   ```

2. **Exploration Profile** (`configs/task3/stage1_exploration.yaml`):
   - `epochs: 3.0`, `lr: 1.5e-5`, `real_weight: 0.60`, `synth_weight: 0.40`
   - High pedagogical coverage with lower learning rate:
   ```bash
   python3 scripts/train_task3.py --config configs/task3/stage1_exploration.yaml
   ```

### Option B: Direct Dynamic CLI Overrides

Every hyperparameter can be passed directly from the terminal without modifying YAML files:

```bash
python3 scripts/train_task3.py \
  --output-dir checkpoints/task3/my_stage1_run \
  --epochs 3.0 \
  --lr 1.5e-5 \
  --batch-size 2 \
  --grad-accum 4 \
  --real-weight 0.60 \
  --synth-weight 0.40 \
  --lora-r 16 \
  --lora-alpha 32
```

### Generated Checkpoint Artifacts
Upon completion, the target `--output-dir` automatically contains:
- `adapter/` - Trained LoRA weights (`adapter_model.safetensors`, `adapter_config.json`)
- `train.log` - Real-time step log: timestamp, step count, train loss, val loss, LR, and GPU VRAM peak
- `train_history.json` - Complete loss curve data across all optimizer steps
- `eval_metrics.json` - Final evaluation summary (`train_loss`, `eval_loss`, `generalization_gap`)
- `hyperparameters.json` - Full configuration metadata used for the run

---

## 4. Stage 2: RLVR Alignment Training (GRPO)

Stage 2 aligns the Stage 1 SFT adapter using Group Relative Policy Optimization (GRPO) with rule-based verifiable rewards (brevity penalties, syntax accuracy, pedagogical clarity):

```bash
python3 scripts/run_grpo_tuning.py \
  --sft-adapter checkpoints/task3/stage1_exploration/adapter \
  --final-adapter-out checkpoints/task3/grpo_adapter
```

---

## 5. Modular Inference & Deployment

The inference engine `scripts/run_task3.py` is fully decoupled and dynamic. You can plug in any checkpoint and toggle reasoning modes:

### Two-Pass Chaining Inference (Pass 1 Technical Diagnosis -> Pass 2 Pedagogical Formatting)

```bash
python3 scripts/run_task3.py \
  --split public \
  --adapter checkpoints/task3/stage1_exploration/adapter \
  --taxonomy-source task2-json \
  --taxonomy-json outputs/task3/public_taxonomy.json \
  --requested-levels outputs/task3/task3_requested_levels.json \
  --allow-unverified-task2-export \
  --context-limit 8192 \
  --two-pass \
  --output outputs/task3/prod_public.predictions.json
```

### Direct Single-Pass Inference (Without Two-Pass)

Simply omit `--two-pass`:

```bash
python3 scripts/run_task3.py \
  --split public \
  --adapter checkpoints/task3/stage1_exploration/adapter \
  --taxonomy-source task2-json \
  --taxonomy-json outputs/task3/public_taxonomy.json \
  --requested-levels outputs/task3/task3_requested_levels.json \
  --allow-unverified-task2-export \
  --context-limit 8192 \
  --output outputs/task3/single_pass.predictions.json
```

---

## 6. Submission Validation & Packaging

Validate generated predictions against competition schemas and package the final ZIP artifact:

```bash
python3 scripts/validate_task3_submission.py \
  --predictions outputs/task3/prod_public.predictions.json \
  --requested-levels outputs/task3/task3_requested_levels.json
```
