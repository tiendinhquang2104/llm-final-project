# Task 3 matched base–V3 control implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline. The user explicitly requests execution through completion, forbids commits and worktree changes, and supplies the complete experiment design.

**Goal:** Generate exactly 120 single-attempt prepared-base responses under historical P_v3, reuse 120 frozen V3 responses/verdicts, review and report in Vietnamese.

**Architecture:** Add a bounded orchestration script; reuse load_native, native context generator/parser, durable Journal, matching validation, metric helpers, and HTML escaping/rendering conventions. Preserve all existing files. Freeze all experiment inputs before any generation; abort for a proven mismatch.

**Tech Stack:** Existing Python 3.12 task3 venv, PyTorch/Transformers/PEFT/bitsandbytes, installed C++ sandbox only for concrete unresolved claims.

**Spec:** /root/.codex/attachments/9fbc5d40-f9e3-4525-a744-2b7259bb4baf/Pasted text.txt (also copied verbatim into new output request.txt).

## Global Constraints

- Stay in /workspace/llm-final-project-arm-d-plus on fix/task3-strict-feedback; preserve all changes; no commits, push, training, public inference, or public prediction edits.
- Exact historical 40 sources, 20 families, Levels 1–3 only; 60 clean/60 faulty; 120 calls, 120 V3 reused by binding; no semantic retry.
- Exact historical prompt/tokenizer/model/preparation/generation/parser. No extra model calls for verification.
- Original gold and V3 verdicts are immutable primary evidence; disputes get a separate record.

## Review Focus

- Reordered/misbound targets must fail, including source/Level collisions and token hash mismatch.
- Interrupted reservations must never issue another model call; completed calls must be recovered from journal.
- Disabled LoRA must preserve all non-adapter parameters and quantization state; merged weights forbidden.
- Invalids remain unknown assessments and in primary denominators; L1 omits prohibited detail without penalty.
- Semantic review assesses actual execution conditions and repair usefulness, never keywords/length.

### Task 1: frozen control runner

- [ ] Add integrity tests for journal corruption, completed/unknown resume, target mismatch, Level exclusion, and single-attempt ceiling; run RED.
- [ ] Add scripts/task3_base_pv3_control.py using existing infrastructure; freeze historical input hashes, code/dependencies, budget, rubric and metric definitions.
- [ ] Verify installed PEFT disable mechanism, enabled runtime against saved V3 runtime, all input IDs, eval, no merge, and unchanged non-adapter weights. Save matching-audit.json before first call.
- [ ] Run focused tests GREEN, then execute all 120 calls and demonstrate resume skips them.

### Task 2: source-grounded review

- [ ] Inspect all base responses against complete unchanged source/specification/gold/private witnesses; record nine axes, assessment, unsupported claims and contradiction reasons per response.
- [ ] Preserve all historical V3 verdicts; inspect factual disagreements, version disputes separately; only concrete new claims can trigger additional sandbox tests.

### Task 3: comparison/report and verification

- [ ] Reuse summarize_system and paired_analysis; add paired diagnosis/repair transitions and family status-versus-real-diagnosis counts.
- [ ] Produce every requested artifact, deterministic six-example selection, complete searchable casebook, cost scope and one bounded next-training proposal (not executed).
- [ ] Verify exact populations, raw hashes, review bindings, metric denominators, zero extra/replayed calls and preserved workspace. Request one fresh final integrity review per executing-plans skill.

## Execution ledger

Ruling: The user's explicit execution request and fixed design supersede the skills' optional design approval/handoff, worktree creation and commit defaults. Execute inline without another approval gate. No design search or prompt changes.
