# Task 3 Round 11 — kiểm chứng cơ chế và oracle finding, 20/10/2026

Chưa đủ điều kiện đóng băng phương pháp. Finding được duyệt giúp C2 ở S106/S112, nhưng không ngăn C2 sinh nhận định sai tại S111; tại S212 C2 vẫn thiếu hướng sửa cụ thể. A còn abstention và finding sai; B sửa cardinality vẫn có cùng false positive theo gold. Bộ kiểm tra cũng có false acceptance và false rejection. Không chạy heldout vì chưa đóng băng phương án; không dùng/chạy public, không push hoặc nộp leaderboard.

Đây là **diagnostic set sáu real-val đã xem nhiều lần**, không phải đánh giá chất lượng tổng quát. Review nội dung dưới đây là phân tích của agent dựa trên nguồn/compiler và phạm vi finding được người dùng duyệt cho thí nghiệm. Không gọi annotation là human-verified. Không chép source sinh viên hoặc raw attempts vào Git; các trích đoạn và log chi tiết nằm trong ignored outputs.

## Provenance và các điều kiện cố định

- Branch `feat/task3-quality-round5`; bắt đầu tại `0ba075a3bb084a43100fb895c00994b49a3b67b5`, working tree sạch.
- `9a480b89413fd64e7f440f823497ee38b95e60cb`: compiler-status prompt, audit uncertainty/export gate, non-compile recheck, direct cardinality control/exact prompt capture, C2 plumbing và test. A1/A2/B1/B2 chạy tại commit này.
- `e73dbc2eeac087df3488a8ea8beca0cefa3471f5`: thay cách ghi review approval để không nhận là human verification. **C1/C2 chính thức cùng chạy tại commit này**. C1-gold trước đó tại `9a480b8` chỉ là pilot, không dùng làm vế chính của cặp C1/C2.
- Bundle được đọc: `outputs/task3/mechanism-round11/review-bundle.zip`, SHA-256 `c10e086c6079f1cd53098c4b0d68ed51edf047ae45b6a8a4573e1faa620062aa`; bản giải nén giữ nguyên bên dưới `bundle/`. Đây là bundle NF4 Round 10 và BF16 C S212 đã yêu cầu, không tái sinh lịch sử.
- Artifacts lịch sử trong bundle dùng commit `154d83880d1a872641ae02c28a4085ad8af41a03`; bộ replay hiện tại giữ compiler lịch sử là **unavailable**, không thay bằng compiler mới.
- Manifest dữ liệu không đổi: `b311193f5c9fcf683019b1ae97c6e1017cfb4572cbcc1f3dfe2a3d9f3a753ee0`. `verify_prepared` xác minh checksum. Không sửa gold, không prepare lại dữ liệu.
- Model Qwen/Qwen2.5-Coder-7B-Instruct, revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`; Qwen2TokenizerFast cùng revision; chat-template SHA-256 `cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f`.
- Tất cả run mới: NF4; packed uint8, phần không quantize FP16, compute BF16; mọi tham số ở cuda:0, không offload. RTX 5090 32.607 MiB; Python 3.12.3, torch 2.8.0/CUDA 12.8, transformers 4.57.1, tokenizers 0.22.2, bitsandbytes 0.48.1.
- Seed 42, greedy, K=0, context 8192, feedback 512 tokens, diagnosis 384, hai retry feedback, prompt policy 7/guard 2. Không chỉnh guard/adequacy/retry policy trong vòng này. Non-compile recheck là nhánh A2 riêng, thêm đúng một lượt có cap 384.
- Thứ tự: EX01-S106, EX01-S111, EX01-S112, EX02-S201, EX02-S211, EX02-S212. Level tương ứng 2, 2, 2, 1, 1, 3. A/B không nhận gold taxonomy hoặc feedback giảng viên trong prompt; C là oracle riêng.

## Giai đoạn 1: truy vết lịch sử

Quy ước nhóm trong bảng: BD = Lỗi biên dịch, LG = Lỗi logic, VL = Lỗi vòng lặp, IO = Lỗi nhập/xuất, HC = Lỗi hard-code. Đây chỉ là viết tắt báo cáo; output vẫn dùng đúng 10 tên chính thức. Không thêm nhóm off_by_one; ánh xạ nội bộ của nó vẫn là Lỗi vòng lặp.

### A pipeline NF4 — diagnosis không xác định bị xuất thành nhãn rỗng

Mọi raw diagnosis có trường taxonomy cấp trên rỗng nhưng có finding gán BD. Parser đối chiếu finding rồi reconcile nhãn; việc lọc finding có thể đưa diagnosis trở lại uncertain. Root audit `validated` chỉ nói xử lý schema/filter hoàn tất, **không** chứng minh diagnosis đáng tin hoặc bài sạch.

| ID | Raw / finding bị loại | Trạng thái sau xử lý | Nhãn export lịch sử | Feedback cuối được chấp nhận; cùng căn cứ? |
|---|---|---|---|---|
| S106 | Hai finding BD về cấp phát/truy cập; không có compile evidence | uncertain; root validated | [] — chưa biết, không phải dự đoán sạch | Nhận định sai về kích thước vùng nhớ và con trỏ ở P4; không có finding đã giữ lại làm căn cứ |
| S111 | Retry định dạng/exact quote rồi hai finding BD bị lọc vì thiếu compiler evidence | uncertain; root validated | [] — chưa biết | Khẳng định biến chỉ số chưa khởi tạo, mâu thuẫn nguồn; có chữ Trung; không cùng finding hợp lệ |
| S112 | Hai lượt có quote không nguyên văn; parser không chấp nhận | unavailable / uncertain | [] — chưa biết | Fallback trung tính; không có coverage chẩn đoán |
| S201 | Finding BD có quote không nguyên văn, retry vẫn không parse được | unavailable / uncertain | [] — chưa biết | Khen gần đúng không có xác minh; không chứng minh clean hay lỗi nào |
| S211 | Như S201 | unavailable / uncertain | [] — chưa biết | Khen gần đúng không có xác minh |
| S212 | Finding BD bị lọc do compiler unavailable | uncertain; root validated | [] — chưa biết | Feedback vẫn nêu đúng tên chưa khai báo và hướng gắn với digit-count; không có nhãn/finding được giữ lại làm căn cứ |

Báo cáo precision trước đây gọi các [] này là prediction thực tế theo file; audit này làm rõ **ngữ nghĩa unknown đã bị mất khi export**, không dùng exact match trên hai gold [] để coi A nhận diện clean đúng.

### B direct NF4 — không có giai đoạn finding riêng

B sinh taxonomy và feedback trong một JSON, sáu lượt đều được parser/guard chấp nhận; không có chuỗi finding-filter độc lập để truy vết. **Prompt B trong bundle là bản dựng lại từ builder/input, không phải capture gốc.** Có wording “one or more” dù parser chấp nhận []; đây là mâu thuẫn cardinality thật, không phải bằng chứng đủ để giải thích mọi false positive.

| ID | Nhãn dự đoán thật | Feedback/căn cứ và vấn đề |
|---|---|---|
| S106 | LG | Bịa phép gán địa chỉ vào liên kết kế tiếp; nhóm trùng một gold nhưng lý do sai, thiếu VL |
| S111 | IO | Nói chung về file/đường dẫn; bỏ lỗi cú pháp có trong nguồn và đưa lời khuyên ở Level 2 |
| S112 | IO | Nhận ra literal thay cho tham số; tên file đích nói sai; taxonomy không khớp gold HC |
| S201 | LG | Level 1 chỉ nói rà soát; không thể suy ra finding LG từ câu này; gold [] |
| S211 | LG | Như S201; gold [] |
| S212 | LG | Có undeclared identifier nhưng lẫn quan hệ với biến khác; finding compile không nhất quán nhãn LG |

Level 1 không được buộc feedback nêu nhãn kỹ thuật để “khớp” taxonomy; cần căn cứ diagnosis nội bộ riêng. B không lưu căn cứ ấy. Vấn đề nguồn được review sau này của S201/S211 cũng không xác nhận lý do LG mà B đã dự đoán.

### C oracle NF4 — nhãn copy gold, không phải taxonomy prediction

| ID | Nhãn đầu vào/đầu ra | Feedback được chấp nhận / giới hạn căn cứ |
|---|---|---|
| S106 | LG, VL | Cùng câu chuyện sai về cấp phát/P4 như A; bỏ finding vòng lặp P3 thật |
| S111 | BD | Bịa biến chưa khai báo dù có declaration trong nguồn |
| S112 | HC | Đúng vấn đề literal/parameter nhưng có chữ Trung; vẫn được chấp nhận |
| S201 | [] | Khen gần đúng không có xác minh |
| S211 | [] | Khen gần đúng không có xác minh |
| S212 | BD, VL | Nêu compile finding có căn cứ và hướng digit-count; chưa có bằng chứng về một lỗi VL độc lập |

Gold taxonomy đúng không bảo đảm feedback dùng cùng bằng chứng; không chấm taxonomy C như model dự đoán.

## Compiler và bằng chứng thật trong prompt

`/usr/bin/g++` 13.3.0 đã có khi kiểm tra cài đặt; không cần thay package. Chạy lại preflight cả sáu nguồn bằng C++11 syntax-only, timeout 5 giây, giới hạn source 200.000 ký tự, diagnostic giữ tối đa 8.000 ký tự. **Không thực thi mã sinh viên, không tạo executable hoặc test output của bài.**

| ID | Compiler status | Bằng chứng mới |
|---|---|---|
| S106 | compiled | Chỉ xác nhận cú pháp; không chứng minh cấp phát/logic đúng |
| S111 | compile_error | Diagnostic thật tại dòng 51 và phép so sánh dòng 53; log giữ 8.000 ký tự, có cả warning/note |
| S112 | compiled | Không chứng minh dùng đúng tên file/tham số |
| S201 | compiled | Không kiểm chứng overflow hoặc tính đúng thuật toán |
| S211 | compiled | Không kiểm chứng stdout đúng hợp đồng |
| S212 | compile_error | Dòng 25 báo identifier chưa khai báo; log 115 ký tự |

`compiled`, `compile_error`, `unavailable` được phân biệt trong prompt; timeout cũng là unknown. Preflight S111/S212 được lưu riêng. Audit **prompt messages thực tế** của cả C1 và C2 xác nhận 4/4 trường hợp S111/S212 chứa compile_error và diagnostic thật. A diagnosis và B direct cũng nhận compiler evidence qua cùng cơ chế. Không coi warning multi-character constant tự nó là compile error; S111 còn có error thật khác. Feedback mới của A nhầm ký tự trong warning cho thấy có log không đồng nghĩa hiểu log đúng.

Artifacts: `compiler-preflight.json`, `EX01-S111.compiler-diagnosis-prompt.preflight.json`, `EX02-S212.compiler-diagnosis-prompt.preflight.json` dưới `outputs/task3/mechanism-round11/`.

## Replay offline: acceptance không đồng nghĩa đúng

37 raw attempts được đọc nguyên trạng: A diagnosis 10, A feedback 9, B direct 6, C NF4 feedback 9, C BF16 S212 feedback 3. Replay **không gọi model**; 27/27 quyết định feedback/direct khớp retry/acceptance aggregate đã lưu. Diagnosis 10 lượt được replay parser riêng và đọc filter/controller trace lịch sử, không đánh đồng parser-only với toàn controller.

Danh sách false acceptance/candidate ở final model feedback lịch sử:

| Run / ID / attempt | Vấn đề lọt qua | Loại bằng chứng |
|---|---|---|
| A S106 / 1 | Cấp phát bị mô tả sai; nguyên nhân P4 bịa | Mâu thuẫn nguồn |
| A S111 / 2 | Nhận định chưa khởi tạo sai; chữ Trung | Mâu thuẫn nguồn và CJK thật |
| C S106 / 1 | Như A S106 | Mâu thuẫn nguồn |
| C S111 / 1 | Bịa tên chưa khai báo | Declaration trong nguồn |
| C S112 / 3 | Nội dung finding có căn cứ nhưng chữ Trung | Language failure, không gọi là factual failure |
| B S106 / 1 | Bịa phép gán con trỏ | Mâu thuẫn nguồn |
| B S111 / 1 | Chẩn đoán file không đủ căn cứ, lời khuyên Level 2 | Unsupported claim / disclosure review |
| B S112 / 1 | Tên file đích sai | Đề đối chiếu nguồn |
| B S212 / 1 | Nhãn LG không cùng compile finding; quan hệ biến bị mô tả sai | Taxonomy/finding mismatch |

Bảng có 9 final acceptances cần bác bỏ/review theo các tiêu chí khác nhau, **không cộng thành 9 factual errors cùng loại**. Bốn câu khen gần đúng tại A/C S201/S211 được tách là unsupported praise; không tự xem chúng là đã chứng minh sai hoặc đủ căn cứ. Dự đoán nhãn dương của B trên hai gold [] là false positive **theo gold**, đồng thời báo bất đồng annotation bên dưới.

False rejection và true rejection:

- C BF16 S212 attempt 1: chẩn đoán có căn cứ, thay bound bằng digit-count trong một dòng và có giải thích; disclosure guard pass nhưng adequacy từ chối `level3_direction_candidate`. Đây là false-rejection candidate rõ về hướng sửa, không phải model không sinh được phản hồi hữu ích.
- Attempt 2 đưa lời giải đầy đủ, attempt 3 code block nhiều dòng: guard từ chối đúng theo giới hạn Level 3. Không gộp ba lần bị từ chối thành ba false rejection.
- A/C S112 có lượt diagnosis-only dùng đối chiếu literal/parameter bị screen `repair_guidance` bắt; có thể quá rộng. Một số raw đồng thời khẳng định “luôn thất bại” không đúng trong mọi hệ thống file: không tự đánh dấu toàn lượt đó là feedback đúng chỉ vì finding lõi đúng.
- Các lượt khác bị chặn sửa code/đưa hướng sửa ở Level 2 vẫn là rejection có căn cứ. Fallback A S112 không được tính feedback hữu ích.

CJK được đếm riêng: A feedback 1/9 lượt (final S111), C NF4 1/9 (final S112), B NF4 0/6; A diagnosis 1/10; BF16 S212 0/3. CJK trong feedback A/C là lỗi tiếng Việt, dù guard chấp nhận. Screen hiện chỉ cảnh báo ngôn ngữ, không hard-reject; không báo chúng là language-compliant. Kết quả replay không phục dựng được subcheck decision chưa capture: B chỉ có validation aggregate; mọi subcheck mới là quan sát offline, prompt B vẫn mang provenance reconstructed.

## Finding được duyệt và ranh giới C2

Draft gồm 7 finding từ nguồn, đề, feedback giảng viên và compiler thật. Trích dẫn mã nguyên văn, problem ID, dòng, source/statement hash, cause, evidence, confidence và điểm tranh luận nằm trong `FINDINGS_DRAFT_FOR_REVIEW.md` / `findings-draft.json` riêng tư. Instructor feedback là đối chiếu, không phải chân lý nếu mâu thuẫn code.

Người dùng duyệt 5 finding cho C2, nguồn xác nhận ghi chính xác **“independent assistant review plus source/compiler evidence”**, không ghi human-verified. File mới `findings-approved-C2.json` giữ hash draft và provenance phê duyệt, không ghi đè draft. SHA-256: `f77321ba62c36764dbf00ea4f7158567fff931dedd8e1c87501b2ee93d6f7d57`.

| Finding | Problem | Nhóm cho C2 | Căn cứ / giới hạn |
|---|---|---|---|
| S106-loop | P3 | VL | Con trỏ duyệt không tiến trong vòng lặp; high confidence |
| S106-allocation | P2 | LG | Một node được cấp phát nhưng bị truy cập nhiều chỉ số, liên kết chưa đúng; cách phân nhóm mảng/chuỗi vẫn có thể tranh luận, không đổi gold |
| S111-syntax | P1 | BD | Danh sách đối số sai tại dòng 51, compiler xác nhận; không tuyên bố đây là toàn bộ lỗi |
| S112-literal | P1 | HC | Literal không dùng tham số; không khẳng định mọi lần mở file đều thất bại |
| S212-undeclared | P1 | BD | Compiler xác nhận identifier chưa khai báo; hướng sửa gắn bound với digit-count |

C2 chỉ có 5 finding trên **4/6 ca**, không phải annotation đầy đủ mọi lỗi. S201-overflow và S211-output được người dùng xác nhận có căn cứ nguồn/đề nhưng loại khỏi C2 gold-consistent; lưu `gold-disagreements.json`. S201: phép tính tĩnh trên input hợp lệ vượt INT_MAX 32-bit được compiler macro xác nhận. S211: stdout thêm lời nhắc ngoài hợp đồng kết quả. Không thực thi để kiểm chứng, không sửa gold [] của cả hai, không dùng nhận định của B thay cho bằng chứng này. Không thêm finding VL độc lập cho S212 để khớp gold.

C2 loader kiểm tra đúng ID/source/statement hash, quote nguyên văn, official label và problem ID. Chỉ các trường finding cần thiết đi vào context; feedback giảng viên không được đưa vào prompt C2. Level 1 chỉ nhận flag có finding, không có quote/cause/repair; vì S201/S211 bị loại nên flag false nghĩa **không supplied approved finding**, không có nghĩa clean. Oracle context được giữ trong 8/8 attempts C2, kể cả retry. Đây là oracle development dùng model thật, không phải thuật toán có thể dùng khi suy luận public; không phải kết quả của replay offline.

## Giai đoạn 2: kết quả kiểm soát mới

### Cặp C1/C2 chính thức

C1 chỉ gold nhóm lỗi; C2 thêm finding được duyệt. 6/6 initial base message arrays giống hệt nhau sau khi bỏ đúng một oracle context message. Cùng commit/config/compiler/model/precision/Level/decoding. Không thay guard để nhận câu trả lời sai.

| ID | C1 gold groups | C2 approved findings | Kết luận theo nguồn / Level |
|---|---|---|---|
| S106 | Nhận định sai về kích thước cấp phát, gán bounds bug thành compile error, thêm nguyên nhân P4 sai; accepted | Đúng cấp phát một node và vòng lặp P3 không tiến; accepted | C2 phủ 2/2 finding, cùng LG/VL; cách nói chỉ số gộp cả vị trí cuối hơi lỏng, không gọi mọi chi tiết hoàn hảo |
| S111 | Trộn so sánh kiểu có căn cứ với các lỗi khai báo/khởi tạo bịa; accepted | Vẫn bịa lỗi chính tả toán tử/khai báo ở dòng 51/53; không mô tả finding được duyệt; accepted | Finding đúng được cung cấp vẫn không bảo đảm grounding; false acceptance của cả hai |
| S112 | Ba lượt: sửa code hoặc bị bắt repair guidance; final fallback | Diagnosis đúng literal/parameter, không repair; accepted lượt 1 | C2 có ích ở Level 2; C1 fallback coverage 0 |
| S201 | Rà soát nhẹ; accepted | Rà soát nhẹ; accepted | Level 1 đạt trần tiết lộ; không phải bằng chứng taxonomy sạch hoặc coverage technical finding |
| S211 | Khen gần đúng chưa xác minh; accepted | Rà soát nhẹ, bỏ lời khen; accepted | C2 giảm unsupported praise ở một ca, chưa đủ kết luận nhân quả rộng |
| S212 | Ba lượt đúng undeclared và hướng bound gắn digit-count; disclosure guard pass, adequacy reject | Ba lượt đúng undeclared nhưng chỉ khuyên khai báo, chưa chỉ giá trị/quan hệ digit-count; adequacy reject | C1 có false-rejection candidate; C2 thiếu hướng sửa hữu ích, không nới guard để cứu completion |

| Run | Accepted / export | Fallback | Taxonomy model | Peak alloc/reserved MiB | Generation mọi attempts s | Wall s |
|---|---|---|---|---:|---:|---:|
| C1-approved-pair | 5/6 prefix; dừng S212; không full export | 1/5 prefix | Không chấm: gold input | 6744 / 6876 | 10,825 (10 attempts) | 20,145 |
| C2-approved-pair | 5/6 prefix; dừng S212; không full export | 0/5 prefix | Không chấm: gold input | 6744 / 6812 | 6,290 (8 attempts) | 15,281 |

Không tính F1/exact match hoặc tỷ lệ fallback toàn split cho hai output chưa hoàn tất. C1 pilot tại commit trước cũng dừng S212, 5 accepted và 1 fallback, nhưng không thay thế cặp chính thức. Latency là synchronize generation theo backend; wall gồm load; allocator peak của process, không phải VRAM toàn host. Thứ tự tuần tự/cache/workload nền không được cân bằng để làm benchmark tốc độ.

### B: chỉ đổi one → zero

Cả hai chạy tại `9a480b8`, cùng compiler evidence mới. Audit exact captured initial messages xác nhận 6/6 chỉ đổi cardinality phrase. Không so B mới với B lịch sử để quy chênh lệch cho cardinality vì compiler prompt lịch sử khác.

| ID | B1 one / B2 zero: taxonomy giống nhau | Review feedback |
|---|---|---|
| S106 | BD / BD | Cả hai bịa thiếu entry point dù nguồn có và syntax compiled; thiếu hai finding thật |
| S111 | BD / BD | Có compile failure thật; thiếu vị trí/cause cụ thể và đưa yêu cầu kiểm tra ở Level 2 |
| S112 | IO / IO | Đúng lõi literal nhưng tên file kỳ vọng sai; bỏ HC theo gold |
| S201 | LG / LG | Cùng rà soát nhẹ; false positive theo gold [], chưa có finding LG được kiểm chứng |
| S211 | LG / LG | Như S201 |
| S212 | BD / BD | Đúng undeclared identifier; chỉ khuyên khai báo, chưa hướng digit-count, thiếu gold VL nhưng không bịa VL độc lập |

| Run | Complete | Fallback | Macro F1 (10 nhóm) / micro F1 | Exact match | FP trên gold [] | Peak alloc/reserved MiB | Gen / wall s |
|---|---:|---:|---|---:|---:|---:|---:|
| B1-one-more | 6/6 | 0/6 | 0,080 / 0,333 | 1/6 | 2/2 | 6744 / 6814 | 3,710 / 12,652 |
| B2-zero-more | 6/6 | 0/6 | 0,080 / 0,333 | 1/6 | 2/2 | 6744 / 6814 | 3,803 / 12,767 |

Macro skip-absent = 0,160 cho cả hai. Đây là điểm so gold nguyên trạng, kể cả gold disagreement; không sửa nhãn để tăng điểm. Từ một cặp greedy không thể kết luận wording không có ảnh hưởng nói chung. Kết luận hẹp: sửa mâu thuẫn schema là đúng nhưng không giải quyết false positive trong cặp này. Heuristic compliance 6/6 của cả hai không đo được đúng sự thật hay đủ Level 3.

### A: unknown riêng biệt và một non-compile recheck

| ID | A1 compiler / A2 recheck | Nullable taxonomy_prediction | Review căn cứ |
|---|---|---|---|
| S106 | uncertain / uncertain | null / null | Compile finding bị loại sau syntax pass; A2 recheck bị truncation/JSON không hợp lệ |
| S111 | predicted_errors / predicted_errors | BD / BD | Compile evidence thật, nhưng finding/feedback diễn giải sai warning/ký tự; label đúng không đủ |
| S112 | uncertain / uncertain | null / null | Compile finding bị loại; A2 recheck bị truncation/JSON không hợp lệ |
| S201 | predicted_errors / predicted_errors | LG / LG | Finding nói accumulator không được cập nhật, mâu thuẫn nguồn; không phải overflow đã duyệt |
| S211 | unavailable / unavailable | null / null | Không có diagnosis parse được; không tự thành [] |
| S212 | predicted_errors / predicted_errors | BD / BD | Compile finding có căn cứ; không tự thêm VL |

Cả hai hoàn thành audit diagnosis 6/6, có nhãn xác định ở 3/6 và abstain 3/6 (2 uncertain + 1 unavailable). **Không có prediction export hoàn chỉnh, không chấm F1/exact toàn split.** A2 chỉ recheck khi compile finding bị lọc rồi còn uncertain; trigger S106/S112, một lượt mỗi ca, cùng cap 384. Cả hai stop vì length, parser từ chối; không tăng cap hoặc giảm chuẩn parse sau khi xem kết quả. Không có rule theo ID.

| Run | Diagnosis attempts / gen s | CLI wall s | Peak alloc/reserved MiB | Feedback probe trên resolved subset |
|---|---:|---:|---:|---|
| A1-compiler | 7 / 13,824 | 22,758 | 6744 / 6814 | Chọn đúng 3 resolved ID; accepted S111/S201, dừng S212 sau 3 attempts; không full export |
| A2-noncompile-recheck | 9 / 23,198 | 32,549 | 6744 / 6814 | Như A1; trạng thái unknown được giữ |

Hai feedback probe bổ sung có manifest scope **resolved subset only**, không phải output toàn sáu mẫu. S111 vẫn diễn giải sai ký tự từ warning; S201 vẫn khen gần đúng chưa kiểm chứng. Không dùng hai accepted prefix này để tuyên bố A hoàn tất 2/6 hoặc có chất lượng trên split. Generation feedback 4,097 / 3,961 giây; các probe dùng lại audit đã lưu, không chạy lại diagnosis hoặc truyền gold.

## Đo riêng factual, coverage, Level và kiểm tra

Rubric review này phân biệt: (a) claim kỹ thuật được nguồn/log hỗ trợ; (b) claim mâu thuẫn hoặc trộn sai; (c) lời khen chưa xác minh; (d) câu Level 1 chỉ nhắc rà soát, không chứa technical diagnosis; (e) fallback. Không biến (d)/(e) thành factual accuracy 100%. Coverage tính theo finding được duyệt và nội dung **được phép ở Level**, không đòi Level 1 tiết lộ lỗi; S201/S211 không nằm trong denominator approved C2 findings.

| Chiều / scope | C1 | C2 | B1 và B2 (mỗi run đầy đủ) |
|---|---|---|---|
| Factual ở Level 2, ba ca | 2/3 final mâu thuẫn/trộn sai; 1/3 fallback | 1/3 final sai (S111); 1/3 hỗ trợ lõi nhưng phrasing hơi lỏng (S106); 1/3 hỗ trợ rõ (S112) | 1/3 false (S106), 1/3 mixed sai filename (S112), 1/3 compile status được hỗ trợ nhưng quá chung (S111) |
| Coverage approved Level 2 (4 findings) | Final prefix 0/4 finding được mô tả đúng, hữu ích; raw S112 có lõi đúng nhưng final fallback | Final prefix 3/4 (hai S106 và S112); S111 không đạt | 1/4 ở mức compile failure S111 nếu cho phép broad coverage; 0/4 chẩn đoán đầy đủ vị trí/cause; S112 core đúng nhưng mixed claim không chấm là finding hoàn toàn đúng |
| Level 1, hai ca | 2/2 không technical disclosure; 1/2 unsupported praise | 2/2 rà soát nhẹ, không praise; không gán technical coverage | 2/2 rà soát nhẹ; taxonomy LG chưa có căn cứ |
| Level 3, một ca | Raw có diagnosis và hướng digit-count; 0 accepted; FR candidate 3/3 attempts | Raw 3/3 có diagnosis nhưng 0/3 hướng sửa đủ cụ thể; 0 accepted | 1/1 accepted nhưng hướng khai báo chung không đủ hữu ích; không chấm Level 3 adequacy pass |
| Nội dung vượt Level 2 | S112 có sửa code rõ ở lượt 1 và 3 (2/3 attempts); final fallback không leakage | 0/3 final tiết lộ repair; factual sai vẫn là fail chất lượng | S111 có lời khuyên kiểm tra ở Level 2: 1/3; hai ca còn lại không chép lời giải |
| CJK mới | 0/10 attempts | 0/8 attempts | 0/6 final và attempts |

Coverage 3/4 của C2 là **prefix Level 2 và annotation đã chọn**, không phải score toàn split hoặc mọi lỗi thật. S106 diễn đạt range truy cập hơi gộp: review chấp nhận hai cơ chế lõi, ghi rõ hạn chế, không tuyên bố không có sai sót. S212 approved compile finding có raw diagnosis đúng ở C1/C2, nhưng C2 không render được hướng sửa đã cung cấp; gold loop chưa có independent finding nên không dùng làm denominator mới.

False acceptance mới: C1 S106/S111 và C2 S111 đều guard-pass dù claim sai; B1/B2 S106/S112 đều accepted dù claim sai/mixed. B S111 có lời khuyên Level 2; B S212 được parser chấp nhận dù hướng sửa chung. Các lỗi này được liệt kê riêng, không trộn thành một metric “guard accuracy”. C1 S212 có FR candidates; C2 S212 không được gọi là ba FR vì raw cũng thiếu action cụ thể. Tỷ lệ FA/FR thật toàn bộ không xác định do chưa có annotation đầy đủ mọi claim/attempt, chỉ có danh sách review evidence và các denominator nêu trên.

## Giai đoạn 3: quyết định và blocker

Giữ thay đổi audit/export: unknown phải là null và fail-closed trước complete export; schema nộp bài chỉ có list nhãn nên không biểu diễn abstention. Không giải quyết bằng cách lặng lẽ điền []. Giữ cardinality đúng “zero or more” mặc định, nhưng không quảng bá đây là sửa chất lượng đã chứng minh.

Chưa chọn/freeze A2: tăng chi phí và thêm hai JSON truncation, không tăng coverage. Chưa chọn C2 thành phương pháp: oracle không khả dụng public, kết quả còn sai dù được cung cấp finding. Bằng chứng chỉ ủng hộ **grounding là một phần nút thắt** (S106/S112), đồng thời feedback renderer và checker là blocker độc lập (S111/S212). Không kết luận diagnosis là nguyên nhân chủ yếu từ cặp này.

Hướng sửa tiếp theo cần kiểm chứng bằng train/artificial fixtures: finding phải có exact quote **và entailment** của observed fact; khớp span chưa chứng minh cause. Map finding sang đúng nhóm, rồi renderer chỉ nói finding được xác nhận; phân biệt compiler warning và error; Level 2 không thêm repair, Level 3 phải giữ quan hệ hành động cụ thể. Với CJK cần policy rõ cho feedback tiếng Việt và test phân biệt quote nguồn với lời model; hiện chỉ warning, nên các output có chữ Trung bị loại khỏi đánh giá đạt ngôn ngữ, không giả vờ đã hard-block.

Adequacy có hai recognizer hướng sửa không nhất quán: bộ rộng nhận động từ khai báo, nhưng nhánh `LEVEL3_DIRECTION_REVIEW_CANDIDATE` hẹp không nhận một số cách viết ấy và động từ đổi đứng riêng. Đây giải thích được FR của BF16 S212 và C1 mới. **Không chỉ thêm động từ rồi coi mọi câu khuyên khai báo là hữu ích**: C2/B có đúng kiểu câu ấy nhưng thiếu binding digit-count. Cần test cả cụ thể/generic/full-solution trước khi sửa policy. Guard/adequacy hiện được giữ nguyên để bảo toàn đối chứng; không có generic Level 3 fallback và không hợp thức hóa claim sai.

Các blocker còn lại: known-clean state chưa có trong diagnosis schema; false positive/cause hallucination; renderer không giữ finding đã duyệt; language warning chưa hard-block; false rejection adequacy; gold disagreement S201/S211 và thiếu independent loop finding S212; bốn test sandbox runtime chưa pass. Vì vậy **không chạy synthetic-heldout, không chạy public, chưa đóng băng**.

## Kiểm tra và tái hiện

- Targeted mechanism/compiler/round9/round10: **49 passed** tại code `e73dbc2`.
- Task 3 suite cuối: **355 passed, 4 skipped, 4 failed**. Bốn lỗi thuộc `test_task3_cpp_checks.py`: `test_actual_cpp11_gcd_inputs_outputs_are_recorded`, `test_cpp11_missing_climits_is_a_useful_compiler_failure`, `test_actual_digits_contract_and_wrong_output_remain_measurements`, `test_cpp_infinite_loop_and_output_flood_are_stopped`.
- Cả bốn bị sandbox fixture compiler không spawn được `/usr/libexec/gcc/x86_64-linux-gnu/13/cc1plus` (`execv: Permission denied`); không phải compile evidence của sinh viên. Không nới Landlock, không bỏ qua rồi gọi full suite pass.
- Scope bỏ riêng module runtime sandbox: **340 passed, 3 skipped**. Các test dùng fixture nhân tạo; không chạy executable của sinh viên.
- Validator offline qua script chính thức repo: **B1 và B2 VALID, 6/6 đúng ID/thứ tự/Level/schema**. C/A không có full export nên không chạy validator prefix như full output. Đây là validator schema, không xác nhận factual/Level semantic.
- Exact prompt pair audit, actual compiler evidence, oracle context persistence và checksum dữ liệu: pass; `verification-summary.json`, `final-checks.json`, logs cuối trong ignored outputs. `git diff --check` trước commit.

Lệnh chính (dùng tên output mới để giữ nguyên artifacts cũ; mỗi model process chạy tuần tự):

```bash
cd /workspace/llm-final-project
export HF_HOME=/workspace/llm-final-project/outputs/task3/hf-cache
.venv-task3/bin/python scripts/run_task3.py --config configs/task3/r11_compiler_control.yaml --split real-val --taxonomy-source gold --output outputs/task3/reproduce-r11-C1.json
.venv-task3/bin/python scripts/run_task3.py --config configs/task3/r11_compiler_control.yaml --split real-val --taxonomy-source gold --oracle-findings outputs/task3/mechanism-round11/findings-approved-C2.json --output outputs/task3/reproduce-r11-C2.json
.venv-task3/bin/python scripts/run_task3_direct_baseline.py --config configs/task3/r11_direct_one_more.yaml --split real-val --output outputs/task3/reproduce-r11-B1.json
.venv-task3/bin/python scripts/run_task3_direct_baseline.py --config configs/task3/r11_direct_zero_more.yaml --split real-val --output outputs/task3/reproduce-r11-B2.json
.venv-task3/bin/python scripts/run_task3.py --config configs/task3/r11_compiler_control.yaml --split real-val --taxonomy-source self-diagnosis --output outputs/task3/reproduce-r11-A1.json
.venv-task3/bin/python scripts/run_task3.py --config configs/task3/r11_noncompile_rediagnosis.yaml --split real-val --taxonomy-source self-diagnosis --output outputs/task3/reproduce-r11-A2.json
.venv-task3/bin/python scripts/validate_task3_submission.py --predictions outputs/task3/mechanism-round11/B2-zero-more.json --requested-levels outputs/task3/mechanism-round11/requested-levels.real-val.json
.venv-task3/bin/python -m pytest -q tests/test_task3_mechanism.py tests/test_task3_compile_evidence.py tests/test_task3_round9_prompts.py tests/test_task3_round10_prompt.py
```

Lệnh A/C dự kiến exit nonzero đúng các blocker trên, không có full predictions. C2 cần file finding riêng tư đã duyệt, không thể tái dựng từ taxonomy gold đơn thuần. Replay offline dùng bundle gốc và current guard, kết quả `offline-replay.json`; chạy lại bằng `PYTHONPATH=. .venv-task3/bin/python outputs/task3/mechanism-round11/replay_only.py` ghi file mới `offline-replay.reproduced.json`, đã đối chiếu bằng nhau hoàn toàn. Script riêng tư `stage1_audit.py` còn có bước tạo draft nên **không chạy lại toàn script để ghi đè annotation đã duyệt**. Index lịch sử `bundle/.../ATTEMPT_INDEX.json` nối từng attempt với artifact; new journals nối sample_id/attempt_index/cache_key với progress/final. Run manifests chứa resolved config, model/tokenizer revision, code SHA, precision, device và allocator telemetry. Không stage raw prompts, source, findings JSON, predictions, data, model cache hoặc bundle ZIP.
