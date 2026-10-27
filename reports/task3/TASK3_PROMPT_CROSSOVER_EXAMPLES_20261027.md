# Task3 — ví dụ ngắn prompt crossover

Quy tắc tất định: từ danh sách candidate đã đóng băng thuật toán trong analysis.json, lấy một case mỗi loại, ưu tiên family chưa dùng rồi sort ID; hai loại đúng↔sai chỉ dùng so sánh đổi prompt trên cùng adapter. Cross-input lấy cặp đầu tiên theo thứ tự comparison. Không chọn theo hướng có lợi. Feedback dưới đây là trích tối đa320 ký tự, dấu[…] chỉ phần lược trong báo cáo; raw/parsed nguyên vẹn và đề/source/verdict đầy đủ ở [casebook80×4](../../outputs/task3/prompt-crossover-20261027-run1/paired-casebook.html). Tất cả là agent review trên dev đã quan sát, không phải human gold độc lập.

## Cùng adapter: đúng→sai khi đổi prompt: F23-C-L2

**v2-old→v2-v3**, family `F23`. Đọc một dòng dài 0 đến 100 ký tự ASCII gồm chữ cái và dấu cách. In YES nếu dòng là palindrome, ngược lại NO. Phân biệt hoa thường và tính cả dấu cách.

**v2-old**: taxonomy `[]`; feedback:

> Bài làm đáp ứng đúng yêu cầu về kiểm tra chuỗi đối xứng trong đề.

**v2-v3**: taxonomy `["Lỗi logic"]`; feedback:

> Bài kiểm tra đảo chuỗi sai thứ tự của hai phần còn lại khi chỉ duyệt nửa chiều.

**Bằng chứng nguồn:** Code dùng getline để giữ dấu cách và duyệt i<size/2, kiểm tra mỗi cặp đối xứng đúng một lần. Không cần so sánh ký tự giữa của chuỗi lẻ. P_old đánh giá đúng; P_v3 bịa ra lỗi thứ tự trong một phép kiểm tra đúng. Verdict và lập luận review gốc nằm trong casebook.

## Cùng adapter: sai→đúng khi đổi prompt: F29-C-L3

**v3-old→v3-v3**, family `F29`. Đọc n trong [1,100], rồi n số nguyên trong [-100,100]. In giá trị có tần suất lớn nhất; nếu hòa, chọn giá trị nhỏ nhất.

**v3-old**: taxonomy `[]`; feedback:

> Biến count khởi tạo bằng -1 nên mỗi lần xuất hiện đầu tiên của một giá trị đều được chọn làm giá trị có tần suất lớn nhất.

**v3-v3**: taxonomy `[]`; feedback:

> Bài làm đáp ứng yêu cầu của đề. Mỗi phần tử xuất hiện ít nhất một lần nên bộ đếm không rỗng. Em hãy giữ nguyên cấu trúc duyệt để ưu tiên giá trị nhỏ hơn khi hai tần suất bằng nhau.

**Bằng chứng nguồn:** map duyệt key tăng dần; chỉ cập nhật khi tần suất lớn hơn nên giữ key nhỏ nhất khi hòa. count=-1 là giá trị khởi tạo hợp lệ vì n>=1 và mọi tần suất ít nhất bằng1. Nhận xét ban đầu suy diễn sai từ biến khởi tạo; nhận xét sau xác nhận đúng cơ chế đang có. Verdict và lập luận review gốc nằm trong casebook.

## Hướng sửa L3 thay đổi: F32-D2-L3

**v2-old→v2-v3**, family `F32`. Đọc n trong [0,100], rồi n số nguyên trong [-100,100]. In các số âm trước, sau đó các số không âm; giữ nguyên thứ tự tương đối trong mỗi nhóm.

**v2-old**: taxonomy `["Lỗi logic"]`; feedback:

> Bài làm còn có lỗi cần sửa. Vị trí xuất phần tử không âm nằm sau phần tử âm nên các số không âm đã được sắp xếp theo thứ tự tăng dần. Để giữ nguyên thứ tự tương đối giữa hai nhóm, hãy chuyển đoạn xuất số không âm sang đầu đoạn xuất số âm.

**v2-v3**: taxonomy `["Lỗi logic"]`; feedback:

