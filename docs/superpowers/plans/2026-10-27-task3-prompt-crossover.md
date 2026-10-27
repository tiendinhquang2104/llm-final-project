# Task 3 Prompt Crossover Implementation Plan

> Execution: superpowers:executing-plans for native implementation; superpowers:dispatching-parallel-agents for independent runtime/input audits and source-grounded review. The user's explicit instruction to execute through reporting overrides additional approval, worktree, commit and integration defaults. No git mutation.

**Goal:** Compare V2 step240 and V3 step480 under the exact historical native old and v3 prompts on the existing dev80, with a technically matched runtime and separate diagnosis/disclosure results.

**Architecture:** Reuse the existing native renderer, pinned NF4/BF16 loader, explicit-context single-attempt generator, durable Journal, strict payload parser, bounded code evidence, and offline casebook patterns. Add a separate crossover wrapper and analysis; preserve every historical byte. Historical cells are reused only after evidence establishes equivalence; otherwise run that entire cell fresh under the frozen common runtime.

**Tech Stack:** Existing task3 Python environment, Transformers/PEFT/bitsandbytes/PyTorch, local pinned Qwen, offline HTML/JSON/Markdown.

**Spec:** `outputs/task3/prompt-crossover-20261027-run1/request.txt`.

## Global constraints

- Repository `/workspace/llm-final-project-arm-d-plus`; branch `fix/task3-strict-feedback`; HEAD `7ad8fd4a66b82f72579170618db3370eaf7dee14`.
- Interpreter `/workspace/llm-final-project/.venv-task3/bin/python`; no training, public inference, submission, git mutation, historical verdict edits, or root prediction overwrite.
- Same20 sources/four Levels/80 targets; no oracle/private findings/target feedback in generation input.
- Exact two prompts preserved. Only prompt and selected adapter may vary; non-equivalent historical cells are not mixed into a cell.
- Fresh cells: one attempt per target,80 each, total at most320; no warmup/retries/verifiers. Freeze the actual reuse decision and call ceiling before inference.
- Official L2 allows multiple sentences; L4 code optional; wrong advice assessed separately from disclosure. False praise on faulty code fails assessment and task success.
- Current 85,460 preexisting files are hashed before new work. Preserve existing datasets, checkpoints, outputs, selections and uncommitted files.

## Approaches and design decisions

The requested conditional reuse design is used: prove equivalence and retain historical raw outputs, rather than assuming every old cell matches or regenerating proven-equivalent cells. If proof is incomplete, use the user's authorized fresh-cell fallback and document the confounder. Context32768 is the common admission guard; actual computation must match the historical implementation for reuse. The user has supplied the full execution design; no additional preference is required.

## Review focus

- A reserved call without completion must remain explicitly uncertain and never be replayed.
- A changed prompt/source/parser/model hash must block resume or reuse.
- Invalids stay in all primary denominators and all requested IDs are covered exactly once.
- False clean praise may pass disclosure but cannot pass diagnosis or successful feedback.
- Paired transitions must align source+Level, distinguish uncertain semantic changes, and preserve full label-set transitions.

### Task 1: Audit and freeze the matched design

Files: new run `audit/*`, `reuse-audit.json`, prompt exports/diff/token records, `manifest.json`, `inputs/*`, `evaluation/*`.

- [x] Independently audit runtime/adapter provenance and exact prompt/input safety.
- [x] Record a readable reuse decision for all three historical cells, including context8192/32768 effects and inherited generation settings.
- [x] Export unchanged prompts, real80×2 token lengths, renderer/role/input differences and exact hashes.
- [x] Freeze all four cell identities, common runtime, parser, review policy and actual new-call ceiling; announce cells/call count before inference.

### Task 2: Implement and execute bounded crossover

Files: `src/task3/prompt_crossover.py`, `scripts/task3_prompt_crossover.py`, `tests/test_task3_prompt_crossover.py`.
Interfaces: `CrossoverJournal(path,fresh_cells,expected_ids)`; `summarize(rows)`; `paired_analysis(before,after)`; CLI stages `freeze`, `run`, `code`, `packets`, `metrics`, `verify`.

- [x] Write/run failing tests for per-cell/global ceilings, foreign/reused-cell reservations, uncertain resume, exact-ID pair alignment, full label transitions and false-praise diagnosis versus disclosure.
- [x] Implement the small wrapper using unchanged native components; run meaningful regression checks.
- [x] Complete every fresh cell once; verify actual adapter tensor hashes, dtype/eval/dropout/attention and exact prompt+token bindings before each cell.
- [x] Preserve raw failures/termination and actual timing/memory; no semantic intervention.

### Task 3: Review all320 records and report

