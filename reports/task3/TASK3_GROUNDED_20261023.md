# Task 3 grounded findings / Level views — 23/10/2026

**Giữ R15; không có winner và không tạo public candidate mới.** Phương pháp mới
đã xử lý đủ 60 ID, nhưng chỉ 5 diagnosis resolve; C1 có 4 output và C2 có 1 output
đạt hợp đồng. Phần thiếu giữ unresolved, không được biến thành taxonomy rỗng hay
feedback placeholder. Thí nghiệm xác định nút thắt ở hợp đồng diagnosis trước
khi có thể kết luận về lợi ích renderer/guard. Đây không phải bằng chứng rằng
mọi phương pháp tách bước đều thất bại.

## A. Trạng thái và phạm vi

HEAD đầu `eca737296a4d31efa56ca90faa8fb6e6c92b4c2d`, branch
`feat/task3-quality-round5`, working tree đầu sạch. HEAD cuối là commit chứa báo
cáo này; hash cụ thể và status cuối ghi trong lời bàn giao và ignored
`outputs/task3/grounded-20261023/handoff.private.json` sau commit, tránh hash tự
tham chiếu trong commit. Không clone/worktree/checkout branch cũ, không push/PR,
không training, API LLM ngoài cho inference hoặc leaderboard upload.

Đã đọc Task3 docs, label_space, sample/public task3 metadata, loader, validator,
compiler code và báo cáo đến R24/level-blind/paired-review. **Không có DOCX gốc**
trong workspace/attachments/danh sách thành viên ZIP đã kiểm. Đã đọc bản chuyển
đổi `DoAn-LLM-Challenge.docx.md`, không giả vờ đã đọc bytes DOCX. Sample có nhãn
input để tách Task2, public không có; public yêu cầu cả taxonomy và feedback.
Định nghĩa Level lấy trực tiếp label_space; ranh giới taxonomy của rulebook là
quy tắc thao tác của nhóm, không phải xác nhận của giảng viên.

File mới: `src/task3/grounded{,_runner,_metrics}.py`, ba CLI
`scripts/task3_grounded_{inventory,experiment,report}.py`, config
`configs/task3/grounded_20261023.json`, rulebook `docs/task3_grounded_rulebook.md`,
bốn test files `tests/test_task3_grounded{,_metrics,_projection,_review_binding}.py`,
plan và báo cáo/aggregate mới. Không sửa tracked file cũ hay dữ liệu/gold/R15/SFT v1.

## B. Flow thực tế và chạy lại

Đề + source + policy + compiler/test state → Qwen diagnosis → kiểm schema,
source quote/span/requirement/evidence/scope → selected findings → taxonomy
projection → feedback → disclosure/semantic screening → output hoặc unresolved.

C0 dùng nguyên native R15 controller/prompt/config, bao gồm bounded retries và
fallback lịch sử. C1/C2 dùng **cùng một diagnosis**, một nhãn chính mỗi finding,
đa nhãn khi có các finding độc lập. Nhãn được lấy từ selected findings chứ không
được renderer đổi. Citation từng câu là điều kiện traceability, không phải bằng
chứng ngữ nghĩa. L1 giữ mapping status→finding ở trace riêng, không đưa ID hay
nguyên nhân vào renderer. Clean là quyết định có lý do với bằng chứng hạn chế;
uncertain/parse/tool failure không được xuất thành `[]`.

C1 nhận full task + findings, wording gần R15 và screen disclosure cũ; schema
feedback chuyển sang cited sentences và taxonomy đã khóa. Vì vậy C1 khác C0 ở
nhiều yếu tố, không phải chỉ thêm evidence một cách hoàn toàn cô lập. C2 nhận
`level_view`: L1 chỉ status/limitation; L2 thêm scope/span/observed/cause; L3 thêm
repair; L4 thêm source detail. C2 gọi Qwen semantic screen, retry chỉ nhận mã lỗi
cố định, không nhận lời giải/chi tiết mới từ guard. Đây là ablation **view +
renderer/guard**, không tách riêng hiệu ứng guard.

