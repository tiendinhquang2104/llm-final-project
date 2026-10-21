# Task 3 — Evaluation v2: family-first controlled holdout

**v2 đã khóa: 60 source evaluation /18 family, 8 source train đủ điều kiện /5 family, 96 requests.** Family được phân trước khi chọn source:10 TRAIN,18 EVALUATION. V2 là **controlled holdout có prior exposure**, không phải benchmark mù. Không train, viết training target, load model, inference hay push trong lượt này. Candidate scope giữ Qwen2.5-Coder-7B-Instruct (<10B).

Điểm xuất phát `e24253df93d100d3e4e1ea1343aa37889235195a`, branch hiện tại `feat/task3-quality-round5`. Working tree ban đầu sạch; chỉ thêm file mới. Toàn bộ v1 code/report/manifest và private seal giữ nguyên bytes; không thay policy, selection hay source-reference v1.

[Manifest v2](TASK3_EVAL_V2_FREEZE_20261021.json) lưu partition, eligibility whitelist, selection/requests, archive member hashes, private artifact hashes, implementation và parent v1 digest. [Verification](TASK3_EVAL_V2_VERIFICATION_20261021.json) ghi test và kiểm tra bảo toàn.

Partition được ghi trước source selection với SHA-256 `0bbd4c383a9127b64cc9aa30d01c7a2d0f9fcac68e54f2f447aef427bedeb5df`. Không thay family sau khi thấy số nguồn bị loại. Các bước plan và verify đều đối chiếu đúng parent v1 SHA-256, không chỉ kiểm một v1 khác có seal hợp lệ.

| TRAIN family đã phân | Source còn đủ điều kiện |
|---|---:|
|SYN-COUNT|0|
|SYN-COUNTEVEN|0|
|SYN-COUNTVOWEL|1|
|SYN-GEN|0|
|SYN-MAXARR|2|
|SYN-PALIN|3|
|SYN-POWER|1|
|SYN-RANGE|0|
|SYN-SUMPAIR|0|
|SYN-UPPER|1|

Sau lọc membership train cố định, used/reserved identity và lexical near-duplicate còn14 source. Review độc lập từng source cùng ba code gần nhất từ **toàn bộ pool18 evaluation family** loại thêm6 template variants dù Jaccard<0.85, còn8 source ở5 family. Các trường hợp gần trùng gồm chung khung đọc file/P1–P4 với sửa predicate/bound/stub và chung helper/main với đổi predicate ký tự. Không chuyển family để bù số lượng.

Cả8 source train còn lại đều là single_problem; các family multi_problem TRAIN không còn ca vượt lọc. Đây là **eligibility về cách ly**, chưa phải target correctness, chưa đủ để suy fine-tuning sẽ hữu ích. Không có training targets hay optimizer run được tạo. Danh sách đầy đủ và code nằm trong sealed `train-eligible.private.json`.

Các registry v2 tách riêng:

- `family-exposure-registry.json`: mô tả family/source-pool từng được xem, gồm28 family dữ liệu hiện tại; không làm blacklist toàn family. R13 corpus/static pipeline exposure không tự biến mọi ID thành một model-output-reviewed ID. Không khẳng định source chưa từng được đọc.
- `used-identity-registry.private.json`: các identity được ghi nhận trong selected development, examples/bank/targets/output review, heldout được reserve và86 source evaluation v1 được giữ riêng. V1 source reference reserve không bị gọi nhầm là đã xem model output.
- `guard-registry.private.json`: chỉ18 EVALUATION family bị cấm toàn family cho v2; TRAIN family được phép khi source có trong whitelist và vượt ID/group/raw-source/token/identifier-rename/near checks. Exposure không được dùng làm lệnh cấm28 family.

Scope count train là root synthetic corpus đúng ZIP627 records, với fixed prepared synthetic-train membership495; real/heldout cũ không được đưa thêm vào train/evaluation để tăng quota. Các identity/history của chúng vẫn được bảo vệ. 10 family TRAIN không bị cấm chỉ vì prior exposure;5 family hết source là kết quả lọc từng code.

