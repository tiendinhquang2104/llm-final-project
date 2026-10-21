# Task 3 — Retrospective offline replay v1 của SHORT (2026-10-21)

**Parser nhận fence đọc được 30/30 raw; chỉ 6/29 raw có finding khớp tọa độ quote, thêm 1 uncertain không có finding. Review nguồn: 4 cơ chế đúng nhưng sai tọa độ, 3 một phần, 22 sai và 1 abstention. Chỉ sửa parser/location chưa đủ căn cứ để tiếp tục thử feedback.** Không gọi model, train, tạo feedback hay đổi prediction/score gốc; giữ R15 production. Không public inference, submission, leaderboard hoặc push.

HEAD trước lượt này: `9ea830abd56f302d679d2867d6fc90395e509c8a`, branch `feat/task3-quality-round5`. Đúng 30 primary source/Level theo selection đã khóa của contract-v1: 24 defect, 6 scoped-clean; không chọn lại source. Đây là TRAIN development có prior exposure. Không đọc nội dung public, Evaluation v2 hoặc bundle24; các artifact cũ chỉ được hash khi kiểm bảo toàn.

## 1. Giao thức: đọc raw, không sửa prediction

Script mới chỉ import JSON/lexical helpers thuần của contract cũ; không import backend model. Mỗi raw phải khớp toàn bộ đúng một fence mở lowercase `json`, một fence đóng trên dòng riêng, ngoài fence chỉ có whitespace. Body phải là một JSON object đầy đủ; từ chối prose, nhiều fence/object, array, duplicate key và NaN. Không tìm một object con để cứu output.

Shape giữ đúng ba trường status/taxonomy/findings và các trường finding cũ, nhưng **replay hậu nghiệm** nhận location string hoặc object. Object chỉ nhận function/function_name và line/start_line/line_start/end_line/line_end; kiểu dữ liệu và từng claim đều được kiểm. String số đơn và khoảng số được đọc như claim gốc, không thay bằng tọa độ quan sát. Dòng bắt đầu phải khớp đầu quote, dòng kết thúc phải khớp cuối quote; không chấp nhận chỉ vì dòng nằm đâu đó trong đoạn. Claim dòng trong cause cũng được kiểm. Function trong object hoặc locator rõ ràng được so với scope từ vựng; prose không phân giải chắc được giữ unverified, không đoán tên hàm.

Đây không phải AST, compiler hay callgraph. Quote có thật không chứng minh finding đúng hoặc code reachable. Comment-only được từ chối khi lexer đủ căn cứ; literal, prototype, macro, nhánh tiền xử lý và đường gọi cần review riêng. Artificial fixtures có quote lặp ở comment và code để tránh nhận dòng comment chỉ vì cùng quote còn xuất hiện ở nơi khác.

| Tầng cumulative trên 30 raw | Qua | First reject tại tầng |
|---|---:|---:|
|Một object trong đúng một JSON fence|30|0|
|Shape, gồm location string/object|30|0|
|10 nhãn/status và tính nhất quán nội bộ|30|0|
|Quote tồn tại/kiểm lexical|30|0|
|Claim location không mâu thuẫn quote|7|23 `location:line_mismatch`|

**7 ở dòng cuối gồm 6 khớp claim từ vựng và 1 kiểm tra rỗng**, không phải 7 diagnosis được chứng minh. Chỉ 29 raw có finding: location object 21 (20 line đơn, 1 start/end), string 8; một uncertain có findings rỗng. Cả 29 quote đều là substring thật; không có comment-only rejection. Không có function field trong 21 object thực tế, nên kiểm function object được xác nhận bằng artificial fixtures, không phải quan sát compliance trên tập này. Semantic review tọa độ độc lập cũng cho 6 đúng, 23 sai, 1 không áp dụng.

Original strict parser vẫn là **0/30 accepted, 0 feedback**, kết quả run gốc không thay. Raw có fence không còn là lỗi wrapper theo đặc tả replay này; lỗi tọa độ vẫn giữ nguyên. Không tạo prediction/final đã “sửa vị trí”. Không tính F1 hay completion mới như một arm thực nghiệm.

Bản smoke replay đầu có hai string số/khoảng số chưa được nhận dạng và để unverified; regression fixtures đã bắt lỗi này. Artifact smoke được giữ riêng, superseded. Kiểm thử bổ sung cũng sửa lỗi implementation ở kiểm function prose, dòng comment có quote lặp và metadata tầng location. Không thay model/prompt/threshold/checkpoint để chọn kết quả. File cuối được định danh rõ bên dưới; các lần chạy offline phục vụ phát triển/kiểm tái lập script.

## 2. Ngữ nghĩa: nguồn và đường chạy, không suy truth từ quote