Machine source checks chỉ xác minh nguồn trích; confidence do model tự khai
không được gọi là semantic proof. Không gọi compiler host trên source sinh viên.
Compiler của tập này unavailable; tests not_run. Không có runtime counterexample
hay trusted expected/actual được tạo; không nói đã chạy test sinh viên. C++ trong
unit/integration tests là fixture nhân tạo, không phải evidence cho bài thật.

Từ repo hiện tại, lệnh kiểm/replay accounting không load model:

```bash
.venv-task3/bin/python scripts/task3_grounded_experiment.py verify --split evaluation
.venv-task3/bin/python scripts/task3_grounded_report.py score --split evaluation
```

Lệnh inference tự động trên snapshot chưa chạy là:

```bash
.venv-task3/bin/python scripts/task3_grounded_experiment.py run --split evaluation
```

Run đã hoàn tất sẽ bị từ chối resample; không xóa marker/journal để chọn response
tốt hơn. Rerun model mới cần một output snapshot riêng được khóa từ cùng nguồn
và config. Raw source/prompts/responses/review ở ignored private root, không
commit. Code Git một mình không chứa dữ liệu nhạy cảm để tái tạo inference;
cần private snapshot và pinned HF cache. Không có Codex agent/human/API tham gia
đường generate; review là bước nghiên cứu bên ngoài inference.

## C. Inventory và khóa trước evaluation

| Dữ liệu hiện có | Số record | Family | SHA256 JSON Task3 |
|---|---:|---:|---|
| real sample |32|2|`d27118a81b0723bc68aecb7c4cf4096d3f6712a85dc938ef39ba57fe71d2c47e`|
| synthetic cũ |612|28|`122d3736634394741ea8eaddb89dd1f068e4d23cd037f380a94c35b67f04bf4f`|
| heldout cũ |65|4|`56c74ce3db5e371dc78fe3425e66109d8d3af20dc3ae6b3f8cfa28eac83c509b`|
| synthetic cập nhật |627|28|`38da5e36636ba74315b3e0d6e8e25e7240595b7cb2dcf33ef00dcc21542f9a32`|
| public metadata |328|6|`6020f0687f661dadf11600a8c50cb7c6cec6cef347ef13f71b09be42a6e631bb`|

Không trùng sample_id trong từng corpus. Synthetic cũ/mới đều có 156 nhóm trùng
raw/token source và 165 nhóm trùng sau chuẩn hóa identifier; đó là **nhóm**, không
phải số record trùng. Heldout có 2 nhóm raw/token, 6 nhóm renamed. Real32 không
trùng theo các phép kiểm này. Giữ nguyên annotation, không sửa để khớp báo cáo cũ.

Bytes ZIP được nhận dạng bằng SHA256:

- `generate-dataset_v2.zip`: `6bda70c29254a3bce91933b65f4a311d73a052e72d181c97e977152e14602f9b` (627 +65).
- ZIP synthetic bên trong archive data cũ: `88eff95f2841efd061ab0203907f9142ad6a2a2b72e266a4d55043a50aedac9c` (612 +65).
- `data-20261017T044357Z-1-001.zip`: `8c04e4e01be73952cb255fb5efd707c758205c19457fa651d944fc02780a3e1e`.
- ZIP public bên trong archive cũ: `637a033ead19dc2fd5c5a82c859e92637762b09f4da870c2d012f108a9183dad`;
  file ngoài `/workspace/public-test-cham-diem-phan-hoi-files.zip`:
  `7ae1fc242e44aab07d8606fd17efca8b43a42139c65906bf6c4db843d37c2158`.

Không lấy chữ v1/v2 trong tên làm phiên bản. Heldout mới cũng 65 nhưng JSON khác
bytes heldout cũ; không gộp chúng. Inventory riêng tư ghi đầy đủ ID/hash/duplicates,
archive members, manifest và preservation baseline cho 2.598 file.

