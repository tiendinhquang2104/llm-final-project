# Task 3 SFT v1 — controlled QLoRA experiment

Executed on 26/10/2026 in fix/task3-strict-feedback at HEAD60c76dc. Full Vietnamese results: [report](../reports/task3/TASK3_SFT_V1_QLORA_20261026.md).

Run artifacts: outputs/task3/sft-v1-qlora-20261026-run1/. Native NF4 double-quantized base, BF16 compute, one main epoch160 steps. Selection step160 by fixed dev completion loss. All400 primary generations and2 smoke generations completed; all400 reviewed by agents. No public inference, commit or push.

Entry point: scripts/task3_sft_v1_experiment.py. Exact fresh/resume and audit/report commands, counts, costs, limitations and paired examples are in the report. Completed runs must not be restarted. Resume refuses optimizer progress beyond the latest complete native checkpoint rather than silently replaying updates.

The adapter is for native end-to-end taxonomy+Vietnamese feedback, not the separate findings/source-coordinate detector. Keep A/R15 available; lower loss does not justify deployment given clean false alarms and weak detailed feedback.

Source snapshots, immutable manifest, actual TrainingArguments/PEFT configuration, real-Qwen masks, smoke reload, checkpoint80/160 optimizer/scheduler/RNG, raw/parsed/invalid responses, paired HTML and quality notes are retained in the run directory. Supplemental fenced/unfenced C++ audits have distinct policies; the unfenced check was introduced after observing that format, without changing primary metrics or training.

Known instrumentation limit: CUDA peak counters reset for evaluations, so whole-main allocated/reserved peak was not independently retained. Smoke and each eval peak are scoped; the report does not claim main's last-window peak as the whole trajectory peak. Smoke reload logits have2 forwards, but their individual latency was not separated from total process time.
