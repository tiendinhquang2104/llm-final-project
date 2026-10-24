# Đánh giá và bản sửa Task 3 D+ — 24/10/2026

Bản sửa nằm trên worktree/branch riêng `fix/task3-strict-feedback`, dựa trên D+ `584efe9cc11772fb3d3b1012abe9acd8036a8f55`. Chưa push thay đổi lên GitHub. Link được gửi, `feat/task3-quality-round5`, trỏ tới `26a9d9b10c32e8daf95d8ef29dc76af61332bda0` lúc kiểm tra; code D+ mới nằm trên `task3/arm-d-plus`.

## Kết luận có bằng chứng

Pipeline cũ chưa kiểm soát đủ chất lượng dù enum đã hợp lệ. Log chạy cũ xác nhận actual BF16, không 4-bit; không có bằng chứng rằng lỗi chính là chọn nhầm precision. Điểm yếu quan sát được nằm ở chẩn đoán, bằng chứng và mức tiết lộ của feedback. Prompt, parser và dữ liệu đi vào renderer cần nhất quán với nhau.

Audit offline trên bundle v1.3 (không gọi model, không sửa predictions):

| Quan sát | Kết quả | Ý nghĩa |
|---|---:|---|
| Hoàn thành | 326/328 | Chưa đủ để nộp một file đầy đủ |
| Finding sao chép mô tả schema | 21 finding / 19 bài | Chuỗi không rỗng đã bị coi là chẩn đoán hợp lệ |
| Evidence không phải trích dẫn nguyên văn | 168 finding / 114 bài | Sau chuẩn hóa CRLF/LF; chưa đồng nghĩa toàn bộ chẩn đoán sai |
| Evidence rỗng | 10 finding | Omission có thể hợp lệ; không thể bắt mọi finding có quote |
| Response JSON hỏng trong journal | 5 response | Đếm cả lần đầu và retry, không phải 5 bài thất bại |
| Retry trả lại nguyên response cũ | 2 | Chỉ yêu cầu chung chung “sửa JSON” chưa hiệu quả |
| Bài cũ bị contract mới từ chối | 126 | Có giao nhau giữa placeholder và quote; không phải dự đoán tỷ lệ fail của lượt chạy mới |
| Renderer Level 1 trong lượt cũ | 115 calls | 162.949 input + 5.989 output token cho bước này |

Con số kiểm tra thô trước chuẩn hóa xuống dòng là 174 quote / 120 bài. Sáu trường hợp chỉ khác CRLF/LF được chấp nhận bởi bản sửa, nên số cuối là 168 / 114.

## Các trường và flow đã rà soát

| Bước | Dữ liệu và kiểm soát |
|---|---|
| Loader → detector | Giữ statement, code, problems/prototype, constraints, I/O, language, restrictions, prerequisites, compile_log, test_report và metadata được cho phép. Loại gold/teacher annotations. Giữ code/log đầy đủ, bỏ bản sao log trùng. |
| Requested Level | Lấy từ input thật; không suy từ sample ID. Detector không được biết Level để tránh chẩn đoán thay đổi theo mức feedback. |
| Findings | Năm trường: problem_id, location, evidence, error, labels. Parser còn hỗ trợ label số ít cho tương thích; prompt chỉ yêu cầu labels dạng mảng. |
| Contract → resolver | Kiểm tra cấu trúc, placeholder đã biết, problem_id thuộc bài, quote không rỗng phải khớp nguồn. Sau đó chuẩn hóa/alias/resolve vào đúng mười nhãn; không dùng nhãn để hợp thức hóa chẩn đoán sai. |
| Renderer Level 1 | Chỉ trạng thái có/không có finding; xuất template tiếng Việt, không gọi LLM, không lộ vị trí/nguyên nhân/cách sửa. |
| Renderer Level 2 | Chỉ findings, taxonomy và quy định Level; không lặp lại toàn bộ code/đề/log. Prompt phân biệt rõ “vì sao sai” với “phải sửa gì”. |
| Renderer Level 3–4 | Giữ findings và context đầy đủ để hướng sửa không vi phạm yêu cầu. Không cho phép tự phát hiện thêm lỗi. |
| Export | Chỉ tạo predictions.json khi đủ đúng ID và schema, nhãn chính thức, feedback không rỗng. Unresolved vẫn được ghi rõ, không điền bằng kết quả cũ. |