R15 public predictions và traces đều328 records; trace SHA
`ba6f4ef99fca8a8cb44404ffb78d9a9d0c77f769d3c029723bcbd05a7ce20280`.
SFT v1 giữ các output BASE/SFT60 requests và public trial328; final public-trial
SHA `c30c5c136195df50529f70a95fb1cf63e0bf61e690930dbe3f82d1ddfbbb33f5`.
Inventory supplemental chỉ kiểm count/hash, không dùng output/traces cũ làm
ví dụ, target hay chọn prompt. Không rerun/tune SFT v1 trong vòng này.

Dùng nguyên evaluation-v2: development **8 source/5 family**, evaluation **60
primary source/18 family**, không chọn theo output. 8 dev toàn single_problem;
evaluation 45 single_problem +15 multi_problem, L1/L2/L3/L4 =19/27/8/6. Không chạy
36 counterfactual requests của snapshot cũ. Không có real trong hai tập chạy mới;
real evaluation metrics là **N/A**, không suy rộng từ six real-val.

Family dev/eval không giao nhau; 480 cross-source comparisons không có near≥0,85,
max structural shingle Jaccard =0,5088757396. Kiểm này không chứng minh độc lập
ngữ nghĩa. Parent v2 đã có review loại các biến thể gần giống ngoài ngưỡng.

**Đây là controlled evaluation có prior exposure, không phải benchmark mù mới.**
V2 kế thừa source/reference và corpus/template exposure. Metadata-only audit cho
thấy **18/60 ID (30%) đã được paired-review chấm output**, 9 ở development và9 ở
validation trước; 42 còn lại không được chứng nhận chưa từng xem. R24/level-blind,
real-val và contract-v1 là development/prior experiments, không được tái gọi là
clean benchmark. Mỗi method sau vòng này cần ghi thêm exposure của vòng hiện tại.

Selection SHA `09fc5078ee2b3a8159ddaa89eb323bd4ac1777a6f61af0e9947978b6a65b1da7`,
khóa trước implementation. Evaluation freeze cuối
`ccac407a7f0a3f704325787584785fdc57da82c3c82e8abd10db659bd8568427`;
prompt template `0cf785a4ebc14eaab9dc759d71a63e24a9731d8ff1ec736aab9bf91d2d97e01d`.
Manifest lưu config/tokenizer/runtime hashes và rendered message hashes trong
raw-before-parser journal. Golden labels/teacher feedback/Level không vào
diagnosis; input allowlist chỉ task/evidence. Public chỉ được đọc metadata/hash
để inventory/validator, không source hoặc raw public attempts để phát triển.
Nội dung IDE selection người dùng gửi không được dùng làm ví dụ hay tuning.

Qwen2.5-Coder-7B-Instruct revision
`c03e6d358207e414f1eca0bb1891e29f1db0e242`, không adapter, NF4/double quant,
compute BF16 trên CUDA0 RTX5090 32GiB, seed42 greedy, context16.384. Metadata
thực xác nhận quantized compute `torch.bfloat16`, không CPU/disk offload. Hash11
HF files (gồm4 shards/config/tokenizer) và packages ở private manifest SHA
`4689f56e053e34ece2e8f124c8aa25f9af186934676b37d84e48acd4d8665692`.
Torch2.8.0, transformers4.57.1, bitsandbytes0.48.1, accelerate1.11.0,
tokenizers0.22.2, Python3.12; versions đầy đủ giữ trong manifest đó.

C0 giữ 1.024 token/45s và tối đa3 attempts nguyên trạng. Candidate1536 token/60s,
diagnosis tối đa2 attempts; renderer tối đa2, mỗi C2 renderer hợp lệ có thêm guard.
Budget/calls khác nhau do thiết kế; không mô tả như equal-cost comparison.

### Development và các preflight được bảo toàn

Một prompt ban đầu cho8 dev cho0/8 diagnosis, chủ yếu thiếu evidence_reference.
Run này và16 diagnosis calls giữ nguyên ở `development-contract-v1`. Sửa chung:
schema template rõ reference, single_problem có P1, source location L2/L3. Prompt
v2 chạy lại cùng8 dev, C0 tái sử dụng **nguyên bytes**, không resample; vẫn0/8
diagnosis. Không tiếp tục tối ưu prompt rồi chỉ trình bày best variant.

