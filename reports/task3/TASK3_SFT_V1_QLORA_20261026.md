# Thí nghiệm Task 3 SFT v1 QLoRA — 26/10/2026

Đã thực thi baseline-dev, smoke GPU và một epoch QLoRA. Main hoàn tất **160/160 bước optimizer** trên 640 target/160 source. Không commit, push hoặc nộp predictions.

Checkpoint chọn: **step 160**, theo minimum fixed-dev equal-example completion loss; hòa tuyệt đối chọn bước sớm hơn. Quyết định lưu trước test. Đây không phải quyết định thay A/R15.

| State | Loss | JSON hợp lệ | Taxonomy micro P/R/F1 | False alarms clean target; source |
|---|---:|---:|---|---|
| base-dev | 2.2238 | 80/80 | 0.5000/0.1667/0.2500 | 3/20; 3/5 |
| step-80-dev | 0.9749 | 77/80 | 0.3816/0.4833/0.4265 | 18/20; 5/5 |
| step-160-dev | 0.9020 | 77/80 | 0.4308/0.4667/0.4480 | 13/20; 5/5 |
| base-test | 2.2451 | 80/80 | 0.4000/0.0667/0.1143 | 1/20; 1/5 |
| selected-test | 0.9457 | 79/80 | 0.4138/0.4000/0.4068 | 10/20; 4/5 |

Mỗi state gồm **80 target / 20 source**, mỗi Level20 target. Taxonomy F1 là metric chẩn đoán, không phải điểm Task3 chính thức. Invalid giữ trong mẫu số; faulty invalid tính FN của nhãn gold, clean invalid vẫn là failure riêng, không thành clean prediction. Bảng per-Level đầy đủ trong metrics-summary.json.

## Review chất lượng

Review do Codex agents đối chiếu source/spec và từng phản hồi, không phải người chấm độc lập hay grader chính thức. Không dùng keyword hoặc exact wording để chấm semantic.

| State | Chẩn đoán pass/fail/?/NE | Level pass/fail/?/NE | Tiếng Việt pass | L3 repair pass/fail/N/A/NE | L4 solution pass/fail/?/NE |
|---|---|---|---:|---|---|
| base-dev | 38/38/4/0 | 31/49/0/0 | 80/80 | 2/16/2/0 | 0/20/0/0 |
| step-80-dev | 42/31/4/3 | 27/50/0/3 | 77/80 | 0/19/0/1 | 4/14/0/2 |
| step-160-dev | 38/36/3/3 | 46/31/0/3 | 77/80 | 0/19/0/1 | 6/12/0/2 |
| base-test | 23/57/0/0 | 33/47/0/0 | 80/80 | 1/14/4/0 | 0/20/0/0 |
| selected-test | 29/49/1/1 | 51/28/0/1 | 79/80 | 1/17/1/0 | 5/14/0/1 |

Tổng hợp mọi verdict, kể cả not_applicable/not_evaluable, theo Level và state ở quality-summary.json. L3/L4 chỉ có20 target mỗi state; các verdict ở Level khác không thuộc mẫu số chuyên biệt.

## Chi phí thực đo

Toàn tiến trình GPU: 808.05 giây (bao gồm load, train, eval, save/reload và I/O). Counts: `{"base_model_loads": 1, "primary_generations": 400, "smoke_generations": 2, "smoke_optimizer_steps": 4, "main_optimizer_steps": 160, "primary_reservations": 400, "smoke_reservations": 2, "generations_with_uncertain_completion": 0, "teacher_forced_evaluation_forwards": 400, "training_forwards": 656, "smoke_reload_logit_forwards": 2, "adapter_reloads": 2}`.

| Phần | Thời gian giây | Peak allocated / reserved GiB |
|---|---:|---|
| smoke training | 6.11 | 10.03 / 11.02 |
| main training time; memory = last checkpoint eval window | 214.69 | 9.05 / 11.58 |
| base-dev: teacher-forced / generation | 7.50 / 62.23 | 8.51 / 10.80 |
| step-80-dev: teacher-forced / generation | 8.50 / 164.04 | 9.05 / 11.58 |
| step-160-dev: teacher-forced / generation | 7.34 / 124.42 | 9.05 / 11.58 |
| base-test: teacher-forced / generation | 6.16 / 53.53 | 8.67 / 10.83 |
| selected-test: teacher-forced / generation | 7.19 / 124.92 | 8.67 / 10.83 |

Smoke generation riêng: 2 calls, 60 output token, 1.570 giây. Chi phí token/thời gian từng state và từng Level nằm trong metrics-summary.json/cost-summary.json; thời gian reload-logit riêng chưa tách khỏi toàn tiến trình.

Đây là NF4 base double quantization, BF16 compute; không phải mọi weights lưu BF16. Loss trung bình assistant CE trong từng hàng rồi trung bình đều giữa hàng, weight1; L4 có68,42% token completion train, không suy ra68,42% loss share.

**Giới hạn đo VRAM:** eval reset bộ đếm peak CUDA, nên peak ghi trong main/training-result.json chỉ phản ánh cửa sổ checkpoint eval cuối; chưa giữ riêng peak allocated/reserved bao trùm toàn bộ main training. Các peak smoke và từng eval có phạm vi đo rõ. Không dùng giá trị main đó như peak toàn trajectory.

## Tái lập và resume

Chạy từ worktree, giữ nguyên dependency/snapshot/cache đã pin:

```bash
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v1_experiment.py \
  --out outputs/task3/sft-v1-qlora-REPRO-NEW
```