Hai agent chia hai nửa cố định 15 source, đọc source/raw/reference và ghi proof; root kiểm các ca biên và binding. Đây là **agent static review, không human-verified**, không reviewer mù. Không compile/run C++; compiler-confirmed và testcase-executed đều 0. Mỗi verdict gắn source/raw/request SHA. Các phản ví dụ/invariant là lập luận tĩnh, không phải output đã đo. Domain/harness của reference được giữ, gồm gọi P4 độc lập và filename do caller cấp; không tự thêm bảo đảm thứ tự gọi.

| Thuộc tính raw | Kết quả |
|---|---:|
|Status phù hợp source-reference|24/30|
|Status raw|29 defective, 1 uncertain, 0 clean|
|Cơ chế chính đúng|4/30|
|Đúng một phần|3/30|
|Sai cơ chế|22/30 (17 defect, 5 scoped-clean)|
|Không đưa cơ chế|1/30, uncertain trên scoped-clean|
|Đúng cơ chế nhưng sai tọa độ/format gốc|4/30; cả 4 đều sai tọa độ|
|False positive trên scoped-clean|5/6; bài còn lại uncertain, không bị tính false positive|
|Bỏ sót cơ chế chính|17/24 defect|
|False-clean theo status|0/24 defect; không có raw status clean|
|Bịa dữ liệu/diễn giải số học cụ thể|1/29 có finding; 1 raw rỗng không áp dụng|

24 status đúng là 24 defect bị gọi defective; không có dự đoán clean đúng. Nếu xem uncertain là abstention thì phân bố là 24 đúng, 5 sai, 1 abstain; bảng status boolean dùng exact alignment nên uncertain trên clean nằm trong 6 không khớp. Con số 1 về dữ liệu/số học chỉ bắt mệnh đề số học cụ thể, không thay cho 22 cơ chế sai hoặc 23 tọa độ sai. Trường hợp đó mô tả phép bình phương thành nhân đôi; không phát hiện witness input/expected/actual được bịa trong các raw này.

Quote được review theo ngữ cảnh: 27 liên hệ đường gọi/khối mã hoặc translation unit đang được chấm bằng suy luận tĩnh, 2 chỉ là prototype, 1 không có quote. Không gọi 27 là đã thực thi/reachability-proven; whole-source quote chứa cả header/helper không xác nhận mọi dòng đều chạy. COUNT006 và COUNT010 cùng quote một prototype: hợp lệ từ vựng nhưng không phải câu lệnh dùng/khởi tạo tham số. Root chuẩn hóa COUNT006 từ cách hiểu translation-unit của reviewer sang prototype-only, có đồng thuận, giữ verdict ban đầu để audit.

Ba ca partial được giữ riêng: COUNTVOWEL011 nhận ra case trùng nhưng diễn giải runtime thay lỗi quy tắc dịch; POWER007 nhận ra hành vi đảo cơ số/số mũ nhưng quy lỗi helper đúng; MAXARR006 nêu hiệu ứng mất cập nhật nhưng thiếu cơ chế truyền giá trị. MAXARR012 được root chốt **wrong**: đúng nhãn biên dịch/vùng khai báo không làm nhận định sai token thiếu thành đúng cơ chế. Ledger giữ nhận định partial ban đầu cùng adjudication; rationale ban đầu trong bảng riêng tư phải đọc như **initial reviewer rationale**, final verdict/adjudication có ưu tiên.

Supplement annotation là nhãn agent-authored đã seal của chính source SUP1, **không có official ZIP annotation v2 cho các code này**. Source-review là reference tĩnh mới, báo tách biệt:

| Raw label-set agreement — không phải score final mới | Annotation supplement | Source-review |
|---|---:|---:|
|Khớp exact set|3/30|3/26|
|Lệch|27|23|
|Unresolved reference|0|4|

Cả hai bảng có cùng ba label-set match: COUNT011, MAXARR012 và POWER003. Hai ca đầu nhãn biên dịch đúng nhưng nguyên nhân sai; POWER003 uncertain có tập rỗng chỉ là agreement của mảng nhãn, **không được thưởng exact-clean hoặc counted completed**. Bốn source taxonomy unresolved giữ null: MAXARR005/007/011 và UPPER006. Không ép nhãn để tăng agreement; cơ chế vẫn được review dù taxonomy chưa chốt.

Bảng dưới là metadata/rationale không chứa source/raw. **Bảng đầy đủ đúng 30 ID, có quote source ngắn, claim raw ngắn và rationale kiểm lại được** nằm tại [30-ID-analysis-final.private.md](../../outputs/task3/diagnosis-contract-v1-replay-v1-20261021/30-ID-analysis-final.private.md). JSON riêng tư giữ quote đầy đủ, claim gốc và proof/điều kiện. `U` là source taxonomy unresolved, `—` là không có finding; A/S là raw set match annotation/source; SHA là 12 ký tự đầu SHA-256 quote đầu tiên (full hash ở ledger). Mọi ID dưới có tiền tố `SUP1-`.