Reviewer code phát hiện scope bỏ sót câu, block theo policy tùy ý và span trỏ
comment; đã test RED→GREEN trước model. Sau dev còn sửa projection exam_type
**chỉ nhánh evaluation**, và mapping trace status L1; không đổi prompt/model
input development. Preflight freezes và exact code snapshots giữ riêng trước
các sửa này; chưa có evaluation model call nào trước freeze cuối. Development
historical freeze giữ hash script cũ; không gọi nó là current-runtime verification.
Evaluation current runtime verify sau run qua60/60.

Historical `task3_freeze_eval_v2.py verify` ban đầu thất bại do metadata R16/R17
đã archived. Sau evaluation, xác minh SHA archive
`d22fe08529ec21421405e18683deb0c5694466e7f5d7810cf90d4b420e368baa` rồi khôi phục
nguyên byte đúng ba tệp thiếu: R16 development-selection và bank R16/R17.
Không ghi đè tệp hiện có, sửa/reseal v1/v2, đưa bank vào prompt hoặc chạy lại
model. Historical verify nay **PASS**; log `historical-verify-restored.log` và
hash từng tệp ở `historical-metadata-restoration.private.json`. Audit mới còn
đối chiếu child frozen hashes, ZIP/members và raw/decoded bytes của68 source.

Config SHA `e3c7515991f41444ebd1b4d1e380f59ce4735570e67ca2c9e9343b204f90e4e1`;
diagnosis/render/guard code SHA
`44958c954a6db785deafb9dc3de68625913a485cc54cfbcf1d9bf9bcf1e22a7f`;
runner SHA `f2e7d1d1d2c40d9cc452a833553f2050e2b44ff91b590086803cd66393ff40b4`.
Các hash khác, per-family/per-label và bảng đủ60 ID không có source/feedback
được lưu trong [aggregate](TASK3_GROUNDED_METRICS_20261023.json).

## D. Taxonomy trên đúng 60 ID

Primary tính trên final outputs; invalid/unresolved không được exact-clean
credit, mọi gold label của chúng vẫn FN. Macro trung bình **đủ10 nhóm**, F1
zero-denominator=0. Empty và false-clean chỉ đếm explicit `[]`, không đếm lỗi parse.

| Arm | Output hợp lệ | Macro-F1 | Micro-F1 | Exact /60 | Explicit [] | False-clean theo gold |
|---|---:|---:|---:|---:|---:|---:|
|C0/R15|60|0,082558|0,181818|13|21|13|
|C1|4|0,015385|0,032787|4|3|0|
|C2|1|0|0|1|1|0|

Không gọi giảm false-clean xuống0 là cải thiện: candidate abstain gần hết tập.
Bảng bổ sung diagnosis-stage được tính **mô tả sau run**, không đổi frozen metric
hay gate: shared C1/C2 có5 valid/55 unresolved, macro0,015385, micro0,032787,
exact5/60. Renderer làm completion giảm5→4→1; taxonomy diagnosis không đổi giữa
C1/C2. Với support render quá thấp, hiệu ứng Level view/guard **chưa xác định**.

Diagnosis116 calls có111 rejection attempts:43 status/confidence mâu thuẫn,
18 scope coverage,17 nhãn không hợp lệ,13 quote không có trong source,9 quote
rỗng,5 quote chỉ comment,5 sai prerequisite block và1 fence. Các lần này không
được sửa thành finding xác nhận. Đây vừa là hợp đồng quá khó cho prompt hiện tại
vừa là nguy cơ nhận định thiếu căn cứ; tỷ lệ JSON đơn thuần không đo chất lượng.

Development8: C0 macro0,171429, micro0,666667, exact3; C1/C2 invalid8, F1=0.
Source-first agent review của C0:0 joint PASS,3 false claims,1 L2 repair leak,
1 taxonomy/feedback contradiction và2 generic outputs. Candidate không có
feedback nên không thể tính compliance thành100% từ0 leaks.


