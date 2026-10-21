# Task 3 — đối chiếu yêu cầu với hành vi source

**Giữ R15 production. Chưa đủ bằng chứng kiểm chứng giả thuyết trên tập mới; candidate vận hành cũng không đạt trên tập điều tra.** Cả hai nhánh hoàn tất 20/20 ID. Candidate giảm cáo buộc trên các bài được agent review là đúng nhưng tăng lời khen sai trên bài có lỗi; chẩn đoán hữu ích theo tiêu chí chặt không tăng. Không huấn luyện thêm, public inference, sửa submission, leaderboard upload hoặc push.

Mốc được giữ nguyên theo yêu cầu: **R15 zero-shot 0,3834; DIRECT SFT v1 0,1517**. Đây là các kết quả public lịch sử, không phải metric của vòng này. Không truy cập lại leaderboard hay dùng public source/predictions/attempts để chọn phương pháp. Provenance và bytes của các artifact cũ được kiểm bằng preservation hashes; không tái diễn giải hoặc ghi đè chúng.

## Checkout, dữ liệu và runtime thực tế

Bắt đầu ở `/workspace/llm-final-project`, branch `feat/task3-quality-round5`, HEAD `4a2f4e088dca990fcdbbf00044d57a5f95604098`, `git status --porcelain` rỗng. Không checkout/reset/worktree/clone. HEAD sau commit, danh sách commit và trạng thái cuối nằm trong `outputs/task3/requirement-evidence-20261021/final-handoff.json` để tránh SHA tự tham chiếu trong commit.

R15 thực tế: `configs/task3/r15_selected.yaml` → `r15_zero_shot.yaml` → `r15_common.yaml`; native `round15.py`, `round15_runner.py`, `round15_disclosure.py` và backend giữ nguyên. Qwen/Qwen2.5-Coder-7B-Instruct revision **`c03e6d358207e414f1eca0bb1891e29f1db0e242`**, base 7B, không adapter/commercial API/mock/replay. RTX 5090, actual NF4 double quant, BF16 compute, toàn bộ parameter trên CUDA, không offload; runtime xác nhận đúng revision. Seed42, greedy, context16384, final cap1024/L4 cap1536, R15 tối đa3 attempts, generation max_time45s. Chat-template SHA `cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f`. Few-shot **0** ở cả hai nhánh; bank R15 được hash để bảo toàn, không đưa ví dụ nào vào prompt.

Dữ liệu train: ZIP root `generate-dataset_v2.zip` SHA `6bda70c29254a3bce91933b65f4a311d73a052e72d181c97e977152e14602f9b`, 627 root records, tách khỏi 65 heldout. Prepared hiện có 495 synthetic-train, 26 real-train, 6 real-val; không mặc định prepared bytes bằng ZIP v2. Audit lưu hash ZIP/members, prepared files, fixed split IDs và label-space. Các ca thêm từ ZIP root ghi rõ `raw-training-archive-development`, **không tuyên bố chúng thuộc prepared synthetic-train**. Original annotation và teacher feedback lấy nguyên từ cùng ZIP root, chỉ nằm trong packet đánh giá; không truyền vào model. Không sửa gold/source.

`g++` 13.3.0 có trên máy, nhưng sandbox namespace không khởi tạo được (`unshare: Operation not permitted`; shell mặc định cũng lỗi bwrap namespace). **Compiler evidence: unavailable**. Không compile/run source sinh viên ngoài cách ly, không có executed testcase/oracle. Các nhận định syntax, invariant và phản ví dụ trong review đều là phân tích tĩnh của tác giả, không phải compiler-confirmed. Compile pass, nếu có ở vòng sau, vẫn không chứng minh logic đúng.

## Vì sao không có 40–60 source mới đáng tin

Quy tắc được áp dụng trước inference, giữ cả danh sách bị loại và nearest-source evidence:

1. Inventory nguồn đã dùng từ registry v2, 60 evaluation v2, source train/validation DIRECT SFT v1/v2, calibration/fresh/bank feedback-prompt, 12 confirmation cũ, và source snapshots của contract/pilot trong archive. Chỉ đọc các member source được allowlist, không đọc archived public attempts/predictions. Corpus-only exposure được phân biệt với output/example/optimizer use. Registry không phải log đầy đủ mọi lượt xem của người hoặc agent; không chứng minh lịch sử phơi nhiễm là exhaustive.
2. Prepared train còn 161 record không trùng ID/token/identifier-renamed identity; screen near lịch sử ở 0,85 còn 28, pairwise còn 17 provisional. Đây chỉ là bước audit, chưa phải freeze cuối.
3. Kiểm thêm canonical ZIP training root, loại clone `-L...`, heldout identities và near-source ở ngưỡng chặt hơn **0,75**: 9 ứng viên; pairwise lexical/structural5gram còn 8. Không nới ngưỡng theo output.
4. Đọc nearest-source diff thủ công: 6/8 vẫn là mutation/template cũ, chuyển hẳn vào **điều tra**, không tính là source mới. Chỉ `SYN-GCDARR-0000`, `SYN-MAXARR-0001` có cách triển khai đủ khác trong screen hiện tại. Không chứng minh hết mọi tương đồng ngữ nghĩa.

**Freeze cuối: mới2 + điều tra template6 + confirmation đã xem12 =20 ID.** Cả 28 family có prior exposure, nên không có family-disjoint/blind benchmark. Hai ca mới đều có invariant đúng trên miền đầu vào có điều kiện nhưng đề thiếu cận n/kiểu số/time; reference chính là **uncertain**, không tự tính thành clean. Tập mới có **0 clean được phân xử và 0 defect được phân xử**: không thể kiểm chứng đồng thời hai mục tiêu. Đây là giới hạn dữ liệu thực, không lấp bằng source tác giả viết thêm hoặc đưa template cũ vào tập mới.

Requested Level giữ nguyên metadata, không suy từ suffix ID: L1=5, L2=14, L3=1, L4=0. Coverage này rất hẹp. Có compile/IO/logic/loop ở tầng điều tra; không có chúng ở tầng mới. Danh sách ID/source hash/Level/family/origin/rule/reference/config/code khóa trong `study-freeze.json` **trước mọi model call**, SHA `4a4031d94c27c9ca3a93242d290d097933ea02aabc300876a6b09a025bc21f07`.

Tất cả reference và semantic verdict là **author-agent review, not human-verified**. Với 12 confirmation cũ, tác giả đọc lại source trước output nhưng kế thừa bối cảnh đã phơi nhiễm; không gọi đó là xác nhận độc lập. Review các output không blind. Không dùng sự đồng ý của LLM làm ground truth.

## Candidate duy nhất và dấu vết chạy

Hypothesis: yêu cầu Qwen đối chiếu từng P với hành vi code và cân nhắc đúng/có lỗi/chưa đủ căn cứ trước khi viết sẽ giảm bịa lỗi và cải thiện chẩn đoán.

Candidate tách riêng, không monkeypatch R15: lượt diagnosis chỉ nhận statement/problems/policy/source/compiler-unavailable, không nhận requested Level hay gold/teacher; mỗi P có status, requirement, behavior, reason, source quote khi đề xuất lỗi và counterexample tùy chọn. Kiểm đủ P và quote substring chính xác. Không chạy testcase hoặc coi quote là proof; counterexample sinh ra được gắn `unverified_not_executed`. Lượt render cùng Qwen nhận source và diagnosis giữ lại, tự sinh nhiều official labels khi cần và feedback theo Level. Không có sublabel hoặc ép một nhãn vì feedback chọn một lỗi trọng tâm.

Tối đa2 diagnosis +2 render; diagnosis cap1536. Chỉ tái dùng guard disclosure hiện có, không thêm dàn regex. Bất kỳ P còn uncertain sau retry hoặc render không hợp lệ dẫn tới dùng **output R15 nguyên trạng đúng ID/Level**. Nếu R15 cũng thiếu output thì giữ completion error, không đổi thành `[]`. Candidate không được xem R15 output trong prompt. R15 fallback có thể vẫn sai về nội dung, nên không được tính là thành công chỉ vì schema hợp lệ.

