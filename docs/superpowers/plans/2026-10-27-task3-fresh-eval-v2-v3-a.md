# Task3 fresh A / V2-old / V3-v3 Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for the narrow runner and integration; use superpowers:dispatching-parallel-agents for independent provenance, corpus, authoring and blinded review work. Steps use checkbox syntax for tracking.

**Goal:** Complete a newly authored, frozen20-family/40-source evaluation and conservatively screen V3 against V2-old and authentic historical A.

**Architecture:** Reuse pinned native loading/rendering/generation/parser, historical A controller and established CppSandbox. Add a small experiment-specific orchestration layer plus report/decision helpers; keep all authored data, private gold, evidence, journals and reviews in one new run. Dataset/gold validation and policy freeze precede every evaluated call. L1–L3 are primary; L4 is separate secondary evidence.

**Tech Stack:** Existing Python3.12.3 virtualenv, pinned PyTorch/Transformers/PEFT/bitsandbytes, Qwen2.5-Coder-7B local snapshot, C++11 through existing chroot/UID/seccomp/resource-limited sandbox; standard-library offline reporting.

**Spec:** `outputs/task3/fresh-eval-v2-v3-a-20261027-run1/request.txt` (verbatim user request).

## Global Constraints

- Existing worktree `/workspace/llm-final-project-arm-d-plus`; required branch `fix/task3-strict-feedback`; actual HEAD `7ad8fd4a66b82f72579170618db3370eaf7dee14`.
- Interpreter `/workspace/llm-final-project/.venv-task3/bin/python`; no package upgrade, training/optimizer, prompt tuning, public inference/export, upload/submit or git mutations.
- One never-overwritten run: `outputs/task3/fresh-eval-v2-v3-a-20261027-run1`; preserve every preexisting uncommitted file, dataset, checkpoint and prior artifact.
- Exactly20 new families, one clean/faulty same-spec pair each,40 sources, four Levels/source,160 targets per available system; no gold/tests/witnesses/expected output in Qwen input.
- At least6 multi-function families and several longer meaningful programs; exclude direct rewrites of locally observed families and document corpus limits.
- Authentic A is a system comparator. If unreproducible, mark unavailable and finish V2/V3. Do not invent a replacement. Current audit provisionally locates actual candidate hash and native three-attempt controller; verify before freezing.
- V2/V3 use actual selected step240/480, native P_old/P_v3 and repetition_penalty1.1; A retains its own authentic dtype/EOS/context/controller/recovery policy.
- Up to480 end-to-end evaluations. Provisional generation ceiling800 if A has3 attempts ×160 plus native1 ×320; freeze exact available-system budgets before calls. No warmup, semantic verifier or added retries.
- Official Level authority is archive `label_space.json`: L2 location/cause can be precise and multi-sentence; L3 useful direction but no full solution; L4 code permitted, not required.
- All semantic claims are source-grounded agent review, not independent human gold. Dataset claim: newly authored and not previously evaluated; no pretraining-independence or official-score claim.

## Review Focus

1. Private gold or clean/faulty cues enter prompt/dataloader: strict input whitelist, opaque IDs and role/token/hash exports must reject leakage.
2. Wrong adapter or historical A substitution: saved selection/candidate hashes, actual tensor identities, one active adapter/eval/dtype assertions; A differences explicit.
3. Interrupted/invalid/recovered results disappear: durable reservations, complete-target skip, uncertain no replay, first/final attempts retained and all denominators complete.
4. Gold ambiguity/corpus overlap: exact+whitespace hashes, semantic/template screen and independent oracle/sandbox discrimination for every pair before freeze.
5. False praise/disclosure/Level confusion causes false promotion: independent correctness/content/disclosure/contradiction axes; conservative uncertain handling; L4 excluded from primary decision; family is statistical unit.

## Task1 — Provenance, dataset design and private gold

**Files:** run `audit/*`, `authoring/*`, `sources/*`, `dataset.private.jsonl`, `gold.private.jsonl`, `dataset-manifest.json`, `evidence/*`; plan ledger here.

