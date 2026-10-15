# Model card — Task 1 rubric grader (QLoRA adapter)

> Điền các ô `…` từ `training_summary.json`, `public_predictions/run_info.json` và `scripts/compare_task1_methods.py`
> sau lượt chạy đầy đủ (`bash run.sh --task1-finetune …` hoặc `kaggle/task1_finetune.ipynb`, `MODE='full'`).

| | |
|---|---|
| **Nhiệm vụ** | Chấm bài C++ nhập môn theo rubric 6 chiều (`compilable` 0–1, `io_format` 0–1, `logic` 0–4, `edge_case` 0–2, `complexity` 0–1, `code_quality` 0–1) và tổng 0–10 |
| **Model nền** | [`Qwen/Qwen2.5-Coder-7B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct), Apache-2.0, 7,6B tham số |
| **Phương pháp** | QLoRA 4-bit NF4, LoRA r 16 / alpha 32 trên mọi lớp attention/MLP; loss chỉ tính trên JSON trả lời; greedy decoding (tất định) |
| **Adapter** | Riêng cho Task 1 (`best_adapter/`, khoảng 160 MB). Task 2 và 3 có adapter riêng |
| **Biến thể được chọn** | `…` (gold-only hoặc silver→gold), epoch `…` |
| **Input** | Đề bài + code sinh viên + `compile_log` + `test_report` (nếu có). **Không** dùng `feedback` (có kiểm tra tự động) |
| **Output** | `{"rubric": {...}, "total_score": n}`; `total_score` được tính lại bằng tổng 6 chiều |

## Dữ liệu huấn luyện
- **Gold:** 32 bài giảng viên chấm (đề EX01 nhiều câu, EX02 một câu), split cố định seed 42: 26 train / 6 validation.
- **Silver:** bài tổng hợp từ `generate-dataset.zip`, nhãn do rulebook gán sau khi chạy code. Sau kiểm tra còn 422/462
  bài (bị loại vì trùng code, mâu thuẫn `exec_report`, trùng gold/public). Bài heldout không được dùng để train.
- **Không dùng** input của public/private test để sinh nhãn hay chọn tham số.

## Kết quả (6 bài gold validation)
| Hệ thống | QWK | MAE | Exact total |
|---|---|---|---|
| QLoRA gold-only (epoch tốt nhất) | … | … | … |
| QLoRA silver→gold (epoch tốt nhất) | … | … | … |
| API zero-shot / few-shot (cùng 6 bài, trước / sau rule) | … | … | … |

Public test (360 bài, 6 đề mới) không có nhãn: chỉ có điểm leaderboard.

## Phần cứng và chi phí
| | |
|---|---|
| Train | Kaggle 1× Tesla T4 16 GB, fp16; thời gian `…`; VRAM đỉnh `…` GB |
| Dự đoán 360 bài | `…` giây, `…` token sinh ra, VRAM đỉnh `…` GB (`run_info.json`) |
| Chi phí | Không tốn phí API (GPU miễn phí của Kaggle) |
| Chạy lại | `bash run.sh --task1-finetune --gold-root … --public-root … --silver-root … --work-dir …` trên máy có GPU ≥ 8–16 GB |

## Giới hạn
- **Đánh giá trên 6 bài:** chọn adapter dựa trên 6 bài gold validation thuộc 2 đề, nên số đo rất nhiễu và có thể lạc quan.
  Các đề thi là 6 đề khác hẳn.
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
