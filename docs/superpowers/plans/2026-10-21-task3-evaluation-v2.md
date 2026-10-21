# Evaluation v2: family-first controlled holdout

Implement the user's v2 correction without modifying any v1 file or seal.

- Lock 10 named training families and 18 evaluation families before source selection. Preserve this partition even if some train families lose all sources to exclusions.
- Keep family exposure (all28 known families) as disclosure metadata. Block only used/reserved ID/group/source/token/rename identities and their near variants; do not turn exposure into family-wide training bans.
- Reserve all v1 evaluation source identities, historical example/target/output-reviewed sources, and heldout identities. Deny evaluation-v2 families and cross-family near duplicates. Admit only a sealed, source-bearing training whitelist, rechecked before targets and optimizer.
- Reuse independently audited v1 references only from the assigned evaluation families, then source-review additional scoped-clean cases. Re-review all19 disagreements in a separate private ledger, including TRAIN-family records without making targets.
- Style needs an explicit statement/policy rule and an actual violating source construct. Do not add labels for quota. Preserve annotation v2; source-reference may have zero style support.
- Probe available isolation without executing student source. If unavailable, keep syntax findings static and compiler confirmation pending; never use host compiler as fallback.
- Report actual train source/family eligibility, both10-label supports and evaluation Level coverage before sealing. Then freeze an independent v2 manifest and private artifact seal.
- Test source/rename/near leakage and spoofed metadata at both `before_targets` and `before_optimizer`, positive eligible cases, family exposure not being a ban, v1 byte preservation, hash tampering, and offline evaluator compatibility.
- Run Task3 tests and independent review; commit only new code/tests/hash metadata/report, no private source and no push. No training, target generation, model loading or inference.