Mỗi thí nghiệm mới tạo thư mục mới. Lệnh sau chỉ dành cho tiếp tục run bị ngắt, không dùng để chạy lại run đã xong:

```bash
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v1_experiment.py \
  --out outputs/task3/sft-v1-qlora-20261026-run1 --resume
```

Resume bỏ qua generation đã lưu, không retry semantic; reservation mất output thành missing/uncertain. Chỉ tiếp tục native checkpoint có optimizer/scheduler/RNG khi journal không có optimizer progress vượt checkpoint; ngắt giữa step bị từ chối để tránh replay ngầm. Smoke bị ngắt cần chẩn đoán riêng, không tự mở lại trajectory.

## Artifacts và giới hạn

manifest.json giữ code/data/tokenizer hashes, HEAD/status, versions, recipe, generation/parser/rubric/budgets/smoke IDs. actual-training-arguments.json, peft-config.json và model-audit.json ghi cấu hình thực. Checkpoint80/160 có adapter/optimizer/scheduler/RNG/trainer state và hash; journal/training-log lưu bước/loss/LR/gradient. Smoke có real minibatch và save/reload logits audit. dev-paired.html/test-paired.html chứa đầy đủ source, gold, raw/parsed và trạng thái trước/sau.

200 source thuộc50 đặc tả synthetic; dev/test cùng trợ lý biên soạn, không phải gold độc lập của BTC. Loss thấp hơn không chứng minh public accuracy hoặc đủ cơ sở thay A/R15. Không public inference/leaderboard mới; 0.3834 chỉ là số lịch sử người dùng báo.

## Ví dụ trước/sau và quyết định sử dụng

- Cải thiện dev F23-D2-L4: base bỏ sót lỗi palindrome; step160 nhận ra trạng thái ok bị đặt lại true sau một cặp ký tự khớp và đưa chương trình đầy đủ giữ trạng thái lỗi. Code vượt bộ test authored hữu hạn.
- Cải thiện test F45-D1-L2: adapter nêu đúng thiếu cạnh ngược của đồ thị vô hướng. F45-D3-L4 có code BFS đúng với d[v]=d[u]+1, dù phần giải thích vẫn quy sai nguyên nhân xử lý đỉnh không tới được.
- Hồi quy test F41-D3-L3: base chỉ đúng lỗi giây và hướng t%60; adapter chuyển sang đổ lỗi công thức phút vốn đúng, hướng sửa sai.
- False alarm clean F45-C-L1/L2/L3: base chấp nhận chương trình BFS đúng; adapter gắn lỗi và ở L3 đòi cập nhật lại đỉnh đã thăm, không phù hợp BFS đồ thị không trọng số.
- Level leakage base-dev F23-D3-L2: đưa replacement bound/cách sửa ở Level2. Việc mất thông tin ở adapter không được tính là cải thiện chẩn đoán chỉ vì hết lộ cách sửa.
- Invalid selected-test F46-D2-L4: JSON lỗi escape dấu nháy trong cout; giữ nguyên raw và tất cả axes not_evaluable, không repair.

Giữ baseline A/R15 hiện dùng. Loss giảm và taxonomy F1 tăng không đủ để thay baseline: false alarms clean và chất lượng L2/L3 còn yếu; code L4 đúng có thể đi kèm giải thích sai. Nếu làm thí nghiệm tiếp theo, cần mục tiêu cụ thể giảm false alarms và giữ chẩn đoán/hướng sửa đúng; không tự mở thêm grid search trong lượt này.

Tất cả ví dụ có raw text và evidence trong paired-examples.json; mọi output kể cả invalid nằm trong casebooks và invalid-responses.jsonl. Đây là review agent có thể sai; bộ authored test hữu hạn, dev/test synthetic cùng tác giả, không phải chứng nhận tổng quát hóa hay điểm chính thức.

## Kiểm C++ bổ sung cho L4

| State | Qua bộ test | Sai test | Compile lỗi | Chưa trích được code | Invalid |
|---|---:|---:|---:|---:|---:|
| base-dev | 0 | 0 | 0 | 20 | 0 |
| step-80-dev | 4 | 3 | 1 | 10 | 2 |
| step-160-dev | 6 | 2 | 0 | 10 | 2 |
| base-test | 0 | 0 | 0 | 20 | 0 |
| selected-test | 5 | 1 | 0 | 13 | 1 |

Thực chạy 22 compiler calls và 158 authored runtime tests. Mỗi hàng20 target L4. Phần unfenced bổ sung sau khi quan sát format code trần; policy/hash riêng, không thay metric primary. Không sửa code/retry. Qua test hữu hạn không chứng minh lời giải tổng quát hoặc giải thích đúng.

132 test liên quan passed;3 optional jail probes skipped. Audit thực đã chạy sandbox C++. Giữ nguyên22 file chưa commit trước thí nghiệm, HEAD/branch và dataset.

Tái tạo audit và báo cáo từ các outputs đã có, không gọi Qwen:

```bash
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v1_l4_audit.py --run outputs/task3/sft-v1-qlora-20261026-run1
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v1_l4_unfenced_audit.py --run outputs/task3/sft-v1-qlora-20261026-run1
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v1_report.py --run outputs/task3/sft-v1-qlora-20261026-run1
```

Hai audit giữ nguyên kết quả đã lưu, chỉ bổ sung target chưa xử lý. Review semantic là artifact agent đã lưu, không tự tái sinh bằng keyword.