Chia family được khóa trước chọn60 evaluation source:56 source-reference v1 thuộc18 family được phân và4 source scoped-clean mới, đều có provenance/hash trỏ về cùng archive. Code/statement/problem/policy/annotation v2 được kiểm lại trực tiếp với archive, không cho review ghi đè. Mọi source đều đã có mức prior corpus/template exposure; không có family generalization hoặc blind claim.

| Nhóm chính thức | Annotation v2 | Source-reference | Family source-reference |
|---|---:|---:|---:|
|Lỗi biên dịch|4|4|4|
|Lỗi nhập/xuất|1|5|5|
|Lỗi logic|12|10|8|
|Lỗi vòng lặp|9|10|8|
|Lỗi mảng/chuỗi|9|9|9|
|Lỗi hàm|8|9|8|
|Lỗi edge case|2|2|2|
|Lỗi thuật toán|8|6|6|
|Lỗi hard-code|6|6|6|
|Lỗi style|1|0|0|

**Source-reference style support vẫn0 theo tiêu chí rõ ràng**, không phải quên review: chỉ gắn style khi có requirement cụ thể trong statement/policy và construct source thật sự vi phạm. Comments/TODO/tên biến/unused helper không đủ. Đề Armstrong có hạn chế phương thức gọi hàm; review các source hiện có không tìm thấy lệnh gọi bị cấm. Không thêm quy tắc style vào đề hay thêm source nhân tạo để đủ quota. Annotation v2 style support1 giữ nguyên; không sửa gold. Evaluator macro luôn đủ10 nhóm, cả nhóm không support.

| Level | Source | Defect | Scoped-clean |
|---|---:|---:|---:|
|1|19|17|2|
|2|27|24|3|
|3|8|6|2|
|4|6|4|2|

Tổng51 defect,9 scoped-clean (15%),0 unresolved source-reference;45 single_problem và15 multi_problem. Level1/2/3 =19:27:8 gần115:163:50, thêm6 L4. L3 có support cho cả9 source groups đã xác nhận bằng review; L1 thiếu edge-case và style. L4 chỉ là tập nhỏ kiểm hợp đồng, thiếu nhiều nhóm; support từng Level/loại đề có trong manifest. Requested Level không xác định taxonomy; strata được bố trí trước inference từ source review.

Counterfactual:12 source từ evaluation, mỗi source ở L1/2/3 →36 requests riêng với60 primary.5 multi-family và7 single-family; task payload giữ nguyên giữa các Level. Request IDs có prefix `v2:` để không nhầm với v1. Model inputs chỉ có source/đề/prototype/policy/compiler evidence, không có annotation, reference hay rubric finding. Primary và counterfactual scoring tách biệt.

Đã rà lại **toàn bộ19 bất đồng v1** trong ledger mới riêng tư, kể cả8 record thuộc TRAIN family nhưng identity được reserve nên không thành training target.18 giữ source-reference cũ; một lỗi literal path thay tham số được đổi primary I/O→hard-code, tránh đếm hai lần cùng nguyên nhân. Ca đổi nhóm này không thuộc evaluation v2. Có11 bất đồng trong subset evaluation60; annotation v2 không bị chỉnh. AL-vs-LG với shadowing, loop duplicate categories, function stub và style không có quy tắc được ghi rationale riêng từng ID/finding.

Có **4 source-reference compile errors** trong evaluation. Probe isolation không khả dụng: namespace `unshare --user --map-root-user --mount --net --pid --fork true` bị `Operation not permitted`; không có runner bwrap/docker/podman khả dụng. **Không gọi compiler trực tiếp trên source evaluation**, không thực thi code để kiểm phản ví dụ. Bốn ca vẫn là agent static syntax reasoning, chưa compiler-confirmed; artifact `isolation-probe.json` ghi đúng giới hạn. Không đánh dấu human-verified. Compile pass, nếu có ở bước sau, cũng không tự chứng minh sạch.

