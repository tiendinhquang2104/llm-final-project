# Experimentation Protocol and Guidelines

This protocol defines rigorous standards for conducting, tracking, and validating experiments within the LLM Grading Challenge repository.

## Guiding Principles

Reliability, reproducibility, and unbiased evaluation form the foundation of our experimental framework. Every reported benchmark must be accompanied by full provenance data.

## Reproducibility Standards

### Deterministic Random Seeds

All stochastic processes, including dataset splitting, sample ordering, weight initialization, and sampling decoders, must be initialized with fixed random seeds.

The default project seed is `42`. All runner scripts accept `--seed` or inherit the value defined in `configs/base.yaml`.

### Environment Manifests

Before training or generating final predictions, scripts automatically capture runtime metadata via `src/training/reproducibility.py`. This manifest records:
- Python runtime version and operating system details
- Git commit hash
- Installed package versions (torch, transformers, peft)
- GPU device identifier and CUDA driver configuration

## Cross-Validation and Data Splits

To prevent data contamination and target leakage:
- Split splits must be strictly generated once using `scripts/create_split.py` and saved to `data/splits/`.
- Training and fine-tuning pipelines must only read `data/splits/train_ids.json`.
- Hyperparameter tuning and threshold calibration must strictly occur on `data/splits/val_ids.json`.
- Test datasets must remain untouched until the final submission generation.

## Experiment Registry

All pipeline executions append results to `experiments/registry.csv`.

| Column | Description |
|---|---|
| `timestamp` | ISO-8601 formatted timestamp of execution. |
| `task` | Challenge task identifier (`task1`, `task2`, `task3`). |
| `experiment_name` | Unique descriptive name for the configuration. |
| `config_path` | File path to YAML configuration used. |
| `rmse` | Root Mean Squared Error (for regression tasks). |
| `mae` | Mean Absolute Error. |
| `pearson` | Pearson correlation coefficient. |
| `qwk` | Quadratic Weighted Kappa score. |
| `accuracy` | Accuracy score (for classification and compliance). |
| `f1_macro` | Macro-averaged F1 score. |

## Baseline Progression Strategy

When testing new model architectures or prompt strategies:
1. Establish a zero-shot or few-shot baseline using API models.
2. Formulate explicit hypotheses for improvements (e.g. CoT prompting, rubric decomposition, domain LoRA).
3. Record results in `experiments/registry.csv`.
4. Perform error analysis on residual outliers before adopting modifications into the production submission.
