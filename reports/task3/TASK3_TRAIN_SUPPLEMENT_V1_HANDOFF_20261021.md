# Task 3 — Archive-only train supplement v1 (2026-10-21)

**Đã khóa 88 source / 10 TRAIN family và 352 target dự thảo; không train, load model, chạy inference hoặc push.** Tạo 100 ứng viên, nhận 88, loại 5 và giữ riêng 7 uncertain. Không thêm biến thể để đạt quota 100–150. Đây là supplement cho **controlled holdout có prior exposure**, không làm Evaluation v2 thành benchmark mù. Cả Evaluation v1/v2 và seal giữ nguyên bytes; không đổi split hay whitelist v2.

HEAD trước lượt: `2acc912438a5f231f92b8cce4b46574f9e135f74`, branch `feat/task3-quality-round5`, working tree ban đầu sạch. Chỉ thêm code/test/metadata/report mới. Không dùng adapter R18, public inputs, public feedback, predictions hoặc leaderboard để tạo source, target hay chọn phương pháp.

**Archive và inventory trước sinh.** Đọc đúng bytes của `generate-dataset_v2.zip`, SHA-256 `6bda70c29254a3bce91933b65f4a311d73a052e72d181c97e977152e14602f9b`; đây là cùng archive người dùng upload với hậu tố `(2)`, không phải dataset version mới. Không extract đè prepared data; không sửa annotation/gold. Loader lọc 10 TRAIN family từ root index trước khi đọc member source; không mở source heldout hoặc EVALUATION family. Teacher prose không được giữ hay dùng. Các member thực đọc đều có hash trong private snapshot.

Inventory đã báo trước sinh: v2 giữ **8 source / 5 family** đủ eligibility, gồm UPPER-0005, PALIN-0015/0017/0019, MAXARR-0010/0011, COUNTVOWEL-0010, POWER-0007 (tiền tố `SYN-`). Đối chiếu annotation của 8 record: BC4, LG3, IO2, AR1, LP1; thiếu FN/EC/AL/HC/ST. Đây chỉ là annotation inventory, không được dùng làm source truth. Supplement không nhập 8 record này vào target mới. Root TRAIN index có 204 records / 149 source text khác nhau trong 10 family; chúng chỉ dùng kiểm trùng, không dùng prose làm target.

| TRAIN family | Yêu cầu từ archive, tóm tắt | Kiểu đề |
|---|---|---|
|SYN-COUNT|Đọc các cặp vào mảng động; đếm dòng; min b; in số dòng|multi_problem|
|SYN-COUNTEVEN|Đọc các cặp; đếm a chẵn; min b; in số đếm|multi_problem|
|SYN-GEN|Đọc các cặp; tổng a; max a; in tổng|multi_problem|
|SYN-RANGE|Đọc các cặp; đếm a<b; max a; in số đếm|multi_problem|
|SYN-SUMPAIR|Đọc các cặp; tổng a+b; max a; in tổng|multi_problem|
|SYN-COUNTVOWEL|Đếm lần xuất hiện của a/e/i/o/u thường trong token|single_problem|
|SYN-MAXARR|Giá trị lớn nhất trong n số nguyên|single_problem|
|SYN-PALIN|Kiểm tra số nguyên không âm đối xứng thập phân, True/False|single_problem|
|SYN-POWER|Tính a mũ b với a,b không âm, kết quả vừa long long|single_problem|
|SYN-UPPER|Chuyển token sang chữ hoa|single_problem|

Năm đề multi dùng `Rec {int a,b;}`, các prototype `Rec* prob1(string filename,int& n)`, `int prob2(Rec*,int)`, `int prob3(Rec*,int)`, `void prob4(Rec*,int)`; P1 là prerequisite. Function submission không bắt buộc `main`. Năm đề single dùng stdin/stdout, không áp đặt helper prototype. Exam/problem/policy được lấy từ archive; mỗi source mới gắn hash exam, statement, problems/prototypes và policy riêng.