Bộ source-reference có61 findings:51 symbolic counterexamples và10 static reasoning; tất cả agent-reviewed, không human-verified hoặc executed counterexample. Các scoped-clean có invariant và miền input rõ; source-level conditions giữ riêng. Review4 clean mới độc lập xác nhận các giả thiết về ASCII/ctype, factorial64-bit, digit sums và array/index bounds.

Gates tại **cả `before_targets` và `before_optimizer`** yêu cầu source thật, tính lại code/rename/source-text hashes, đối chiếu family/ID/group/declared hashes với whitelist và kiểm protected identities +near variants. ID tự tạo, đổi family khai báo, metadata/hash giả hoặc code thay đổi đều bị chặn.6 source bị manual audit loại không thể được đưa lại dưới whitelist v2.8 source hợp lệ qua cả hai boundary;60 source evaluation bị từ chối ở cả hai. Các script train cũ giữ nguyên để bảo toàn v1; bước fine-tuning sau phải gọi v2 verify+guard trong target writer và trước optimizer, không chỉ gọi CLI một lần rồi thay source.

Kiểm thử: **753 passed,4 skipped** cho `tests/test_task3*.py`, gồm29 test v2 mới. Artifact audit độc lập cuối qua204 kiểm tra, không còn vấn đề quan trọng; chi tiết/hash trong Verification JSON. Regression gồm positive eligibility trên family đã phơi nhiễm, spoof source/metadata, renamed/near variants, manual review đủ ID, immutable archive/gold, exact v1 parent binding, no-public/no-prediction planning và v1 byte preservation. Toàn bộ540 baseline file (529 tracked ban đầu và11 private sealed v1 files) cùng154 artifact được bảo vệ giữ nguyên bytes. Root public predictions chỉ hash trong preservation check, không parse/chọn mẫu; SHA-256 vẫn `9ba7411c35a3461b5747be367274631d5122455335061005c695276ed76c5a45`.

Evaluator offline giữ hai bảng annotation-v2/source-reference và đủ10 nhãn; unresolved/abstention khác `[]`, error không hưởng exact-clean. Semantic feedback cần ledger gắn đúng prediction hash và source rationale; thiếu review là pending. Không keyword gate/LLM judge nào làm ground truth. Empty-prediction smoke chỉ là fixture:60 unresolved,0 exact-clean reward,12 incomplete triples, không phải một lượt model inference.

Private snapshot tuyệt đối: `/workspace/llm-final-project/outputs/task3/eval-freeze-v2-20261021/frozen`. Source, statement, quote, finding và audit chi tiết chỉ nằm dưới ignored storage. Hash các file sealed:

| Artifact | SHA-256 |
|---|---|
|`code-review-followup.private.json`|`d6ffb1f351187fa736c8998c5b5e496c50c92eb6d7baa292cf006e7348112148`|
|`code-review.private.json`|`027f5d884fcdb9b17dc63ff9bb2a06ca679faba338e2edc8b9506f1fa3bdd9a9`|
|`disagreement-review.private.json`|`722881edc3ef251e038462526b0ef2c0f96f7280a568b29a7c4664039e8493de`|
|`family-exposure-registry.json`|`f355b9fc5a5bfd0907d16957d968deaa285a468f9ad2d0bd1c956f294f09fc77`|
|`family-partition.json`|`0bbd4c383a9127b64cc9aa30d01c7a2d0f9fcac68e54f2f447aef427bedeb5df`|
|`guard-registry.private.json`|`148e889efa0c6b9bf9dff42a6650ea47b05950ec3d97aaa0dce129abb555c5d2`|
|`isolation-probe.json`|`29965748ef81b7ee71659c25ece5bc992e9a71c0a0740b63ab32bf5f033f6d93`|
|`metric-definitions.json`|`c2190e8b475fccd38fc0d45a0355fe969febb1f8238de4ae186dc28652a4d39d`|
|`model-inputs.private.json`|`425b509e0068ecebdd2fa0e030920d6a9bd194c631e5db65e96cbf584d2e30f9`|
|`policy.json`|`436408c0359749e4ff5e1bf730293a5bdcc484a452a974d277e910582d3181e0`|
|`prefreeze-final-report.json`|`c98eea874f243f11234991d82ce7d94da143217cc68fb280eff2d86cc5c5d2c4`|
|`reference.private.json`|`66e445413b112e7c7c41a7dfb4eaa964993aa4ad20be15651401003eb84a4809`|
|`review-packet.private.json`|`16834213b7f632ed745c5c890f15fe58dc6b2c3811ecdd632d9ef844591f44b6`|
|`train-eligible.private.json`|`cb624bfcd0057f5d6379736d35ef1fc82c5456ac437b179047851741d49638eb`|
|`train-near-review.private.json`|`99ebcf092ea40407fd8302c50ac8fee4635dc7a3be2474957fdf2e271ab90cfa`|
|`train-rejections.private.json`|`be89495139bdf8a30c398672b4aed976c199372e24b5f9eaeb71d8d4dd1286cc`|
|`used-identity-registry.private.json`|`d51a0a97a2de8a07ff2727b7946332a3105f14e26083f5eca2e8b0da62e9ca0d`|