| ID | L | Cơ chế | Vị trí quote | A/S | Quote SHA | Rationale |
|---|---:|---|---|---|---|---|
|UPPER-008|2|sai|sai|lệch/lệch|fb34e62436b5|Quy lỗi cho xuất newline hợp lệ; bỏ cơ chế phá ký tự ngoài chữ thường.|
|RANGE-004|1|sai|đúng|lệch/lệch|1252fcfb2c2a|Cáo buộc không đọc input sai; bỏ việc mất bản ghi trùng khóa.|
|MAXARR-007|3|đúng|sai|lệch/U|91cfa56845f3|Nhận đúng bỏ phần tử lẻ cuối; tọa độ sai.|
|MAXARR-011|4|sai|sai|lệch/U|0d48ed7ed1c4|Đổ lỗi phép lấy cực đại đúng; bỏ seed sai cho toàn số âm.|
|COUNTVOWEL-005|2|sai|đúng|lệch/lệch|1714b59dc57b|Nói hàm không trả giá trị dù có return; bỏ kết quả đệ quy bị mất.|
|COUNTVOWEL-004|1|sai|sai|lệch/lệch|1315ff8f0b25|Nói lặp vô hạn dù biến tăng; lỗi thật là chỉ đếm tiền tố.|
|GEN-007|2|sai|đúng|lệch/lệch|5b85b673704f|Bịa thiếu thư viện; bỏ phụ thuộc cache khi gọi output độc lập.|
|COUNT-006|3|sai|sai|lệch/lệch|a557447020b9|Nhầm prototype tham chiếu hợp lệ thành lỗi khởi tạo; bỏ đảo trường dữ liệu.|
|COUNTVOWEL-011|2|một phần|sai|lệch/lệch|7b0a68b881dd|Nhận ra case trùng, nhưng giải thích runtime thay vì lỗi quy tắc dịch.|
|GEN-001|3|sai|sai|lệch/lệch|c869b2d08a7c|False positive sạch: cáo buộc thiếu thư viện không có căn cứ.|
|UPPER-002|1|sai|đúng|lệch/lệch|f318bccda897|False positive sạch: header chuẩn bị cho là không tồn tại.|
|COUNTEVEN-006|3|sai|sai|lệch/lệch|869ac315ecaf|Cáo buộc tham số chưa khởi tạo; bỏ max-heap khi đề yêu cầu min.|
|COUNTEVEN-008|1|sai|sai|lệch/lệch|e9404b96a78d|Nói stream không dùng dù có đọc; bỏ đường dẫn hard-code.|
|COUNTEVEN-001|3|sai|sai|lệch/lệch|b132a3360d4b|False positive sạch: tham số có khai báo bị nói chưa khai báo.|
|GEN-003|2|sai|sai|lệch/lệch|9bdb1599ffaa|Cáo buộc API mở file chuẩn sai; bỏ cộng lặp tổng tiền tố.|
|COUNT-010|2|sai|sai|lệch/lệch|a557447020b9|Nhầm thiếu gán output count thành chưa khởi tạo; quote chỉ prototype.|
|PALIN-011|3|đúng|sai|lệch/lệch|b81d974c53b7|Đúng thiếu ngoặc đóng trong điều kiện; tọa độ và taxonomy sai.|
|RANGE-003|1|sai|sai|lệch/lệch|c5f0b9acdd1f|Cáo buộc cấp phát hợp lệ; bỏ tìm kiếm nhị phân trên predicate không đơn điệu.|
|COUNT-005|2|sai|sai|lệch/lệch|d25ae94db494|Nói tham số chưa khởi tạo; bỏ việc gọi min thay hàm đếm.|
|SUMPAIR-001|2|sai|đúng|lệch/lệch|0a48b4bf057a|False positive sạch: tham số filename bị nói chưa khai báo.|
|COUNTVOWEL-009|2|đúng|sai|lệch/lệch|e48e85ef8420|Đúng bỏ nguyên âm liền kề do bước nhảy; tọa độ sai.|
|COUNT-011|4|sai|sai|khớp/khớp|63f904f51023|Nhãn biên dịch đúng nhưng nêu thiếu kiểu trả về thay dấu kết thúc lệnh.|
|UPPER-006|2|sai|sai|lệch/U|0ba1048138bf|Quy lỗi cho newline hợp lệ; bỏ điều kiện dừng làm mất ký tự cuối.|
|MAXARR-005|1|đúng|sai|lệch/U|965806f47849|Đúng in index thay value; tọa độ sai, source taxonomy còn unresolved.|
|POWER-007|3|một phần|đúng|lệch/lệch|6a14e9b3c801|Đúng hiệu ứng đảo cơ số/số mũ; quy lỗi helper đúng thay chỗ gọi.|
|RANGE-001|2|sai|sai|lệch/lệch|9470c4c4786f|False positive sạch từ cảnh báo API chung, không có lỗi tại source.|
|POWER-003|1|không có|—|khớp/khớp|—|Abstain trên scoped-clean; không có finding để chấm cơ chế/vị trí.|
|MAXARR-006|3|một phần|sai|lệch/lệch|c905141c847c|Đúng hiệu ứng mất cập nhật ở caller; thiếu nguyên nhân truyền giá trị.|
|MAXARR-012|1|sai|sai|khớp/khớp|707a4ff3aed8|Đúng vùng khai báo/nhãn biên dịch, nhưng nói sai token thiếu.|
|POWER-008|2|sai|sai|lệch/lệch|e2a54dd9d73d|Gọi bình phương là nhân đôi; bỏ việc diễn giải số mũ thập phân như nhị phân.|

