# KẾ HOẠCH CHI TIẾT THỰC HIỆN ĐỒ ÁN MÔN HỌC LARGE LANGUAGE MODEL
## HƯỚNG TIẾP CẬN: MÔ HÌNH HỢP NHẤT (UNIFIED MULTI-TASK MODEL)

* **Tên đồ án:** Hệ thống Chấm điểm và Phản hồi Sư phạm Tự động cho Bài Lập trình C++ của Sinh viên dựa trên Mô hình Ngôn ngữ Lớn Hợp nhất (Unified Multi-Task LLM)
* **Khóa học:** Học viên Cao học — Lớp Large Language Model
* **Thời lượng:** 8 tuần
* **Mô hình nền tảng chủ lực:** `Qwen/Qwen2.5-Coder-7B-Instruct` (Tập trung toàn lực huấn luyện trực tiếp trên bản 7B ngay từ đầu để tối ưu thời gian)
* **Tài liệu tham chiếu:** [DoAn-LLM-Challenge.docx.md](file:///c:/Users/daniel.dinh/Desktop/Learning/LLM/DoAn-LLM-Challenge.docx.md) và [KhaoSat-MoHinh-LLM-Duoi-10B.md](file:///c:/Users/daniel.dinh/Desktop/Learning/LLM/KhaoSat-MoHinh-LLM-Duoi-10B.md)

## 1. THÔNG TIN CHUNG & PHÂN CÔNG ĐỘI NGŨ THỰC HIỆN

Đội ngũ gồm 5 thành viên được tổ chức theo các vai trò kỹ thuật chuẩn mực của một dự án Trí tuệ Nhân tạo / LLMOps:

| STT | Họ và tên (Quy ước) | Vai trò chính | Trách nhiệm chuyên môn |
| :---: | :--- | :--- | :--- |
| 1 | **Tiến** | **Project Lead & MLOps Engineer** | Quản lý tiến độ chung, thiết lập hạ tầng Unsloth/GPU, pipeline tự động hóa suy luận và đóng gói repository. |
| 2 | **Hưng** | **Data & NLP Engineer** | EDA dữ liệu, tiền xử lý code C++, chuẩn hóa định dạng ChatML, bảo đảm chống rò rỉ nhãn (Data Leakage Guard). |
| 3 | **Nam** | **Modeling & Fine-Tuning Engineer** | Thiết kế kiến trúc Prompt/LoRA Adapter, tinh chỉnh siêu tham số huấn luyện QLoRA 4-bit trên Colab T4 / GPU cá nhân. |
| 4 | **Trang** | **Evaluation & Post-Processing Specialist** | Xây dựng công cụ đo metric local (QWK, Macro-F1, Level Compliance), tối ưu ngưỡng (threshold tuning) và luật nghiệp vụ đề thi. |
| 5 | **Dũng** | **Prompt Engineer & Error Analyst** | Xây dựng nhánh đối chứng Prompting (Hướng 1), phân tích lỗi sai (Error Analysis) và trích xuất bằng chứng săn 10% điểm thưởng. |

## 2. BẢNG KẾ HOẠCH CHI TIẾT THỰC HIỆN DỰ ÁN (MASTER PLAN MATRIX)

Bảng phân rã công việc (Work Breakdown Structure) được chuẩn hóa theo đúng cấu trúc 6 cột (STT, Đầu mục, Công việc, Giai đoạn / Phần, Deadline, Người phụ trách), đánh số liên tục 32 đầu việc bao quát toàn bộ 8 tuần của đồ án:

| STT | Đầu mục | Công việc | Giai đoạn / Phần | Deadline | Người phụ trách |
| :---: | :--- | :--- | :--- | :---: | :---: |
| 1 | 1.1 Xác định tên & mục tiêu dự án | Xác định tên dự án, phạm vi bài toán, mục tiêu xây dựng 1 mô hình Unified giải quyết đồng thời cả 3 Task theo định dạng JSON. Sản phẩm: Project Charter, mục tiêu SMART và kiến trúc tổng quan. | Phần 1: Khởi động & Đặc tả yêu cầu | Ngày 3 - Tuần 1 | **Tiến** |
| 2 | 1.2 Xây dựng thông tin đội ngũ | Thiết lập bảng phân công nhiệm vụ 5 thành viên, kênh trao đổi, quy ước Git và lịch họp tiến độ 2 lần/tuần. Sản phẩm: Repository GitHub nhóm, bảng Kanban phân công công việc. | Phần 1: Khởi động & Đặc tả yêu cầu | Ngày 5 - Tuần 1 | **Tiến** |
| 3 | 1.3 Phân tích đặc tả 3 Task & Quy chế | Nghiên cứu kỹ barem chấm: Task 1 (QWK), Task 2 (Macro-F1), Task 3 (Level Compliance), luật cấm dùng feedback cho Task 1/2. Sản phẩm: Tài liệu tóm tắt đặc tả kỹ thuật, danh sách điều kiện biên và quy tắc cấm. | Phần 1: Khởi động & Đặc tả yêu cầu | Ngày 7 - Tuần 1 | **Trang** |
| 4 | 1.4 Khám phá dữ liệu (EDA) tập mẫu | Phân tích sample_dataset: đo độ dài token code C++, phân bố điểm rubric, tỷ lệ mất cân bằng của 10 nhãn lỗi. Sản phẩm: Notebook `eda_analysis.ipynb`, biểu đồ phân bố điểm số và nhãn lỗi. | Phần 2: Xử lý dữ liệu & EDA | Ngày 3 - Tuần 2 | **Hưng** |
| 5 | 1.5 Xây dựng bộ đánh giá cục bộ (Local Evaluator) | Lập trình các hàm tính toán metric cục bộ: QWK (Quadratic Weighted Kappa), MAE, Macro-F1, Micro-F1, Exact Match và regex kiểm tra vi phạm lộ code ở Level 1 & 2. Sản phẩm: Script `evaluator.py` độc lập dùng chung. | Phần 3: Thẩm định & Đo lường | Ngày 5 - Tuần 2 | **Trang** |
| 6 | 1.6 Xây dựng Hướng 1: Baseline Prompting LLM | Thiết kế prompt Zero-shot & Few-shot kèm CoT gọi mô hình qua API (GPT-4o-mini) hoặc Ollama Qwen2.5-Coder-7B; ghi nhận chi phí token. Sản phẩm: Script `baseline_prompting.py`, bảng thống kê chi phí API và baseline score ban đầu. | Phần 4: Baseline Prompting (Hướng 1) | Ngày 6 - Tuần 2 | **Dũng** |
| 7 | 1.7 Xuất file và nộp lần đầu Public Leaderboard | Tạo file `predictions.json` từ kết quả Baseline 1, chạy script kiểm tra định dạng của ban tổ chức và nộp thử nghiệm lần 1 lên Public Leaderboard. Sản phẩm: File `predictions_baseline.json`, xác nhận nộp thành công. | Phần 4: Baseline Prompting (Hướng 1) | Ngày 7 - Tuần 2 | **Tiến** |
| 8 | 2.1 Tiền xử lý dữ liệu huấn luyện ChatML | Viết script chuyển đổi toàn bộ bài tập mẫu (`exams.json` + `submissions/*.cpp` + `compile_log` + nhãn) thành file `train.jsonl` chuẩn template ChatML (`<|im_start|>...`). Sản phẩm: Script `preprocess_data.py`, tập dữ liệu `train_unified.jsonl`. | Phần 2: Xử lý dữ liệu & EDA | Ngày 2 - Tuần 3 | **Hưng** |
| 9 | 2.2 Thiết lập cơ chế chống rò rỉ nhãn (Data Leakage Guard) | Đảm bảo tuyệt đối trường `feedback` không xuất hiện ở phần `user` prompt khi huấn luyện Task 1 và Task 2; kiểm tra assert tự động trong pipeline. Sản phẩm: Test case tự động kiểm tra tính toàn vẹn dữ liệu huấn luyện (zero leakage). | Phần 2: Xử lý dữ liệu & EDA | Ngày 4 - Tuần 3 | **Hưng** |
| 10 | 2.3 Cài đặt môi trường Unsloth QLoRA 4-bit | Thiết lập môi trường huấn luyện Unsloth trên Google Colab T4 (16GB) và máy local RTX 3060/4060; kiểm tra khả năng tiết kiệm VRAM và tăng tốc x2-x5. Sản phẩm: File `environment.yml` / `requirements.txt` và notebook chạy thử. | Phần 5: Hạ tầng MLOps | Ngày 6 - Tuần 3 | **Tiến** |
| 11 | 2.4 Cố định Random Seed & Cấu hình siêu tham số | Thiết lập `random_state = 42` theo quy định tái lập; cấu hình LoRA rank $r=16$, alpha $\alpha=16$, learning rate $2\times 10^{-4}$, context length 2048, optimizer `adamw_8bit`. Sản phẩm: File cấu hình `training_config.yaml` và kịch bản train chính thức. | Phần 6: Huấn luyện Mô hình Chủ lực | Ngày 7 - Tuần 3 | **Nam** |
| 12 | 2.5 Sanity Check & Dry-run trực tiếp trên Qwen2.5-Coder-7B | Bỏ qua các bản nhỏ, chạy thử 30–50 steps trực tiếp trên `Qwen2.5-Coder-7B-Instruct` để rà soát mức ăn VRAM thực tế (~8.5GB trên T4), kiểm tra gradient loss và verify format output. Sản phẩm: Log dry-run xác nhận VRAM an toàn (< 10GB trên Colab T4), không OOM. | Phần 6: Huấn luyện Mô hình Chủ lực | Ngày 3 - Tuần 4 | **Nam** |
| 13 | 2.6 Huấn luyện chính thức toàn diện Qwen2.5-Coder-7B | Huấn luyện chính thức toàn diện trên `Qwen2.5-Coder-7B-Instruct` (500 steps / 3 epochs); tự động lưu checkpoint sau mỗi 50 steps và theo dõi validation loss. Sản phẩm: Checkpoint LoRA Adapter `final_lora_qwen7b_unified` (~150MB), đồ thị loss hội tụ. | Phần 6: Huấn luyện Mô hình Chủ lực | Ngày 5 - Tuần 4 | **Nam** |
| 14 | 2.7 Đánh giá sơ bộ & Nộp Public Leaderboard lần 2 | Dùng checkpoint 7B vừa huấn luyện suy luận trên tập dev; đo lường sự cải thiện so với Baseline 1 và nộp bài lên Public Leaderboard. Sản phẩm: Bảng so sánh điểm số Baseline vs Fine-tuned Model (QWK tăng, Macro-F1 tăng). | Phần 7: Đánh giá & Nộp bài Leaderboard | Ngày 7 - Tuần 4 | **Trang** |
| 15 | 3.1 Xây dựng bộ trích xuất JSON kiên cố (Robust Parser) | Lập trình module regex bóc tách JSON an toàn, tự động sửa lỗi thiếu dấu ngoặc nhọn hoặc ký tự thừa ngoài JSON để bảo đảm 100% không bị từ chối bài nộp. Sản phẩm: Module `json_extractor.py` kèm unit test trên 100 trường hợp sinh text bất thường. | Phần 8: Kỹ thuật Hậu xử lý & Tối ưu Metric | Ngày 2 - Tuần 5 | **Tiến** |
| 16 | 3.2 Tối ưu hóa Metric Task 1: Hiệu chỉnh QWK & Ràng buộc 6 chiều | Triển khai thuật toán hiệu chỉnh ngưỡng điểm số và ép điểm `total_score` phải nhất quán với tổng 6 tiêu chí rubric (loại bỏ trường hợp model sinh số mâu thuẫn). Sản phẩm: Thuật toán `qwk_calibrator.py`, cải thiện độ chính xác exact-match và QWK. | Phần 8: Kỹ thuật Hậu xử lý & Tối ưu Metric | Ngày 4 - Tuần 5 | **Trang** |
| 17 | 3.3 Ép quy tắc nghiệp vụ đề thi (Rule Enforcement) | Cài đặt luật cứng: với đề nhiều câu (`multi_problem`), nếu câu tiên quyết sai thì tự động gán các câu sau bằng 0 điểm đúng quy định đề bài. Sản phẩm: Hàm hậu xử lý `enforce_prerequisite_rule()` tích hợp vào pipeline. | Phần 8: Kỹ thuật Hậu xử lý & Tối ưu Metric | Ngày 6 - Tuần 5 | **Trang** |
| 18 | 3.4 Tối ưu hóa Metric Task 2: Threshold Tuning cho 10 nhãn lỗi | Tinh chỉnh ngưỡng xác suất kích hoạt riêng cho từng nhãn trong 10 nhãn taxonomy (hạ ngưỡng cho nhãn hiếm như `hard-code`, `style`; nâng ngưỡng cho nhãn `logic`). Sản phẩm: Bộ trọng số ngưỡng tối ưu `optimal_thresholds.json`, tăng vọt Macro-F1. | Phần 8: Kỹ thuật Hậu xử lý & Tối ưu Metric | Ngày 3 - Tuần 6 | **Trang** |
| 19 | 3.5 Tối ưu hóa Metric Task 3: Regex Filter chống lộ code | Viết bộ lọc tự động rà soát output tiếng Việt của Task 3: nếu yêu cầu Level 1 hoặc Level 2 mà phát hiện thẻ code hoặc cú pháp C++, tự động gọt bỏ code. Sản phẩm: Bộ lọc `pedagogical_guard.py`, đảm bảo tỷ lệ Level Compliance đạt 100%. | Phần 8: Kỹ thuật Hậu xử lý & Tối ưu Metric | Ngày 5 - Tuần 6 | **Dũng** |
| 20 | 3.6 Xây dựng Pipeline suy luận tự động & Test tính tất định | Script `run_inference.py` cấu hình Greedy Decoding (`temperature=0.0`, `do_sample=False`) đảm bảo cùng 1 bài luôn ra đúng 1 điểm duy nhất (độ lệch chuẩn $\sigma=0$); chạy tự động 100%. Sản phẩm: Script suy luận kèm Unit test chứng minh kết quả lặp lại 100%. | Phần 5: Hạ tầng MLOps | Ngày 6 - Tuần 6 | **Tiến** |
| 21 | 3.7 Nộp tối ưu Public Leaderboard liên tục | Khai thác tối đa hạn ngạch 2 lượt nộp/ngày trên Public Leaderboard để theo dõi thứ hạng thực tế của mô hình sau khi tối ưu các kỹ thuật hậu xử lý. Sản phẩm: Bảng ghi nhận thứ hạng Public Leaderboard qua các ngày và phân tích biến thiên điểm. | Phần 7: Đánh giá & Nộp bài Leaderboard | Ngày 7 - Tuần 6 | **Tiến** |
| 22 | 4.1 Phân tích lỗi sai chuyên sâu (Error Analysis) | Lọc các mẫu bài nộp bị dự đoán lệch nhiều nhất: phân tích tại sao mô hình sai ở các bài con trỏ phức tạp, danh sách liên kết vòng hoặc lỗi đệ quy không dừng. Sản phẩm: Báo cáo phân tích lỗi chi tiết kèm ví dụ trực quan từng case study để đưa vào báo cáo. | Phần 9: Phân tích Lỗi (Error Analysis) | Ngày 2 - Tuần 7 | **Dũng** |
| 23 | 4.2 Thu thập bằng chứng bất cập 1: Lệch chuẩn MSVC vs g++ | Đo đạc thống kê số bài `compiles_locally = false` (do dùng `void main`, thiếu `#include <cmath>`) nhưng giáo viên vẫn chấm `compilable = 1`; tính độ lệch chuẩn. Sản phẩm: Bảng số liệu định lượng, log biên dịch g++ đối chiếu cột điểm giảng viên. | Phần 10: Khai thác Bất cập Dữ liệu (+10% Bonus) | Ngày 3 - Tuần 7 | **Dũng** |
| 24 | 4.3 Thu thập bằng chứng bất cập 2 & 3: Nhiễu nhãn & Phân rã lỗi | Thống kê số trường hợp giáo viên chấm vớt điểm $P_2$ dù $P_1$ sai; phân tích hiện tượng nhãn `Lỗi logic` lấn át làm lu mờ các nhãn cụ thể khác. Sản phẩm: Bằng chứng định lượng về mâu thuẫn nhãn (label noise) và ma trận suy biến nhãn. | Phần 10: Khai thác Bất cập Dữ liệu (+10% Bonus) | Ngày 5 - Tuần 7 | **Hưng** |
| 25 | 4.4 Đề xuất giải pháp kỹ thuật khắc phục bất cập | Soạn thảo giải pháp: Dual-compiler container (kiểm tra cả g++ và clang permissive) và Ma trận phạt phân cấp (Hierarchical Penalty Matrix) cho Task 2. Sản phẩm: Bản thảo mục "Phát hiện & Đề xuất khắc phục bất cập dữ liệu" (+10% điểm thưởng). | Phần 10: Khai thác Bất cập Dữ liệu (+10% Bonus) | Ngày 6 - Tuần 7 | **Nam** |
| 26 | 4.5 Đóng băng Checkpoint & Đo đạc phần cứng chính thức | Chọn checkpoint có điểm dev cao nhất; đo đạc và ghi nhận chính xác: VRAM sử dụng (GB), thời gian suy luận (giây/mẫu), dung lượng model và cấu hình GPU. Sản phẩm: File cấu hình `hardware_profile.json` và log thông số GPU phục vụ báo cáo. | Phần 5: Hạ tầng MLOps | Ngày 7 - Tuần 7 | **Tiến** |
| 27 | 5.1 Đóng gói Repository chuẩn mực theo quy chế | Chuẩn hóa mã nguồn, bổ sung docstrings/comments, viết `README.md` hướng dẫn cài đặt và tạo script chạy 1 lệnh duy nhất (`bash run_all.sh` / `run.bat`). Sản phẩm: Repository GitHub hoàn thiện, script tái lập kết quả tự động 100%. | Phần 11: Đóng gói Sản phẩm & Báo cáo | Ngày 2 - Tuần 8 | **Tiến** |
| 28 | 5.2 Xây dựng Model Card cho hệ thống cuối cùng | Soạn thảo Model Card chuẩn mực: thông tin kiến trúc `Qwen2.5-Coder-7B-Instruct`, dữ liệu huấn luyện, giới hạn kỹ thuật và cảnh báo rủi ro khi chấm điểm thật. Sản phẩm: File `MODEL_CARD.md` đính kèm trong repository. | Phần 11: Đóng gói Sản phẩm & Báo cáo | Ngày 3 - Tuần 8 | **Nam** |
| 29 | 5.3 Soạn thảo Báo cáo khoa học 10–15 trang | Viết báo cáo khoa học theo barem: Mô tả bài toán & EDA, So sánh 2 Hướng tiếp cận, Bảng Ablation Study, Phân tích lỗi, Chi phí & Khả năng triển khai, Hạn chế. Sản phẩm: File báo cáo PDF/Word 10–15 trang đạt chuẩn học thuật môn học. | Phần 11: Đóng gói Sản phẩm & Báo cáo | Ngày 5 - Tuần 8 | **Cả nhóm (Dũng chủ trì)** |
| 30 | 5.4 Chạy suy luận trên tập Test riêng tư | Khi nhận tập Private Test từ ban tổ chức: nạp mô hình đã đóng băng, chạy script tự động xuất ra file `predictions.json` cuối cùng và kiểm tra MD5 checksum. Sản phẩm: File `predictions.json` nộp Private Leaderboard (quyết định 30% điểm số). | Phần 7: Đánh giá & Nộp bài Leaderboard | Ngày 6 - Tuần 8 | **Tiến** |
| 31 | 5.5 Thiết kế Slide thuyết trình chuyên nghiệp | Thiết kế bộ slide báo cáo súc tích, trực quan gồm: Kiến trúc mô hình Unified, Kết quả đối đầu Ablation, Case study bắt lỗi code C++, Bất cập dữ liệu (+10%). Sản phẩm: File Slide PowerPoint / PDF (15 phút trình bày + 10 phút Q&A). | Phần 12: Trình bày & Bảo vệ Đồ án | Ngày 6 - Tuần 8 | **Trang** |
| 32 | 5.6 Tập dượt thuyết trình & Q&A phản biện | Cả nhóm họp tổng duyệt thuyết trình đúng 15 phút; phân công người trả lời các câu hỏi hóc búa của hội đồng về phần cứng, chi phí, lý do chọn mô hình Unified. Sản phẩm: Buổi tập dượt hoàn tất, sẵn sàng cho buổi báo cáo chính thức. | Phần 12: Trình bày & Bảo vệ Đồ án | Ngày 7 - Tuần 8 | **Cả nhóm (Tiến điều phối)** |

## 3. CHECKLIST TOÀN DIỆN CÁC YÊU CẦU ĐỒ ÁN CẦN ĐÁP ỨNG (PROJECT COMPLIANCE CHECKLIST)

Bảng đối chiếu toàn bộ các yêu cầu bắt buộc trích xuất từ tài liệu đặc tả đồ án [DoAn-LLM-Challenge.docx.md](file:///c:/Users/daniel.dinh/Desktop/Learning/LLM/DoAn-LLM-Challenge.docx.md), phân loại theo từng nhóm tiêu chí kỹ thuật, nghiệp vụ và quy chế:

### 3.1. Nhóm Yêu cầu Quy chế & Tổ chức Đội ngũ

| STT | Yêu cầu đồ án | Tiêu chí nghiệm thu cụ thể | Trạng thái |
| :---: | :--- | :--- | :---: |
| 1 | Quy mô nhóm thực hiện | Đội ngũ từ 5 đến 7 học viên cao học. | [x] Đạt (5 thành viên) |
| 2 | Thời lượng thực hiện | Dự án hoàn thành trong đúng 8 tuần theo kế hoạch. | [x] Đạt (Master Plan 8 tuần) |
| 3 | Bảng đóng góp thành viên | Nộp kèm bảng phân bổ công việc có tỷ lệ phần trăm và sự xác nhận cam kết của cả 5 thành viên. | [x] Đạt (Mục 5 tài liệu này) |
| 4 | Liêm chính học thuật & Bảo mật | Dữ liệu C++ là bài làm thật của sinh viên: tuyệt đối không phát tán ra ngoài, không đưa lên GitHub public, không gán nhãn thủ công tập test, không chia sẻ code/kết quả giữa các nhóm. | [ ] Đang tuân thủ |
| 5 | Khai báo công cụ GenAI | Ghi rõ ở cuối báo cáo đã sử dụng công cụ AI nào cho mục đích gì. | [ ] Đã đưa vào dàn ý báo cáo |

### 3.2. Nhóm Yêu cầu Nghiệp vụ cho 3 Task & Ràng buộc Dữ liệu

| STT | Yêu cầu đồ án | Tiêu chí nghiệm thu cụ thể | Trạng thái |
| :---: | :--- | :--- | :---: |
| 6 | Cấu trúc dữ liệu đầu vào | Mã nguồn đọc từ `submissions/<mã đề>/<mã đề>-<mã SV>.cpp`, file JSON chỉ tham chiếu đường dẫn qua `code_file`, không chứa code trực tiếp. | [ ] Đã thiết kế parser |
| 7 | Xử lý 2 loại đề thi | Phân biệt rõ `multi_problem` (nhiều câu, ràng buộc tiên quyết, tín hiệu `compile_log`) và `single_problem` (1 câu, stdin/stdout, tín hiệu `compile_log` + `test_report`). | [ ] Đã đưa vào pipeline |
| 8 | Task 1: Chấm điểm Rubric 6 chiều | Dự đoán đúng 6 chiều: `compilable` (0-1), `io_format` (0-1), `logic` (0-4), `edge_case` (0-2), `complexity` (0-1), `code_quality` (0-1) và tổng `total_score` (0-10). Metric chính: QWK. | [ ] Đã xây dựng Evaluator |
| 9 | Task 1: Chính sách chấm câu tiên quyết | Với đề nhiều câu (`multi_problem`), nếu câu tiên quyết ($P_1$) sai/không biên dịch được thì toàn bộ các câu phụ thuộc phía sau ($P_2 \rightarrow P_4$) bắt buộc gán 0 điểm. | [ ] Đã lập trình Rule Engine |
| 10 | Task 2: Phân loại lỗi đa nhãn (Multi-label) | Phân loại chính xác trên 10 nhãn taxonomy lỗi. Trả về mảng rỗng nếu bài làm không có lỗi. Metric chính: Macro-F1 (do mất cân bằng dữ liệu nghiêm trọng). | [ ] Đã thiết lập Threshold Tuning |
| 11 | Task 3: Sinh phản hồi có kiểm soát mức độ | Sinh phản hồi bằng tiếng Việt bám sát chẩn đoán của giảng viên theo 4 cấp độ (Level 1: gợi ý nhẹ đến Level 4: giải mẫu). | [ ] Đã chuẩn bị ChatML Prompt |
| 12 | Task 3: Vi phạm Level Compliance (RẤT QUAN TRỌNG) | Tuyệt đối KHÔNG đưa code C++ sửa hoặc lời giải mẫu ở Level 1 và Level 2. Nếu vi phạm sẽ bị đánh giá rớt hoặc phạt điểm rất nặng. | [ ] Đã có Pedagogical Guard |
| 13 | Quy tắc cấm rò rỉ dữ liệu (CẤM TUYỆT ĐỐI) | Tuyệt đối KHÔNG được dùng trường `feedback` làm input cho Task 1 và Task 2 dưới bất kỳ hình thức nào. | [x] Đã assert trong code |

### 3.3. Nhóm Yêu cầu Kỹ thuật Mô hình & MLOps

| STT | Yêu cầu đồ án | Tiêu chí nghiệm thu cụ thể | Trạng thái |
| :---: | :--- | :--- | :---: |
| 14 | Tối thiểu 2 hướng tiếp cận đối đầu | Phải triển khai và so sánh: (1) Ít nhất một hướng Prompting trên LLM; (2) Ít nhất một mô hình open-weight fine-tuned ($\le 10\text{B}$). | [x] Đã xác định 2 hướng |
| 15 | Khả năng chạy cục bộ & Báo cáo phần cứng | Mô hình fine-tuned chạy được cục bộ (hoặc Colab cá nhân) và ghi nhận đầy đủ thông số: dung lượng GPU VRAM, tốc độ suy luận, CPU/RAM. | [ ] Đã có hardware profiler |
| 16 | Minh bạch chi phí API | Nếu sử dụng API thương mại (OpenAI, Anthropic, Google) ở nhánh Prompting, phải thống kê và báo cáo chi tiết tổng chi phí phát sinh. | [ ] Đã lập bảng log chi phí |
| 17 | Tự động hóa Pipeline 100% | Toàn bộ quy trình suy luận từ nhận file đầu vào đến sinh file `predictions.json` phải chạy hoàn toàn tự động qua dòng lệnh, không có sự can thiệp thủ công của con người. | [ ] Đã lên khung `run_all.sh` |
| 18 | Tính tất định & Khả năng tái lập | Cố định `seed = 42`, cấu hình Greedy Decoding (`temperature = 0.0`), khóa cứng phiên bản thư viện. Kết quả cùng bài test phải ra đúng một đáp số duy nhất ($\sigma = 0$). | [ ] Đã cố định seed và config |

### 3.4. Nhóm Yêu cầu Nộp bài Leaderboard

| STT | Yêu cầu đồ án | Tiêu chí nghiệm thu cụ thể | Trạng thái |
| :---: | :--- | :--- | :---: |
| 19 | Định dạng nộp bài `predictions.json` | Mỗi phần tử gồm `sample_id` và trường output tương ứng cho từng task. Bắt buộc kiểm tra qua script validate trước khi nộp để không bị từ chối bài. | [ ] Đã tích hợp validate script |
| 20 | Tối ưu Public Leaderboard (Tập Dev) | Tận dụng tối đa quota 2 lượt nộp/ngày/nhóm để kiểm nghiệm mô hình liên tục trên cả 3 bảng xếp hạng riêng và bảng xếp hạng tổng hợp. | [ ] Đã lên lịch nộp bài |
| 21 | Chinh phục Private Leaderboard (Tập Test) | Nộp kết quả suy luận của mô hình tốt nhất trên tập Test riêng tư vào cuối kỳ (chiếm 30% tổng điểm đồ án). | [ ] Lên kế hoạch Tuần 8 |

### 3.5. Nhóm Yêu cầu Sản phẩm Bàn giao & Bảo vệ Cuối kỳ

| STT | Yêu cầu đồ án | Tiêu chí nghiệm thu cụ thể | Trạng thái |
| :---: | :--- | :--- | :---: |
| 22 | Sản phẩm 1: Mã nguồn (Repository) | Mã nguồn sạch sẽ, docstrings đầy đủ, có `README.md` hướng dẫn chi tiết và script chạy tái lập kết quả bằng đúng một lệnh duy nhất (`run_all.sh` / `run.bat`). | [ ] Tuần 8 |
| 23 | Sản phẩm 2: Báo cáo Khoa học (10–15 trang) | Báo cáo đầy đủ 6 phần: EDA dữ liệu, So sánh 2 hướng tiếp cận, Bảng Ablation Study, Phân tích lỗi cụ thể, Chi phí & Khả năng triển khai, Hạn chế của hệ thống. | [ ] Tuần 8 |
| 24 | Sản phẩm 3: Model Card | File `MODEL_CARD.md` tóm tắt kiến trúc, tập dữ liệu huấn luyện, giới hạn kỹ thuật và rủi ro đạo đức/sư phạm khi triển khai thực tế. | [ ] Tuần 8 |
| 25 | Sản phẩm 4: Slide & Thuyết trình | Bộ slide súc tích; hoàn thành phần trình bày 15 phút và trả lời chất vấn phản biện 10 phút trước hội đồng. | [ ] Tuần 8 |
| 26 | Sản phẩm 5: File nộp bài cuối cùng | File `predictions.json` cho tập test riêng tư kèm mã băm MD5 checksum xác thực. | [ ] Tuần 8 |
| 27 | Mục tiêu Điểm thưởng (+10% Bonus) | Chỉ ra ít nhất 1 vấn đề thật trong dữ liệu hoặc bộ metric (Lệch chuẩn compiler MSVC vs g++, nhiễu nhãn giảng viên) kèm bằng chứng định lượng và đề xuất giải pháp kỹ thuật. | [ ] Đã có kế hoạch Tuần 7 |

## 4. CHECKLIST KIỂM SOÁT RỦI RO & ĐIỀU KIỆN TIÊN QUYẾT (RISK MANAGEMENT)

Để tránh các lỗi nghiêm trọng bị trừ điểm hoặc bị từ chối bài nộp, nhóm thiết lập bảng kiểm soát rủi ro như sau:

| Rủi ro kỹ thuật | Mức độ | Biện pháp phòng ngừa & Xử lý sự cố | Phụ trách |
| :--- | :---: | :--- | :---: |
| **Mô hình chấm lệch điểm giữa các lần chạy (Không nhất quán)** | Nghiêm trọng (Mất tính công bằng) | Bắt buộc cấu hình chế độ Greedy Decoding (`do_sample=False`, `temperature=0.0`), cố định random seed CUDA, chạy test lặp lại 3 lần trên cùng 1 bài test để chứng minh kết quả giống nhau $100\%$ ($\sigma = 0$). | Trang |
| **Tràn bộ nhớ GPU (Out-Of-Memory - OOM)** | Cao | Sử dụng Unsloth QLoRA 4-bit, giới hạn `max_seq_length = 2048`, giữ `per_device_train_batch_size = 1` và tăng `gradient_accumulation_steps = 4`. | Nam |
| **Rò rỉ dữ liệu (Data Leakage) ở Task 1 & 2** | Nghiêm trọng (Bị 0 điểm) | Tạo hàm kiểm tra tự động assert: nếu trường `feedback` xuất hiện trong input prompt của Task 1 hoặc Task 2 thì dừng chương trình ngay lập tức. | Hưng |
| **Mô hình sinh lỗi định dạng JSON** | Cao (Bị hủy bài nộp) | Luôn bọc hàm `extract_json()` với regex bắt khối `{...}`; nếu parse JSON thất bại thì fallback về giá trị trung bình an toàn của tập train. | Tiến |
| **Vi phạm cấp độ phản hồi (Level Compliance)** | Trung bình | Cài đặt bộ lọc Regex: tự động cắt bỏ bất kỳ đoạn code C++ nào trong output nếu `target_feedback_level` là Level 1 hoặc Level 2. | Dũng |
| **Mất kết nối Colab khi đang huấn luyện** | Trung bình | Tự động lưu checkpoint LoRA adapter sau mỗi 50 steps lên Google Drive gắn kèm (`/content/drive/MyDrive/...`). | Tiến |
| **Kết quả không tái lập được** | Nghiêm trọng | Cố định `seed = 42` trên toàn bộ các thư viện (`torch`, `numpy`, `random`, `transformers`) và ghi rõ hash commit Git. | Nam |

## 5. MA TRẬN PHÂN BỔ TRỌNG SỐ ĐÓNG GÓP THÀNH VIÊN (CONTRIBUTION MATRIX)

Theo quy chế đồ án (mỗi nhóm nộp kèm bảng đóng góp có xác nhận cam kết của cả nhóm):

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        BẢNG ĐÓNG GÓP DỰ KIẾN CỦA CÁC THÀNH VIÊN                        │
├─────────────┬───────────────────────────┬───────────────────────────────┬──────────────┤
│ Thành viên  │ Phụ trách chính           │ Module bàn giao chính         │ Tỷ lệ cam kết│
├─────────────┼───────────────────────────┼───────────────────────────────┼──────────────┤
│ **Tiến**    │ MLOps, Hạ tầng & Nộp bài  │ Script tự động, Repo, Nộp bài │ 20%          │
│ **Hưng**    │ Data Pipeline & ChatML    │ Dữ liệu train, Chống leak nhãn│ 20%          │
│ **Nam**     │ Fine-Tuning QLoRA Model   │ Checkpoint 7B Unified, Config │ 20%          │
│ **Trang**   │ Evaluator & Tối ưu Metric │ Metric local, QWK & Threshold │ 20%          │
│ **Dũng**    │ Prompting & Phân tích lỗi │ Nhánh Baseline, Bonus +10%    │ 20%          │
├─────────────┴───────────────────────────┴───────────────────────────────┼──────────────┤
│ TỔNG CỘNG                                                               │ 100%         │
└─────────────────────────────────────────────────────────────────────────┴──────────────┘
```

## 6. HƯỚNG DẪN BẮT ĐẦU NGAY (QUICK START DÀNH CHO NHÓM)

1. **Khởi tạo môi trường làm việc:**
   * Clone repo và kích hoạt môi trường Anaconda:
     ```bash
     conda activate base
     pip install unsloth "xformers<0.0.27" "trl<0.9.0" peft accelerate bitsandbytes
     ```
2. **Kiểm tra dữ liệu mẫu:**
   * Mở thư mục [sample_dataset](file:///c:/Users/daniel.dinh/Desktop/Learning/LLM/sample_dataset/sample_dataset) và chạy thử notebook EDA đầu tiên theo Đầu mục **1.4**.
3. **Theo dõi tiến độ:**
   * Cập nhật trạng thái từng đầu mục trong bảng trên vào mỗi buổi họp nhóm đầu tuần (Thứ 2) và cuối tuần (Thứ 6).
