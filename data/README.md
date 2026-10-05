# Data Management Guidelines

This directory houses raw datasets, processed ChatML files, and reproducible train/val splits
for the Unified Multi-Task LLM grading challenge.

## Security and Privacy Notice

Never commit raw competition or student evaluation datasets to version control. The `.gitignore`
file excludes contents inside `data/raw/` and `data/processed/` while retaining directory tracking
via `.gitkeep`.

## Expected raw layout

Place the official dataset (or `sample_dataset`) so that this folder contains:

```text
data/raw/   OR   path/to/sample_dataset/
├── exams.json
├── label_space.json
├── task1_grading.json
├── task2_error_taxonomy.json
├── task3_feedback.json
└── submissions/<exam_id>/<sample_id>.cpp
```

## Preprocessing (required before training all 3 tasks)

```bash
# From repo root — auto-detects ../sample_dataset if present
python scripts/prepare_data.py \
  --data_dir ../sample_dataset/sample_dataset \
  --output_dir data/processed \
  --val_ratio 0.2 \
  --seed 42

# Optional EDA summary
python scripts/eda_report.py --data_dir ../sample_dataset/sample_dataset
```

Outputs:
- `data/processed/train_unified.jsonl` — ChatML records for Task1+2+3 (train)
- `data/processed/val_unified.jsonl` — ChatML records (val)
- `data/processed/task{1,2,3}_{train,val}.jsonl` — per-task ablation files
- `data/processed/unified_samples.jsonl` — joined code+labels (no ChatML)
- `data/processed/manifest.json`
- `data/splits/train_ids.json`, `data/splits/val_ids.json`

Hard rule: teacher `feedback` is **never** placed in Task 1 / Task 2 user prompts
(enforced by `src/data/leakage_guard.py` during preprocess).
