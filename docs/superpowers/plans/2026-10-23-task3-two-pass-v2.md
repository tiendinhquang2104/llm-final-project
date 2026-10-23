# Task 3 role grounding and taxonomy ablations implementation plan

**Goal:** trace the meta sentence, isolate stage2-v2 (C), isolate stage1-v2 (D),
then run E only if C/D justify it; preserve R15 A and two-pass-v1 B.
**Architecture:** new prompt module and runner reuse v1's durable journal,
structural JSON parser and sequential call boundaries without editing v1.
An offline audit script reconstructs v1 boundaries and creates blinded review
packets/scoring. All16 old IDs remain exposed development. No public or push.
**Tech stack:** existing Python, Transformers, Qwen7B NF4/BF16, pytest.
**Spec:** user attachment ce8ca661-501c-409b-acd2-d1667e675dbd/Pasted text.txt.
User requests direct implementation/run/review/commit on the current branch;
no additional design approval or worktree is needed.

## Fixed decisions

- Initial HEAD26a9d9b10c32e8daf95d8ef29dc76af61332bda0, clean branch
  feat/task3-quality-round5. Preserve2918 old files by SHA256.
- New private root outputs/task3/two-pass-v2-20261023; exact previous16 IDs,
  no new split, gold edit, example or prompt selection from public.
- Source→rendered1→raw1→parsed1→rendered2→raw2→parsed2→final before prompt changes.
  Actual pinned tokenizer reconstructs rendering; no model calls for this audit.
- One frozen stage2-v2 and one frozen stage1-v2, no v3/v4 search.
- C reuses frozen B stage1; only stage2-v2 generates. Frozen contradictions
  are recorded as contract failures, not silently repaired: stage2 is skipped
  and the ID remains unresolved. Its raw B stage1 is retained.
- D generates stage1-v2 then uses exact v1 stage2 message function unchanged.
  E, if eligible, independently generates stage1-v2 then stage2-v2 per ID.
  C/D are ablations, not a claimed end-to-end new production candidate.
- Stage1-v2 requires taxonomy set == issue-label set. No LLM semantic gate,
  retries, code replacement, label repair, generic filler or fallback.
- Stage2-v2: direct teaching assistant→student using em naturally; explicitly
  handle clean evidence before L2/L3 diagnosis/repair rules; no meta commentary.
  No sample-specific answers/examples. Runtime output parser remains structural.
- Official10 labels/own Level definitions; source and trusted evidence only;
  no gold/teacher/reviewer/public/history in model inputs.
- C and D use one model/tokenizer load in a serial invocation. Gate E offline
  after C/D review; if E runs, one load and <=2 generates/ID. Same native runtime
  revision/NF4/BF16/seed42/greedy/16384 context/1024tokens/45s as controls.
- Two fresh source-first independent reviewers cover16 each, then blinded
  A/B/C/D and optional E. Semantic review is offline, never inside inference.
  Role/direct-em/meta/clean-false-error are separate rubric axes, not regex truth.
- E gate: C must have no reviewer-flagged meta or confirmed clean-case false error,
  and direct natural em for every completed output (at least15/16 complete);
  unresolved clean-case dispute gives no claim of success. D must improve
  original-gold micro and macro10, with genuine TP in previously missed groups.
  Otherwise stop before E; no prompt resampling. To select E also require both
  taxonomy improvement and conservative content+Level+role/joint improvement,
  no confirmed L2 repair leaks, full-denominator completion disclosure.
- No separate new evaluation now: only propose if signal good and describe
  exposure/source-family limits. No public, candidate328, upload, push or PR.

## Review focus

Interrupted reservation must never reissue a physical model call. C's frozen
contradiction must never become [] plus erroneous prose or a repaired label.
D must not accidentally use v2 feedback rules. E must not reuse D outputs and
claim two new calls. Reviewer/key/source/prediction hashes must bind all scores;
invalid/non-run rows must not disappear from denominators or become clean.

## Tasks and evidence ledger

- [x] Inspect branch/config/source/parser/backend; lock old16 and preservation.
- [x] Trace with pinned tokenizer before changing prompts. All32 original inputs
  match source allowlist; token counts and assistant generation prefix match.
  Meta phrase first occurs in DIGITSUM0001 stage2 raw, unchanged to final.
  No observed data leakage; ambiguous v1 role and underspecified clean behavior.
- [x] Write artificial regression tests; observe RED before new prompt/runner.
- [x] Implement new module/config/CLI; observe GREEN; independent code audit;
  fix Important defects before freeze. Freeze once before any model call.
- [x] Seal fresh source-only reviews, run C then D once, blind paired review.
- [x] Gate E from C/D; E not eligible,0 calls; no further prompts/evaluation.
- [x] Score all16, all10 original-gold labels, role/clean/Level/content/joint,
  per-ID deltas, stage provenance and tokens/latency. No oracle/gold production.
- [x] Run relevant/full tests and real output validator where complete; preserve
  raw privately, sanitized report in Git. Commit only own files, no push.

## Final evidence ledger

- Trace complete before prompt edits: DIGITSUM0001 meta first in stage2 raw;
  B/D same messages and raw hash reproduce it; C changes renderer input/output.
- New32 tests pass; final related suite111 passed. Audit fixes RED→GREEN before freeze: D evidence rejection,
  optimized integrity checks, interrupted origin, E leaf/current-output binding,
  metric helper/gold hash freeze, clean-disagreement gate, independent leak
  disqualification and Level applicability. D allowed16 payloads equal v1.
- Freeze8a9b40a7cf7829b7682019fbfe1470f9db283526d15a9ad696ea35daa88fceaf;
  one pair only; no code/prompt/scorer changes after generation.
- C15/16,1 inconsistency unresolved,15 calls; D16/16,32 calls; one model load.
  Two fresh reviewers each scored64 blinded outputs; only schema normalization
  on unresolved evidence, no verdict changes. No gold edits.
- C meta0 but direct em3/16, clean false errors2/4, confirmed L2 leaks2/5.
  D micro.1935/macro10.0649 vs B.2857/.1133; no new rare TP. E gate fails.
  Retain R15; E not run; no public/fresh evaluation/328candidate/push.
- Full Task3:1433 pass,5 skip,1 pre-existing root-predictions baseline failure;
  bare pytest2 existing sklearn collection errors in Task1. D actual output
  validator VALID16; C incomplete rejected with full16map, as reported.
- Preserved2918 old files unchanged. Only new code/config/tests/plan/reports
  enter the requested local handoff commit; all raw remains ignored.