Sáu raw qua tọa độ có năm cơ chế sai và một partial (POWER007); raw thứ bảy là uncertain rỗng. Bốn cơ chế đúng đều chưa qua tọa độ. Vì vậy có bottleneck format/location thật, đồng thời vẫn có sai diagnosis độc lập. Replay không đo được giữ finding hoặc chất lượng L2/L3 vì không tạo feedback. **Chỉ sửa parser/location không đủ lý do tiếp tục thử feedback từ kết quả này.** Dừng ở chẩn đoán hậu nghiệm; không chọn prompt, threshold, checkpoint hoặc đưa flow sang public.

## Artifacts và kiểm chứng

Chỉ thêm [script](../../scripts/task3_contract_v1_replay.py), [54 artificial tests](../../tests/test_task3_contract_v1_replay.py) và report này vào Git. Fixture gồm empty stdout, comment, helper không gọi, loop thiếu cập nhật, string/object location, duplicate quote, function claim mâu thuẫn, numeric range, stale hash và unresolved reference; không hard-code Evaluation ID. Source/raw/ledger/quote chi tiết ở ignored root `/workspace/llm-final-project/outputs/task3/diagnosis-contract-v1-replay-v1-20261021/`.

| Artifact cuối, riêng tư | SHA-256 |
|---|---|
|`protocol-replay-v1.1.private.json`|`fd7fb7f73edd2e5f60bba218ff1e1d71733688e0acf80cddc5e009cd7d03e569`|
|`semantic-final.private.json`|`8be8f39908981e713514d93877d57fcf52379fa55442d664fbdb684fc5a49f13`|
|`30-ID-analysis-final.private.md`|`667cc0752fa9b11ea6ca54c93be41222093ca13e5a6e697c229175e00131bd33`|
|`preservation-final.private.json`|`45075531799cf876ecd7d3b8f495b72a4afd09944e9fca4d762b6781e5963a3a`|

Original immutable bindings: seal SHA `d5ba90181827eb6c54c47fa8684f6201b06d96a7755e069fa9d84e5c634934f4`; original results SHA `c24a005509f4bc230503c4ee48c524228c945ac74a619946670144f7ed0c94bb`. Preservation xác nhận **643 file cũ giữ nguyên bytes**, gồm tracked production/report, toàn bộ contract-v1 private tree, các seal hiện có và bundle24 chỉ hash. Public predictions chỉ hash, vẫn `9ba7411c35a3461b5747be367274631d5122455335061005c695276ed76c5a45`.

Commands đã chạy từ repo:

```bash
.venv-task3/bin/python -m pytest -q tests/test_task3_contract_v1_replay.py
.venv-task3/bin/python scripts/task3_contract_v1_replay.py run
.venv-task3/bin/python scripts/task3_contract_v1_replay.py review
.venv-task3/bin/python scripts/task3_contract_v1_replay.py verify
.venv-task3/bin/python -m pytest -q tests/test_task3*.py
.venv-task3/bin/python -m pytest -q
```

`run`/`review` ghi exclusive vào artifact mới, không được ghi đè; dùng `verify` để tái tính 30 protocol rows và kiểm hashes hiện tại. Review semantic vẫn là judgment thủ công, không được suy thành chứng minh từ script. Các bản smoke/combined trước chốt được giữ riêng, superseded; chỉ các artifact mang tên cuối trong bảng trên là bàn giao chính thức.

Verification: **54 replay tests pass; Task3 946 passed, 2 skipped**. Global pytest dừng khi collect 2 module Task1 vì thiếu sklearn; không tuyên bố full repository pass, không cài dependency ngoài phạm vi. Independent audit tái tính stage counts, semantic summary/joins, mọi request/source/raw binding, quote excerpt, original location và null reference; không còn finding code quan trọng. Không có runtime model modules được load trong replay. HEAD cuối được ghi trong bàn giao chat; không push.