### Per-label support và TP/FP/FN (gold gốc)

| Nhãn | Support | C0 TP/FP/FN | C1 TP/FP/FN | C2 TP/FP/FN |
|---|---:|---|---|---|
|Lỗi biên dịch|4|2/2/2|0/0/4|0/0/4|
|Lỗi nhập/xuất|1|0/4/1|0/0/1|0/0/1|
|Lỗi logic|12|7/24/5|1/0/11|0/0/12|
|Lỗi vòng lặp|9|0/0/9|0/0/9|0/0/9|
|Lỗi mảng/chuỗi|9|0/0/9|0/0/9|0/0/9|
|Lỗi hàm|8|0/0/8|0/0/8|0/0/8|
|Lỗi edge case|2|0/0/2|0/0/2|0/0/2|
|Lỗi thuật toán|8|0/0/8|0/0/8|0/0/8|
|Lỗi hard-code|6|0/0/6|0/0/6|0/0/6|
|Lỗi style|1|0/0/1|0/0/1|0/0/1|

Nhóm có support1–5 rất ít; đây không phải ước lượng chất lượng tổng quát.

## E. Feedback, joint và các ca tiêu biểu

Ba reviewer agent độc lập chấm20 source/người, đủ180 output slots kể cả
unresolved. Nhánh được ẩn/xáo thứ tự; không đưa generator findings, trace,
lời tự giải thích, gold hay feedback giảng viên cho reviewer. Review dựa trên
source được niêm phong trước khi đối chiếu gold. **Hạn chế quy trình:** preview
ban đầu hiển thị source cùng output ở43/60 ca (reviewer1:9, reviewer2:14,
reviewer3:20), trước dedicated source-only pass. Không tuyên bố source judgment
hoàn toàn output-blind;17 ca còn lại cũng không được gọi là benchmark mới sạch.
Giữ đủ60 ca, không loại ca bất lợi. Ba reviewer chia tập, không có chấm đôi cùng
ca để ước lượng inter-rater agreement.

Mỗi verdict có trích dẫn ngắn khớp chính xác source/đề và feedback trong private
`evaluation/review/source-review-{1,2,3}.private.json`. Review seal SHA
`581eee7080ce063c12c6f31cd3446a89985b03e0657f9e2be170393c4bce3f81`.
Scorer kiểm hash review, packet seal, key/units và đối chiếu source/status/output
hiện tại với packet đã review trước khi tính điểm. Code review độc lập phát hiện
thiếu ràng buộc này; đã sửa riêng tooling báo cáo và qua8 mutation tests, không
đổi inference/prompt sau evaluation.

| Rubric / số output | C0/R15 | C1 | C2 |
|---|---:|---:|---:|
|Hoàn tất /60|60|4|1|
|Joint PASS /60|4|1|1|
|Lỗi chính được nêu hoặc clean assessment phù hợp|25|4|1|
|Có false claim|32|0|0|
|Support verdict=no, chỉ output hoàn tất|47|0|0|
|Support verdict=disputed|6|2|0|
|Mâu thuẫn taxonomy/feedback, output hoàn tất|10|0|0|
|Sai Level, output hoàn tất|19|1|0|
|L1 location/cause leak / L1 hoàn tất|2/19|0/0|0/0|
|L2 repair leak, explicit hoặc implicit / L2 hoàn tất|11/27|1/2|0/0|
|L3 có hướng sửa / L3 hoàn tất|2/8|0/1|0/0|
|Tiếng Việt tự nhiên|59|4|0|
|Generic feedback|7|0|1|

Không lấy0/0 làm100% compliance. C2 không có L1/L2 output để kiểm độ an toàn.
Support=no là đánh giá **cấp output**, có thể do thiếu/thừa nhãn, không phải47
mệnh đề sai độc lập. Không thu thập exhaustive per-clause unsupported counts
hoặc bộ phân loại riêng wrong-language; không suy ra các số này bằng0. Toàn bộ
unresolved được tính FAIL, không có false claim do không có câu để phát biểu.
Coverage là số output, không phải tỷ lệ mọi defect đã được phát hiện.

