**ĐỒ ÁN MÔN HỌC**

**LARGE LANGUAGE MODEL**

*Challenge: Chấm điểm và phản hồi tự động cho bài lập trình của sinh viên*

| Đối tượng | Học viên cao học — lớp Large Language Model |
| :---- | :---- |
| **Hình thức** | Đồ án nhóm, 5–7 học viên/nhóm |
| **Thời lượng** | 8 tuần |
| **Đánh giá** | Có bảng xếp hạng (leaderboard) cập nhật liên tục trong suốt đồ án |

# **1\. Bối cảnh**

Mỗi học kỳ, giảng viên các môn lập trình nhập môn phải chấm hàng nghìn bài nộp: vừa cho điểm theo rubric, vừa chỉ ra sinh viên sai ở đâu, vừa viết phản hồi sao cho sinh viên học được chứ không phải chỉ chép đáp án. Đây là công việc tốn thời gian nhất và cũng là nơi chất lượng dao động nhiều nhất vì cùng một bài, hai giảng viên có thể chấm lệch nhau.

Đồ án này yêu cầu các nhóm xây dựng hệ thống dựa trên LLM để hỗ trợ công việc đó, trên dữ liệu chấm điểm của hai môn Cấu trúc dữ liệu & Giải thuật và Cơ sở lập trình. Dữ liệu có đầy đủ những vấn đề của dữ liệu thực tế: nhãn mất cân bằng, phân bố điểm không đều, và một số nhãn gần như suy biến. Việc phát hiện và xử lý những vấn đề này là một phần thách thức của đồ án.

# **2\. Dữ liệu: [https\://drive.google.com/file/d/1iqkw6ZWUV6-I6rsVQdqHBOhiRgRkk\_UZ/view?usp=sharing](https://drive.google.com/file/d/1iqkw6ZWUV6-I6rsVQdqHBOhiRgRkk_UZ/view?usp=sharing)**

Bài nộp là mã nguồn C++ của sinh viên, đã được ẩn danh (MSSV, họ tên, mã lớp đều đã thay thế). Mỗi bài nộp có nhãn do giảng viên chấm gồm ba phần:

* **Rubric 6 chiều:** compilable (0–1), io\_format (0–1), logic (0–4), edge\_case (0–2), complexity (0–1), code\_quality (0–1) — tổng (0–10).

* **Taxonomy lỗi:** đa nhãn (multi-label) trên 10 nhãn (Lỗi biên dịch, Lỗi logic, Lỗi vòng lặp, Lỗi hàm, …).

* **Phản hồi tiếng Việt** kèm mức phản hồi từ Level 1 (gợi ý nhẹ) đến Level 4 (lời giải mẫu).

Có hai loại đề (dùng chung một rubric):

|  | multi\_problem | single\_problem |
| :---- | :---- | :---- |
| **Cấu trúc** | Nhiều câu trong một file nộp, trọng số khác nhau | Một câu, stdin/stdout |
| **Đặc thù** | Có ràng buộc tiên quyết giữa các câu | Có testcase công khai |
| **Tín hiệu phụ** | compile\_log | compile\_log \+ test\_report |

**Lưu ý định dạng.** Mã nguồn nằm trong thư mục submissions/\<mã đề\>/\<mã đề\>-\<mã SV\>.cpp; file JSON chỉ tham chiếu qua trường code\_file, không chứa code.

# **3\. Ba task**

## **Task 1 \- Chấm điểm theo rubric**

| Input | Đề bài \+ code sinh viên (tuỳ chọn: compile\_log, test\_report) |
| :---- | :---- |
| **Output** | 6 điểm thành phần \+ tổng điểm 0–10 |
| **Metric** | QWK trên tổng điểm (chính) · MAE · exact-match từng chiều |

Với đề nhiều câu, hệ thống phải tôn trọng chính sách chấm của đề — ví dụ câu tiên quyết sai thì các câu sau không được tính điểm. Đây là một phần của bài toán, không phải chi tiết phụ.

## **Task 2 \- Phân loại lỗi đa nhãn**

| Input | Giống Task 1 |
| :---- | :---- |
| **Output** | Tập nhãn trong 10 nhãn taxonomy (rỗng là hợp lệ — bài không mắc lỗi nào) |
| **Metric** | macro-F1 (chính) · micro-F1 |

Macro-F1 được chọn làm metric chính vì phân bố nhãn rất lệch — một hệ thống chỉ đoán nhãn phổ biến sẽ bị phạt nặng.

## **Task 3 \- Sinh phản hồi có kiểm soát mức độ**

| Input | Đề \+ code \+ nhãn lỗi (cho sẵn) \+ mức phản hồi yêu cầu |
| :---- | :---- |
| **Output** | Đoạn phản hồi tiếng Việt |
| **Metric** | (a) Level compliance \- sinh ở Level 1/2 mà đưa code sửa hoặc lời giải là VI PHẠM;  (b) độ chính xác chẩn đoán so với phản hồi của giảng viên |