Manifest v2 SHA-256: `24c8de5781d090a15753d1ef6534122cbe836846db5cb3300bc3f07c28e89bab`.
Seal v2 SHA-256: `1829df225a3b4443f5afad22bb07763170683b122b85a91aa951422f2250f40c`.
Parent v1 manifest SHA-256 giữ nguyên: `f7693da146b174faefd12fae96f9a7a3fbca118c1f8fd01d164d16b30d619e83`; seal v1 giữ nguyên `3276cb4fa2990330fcd6d9f92e0b691db352090452146db02abb0e3cda94f2f1`.

Các audit được chuẩn hóa JSON khi copy vào seal, nên hash file sealed có thể khác raw input audit; cả raw source-input hashes và sealed hashes đều nằm trong manifest. `prefreeze-report.json` bên ngoài seal giữ báo cáo sơ bộ14 source; `prefreeze-final-report.json` khóa báo cáo8 source sau manual exclusions. Số8/5 và coverage evaluation đã báo trước freeze; không có điều chỉnh sau model output.

Lệnh từ `/workspace/llm-final-project`:

```bash
.venv-task3/bin/python scripts/task3_freeze_eval_v2.py verify
.venv-task3/bin/python scripts/task3_freeze_eval.py verify
.venv-task3/bin/python scripts/task3_freeze_eval_v2.py train-gate \
  --candidates outputs/task3/eval-freeze-v2-20261021/frozen/train-eligible.private.json \
  --stage before_targets
.venv-task3/bin/python scripts/task3_freeze_eval_v2.py train-gate \
  --candidates outputs/task3/eval-freeze-v2-20261021/frozen/train-eligible.private.json \
  --stage before_optimizer
```

Các lệnh chuẩn bị `plan` rồi `freeze` đã chạy sau family partition/source audit. Chạy lại từ chối ghi đè; dùng `verify` cho snapshot hiện tại. Không xóa seal/đổi family để chọn lại. Tăng train set cần một manifest/whitelist được version và review riêng; không lách guard của snapshot này.

Offline scoring prediction tương lai, không chạy model:

```bash
.venv-task3/bin/python scripts/task3_freeze_eval_v2.py review-template \
  --predictions outputs/task3/eval-v2-step2/METHOD.predictions.json \
  --output outputs/task3/eval-v2-step2/METHOD.review-template.json
.venv-task3/bin/python scripts/task3_freeze_eval_v2.py evaluate \
  --predictions outputs/task3/eval-v2-step2/METHOD.predictions.json \
  --ledger outputs/task3/eval-v2-step2/METHOD.reviewed-ledger.json \
  --output outputs/task3/eval-v2-step2/METHOD.evaluation.json
```

Bỏ `--ledger` để chỉ tái tính taxonomy/completion và giữ semantic pending. Predictions là list có `request_id,status,output` hoặc `raw_text`; IDs lấy từ manifest v2. Lượt hiện tại kết thúc ở freeze/test/commit, chưa train hoặc inference.
