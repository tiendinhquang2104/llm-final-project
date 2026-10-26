# Controlled Task 3 SFT v1 QLoRA experiment

**Goal:** Execute the user-authorized first experiment, not another CPU preflight.
**Spec:** attached request copied into the fresh experiment directory before execution.
**Architecture:** Reuse sft_v1 loader/encoder/Trainer factory and completion loss. Add a local-only runner with journaled single-attempt generation, native resumable Trainer checkpoints and source-grounded paired review. Native dataset prompt throughout.
**Method:** NF4 double-quantized pinned Qwen base, BF16 compute, fixed YAML recipe, seed 42; smoke 16 targets/4 steps; fresh main 640 targets/160 steps; checkpoint dev at 80/160; select by dev loss then test.
**Authority:** The supplied request explicitly authorizes implementation, inference, GPU smoke, main training and evaluation. No additional design approval, branches, commits, pushes or submissions.

## Tasks
- [x] Preserve existing bytes and verify cached preflight identity; inspect environment and actual Trainer accumulation.
- [x] Write regression tests before runner implementation: strict recipe mapping, checkpoint selection, interruption-safe call accounting, RNG isolation and gradient accumulation objective.
- [x] Add runnable local GPU entry point and freeze code/data/tokenizer/dependency/parser/rubric/settings/call budgets/smoke IDs before any model evaluation.
- [x] Baseline dev loss + 80 generations before training; complete casebook, retain invalids.
- [x] Real Qwen smoke 4 steps, masks/private-input guard, adapter gradients/deltas/base-freeze, save/reload logits and 2 generations; fresh initialization for main.
- [x] Main 160 steps, resumable checkpoints 80/160 plus native optimizer/scheduler/RNG, dev losses and 80 generations each, eval RNG isolation.
- [x] Persist selection before test; base + selected test loss/80 generations each; no unselected test.
- [x] Review all outputs by source/spec across states (agent review, invalids not_evaluable), paired HTML, metrics/costs, Vietnamese report, final validation and reproduction/resume commands.

## Frozen evaluation
400 primary generations: base-dev, step80-dev, step160-dev, base-test, selected-test (80 each). Two additional smoke train generations only. Greedy concurrency 1, max_new_tokens 1024 L1-3/1536 L4, max_time45s. Prompt-only generation, no repair/retry. Parser may remove only an entire outer JSON fence. Every invalid retained. Quality rubric covers diagnosis/location/trigger/unsupported defects/Level/Vietnamese/L3 repair/L4 solution, explicitly separate from taxonomy and checkpoint loss.

## Resume policy
Immutable manifest plus per-call reservation/result journal prevent duplicate generations. Completed phases skipped. A reserved generation lacking output becomes an explicit missing/uncertain record, never a retry. Main resume requires native optimizer/scheduler/RNG checkpoint and no journaled optimizer progress beyond it; ambiguous mid-step interruption is refused explicitly rather than replayed silently. Evaluation preserves Python/NumPy/CPU/CUDA RNG around all teacher-forced and generation work.

## Independent work
Evaluation/parser/HTML module and its tests delegated under dispatching-parallel-agents; parent owns GPU training runner and its tests. Shared interfaces fixed before implementation. No agent is authorized to run a second GPU trajectory.

## Execution ledger
- Pre-execution regression:80 passed. Review fixes applied before immutable freeze (resume dev recovery, initial identity preservation, smoke args, artifact binding, uncertain calls).
- Run:outputs/task3/sft-v1-qlora-20261026-run1; frozen manifest SHA266866bd2d115f1dbd993ae981ecd284d2027df44945fa68023620ed371496d5.
- Baseline dev completed80calls; mean loss2.2237816662, valid80/80.
- Real GPU smoke completed4optimizer steps/16trainforwards,392adaptertensorschanged, basefrozen, reloadmaxabslogitdifference0,2greedygenerationsidentical.
- Main fresh init verified identical to seeded pre-smoke identity; step80 checkpoint saved; devmeanloss0.9748897295, generation in progress.

## Completion
- Main160/160 completed; checkpoints80/160 resumable. Selection160 before test, devloss0.9019908810.
- Actual1base load;400primary+2smoke generations;4smoke+160main optimizersteps;656trainexampleforwards+400teacherforced+2smokereloadlogitforwards. No retries/unknowncalls.
- All400 targetresponses reviewedbyagents;7invalid retained asNE. 80targets/state are20sources, not80independentprograms.
- SupplementalL4:22compiler calls/158runtimecases, policies separate; selected5/20 pass finitecases,13notextractable,1testfailure,1invalid.
- Final regression132passed/3optionalprobes skipped. Independentread-only artifactaudit found no blocker.
- FullmainVRAMpeak notretained separately due evalcounterreset; limitation stated, no rerun or parametersearch.
- KeepA/R15 baseline; improvedloss/F1 accompaniedbycleanfalsealarms. All22prioruncommittedfiles unchanged, sameHEAD/branch, datasetchecksums preserved; no publicinference/commit/push.