**Source và bằng chứng.** Ba batch tác giả chỉ nhận context TRAIN/label space được lọc, không nhận Evaluation reference, findings, outputs hoặc teacher feedback. Mỗi source có ID versioned, generator/seed42/provenance, bytes/hash, domain, compile expectation, testcase và finding với quote/span/location, nguyên nhân, nhãn, expected/actual suy luận cùng hướng sửa. Clean có bất biến và miền cụ thể. Record P1 sai không gán kết quả xác định cho downstream không còn hợp lệ.

Namespace probe `unshare --user --map-root-user --mount --net --pid --fork true` thất bại `Operation not permitted`; không có bwrap/docker/podman usable. **Không compile hoặc chạy source supplement trên host.** 88 source nhận có mức `independently-checked static reasoning`, đều assistant-reviewed, không human-verified. 84 source được kỳ vọng valid C++11, 4 được kỳ vọng compile_error theo lập luận grammar. **Compiler-confirmed = 0; counterexample-executed = 0; diagnostic thực = null.** Python chỉ dùng xử lý dữ liệu, kiểm hash và tính số học đặc tả; không gọi mã C++ sinh viên.

| Family | Tạo | Nhận | Clean nhận | Defective nhận |
|---|---:|---:|---:|---:|
|SYN-COUNT|11|10|2|8|
|SYN-COUNTEVEN|8|8|1|7|
|SYN-COUNTVOWEL|11|11|2|9|
|SYN-GEN|8|6|1|5|
|SYN-MAXARR|12|12|2|10|
|SYN-PALIN|11|11|3|8|
|SYN-POWER|11|7|2|5|
|SYN-RANGE|8|8|1|7|
|SYN-SUMPAIR|8|5|2|3|
|SYN-UPPER|12|10|2|8|
|**Tổng**|**100**|**88**|**18**|**70**|

Nhận 51 single_problem và 37 multi_problem. 18/88 clean = 20.45%. Đếm source, không tính ba Level thành ba code. Không gọi 88 source là 88 thuật toán độc lập: các đề nhỏ có chung phép duyệt, đối xứng, reduction và prototype; review phân biệt cơ chế lỗi, cấu trúc dữ liệu và điều khiển với thay đổi bề mặt.

| Nhóm chính thức | Source nhận |
|---|---:|
|Lỗi biên dịch|4|
|Lỗi nhập/xuất|6|
|Lỗi logic|30|
|Lỗi vòng lặp|3|
|Lỗi mảng/chuỗi|1|
|Lỗi hàm|6|
|Lỗi edge case|3|
|Lỗi thuật toán|12|
|Lỗi hard-code|5|
|Lỗi style|0|

Giữ đủ 10 nhãn chính thức. TRAIN statements/policy không có ràng buộc style cụ thể đủ làm finding; không gán ST cho comment, TODO, tên biến hoặc sở thích trình bày. Coverage AR/LP/EC còn mỏng. Nhãn và ranh giới AL/LG/FN là review của assistant, không trở thành annotation gold của archive.

**Diversity và leakage.** Guard v2 được import nguyên trạng, không sửa hoặc bypass. Registry family exposure vẫn chỉ mô tả; registry dùng làm ví dụ/target/output-review và reserved identities tiếp tục là exclusion. New whitelist chỉ nhận 88 source supplement đã được khóa; không tự hợp nhất hoặc nới whitelist 8 source cũ. Protected metadata gồm registry v2 và chữ ký của root TRAIN originals. Chỉ dùng ID/hash/shingle của protected Evaluation/history để loại trừ; không đọc source/reference của chúng cho generation/targets.