> Bài làm còn có lỗi về sắp xếp nên chưa đáp ứng yêu cầu của đề. Cần giữ thứ tự trong từng nhóm khi xuất.

**Bằng chứng nguồn:** sort làm mất thứ tự tương đối trong từng nhóm trước khi xuất. Chuyển nhóm không âm lên đầu còn vi phạm thứ tự hai nhóm và không sửa việc sort. Hướng sửa sau yêu cầu giữ thứ tự trong từng nhóm, đúng trọng tâm và phù hợp L3. Verdict và lập luận review gốc nằm trong casebook.

## Taxonomy–feedback mâu thuẫn: F23-C-L2

**v3-old→v3-v3**, family `F23`. Đọc một dòng dài 0 đến 100 ký tự ASCII gồm chữ cái và dấu cách. In YES nếu dòng là palindrome, ngược lại NO. Phân biệt hoa thường và tính cả dấu cách.

**v3-old**: taxonomy `[]`; feedback:

> Vòng kiểm tra đảo chỉ soạn nửa chuỗi nên bỏ sót cặp ký tự đối xứng.

**v3-v3**: taxonomy `[]`; feedback:

> Bài làm đáp ứng đúng yêu cầu về kiểm tra chuỗi palindrome trong đề.

**Bằng chứng nguồn:** Taxonomy rỗng nhưng feedback của v3-old lại khẳng định có cặp đối xứng bị bỏ sót: payload tự mâu thuẫn. Code thực tế kiểm tra đủ mọi cặp. v3-v3 thống nhất taxonomy rỗng với đánh giá clean có căn cứ. Verdict và lập luận review gốc nằm trong casebook.

## Prompt khác nhưng output không đổi: F23-C-L1

**v3-old→v3-v3**, family `F23`. Đọc một dòng dài 0 đến 100 ký tự ASCII gồm chữ cái và dấu cách. In YES nếu dòng là palindrome, ngược lại NO. Phân biệt hoa thường và tính cả dấu cách.

**v3-old**: taxonomy `[]`; feedback:

> Bài làm đáp ứng yêu cầu của đề.

**v3-v3**: taxonomy `[]`; feedback:

> Bài làm đáp ứng yêu cầu của đề.

**Bằng chứng nguồn:** Hai payload trùng nhau và đánh giá đúng source clean. Cả hai giữ giới hạn L1 chỉ nêu trạng thái; prompt khác không tạo thay đổi có ý nghĩa ở target này. Verdict và lập luận review gốc nằm trong casebook.

## Tendency false alarm giảm nhưng miss tăng trên input khác nhau

**v2-v3→v3-v3**. Đây là hai source khác nhau; không phải một source sạch biến thành lỗi. Nonempty taxonomy ban đầu cũng không tự chứng minh chẩn đoán đúng.

**clean_example_id: F23-C-L2**

v2-v3: `{"taxonomy_error": ["Lỗi logic"], "feedback": "Bài kiểm tra đảo chuỗi sai thứ tự của hai phần còn lại khi chỉ duyệt nửa chiều."}`

v3-v3: `{"taxonomy_error": [], "feedback": "Bài làm đáp ứng đúng yêu cầu về kiểm tra chuỗi palindrome trong đề."}`

**faulty_example_id: F29-D1-L2**

v2-v3: `{"taxonomy_error": ["Lỗi logic"], "feedback": "Bài làm còn có lỗi về tính chất của giá trị xuất hiện nhiều nhất."}`

v3-v3: `{"taxonomy_error": [], "feedback": "Bài làm đáp ứng đúng yêu cầu về tần suất xuất hiện của dãy số trong đề."}`

**Cơ chế:** F23-C là phép kiểm tra palindrome đúng. F29-D1 duyệt map tăng dần nhưng dùng p.second>=count, nên khi hòa lại chọn key lớn hơn. V3 sửa false alarm ở source clean đồng thời khen sai source lỗi này; feedback v2 trên source lỗi cũng quá chung để tự chứng minh chẩn đoán đúng.

Danh sách candidate ở cả bốn comparison, các hướng thay đổi khác và nguồn đầy đủ: [selected-examples-expanded.md](../../outputs/task3/prompt-crossover-20261027-run1/selected-examples-expanded.md). Không sửa output hoặc chọn checkpoint từ các ví dụ này.
