# C-feedback-v3 implementation plan

**Goal:** improve only C's renderer, preserving stage1-v1 bytes and every old artifact.
**Architecture:** one short requested-Level prompt, v1 structural parser/journal;
new renderer supports production two-call scheduling and replay of new B stage1.
Small CLI/report adapters reuse existing review rubric, combine/bind/metrics.
**Spec:** user attachment aa800d6c-81f9-45b1-abcb-8b397a2eb3f3/Pasted text.txt.
User requests direct implementation/run/commit in existing branch; no approval
pause/worktree/push/public/328candidate/fine-tuning. No D or E inference.

## Registered choices, before any new model output

- Initial HEAD0e06f6e8432cb3cc850efd7a58b3a6c24737aebe, clean branch.
  Preserve3032 old file hashes. Old16 used for casebook analysis only.
- New12 internal development IDs fixed before prompt:9 families, all ID AND
  family disjoint from casebook16; Levels5/4/3,3 original-clean,4 multi/8single.
  All12 already appeared in grounded60; explicitly prior-exposed, not unseen.
  Original label diversity7/10; IO/edge/style have zero support. Macro divides10.
- One candidate C-feedback-v3, no prompt sweep or real-ID answer examples.
  Keep JSON feedback output: old C parsed15/15; errors were semantic/voice,
  so plain text has no demonstrated parsing benefit and would change another
  stage2 choice. Parser keeps the string unchanged; no bạn→em/post-filter.
- Stage1 messages/parser/results/mapping are byte-identical v1, never stage1-v2.
  Unexpected metadata is rejected before generation rather than cleaning the
  original stage1 input. Consistency is checked outside v1 parser; contradictions
  stay unresolved, never repaired or filled with R15.
- A prior R15 same-ID provenance. B freshly run exact v1 on new12 because no
  matching two-pass-v1 outputs exist. C-old and C-new replay B stage1 and make
  one renderer call each; report replay vs fresh calls. All share same model
  load, NF4/BF16/revision/seed42/greedy/16384context/1024tokens/45s as v1.
- Production helper still stage1→stage2→save per ID, at most2 generates/ID.
  Offline comparison B→C-old→C-new uses stage1 replay, not new end-to-end claim.
- One prompt includes only requested Level plus official own rule. Clean branch
  comes first; students are addressed as em (not ambiguous speaker self-address).
  No sources of teacher/gold/reviewer/public/history in any generation.
- Two fresh source-first reviewers12 each, then blinded A/B/C-old/C-new. Reuse
  rubric plus explicit bạn and placeholder axes; role score is semantic, not regex.
  Scope caveat alone is separate from genuine ambiguity in a demonstrated defect.
- Continue only if conservative feedback-pass count increases over R15 and
  C-old, false claims do not increase versus R15, and L1/L2 leak counts do not
  exceed R15. No leaderboard claim from fixed weak taxonomy. Otherwise retainR15;
  no additional internal evaluation in this request, only evidence-based proposal.

## Casebook diagnosis before prompt changes

Categories: a=wrong stage1 issue; b=new stage2 false assertion;
c=voice; d=Level leak; e=placeholder/nonactionable L3.

| ID suffix | Categories | Concrete failure |
|---|---|---|
|COUNTVOWEL-0010|c,e|Supported compile diagnosis becomes generic L3 placeholder.|
|UPPER-0005|c,e|General L1 warning uses forbidden placeholder/recipient omitted.|
|BASE2-0007|a,b,c,d|Treats special branch itself as violation; contradictory praise; details in L1.|
|DIGITSUM-0007|c,d|Correct diagnosis followed by direct replacement instruction at L2.|
|FACT-0008|a,c,d|Wrong comma from note copied; insertion advice at L2.|
|REVSTR-0007|a,c,d|Copies imprecise lost-character assertion and exposes replacement index.|
|DIGITSUM-0001|c|Clean praise but calls student bạn.|
|FACT-0001|b|Invents optimization/replacement loop in correct solution.|
|SUMB-0005|a,b,c,d|Comment mistaken for declaration; execution success invented; detailed L1.|
|DISTINCT-0017|a|Empty taxonomy with issue label; unresolved, no renderer call.|

Source/rendered prompts/raw/reviewer evidence and hashes remain ignored in
outputs/task3/c-feedback-v3-20261023/casebook-analysis.private.json.

## Tasks and ledger

- [x] Inspect casebook, immutable inputs and runtime; lock new12 and exposure.
- [x] Artificial behavior tests RED; implement only renderer/scheduler, GREEN.
- [x] CLI/config/report adapter, frozen dependencies and independent code audit;
  source-first seals, one candidate freeze before any new generate.
- [x] One model load: B v1, C-old replay, C-new replay; no guard/retry/fallback.
- [x] Blind source-grounded review; full-denominator all10 metrics, separate
  stage1-only metric and completion effects, Level/voice/factuality/joint/cost.
- [x] Real validator, relevant/full tests, artifact preservation, report and
  explicit local commit; no push/public/new D/E or extra prompt variants.


## Final evidence and decision

- Old casebook10 inspected; new12 locked from prior-exposed grounded development,
  all ID/family disjoint from casebook16. Two source-first reviews sealed before
  the single candidate run;48 blinded output reviews per reviewer sealed before
  opening original gold for scoring.
- RED→GREEN:15 contract tests plus1 regression for current official review-Level
  binding. Independent pre-freeze code audit found only that binding issue, fixed
  before freezing; no prompt/core/scorer changes after generation.
- Actual model one load, B24 calls, C-old12 + C-new12 stage2 replay calls.
  All12/12 complete per arm, no inconsistency/fallback/retry/semantic editing.
- C-old→C-new: direct-em1→2/12, false claims7→4/12, L1leak3→4/5,
  L2leak2→2/4, L3actionable3→3/3, full-feedback and joint0→0/12.
  R15 L1leak0/5, L2leak1/4. Gate FAIL/PASS/FAIL/FAIL: retain R15,
  stop candidate, no further inference/evaluation/public/328 submission.
- New16 tests and related127 pass; fullTask3:1449pass/5skip/1 pre-existing
  root-predictions baseline failure; fullpytest2 pre-existing Task1 sklearn
  collection errors. Keep unrelated inputs/baselines unchanged.
- Real three prediction files each VALID12; frozen input/code verification
  and3032 historical file hashes checked; explicit local commit only own new
  code/config/tests/plan/report/metrics, no raw source/review/output, no push.
- Reports: reports/task3/TASK3_C_FEEDBACK_V3_20261023.md and
  reports/task3/TASK3_C_FEEDBACK_V3_METRICS_20261023.json.
