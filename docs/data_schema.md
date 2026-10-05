# Data Schema — Unified Multi-Task C++ Grading

Schema mirrors the official challenge `sample_dataset` layout. Code never lives inside JSON;
JSON only references `code_file`.

## Raw inputs

| File | Role |
|---|---|
| `exams.json` | Exam statements + `exam_type` (`multi_problem` / `single_problem`) + grading policy |
| `task1_grading.json` | Rubric 6-dim + `total_score` |
| `task2_error_taxonomy.json` | Multi-label `taxonomy_error` (10 labels; `[]` = no error) |
| `task3_feedback.json` | `target_feedback_level` + gold `feedback` |
| `label_space.json` | Rubric ranges, taxonomy, feedback-level definitions |
| `submissions/<exam_id>/<sample_id>.cpp` | Student code |

Shared `sample_id` across all three task files.

## Joined sample (`UnifiedSample`)

Produced as `data/processed/unified_samples.jsonl`.

| Field | Description |
|---|---|
| `sample_id`, `exam_id`, `exam_type`, `language` | Identifiers |
| `code`, `code_file` | Loaded C++ source |
| `exam_statement`, `grading_policy` | From `exams.json` |
| `compile_log`, `test_report` | Auxiliary signals (not ground truth) |
| `rubric`, `total_score` | Task 1 labels |
| `taxonomy_error` | Task 2 labels |
| `target_feedback_level`, `feedback` | Task 3 input level + gold text |

## ChatML training record (`ChatMLRecord`)

Each sample expands into **3** records (`task1`, `task2`, `task3`) in:

- `train_unified.jsonl` / `val_unified.jsonl`
- plus per-task `task{1,2,3}_{train,val}.jsonl`

```json
{
  "sample_id": "EX02-S204",
  "task": "task1",
  "exam_id": "EX02",
  "split": "train",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "{\"rubric\":{...},\"total_score\":10}"}
  ],
  "text": "<|im_start|>system\\n...<|im_end|>\\n...",
  "target": "..."
}
```

### Leakage rule (hard)

Teacher `feedback` must **never** appear in Task 1 / Task 2 user or system prompts.
Task 3 may use `taxonomy_error` + `target_feedback_level` as inputs; `feedback` is the assistant target only.
Enforced by `src/data/leakage_guard.py` inside `prepare_data.py`.
