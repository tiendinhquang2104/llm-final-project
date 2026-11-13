# Model card — Task 1 rubric grader (QLoRA adapter)

> Số liệu của adapter **v4** (lượt Kaggle `task1-run-20261113T032613Z`, commit `71654c0`). Các ô `…` còn lại lấy từ
> `public_predictions/run_info.json` của lượt đó.

| | |
|---|---|
| **Nhiệm vụ** | Chấm bài C++ nhập môn theo rubric 6 chiều (`compilable` 0–1, `io_format` 0–1, `logic` 0–4, `edge_case` 0–2, `complexity` 0–1, `code_quality` 0–1) và tổng 0–10 |
| **Model nền** | [`Qwen/Qwen2.5-Coder-7B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct), Apache-2.0, 7,6B tham số |
| **Phương pháp** | QLoRA 4-bit NF4, LoRA r 16 / alpha 32 trên mọi lớp attention/MLP; loss chỉ tính trên JSON trả lời; greedy decoding (tất định) |
| **Adapter** | Riêng cho Task 1 (`best_adapter/`, khoảng 160 MB). Task 2 và 3 có adapter riêng |
| **Biến thể được chọn** | `silver_then_gold`, **checkpoint cuối giai đoạn silver** (epoch silver 2, `checkpoint-216`); giai đoạn gold sau silver không được chọn |
| **Input** | Đề bài + code sinh viên + `compile_log` (chỉ giữ lỗi compiler/linker) + `test_report` (nếu có). **Không** dùng `feedback` (có kiểm tra tự động) |
| **Output** | `{"rubric": {...}, "total_score": n}`; `total_score` được tính lại bằng tổng 6 chiều |

## Dữ liệu huấn luyện
- **Gold:** 32 bài giảng viên chấm (đề EX01 nhiều câu, EX02 một câu), split cố định seed 42: 26 train / 6 validation.
- **Silver:** bài tổng hợp từ `generate-dataset.zip`, nhãn do rulebook gán sau khi chạy code. Sau kiểm tra còn 422/462
  bài (bị loại vì trùng code, mâu thuẫn `exec_report`, trùng gold/public). Bài heldout không được dùng để train.
- **Silver v3+ (distillation, dùng cho adapter v4):** cùng các bài silver, nhưng nhãn do hướng API (Gemini 3.5 Flash Lite,
  e2 + rule) chấm lại (`scripts/distill_task1_silver.py`). Sau lọc còn 418/462 bài; 41 bài (10% mỗi đề) giữ lại để chọn
  checkpoint, 377 bài train cùng 2 bản gold train (replay).
- **Cách train v4:** silver + replay 2 epoch, lr 1e-4; sau đó 2 epoch gold, lr 3e-5. Nhánh đối chứng gold-only: 3 epoch,
  lr 1e-4. Chọn checkpoint theo QWK (rồi MAE) trên 6 bài gold val + 41 bài silver val.
- **Không dùng** input của public/private test để sinh nhãn hay chọn tham số.

## Kết quả

**Validation** (checkpoint tốt nhất của mỗi nhánh):

| Nhánh | QWK gold val (6) | MAE gold val | QWK silver val (41) | QWK tập chọn (47) | MAE tập chọn |
|---|---|---|---|---|---|
| gold-only (epoch 2) | 0.430 | 3.17 | 0.340 | 0.362 | 2.62 |
| **silver → gold (silver ep 2)** | 0.428 | 3.17 | **0.874** | **0.756** | **1.17** |

Trên 6 bài gold hai nhánh gần như bằng nhau; silver val (độ khớp với giáo viên API) mới tách được hai nhánh.

**Public leaderboard** (328 bài, 6 đề mới, không có nhãn tại máy):

| Hệ thống | QWK | MAE | compilable | io_format | logic | edge_case | complexity | code_quality |
|---|---|---|---|---|---|---|---|---|
| QLoRA v1 (nhãn generator) | 0.7188 | 2.03 | 0.909 | 0.817 | 0.595 | 0.622 | 0.805 | 0.768 |
| QLoRA v3 (nhãn API, cách train v1) | 0.7096 | 1.94 | 0.909 | 0.796 | 0.686 | 0.720 | 0.781 | 0.747 |
| **QLoRA v4 (adapter này)** | **0.7955** | **1.66** | 0.909 | 0.881 | 0.598 | 0.637 | 0.851 | 0.820 |
| API e7 (Gemini, giáo viên) | 0.8759 | 1.12 | 0.909 | 0.878 | 0.723 | 0.808 | 0.866 | 0.814 |

## Phần cứng và chi phí
| | |
|---|---|
| Train | Kaggle 1× Tesla T4 16 GB, fp16; thời gian `…`; VRAM đỉnh `…` GB |
| Dự đoán 328 bài | `…` giây, `…` token sinh ra, VRAM đỉnh `…` GB (`run_info.json`) |
| Chi phí | Train/dự đoán: GPU miễn phí của Kaggle. Gán nhãn silver bằng API (Gemini 3.5 Flash Lite): 464 request, 637.713 token input / 103.439 token output, 0 USD (free tier) (`distill_manifest.json`) |
| Chạy lại | `bash run.sh --task1-finetune --gold-root … --public-root … --silver-root … --work-dir …` trên máy có GPU ≥ 8–16 GB |

## Giới hạn
- **Đánh giá ít bài gold:** chỉ có 6 bài gold validation thuộc 2 đề. Từ v4 việc chọn checkpoint dùng thêm 41 bài silver
  giữ lại, nhưng silver val đo độ khớp với **giáo viên API** trên đề tổng hợp, không phải với giảng viên trên đề thật.
  Các đề thi là 6 đề khác hẳn.
- **Chấm cao:** trên public, adapter lệch trung bình +0.52 điểm so với API e7 (cho tổng 7 ở 73/328 bài, API 17), và
  thấp hơn API rõ ở `logic`, `edge_case`.
- **Không áp rule câu tiên quyết bằng code:** model không trả trạng thái P1–P4, nên chính sách "P1 sai thì các câu sau
  không được tính" chỉ được học ngầm từ điểm. Hướng API có rule này bằng code.
- **Silver là nhãn tổng hợp:** chấm theo rulebook, trọng số câu 2,5 điểm (đề thật 1/4/2/3), không có `compile_log`;
  model có thể học theo bộ sinh dữ liệu thay vì theo cách giảng viên chấm.
- **Nhãn gold có mâu thuẫn:** 3 bài EX01 cho điểm câu sau dù P1 sai (`scripts/audit_task1_labels.py`).
- **Output hỏng định dạng:** bài như vậy nhận điểm trung vị theo dạng đề (`fallback_used`, số lượng ghi trong `run_info.json`).

## Rủi ro khi dùng để chấm điểm thật
- **Sai lệch có hệ thống:** model có thể chấm sai cả một kiểu bài (ví dụ lỗi kiểu MSVC bị coi là không biên dịch được),
  ảnh hưởng tới nhiều sinh viên cùng lúc. Cần giảng viên duyệt, nhất là các bài điểm thấp hoặc lệch nhiều.
- **Không giải thích được:** model chỉ trả điểm, không có lý do. Sinh viên không biết vì sao bị trừ điểm.
- **Chỉ đúng phạm vi đã học:** chỉ phù hợp với bài C++ nhập môn cùng dạng đề. Đề mới, ngôn ngữ khác, bài dài hơn
  khoảng 3.800 token đều nằm ngoài phạm vi đã kiểm chứng.
- **Dữ liệu cá nhân:** bài làm sinh viên đã ẩn danh, nhưng vẫn không được phát tán; adapter train trên dữ liệu lớp học
  không nên chia sẻ công khai.
- **Khuyến nghị:** dùng như công cụ **gợi ý điểm** để giảng viên duyệt, không thay thế giảng viên.