Không có exact/group/token/identifier-renamed collision hoặc shingle Jaccard ≥0.85 được phát hiện ở 100 ứng viên so với protected/originals hoặc trong supplement. Đây là điều kiện máy, không phải chứng minh semantic độc lập. Review thêm toàn bộ 10 danh sách thiết kế, **54 cặp có Jaccard ≥0.45**, và một cặp semantic dưới 0.45. Mỗi cặp có rationale riêng về logic thật và boilerplate, đồng thời bind cả hai source/recipe hashes. Source review và family review do tác giả khác thực hiện; parent cross-check các quyết định. Các trường hợp không đủ chắc được giữ ngoài target, không dùng một ngưỡng lexical làm ground truth.

Loại 5 ID: `SUP1-UPPER-003`, `SUP1-UPPER-012`, `SUP1-POWER-005`, `SUP1-POWER-006`, `SUP1-POWER-011`: biến thể mapping/accumulator/recurrence, thay toán tử hoặc thêm lỗi syntax không đủ chứng minh source độc lập. Giữ uncertain `SUP1-GEN-005`, `SUP1-SUMPAIR-003` do core recurrence gần source khác; thêm `SUP1-POWER-002`, `SUP1-COUNT-009`, `SUP1-GEN-002`, `SUP1-SUMPAIR-005`, `SUP1-SUMPAIR-006` vì tín hiệu gần protected code chưa thể kết luận từ metadata. Năm ca sau được cách ly bảo thủ, không mở Evaluation reference để cứu eligibility. Không chứng minh đã loại mọi semantic near-duplicate có shingle thấp trong lịch sử opaque. V2 vẫn có prior family/template exposure.

Trước freeze, kiểm tra chéo sửa review RANGE-005: parent đã đọc sót domain loại b=0 có sẵn trong raw recipe. Lập luận chia nguyên trong miền b≠0 hợp lệ; sửa review uncertain→pass, giữ original review và errata, không đổi source/ID/label/test. Một lần dựng metadata source freeze bị thiếu import `identity`; dừng trước manifest/seal/target. Partial staging được giữ riêng trong ignored storage; đã sửa construction trước write và chỉ có một source freeze hoàn chỉnh. Không xóa hoặc ghi đè seal để chọn lại.

**Target draft và hai boundary.** Source manifest/whitelist được seal trước khi writer tạo target. Writer tự verify parent/source/implementation/input hashes rồi gọi `require_supplement_isolation(..., stage='before_targets')` trên actual code. Có 88 diagnostic + 88 feedback mỗi L1/L2/L3 = **352 examples**. Diagnostic input chỉ gồm exam/context/policy/code/domain/compiler unavailable, không requested Level, gold/reference/teacher prose. Feedback input có cùng diagnosis và requested Level; taxonomy lấy từ diagnosis, không được suy lại theo Level. Không tokenize, chọn training hyperparameter hoặc train trong lượt này.

L1 chỉ báo còn vấn đề hoặc nhận xét sạch có giới hạn miền. L2 có vị trí/nguyên nhân/hệ quả, không ghép repair. L3 thêm hướng sửa đã review, không lời giải hoàn chỉnh. Clean L2/3 giải thích bất biến. Các mô tả vị trí/tên hàm/quote kỹ thuật giữ nguyên, phần giải thích tiếng Việt. Parent đọc các bản render, ledger bind từng example SHA-256 và ghi source-grounding, Level, ngôn ngữ, taxonomy; không coi keyword detector hoặc model judge là ground truth. Các target vẫn là **assistant-reviewed drafts**, không có xác nhận giảng viên hoặc đo chất lượng sau SFT.

Sau review, target được seal riêng và bind source manifest/seal. `before_optimizer` đã chạy **dry check**, không có optimizer được tạo. CLI `train-gate` ở cả hai stage verify đủ source/target freeze rồi kiểm lại code thực. Hai CLI positive nhận 88/88; **34 negative checks** chặn cả 12 source bị loại/uncertain cùng các ca giả family/hash, copy, rename và near-copy ở hai boundary. Unit tests còn kiểm riêng near-copy thật vượt 0.85 với identity được tính lại, control dưới ngưỡng, review stale/self-review và writer không ghi gì nếu seal/guard sai. Mọi target writer hoặc optimizer tương lai vẫn phải gọi guard ngay trong code ở đúng boundary, với đúng candidate bytes.

