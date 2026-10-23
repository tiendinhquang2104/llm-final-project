# Task 3 grounded findings and Level information flow

User supplied the implementation specification in the attachment on 23 October
2026 and explicitly authorized inline execution, independent review, experiments
and commit on the existing branch without intermediate design approvals. This
plan follows that authorization. No worktree, training, public tuning or upload.

**Goal:** Compare immutable R15 (C0), grounded diagnosis plus legacy-style
feedback (C1), and the same diagnosis plus isolated Level views and semantic
feedback guard (C2). Keep Qwen2.5-Coder-7B-Instruct as the only inference model.

**Architecture:** Reuse the pinned NF4/BF16 backend, R15 controller and lexical
source checks. Add a small diagnosis contract, deterministic taxonomy projection,
Level views, citation-bearing sentence renderer, Qwen semantic review and a
hash-bound journal. Uncertain/invalid remain unresolved, never clean fallbacks.

**Evaluation:** Reuse all 60 primary evaluation-v2 requests and eight eligible
development sources with their original Levels. Preserve original annotations;
evaluate agent source references separately. These are prior-exposed controlled
data, not a new blind benchmark. Lock ID/source/config/prompt hashes before model
calls. No method changes after evaluation output inspection.

**Alternatives considered:** A direct prompt delta was already tested in R24;
taxonomy-only Level removal was already tested and increased unsupported FP.
Reusing the rich discovery framework would increase complexity and output cost.
This experiment tests missing source-to-claim contracts and information flow.

## Tasks

- [x] Inventory actual data/archive versions, contracts, hardware, history and
  protected artifacts; save ID/hash selection before implementation.
- [x] Add adversarial tests for diagnosis schema/source/status, Level redaction,
  citations, prerequisite scope, semantic guard and bound resume; observe RED.
- [x] Implement versioned rulebook, prompts, parser, runner and freeze CLI; GREEN.
- [x] Run eight development sources, obtain independent source-before-gold blinded
  review, then freeze the method before 60 evaluation sources.
- [x] Run paired C0/C1/C2, review and score all IDs without tuning on results.
- [x] Run Task 3 checks; report support, taxonomy, semantic feedback, joint proxy,
  unresolved, costs, exposure and limitations. Select only under the user gate.
- [x] Verify protected bytes, independent code review and explicit commit scope;
  final commit hash/status recorded in the handoff after commit succeeds.

## Review focus

Exact quotes do not establish semantic truth. Semantic guard predictions are
fallible and separately agent-reviewed. L1 view must contain no source, labels,
location or cause; L2 no repair data. A parse/tool failure cannot produce `[]`.
Compiler unavailable cannot become compiled. Prerequisite restrictions cannot be
silently dropped. C0 remains byte-identical and its fallbacks remain disclosed.

## Execution ledger

Initial HEAD eca737296a4d31efa56ca90faa8fb6e6c92b4c2d; branch
feat/task3-quality-round5; initial status clean. DOCX original unavailable after
workspace/attachment/archive search; supplied Markdown conversion read instead.
Mandatory label-space, task3 metadata, loader, validator and recent reports read.

Completed evaluation: C0/C1/C2 valid60/4/1, joint4/1/1; no winner, retain R15,
no new public inference. Independent agent review sealed180 slots. Combined
source/output previews affected43 source judgments before the dedicated source
pass; gold and arm keys remained hidden. No claim of pristine output-blindness.
Original gold unchanged; post-seal mechanical disagreement overlay is separate.

Independent final code review found a report provenance gap; fixed packet/key/
unit/current-output binding and eight mutation tests passed. No frozen inference
method changes after evaluation. Focused94 passed; full Task3 1319 passed,
5 skipped,1 historical root-prediction hash mismatch. Restored three missing
historical files verbatim from SHA-verified archive; historical v2 verify passed.
All2598 protected hashes unchanged. Full-repo collection still lacks sklearn in
two Task1 tests; no out-of-scope dependency changes. Detailed evidence in report.