Đây là task khác biệt nhất so với các benchmark code-feedback quốc tế. Phần lớn benchmark chỉ đo “phản hồi có đúng không”; ở đây còn đo **tính sư phạm**: hệ thống có kiềm chế được việc nói cả đáp án khi giảng viên chỉ muốn gợi ý hay không. Một model viết phản hồi rất chính xác nhưng luôn kèm code sửa sẽ bị điểm thấp.

# **4\. Yêu cầu kỹ thuật**

Vì đây là môn Large Language Model, đồ án phải thể hiện được năng lực làm việc với LLM chứ không chỉ gọi API. Mỗi nhóm phải triển khai và so sánh **tối thiểu 2 hướng tiếp cận**, trong đó:

1. **Ít nhất một hướng prompting trên LLM**:  zero-shot, few-shot, chain-of-thought, self-consistency, RAG trên tập train, hoặc kết hợp.

2. **Ít nhất một mô hình open-weight được fine-tune** (khuyến nghị ≤ 10B). Nhóm phải chạy được mô hình này cục bộ và báo cáo cấu hình phần cứng.

Ngoài ra:

* Được dùng LLM thương mại qua API để huấn luyện, nhưng phải **báo cáo chi phí.** 

* Toàn bộ pipeline phải **chạy tự động**. Không được có người can thiệp vào từng bài lúc suy luận.

* Phải cố định seed và ghi rõ phiên bản model. Kết quả không tái lập được sẽ không được chấm.

* **Cấm dùng trường feedback làm input cho Task 1 và Task 2**

# **5\. Leaderboard**

**Ba bảng xếp hạng riêng** cho ba task, cộng một **bảng tổng** xếp theo trung bình thứ hạng.

* **Public leaderboard (giới hạn 2 lượt nộp/ngày/nhóm)** chạy trên tập dev, cập nhật ngay sau mỗi lần nộp. 

* **Private leaderboard** chạy trên tập test riêng tư, chỉ công bố ở buổi báo cáo cuối. Xếp hạng chính thức lấy theo bảng này.

Định dạng nộp là một file predictions.json, mỗi phần tử gồm sample\_id và trường output tương ứng với task. Script kiểm tra định dạng được phát kèm; file sai định dạng bị từ chối và vẫn tính vào quota.

# **6\. Đánh giá**

| Thành phần | Tỷ trọng |
| :---- | :---: |
| Thứ hạng private leaderboard (tính tương đối trong lớp) | 30% |
| Chất lượng phương pháp và tính hợp lý của thiết kế thí nghiệm | 25% |
| Ablation và phân tích lỗi | 15% |
| Báo cáo và trình bày | 20% |
| Khả năng tái lập và chất lượng mã nguồn | 10% |

**Điểm thưởng (tối đa \+10%)** cho nhóm chỉ ra được vấn đề thật trong chính bộ dữ liệu hoặc bộ metric, kèm bằng chứng định lượng và đề xuất khắc phục. Bộ dữ liệu này ***có*** những vấn đề như vậy — nhóm nào tìm ra và chứng minh được sẽ được ghi nhận. 

Mỗi nhóm nộp kèm **bảng đóng góp** ghi phần việc của từng thành viên, có xác nhận của cả nhóm. Điểm cá nhân có thể lệch khỏi điểm nhóm nếu đóng góp chênh lệch rõ rệt.

# **8\. Sản phẩm nộp**

1. **Repository** — mã nguồn, hướng dẫn cài đặt, script tái lập kết quả tốt nhất bằng một lệnh.

2. **Báo cáo 10–15 trang** gồm: mô tả dữ liệu và EDA, các hướng tiếp cận, bảng ablation, phân tích lỗi (nêu cụ thể hệ thống sai ở kiểu bài nào và vì sao), thảo luận về chi phí và khả năng triển khai thực tế, hạn chế.

3. **Model card** ngắn cho hệ thống cuối cùng: dữ liệu huấn luyện, giới hạn, rủi ro khi dùng để chấm điểm thật.

4. **Slide \+ trình bày 15 phút \+ hỏi đáp 10 phút.**

5. **File predictions.json** cho tập test riêng tư.

# **9\. Liêm chính học thuật và bảo mật dữ liệu**

* Dữ liệu là bài làm thật của sinh viên, đã ẩn danh. **Không được phát tán ra ngoài lớp học**, không đưa lên repository công khai, không dùng cho mục đích khác.

* **Không được gán nhãn thủ công cho tập test**, dù chỉ một phần. Không được tìm cách truy ngược danh tính sinh viên trong dữ liệu.

* Không chia sẻ mã nguồn hay dự đoán giữa các nhóm. Được thảo luận ý tưởng công khai trên diễn đàn lớp; khuyến khích điều đó.

* Được dùng LLM để hỗ trợ viết mã và viết báo cáo, nhưng phải ghi rõ ở cuối báo cáo là đã dùng công cụ nào cho việc gì.