|Chạy thật|R15|Candidate, kể cả fallback|
|---|---:|---:|
|Final đủ ID|20/20|20/20|
|Raw calls|23|43: 25 diagnosis +18 render|
|Output tokens|1.459|8.959|
|Generation latency, không gồm load|19,90s|111,21s|
|Runtime/completion errors|0/0|0/0|
|Fallback|1/20 native|8/20 tái dùng R15|

Không cộng lại chi phí fallback inference: candidate tái dùng baseline đã chạy. Deployment riêng sẽ cần trả thêm chi phí R15 cho fallback; chưa benchmark đường đó. Model load6,03s, peak allocated7,07GB. Native R15 fallback ở `SYN-PERFECT-0000`. Candidate fallback IDs: `SYN-COUNT-0004`, `SYN-COUNTUPPER-0010`, `SYN-GCDARR-0000`, `SYN-PERFECT-0000`, `SYN-PERFECT-0001`, `L2D-COUNT-02`, `L2D-SUMPAIR-01`, `L2D-SUMPAIR-02`. Internal explicit uncertain4/20; operational uncertain hoặc chưa phân giải schema5/20; source-reference uncertain2/20 là khái niệm khác.

## Metric theo annotation gốc — không phải điểm leaderboard

Chỉ **8 raw archive source** có annotation gốc; 12 source confirmation do agent viết **không có annotation giảng viên**, không thay bằng reference agent. Trong8 có2 ca mới,6 ca investigation. Output taxonomy của8 ca giống nhau giữa hai nhánh, nên mọi số dưới đây bằng nhau. Thiếu output sẽ không được exact-clean và positive label bị FN; vòng này không thiếu output.

|Trên8 original annotations|R15|Candidate|
|---|---:|---:|
|Micro precision /recall /F1|0,2500 /0,1429 /0,1818|0,2500 /0,1429 /0,1818|
|Macro P /R /F1, đủ10 nhóm|0,1000 /0,1000 /0,1000|0,1000 /0,1000 /0,1000|
|Exact match|3/8|3/8|

|Nhóm chính thức|Support|TP|FP|FN|P/R/F1 (cả hai nhánh)|
|---|---:|---:|---:|---:|---|
|Lỗi biên dịch|3|0|0|3|0 /0 /0|
|Lỗi nhập/xuất|1|1|0|0|1 /1 /1|
|Lỗi logic|1|0|1|1|0 /0 /0|
|Lỗi vòng lặp|1|0|0|1|0 /0 /0|
|Lỗi mảng/chuỗi|0|0|1|0|0 /0 /0; không support|
|Lỗi hàm|0|0|1|0|0 /0 /0; không support|
|Lỗi edge case|0|0|0|0|0 /0 /0; không support|
|Lỗi thuật toán|0|0|0|0|0 /0 /0; không support|
|Lỗi hard-code|0|0|0|0|0 /0 /0; không support|
|Lỗi style|1|0|0|1|0 /0 /0|

Zero denominator quy ước0, macro gồm đủ10 nhóm. Trên **mới2**, exact2/2 của cả hai chỉ phản ánh annotation đều rỗng; không có positive support và source-review vẫn uncertain. Không gọi đó là nhận đúng bài đúng.

Bất đồng quan trọng: `SYN-COUNT-0004` có annotation `[]` nhưng reference chỉ ra yêu cầu phụ chưa thực hiện; `SYN-COUNTUPPER-0010` có style nhưng source chỉ hỗ trợ defect logic, không có quy định style bị vi phạm. Leading-space claim ở `SYN-DISTINCT-0003` thiếu comparator policy, nên disputed thay vì tự kết luận đúng/sai. Với `L2D-COUNT-02`, nhóm hàm của model có thể là cách gán hợp lý khác đề xuất IO/logic của reference; không sửa reference khóa hay tính lại original gold. Mọi ca có annotation, review và ý kiến tranh luận riêng trong packet.

