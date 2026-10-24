# Task 3 language × precision implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline; final code review by a fresh reviewer.

**Goal:** Execute the user-approved 2×2 internal Qwen experiment with frozen provenance and auditable review.
**Architecture:** A small prompt bundle/runner module reuses v1 payload/parser/Journal/HFBackend without modifying historical code. A CLI verifies the sealed internal development set, freezes all inputs, loads NF4 once for A/B and original BF16 once for C/D, then exports blinded packets and reports.
**Tech Stack:** Existing Python, torch/transformers/bitsandbytes environment, one RTX 5090.
**Spec:** User-provided `/workspace/llm-final-project/codex-task3-prompt-language-precision-ablation.txt` (read in full). Its instructions override workflow defaults.

## Global Constraints

Exactly A VI/NF4, B EN/NF4, C VI/BF16, D EN/BF16; Vietnamese feedback throughout. Preserve VI bytes and translate only system/guidance, retaining official Vietnamese enum/schema/Level definitions and negative examples. Qwen revision c03e6d358207e414f1eca0bb1891e29f1db0e242, seed42, greedy, context16384, stage budgets1536/1024, max_time45, 2 calls/sample, concurrency1, no retry/fallback/semantic gate. Same sealed30 IDs/27 sources with unavailable compiler/not_run tests. Freeze before first main call; no smoke calls, no prompt tuning, no public inference, no push/PR. Keep private data/output ignored. Commit code/config/tests/aggregate reports only.

## Review Focus

Interrupted reservations cannot generate again; per-arm identity binds entire manifest/config/prompts. Full denominator must include stage failures; feedback remains exactly JSON-unescaped. Precision audit checks actual CUDA storage and Linear4bit, not a mock flag. Old sealed source references and code/archive metadata must bind exactly. No content metric may be inferred from keyword statistics alone; blind qualitative review required, independence limits disclosed.

### Task 1: prompts and runner
- [x] Write and run failing tests for matrix, VI bytes, EN preserved payload, per-Level messages, malformed/EOS/enum handling, clean union, resume/identity and feedback preservation.
- [x] Implement `src/task3/language_precision_ablation.py` and `configs/task3/language_precision_ablation_v1.json`. Reuse v1 Journal/parser. Keep runtime/config instrumentation local to new runner/backend subclass.
- [x] Run new and historical tests, including precision regression. Expected: all selected tests pass.

### Task 2: provenance, freeze, execution
- [x] Implement `scripts/task3_language_precision_ablation.py`: prepare/freeze/run/packets/report. Verify historical selection/source seals and original/nested ZIP hashes, source code/semantic/evidence/Level/gold. Produce translation alignment and freeze code/deps/tokenizer/config before inference.
- [x] Preflight GPU; run fixed arm-major A30,B30 then C30,D30 sequence with two model loads, separate journals, full raw/rendered/runtime artifacts, no repair/retry. Audit original BF16 storage. Expected: all30 IDs accounted per arm even unresolved.

### Task 3: review, reporting, handoff
- [x] Generate opaque shuffled review packets using old source-only references and preselected balanced second-review subset; review full120 outputs against one rubric, preserving disputes and main finding inventory. Record independence limits honestly.
- [x] Compute final/stage1 ten-label metrics, content/Level/voice/placeholder/joint counts, paired ID deltas and interaction, costs/runtime, source clone limits. Write full per-ID table privately and aggregate report publicly.
- [x] Validate completed subsets/full sets correctly; ZIP all private evidence. Final fresh code review and regression verification, preservation hashes, commit only approved public files. No push/PR.

## Ledger

Baseline HEAD35c2915 exactly matches reference; only user prompt untracked in original checkout. Isolated sibling worktree shares old artifacts/cache by symlink; no model/data copy. Baseline66 findings tests passed. Initial test command named nonexistent inference glob; corrected to discovered precision test file, no test failure hidden. Design already fixed/authorized in user's spec; execute without another approval gate.

Prefreeze independent review: two runtime issues fixed with RED→GREEN fixtures: reset arm peaks while retaining load/group peaks; preserve first runtime snapshots plus per-invocation measurements and append-only load events. Core prompt/provenance/inference review passed.

Completion ledger: Task1 complete, Task2 complete (freeze143b78b/2e625172...,238 physical calls,2 loads, no extra calls; A/B29,C/D30). Task3 complete: two blinded agents independently reviewed30×4 each/289 findings; ratings sealed; conservative and dispute-gate sensitivity both joint-gold0 all arms. Main report includes all10 labels, paired contrasts, inventory/Level/voice/attribution and private evidence index.
Final review fixes: per-arm peak reset and immutable invocation measurements; claim/faithfulness consistency, nonoptional L3 evaluation and all material dispute coverage (RED→GREEN). ZIP receipt excluded on repeat packaging and scored seal checked before mutations. No deferred minors.
Ruling: source domain notes and any finding dispute require secondary coverage, but standalone source notes do not automatically invalidate every feedback. Conservative published pass additionally excludes output/finding disputes; explicit sensitivity without that gate keeps joint-gold0. This prevents taxonomy-only uncertainty from being mistaken for proof that every feedback sentence is false. Counts per reviewer remain separate; combined inherited/new counts are category maxima, not deduplicated assertions.
Verification:171 related tests pass. Existing test_task3_eval_v2 baseline failure independently reproduced at original35c2915, only root predictions.json hash drift9ba741...→c30c5c...; baseline untouched. No full-suite green claim, Task1/2 dependency installation, public run, push or PR. Branch/worktree preserved as explicitly requested by user spec.
