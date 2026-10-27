# Task 3 SFT v3 — đặc tả đóng băng

Yêu cầu gốc: `DoAn-LLM-Challenge.docx.md`, SHA256 `2acd25dd63c422c95f6b055cee7d9edf693b76dd1021983452491cd10fe6cd3b`.
Label chính thức: `/workspace/llm-final-project/data/raw/public_test_release/label_space.json`, SHA256 `056a4d1a0ccfd60688b43efdf5df64a4c1310e3c6f1d99ab813691a2da27a9dc`.

- **Level 1 - Gợi ý nhẹ**: “Chỉ báo có vấn đề / khen ngợi, không chỉ ra vị trí lỗi.” Cấm: “không nêu nguyên nhân cụ thể, không đưa code sửa.”
- **Level 2 - Chẩn đoán**: “Chỉ ra lỗi ở đâu và nguyên nhân là gì.” Cấm: “không đưa cách sửa cụ thể, không đưa code.”
- **Level 3 - Gợi ý sửa**: “Chẩn đoán + gợi ý hướng sửa.” Cấm: “không đưa lời giải hoàn chỉnh.”
- **Level 4 - Lời giải mẫu**: “Được phép đưa code sửa / lời giải mẫu.” Cấm: “—”

Đề gốc nhận nhãn cho sẵn; schema public yêu cầu taxonomy + feedback. Candidate ở đây tự chẩn đoán end-to-end; oracle là probe riêng chỉ trên dev.
Không giới hạn L2 một câu. L4 không bắt buộc code. Độ dài tăng theo Level là phong cách tùy chọn. Chẩn đoán L2 chính xác được phép dù người học suy ra cách sửa. Hướng sửa cục bộ có thể cụ thể ở L3; không đưa chương trình/lời giải hoàn chỉnh.

Dữ liệu train được audit toàn bộ bằng agent, không phải human gold độc lập. Giữ nguồn/spec/split và gold lịch sử; canonical private không vào dataloader. Dev20/80 để chọn; final40/160 đã quan sát chỉ mở nội dung sau selection.

Một adapter mới, pinned Qwen revision c03e6d358207e414f1eca0bb1891e29f1db0e242, NF4 double quant/BF16, LoRA16/32/0.05, LR2e-5, AdamW weight_decay0, cosine, warmup0.03, clip1, batch1/accum4/seed42, context train8192, 2 epoch. Không packing/truncation, assistant-only termination loss và equal-example mean. Smoke16 targets/4 steps/2 generation tối đa, bỏ toàn bộ cập nhật smoke. Lưu ở cuối mỗi epoch. Evaluation context32768, greedy một lần, L1–3 tối đa1024 token, L4 tối đa1536, max_time45s.

640 dev generation = 4 states × (80 end-to-end + 80 oracle). Sau selection khóa, 480 observed-final end-to-end = 3 states ×160. Không semantic retry/verifier/public inference.

Các trục: disclosure chính thức; chẩn đoán/coverage; fidelity/điều kiện; hướng sửa L3; hữu ích L4; code đúng; tiếng Việt/schema. Hướng sửa sai không tự động tính thành disclosure sai. Clean không cần lỗi/hướng sửa hư cấu. Faulty khen chung không hoàn thành nhiệm vụ. Code có cung cấp mà sai làm joint fail.

Eligibility so với v2 cùng prompt: invalid, clean false alarm, faulty miss cộng faulty invalid không tăng; supported faulty diagnosis và L3 correct không giảm. Trong ứng viên đạt: Level, balanced joint, oracle fidelity+Level joint, dev loss, checkpoint sớm. Không ai đạt: balanced joint, supported faulty diagnosis, Level, sớm; ghi fail promotion rồi vẫn đánh giá final. Mục tiêu95% chỉ mô tả.

Cùng thay target và prompt nên không tách được tác động nhân quả. Oracle đổi nhiệm vụ nên chênh lệch oracle/end-to-end không phải phân rã nhân quả thuần túy. Điểm lịch sử user báo A0.3834, v2 0.3567, B0.3247 không phải số đo mới. Không suy điểm public từ synthetic.