## Metric theo source review dự thảo

Các tỷ lệ clean/defect dưới đây **hoàn toàn đến từ tầng điều tra18**: clean5, defect13. Mới2 nằm bảng uncertain, không vào mẫu số clean/defect. Bảng tổng vẫn giữ đủ20 ID, gồm8 fallback. Location+cause xét11 defect L2+, không thưởng L1 vì lộ chẩn đoán. Strict còn đòi không false claim, không bỏ lỗi trọng tâm, không false-clean và đúng Level.

|Review metric|R15|Candidate|
|---|---:|---:|
|Clean bị taxonomy khác rỗng|4/5|1/5|
|Clean có taxonomy rỗng|1/5|4/5|
|Defect có taxonomy khác rỗng|12/13|8/13|
|Defect bị taxonomy rỗng|1/13|5/13|
|Defect được khen đúng (false-clean prose)|0/13|4/13|
|Bỏ sót/không chẩn đoán đúng lỗi trọng tâm|11/13|11/13|
|Đúng vị trí +nguyên nhân của lỗi được nói tới|1/11|2/11|
|Strict useful diagnosis|1/11|1/11|
|False technical claim chắc chắn|12/18 assessed +2 unknown|7/17 assessed +3 unknown|
|Vi phạm Level|4/20|5/20|
|L1 lộ nguyên nhân|1/5|1/5|
|L2 lộ hướng sửa|3/14|3/14|
|L3 thiếu hướng sửa khả thi|1/1|1/1|
|L4|không support|không support|
|Nghiêm trọng theo rubric|14/20|11/20|

Level3 baseline có lời khuyên nhưng lời khuyên dựa trên chẩn đoán sai và thao tác đã có; candidate tìm được lỗi thật nhưng không đưa hướng sửa. Vì vậy baseline không bị đánh dấu *thiếu bước sửa về hình thức*, nhưng cả hai đều0/1 hướng sửa khả thi. Taxonomy/feedback mismatch rõ ở `SYN-COUNTUPPER-0010`: prose thừa nhận lỗi nhưng taxonomy rỗng, giữ nguyên qua fallback. Unknown technical claims là các claim phụ thuộc cận input/comparator hoặc lời khẳng định correctness chưa phân xử; không chuyển null thành pass. Severe đếm mỗi ID một lần khi bịa lỗi trên clean, khen sai, có false technical claim chắc chắn, hoặc bỏ lỗi chính ở defect L2+; chỉ là rubric nội bộ.

## Từng ID — mô tả đã lược source

`F` = candidate dùng nguyên R15; `U` = reference uncertain. Full source, exact feedback, quote, symbolic evidence và cả raw attempts nằm trong private packet, không ở Git.