## Những thay đổi đã thực hiện

- Viết lại prompt tiếng Anh với kiểm tra yêu cầu → hành vi thực tế → điều kiện vi phạm; rà declaration/initialization, storage duration, bounds, compiler warning/error, token output và domain. Không còn object ví dụ chứa diagnosis placeholder dễ bị sao chép.
- Kiểm tra contract trước renderer. Không xóa finding không hợp lệ rồi giả thành bài không lỗi. Quote chỉ được chuẩn hóa khác biệt CRLF/LF, không tự viết lại code. Quote rỗng vẫn được phép cho omission để tránh lặp lỗi schema của v1.1/v1.2.
- Retry nhận loại lỗi, lỗi parser, vùng ký tự lỗi và raw response dưới dạng dữ liệu. Không nhét response hỏng vào vai assistant. Tối đa một lần sửa; lỗi chưa sửa được vẫn unresolved. Đây chưa phải constrained JSON decoding và chưa chứng minh sửa thành công hai ca cũ bằng model thật.
- Level 1 dùng hai câu giới hạn cố định; Level 2 giảm context; Level 3–4 giữ context cần sửa. Taxonomy vẫn do detector/resolver quyết định, không bị template thay đổi.
- Nâng method/config thành `arm-d-plus-v1.4-strict`; freeze/hash gồm prompt sửa lỗi và template. Resume khác method bị từ chối. Kiểm tra lại contract khi đọc checkpoint đã hoàn thành.
- Thêm audit offline và tài liệu prompt/chạy lại. Report runtime ghi số renderer theo chế độ, không tiếp tục nói mọi Level đều sinh feedback bằng LLM.

Ví dụ Level 1 dưới đây là output thật của renderer xác định bằng code, **không phải Qwen vừa sinh**:

- Có finding: “Bài làm của em còn có điểm chưa đáp ứng yêu cầu.”
- Không có finding: “Trong phần mã đã xem, chưa phát hiện vấn đề có đủ căn cứ để góp ý.”

## Kiểm chứng và giới hạn

182 test liên quan pass: parser, label mapping, constrained logits với Torch thật trên CPU, retry, failure handling, resume, input metadata, Level routing, public contract và submission validation. 14 test mới cho các thiếu sót cốt lõi đã chạy thất bại trên code cũ trước khi sửa; test audit offline cũng được bổ sung. Lệnh đầy đủ ở `task3-strict-codex-run.md`. `git diff --check` sạch.

Môi trường kiểm tra có Torch 2.8.0+cpu, CUDA unavailable, GPU count0. Chưa chạy lại Qwen BF16, chưa đo F1 mới, chưa có predictions.json mới hay bằng chứng semantic quality tăng. Chưa chạy preflight bằng tokenizer Qwen thật ở đây.

Contract mới cứng hơn có thể làm tăng retry/unresolved nếu model vẫn tạo quote sai. Cần chạy internal30 trước, đo tỷ lệ đó và xem raw; không bỏ gate chỉ để có số completed đẹp. Một quote khớp code không chứng minh cách hiểu code đúng; placeholder blacklist cũng không nhận diện được mọi câu vô nghĩa. Level 2–4 vẫn cần review nội dung/ngôn ngữ. L1 có template loại bỏ việc tiết lộ chi tiết, nhưng trạng thái có lỗi vẫn phụ thuộc chất lượng detector.

Không nên tiếp tục đổi precision hoặc thêm hàng loạt prompt từ cảm giác. Bước kế tiếp là chạy đúng bản sửa đã đóng băng trên internal30, kiểm tra các lỗi có bằng chứng, rồi chạy một lượt public đầy đủ theo hướng dẫn. Chỉ kết luận cải thiện khi số đo và ví dụ mới hỗ trợ kết luận đó.
