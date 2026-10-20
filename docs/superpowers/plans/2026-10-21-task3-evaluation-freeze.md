# Task 3 evaluation snapshot implementation plan

> **For agentic workers:** Execute the user's supplied Step 1 specification in the existing checkout. Source review batches and the offline evaluator are independent parallel tasks; integrate and review before freeze.

**Goal:** Freeze a source-grounded private evaluation and public hash-only handoff, without inference or training.

**Architecture:** Read the archive by its required SHA-256 without extraction. Separate source-only review, historical identity registry, model-input requests, reference snapshot, and deterministic evaluator. Publish metadata and hashes only; private source/evidence stays under ignored outputs.

**Tech stack:** Python standard library, existing taxonomy/schema, pytest.

**Spec:** User's attached five-part Vietnamese Step 1 request, received 2026-10-21 Asia/Saigon; the repository report repeats the final contracts and limitations.

## Constraints

- Work only in this repository on current branch; preserve existing files. No worktree/clone/push/public inference/leaderboard/model loading/training.
- Archive SHA-256: `6bda70c29254a3bce91933b65f4a311d73a052e72d181c97e977152e14602f9b`; 627 root records; keep v2 annotation separate from reviewed findings.
- All references are agent-reviewed, never human-verified. No execution of student code without an isolated sandbox.
- Family exclusion includes evaluation and historical development, before target writing and before optimizer. Fail closed on missing identities or changed snapshot.

## Review focus

- Historical selections/bank parents/heldout and R18 targets, including both leaked IDs and all their peers.
- Uninitialized allocated slots versus allocation bounds; C++11 string terminator reads versus writes.
- Conditional whitespace, capacity, overflow/time limits, and AL/LG classification disagreements.
- Missing/schema/abstention never earns exact-clean; 10-label macro denominator fixed.
- Semantic review missing/stale ledgers remain pending; no keyword judge masquerades as reference.

## Tasks

- [x] Write leakage/archive/snapshot tests; observe failure; implement `src/task3/eval_snapshot.py`.
- [x] Write metric/schema/ledger tests; observe failure; implement `src/task3/frozen_eval.py`.
- [x] Inventory R13–R18 metadata, prepared splits and 15 appended sources. Save private provenance and review source shortlist, without reading previous predictions.
- [x] Build source-level findings, conditional/disputed packet and per-finding Level rubrics. Verify exact quote spans and reference consistency.
- [x] Implement `scripts/task3_freeze_eval.py` prepare/verify/evaluate/review-packet/train-gate commands. Freeze selection, requests, registry, definitions, implementation and private hashes atomically with a last-written seal.
- [x] Test malformed versions, identities, alias/near duplicates, Level contracts, offline determinism, forbidden selection inputs, tampering and overwrite refusal.
- [x] Independently review integrated work, run relevant/full feasible tests, report support and limitations, verify original tracked bytes, commit only new code/tests/metadata/report.

Verification notes: 65 new tests pass. Full pytest collection is blocked by pre-existing missing sklearn in two Task1 modules. Snapshot seal and all original tracked/protected bytes verified. Task3 suite: 724 passed, 4 skipped. Optional broad Task3+synthetic generated-fixture build was interrupted after >10 minutes; no pass claim. Final independent artifact audit: 520 checks, no material findings. See committed verification JSON.
