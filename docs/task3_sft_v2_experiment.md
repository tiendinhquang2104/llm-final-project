# Task 3 SFT v2 — cách chạy và đọc kết quả

Worktree `/workspace/llm-final-project-arm-d-plus`, branch
`fix/task3-strict-feedback`; HEAD gốc `60c76dc1a1104557b5d10dca4f78baf57413cf4d`.
Không commit/push trong thí nghiệm này. Các thay đổi và output v1 được giữ nguyên.

Run: `outputs/task3/sft-v2-qlora-20261026-run1/`.
Dataset riêng: `data/raw/task3-sft-v2/`. Manifest/checksum bao gồm train240
nguồn/960 targets, dev20/80, test cũ20/80 và final mới40/160. Test cũ là tập
regression đã quan sát. Final là synthetic, agent-reviewed, không phải gold độc lập.

Quy trình dùng lại encoder, collator, equal-example completion loss, Trainer,
khởi tạo adapter, smoke và native generation của v1. Mã v1 không bị sửa.
Recipe tương thích v1 còn giữ trường chọn checkpoint theo loss để qua validator
cũ; **quy tắc semantic trong manifest v2 mới là quy tắc chọn thực tế**.

Lệnh đã chạy theo thứ tự, bằng Python có sẵn:

```bash
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_prepare.py --out outputs/task3/sft-v2-qlora-20261026-run1
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_experiment.py freeze --out outputs/task3/sft-v2-qlora-20261026-run1
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_experiment.py ar15-dev --out outputs/task3/sft-v2-qlora-20261026-run1
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_experiment.py train --out outputs/task3/sft-v2-qlora-20261026-run1
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_review.py packets --split dev --out outputs/task3/sft-v2-qlora-20261026-run1
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_review.py l4 --split dev --out outputs/task3/sft-v2-qlora-20261026-run1
```

Sau khi hoàn tất review có bằng chứng, lệnh `select` ghi quyết định và seal
hash; không cho chạy final nếu decision, checkpoint hay bằng chứng dev thay đổi:

```bash
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_review.py select --out outputs/task3/sft-v2-qlora-20261026-run1
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_experiment.py final-native --out outputs/task3/sft-v2-qlora-20261026-run1
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_experiment.py ar15-final --out outputs/task3/sft-v2-qlora-20261026-run1
```

Export/freeze/train/select từ chối ghi đè trạng thái đã hoàn tất. `train --resume`
chỉ dùng khi checkpoint native đã được seal và journal không có bước vượt qua
checkpoint; không âm thầm replay optimizer. Reservation sinh dang dở được giữ
thiếu, không gọi lại. Không chạy lại các lệnh GPU chỉ để dựng báo cáo.

Sau khi generation và review final/regression hoàn tất, lệnh offline tái tạo
casebooks và báo cáo, không load model:

```bash
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_report.py --run outputs/task3/sft-v2-qlora-20261026-run1
```

`analysis.json` kiểm khớp per-target verdict với tổng, giữ invalid trong mẫu số.
HTML nhúng source/spec, raw/parsed, bằng chứng review và kết quả L4 riêng.
“FA được sửa” trong nhóm ví dụ là thay đổi **taxonomy false alarm**; vẫn phải đọc
verdict diagnosis/unsupported defects để biết văn xuôi có hết chẩn đoán bịa hay chưa.

Review chỉ mù một phần: packet ẩn tên và đảo panel theo source, nhưng agent giữ
lịch sử task và có vai trò author/reviewer. L3 hướng sửa sai fail cả repair lẫn
Level theo calibration dùng chung; hai trục này không độc lập. L4 giải thích và
code được chấm riêng. Reviewer có thể sai; ledger adjudication lưu những chỗ
cùng source/Level/payload được chấm không nhất quán, giữ cả bản review ban đầu.

A/R15 dùng snapshot renderer/backend/controller/parser/guard/fallback lịch sử,
tối đa ba lần thử; native chỉ một lần. JSON export được controller chấp nhận
khác với tính hợp lệ của raw attempt. Casebook giữ cả export và raw/termination
từng attempt. Đây là system comparator; chỉ native base/v1/v2 là so sánh adapter
với cùng prompt. Không có public inference hoặc điểm leaderboard mới.
