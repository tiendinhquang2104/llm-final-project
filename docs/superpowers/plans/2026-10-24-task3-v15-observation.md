# v1.5 Observational Continuation Plan

User-approved execution design: outputs/task3/v1.5-observation-execution-audit/request.txt. Execute inline in existing fix/task3-strict-feedback worktree; no additional design approval, commits or branch operations.

**Goal:** Complete internal30 then public328 once with the exact existing inference treatment; quality failures remain assessments and no longer stop measurement.
**Architecture:** Add a focused noninteractive observation runner reusing existing preparation, source/compiler cache, tokenizer preflight, BF16 backend, durable journal, parser/resolver and run_units. No frozen inference source/config changes. Separate observation policy/identity, execution readiness, quality assessment, and contract-valid export readiness. Capture runtime in finally.

- [x] Write failing tests for nonblocking quality, integrity stop, preserved detector on renderer failure, exhausted/resolved resume, isolated content failure and partial export.
- [x] Implement runner-only entrypoint; fresh code review; run224 prior tests plus new tests and diff check.
- [x] Bind original v1.5 treatment/input/fixture hashes, prepare both phases, preselect public content-review slice and freeze before model loading.
- [x] One BF16 load, internal30 then public328 in the same process; checkpoint each input; stop only actual integrity/infrastructure problems. Never rerun fixture calls.
- [ ] Review all internal30 and preregistered public slice plus failures/flagged cases; produce stage-separated metrics/costs/casebooks/at least8 actual examples, honest quality verdicts, exports and exact commands.

Review focus: unchanged prompts/config/compiler/source semantics; replay never regenerates exhausted calls; failed renderer retains detector score; isolated bad references versus corrupted catalogs; no quality-based suppression or completeness padding; finally runtime-after; public has no gold accuracy claim.

Progress: root/branch/HEAD confirmed. All161 prior frozen files match; prior fixture journal27 records, internal journal absent, no observation outputs. Prior artifacts hash manifest saved before any changes.

Execution progress:237 tests passed. Two fresh Important review findings fixed with RED/GREEN; JSON key-type freeze comparison fixed without prompt changes. Public compiler guard was investigated: original #include <sstring> remains dependency_failure with exact cached diagnostics; separate hash-bound readiness record permits measurement without relabeling. Pre-inference drafts preserved. One public detector input exceeds context and remains a sample-local failure. Actual model process running under session45741, PID2092816: internal30 completed2 valid/28 unresolved, public328 in progress. No fixture re-generation; current code frozen and must not change.

Complete: one BF16 load, internal30 attempted (2 detector/feedback-valid,28 unresolved), public328 attempted (0 valid,328 unresolved; one context overflow).715 new generations, no resolver or fixture calls; prior27 fixture generations reused. Runtime-after and invocations captured normally; post-run verify-only passed without model. All30 internal source reviews, preregistered8 public source reviews plus all328 schema/status audits, complete casebooks and10 actual examples saved. Quality remains failed; no predictions.json created. Current root/branch/HEAD unchanged; prior outputs verified byte-for-byte unchanged.
