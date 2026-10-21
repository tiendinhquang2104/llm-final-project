# Task 3 — Một pilot DIRECT SFT 7B, development evaluation (2026-10-21)

**Đã chạy đúng một optimizer pilot DIRECT SFT và một pass60primary cho mỗi nhánh. Adapter tăng taxonomy và giảm L1 false-clean/L2 repair leak, nhưng L2 đúng vị trí/nguyên nhân không tăng, L3 chưa có hướng sửa khả thi và còn2flag ngữ nghĩa pending. Không đạt tiêu chí feedback đã khóa: giữ R15 production, không tạo candidate328, không public inference/leaderboard/push.** Nhánh thử nghiệm SHORT/two-stage đóng tại báo cáo cũ; lượt này không tạo diagnosis JSON trung gian hay train chain-of-thought.

HEAD trước lượt này `709e5a2d02f8293690b7475b9dc293d8ba8d97fb`, branch `feat/task3-quality-round5`; working tree ban đầu sạch. Chỉ thêm file mới. Các seal/gate lịch sử, R15 và predictions gốc không sửa. Evaluation v2 được dùng lại như **development có prior exposure**, không phải benchmark mù. Protocol DIRECT mới cho phép chung family nhưng chặn identity/source/group/near-duplicate; không mở lại hoặc bypass gate family-disjoint cũ.

## Kiểm kê thực tế và protocol cách ly mới

ZIP được kiểm bằng bytes SHA-256 `6bda70c29254a3bce91933b65f4a311d73a052e72d181c97e977152e14602f9b`: **627root records,65heldout records,1.168file members được hash**. Không suy version từ tên. Synthetic dùng source/annotation hiện tại trong ZIP và membership train đã chuẩn bị; real dùng source/context hiện có cùng fixed real train IDs, có hash từng file. Không lấy con số eligibility cũ làm đầu vào.

| Bước | Real | Synthetic ZIP | Supplement riêng | Tổng |
|---|---:|---:|---:|---:|
|Membership train hiện tại|26|495|0|521|
|Sau gate/dedup identity và near|25|131|0|156|
|Chọn review trước target|25|75|0|100|
|Giữ sau source/annotation audit|14|50|0|64|
|Thêm scoped-clean TRAIN supplement được gate riêng|0|0|6|6|
|Dataset được khóa, trước split|14|50|6|70|
|**Thực sự vào optimizer**|**11**|**42**|**3**|**56**|
|Internal validation, không optimizer|3|8|3|14|

Trong521candidate,365 bị loại do identity/variant/near hoặc trùng candidate; thêm132root ZIP không thuộc membership train hiện tại nên chưa bao giờ được admit. Artifact excluded có497rows =365+132; các reason counts có thể chồng nhau, không cộng chúng thành số source độc lập. Không đổi split gốc để đưa132record ấy vào train.

New registry bảo vệ506identity variants, gồm328public fingerprints,60Evaluationv2 source, heldout mới/cũ và real-val. Public chỉ được đọc ID/code-file reference và source bytes để tạo fingerprint loại leakage; không lấy statement, requested Level, feedback, predictions, điểm hoặc prompt public làm training signal. Không có public model call. Dữ liệu đưa vào model đều đến từ TRAIN hoặc safe development projection.

Gate mới `require_direct_isolation` tái tính actual code tại cả `before_targets` và `before_optimizer`: ID/group/raw SHA/decoded SHA/token identity/identifier-renamed identity và shingle Jaccard>=0.85. Thiếu source/signature bị từ chối. Registry whitelist và thresholds được khóa; family exposure là metadata, không là lệnh cấm. Cả88source supplement đã được screen; chỉ18scoped-clean hợp lệ được whitelist thêm, chọn6 để fresh-review. Supplement không nằm trong ZIP và luôn ghi origin riêng. Inventory gốc giữ bytes, extension có manifest/hash riêng.

Actual optimizer56source thuộc24family, **trùng15/18Evaluationv2 family**; toàn bộ pool eligible có overlap cả18. Vì vậy không còn claim family-disjoint cho thí nghiệm DIRECT này. Gate loại lexical near-duplicate ở ngưỡng đã nêu, không chứng minh loại hết semantic/template tương đồng; các motif và nhiều family đã xuất hiện trong nghiên cứu trước.

