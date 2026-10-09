# Data

Keep the extracted sample dataset under `data/raw/sample_dataset/` (or point a command to another dataset root containing `exams.json`, `task1_grading.json`, and `submissions/`). Raw student code and processed records are excluded from Git.

The fixed Task 1 split in `data/splits/` is **26 train / 6 validation**, seed 42. Task 1 and the unified preprocessing for Tasks 1–3 use these same IDs. Historical Gemini metrics from the former 13/19 split use `data/splits/history_13_19/` and must not be compared directly with new 26/6 metrics.

To prepare all three tasks, run:

```bash
python scripts/prepare_data.py --data_dir data/raw/sample_dataset --output_dir data/processed --val_ratio 0.2 --seed 42
```

To recreate only the ID split, run:

```bash
python scripts/create_split.py --data_dir data/raw/sample_dataset --ratio 0.2 --seed 42
```

Both commands can overwrite split files; inspect existing experiments before regenerating them. Task 1 reads the raw dataset directly and never sends validation labels or Task 3 feedback to the model. The preprocessing output includes `unified_samples.jsonl`, `train_unified.jsonl`, `val_unified.jsonl`, and per-task train/validation JSONL files.