Files: separate blinded packets/quality/verdicts; `scripts/task3_prompt_crossover_report.py`; Vietnamese report/examples and offline complete paired casebook.
Interfaces: expanded rows carry `cell,sample_id,example_id,level,status,raw,parsed,faulty,gold_taxonomy,axes,code_verdict,evidence`.

- [x] Freeze one rubric separating disclosure restrictions from required diagnostic/hint content and successful feedback; apply it anew to all four cells.
- [x] Reuse valid compiler/runtime evidence only with exact response/case bindings; review supplied snippets and factual examples separately.
- [x] Complete blinded source-grounded reviews and validate exact full-panel groups/320-ID coverage; label agent review honestly.
- [x] Compute objective and semantic metrics by cell/Level/status, all four paired comparisons, full objective label transitions and semantic win/loss/tie/uncertain.
- [x] Select examples deterministically across source families, publish every case, and state diagnosis tradeoffs without selecting by disclosure/joint alone.
- [x] Run fresh code review, applicable tests, full preservation verification and new artifact sealing. Report actual new/reused calls, technical matching, prompt/adapter associations, one evidence-backed next action and development-set limitations.

## Interface ledger

- Task1→Task2: frozen per-cell old/v3 prompt hashes, verified selected-adapter paths and reuse decision drive generation; no inference before freeze.
- Task2→Task3: durable raw rows and bounded code evidence drive new reviews; historical verdicts are evidence only and remain untouched.
- Task3→report: all320 completed verdicts required; pending or duplicate/foreign IDs block reporting.

## Execution ledger

- Initial snapshot:85,460 non-cache preexisting files; actual HEAD/branch/status recorded. Skill branch/worktree/commit steps are inapplicable under the user's explicit preservation constraints.
- Independent runtime and prompt audits prescribe 160 fresh calls (v2-old, v3-old) and 160 reused outputs (v2-v3, v3-v3). The 8192/32768 guard is nonbinding; effective inherited repetition_penalty is 1.1. Explicit BF16 locks all 196 bitsandbytes compute flags at construction; dependency sources match installed wheel records.
- Fresh runner review found three important gaps, addressed with failing-then-passing regression checks: external runtime/tokenizer guards, durable raw/journal integrity even for complete cells, and explicit cross-input false-alarm/miss examples.
- First freeze failed during verification of legitimate same-model Hugging Face blob symlinks, before any model call. Its manifest, seal, source snapshot and log are preserved in preflight-failed-1; preflight-failures.json records the correction.
- Latest focused checks: 39 passed. Broad Task3 regression: 2,031 passed, 15 skipped. Full-repository collection is limited by missing sklearn in two unrelated Task1 modules; no dependencies installed.
- Generation complete: v2-old 80 calls /142.9164549075067 generation seconds /6,447 output tokens; v3-old 80 calls /93.54770569689572 seconds /4,165 output tokens. Zero uncertain reservations; two reused cells retain all160 raw rows. Fresh v2-old raw bytes match rejected-for-reuse historical outputs80/80 in a secondary read-only audit; actual cost remains160 fresh calls.
- Bounded feedback-code evidence complete320/320:15 new compile calls,124 new runtime calls;160 exact-bound historical evidence rows reused. New blinded review has282 whole-panel groups covering320 records, split98/100/84 among three isolated source-grounded reviewers. Shared interpretation notes in review-conventions.md; no identities or historical verdicts supplied to reviewers.
- Final executed Task3 suite against frozen implementation:2,031 passed,15 skipped in12.85s. Generation integrity confirms160 reservations/160 completions/zero unknown, exact320 target coverage, strict parser recomputation and preservation of85,460 original files.
- All282 blind panels/320 records reviewed anew with evidence and explicit contradiction flags. Independent objective count/P-R-F1 cross-check passed after a helper field-name mapping correction (failed log retained). Metrics, all4 paired comparisons, complete80×4 casebook, expanded technical appendices and concise Vietnamese reports published. Presentation-only composer and exact reproduction commands saved separately from frozen inference code.
- Final artifact reviewer independently recomputed coverage, transition/W-L-T-U arithmetic and HTML card/verdict joins; no Critical/Important finding. It caught prospective hook/post-cell language in the frozen dtype addendum: only actual pre-cell profiles were measured. Scope limits are disclosed in a separate JSON, readable audit/main/reproduction; frozen JSON is unchanged and no extra forward was performed.
- Final native verification passed after publication; all85,460 preexisting files, HEAD/branch and root predictions SHA preserved. Final artifact review is stable with no requested implementation/verdict changes; run status and SHA index seal the completed deliverables. No next experiment was started.
