# Task 3 — feedback prompting offline, 2026-10-21

**Quyết định: GIỮ R15. Dừng trước public inference.** C không vượt các điều kiện đã khóa về L1/L2 disclosure, net wins L2/L3 và false-clean L1. Không training, adapter, public inference, tạo bộ328, push hoặc upload leaderboard.

## Protocol và giới hạn bằng chứng

Bối cảnh lịch sử duy nhất dùng điểm public: R15 zero-shot **0.3834 public**, DIRECT SFT v1 **0.1517 public**, v2 chưa nộp. Đây không phải điểm private; kết quả proxy dưới đây không dự báo điểm leaderboard hay cam kết vượt0.5. Artifact/kết luận lịch sử được giữ nguyên.

Branch `feat/task3-quality-round5`; parent HEAD `1a5c32386f29dc20acb0260da387694e8384013c`. Làm tại checkout hiện tại, không worktree/clone. Giữ nguyên630 đường dẫn đã hash lúc bắt đầu, gồm root predictions và các artifact lịch sử được bảo vệ.

Đã đọc trực tiếp header metadata Task3 và label_space của sample/release, không đọc public sample/source/output để thiết kế prompt hoặc chọn ví dụ. Sample có taxonomy trong input và chỉ feedback trong output; release bỏ input taxonomy, yêu cầu output taxonomy_error + feedback. Release mô tả một điểm feedback: lộ lời giải/code L1–2 nhận0; còn lại chấm chẩn đoán đối chiếu nhãn và nhận xét giảng viên. Không mô tả taxonomy F1 riêng. Định nghĩa Level sample/release giống nhau. Không suy đoán hidden grader. Trả lời của thầy được ghi nhận là context do người dùng cung cấp, không phải xác minh độc lập.

|Tệp|SHA-256|
|---|---|
|`data/raw/sample_dataset/task3_feedback.json`|`d27118a81b0723bc68aecb7c4cf4096d3f6712a85dc938ef39ba57fe71d2c47e`|
|`data/raw/sample_dataset/label_space.json`|`2e21d225a20609c3adac8c0c95110d08c18dc8982d083879b8029fea2286c715`|
|`data/raw/public_test_release/task3_feedback.json`|`6020f0687f661dadf11600a8c50cb7c6cec6cef347ef13f71b09be42a6e631bb`|
|`data/raw/public_test_release/label_space.json`|`056a4d1a0ccfd60688b43efdf5df64a4c1310e3c6f1d99ab813691a2da27a9dc`|