Joint proxy đã khóa yêu cầu taxonomy có căn cứ và không thiếu/thừa nhãn theo
source review, lỗi chính được phủ, không false claim, nhất quán và đúng Level.
Proxy **không gồm natural/generic**, được báo riêng. Vì vậy C2 REVSTR0001 vẫn có
1 mechanical joint PASS dù reviewer chê dùng từ sai ngữ cảnh và generic; nếu
thêm natural/non-generic sau run thì chỉ còn0, đây là sensitivity, không sửa gate.
C1/C2 mỗi nhánh có **0 thắng,3 thua,57 hòa** so với C0 theo joint đã khóa.

Gold-disagreement có33/60 source; source_disputed22/60. Giữ nguyên gold gốc.
`id-metrics.private.json` có overlay yes/no+lý do cho từng output, so sánh nhãn
bằng máy **sau seal**, dùng rationale từ reviewer; đây không phải người/agent mới
adjudicate lại gold. Raw review giữ nguyên trường pending, không sửa sau niêm
phong. Các câu hỏi domain/capacity/prerequisite và ranh giới nhãn vẫn disputed.
Theo reference agent riêng: macro/micro C0=0,100940/0,201835, C1=0,013333/0,028169,
C2=0/0; exact=12/4/1. Reference này fallible, gồm ca disputed, không thay gold và
không dùng chọn winner.

| sample_id (Level) | Đối chiếu và bằng chứng được diễn giải, không chép source |
|---|---|
|SYN-REVSTR-0001 (4)|Cả ba nhận định clean có giới hạn được source review hỗ trợ; C2 dùng từ chỉ “đoạn văn” cho code nên không tự nhiên. Không có cải thiện joint.|
|SYN-DIGITSUM-0006 (2)|C0/C1 cùng nhận đúng phép tính sai và nhãn Logic. C0 đưa thay thế cụ thể; C1 nói phép trừ thay vì cộng, vô tình chỉ cách thay toán tử. Cả hai leak L2; C2 unresolved.|
|SYN-ARM-0008 (4)|C0 nhận đúng lỗi chuyển ký tự số và hướng sửa được phép ở L4; C1/C2 unresolved. Đây là suy giảm completion, không phải thắng về safety.|
|SYN-COUNTUPPER-0012 (2)|Source kết thúc mà không đọc/in theo đề; C0 chỉ mô tả hành vi thiếu, không đưa cách triển khai nên L2 hợp lệ. Agent reference chọn I/O khác gold; candidate unresolved.|
|SYN-ARM-0026 (2)|C0 nói accumulator bị ghi đè; source review xác định shadowing và tự tham chiếu biến chưa khởi tạo. Nhãn Logic có thể đúng nhưng nguyên nhân trong feedback sai.|
|SYN-BASE2-0007 (1)|C0 xuất[]/clean trong khi lần đọc phụ đã tiêu thụ input duy nhất. False-clean theo source review; gold-disagreement được giữ riêng.|
|SYN-COUNTGT-0005 (1)|C0 bỏ hai defect độc lập: chỉ số compare/assign lệch và đọc phần tử chưa khởi tạo. Agent reference có Logic + Array; không gộp hai cơ chế thành một nhãn cho tiện.|
|SYN-REVSTR-0007 (2)|C0 nhận sai chỉ số nhưng chọn Logic thay Array và còn chỉ định vị trí hoán đổi đúng: explicit L2 repair leak.|
|SYN-GCDARR-0009 (3)|C0 nói thiếu phần tử nhưng source thực dùng phần tử đầu rồi bốn phần tử sau. Bỏ invalid main và hướng sửa hữu ích; phân loại cận cố định giữ disputed.|
|SYN-PRIME-0024 (1)|C0 nhắc chung đúng L1, taxonomy Logic được source hỗ trợ cho shadowing. Joint source PASS nhưng gold khác nhãn: không sửa gold để tăng exact.|
|SYN-MAXDIFF-0003 (3)|Source review nêu sai chỉ số cuối và P2 hằng0, cùng nghi vấn capacity/prerequisite; C0 chẩn đoán “bỏ cuối” chưa đúng và không phủ lỗi chính. Giữ disputed/gold-disagreement.|