|ID|Tầng /review|R15|Candidate và nguyên nhân thay đổi|
|---|---|---|---|
|SYN-GCDARR-0000|mới /U|Không thấy lỗi rõ|F; diagnosis bịa điều kiện luôn đúng, render lộ chẩn đoán L1 nên bị loại; fallback tránh đưa claim đó ra final|
|SYN-MAXARR-0001|mới /U|Không thấy lỗi rõ|Taxonomy giữ rỗng; lời kết luận trở nên tuyệt đối hơn, không giải quyết thiếu cận đề|
|SYN-COUNT-0004|template /defect|Nêu capacity có điều kiện, bỏ yêu cầu phụ còn trống|F; candidate cũng để uncertain ở yêu cầu có thể chỉ rõ defect|
|SYN-COUNTUPPER-0010|template /defect|Nêu cơ chế thật nhưng L1 lộ nguyên nhân, taxonomy rỗng|F; diagnosis còn bịa cơ chế phủ định phép so sánh, retry render không qua guard|
|SYN-DISTINCT-0003|template /defect|Tập trung định dạng còn tranh luận, bỏ compile blocker; L2 sửa|Candidate giữ lỗi này; exact quote có thật nhưng không chứng minh comparator policy|
|SYN-MAXARR-0004|template /defect|Sai nguyên nhân vòng lặp, lời sửa không hữu ích|Tìm đúng phần tử cuối bị bỏ; vẫn bỏ compile blocker và thiếu hướng sửa L3|
|SYN-PERFECT-0000|template /defect|Native fallback chung chung, sai nhóm trọng tâm|F; uncertain vì suy sai rằng entry point cần tham số, không tìm đúng compile blocker|
|SYN-PERFECT-0001|template /clean|Không bịa lỗi|F; diagnosis không phủ đúng tập P nên bị loại; kết quả đúng nhờ baseline|
|L2D-COUNT-01|confirmation /clean|Bịa thiếu khai báo cấu trúc|Nhận clean, bỏ lỗi bịa; diagnosis chỉ diễn đạt lại yêu cầu nên chưa phải cơ chế xác minh|
|L2D-COUNT-02|confirmation /defect|Đúng vị trí/nguyên nhân không đọc file|F; candidate nhận ra hành vi trong prose nhưng vẫn gọi uncertain; không tạo lợi ích riêng|
|L2D-COUNT-03|confirmation /defect|Đúng hàm nhưng bịa thiếu đối số|Khen đúng dù có toán tử thiếu toán hạng; chuyển từ chẩn đoán sai sang false-clean|
|L2D-PROD-01|confirmation /clean|Bịa compile error từ mảng hợp lệ trên miền đã cho|Nhận clean; cùng kiểu nhận định all-correct sẽ gây hại ở hai ca kế tiếp|
|L2D-PROD-02|confirmation /defect|Bịa thiếu khai báo, bỏ phép ghi đè tích lũy|Khen đúng; lặp yêu cầu tính tổng thay vì mô tả phép gán thực tế|
|L2D-PROD-03|confirmation /defect|Bịa lỗi vòng lặp phụ, bỏ parser không khớp separator|Khen đúng; không kiểm tra hành vi đọc file đối với domain CSV rõ ràng|
|L2D-COUNTGT-01|confirmation /clean|Bịa truy cập con trỏ khi dùng sentinel hợp lệ|Nhận clean; giảm false accusation có căn cứ từ source review|
|L2D-COUNTGT-02|confirmation /defect|Đúng biểu thức nhưng bịa luôn true|Diagnosis thấy so sánh rộng hơn yêu cầu, final đảo sai quan hệ và lộ biểu thức thay thế L2|
|L2D-COUNTGT-03|confirmation /defect|Bịa chia0 trái miền đề và gợi ý check|Bỏ chia0, tìm đúng biểu thức; chưa giải thích mất phần thập phân, vẫn đưa sửa cụ thể L2|
|L2D-SUMPAIR-01|confirmation /clean|Bịa bỏ phần tử cuối dù predecrement trước dùng|F; diagnosis nhận clean, renderer lại sinh nhãn lỗi hai lần; consistency check gây quay về lỗi bịa cũ|
|L2D-SUMPAIR-02|confirmation /defect|Bịa recursion không tiến, bỏ gọi nhầm hàm xuất|F; uncertain ở các hàm đúng dù domain đã giới hạn; không giúp phát hiện lỗi output|
|L2D-SUMPAIR-03|confirmation /defect|Khuyên đổi phép tăng đã đúng, bỏ thiếu thành phần tổng|Khen đúng; lời mô tả behavior sao chép yêu cầu thay vì đối chiếu toán hạng thực tế|

Điểm tốt không bền: giảm cáo buộc trên3 clean đến cùng một thói quen paraphrase/all-correct, cũng tạo4 false-clean mới. Trích source thật vẫn cho phép kết luận ngữ nghĩa sai; kiểm quote không thể nhận ra một lỗi đã bị model bỏ qua hoàn toàn. Lượt render có thể phá finding tương đối đúng hoặc lộ sửa ở L2; fallback có thể khôi phục lỗi bịa từ R15. Không có bằng chứng rằng làm schema/guard chặt hơn sẽ giải quyết cơ chế này, nên không thêm regex hoặc fine-tune từ finding chưa được người review xác nhận.

