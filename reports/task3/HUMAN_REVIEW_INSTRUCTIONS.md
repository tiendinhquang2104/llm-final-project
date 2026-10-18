# Hướng dẫn chấm human review Task 3

Worklist này chỉ chứa ID, Level, exam type và độ dài tổng hợp; nó không chứa source code, prompt, gold feedback hoặc dự đoán dạng văn bản. Reviewer được ủy quyền mở dữ liệu và các output tại máy cục bộ, không sao chép nội dung riêng tư vào notes, chat, cloud hoặc phiên bản worklist gửi đi.

Chấm E1 và E2 độc lập trước khi xem kết quả của reviewer còn lại:
- Diagnosis correctness: 0 = sai/không được bằng chứng hỗ trợ; 1 = một phần đúng hoặc thiếu trọng tâm; 2 = chẩn đoán cốt lõi chính xác, có bằng chứng.
- Evidence support: 0 = không có/có bịa; 1 = hỗ trợ một phần; 2 = gắn đúng bằng chứng trong bài/log.
- Level violation: yes nếu tiết lộ vượt mức yêu cầu (đặc biệt L1/L2); ghi violation type, không chép nội dung học sinh.
- Hallucinated error: yes nếu nêu lỗi không có trong bằng chứng.
- Level 1: chỉ đánh giá lời gợi ý/khen có phù hợp, không tiết lộ chẩn đoán.
- Level 2/3: so sánh độ cụ thể, khả năng định vị nguyên nhân và hướng sửa theo quy tắc Level.
- Level 4 heldout: xác minh tính đúng của lời giải độc lập; không coi pass heuristic là correctness.

Dùng các cột Reviewer 1/2 riêng. Không điền bằng AI. Sau khi hoàn tất, adjudicate bất đồng; chỉ tổng hợp diagnosis/evidence score, hallucination, Level violation, agreement và coverage khi có dữ liệu chấm thật.