Private development casebook còn ghi COUNTVOWEL0010 false delimiter claim,
POWER0007 false uninitialized claim dù đã khởi tạo, PALIN0015 L2 repair leak,
UPPER0005 taxonomy[] trái lời phê lỗi. Chúng chỉ thuộc development; không dùng
evaluation examples ở bảng trên để sửa prompt rồi tuyên bố chiến thắng mới.

### Theo family, synthetic evaluation

Mỗi ô là **exact theo gold gốc / output hợp lệ**; mẫu số nghiên cứu là cột n,
không chỉ các output hợp lệ. Macro/micro và support từng family có trong aggregate.
Real evaluation n=0, metrics N/A.

| Family | n | C0 | C1 | C2 |
|---|---:|---:|---:|---:|
|ARM|4|1/4|0/0|0/0|
|BASE2|3|1/3|0/0|0/0|
|COUNTGT|3|0/3|0/0|0/0|
|COUNTUPPER|4|1/4|1/1|0/0|
|DIGITSUM|4|2/4|2/2|0/0|
|DISTINCT|4|1/4|0/0|0/0|
|FACT|4|1/4|0/0|0/0|
|FIB|3|1/3|0/0|0/0|
|GCDARR|3|1/3|0/0|0/0|
|MAXDIFF|3|0/3|0/0|0/0|
|MINA|3|0/3|0/0|0/0|
|PERFECT|3|1/3|0/0|0/0|
|PRIME|4|0/4|0/0|0/0|
|PROD|3|0/3|0/0|0/0|
|REVSTR|3|1/3|1/1|1/1|
|SECONDMAX|3|0/3|0/0|0/0|
|SUMB|3|1/3|0/0|0/0|
|SUMEVEN|3|1/3|0/0|0/0|

## F. Quyết định và giới hạn

C1 fail complete, serious-leak, joint-gain, taxonomy-drop và rare-label retention.
C2 fail complete, joint-gain, taxonomy-drop và rare-label retention. Gate yêu cầu
đủ60, zero serious L1/L2 leak, joint tăng ít nhất3, micro giảm không quá0,02,
false claims/false-clean không tăng và rare TP không giảm. Với C0 joint4, ứng viên
cần≥7; thực tế chỉ1. C0 có2 TP compile thuộc nhóm hiếm, C1/C2 không giữ được.
Không lấy việc abstain để được0 false claim làm thắng.

**Giữ R15, chưa có winner.** Đây không phải xác nhận R15 đủ tốt: source review
cho thấy false claims và Level leaks đáng kể. Chưa có bằng chứng vượt0,5
leaderboard. Không có real evaluation, tập prior-exposed, agent review có preview
bias và bất định taxonomy/domain. Phân tích tĩnh/guard model đều có thể sai.
Locked60 nay đã exposed cho vòng này; prompt sửa tiếp cần development và một
tập đánh giá khác được khóa, không chạy lại60 để gọi là benchmark sạch.

## G. Public handoff

Không tạo predictions mới vì gate hoàn tất đã fail. File R15 hiện có giữ nguyên:
`/workspace/llm-final-project/outputs/task3/round15/public-candidate-zero/predictions.json`,
SHA256 `9ba7411c35a3461b5747be367274631d5122455335061005c695276ed76c5a45`.
Validator thật chạy trên file đó với map mới **chỉ từ sample_id và input Level
của release**: VALID328, Levels115/163/50/0. Log:
`outputs/task3/grounded-20261023/r15-existing-validator.log`. Đây là xác minh schema,
không chứng minh chất lượng feedback. Không upload leaderboard.

## H. Chi phí, kiểm thử và bảo toàn

