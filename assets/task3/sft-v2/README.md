# SFT V2 external artifacts

This directory stores metadata only. The authorized external bundle must supply
the context32768 freeze, all sealed runtime and predecessor bytes, checkpoint
240 adapter files, and a pre-provisioned historical checkout at
`60c76dc1a1104557b5d10dca4f78baf57413cf4d` on
`fix/task3-strict-feedback`, at the fixed location
`/workspace/llm-final-project`. Its sealed V2 training runtime, V1 historical
runtime, and root prediction are external too. Do not place those artifacts in
Git or enable Git LFS for them. For the current fresh inference flow, use
`sft-v2-repro-v1` and pass the adapter directory explicitly; see
[`docs/task3_flow_equivalent.md`](../../../docs/task3_flow_equivalent.md).