Qwen/Qwen2.5-Coder-7B-Instruct, revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`; NF4, compute BF16, GPU RTX5090, seed42, greedy. Template SHA `cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f`. Cả5 run xác nhận revision/precision/template giống nhau; không adapter. Context16384; output1024, L4=1536; tối đa3 attempts, generation max_time45s; cùng parser/schema/guard/retry/fallback R15. A dùng nguyên văn prompt/controller R15. B thêm chỉ dẫn chọn một finding chắc nhất và sinh thẳng JSON. C cùng B, tối đa2 ví dụ train cùng Level,2 family khác nhau, xếp bằng hash query-code/bank-ID, bỏ ví dụ cuối nếu vượt budget; không cắt source.

Khác biệt với run R15 lịch sử: compiler evidence trong **mọi arm của lượt này** là unavailable, vì không có sandbox C++ khả dụng. Không chạy/compiler-confirm source đánh giá; chỉ trace testcase tĩnh và agent review. Legacy synthesis tests riêng có compile/chạy fixture xác định từ repo trong thư mục tạm; không được dùng làm bằng chứng kiểm chứng source đánh giá.

Calibration gồm đủ6 real-val +47 synthetic-heldout đã exposed; có exact duplicates lịch sử, không gọi là benchmark mù. Bank24 demonstration/6 source/6 family: BASE2, COUNTVOWEL, UPPER, COUNTUPPER, POWER, GCDARR. Cả6 là prepared synthetic-train, code/statement/provenance đối chiếu; Level override ghi rõ. Feedback ví dụ tự viết theo source, không chép teacher/gold. Hai ví dụ clean sửa bất đồng style annotation chỉ trong bank review, không sửa gold lịch sử. Evaluation families không trùng6 bank families.

Bộ mới:48 source synthetic viết mới từ12 đề TRAIN, ban đầu12/Level, mỗi Level3 clean+9 defect. Có domain restriction ghi riêng từng source; chỉ single_problem, thiếu file/multi-problem coverage. Lọc ID/group/raw/token/renamed hash và lexical/structural5-gram Jaccard>=0.75 qua521 prepared train,53 calibration,627 newer train archive, v1/v2 reserves, bank và pairwise mới. Hai draft bị loại và một draft gần template được thay trước freeze; không đổi prompt sau calibration hay output bộ mới.

**Rà soát sau freeze không xác nhận đủ48 source độc lập.** Review agent không xem output chỉ ra hai nhóm rõ; tác giả cách ly thêm hai ca thận trọng. Giữ nguyên48 input/reference/output đã khóa, cho4 ca điểm0/unknown trong bảng chính và báo sensitivity44 ca còn lại;44 cũng không được gọi là benchmark độc lập mù. Không nới bất kỳ threshold nào khi thiếu48. Các ca cách ly: `FPNEW-03-4`, `FPNEW-05-4`, `FPNEW-04-3`, `FPNEW-11-3`. Phân bổ subset44: L1=12,L2=12,L3=10,L4=10. Lỗi của prefreeze dedup là dùng nhận xét template chung cho mọi survivor; quarantine ledger ghi rõ để reviewer không tin assertion đó như chứng cứ.

Mỗi nguồn có đề, domain, code, requested Level, clean/defect, core finding/clean basis, quote/line, static testcase trace, taxonomy, provenance và trạng thái agent-reviewed. FPNEW-09-3 có recursion tới50 triệu frame; sửa comparator cục bộ chưa chứng minh khả thi toàn miền. Không có human-verified/compiler-confirmed claim.

Rubric đã khóa trong [TASK3_FEEDBACK_PROMPT_RUBRIC_20261021.md](TASK3_FEEDBACK_PROMPT_RUBRIC_20261021.md): proxy0/.5/1, sai kỹ thuật nghiêm trọng/false-clean/vi phạm Level=>0; L1/2 concrete repair=>0; generic L2=>0. Coverage chỉ core finding, không được hiểu là bao phủ mọi lỗi. Taxonomy là bảng phụ đối chiếu **source-reviewed core reference**, không phải F1 chính thức. Calibration review thấy tên arm; fresh review dùng X/Y xáo trộn riêng từng ID, khóa đủ96 verdict trước mở key. Tác giả có thể đoán arm từ phong cách nên đây là blinding hạn chế, không độc lập human.

## Calibration (53 ca/arm, prior exposure)

|Arm|Proxy|L1|L2|L3|L4|False claim|False-clean|Generic|Semantic Level violation|Repair disclosure|Retries/fallback|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|A|0.3208|0.4167|0.2778|0.2143|0.1250|18|9|6|7|7|14/6|
|B|0.3302|0.2917|0.4444|0.2143|0.2500|14|0|12|13|3|8/1|
|C|0.4151|0.5000|0.5000|0.1429|0.0000|17|12|3|1|0|7/3|

Chọn C theo mean proxy; tie rule là ít false claim hơn rồi B, không dùng F1. B so A:11 thắng/12 thua/30 hòa. C so A:12 thắng/7 thua/34 hòa. C vẫn kém ở chẩn đoán L3 và false-clean; không loại C bằng quy tắc mới sau calibration. Full53-ID ledger/reasons nằm trong bundle.

## Bộ mới: A so C, một pass

|Scope|N/arm|A proxy|C proxy|C wins/loss/tie|Net|L2 net|L3 net|
|---|---:|---:|---:|---|---:|---:|---:|
|Frozen48,4 unknown chấm0|48|0.3438|0.4688|15/8/25|+7|+1|−1|
|Sensitivity44, bỏ4 ca cách ly|44|0.3750|0.5114|15/8/21|+7|+1|−1|

Mức0.5114 là proxy offline trên subset tự tạo, **không phải điểm private/public hoặc bằng chứng vượt0.5 leaderboard**. Paired bootstrap10.000 lần, seed20261021: chênh mean full48=0.125,95% interval[−0.03125,0.28125]; subset44=0.1364,[−0.0341,0.3068]. Đây là mô tả, phụ thuộc family và chủ quan review, không phải uncertainty chính thức.

|Level (frozen48)|N|A proxy|C proxy|C win/loss/tie|
|---|---:|---:|---:|---|
|1|12|0.4167|0.6667|6/2/4|
|2|12|0.3333|0.4167|2/1/9|
|3|12|0.4583|0.3750|2/3/7|
|4|12|0.1667|0.4167|5/2/5|

|Final behavior (48)|A|C|
|---|---:|---:|
|false_technical_claim|18|14|
|false_clean|5|8|
|location_correct|15|17|
|cause_correct|15|17|
|feasible_repair|4|7|
|generic|6|1|
|level_violation|6|3|
|repair_disclosure|3|3|
|unknown|4|4|
|fallback|6|1|
|retries|15|3|
|raw_first_regex_disclosure|9|2|
|final_regex_disclosure|0|0|

Các regex guard final đều không phát hiện disclosure, nhưng manual semantic review vẫn thấy3 concrete repairs ở C L2: FPNEW-04-2,07-2,09-2. L1 false-clean A=1,C=4. Location/cause/repair flags là thuộc tính review, không suy từ taxonomy; số false-clean không gộp vào false-technical-claim để tránh giấu một failure mode.

|Điều kiện khóa|Kết quả|
|---|---|
|all_complete_valid|PASS|
|no_l1_l2_repair_disclosure|FAIL|
|false_technical_claim_not_increased|PASS|
|net_wins_ge6|PASS|
|l2_net_ge3|FAIL|
|l3_net_ge1|FAIL|
|l1_false_clean_not_increased|FAIL|
|no_unresolved_material_unknown|FAIL|

Không đạt no-disclosure, L2>=3, L3>=1, L1 false-clean không tăng; còn material unknown. Net tổng+7 và fewer false claim không bù được các gate fail. Giữ R15, không tạo public candidate.

## Taxonomy phụ

|Scope/arm|Micro-F1|Macro-F1, đủ10 nhãn|
|---|---:|---:|
|calibration/A|0.2895|0.1493|
|calibration/B|0.2400|0.1403|
|calibration/C|0.2632|0.1551|
|fresh/A|0.6571|0.1412|
|fresh/C|0.5758|0.1053|

Gold taxonomy/teacher của calibration không vào prompt; bảng F1 này dùng core-source reference do review tạo, không phải annotation đầy đủ hay metric thắng. Few-shot làm giảm fallback nhưng vẫn có lỗi kỹ thuật/false-clean. Thay đổi F1 không đảo quyết định feedback.

## Paired ledger (đủ48 ID)

FT=false technical claim; FC=false-clean; LV=Level violation; RD=repair disclosure; G=generic; U=source independence unknown. Quote source, toàn văn output và lý do kỹ thuật từng arm giữ riêng trong bundle, không stage dữ liệu bài làm.

|ID|L|Family|A|C|Quan hệ|A lỗi/thiếu|C lỗi/thiếu|
|---|---:|---|---:|---:|---|---|---|
|FPNEW-01-1|1|SYN-DIGITSUM|1|1|tie|Đúng core/scope|Đúng core/scope|
|FPNEW-01-2|2|SYN-DIGITSUM|0|1|win|FT,LV,RD|Đúng core/scope|
|FPNEW-01-3|3|SYN-DIGITSUM|0|1|win|FT|Đúng core/scope|
|FPNEW-01-4|4|SYN-DIGITSUM|0.5|1|win|Thiếu hướng sửa khả thi|Đúng core/scope|
|FPNEW-02-1|1|SYN-REVSTR|0|1|win|LV|Đúng core/scope|
|FPNEW-02-2|2|SYN-REVSTR|1|1|tie|Đúng core/scope|Đúng core/scope|
|FPNEW-02-3|3|SYN-REVSTR|1|0|loss|Đúng core/scope|FT|
|FPNEW-02-4|4|SYN-REVSTR|0.5|0|loss|Thiếu hướng sửa khả thi|FT|
|FPNEW-03-1|1|SYN-PRIME|0.5|0|loss|G|FC|
|FPNEW-03-2|2|SYN-PRIME|0|0|tie|FT|FT|
|FPNEW-03-3|3|SYN-PRIME|1|1|tie|Đúng core/scope|Đúng core/scope|
|FPNEW-03-4|4|SYN-PRIME|0|0|unknown|FT,U|FT,U|
|FPNEW-04-1|1|SYN-SUMEVEN|0.5|1|win|G|Đúng core/scope|
|FPNEW-04-2|2|SYN-SUMEVEN|0|0|tie|FT,LV,RD|FT,LV,RD|
|FPNEW-04-3|3|SYN-SUMEVEN|0|0|unknown|U|U|
|FPNEW-04-4|4|SYN-SUMEVEN|0|1|win|FT|Đúng core/scope|
|FPNEW-05-1|1|SYN-MAXARR|0.5|1|win|G|Đúng core/scope|
|FPNEW-05-2|2|SYN-MAXARR|1|1|tie|Đúng core/scope|Đúng core/scope|
|FPNEW-05-3|3|SYN-MAXARR|0.5|0.5|tie|Thiếu hướng sửa khả thi|Thiếu hướng sửa khả thi|
|FPNEW-05-4|4|SYN-MAXARR|0|0|unknown|FC,U|FC,U|
|FPNEW-06-1|1|SYN-FIB|0.5|1|win|G|Đúng core/scope|
|FPNEW-06-2|2|SYN-FIB|0|1|win|FT|Đúng core/scope|
|FPNEW-06-3|3|SYN-FIB|0.5|0|loss|Thiếu hướng sửa khả thi|FC|
|FPNEW-06-4|4|SYN-FIB|0|1|win|FT|Đúng core/scope|
|FPNEW-07-1|1|SYN-SECONDMAX|0|1|win|FT,LV|Đúng core/scope|
|FPNEW-07-2|2|SYN-SECONDMAX|1|0|loss|Đúng core/scope|FT,LV,RD|
|FPNEW-07-3|3|SYN-SECONDMAX|0|0|tie|FT|FT|
|FPNEW-07-4|4|SYN-SECONDMAX|0|0|tie|FT|FT|
|FPNEW-08-1|1|SYN-FACT|0.5|1|win|G|Đúng core/scope|
|FPNEW-08-2|2|SYN-FACT|0|0|tie|FC|FC|
|FPNEW-08-3|3|SYN-FACT|1|0|loss|Đúng core/scope|FT|
|FPNEW-08-4|4|SYN-FACT|0|1|win|FT|Đúng core/scope|
|FPNEW-09-1|1|SYN-PERFECT|1|1|tie|Đúng core/scope|Đúng core/scope|
|FPNEW-09-2|2|SYN-PERFECT|0|0|tie|FC|FT,LV,RD|
|FPNEW-09-3|3|SYN-PERFECT|0|0|tie|FT|FT|
|FPNEW-09-4|4|SYN-PERFECT|0|1|win|FT|Đúng core/scope|
|FPNEW-10-1|1|SYN-PALIN|0.5|0|loss|G|FC|
|FPNEW-10-2|2|SYN-PALIN|1|1|tie|Đúng core/scope|Đúng core/scope|
|FPNEW-10-3|3|SYN-PALIN|1|1|tie|Đúng core/scope|Đúng core/scope|
|FPNEW-10-4|4|SYN-PALIN|1|0|loss|Đúng core/scope|FT|
|FPNEW-11-1|1|SYN-DISTINCT|0|0|tie|FC|FC|
|FPNEW-11-2|2|SYN-DISTINCT|0|0|tie|FC|FC|
|FPNEW-11-3|3|SYN-DISTINCT|0|0|unknown|FT,U|U|
|FPNEW-11-4|4|SYN-DISTINCT|0|0|tie|FT|FT|
|FPNEW-12-1|1|SYN-ARM|0|0|tie|LV|FC|
|FPNEW-12-2|2|SYN-ARM|0|0|tie|FT,LV,RD|G|
|FPNEW-12-3|3|SYN-ARM|0.5|1|win|Thiếu hướng sửa khả thi|Đúng core/scope|
|FPNEW-12-4|4|SYN-ARM|0|0|tie|FT|FT|

## Verification và bàn giao

13 test protocol mới pass; tập experiment + R15 **108 pass**. Task3 đầy đủ: **1031 pass,2 skip,1 fail** (`test_task3_eval_v2.py::test_v2_plan_preserves_v1_and_does_not_read_prediction_or_public_inputs`). Test này kỳ vọng root predictions hash R15 `9ba741…`; root đã là `c30c5c…` trước lượt này và giữ nguyên. Không sửa artifact để làm test xanh.

Full `pytest -q`:2 collection errors do thiếu sklearn. Run `--continue-on-collection-errors` dừng fixture synthesis sau khoảng11 phút (không hoàn tất; exit143). Run tiếp toàn repo trừ `tests/test_synth_build.py`: **1290 pass,8 skip,12 fail,2 collection errors**.11 fail ngoài Task3 thuộc:2 Colab secrets/mock-env,2 synth-gate fixture mismatch,7 Task2 thiếu sklearn. Tên từng test và exception có trong logs bundle; không gọi toàn repo pass. Không cài thêm dependency hay sửa subsystem khác.

Review độc lập bằng agent tìm thấy shallow-whitelist nhận nested metadata. Frozen renderer không đổi sau inference. Test mới/read-only auditor từ chối nested teacher/reference trong field được phép; **302 actual attempts** đã replay nguyên văn và audit mọi payload scalar, không có leak đó trong run hiện tại. Đây là audit dữ liệu thực tế, không tuyên bố renderer tổng quát đã được harden cho mọi input. Manifest binding và schema validator pass cho255 final outputs; input/code đầy đủ, parser/guard/retry giữ nguyên.

Artifacts riêng tư: `outputs/task3/feedback-prompt-20261021/`. Review bundle: `outputs/task3/feedback-prompt-20261021/review-bundle.tar.gz` kèm outer `.sha256`, bên trong `MANIFEST.sha256`. Bundle gồm prompts A/B/C nguyên văn, bank/provenance, code/config/freeze SHA, rubric, nguồn/reference, mọi raw/rendered/final output, đủ53-ID calibration và48-ID fresh ledger, full48 pairs và>=16 cặp chọn để đọc trải Level/win/loss/tie/unknown. Không chứa public source/output, adapter/weights hoặc secrets. Report JSON aggregate tracked là `TASK3_FEEDBACK_PROMPT_RESULTS_20261021.json`.

Giới hạn: agent-created/source-reviewed, blinding hạn chế, family đã exposed, calibration có duplicates,4 ca independence unresolved,44 sensitivity không đủ quota12 mỗi Level, không compiler evidence, thiếu multi-problem fresh, proxy/secondary-taxonomy chủ quan và chỉ core finding. Người review cần kiểm lại source/reason/flags; mọi quyết định public dành cho lượt sau.

Lượt source reviewer bị automatic approval review từ chối đọc prepared/archive comparison sources vì lo có real/public data. Reviewer không thử lại; nearest-train template comparison của FPNEW-11-3 được để unresolved và cách ly. Các bước khác hoàn tất trên artifact được phép; không cần mở public để bàn giao.

Dừng tại commit offline. Không push, không public inference, không tạo predictions328 mới, không upload leaderboard.
