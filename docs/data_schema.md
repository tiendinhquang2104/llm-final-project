# Data Schema Specification

This document details the standardized schema and data contracts utilized across all tasks in the LLM Grading Challenge repository.

## Overview

All datasets ingested or emitted by the system adhere to strongly typed Pydantic models. Data is stored on disk primarily as JSON Lines (`.jsonl`) to support streaming, robust parsing, and scalability.

## Core Schema Models

### GradingSample

The primary data entity representing an individual problem, student submission, and associated rubric metadata.

| Field | Type | Required | Description |
|---|---|---|---|
| `sample_id` | string | Yes | Unique identifier for each submission item. |
| `question` | string | Yes | The prompt, question, or problem instruction. |
| `student_response` | string | Yes | The student's written response to be evaluated. |
| `reference_answer` | string | No | Authoritative reference answer or solution. |
| `rubric` | dictionary | No | Grading criteria, weights, and scoring rules. |
| `ground_truth_score` | float | No | Target score used for training or evaluation. |
| `metadata` | dictionary | No | Auxiliary constraints, tags, or split labels. |

### PrerequisiteResult

Output of deterministic heuristic and rule-based screening before LLM inference.

| Field | Type | Required | Description |
|---|---|---|---|
| `passed` | boolean | Yes | True if all prerequisite rules are met. |
| `reason` | string | Yes | Description of failure reason if rejected. |
| `rule_details` | dictionary | No | Key-value breakdown per rule condition. |

### ScoreResult

Unified output format for scoring and evaluation.

| Field | Type | Required | Description |
|---|---|---|---|
| `sample_id` | string | Yes | ID corresponding to the evaluated sample. |
| `final_score` | float | Yes | Final normalized numeric score. |
| `subscores` | dictionary | No | Breakdown of scores across specific rubric criteria. |
| `reasoning` | string | Yes | Explanation or justification for awarded score. |
| `passed_prerequisites` | boolean | Yes | Indicates whether prerequisites passed. |
| `metadata` | dictionary | No | Execution metadata and runtime diagnostics. |

### SubmissionFormat

Official structure for final challenge output submissions.

| Field | Type | Required | Description |
|---|---|---|---|
| `sample_id` | string | Yes | Sample identifier matching evaluation dataset. |
| `predicted_score` | float | Yes | Continuous or discrete grade awarded. |
| `explanation` | string | No | Optional rationalization for auditability. |

## Data Serialization Standards

All files in `data/processed/` must be formatted in UTF-8 encoded JSON Lines where every line is a self-contained, valid JSON object conforming to `GradingSample`.
