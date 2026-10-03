# LLM Grading Challenge

A modular, production-ready framework for automated grading, rubric scoring, fine-tuning, and compliance validation using Large Language Models.

## Overview

This repository provides an end-to-end pipeline designed for the LLM Grading Challenge. The system is architected into three specialized tasks:

- **Task 1: Automated Rule & Rubric Scoring**: Combines deterministic prerequisite rule checks with LLM prompting pipelines to evaluate responses against structured rubrics.
- **Task 2: Model Fine-Tuning & Score Classification**: Implements Parameter-Efficient Fine-Tuning (PEFT/LoRA) and threshold calibration for granular essay/answer grading.
- **Task 3: Compliance & Constraint Verification**: Validates adherence to complex multi-condition instructions, factual consistency, and scoring criteria.

## Repository Structure

The codebase is organized into modular packages to isolate concerns between data handling, model inference, training, evaluation, and experiment tracking:

```text
llm-grading-challenge/
├── README.md
├── pyproject.toml
├── requirements.txt
├── .gitignore
├── .env.example
├── run.sh
├── configs/
│   ├── base.yaml
│   ├── task1/ (baseline_api.yaml, prompt_exp.yaml)
│   ├── task2/ (baseline_api.yaml, lora.yaml)
│   └── task3/ (baseline_api.yaml, lora.yaml)
├── data/
│   ├── raw/ (Raw datasets - excluded from git)
│   ├── processed/ (Preprocessed jsonl/csv files)
│   ├── splits/ (Train/Val/Test ID splits)
│   └── README.md
├── src/
│   ├── data/ (loader, schema, preprocessing, validation)
│   ├── task1/ (prompts, scorer, prerequisite_rules, evaluator, pipeline)
│   ├── task2/ (prompts, dataset, model, train, inference, threshold, evaluator)
│   ├── task3/ (prompts, dataset, model, train, inference, compliance, evaluator)
│   ├── llm/ (api_client, local_model, generation)
│   ├── training/ (lora, trainer, reproducibility)
│   ├── evaluation/ (metrics, error_analysis)
│   └── utils/ (logger, config, seed)
├── scripts/
│   ├── prepare_data.py
│   ├── create_split.py
│   ├── run_task1.py
│   ├── run_task2.py
│   ├── run_task3.py
│   ├── evaluate.py
│   └── build_submission.py
├── experiments/
│   └── registry.csv
├── outputs/
│   ├── task1/
│   ├── task2/
│   └── task3/
├── tests/
├── notebooks/
└── docs/
```

## Quick Start

### 1. Environment Setup

Create or activate your Python environment (Python 3.10+ recommended) and install dependencies:

```bash
pip install -r requirements.txt
pip install -e .
```

Copy the environment file template and supply your API keys:

```bash
cp .env.example .env
```

### 2. Data Preparation

Place the original datasets into `data/raw/`. Run the preprocessing and splitting pipeline:

```bash
python scripts/prepare_data.py --input_dir data/raw --output_dir data/processed
python scripts/create_split.py --data_path data/processed/dataset.jsonl --ratio 0.8 --seed 42
```

### 3. Running Pipelines

Execute baseline and fine-tuned experiments via dedicated runner scripts:

```bash
# Run Task 1 (Rule-based and LLM baseline)
python scripts/run_task1.py --config configs/task1/baseline_api.yaml

# Run Task 2 (LoRA training & inference)
python scripts/run_task2.py --config configs/task2/lora.yaml

# Run Task 3 (Compliance check)
python scripts/run_task3.py --config configs/task3/baseline_api.yaml
```

Alternatively, use the orchestration script:

```bash
bash run.sh --all
```

### 4. Running Tests

Run unit tests across schemas, rule validators, and submission formatting:

```bash
pytest tests/ -v
```

## Experiment Tracking

All experimental runs, hyperparameters, validation scores, and output checkpoint locations are logged to `experiments/registry.csv`.
