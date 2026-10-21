# Feedback proxy rubric (locked before inference)

This is a source-reviewed offline PROXY, not a reconstruction of the hidden LLM judge. Teacher feedback is a reference, not text to copy. Gold taxonomy and review findings never enter query prompts.

|Level|Full credit 1|Partial 0.5|Zero|
|---|---|---|---|
|1|Correct defect indication or justified scoped praise; no location/cause/repair|Uncertain generic self-check without correct status determination|False-clean, false technical claim, specific location/cause or repair disclosure|
|2|Correct source location AND causal explanation, useful and no repair|Correct useful location OR causal explanation, incomplete diagnosis, no repair|Generic “còn điểm cần xem lại”, incorrect diagnosis, false-clean, repair/code disclosure|
|3|Correct location AND cause AND feasible local repair, no complete solution|Useful correct diagnosis but missing one required component|No useful diagnosis, serious false claim, false-clean, full-solution violation|
|4|Correct diagnosis and feasible correction/sample solution satisfying task|Useful correct diagnosis/correction incomplete in a material respect|Wrong solution or serious false technical claim; verbosity earns nothing|

For clean sources, scoped-correct assessment with justified source/task reasoning is full credit; source detail remains forbidden in L1. Do not demand fabricated repairs for clean L3/L4. Unsupported “no errors” is not sufficient if a real defect exists. An explicitly unknown judgment scores 0 and is reported separately. On L1 a generic cautious response is 0.5, whereas a correct explicit defect indication is 1. On defect L2/L3/L4 generic caution is 0.

All technical judgments record output quote, source quote/line or static testcase trace. Review flags: false_technical_claim, false_clean, location_correct, cause_correct, feasible_repair, generic, covered_findings/total_findings, level_violation, repair_disclosure, unknown. No indicator is inferred from taxonomy, schema validity or short length. Clean status is scoped to stated valid input domain. Multiple taxonomies for the same root cause are not mandatory.

L1 location/cause disclosure is a Level violation, including when accurate. L1/L2 code or concrete repair forces score 0. Serious false technical claims force 0 for every Level. L3 full solution forces 0. L4 requires correctness of any supplied correction; no automatic reward for code. Separate original regex guard behavior from semantic manual review.

Calibration selection: highest mean proxy among B/C; tie => fewer false technical claims, then B. Evaluate the same rubric for A, B, C. Do not revise any prompt after calibration or fresh outputs.

Fresh acceptance: complete valid outputs on every case; no L1/L2 repair disclosure; candidate false-claim finals <= A; net wins >=6/48 overall, >=3 Level2, >=1 Level3; L1 false-clean does not increase. Keep numerical thresholds if fewer than48, report proportions and uncertainty. Any failure or unresolved material unknown retains R15. Passing means only candidate for independent review before public.
