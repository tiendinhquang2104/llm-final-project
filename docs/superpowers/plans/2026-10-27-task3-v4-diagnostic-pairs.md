# Task 3 V4 diagnostic pairs implementation plan

> **For agentic workers:** Use executing-plans inline; dispatch independent data-author batches via dispatching-parallel-agents. User explicitly authorizes end-to-end execution without planning handoff and forbids git/worktree mutations.

**Goal:** Author/validate88 family pairs (528 L1–L3 targets), train one fresh pinned-base adapter for96 steps, complete504 bounded evaluations, dev-only selection and Vietnamese report.
**Architecture:** Reuse native_prompt/encode_examples/make_trainer/equal-example loss, load_native/new_adapter, durable journals, CppSandbox, metric and casebook helpers; small adapters for three-Level population and new selection rule. No new inference pipeline/verifier or public inference.
**Tech Stack:** Existing task3 Python3.12 venv, pinned Qwen/PEFT/NF4 stack, established C++ jail.
**Spec:** outputs/task3/sft-v4-diagnostic-pairs-20261027-run1/request.txt

## Global constraints
- Stay on fix/task3-strict-feedback in existing worktree; no commit/push/upload/submission/public inference. Preserve all prior state.
- Quotas12/20/20/16/12/8, splits64/12/12 whole families preallocated. No L4, no historical family training, no metadata leakage.
- Main384 examples once,96 optimizer steps; lr2e-5, one epoch, checkpoints48/96, assistant-only equal-example CE, all fixed recipe values per spec.
- Dev288 generations then sealed selection, test216; single-attempt504 maximum, no old fresh-eval rerun.

## Review focus
- Novelty exact/whitespace plus semantic/template overlap, related groups kept in one split.
- Clean/faulty/repaired evidence distinguishes one root; compile failures never invented runtime evidence.
- Real minibatch full assistant/termination supervision and padding mask; train dataloader excludes dev/test.
- Checkpoint/journal parity prevents optimizer replay; generation interrupted reservations never replay.
- Pair discrimination distinct from labels/style, uncertainty explicit, test inaccessible before selection seal.

### Task1 data/evidence
- [x] Allocate before authoring, preserve prior workspace, author independent batches88, inventory corpus.
- [x] Validate all pairs via existing CppSandbox, repair pass, target consistency/schema/disclosure, overlap audit and dataset card.
### Task2 frozen runtime/training
- [x] Add relevant failing tests, small three-Level training/evaluation wrappers, verify tests.
- [x] Freeze data, code, metrics, prompt/model/runtime/recipe/selection/budgets, inspect actual minibatch; train96 steps with resumable checkpoints and verified exposure/base identity.
### Task3 dev/selection/test
- [x] Dev4×72, opaque source-grounded review, metrics, exact eligibility/ranking, seal selection before loading test outputs.
- [x] Test3×72 single attempts, all semantic reviews including uncertainty, comparisons and examples.
### Task4 report/verification
- [x] Complete costs/model-load/train/smoke/generation/teacher-forced/compiler/runtime accounting, searchable casebook and Vietnamese report.
- [x] Fresh final review and full artifact/workspace verification; no public action.

## Execution rulings
- New request supersedes proposal: learning rate2e-5 (not1e-5), include V3 comparator in both splits,504 evalcalls (not360), pair-success primary and eligibility relative to V3 (not absolute2/36 and1/72); ranking exactly specified. No training has started at planning time.
