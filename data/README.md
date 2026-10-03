# Data Management Guidelines

This directory houses all raw datasets, processed files, and reproducible train/val splits for the LLM Grading Challenge.

## Security and Privacy Notice

Never commit raw competition or student evaluation datasets to version control. The `.gitignore` file is configured to exclude contents inside `data/raw/` and `data/processed/` while retaining directory tracking via `.gitkeep`.

## Directory Organization

### data/raw/
Place all incoming raw files (e.g. CSV, JSON, Parquet files provided by the competition organizers) into this folder.

Expected naming convention:
- `train_raw.json` or `train_raw.csv`
- `test_raw.json` or `test_raw.csv`
- `rubrics.json`

### data/processed/
Contains cleaned, standardized, and tokenized datasets ready for model ingestion and prompt evaluation. Files in this folder are generated deterministically by `scripts/prepare_data.py`.

Standardized JSON Lines schema:
- `task1_eval.jsonl`
- `task2_train.jsonl`
- `task2_val.jsonl`
- `task3_eval.jsonl`

### data/splits/
Stores reproducible identifier lists for validation splits to prevent data leakage and ensure fair comparison across models:
- `train_ids.json`: List of sample IDs reserved for training.
- `val_ids.json`: List of sample IDs reserved for validation/checkpoint selection.

## Preprocessing Pipeline

To convert raw inputs into processed datasets and splits, execute:

```bash
python scripts/prepare_data.py --input_dir data/raw --output_dir data/processed
python scripts/create_split.py --data_path data/processed/dataset.jsonl --ratio 0.8 --seed 42
```