## Target audit và source-level split

Selection100source gốc và6supplement được ghi trước target/model generation; có khám phá source TRAIN trước selection, đã khai báo, không gọi metadata-only hay blind selection. Review toàn bộ106source; các positive label thiếu căn cứ, clean annotation có defect, mapping mâu thuẫn, style thiếu quy tắc và whitespace I/O chưa rõ checker đều bị loại. **Không sửa label để ép gold.**

| Lý do loại khỏi100source gốc | Source |
|---|---:|
|Annotation thiếu/mâu thuẫn source|6|
|Taxonomy mapping chưa chốt|4|
|Annotation rỗng nhưng source có defect|15|
|Loop-positive thiếu căn cứ|1|
|Style-positive thiếu quy tắc rõ|4|
|I/O chỉ whitespace, quy tắc chưa rõ|6|
|Tổng|36|

Loại36/100source (36%) và108/300derived examples (36%).64source gốc giữ nguyên tập annotation khi được review source hỗ trợ. Thêm6supplement, tổng70source/210target mới. Feedback giảng viên chỉ là tài liệu tham chiếu; **210/210feedback được viết mới**, không sao chép teacher prose. Supplement labels là agent-authored, không giả là annotation ZIP. Mỗi target có đúng `{taxonomy_error,feedback}`; không diagnosis, witness tự tạo, tự xưng đã kiểm chứng hay chain-of-thought.

Label-space definitions trong ZIP là chuẩn: L1 không vị trí/cause/repair; L2 vị trí/cause không repair; L3 thêm hướng sửa không full solution. Lượt này train L1/L2/L3, **không có supervised L4**. Cả9nhóm có căn cứ trong pool được review; style support0 và không bịa quota.

Agent audit toàn bộ70source/210target; reviewer độc lập kiểm thêm37source/111target gồm tất cả real/clean và strata hiếm. Bắt1L2 repair leak, sửa **1/210target (0.476%)** trong v2 riêng,0label changes. Giữ v1targets/audit và before/after hashes. Independent recheck v2 pass trước optimizer. Đây là **agent static review, không human-verified**; không bảo đảm tất cả target đúng hoặc đủ mọi lỗi.

Dataset có7scoped-clean/63defect. Sáu supplement giữ constraints nguyên bản, được projection sang statement để model thấy scope, không đưa clean-basis/proof vào input. Clean ZIP còn lại dùng precondition không rỗng của phép min; caveat giữ trong review, không tự coi file rỗng là được xử lý. Các scope giới hạn ASCII/count/range/overflow phải đọc cùng proof. Sáu source có constraints supplement đều clean, nên có nguy cơ model học cue từ context; lượt này không tách hiệu ứng đó.

Compiler-confirmed/testcase-executed=0. Probe mới: bwrap không được cài; `unshare --user --map-root-user --net --pid --fork /bin/true` bị Operation not permitted. Không compile/run student code trên host. Syntax findings là suy luận tĩnh, không giả diagnostic/compiler pass. Thiếu sandbox không chặn optimizer.

Split theo source/group/near-connected component,seed42, khoảng80/20; mọi Level của cùng source ở cùng phía. Train56source:52defect+4clean; validation14:11defect+3clean. Nhiều Level không tạo thêm source độc lập.

| Nhãn, support theo source | Optimizer TRAIN | Internal validation |
|---|---:|---:|
|Lỗi biên dịch|15|3|
|Lỗi nhập/xuất|3|2|
|Lỗi logic|13|0|
|Lỗi vòng lặp|8|1|
|Lỗi mảng/chuỗi|6|0|
|Lỗi hàm|10|5|
|Lỗi edge case|7|0|
|Lỗi thuật toán|1|0|
|Lỗi hard-code|4|2|
|Lỗi style|0|0|

Validation thiếu logic/AR/edge/algorithm/style, train algorithm chỉ1source; validation loss không chứng minh giữ được các nhóm này. Source và group tách không tạo benchmark family mới.

## Freeze và đúng một optimizer run