**Manifest và storage.** [Source freeze/ID/hash của cả 100 ứng viên và whitelist 88](TASK3_TRAIN_SUPPLEMENT_V1_FREEZE_20261021.json), [target draft freeze](TASK3_TRAIN_SUPPLEMENT_V1_TARGETS_20261021.json), [verification](TASK3_TRAIN_SUPPLEMENT_V1_VERIFICATION_20261021.json). Private root: `/workspace/llm-final-project/outputs/task3/train-supplement-v1-20261021/`. Source/generator/testcase/proof/raw review/feedback chỉ nằm ignored; Git không chứa source supplement hoặc testcase cụ thể.

| Artifact | SHA-256 |
|---|---|
|Source manifest|`c51a35301869011c960325a979d76bcb115c15caae7b104b19512687c59cac84`|
|`source-frozen/seal.json`|`f2eccd78817127e4ad8b89599912181a50efd4684b8c530c94f0af526e92b284`|
|Target manifest|`7fabd22d10a2792d3ba5fbc45109cb7bed7456f8a0760a1de919d6902c850cb2`|
|`target-frozen/seal.json`|`fbee1740f84bebea6f9875bc1e368f261dfbc3ca56be868b675d71c1f10e21e7`|
|352 draft examples|`d7b15446df10178ec04910515990472e03a8bd771152b43e935198d3f522d510`|

Từ `/workspace/llm-final-project`, kiểm snapshot hiện tại:

```bash
.venv-task3/bin/python scripts/task3_train_supplement.py verify
.venv-task3/bin/python scripts/task3_train_supplement.py train-gate \
  --candidates outputs/task3/train-supplement-v1-20261021/source-frozen/approved.private.json \
  --stage before_targets
.venv-task3/bin/python scripts/task3_train_supplement.py train-gate \
  --candidates outputs/task3/train-supplement-v1-20261021/source-frozen/approved.private.json \
  --stage before_optimizer
.venv-task3/bin/python -m pytest -q tests/test_task3*.py
```

Chuỗi đã chạy: `inventory` → private author/review → `plan` → `freeze-sources` → `targets` → private rendered-target review → `seal-targets` → `verify`. Các lệnh tạo snapshot từ chối overwrite; không rerun generator vào files đã khóa, không xóa seal. Tái dựng cần đúng archive và private author/review artifacts; Git không chứa dữ liệu riêng tư để tự tái tạo bằng một clone trống. Thay source/target/builder sau này cần version mới với parent và changelog.

**Verification:** toàn bộ `tests/test_task3*.py`: **777 passed, 4 skipped**, gồm 24 test mới. Full repository pytest không được chạy lại; môi trường trước đây thiếu sklearn cho Task1, không sửa dependency ngoài phạm vi. Bộ Task3 dùng artificial fixtures có sẵn, không phải bằng chứng đã chạy C++ supplement. Kiểm tra bytes: 566 baseline paths (tracked ban đầu cộng private Evaluation v1/v2 snapshots) và 154 protected artifacts giữ nguyên; public predictions chỉ được hash, vẫn `9ba7411c35a3461b5747be367274631d5122455335061005c695276ed76c5a45`. Kết quả review artifact độc lập và trạng thái Git trước commit ghi trong verification JSON; commit và trạng thái sau commit được bàn giao cùng báo cáo.

Tập nhận thực tế là 88 source; giới hạn đến từ độ đơn giản của 10 đề, các recurrence/mapping dùng chung và cách ly bảo thủ. Không lấy EVALUATION source hay đổi family split để tăng số. **Training configuration chưa được chọn hoặc freeze; chưa được chạy model trên Evaluation v2 để hoàn thiện tập này.**
