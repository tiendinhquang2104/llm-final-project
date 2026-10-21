# Task 3 — DIRECT SFT v1: candidate nộp thử (2026-10-21, Asia/Saigon)

**Candidate thử nghiệm hợp lệ về schema, 328/328 ID; không thay R15 production.** Adapter v1 **không đạt gate nghiên cứu Level 3**. Người dùng yêu cầu chọn bản này để nộp thử dựa trên development đã có; không coi đây là phương pháp đã chứng minh thắng leaderboard. Không train lại, không dùng adapter v2, không chọn lại checkpoint hoặc chỉnh method theo public output. Không push hoặc upload leaderboard.

**File để tự nộp:** [predictions.json](/workspace/llm-final-project/outputs/task3/direct-sft-v1-public-trial-20261021/predictions.json).

- SHA-256: `c30c5c136195df50529f70a95fb1cf63e0bf61e690930dbe3f82d1ddfbbb33f5`.
- Kích thước: **105592 bytes**.
- **328 ID**; L1 = **115**, L2 = **163**, L3 = **50**, L4 = **0**.
- Official validator CLI: **VALID, exit 0**. [Validator log](/workspace/llm-final-project/outputs/task3/direct-sft-v1-public-trial-20261021/validator.log), SHA `0fac64d88a34c896225b8a43cb1d01b22eac4d89df68310953600b08aca5822a`.
- Fallback: **0 requests**; phân bố: `{"Level 1 - Gợi ý nhẹ": 0, "Level 2 - Chẩn đoán": 0, "Level 3 - Gợi ý sửa": 0, "Level 4 - Lời giải mẫu": 0}`.

## Adapter, config và lựa chọn nộp thử

Đã verify toàn bộ frozen v1 trước public: manifest `a838199811b6dafe0c7b8f5264ae2e77b7b8e977a02d35ceb39c8f7bd82a1d55`, seal `ecbbb2f4ceb5aa3fc0aa6ddbd07c6dc384dfd2afb21c42690b8affa95a901a1d`, config `4131a48a9d912cd088133be69908d04c068965088d956df1faa4c00b30d02e6e`; 77 implementation hashes và library versions đều khớp. Adapter epoch 2 giữ nguyên lựa chọn internal TRAIN-only validation cũ; tensor SHA đúng **`a193807c8e21c1d4bd9d826717e9c40dc32d6f18f891e39a78a7517f4c21de3e`**, cả 10 file checkpoint khớp training result.

Base `Qwen/Qwen2.5-Coder-7B-Instruct`, revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`; 11 file snapshot được hash trước chạy. Runtime xác nhận đúng resolved revision, NF4 double quantization/BF16 trên CUDA. Giữ nguyên native R15 direct prompt, greedy seed42, context16384, cap1024/L4cap1536, deadline60s, tối đa3 attempts, fewshot0, disclosure guard và fallback của **phép so sánh DIRECT v1**. Deadline60s này là config v1 đã khóa; không đổi sang mặc định45s của R15 production.

Gate nghiên cứu cũ và báo cáo v1 vẫn giữ nguyên failed. Đây là lựa chọn thử theo yêu cầu mới của người dùng, được ghi trong metadata riêng; không sửa gate để gọi candidate là research-approved. Mốc R15 **0,3834** là điểm người dùng cung cấp để tự đối chiếu, không được xác minh qua leaderboard trong lượt này và không dùng chỉnh phương pháp. Candidate v1 chưa có điểm leaderboard trong lượt này.

## Một pass public và provenance

Public chỉ dùng làm inference input và kiểm coverage/schema, không dùng làm few-shot, target, train hoặc tín hiệu chọn prompt/checkpoint. Tạo requested-Level map riêng trong ignored storage từ ID và Level gốc vì raw release không có file map tách riêng. Tập và thứ tự328ID khớp release; hai ID có cùng payload vẫn được xử lý riêng. Không sửa tay taxonomy/feedback hoặc đọc nội dung từng ID để đổi cấu hình.

Có hai lỗi setup được giữ nguyên log: chuẩn bị timestamp/serialization dừng trước model load; sau đó wrapper ghi log dành cho comparison yêu cầu payload duy nhất và dừng **trước mọi generation**, vì328ID có327payload khác nhau. Dùng `RawCaptureBackend` R15 sẵn có cùng `run_records` nguyên trạng để ghi raw/attempt identity. Chỉ auxiliary capture khác; không sửa prompt, model/config, decoder, guard hoặc fallback. Có **một pass thực sự sinh public output**.

Pass hoàn tất **328/328**, unresolved **0**; raw calls **341**, extra retry calls **13**, schema-error attempts **0**, fallback **0**. Final origins: `{"qwen_initial": 315, "qwen_retry": 13}`. Không tạo output giả để lấp thiếu; projection submission lấy nguyên final của controller.

Audit cơ học tái dựng từng actual prompt/retry, kiểm examples_used=0, raw→attempt→decision, schema/disclosure và fallback native, rồi đối chiếu exact final với file submission. **Không semantic review public hoặc suy F1/chất lượng từ JSON hợp lệ.** Validator chỉ chứng nhận schema, nhãn hợp lệ, feedback không rỗng, ID/thứ tự và coverage; không chứng nhận Level3 usefulness, truth hoặc điểm thi.

Raw public và actual messages nằm riêng dưới ignored `/workspace/llm-final-project/outputs/task3/direct-sft-v1-public-trial-20261021/public-inference`. Adapter giữ nguyên tại ignored `/workspace/llm-final-project/outputs/task3/direct-sft-v1-20261021/training/adapter`; không copy weights vào Git. Candidate/map/log cũng ignored. [Metadata](TASK3_DIRECT_SFT_V1_PUBLIC_TRIAL_20261021.json) chỉ chứa config/hash/count/provenance, không source, feedback hay raw public.

## Bảo toàn và kiểm chứng

**825 file cũ giữ nguyên SHA**, gồm frozen v1/adapter, production code và seal lịch sử. R15 tại `/workspace/llm-final-project/predictions.json` vẫn **`9ba7411c35a3461b5747be367274631d5122455335061005c695276ed76c5a45`**. Không ghi đè file này bằng candidate thử nghiệm.

Existing artificial controller/inference/validator tests: **27 passed in 0.09s**. Official validator trên file thực đã chạy thành công. Commands kiểm lại từ repo, không gọi model:

```bash
.venv-task3/bin/python scripts/validate_task3_submission.py --predictions outputs/task3/direct-sft-v1-public-trial-20261021/predictions.json --requested-levels outputs/task3/direct-sft-v1-public-trial-20261021/task3_requested_levels.json
.venv-task3/bin/python scripts/task3_direct_sft_prepare.py verify
sha256sum outputs/task3/direct-sft-v1-public-trial-20261021/predictions.json predictions.json
```

Private driver/public-run/audit cùng exact hashes và setup logs được giữ để audit. Không chạy lại inference hoặc xóa marker để tìm output thuận lợi. HEAD trước lượt này `0ead2a83ca124f898c191cdf87eb58bbadeb3c08`; HEAD commit bàn giao ghi trong chat. Chỉ commit report/metadata mới; không push, không tự upload.
