# Task 3 simple two-pass implementation plan

User supplied the full specification in attachment28be314d and requested direct
implementation, experiments, offline reviewers and commit on the existing branch.
No worktree, design approval pause, fine-tuning, push, PR or public inference.

**Goal:** measure predicted-taxonomy→feedback with exactly one call per stage and
at most two generates per ID, independently of R15 and old semantic gates.
**Architecture:** one small module owns two prompts, structural parsers, a
reservation-backed raw journal and a sequential runner. CLI freezes input/code/
prompt/config hashes, loads Qwen once and emits results per ID. Offline reviewers
and accounting are outside inference. Hybrid, if needed, replaces the whole failed
pair using fixed prior R15 outputs, never mixes stage1 labels with control prose.

## Constraints and decisions

- Initial HEAD21400d0c936d2af62ff404a0b526d4b600d3278c, expected branch
  feat/task3-quality-round5, initial status clean. Preserve all old artifacts.
- One frozen pair of short prompts; no semantic validation/retries/guard calls.
- Stage1 allowlist excludes Level, gold, teacher feedback, reviewer data. Stage2
  receives the same task plus the actual prediction, issues and own Level rule.
- Parser validates JSON/types/official10-label membership, never note semantics.
- Stage1 parse failure skips stage2, stage2 failure remains unresolved, no[] or
  placeholder. A durable pre-call reservation prevents resuming an interrupted
  generate with a third physical call.
- All16 IDs selected before prompt implementation:3 old8 sources +13 old60
  sources, all prior-exposed development.14 single/2 multi, Levels1/2/3=5/5/6,
  four original-clean and coverage of all10 original labels. Never fresh blind.
- TRAIN feedback lengths/tone inspected for EX02-S202/EX01-S101/EX02-S203 only;
  no verbatim examples inserted; official Levels override sample violations.
- Model/revision/NF4/BF16/seed/greedy match R15;1024tokens/45s/context16384.
- Offline source-first reviewer A16; reviewer B8 predefined including every L2.
  Preserve disagreements, no gold repair. No oracle ablation needed initially.
- Continue to separate internal evaluation only if completion AND taxonomy/
  source-grounded feedback improve without confirmed L2 repair leaks. Otherwise
  stop after development with no extra prompt version or public run.

## Tasks

- [x] Inspect real repo/config/loader/labels/validator/prior report/tests; freeze
  ID/control/provenance and preservation hashes before prompt code.
- [x] Write artificial behavior tests for one-ID prompts, no gold/Level at stage1,
  exact call order/cap, partial errors, interruption/resume and immutable taxonomy.
  Observe RED, implement src/task3/two_pass.py and observe GREEN.
- [x] Add config/CLI freeze, one-load local run and raw per-stage logging; verify
  one pair and no model-based postprocessing, freeze before any generation.
- [x] Run16 sequential IDs; seal source reviews first, then shuffled paired
  review and disputed cases. Score full denominators, per-label and per-Level.
- [x] Attribute errors to stage1/stage2, report naturalness/specificity and costs;
  optionally fixed hybrid for operational schema only, not pure-method quality.
- [x] Relevant tests, full Task3 suite, official validator on actual complete
  internal file, independent code review and preservation check. This plan is
  included in the user's requested local handoff commit; no push.

## Outcome

One frozen pair,16/16 complete,32 calls,0 unresolved/fallback. Original-gold
micro-F1 R15=.3200 versus two-pass=.2857; macro10=.1400 versus .1133;
conservative strict joint2/16 versus2/16. Continue gate fails joint gain and
micro-F1. Retain R15; no larger evaluation, public inference or candidate328.
18 runner tests and22 report-integrity tests pass;108 related tests pass.
Full Task3 has1401 passed,5 skipped,1 pre-existing root-prediction baseline
hash failure. Protected2848 old file hashes remain unchanged.

## Review focus

No cross-sample conversation or template examples, hidden third call on resume,
schema failure→clean conversion, label mutation by stage2, or quality filtering
masquerading as structural validation. Logs must capture both model stages
before parse. Private source/output/reviews never enter Git.