| Evaluation component | Calls | Input tokens | Output tokens | Generation latency (s) |
|---|---:|---:|---:|---:|
|C0, gồm retries|77|59.017|5.303|67,646|
|Diagnosis dùng chung C1/C2|116|154.891|34.706|413,726|
|C1 renderer|6|6.026|266|3,687|
|C2 renderer + guard|16|5.823|720|9,248|

Chi phí độc lập của C1=122 calls/417,412s và C2=132 calls/422,973s nếu mỗi pipeline
tự chạy diagnosis. Chi phí thí nghiệm không cộng diagnosis hai lần. Tổng actual
generation gồm development/control (C0 chỉ tính một lần), development v1 thất
bại, development v2 và evaluation: **261 calls,271.130 input tokens,50.198 output
tokens,606,026s**. Model-load latency riêng ở runtime manifests, không gộp vào
generation. Không quy đổi thành tiền hay coi local GPU miễn phí; chi phí Codex
implementation/reviewer chưa có billing telemetry để định lượng.

Gate tests mới/liên quan: **94 passed**; trong đó42 tests mới bao gồm strict10
labels, parse≠clean, compiled≠logic-correct, independent multi-label paths,
missing evidence, source quote/comment/span, prerequisite coverage, Level views,
L1 internal mapping, L2 implicit-repair semantic verdict, L3 repair visibility,
sentence citations, bound resume, exam_type archive projection và8 ca chống
đổi source/output/status/key/packet sau review. Fixtures nhân
tạo không được đưa làm few-shot inference. Semantic screen unit test chỉ kiểm
việc tôn trọng verdict, không chứng minh Qwen phân loại ngữ nghĩa đúng; phần đó
được đánh giá bởi reviewer source-first.

Toàn bộ Task3 command trên code cuối: **1.319 passed,5 skipped,1 failed**.
Lần trước khi khôi phục archive có1.303 passed,4 failed,5 errors do thiếu metadata;
giữ cả log thất bại ban đầu. Sau khôi phục, chỉ còn
`test_v2_plan_preserves_v1_and_does_not_read_prediction_or_public_inputs`:
historical original-hashes đòi root `predictions.json` có SHA R15, nhưng tệp ở
gốc **đã mang SHA SFT v1 từ đầu phiên**, đúng preservation baseline của phiên này.
Không đổi root prediction, sửa baseline, tạo fixture giả hay thay seal để ép
xanh. Không gọi toàn suite là green; không tạo checkout khác để chạy baseline.

Bare `pytest -q` dừng collection ở `test_clm_zeroshot_task1.py` và
`test_task1_clm_probe.py` vì thiếu sklearn. Không sửa Task1/2 hoặc cài dependencies
ngoài scope. Logs: `task3-tests-post-restoration.log`, `full-tests-final.log`,
`focused-tests-post-review.log` dưới private root.

Current evaluation freeze/source/runtime verification sau model run:
**60/60 verified**. Preservation check **2.598/2.598 hashes unchanged**, gồm tracked
files cũ, dữ liệu/splits, R15, SFT v1, frozen evaluation và public predictions cũ.
Chỉ stage file mới thuộc thay đổi này; không stage private sources, raw attempts,
feedback, predictions, weights hoặc file của người khác. Commit trên branch hiện
tại, không push hoặc upload.

## Kết luận nghiên cứu

Không đạt gate completeness, taxonomy hoặc khả năng giữ nhóm hiếm; giữ R15.
Không tuyên bố vượt0,5 leaderboard. Bước thử tiếp theo là giảm hợp đồng model
phải tự serialize, tách các ràng buộc machine-derived khỏi suy luận ngữ nghĩa,
và đo source-grounded diagnosis trên train trước một tập đánh giá khác được
khóa. Không tự mở fine-tuning. Tập60 hiện tại đã được review và không còn là
nguồn kết luận mới sạch cho prompt sửa tiếp theo.

Đã dùng Codex để implementation, tests, nghiên cứu và review độc lập; Qwen7B để
mọi model generation/guard trong thí nghiệm. Agent review không phải human
verification và joint PASS chỉ là proxy nội bộ, không phải metric leaderboard.
