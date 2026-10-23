# Task 3 compact diagnosis implementation plan

> **For agentic workers:** execute inline using executing-plans and TDD. The user
> supplied the binding specification in the continuation attachment and explicitly
> requested execution without per-finding approval, on the existing branch.

**Goal:** repair completion without turning uncertainty or unsupported claims into
clean predictions; evaluate diagnosis separately from renderer.

**Architecture:** new compact module and runner reuse the existing source scanner,
strict JSON reader, Qwen backend, hash-bound journal, R15 prompt and feedback
citations. Model supplies assessment/reason and short semantic findings. Runner
derives identity, span, evidence metadata, scope scheduling and prerequisites.
An independent Qwen check can reject individual findings; offline Codex review
measures whether that check is right. Rescue uses the direct R15 prompt with
bounded retries and semantic Level screening, never its placeholder fallback.

**Tech stack:** existing Python3.12, Qwen2.5-Coder-7B-Instruct NF4/BF16, pytest.
**Spec:** user attachment b0ac9f8c-bae2-4ccc-a02e-41fad2e6bbb9/Pasted text.txt.

## Global constraints

- No public input/attempt tuning, training, external generation API, push or PR.
- Existing source/gold/R15/SFT/raw outputs remain byte-identical.
- Initial HEAD63a5763f7c4e0a5b1243aa6e12b802c8f804d02c; initial tree clean.
- Two diagnosis prompt versions maximum; at most one evidence-based contract fix.
- P1 requires8/8 diagnosis states usable or reasoned no-error, excluding rescue.
- Only after P1 passes, P2 selects20 development IDs before candidate generation;
  require19/20 final completion after pre-registered rescue, with quality review.
- P3 cannot run before both gates and independent review. Old60 are development
  exposure only. Any new evaluation must report family/source overlap honestly.
- Stop expansion if gates fail; preserve negative experiments and commit progress.

## Design decisions and alternatives

Relaxing the old validator globally would admit fabricated findings. Keeping its
16 model-authored finding fields repeats the serialization bottleneck. Use compact
semantic fields plus deterministic provenance, with per-finding rejection instead.
One JSON fence and source whitespace normalization are harmless; fuzzy source or
label synonym replacement is forbidden. Uncertain remains unverified even when a
quote matches. A known compiler executable is insufficient isolation: no student
execution or unsafe compiler invocation; actual evidence availability is recorded.

## Review focus

- Partial valid findings survive, but cannot imply complete coverage or clean.
- Multi-question metadata schedules bounded scope calls, P1 errors block later
  questions and P1 uncertainty prevents unconditional later conclusions.
- Multi-label single findings need explicit overlap rationale, primary/secondary
  trace and separate semantic review; Logic is never appended automatically.
- L1 retains topic context without source/locations/causes; L2 has no repair.
- Guard failure is not a clean decision; rescue attribution and journal identity
  survive resume, with no final submission when any ID is unresolved.

## Tasks

- [x] P0: replay old attempts offline, inspect representative raw examples for all
  eight rejection groups; save private excerpts and sanitized root-cause table.
- [x] Contract tests RED: compact schema, safe whitespace matching, false quotes,
  comments, partial findings, uncertain, overlaps and P1 policies. Implement GREEN
  in src/task3/compact.py with new operational rulebook.
- [x] Runner tests RED: bounded scopes/retries, semantic rejection, rescue origin,
  resume and Level view/citation handling. Implement src/task3/compact_runner.py.
- [x] CLI/config: frozen P1 inputs, model/runtime/prompt/code hashes, real local
  generation, no evaluation bypass. scripts/task3_compact.py controls gates.
- [x] Run P1 v1; if necessary v2 and one justified contract repair. Stop evaluation
  expansion if8/8 diagnosis gate still fails. All variants retained separately.
- [x] P2 permission gate evaluated:0/8 after both variants, so P2/evaluation
  deliberately not opened. Separate oracle renderer experiment completed on
  reviewed development findings; never production evidence.
- [x] Two independent reviewers overlap a subset; seal source judgments before
  output and gold. Score complete denominators, strict joint includes non-generic.
- [x] Verify protected bytes, new tests/Task3/full collection, final code review,
  report true blockers and explicit commit scope. Commit hash recorded after
  success in the handoff. No new public file absent winner.

## Execution ledger

Preflight: compact findings feed both production renderer and oracle experiment;
oracle provenance must be explicit and rejected by production entrypoint.
P0 auditor reports status/quote rejects often also contain substantive false claims,
and the fence example is truncated rather than a harmless wrapper. These cannot
be repaired merely by changing status or fuzzy-matching source.
Preservation snapshot:2734 files. Compiler g++ exists now; docker/bwrap unavailable.
GPU initially has19007MiB free; do not interfere with another process.

Task1 complete: offline P0 reproduced116calls/111rejects/55unresolved and read
eight raw/source representatives. Original snapshots unchanged.
Task2 complete: contract RED19 failures → GREEN19; contract repair RED2 scope
failures → GREEN30 with runner tests. One contract revision before promptv2.
Task3 complete: P1v1/v2 each0/8 diagnosis and0/8 final. No P2/new evaluation.
Task4 complete: source-only A8/B4 sealed before outputs/gold; oracle10 paired
cases completed C1=8/C2=3. Independent output/guard reviews sealed. Strict joint
A5/0, conservative4/0; not production scores.
Task5 complete: final fresh code reviewer found token-normalization changes,
production C1 guard bypass, and vacuous empty-scope clean. Reproductions RED8
failures, fixes GREEN; literal suffix/member-pointer/preprocessing regressions added.
Final new tests42 passed; integration102passed;
Task3 1361passed/5skipped/1 historical SHA mismatch; full collection2 sklearn
errors in Task1. No model calls after correctness fixes; exact runtime snapshots
preserved, current code not claimed model-evaluated.2734 protected hashes unchanged.

Ruling: withhold P2 entirely after failed P1 rather than select20 new sources —
the user's explicit compute/completion gate takes precedence over broad coverage.
Cost: no new evidence on multi_problem/rare groups, reported as unmeasured.
Ruling: retain P1 unknown as unassessed later prerequisite scopes — avoids
unconditional claims about dependent questions, at a potential completion cost.
Ruling: fix Important software issues after runs without resampling — safer
software and unchanged research results, but current code has no new model score.
