# Round23 — offline checkpoint, chưa chạy model

User chuyển GPU server vì server hiện tại quá tải. **Đã hoàn tất audit offline và freeze, chưa load model/gọi Qwen Round23.** Giữ R15 production; chưa chấm gate, chưa renderer. Pending không phải0 điểm hay kết luận candidate thất bại.

Branch `feat/task3-quality-round5`, HEAD ban đầu `a6a4c8e25dc59cfa4ae631819c0acde80fa941cd`. Snapshot bảo vệ3.173 file cũ. Không push/train/public inference/submission; original gold và COUNT0004/PERFECT0000 vẫn quarantine.

## Audit Round22

Đã verify218 manifest entries của bundle Round22, SHA `1643323538f657770fd22ed045da64f3b085d83b7ee4a781fd8a57046a7bb7f9`. Audit đủ96 attempts/48ID, mọi lần compile/run để chấm lại đều trong chroot+UID/seccomp/rlimits. Một agent khác review source độc lập; **not human-verified**.

|Dimension|Attempts /96|
|---|---:|
|Schema nguyên trạng hợp lệ|2|
|Chỉ empty files stdin: schema hợp lệ|26|
|Chỉ source whitespace: schema hợp lệ|14|
|Cả hai chuẩn hóa: schema hợp lệ|43|
|Schema cứu hoàn toàn cơ học|41|
|Input sai miền|41|
|Uncertain, không có input để chấm|1|
|Valid input nhưng không lộ mutant|6|
|Predicted actual sai, trên valid input|18|
|Predicted expected sai, trên valid input|21|
|Cơ chế đúng /sai /unknown|37 /58 /1|
|Exact proposed taxonomy đúng /sai /thiếu-unknown|11 /38 /47|

Dimension chồng lấp, không cộng thành phân bố nguyên nhân loại trừ nhau.54 proposals có input hợp lệ. Không sửa nghĩa response/nhãn, không best-of, không đổi điểm vận hành Round22. Proposed canonical taxonomy có ambiguity và chưa human-verified; tám bất đồng với review tác giả cũ được giữ.

Theo attempt cố định, sau mechanical normalization: attempt1 có9 non-uncertain schema-valid,7 valid input, chỉ1 đồng thời đúng actual/expected; attempt2 tương ứng33,16,4. Thêm cơ chế/exact proposed taxonomy thì paired hậu kiểm0/24 ở từng attempt, không ghép response đẹp. Format là rào cản lớn nhưng sửa format không đủ. Chưa có kết quả nhân quả của short contract/execution mới.

## Protocol đã khóa

40 cặp/80ID:24 cặp Round22 development và16 evaluation mới từ allowed train, thuộc16 family. Bốn family không có trong Round22: UPPER,COUNT,MAXDIFF,COUNTEVEN;12 family còn lại overlap. **Không blind**, không coi family là quan sát thống kê độc lập.32 new sources:0 exact/renamed matches,0 similarity≥0,75, max0,51724 trong allowed history đã audit; không chứng minh độc lập ngữ nghĩa.

New baselines khớp326 tests, thêm100 separate P3 probe executions. Independent reviewer kiểm326 expected values, xem hash-bound logs và source, không rerun C++. Parser EOF boundary và CSV newline mismatch được sửa trước freeze. File scope thống nhất filename/comma CSV/LF-CRLF. Development CSV context changes ghi riêng, không gọi lợi ích đó thuần format.

Contract7 field, code điền file mapping/source positions; parser bảo toàn literals/operators và không sửa arithmetic/nhãn. Hai diagnosis arms dùng chung first call; execution chỉ chạy valid input của chính source rồi cung cấp actual cho một continuation giữ input cố định. Expected không lấy từ oracle. Không retry/fallback. Supplied actual không phải dự đoán độc lập; additional-call budget là confound. Native R15 không đổi.

Qwen7B revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`, NF4/BF16 CUDA, greedy seed42. Gate evaluation:≥8/16 strict pairs, hơn R15 exact-taxonomy pairs≥2,≥12/16 numerical trustworthy mutant witnesses và không thêm false-clean. Chỉ arm qua gate mới được render/review Level1–3; Level2 leak hoặc Level3 không hữu ích thì giữ R15.

Freeze SHA **`2f2ed935da3fdd35d66ada15b861e036acd3909b478ea79d3bc57609cb7ebeb5`**.80 real-tokenizer preflights fit context; max R15 input1.001 tokens, short932. Code review không còn material finding;30 new tests pass. Focused suite198 passed/3 confinement tests skipped khi không đặt env; chạy riêng confinement suite8 passed, gồm cả3 actual probes.

## Handoff

Đọc `TASK3_ROUND23_HANDOFF_20261022.md`. Private root `outputs/task3/round23-20261022/` giữ audit từng attempt, source/tests/oracles/actuals, reviews, freeze và80 initial prompts. Transfer gồm Git bundle toàn branch và private resume archive có rootfs/jails/source-binary bindings, manifest/checksum; không weights/virtualenv/public data. Commit/paths/hash thực nằm trong `transfer-handoff.json` được tạo sau commit.

Còn lại: chạy80ID/ba nhánh trên GPU mới; collect numerical evidence theo frozen scorer, independent review mechanism/taxonomy; tạo80-row `id-metrics.private.json` và `post-inference-review-freeze.json`; chạy report; chỉ render nếu gate pass; commit kết quả/bundle cuối. Chưa có final Round23 metrics. Hiện execution chỉ được chứng minh trên scoped synthetic harness, chưa có triển khai chung cho mọi đề Task3 thực.
