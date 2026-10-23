# Compact diagnosis rulebook

Official strings and Level definitions remain in label_space.json. Reuse the ten
operational descriptions in grounded.RULES; these are research choices, not
instructor-approved boundaries. No unsupported synonym-to-label conversion.

The model supplies verdict, reason, and up to three short findings with an optional location,
quote, observed current behavior, causal conflict, valid condition and labels.
IDs, spans, metadata, evidence references and prerequisite scheduling are runner
responsibilities. Quote/source binding proves provenance, never semantic truth.
The separate Qwen semantic check is also fallible and must be agent-reviewed.
The scope is the runner's scheduled PID/whole, not a model-authored requirement.
Any explicit competing/nonexistent PID is rejected; descriptive location prose is
retained as untrusted model_location and never changes that scheduled scope.

A single finding may carry two labels only with an overlap_reason explaining
each named category and an allowed overlap below. First label is primary,
second secondary. No automatic Logic suffix and no label from rejected findings.

| Pair | Required distinct facets of the same mechanism |
|---|---|
| Loop + Array | Bound/update causes the iteration defect and reaches an invalid storage index. Mere wrong numeric result is insufficient. |
| Loop + Edge | Explicitly valid boundary is omitted and the loop mechanism itself is wrong; state both conditions. Not every endpoint automatically earns Edge. |
| Loop + Logic | Wrong iteration mechanism plus a separately explained state/decision effect justified by the annotation policy; vague “wrong answer” is insufficient. |
| Array + Edge | Reachable invalid index/storage behavior on a documented boundary; both storage and boundary facets must be stated. |
| Function + Logic | Required return/argument contract violation and an explained decision/state contradiction. Merely occurring inside a helper is insufficient. |

These reasons are checked by a separate Qwen pass and offline source reviewers;
review disagreement remains disputed. No claim that lexical checks certify an
overlap. Other label combinations need separate findings in this version.

Only complete JSON with an optional single complete fence is parsed. Token
whitespace matching preserves identifiers, multi-character operators, literals
and comments; no fuzzy edit, quote replacement, appended braces or recovered
label prefix. Invalid individual findings are logged and removed. Valid positives
survive without certifying completeness; explicit uncertainty is never promoted.
Only reviewed_no_error_found with a reason and an independent model clean check
can project to[]. Partial scope assessment cannot certify whole-program clean.

Four internal states: confirmed_findings (model assertions with source binding
and separate model screen), candidate_unverified, reviewed_no_error_found,
generation_or_tool_failure. “Confirmed” does not mean human/semantic proof.

Multi-problem analysis schedules each metadata PID with bounded calls, without
requiring the model to serialize a coverage proof. A supported P1 defect under
the exact known prerequisite policy blocks dependent PIDs; P1 uncertainty leaves
later PIDs unassessed. Clean requires all scheduled scopes, not absence of claims.

L1 gets a topic derived from the statement plus status/limitations, no code,
variables, locations or causes. L2 gets diagnosed behavior/cause, no repair field;
semantic guard checks indirect repair. L3 adds an abstract repair direction or
asks the renderer to infer one from the diagnosis; L4 permits detail. Sentence
citations remain private. Oracle findings are explicitly rejected by production.

Pre-registered rescue is the same pinned Qwen with R15 direct prompt, bounded
schema/disclosure retries, source support reconstruction and semantic screening.
It never invokes R15's placeholder fallback. Rescue is reported separately and
cannot satisfy the diagnosis-only P1 gate. Exhaustion stays unresolved; no final
submission file is produced with missing IDs.