## Handoff và tái hiện

Private ignored root: **`outputs/task3/requirement-evidence-20261021/`**. Local archive: **`review-bundle.tar.gz`**, sidecar **`review-bundle.tar.gz.sha256`**, manifest **`MANIFEST.sha256`**. File lớn/nhạy cảm không được stage. Manifest/hash và kiểm preservation/ID/journal/metrics đầy đủ trong `bundle-verification.json`; HEAD/status cuối trong `final-handoff.json`.

|Cần review|Đường dẫn tương đối trong private root|
|---|---|
|ID/hash/Level/family/origin/rule freeze|`frozen-selection.private.json`, `study-freeze.json`|
|Reference/uncertain/disputes/annotation/teacher|`reference-review.private.json`|
|R15 mọi ID, raw, fallback, trace|`R15/predictions.json`, `R15/attempts.jsonl`, `R15/decisions.jsonl`, `R15/traces.json`, `R15/run.json`|
|Candidate mọi ID, raw, diagnosis/evidence/fallback|`candidate/predictions.json`, `candidate/attempts.jsonl`, `candidate/results.private.json`|
|Full paired đề/source/annotation/output/evidence|`paired-ledger.private.json`, `paired-ledger.private.csv`|
|40 verdict và authority|`semantic-review.private.json`, `semantic-review-freeze.json`|
|Model/config/dependencies/input hashes/exposure|`resolved-config.json`, `runtime-before.json`, `run.json`, `inventory.private.json`, `raw-inventory.private.json`|
|Selection exclusions/nearest/template/provenance|`selection-rejections.private.json`, `raw-selection-rejections.private.json`, `raw-candidate-pool.private.json`|
|Scores đủ strata/mẫu số/unknown, code snapshot|`metrics.json`, `implementation/`|

Từ repository hiện tại, các lệnh chỉ kiểm tra/tái tính, không gọi model:

```bash
.venv-task3/bin/python scripts/task3_requirement_evidence.py --verify-only
.venv-task3/bin/python scripts/task3_requirement_report.py
.venv-task3/bin/python -m pytest tests/test_task3_requirement_evidence.py tests/test_task3_requirement_report.py tests/test_task3_round15.py tests/test_task3_round15_runner.py tests/test_task3_round15_disclosure.py tests/test_task3_round15_selection.py tests/test_task3_feedback_prompt.py tests/test_task3_feedback_prompt_report.py tests/test_task3_level2_prompt.py -q
.venv-task3/bin/python outputs/task3/requirement-evidence-20261021/audit.private.py
```

Inference đã chạy bằng `.venv-task3/bin/python scripts/task3_requirement_evidence.py` sau freeze; CLI cố ý từ chối chạy đè một completed study. Các script prepare/freeze, môi trường, prompt và mọi raw result được giữ trong bundle để phục dựng pre-run snapshot khi cần tái chạy độc lập; không xóa marker hay chọn output đẹp hơn. Không cần chạy public để review kết quả này.

Validation: **144 focused artificial regression tests passed**. Một reviewer code độc lập không tìm thấy issue có thể hành động trong candidate/config/runner/tests được giao; reviewer đó không chấm source, split, output hay bundle. Tác giả tự audit các phần còn lại, không gọi chúng là xác nhận độc lập/human review. Các giới hạn dữ liệu và authority là điều kiện của kết luận, không phải lỗi được metric che đi.

Bước tiếp theo đề xuất: người review xác nhận4 false-clean mới, clean bị bịa lỗi và các ca Level2/cause truyền sai trong packet; sau đó cần nguồn train/dev mới có family/domain rõ để tạo tập40–60 thật sự tách biệt, có clean và defect đáng tin. Chưa có cơ sở huấn luyện từ các finding này, thay production hoặc dự đoán điểm leaderboard trên0,5.