**Interfaces:** Dataset row contains opaque `sample_id`, `family_id`, statement, code, C++11 full-program submission mode, checker; private gold keyed by source holds status/taxonomy/location/mechanism/conditions/witness/acceptable and unacceptable L3 directions. Target IDs append requested Level1–4 only. Test cases use existing `{input,expected,files?}` format; metadata never sent to model.

- [x] Verify actual branch/checkpoint/path and create fresh86,052-file byte-preservation snapshot before new work.
- [x] Audit A/V2/V3 actual configurations/callable code and official archive contract; record availability and precise runtime/controller differences.
- [x] Inventory available train/dev/test/final/crossover/source archives; exact/whitespace and semantic/template checks; record unavailable scope.
- [x] Design20 family pairs, reject weak semantic rewrites, then author varied clean/faulty C++ and independently structured Python oracles/test domains.
- [x] Validate every clean through authored tests and every fault with discriminating witness or compile evidence in CppSandbox; record finite-test limits and minimality scope. No unconfined execution.
- [x] Independently review private gold/source/spec and repair ambiguous pairs before freeze; enforce exactly20/40/160 and coverage/length/multi-function requirements.

## Task2 — Narrow frozen execution wrapper

**Files:** new `src/task3/fresh_eval.py`, `scripts/task3_fresh_eval.py`, `tests/test_task3_fresh_eval.py`; run `systems.json`, `frozen-policy.json`, `manifest.json`, `prompts/*`, `generations/*`.

**Interfaces:** `EvaluationJournal(path, system_budgets, target_ids)` for native one-attempt calls and authentic A bounded attempts; `validate_dataset`, `validate_target_rows`, `screen_v3`; CLI stages validate/freeze/run/evidence/review/metrics/verify. Reuse `native_prompt`, `load_native`, native `generate`, A historical `run_arm`/controller with isolated syntax metadata, existing payload parsers and code sandbox. Distinct first and final A outputs preserve raw attempts/controller final identity.

- [x] Write failing focused tests for budgets/foreign IDs/uncertain resume, input whitelist/bindings, primary-vs-L4 decision/family grouping and false-praise gates; observe RED, implement minimal helpers and GREEN.
- [x] Freeze official policy, exact systems, new dataset/gold hashes, allowed model fields, actual prompt/token IDs, context+recovery headroom, parser/recovery/call budgets and deterministic example/decision rules.
- [x] Inspect real model/tokenizer/dtype/adapter dispatch before each phase, no extra forward; fail technical integrity mismatches before evaluated calls. Record actual observation scope rather than proposed hooks.
- [x] Execute all160 targets/system through each authentic pipeline, save every completed target and attempt; continue poor outputs/invalids; no tuning or cherry-picking.
- [x] Preserve first/final outcomes and failure/recovery costs; native one attempt, A existing bounded recovery; safe complete/uncertain resume.

## Task3 — Blinded review, metrics and deliverables

**Files:** run `review-packets/*`, separate identity mapping, `reviews.private.jsonl`, `metrics.json`, `comparison.json`, `costs-and-runtime.json`, `decision.json`, `paired-casebook.html`, `EXAMPLES.vi.md`, `REPORT.vi.md`, `reproduction-commands.json`; new `scripts/task3_fresh_eval_report.py` if needed.

**Interfaces:** Reuse crossover nine-axis source-grounded summary/joint/paired functions with new system keys. Final-state review mandatory for all480 available-system records. First-attempt A objective outcomes reported separately; any extra semantic first-view review clearly labeled and excluded from primary target counts. `screen_v3` consumes only L1–L3 joint, faultyL2–L3 diagnosis, faultyL3 repair, clean alarms, invalids and per-source contradiction/disclosure judgments. Per-source primary success0..3, per-family pair success0..6; no individual-target confidence intervals.

