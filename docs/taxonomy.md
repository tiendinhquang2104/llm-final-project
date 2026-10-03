# Challenge Taxonomy and Grading Criteria

This document defines the conceptual hierarchy, evaluation rubrics, and error classification taxonomy used throughout the LLM Grading Challenge.

## Evaluation Dimensions

Student responses are evaluated across three primary dimensions:

### 1. Factual and Conceptual Accuracy

Measures the factual correctness, truthfulness, and domain fidelity of the submitted response relative to canonical ground-truth knowledge and task requirements.

- High Fidelity: Fully accurate assertions, precise technical terminology, and zero hallucinations.
- Moderate Fidelity: Primarily correct concepts with minor inaccuracies that do not compromise primary logic.
- Low Fidelity / Factually Defective: Major misconceptions, incorrect facts, or contradicted reference knowledge.

### 2. Reasoning Depth and Completeness

Evaluates whether the student demonstrates clear step-by-step problem-solving, causal relationships, and thorough coverage of all sub-questions.

- Comprehensive: Explores nuances, explains mechanism of action, and addresses all question constraints.
- Superficial: Gives bare assertions without supporting evidence or mechanistic reasoning.
- Fragmentary: Omits core components of the requested prompt.

### 3. Structural Clarity and Expression

Assesses organization, grammatical correctness, concise phrasing, and readability.

- Structured: Cohesive paragraph structure, logical transitions, and unambiguous terminology.
- Disorganized: Rambling prose, self-contradictory clauses, or ambiguous phrasing.

## Error Taxonomy

When conducting residual and failure analysis (`src/evaluation/error_analysis.py`), errors are categorized under the following taxonomy:

| Error Category | Code | Description | Typical Remediation |
|---|---|---|---|
| Prompt Length Bias | `ERR_LEN` | Model awards higher scores to long, vacuous responses. | Enforce length normalization and rubric penalties. |
| Hallucination Tolerance | `ERR_HAL` | Model overlooks factually incorrect claims amidst fluent text. | Introduce fact-checking subprompts or prerequisite rules. |
| Strictness Drift | `ERR_STRICT` | Inconsistent scoring threshold variance across batches. | Use low temperature (0.0) or few-shot calibrated anchors. |
| Constraint Neglect | `ERR_CNST` | Model ignores negative constraints or explicit formatting instructions. | Run dedicated Task 3 compliance auditor. |
| Non-attempt Misclassification | `ERR_REFUSAL` | Model awards partial points to refusal or empty answers. | Filter via prerequisite rule checker. |
