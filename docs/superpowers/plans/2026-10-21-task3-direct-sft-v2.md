# DIRECT SFT v2 implementation plan

**Goal:** Run one source-isolated, final-JSON-only QLoRA pilot on pinned Qwen2.5-Coder-7B-Instruct, testing concrete Level 2/3 feedback while preserving R15 and every v1 artifact.

**Architecture:** New versioned paths reuse the tested R15 direct contract and pure v1 tokenization/scoring helpers. Keep all 14 v1 internal validation sources fixed and protected. Reuse immutable BASE/v1 development predictions and generate v2 once on the same 60 requests. Separate retrospective development analysis from fresh TRAIN target authorship.

**Authorization:** The user's detailed four-step request authorizes implementation, one optimizer run, paired development assessment and a local commit. Existing branch and historical artifacts must remain in place; no worktree, public generation or push is needed.

**Tech stack:** Python, pytest, transformers/PEFT/bitsandbytes, pinned Qwen revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`, NF4/BF16, LoRA r16/alpha32, 2 epochs, seed42. No continuation from adapter v1, diagnosis targets or chain of thought.

## Tasks

- [x] Bind preservation hashes; audit all 56 optimizer L3 targets and six defective L3 development pairs, L2 regressions and both pending flags. Keep source proofs private and attribute agent review.
- [x] Review remaining eligible TRAIN sources without development output access. Reject annotation conflicts; preserve original scopes. Gate all additions against protected sources and fixed internal validation before authoring.
- [x] Review/strengthen TRAIN L3 targets using their own source proofs. Combine old optimizer sources plus eligible additions, preserve fixed validation and keep all Levels of a source together. Audit every defect L3 for cause and concrete feasible operation; record revisions and exclusions.
- [x] Add new versioned prepare/train/infer runtime, explicit registry wrapper and artificial tests. Pin dataset, source split, target audit, retrospective audit, prompt, config, model/runtime hashes and decision rule before optimizer.
- [x] Run one base-initialized optimizer pilot with assistant-only loss, no truncation, validation-only epoch selection. Verify source bytes immediately before the first optimizer step; durable markers forbid resume or second run.
- [x] Verify immutable BASE/v1 predictions and generate v2 once on all 60 original development primary requests. Review all outputs by source, preserve unknown flags and report taxonomy separately from semantic quality.
- [x] Apply frozen production rule, retain R15 unless all conditions pass; no public generation in this task. Run artificial/new and Task3 tests, disclose global test failures, verify preservation, commit new code/config/tests/metadata/report only.

## Frozen decision design

All 60 v2 outputs must complete and all required review flags be resolved. Both raw Level 2 correct location/cause and strict Level 2 usefulness must improve over BASE and v1 on the same defects; Level 3 correct cause plus feasible repair must exceed both and reach at least 2/6. Annotation and source micro/macro F1 must each retain at least 90% of the positive v1 gain over BASE: `BASE + 0.9 * max(0, V1 - BASE)`. False technical claims must not exceed v1 and must be lower than BASE; L1 false-clean must not exceed v1. Any missing/unknown criterion blocks replacement. L4 is reported but is neither trained nor claimed improved.

## Review focus

Fixed validation is never admitted by the new registry; sources with many Levels cannot cross splits. Old output digests and identical safe prompts must bind reused arms. An unknown judgment remains pending rather than false/pass. Quote/schema validity does not prove semantic correctness. Targets never copy development witnesses or labels into TRAIN examples. All source/raw/weights and detailed source proofs stay ignored.
