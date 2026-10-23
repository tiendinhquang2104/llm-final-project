# Two-pass findings v1 implementation plan

> **For agentic workers:** Execute inline with superpowers:executing-plans; use test-driven-development and an independent final code review.

**Goal:** Evaluate a findings-first two-generate Task 3 arm against unchanged R15 and C-old on 30 locked internal train IDs.

**Architecture:** Reuse dataset loader, HFBackend, two_pass.Journal and existing taxonomy metrics. New structural parser accepts only findings and derives ordered taxonomy from the official on-disk label space. Persist stage1 before stage2; reserve each physical call before generate, reject truncation, never repair feedback or fall back.

**Tech Stack:** Existing Python/pytest/Transformers/Qwen NF4 environment.

**Spec:** User attachment `Pasted text.txt`, complete Task 3 two-pass-findings-v1 assignment received 2026-10-23. This plan records implementation decisions; the attachment is authoritative.

## Global Constraints

- Preserve all existing code/config/prompts/artifacts, split and gold. New branch `two-pass-findings-v1` from fee2c49; initial working tree clean. Work in current checkout to retain access to ignored data/model/artifacts.
- No push/public inference/submission/fine-tuning/D/E. Production default stays R15.
- Same pinned Qwen revision/NF4 BF16 compute/seed42/greedy/chat template; one model load. New stage1 cap1536, stage2 cap1024; context16384; 45s generation limit unchanged.
- Only synthetic-train with metadata/source version verified against original nested archive. No public/heldout inputs. Evidence unavailable unless source-bound trusted compiler/test material exists; no student execution.
- Successful new samples exactly two calls in per-ID sequence. No retry, third call, semantic gate, alias mapping, fallback or editorial postprocessing. Unresolved retained in full status denominator.
- No raw source/gold feedback in committed documents; private artifacts only under ignored outputs.

## Review Focus

- Interrupt after reservation or stage1 save: no call replayed physically.
- Parse-valid JSON returned with length finish: unresolved, even if clean.
- Nested evidence/metadata carrying labels: allowlist; no whole record in prompt.
- Changed source/Level/config/tokenizer: cache identity mismatch.
- Missing outputs/reviews: full denominator and no joint credit for unresolved.

### Task 1: Core contract

**Files:** create `src/task3/two_pass_findings.py`, `tests/test_task3_two_pass_findings.py`, `configs/task3/two_pass_findings_v1_20261023.json`.
**Interfaces:** messages_findings(unit, labels), parse_findings(raw, labels), taxonomy(findings, labels), messages_feedback(unit, findings, labels, definitions), run_units(units, backend, config, out, label_space).

- [x] Write behavior tests for input isolation, schema/enum/order, truncation, sequential persistence, verbatim feedback, no retry, resume provenance and unresolved coverage.
- [x] Run new tests RED, implement using existing journal/backend, rerun GREEN and related baseline tests.

### Task 2: Freeze and experimental CLI

**Files:** create `scripts/task3_two_pass_findings.py` and `tests/test_task3_two_pass_findings_experiment.py`.
**Interfaces:** select/freeze/verify/run/packets/score commands with default private directory `outputs/task3/two-pass-findings-v1-20261023`.

- [x] Lock 30 IDs (10 per Level), prefer families absent from old16+12, stratify official gold labels without modifying gold. Record ID/family exposure as unknown unless historical evidence proves seen; no claims of unseen.
- [x] Hash archive/exam/raw code/evidence, source-only packet, selection and full preservation snapshot. Establish source references before predictions, with independent reviewer where available.
- [x] Test freeze/cache/report denominator behavior RED→GREEN. Freeze one prompt/config candidate, source/reference hashes, exact tokenizer/runtime and old dependency hashes.
- [x] Run original R15 pipeline/config, original C-old (v1 detector plus v2 C renderer), and new pipeline on same inputs with one model load. Old R15 retries/fallback are reported; new arm has none. Optional C-old renderer replay on findings via label/note structural adapter, reported separately.

### Task 3: Offline review, metrics and handoff

**Files:** create `scripts/task3_two_pass_findings_report.py`, `reports/task3/TASK3_TWO_PASS_FINDINGS_V1_20261023.md` and aggregate metrics JSON.
**Interfaces:** blinded packet references complete output and stage1; offline review is bound to source, manifest and results hashes. Scorer reuses taxonomy_metrics and counts gold joint separately from source-grounded joint.

- [x] Blind seeded output ordering, review with same rubric, source-grounded findings before predictions; second review for disputed cases if available. Seal reviews before scoring.
- [x] Report full denominator, per-label TP/FP/FN/F1, exact, finding accuracy/label errors/misses, stage2 inherited/new errors, Level/role and joint. Keep per-ID private table and non-source summary in committed report.
- [x] Validate actual outputs with existing validator, run focused tests and repository suite; disclose pre-existing failures.
- [x] Independent whole-branch code review; address important findings with regression tests. Verify old preservation snapshot, diff and staged files; commit locally, no push.

## Execution ledger

- Initial: baseline related tests 54 passed. GPU RTX5090 available; pinned Qwen cache present. No applicable AGENTS.md found in /, /workspace or repo.
- Design choice: separate new arm using existing journal rather than modifying old engines; old renderer ablation only as replay, never claimed end-to-end. User explicitly requested autonomous implementation, so no design approval pause.

- Task1 complete:66 new tests passed after source/Level/evidence isolation, archive binding, status, denominator and attribution integrity fixes. RED→GREEN logs are private. Existing related baseline54 passed.
- Task2 complete: selection seal0d987472…; source A30+B12 sealed before Qwen; candidate freeze7b125fa2…; one model load, A40/C-old60/C59/ablation29 fresh calls. C29 complete+1 unknown-label unresolved, no retry/fallback; all29 successful C samples exactly2 calls. Replays:30 requested,29 parsed available.
- Full Task3 final:1515 passed,5 skipped,1 known baseline failure (root predictions hash drift predates this branch). Bare pytest:2 Task1 collection errors, missing sklearn. User requires preserving old work, so neither baseline nor Task1 changed.
- Preservation verified:422893 pre-existing files byte-identical. Source corpus30 IDs/27 code hashes, all IDs/families historically present; old16+12 ID/family disjoint. No unseen generalization claim.
- Decisions: use static evidence only because available exec_report strings lack this run's trusted source-bound execution provenance; do not execute student programs. Keep historical artifacts private; no D/E/public work. Production remains R15.
- Review fixes before freeze: reject nested records and nontext task data; lookup own official Level by name; bind prepared exam metadata to verified raw archive; bind transitive runtime and accounting files; score ID-aligned full denominator; validate attribution indices/types and unresolved status consistency. No prompt/config/runtime edits after viewing Qwen outputs.

- Task3 complete: paired reviews A120/B48 sealed before attribution A82/B32. Metrics scored and source/gold joint separated; committed reports contain no raw source or teacher feedback. Gold joint0/30 in A/C-old/C; retainR15. Optional old renderer projection drops structured metadata, so documented as exploratory, not a pure style-only ablation. Secondary finding/lineage disagreements preserved.
- Final disposition explicitly requested by user: local commit only on two-pass-findings-v1, no push/merge/public. Known unrelated test failures remain documented rather than changing preserved baseline artifacts.