- [x] Boundedly check supplied code/snippets/examples, with raw/case bindings and no JSON repair; isolate all generated C++.
- [x] Review under opaque system IDs with map separate until fixed; exact whole-panel groups, every record/invalid retained; evidence for failure/dispute and explicit uncertainty.
- [x] Primary L1–L3 and separate L4 tables; clean/faulty, source/family counts; auxiliary taxonomy, contradictions/Vietnamese/disclosure; paired W/L/T/U and full objective transitions.
- [x] Apply each pre-frozen screening condition versus V2-old and authentic A. Strict joint improvement and no worse diagnosis/repair/alarm/invalid; no systematic new contradiction or Level failure. Ambiguity/dispute is not a pass; keep A baseline if mixed.
- [x] Publish all sources/spec/raw/parsed/gold/evidence/verdicts in casebook; at least6 fixed-rule examples covering clean/faulty, improvements/regressions, two L3 repairs, contradictions/invalids when present. Identify at most3 dominant failure mechanisms and later-training-example proposals if V3 fails, without training.
- [x] Record load/generation/compiler/runtime/recovery/failure time, tokens and peak VRAM scope; no unknown metering invented as0. Fresh review/code review, focused regression and preservation verification; seal artifacts and exact reproduction commands. Final response Vietnamese with completed counts, decision/baseline, comparisons, six evidence-backed examples, costs/limits and one next action.

## Pre-flight interface ledger

- Task1→Task2: only public-safe statement/code/mode/language/syntax log/Level are rendered; private metadata stays in gold/evidence. Syntax log produced separately with real C++11 syntax-only flags inside existing confinement.
- Task2→Task3: final raw and authentic A attempts/controller metadata remain immutable; semantic review cannot alter inference or select attempts.
- Task3→decision: L4 never enters primary screening; all systems share rubric while authentic A system differences remain labeled.

## Execution ledger and rulings

- Initial state: required branch/HEAD present; V3 selected adapter file present. Snapshot contains86,052 preexisting non-cache files and full git status; one new run created exclusively.
- Ruling: user's explicit end-to-end execution instruction and fixed worktree/no-commit constraints override skill approval, worktree and commit gates. Execute native integration without pausing for design permission; independent audit/authoring/review delegation follows dispatching skill. Preserve scratch/evidence rather than delete the run.
- Ruling: source IDs must not encode clean/faulty status in inference. Native renderer already omits IDs; use opaque source IDs and no status-bearing source comments/diagnostic basenames.
- Ruling: no uncertainty intervals are required; report paired source/family summaries directly. If intervals are added, family/pair resampling only, descriptive for this authored sample.

- Pre-generation evidence: all20 clean references pass3490 inputs; all20 faults discriminated;6895 total sandbox runs,40 full compiles+40 confined syntax checks. Gold/novelty reviewer passed all40 source and160 target bindings;1686 historical exact sources/1660 normalized groups/299 statements screened. FE04 ID bounds clarified and FE11 minimum triangle witness promoted from existing execution index48 before freeze; evidence order preserved.
- Focused pre-freeze regression:69 passed. Independent runner review identified interrupted A accounting; corrected to global completed/reserved ledger, pending reviewer recheck. No evaluated model calls yet.

- Execution complete:480 fresh end-to-end targets,505 actual calls (A185,V2-old160,V3-v3160); no unknown calls. Zero-call/zero-load completed-target resume verified. A first schema159/160, final160/160;25 recovery calls and11 authentic fallbacks. Native invalids2/7, all at L4.
- Blind review: all480 verdicts fixed and sealed before identity reveal; seven localized-code resolutions; two genuine prose uncertainties retained (one primaryV3, one L4V2). Generated code53 compiles/5583 sandbox tests.
- Frozen screening failed: primaryjoint A34,V2-old62,V3-v357 of120; faultyL23diagnosis7/2/4 of40; usefulL3repair1/0/2 of20. V3 remains ineligible for public inference; retain A submission baseline. No training/public inference/git mutation.
- Final verification: fullTask3 suite2072passed15skipped; independent artifact review passed, all480 packet/generation/review bindings and readable artifact recomputation match;86,052 preexisting files preserved. Final artifact hash sealing and read-only verifier are recorded in run status/seal.