[Config](../../configs/task3/direct_sft_v1_20261021.json), [freeze metadata](TASK3_DIRECT_SFT_V1_FREEZE_20261021.json), [plan](../../docs/superpowers/plans/2026-10-21-task3-direct-sft-v1.md). Dataset, split, native R15 zero-shot prompt, rubric,77runtime files cùng library versions và decoder khóa trước optimizer. Private manifest SHA `a838199811b6dafe0c7b8f5264ae2e77b7b8e977a02d35ceb39c8f7bd82a1d55`. Model input chỉ projection đề/problem/prototype/policy/code/compiler-unavailable/Level; không teacher/reference/proof. Output assistant trực tiếp đúng hai trường.

Dùng base Qwen/Qwen2.5-Coder-7B-Instruct revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`, không load adapter cũ.7,615,616,512base logical params +40,370,176LoRA params ≈7.656B, dưới10B. RTX5090 32GB,196actual bitsandbytes layers,NF4 double quant/BF16 compute. LoRA r16/alpha32/dropout.05 trên q/k/v/o/gate/up/down; lr1e-4 cosine,warmup.03,batch1×accum4,seed42,2epochs. Ngưỡng preflight16GiB khi đo free~18.5GiB; không dừng/đổi R15 production để lấy VRAM.

Loss chỉ assistant final JSON và end-of-turn; prompt/header/padding mask bằng actual tokenizer prefix check. CE trung bình trong example, validation mean trong source rồi equal-source mean. Unit direct weights, không diagnostic weighting/sampling. Cap8192, fail nếu vượt, không truncate.

| Token audit / epoch | Train | Validation |
|---|---:|---:|
|Source / examples|56 /168|14 /42|
|L1/L2/L3 examples|56/56/56|14/14/14|
|Input+target tokens|162233|44271|
|Supervised tokens|10970|2706|
|Sequence dài nhất|3705|2499|

Một optimizer run/84steps;336example exposures,324466input+target tokens,21940supervised tokens trong2epochs. Durable exclusive marker chặn resume/train lần hai. New gate và actual source/context/target→tensor binding recheck trước optimizer setup và step đầu.84/84gradient checks hữu hạn/khác0; LoRA update hữu hạn/khác0.

Validation trước train2.263735; epoch1=1.002983,epoch2=0.949324. Chọn epoch2 bằng min internal validation equal-source CE, earliest tie; hoàn tất selection trước development inference. Adapter tensor SHA `a193807c8e21c1d4bd9d826717e9c40dc32d6f18f891e39a78a7517f4c21de3e`. Không dùng Evaluationv2 hoặc public để chọn epoch. Loss giảm không phải tiêu chí thành công phương pháp.

Load/train/save195.55s; training wall162.57s gồm validation/save callbacks. Peak allocated14.66GiB, reserved16.93GiB. Không optimizer run hoặc adapter thử thêm.

## Paired60primary — output direct và cùng controller

R15 BASE và DIRECT SFT dùng cùng native R15 prompt/parser/disclosure guard/retry<=3/fallback policy; chỉ adapter khác.60/60first system+user payload và decoder hashes bằng nhau; retry message sau đó có thể khác do output. Greedy,seed42,NF4double/BF16,context16384,cap1024/L4cap1536,deadline60s. Không few-shot. R15 production code không sửa; deadline là giá trị khóa cho paired pilot. Safe model input projection60primary lấy nguyên từ sealv2, không reference/ledger vào model. Không chạy36CF và không claim taxonomy invariance.

| Completion/chi phí | BASE | DIRECT SFT |
|---|---:|---:|
|Final completed /60|60|60|
|L1/L2/L3/L4 completed|19/27/8/6|19/27/8/6|
|Schema-error/runtime-error/unresolved final|0/0/0|0/0/0|
|Raw generation calls|77|61|
|Raw schema valid|76/77|61/61|
|Extra retry calls|17|1|
|Fallback finals|6|0|
|Generation latency tổng,s|90.98|87.72|
|Input/output tokens|59017/5303|45338/2971|
|Final characters mean/median|123.55/113|108.87/99|
|Final words mean/median|28.20/26|24.72/23|

Không gọi schema/quote compliance là semantic correctness. Latency là generation-only, không end-to-end/model load/train; không đủ cơ sở tuyên bố tốc độ phương pháp tốt hơn. BASE fallback giữ taxonomy, đổi feedback; mọi raw/final/decision/prompt/config hash giữ riêng.

## Taxonomy: annotation và source-reference tách biệt

60primary là60source độc lập theo trọng số báo cáo. Micro/macro đủ10nhãn,zero_division0; style annotation support1/source support0 vẫn ở macro. Các reference bất đồng giữ nguyên. Missing không nhận exact-clean (thực tế cả2arm hoàn tất đủ60).

| Metric | BASE | DIRECT SFT |
|---|---:|---:|
|Annotation v2 micro-F1|0.1818|0.5200|
|Annotation v2 macro-F1|0.0826|0.3844|
|Annotation v2 exact set /60|13|33|
|Source-reference micro-F1|0.1400|0.4950|
|Source-reference macro-F1|0.0744|0.3725|
|Source-reference exact set /60|11|30|

| Level, requests | Annotation micro BASE/SFT | Annotation macro BASE/SFT | Source micro BASE/SFT | Source macro BASE/SFT | Exact annotation BASE/SFT | Exact source BASE/SFT |
|---|---|---|---|---|---|---|
|L1, 19|0.0000/0.5000|0.0000/0.3524|0.0870/0.5000|0.0250/0.3476|3/10|3/9|
|L2, 27|0.3265/0.6047|0.1300/0.4411|0.2041/0.5581|0.1086/0.4311|8/16|6/14|
|L3, 8|0.1111/0.2353|0.0250/0.0900|0.1053/0.2222|0.0250/0.0900|1/2|1/2|
|L4, 6|0.0000/0.7500|0.0000/0.2667|0.0000/0.7500|0.0000/0.2667|1/5|1/5|

Per-label: ô là TP/FP/FN;F1. Support không cộng thành số source vì multi-label.

|Annotation v2|Support|BASE|DIRECT SFT|
|---|---:|---|---|
|Lỗi biên dịch|4|2/2/2;0.5000|3/0/1;0.8571|
|Lỗi nhập/xuất|1|0/4/1;0.0000|0/0/1;0.0000|
|Lỗi logic|12|7/24/5;0.3256|5/6/7;0.4348|
|Lỗi vòng lặp|9|0/0/9;0.0000|4/6/5;0.4211|
|Lỗi mảng/chuỗi|9|0/0/9;0.0000|5/0/4;0.7143|
|Lỗi hàm|8|0/0/8;0.0000|6/2/2;0.7500|
|Lỗi edge case|2|0/0/2;0.0000|0/0/2;0.0000|
|Lỗi thuật toán|8|0/0/8;0.0000|0/0/8;0.0000|
|Lỗi hard-code|6|0/0/6;0.0000|3/0/3;0.6667|
|Lỗi style|1|0/0/1;0.0000|0/0/1;0.0000|

|Source-reference|Support|BASE|DIRECT SFT|
|---|---:|---|---|
|Lỗi biên dịch|4|2/2/2;0.5000|3/0/1;0.8571|
|Lỗi nhập/xuất|5|0/4/5;0.0000|0/0/5;0.0000|
|Lỗi logic|10|5/26/5;0.2439|4/7/6;0.3810|
|Lỗi vòng lặp|10|0/0/10;0.0000|4/6/6;0.4000|
|Lỗi mảng/chuỗi|9|0/0/9;0.0000|5/0/4;0.7143|
|Lỗi hàm|9|0/0/9;0.0000|6/2/3;0.7059|
|Lỗi edge case|2|0/0/2;0.0000|0/0/2;0.0000|
|Lỗi thuật toán|6|0/0/6;0.0000|0/0/6;0.0000|
|Lỗi hard-code|6|0/0/6;0.0000|3/0/3;0.6667|
|Lỗi style|0|0/0/0;0.0000|0/0/0;0.0000|

Gain rõ ở compiler/hard-code/function/array/loop và giảm logic false positives; edge/I/O/algorithm/style chưa có TP. Không gọi đây là generalization sang family mới hoặc reasoning gain.

## Review feedback theo source và Level

Review **toàn bộ60source ×2arms**, chia hai nửa cố định, không chọn ca theo output và không xem aggregate F1 trước verdict. Ledger gắn exact output digest,source proof/reviewer/rationale; static agent review, không human-verified. Reference chỉ được mở sau khi training/selection và cả2arm hoàn tất. Claim cụ thể sai tách khỏi taxonomy mismatch hoặc generic concern. Không suy output xác định sau undefined behavior.

Tất cả120final có review record. Hai SFT false-claim flags còn null (ARM-0026 L2,GCDARR-0009 L3) vì diễn đạt mơ hồ, không biến null thành false/pass. Trong JSON, field `reviewed=58` nghĩa false-claim flags đã chốt58, **không phải thiếu2review/source/output**. L2 strict pending1 vì giao với false-claim flag ấy.

| Feedback trên tập cố định | BASE | DIRECT SFT |
|---|---:|---:|
|Final/source pairs thực sự đã review|60/60|60/60|
|Material false technical claim|32/60|15/58 +2pending|
|False-clean assurance trên51defect|12/51|1/51|
|Taxonomy[] trên51defect (khác assurance)|16/51|12/51|
|L1 false-clean trên17defect|9/17|0/17|
|L1 disclosure trên19final|2/19|0/19|
|L2 đúng vị trí+nguyên nhân trên24defect|11/24|10/24|
|L2 concrete repair leak trên27final|6/27|0/27|
|L2 useful AND không repair/false claim|7/24|9/23 +1pending|
|L2 bỏ core finding trên24defect|13/24|14/24|
|L3 cause+feasible repair trên6defect|1/6|0/6|
|L3 useful AND không false claim|0/6|0/6|
|L4 bỏ core finding trên4defect|1/4|1/4|

BASE L3 positive duy nhất có hướng modulo khả thi nhưng thêm một ngoại lệ số học sai; strict L3 vẫn0. Không biến nó thành một lời giải hoàn toàn đúng. SFT chưa cung cấp direction khả thi ở6defect L3. L1 generic concern giảm assurance/disclosure nhưng không tự xác nhận đã hiểu nguyên nhân.

| Level | Defect/clean | BASE false claim | SFT false claim | BASE/SFT missing-core, defect |
|---|---:|---:|---:|---|
|L1|17/2|10/19|0/19|12/17 →7/17|
|L2|24/3|15/27|8/26 +1pending|13/24 →14/24|
|L3|6/2|5/8|5/7 +1pending|1/6 →2/6|
|L4|4/2|2/6|2/6|1/4 →1/4|

Trên58ID common-assessed false-claim: BASE31/58,SFT15/58. Trên23defect L2 common-assessed strict:7/23→9/23. Kể cả gán cả2pending thành false-claim thì SFT tối đa17/60, vẫn thấp hơn32/60; vẫn không tự chốt verdict để pass gate. L2 strict gain chủ yếu đi cùng giảm repair leak, trong khi count đúng cause thuần không tăng. Claim-record rates không là atomic-claim precision; SFT ngắn hơn và có ít cơ hội phát biểu kỹ thuật hơn.

Evidence đầy đủ cho mọi60case và cả2output ở private `review/semantic-{a,b}.private.json`, combined cases và `ledger-{BASE,SFT}.private.json`. Vài ví dụ cân bằng (chỉ metadata/rationale dưới đây, source/raw/proof chi tiết giữ private):

| Source, tiền tốSYN- | Level | Paired observation |
|---|---:|---|
|ARM-0000/ARM-0027,COUNTGT-0005,SUMB-0003/SUMB-0005|1|SFT đổi assurance sạch sai của BASE thành concern nhẹ; gain contract, không chứng minh diagnosis reasoning.|
|DIGITSUM-0006|2|SFT giữ location/cause và bỏ replacement directive của BASE.|
|FACT-0008,SUMB-0034|2|SFT nêu missing semicolon có căn cứ; BASE nêu sai token/cause. Static grammar review, không compiler-confirmed.|
|COUNTUPPER-0007|2|SFT xác nhận sai điều kiện strict bounds đang bỏ hai endpoint, còn false-clean.|
|FIB-0007|2|SFT bịa thiếu base case dù source đã có; không nhận gain theo label đơn thuần.|
|MAXDIFF-0007,REVSTR-0007|2|SFT mất cause đúng của BASE và đưa nguyên nhân khác không được source hỗ trợ.|
|DIGITSUM-0016|3|SFT lẫn digit count/sum, không có feasible repair; BASE cũng chưa đủ strict usefulness.|
|GCDARR-0009|3|SFT có finding giới hạn fold nhưng thiếu hướng sửa; một claim còn mơ hồ được giữ pending.|

**Quyết định đã khóa trước output:** SFT phải complete60/60, không pending; micro và macro cao hơn BASE ở cả2reference; false claims thấp hơn; strict L2 rate cao hơn; L1 false-clean không tăng; L3 rate không giảm và có ít nhất1feasible repair. Các điều kiện là conjunctive. Lượt này taxonomy/L1/leak/strict L2 đạt phần tương ứng, **L3 và completeness của semantic verdict không đạt**. Không lấy F1/loss thay feedback correctness. Không đổi prompt/threshold/checkpoint để cứu kết quả; không candidate328/public call/submission.

## Artifacts và tái kiểm

[Results metadata](TASK3_DIRECT_SFT_V1_RESULTS_20261021.json), [verification metadata](TASK3_DIRECT_SFT_V1_VERIFICATION_20261021.json) chứa metrics hai reference,per-Level/per-label, mọi raw/final digest, costs và decision; không có source,raw text,teacher hoặc private review proof. Private root: `/workspace/llm-final-project/outputs/task3/direct-sft-v1-20261021/`:

- `data/`: actual ZIP inventory, source/group fingerprints, excluded reasons, whitelist và additive supplement extension.
- `targets/`: fixed selections, source/targets v1,v2, audit/exclusions/scope projection; source-specific writer/provenance giữ ignored.
- `frozen/`: source split,examples,safe development inputs,config/token audit/rubric/manifest/seal.
- `training/`: một marker/attempt,epoch1/2,selected adapter,gradient/source gates và logs.
- `inference/arm-{BASE,SFT}/`: actual messages/raw/config/tokens/timing/legacy attempts+decisions/final predictions/status.
- `review/`: independent pretrain37source audit,v2fix recheck, toàn bộ60paired source reviews,533integrity checks và297score checks.

Reporter offline từng thiếu chặn relevant semantic flags pending; artificial regression bắt và sửa trước aggregate scoring. Chỉ reporter/test mới đổi; runtime/model/prompt/controller/seal không đổi. Report không thưởng pending hoặc missing. Rà soát độc lập tái tính per-label/micro/macro/Level/semantic intersections và gate, khớp artifact cuối.

Commands đã chạy từ repo, **không phải hướng dẫn train/infer lần hai**:

```bash
.venv-task3/bin/python scripts/task3_direct_sft_inventory.py inventory
.venv-task3/bin/python scripts/task3_direct_sft_inventory.py supplement
.venv-task3/bin/python scripts/task3_direct_sft_inventory.py verify
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HOME=/workspace/llm-final-project/outputs/task3/hf-cache .venv-task3/bin/python scripts/task3_direct_sft_prepare.py prepare
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HOME=/workspace/llm-final-project/outputs/task3/hf-cache .venv-task3/bin/python scripts/task3_direct_sft_train.py --run
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HOME=/workspace/llm-final-project/outputs/task3/hf-cache .venv-task3/bin/python scripts/task3_direct_sft_infer.py --arm BASE --start
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HOME=/workspace/llm-final-project/outputs/task3/hf-cache .venv-task3/bin/python scripts/task3_direct_sft_infer.py --arm SFT --start
.venv-task3/bin/python scripts/task3_direct_sft_report.py --score
.venv-task3/bin/python scripts/task3_direct_sft_prepare.py verify
.venv-task3/bin/python -m pytest -q tests/test_task3*.py
.venv-task3/bin/python -m pytest -q
```

Inventory/prepare/start/report ghi exclusive; optimizer marker không được xóa để resume. Target authoring là source curation có review, cần private target/source artifacts đã lưu; không có cách tái tạo teacher-free prose bằng một detector máy rồi coi nó là verified. Dùng `verify` để tái kiểm hiện trạng, không mở lại seal.

Verification cuối: **989passed,2skipped Task3**, gồm43test mới cho direct protocol; global pytest vẫn2Task1 collection errors thiếu sklearn, không cài dependency ngoài phạm vi và không tuyên bố full-repo pass. Source compiler probe và các static judgments được ghi riêng. **663file baseline giữ nguyên bytes**, gồm R15/tracked history,các seal,contract-v1 raw và bundle24; public predictions chỉ hash, vẫn `9ba7411c35a3461b5747be367274631d5122455335061005c695276ed76c5a45`. Commit chỉ file mới code/config/test/metadata/report; HEAD cuối bàn giao trong chat. Không push.
