# Task 3 — kiểm chứng ngôn ngữ chỉ dẫn × precision, 24/10/2026

## Thiết kế và provenance

Thí nghiệm 2×2 chạy mới trên cùng30 ID nội bộ đã seen,27 code hash riêng; không phải holdout. Mỗi Level1/2/3 có10 ID, không đánh giá L4. Ba gold-clean đều ởL1; reference nguồn tĩnh có6 source-clean và33 finding inventory theo ID, có clone lặp. Giữ gold gốc và tranh luận source riêng. Không dùng328 ID public.

HEAD ban đầu35c29158b4032d76a0c5344a49eaf5de347cbb51 đúng commit tham chiếu; không có diff tracked, chỉ prompt người dùng untracked. Nhánh `experiment/task3-language-precision-2x2`, worktree `/workspace/llm-final-project-ablation`, dùng symlink đọc artifact/cache/dataset, không copy model/data. Freeze inference ở commit143b78b, SHA256 `2e6251729326309219b1f477ec4efb4c042971d720da34eafe8048a5d21dbd02`. Code/report bổ sung sau freeze không được import vào inference.

Archive ngoài SHA256 `8c04e4e01be73952cb255fb5efd707c758205c19457fa651d944fc02780a3e1e`; nested ZIP SHA256 `88eff95f2841efd061ab0203907f9142ad6a2a2b72e266a4d55043a50aedac9c`. Code bytes, đề semantic hash, family, gold và requested Level khớp archive/metadata; evidence vẫn compiler unavailable/tests not_run. Không suy Level từ suffix ID. Manifest, source references/seals và source/gold giữ riêng trong artifact ignored.

A=VI/NF4, B=EN/NF4, C=VI/BF16, D=EN/BF16. A=C giữ nguyên byte các hằng VI findings-v1; B=D dùng đúng một bản EN đã đối chiếu từng đoạn rồi freeze trước call đầu. Đề/code/evidence, JSON keys,10 nhãn tiếng Việt, định nghĩa chính thức duy nhất của requested Level giữ nguyên. Negative placeholder và các từ em/bạn/mình/thầy/tôi giữ trong bản EN. Mọi arm phải feedback tiếng Việt; không có dịch lần3.

Hai lượt fresh messages: findings trước, runner union taxonomy theo thứ tự chính thức, rồi renderer chỉ nhận findings/taxonomy của chính arm/ID. Parser và Journal cũ giữ nguyên. Không retry, fallback, semantic guard, sửa JSON, sửa đại từ/placeholder, reuse stage1, chọn response hoặc thử thêm prompt.

## Hoàn tất và taxonomy trên mẫu số30

|Arm|Complete|Unresolved|Micro-F1|Macro-F1 (10 nhóm)|Exact/30|Precision|Recall|TP/FP/FN|
|---|---:|---:|---:|---:|---:|---:|---:|---|
|A|29|1|0.3810|0.3070|4|0.3846|0.3774|20/32/33|
|B|29|1|0.3673|0.1808|2|0.4000|0.3396|18/27/35|
|C|30|0|0.3303|0.1973|1|0.3214|0.3396|18/38/35|
|D|30|0|0.4423|0.2841|2|0.4510|0.4340|23/28/30|

Unresolved dùng prediction rỗng chỉ để tính TP/FP/FN và F1 (zero_division=0), nhưng luôn fail exact/joint, không tạo output sạch. Mọi stage1 valid đều có stage2 complete ở run này, nên stage1 taxonomy và final taxonomy trùng các số trên; hai cột vẫn lưu riêng trong JSON. A/B mỗi arm có1 enum failure ở stage1; JSON/escape/EOS/context/OOM failure đều0. Không gọi stage2 sau lỗi stage1.

Validator: A/B chỉ VALID completed-subset29 theo đúng Level map; không có predictions.json đầy đủ. C/D VALID full30, có predictions.json. Status vẫn đủ30/arm. Không arm nào có findings=[]; fixture clean không phải empirical clean success.

|Metric|B−A (EN ởNF4)|D−C (EN ởBF16)|C−A (BF16 ởVI)|D−B (BF16 ởEN)|Tương tác (D−C)−(B−A)|
|---|---:|---:|---:|---:|---:|
|micro_f1|-0.0136|+0.1120|-0.0507|+0.0750|+0.1256|
|macro_f1|-0.1262|+0.0868|-0.1098|+0.1033|+0.2131|
|exact_match|-0.0667|+0.0333|-0.1000|+0.0000|+0.1000|
|precision|+0.0154|+0.1296|-0.0632|+0.0510|+0.1142|
|recall|-0.0377|+0.0943|-0.0377|+0.0943|+0.1321|

Taxonomy gold không cho thấy EN tăng đồng đều: micro-F1 giảm ởNF4 nhưng tăng ởBF16; BF16 giảm vớiVI, tăng vớiEN. Đây là tương tác mô tả trên tập nhỏ đã seen, không phải significance hay generalization. Thay ngôn ngữ tác động cả detector và renderer, không phải hiệu ứng renderer riêng.

|Arm|Placeholder nguyên câu L1|L2|L3|Tổng|
|---|---:|---:|---:|---:|
|A|8|0|2|10|
|B|0|0|0|0|
|C|6|0|1|7|
|D|0|0|0|0|

Đếm nguyên câu sau parser, bỏ khoảng trắng ngoài: “Chương trình cần được kiểm tra lại.”. Các biến thể chung được reviewer chấm riêng; không gộp mọi lờiL1 khái quát thành placeholder.

## Precision, GenerationConfig và runtime

Qwen/Qwen2.5-Coder-7B-Instruct, revision c03e6d358207e414f1eca0bb1891e29f1db0e242; seed42, do_sample=false, few_shot_k=0, context16384, token cap1536/1024, max_time45, tối đa2 calls/sample, concurrency1. Checkpoint kế thừa repetition_penalty1.1, num_beams1, EOS[151645,151643], pad151643; temperature0.7/top_p0.8/top_k20 không điều chỉnh và không dùng làm biến sampling. Toàn bộ GenerationConfig trước generate và kwargs override lưu riêng theo stage/arm; max_new_tokens ưu tiên hơn max_length kế thừa khi generate dựng stopping limit từ chiều dài input.

A/B load NF4 4-bit, double quant,196 Linear4bit, compute BF16; parameter storage UINT8=3.262.644.224 elements và tensor không lượng tử hóa FP16=1.090.328.064 elements. Không gọi NF4 là model BF16. C/D load checkpoint gốc không lượng tử hóa:7.615.616.512 parameters đều BF16 trêncuda:0, is_loaded_in_4bit=false,0 Linear4bit. Không dequantize, FP16 fallback hay CPU/disk offload. So sánh precision là hai load path đã quy định, gồm khác biệt dtype tensor không lượng tử hóa.

Cùng RTX5090 (32.607MiB), SDPA, torch2.8.0/CUDA12.8, transformers4.57.1, tokenizers0.22.2, bitsandbytes0.48.1, accelerate1.11.0; driver590.48.01 (driver báo CUDA13.1 khác toolkit torch12.8). TF32 matmul=false, cudnn=true; matmul precision=highest; cudnn benchmark=false/deterministic=false, deterministic algorithms=false; SDPA flash/mem_efficient/math đều enabled. Giữ nguyên giữa arm. Tokenizer/chat template hash khớp reference; full tokenizer hash nằm trong freeze.

Lịch chốt trước chạy: A30→B30, giải phóng NF4, C30→D30. Đúng2 loads, không crash/reload,0 warm-up/smoke/extra Qwen calls. A chạy mới,59 raw responses trùng byte historical findings-v1 C59/59; đây là kiểm reproducibility sau chạy, không reuse historical responses.

|Arm|Calls/reservations|Stage1/2|Input tokens|Output tokens|Generate s|Peak allocated GiB|Peak reserved GiB|
|---|---:|---|---:|---:|---:|---:|---:|
|A|59/59|30/29|62420|9706|117.027|5.709|6.717|
|B|59/59|30/29|58498|9488|114.242|5.667|6.717|
|C|60/60|30/30|62740|8669|112.164|14.504|15.084|
|D|60/60|30/30|59393|8459|109.390|14.464|15.084|

Load latency NF4=5.424s, BF16=1.366s; main wall time=461.239s.238 calls,240 reservations maximum; actual238 reservations,0 interrupted,2 skipped renderer calls.238/238 responses kết thúc EOS. Timing chỉ là đo trên máy/lịch này; không phải benchmark deployment. Peak allocated reset mỗi arm; reserved bao gồm allocator cache đã có khi arm bắt đầu, nên B/D có thể giữ cache của A/C. Group/load peaks lưu riêng; không cộng load latency bốn lần. Reviewer agent calls là review ngoài inference, không cộng thành Qwen calls.

## Review nội dung và joint

Hai reviewer agent riêng đọc đủ30 ID×4 outputs mỗi người (240 assessments), ẩn arm/precision/prompt language và không đọc gold/key/raw. Source references có trước output mới. Subset12 cân bằng4/Level chốt trước inference; secondary mở rộng đủ30 để bao phủ mọi dispute. Ngôn ngữ prose không che hoàn toàn. Đây là review agent chưa được human validation; không dựng kết quả đồng thuận.

Good flags tổng hợp bằng AND, bad flags bằng OR; verdict finding ưu tiên false→unsupported→disputed→correct khi hai người khác nhau. Mọi nhận định/quote của từng reviewer vẫn giữ riêng. “Disputed” trong output không được joint credit; giới hạn miền input/capacity/style và alternative taxonomy giữ riêng, không tự coi mọi khác biệt gold là lỗi model. Ghi chú domain trong source reference được dùng yêu cầu secondary coverage; ghi chú điều kiện không tự làm mọi feedback của bài đó fail. Joint-source còn yêu cầu taxonomy khớp nguồn và không có source-label dispute.

Joint-gold = complete + taxonomy exact với gold gốc + feedback factual/faithful/bao phủ lỗi chính/đúng Level/vai tự nhiên + không placeholder/leak/new diagnosis hay dispute ảnh hưởng output. Joint-source là cột riêng theo reference nguồn; không thay gold. Factual đánh giá claim với source; faithful đánh giá chỉ diễn đạt findings. Renderer trung thành với finding sai vẫn có thể fail factual. Chẩn đoán mới đúng vẫn fail faithful.

|Arm|Findings đúng/sai/unsupported/disputed|Label đúng / findings|Đúng finding nhưng sai label|Recall inventory /33|Phát hiện lỗi chính /24 source-defective|Gold-clean gán lỗi /3|Source-clean gán lỗi /6|
|---|---|---|---:|---|---|---:|---:|
|A|21/34/15/12|31/82|0|22/33|15/24|3|6|
|B|11/27/9/21|33/68|0|15/33|12/24|3|6|
|C|20/30/12/12|34/74|0|20/33|16/24|3|6|
|D|8/24/9/24|30/65|0|17/33|13/24|3|6|

Finding inventory được đếm theo ID, có clone lặp; không phải33 lỗi độc lập trên33 source. Unresolved không được detector recall credit, vẫn ở mẫu số30 IDs và full inventory33. “Unsupported” gồm claim có thể đúng ở miền giả định chưa được đề/evidence xác nhận; “false” là sai/contradicted; “disputed” giữ ranh giới còn tranh luận. Label đúng không tự chứng minh finding đúng.

|Arm|Factual /30|Faithful /30|Main covered /30|Level /30|Vai tự nhiên /30|Feedback pass /30|Joint-gold /30|Joint-source /30|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|A|10|22|15|5|25|0|0|0|
|B|6|21|14|4|26|0|0|0|
|C|10|24|14|5|25|0|0|0|
|D|4|22|12|6|29|0|0|0|

|Arm|L1 detail leak /10|L2 repair leak /10|L3 actionable /10|Generic placeholder variant /30|Gọi bạn|Tự xưng|Meta|Có em (chỉ hỗ trợ)|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|A|2|3|4|10|4|0|0|0|
|B|5|5|5|5|0|0|3|8|
|C|4|5|3|7|5|0|0|2|
|D|7|6|3|3|1|0|0|7|

|Arm|Inherited false claims (envelope)|New false claims (envelope)|New diagnoses ngoài findings (envelope)|ID inherited/new|Reviewer disagreement IDs|Finding prose (primary)|
|---|---:|---:|---:|---|---:|---|
|A|25|9|8|15/7|24|{"vi": 27, "none": 1, "en": 1, "mixed": 1}|
|B|36|9|9|22/8|24|{"en": 26, "vi": 3, "none": 1}|
|C|32|7|6|19/7|18|{"vi": 30}|
|D|33|14|10|23/10|24|{"en": 23, "vi": 5, "mixed": 2}|

Attribution envelope lấy MAX theo từng ID và từng loại claim giữa reviewer, không phải tổng assertions đã deduplicate. Khi cùng claim bị một người gọi inherited và người khác gọi new, envelope có thể ghi ở cả hai loại; không cộng hai cột để khẳng định số claim độc lập. Counts từng reviewer riêng nằm trong metrics JSON/reviewer_separate_totals và artifact gốc. Finding language “mixed” có trường hợp Chinese, được chú thích trong reason; không gộp Chinese thành English, không suy ra model “suy nghĩ bằng tiếng Anh”. Feedback target vẫn tiếng Việt. Có em chỉ là thống kê token hỗ trợ, không tính voice pass.

### Độ nhạy với dispute gate

Scoring chính bảo thủ loại cả output có finding/label dispute, kể cả khi tranh luận không nằm trong câu feedback. Vì vậy feedback_pass0/30 không có nghĩa mọi câu đều sai nội dung. Bỏ riêng gate dispute nhưng giữ mọi điều kiện factual/faithful/main/Level/voice/placeholder/claim: feedback-core A/B/C/D=2/1/1/2 trên30; joint-gold vẫn0/0/0/0. Các ca và lý do nằm trong dispute-gate-sensitivity.private.json. Đây là phân tích độ nhạy minh bạch, không sửa rating/gold hoặc chọn output khác; kết luận không tăng joint-gold không phụ thuộc gate này.

### Paired so sánh trên cùng30 IDs

Mỗi ô: delta tổng đếm [wins/losses/ties]. Bảng này dùng full30 IDs; L1/L2/L3 có20 ID không áp dụng được tính0/tie. JSON paired_applicable_levels cung cấp đúng subset10 ID của từng Level để tránh hiểu nhầm20 ties đó. Với false/unsupported/placeholder/leak/claim càng thấp càng tốt: delta âm là cải thiện. Với metric tốt: delta dương là cải thiện. F1 aggregate và interaction ở bảng trên; JSON còn giữ delta trung bình, từng metric và stage1 riêng.

|Metric|B−A|D−C|C−A|D−B|Tương tác (delta count)|
|---|---|---|---|---|---:|
|finding_correct|-10 [0/9/21]|-12 [1/11/18]|-1 [2/3/25]|-3 [1/3/26]|-2|
|finding_false|-7 [8/7/15]|-6 [9/5/16]|-4 [6/6/18]|-3 [6/4/20]|+1|
|finding_unsupported|-6 [7/3/20]|-3 [7/4/19]|-3 [5/3/22]|+0 [4/3/23]|+3|
|main_detected|-3 [1/4/25]|-3 [2/5/23]|+1 [2/1/27]|+1 [1/0/29]|+0|
|factual|-4 [1/5/24]|-6 [0/6/24]|+0 [4/4/22]|-2 [1/3/26]|-2|
|faithful|-1 [4/5/21]|-2 [4/6/20]|+2 [6/4/20]|+1 [6/5/19]|-1|
|level_ok|-1 [3/4/23]|+1 [5/4/21]|+0 [3/3/24]|+2 [5/3/22]|+2|
|natural_role|+1 [5/4/21]|+4 [5/1/24]|+0 [3/3/24]|+3 [4/1/25]|+3|
|placeholder_exact|-10 [10/0/20]|-7 [7/0/23]|-3 [5/2/23]|+0 [0/0/30]|+3|
|generic_placeholder|-5 [6/1/23]|-4 [4/0/26]|-3 [5/2/23]|-2 [3/1/26]|+1|
|l1_detail_leak|+3 [1/4/25]|+3 [0/3/27]|+2 [2/4/24]|+2 [1/3/26]|+0|
|l2_repair_leak|+2 [1/3/26]|+1 [1/2/27]|+2 [1/3/26]|+1 [0/1/29]|-1|
|l3_actionable|+1 [2/1/27]|+0 [3/3/24]|-1 [1/2/27]|-2 [0/2/28]|-1|
|feedback_pass|+0 [0/0/30]|+0 [0/0/30]|+0 [0/0/30]|+0 [0/0/30]|+0|
|joint_gold|+0 [0/0/30]|+0 [0/0/30]|+0 [0/0/30]|+0 [0/0/30]|+0|
|joint_source|+0 [0/0/30]|+0 [0/0/30]|+0 [0/0/30]|+0 [0/0/30]|+0|
|inherited_false_claims|+11 [5/11/14]|+1 [7/8/15]|+7 [3/7/20]|-3 [9/6/15]|-10|
|new_false_claims|+0 [5/5/20]|+7 [4/7/19]|-2 [7/6/17]|+5 [5/8/17]|+7|
|new_diagnoses|+1 [5/5/20]|+4 [4/6/20]|-2 [6/5/19]|+1 [5/6/19]|+3|

### Bằng chứng theo source và từng ID

`casebook.private.json` trong ZIP giữ đề/code gốc, cả4 output, inventory và quotes/reason của cả hai reviewer cho đủ30 IDs. `per-ID-table.private.md` có Level/family/hash, gold, taxonomy/status từng arm, finding sai/unsupported/bỏ, feedback/Level/voice/placeholder, inherited/new và dispute. `example-selection.private.json` chọn ID đầu theo thứ tự từ điển cho mỗi contrast×metric×hướng improved/worsened/unchanged; không chọn riêng ví dụ đẹp. Phần diễn giải ví dụ cụ thể tiếp ở ghi chú riêng tư đi kèm. Không đưa source/gold/feedback chi tiết lên git.

## Taxonomy từng nhóm (gold, zero_division=0)


|Arm|Label|Support|TP|FP|FN|Precision|Recall|F1|
|---|---|---:|---:|---:|---:|---:|---:|---:|
|A|Lỗi biên dịch|5|2|4|3|0.3333|0.4000|0.3636|
|A|Lỗi nhập/xuất|3|3|0|0|1.0000|1.0000|1.0000|
|A|Lỗi logic|7|4|16|3|0.2000|0.5714|0.2963|
|A|Lỗi vòng lặp|10|8|2|2|0.8000|0.8000|0.8000|
|A|Lỗi mảng/chuỗi|8|2|9|6|0.1818|0.2500|0.2105|
|A|Lỗi hàm|3|0|0|3|0.0000|0.0000|0.0000|
|A|Lỗi edge case|6|0|0|6|0.0000|0.0000|0.0000|
|A|Lỗi thuật toán|2|0|0|2|0.0000|0.0000|0.0000|
|A|Lỗi hard-code|3|1|1|2|0.5000|0.3333|0.4000|
|A|Lỗi style|6|0|0|6|0.0000|0.0000|0.0000|
|B|Lỗi biên dịch|5|0|0|5|0.0000|0.0000|0.0000|
|B|Lỗi nhập/xuất|3|0|4|3|0.0000|0.0000|0.0000|
|B|Lỗi logic|7|2|9|5|0.1818|0.2857|0.2222|
|B|Lỗi vòng lặp|10|9|3|1|0.7500|0.9000|0.8182|
|B|Lỗi mảng/chuỗi|8|6|8|2|0.4286|0.7500|0.5455|
|B|Lỗi hàm|3|0|1|3|0.0000|0.0000|0.0000|
|B|Lỗi edge case|6|0|0|6|0.0000|0.0000|0.0000|
|B|Lỗi thuật toán|2|0|0|2|0.0000|0.0000|0.0000|
|B|Lỗi hard-code|3|0|0|3|0.0000|0.0000|0.0000|
|B|Lỗi style|6|1|2|5|0.3333|0.1667|0.2222|
|C|Lỗi biên dịch|5|3|3|2|0.5000|0.6000|0.5455|
|C|Lỗi nhập/xuất|3|0|1|3|0.0000|0.0000|0.0000|
|C|Lỗi logic|7|3|15|4|0.1667|0.4286|0.2400|
|C|Lỗi vòng lặp|10|9|0|1|1.0000|0.9000|0.9474|
|C|Lỗi mảng/chuỗi|8|3|14|5|0.1765|0.3750|0.2400|
|C|Lỗi hàm|3|0|1|3|0.0000|0.0000|0.0000|
|C|Lỗi edge case|6|0|0|6|0.0000|0.0000|0.0000|
|C|Lỗi thuật toán|2|0|0|2|0.0000|0.0000|0.0000|
|C|Lỗi hard-code|3|0|0|3|0.0000|0.0000|0.0000|
|C|Lỗi style|6|0|4|6|0.0000|0.0000|0.0000|
|D|Lỗi biên dịch|5|2|0|3|1.0000|0.4000|0.5714|
|D|Lỗi nhập/xuất|3|0|5|3|0.0000|0.0000|0.0000|
|D|Lỗi logic|7|1|6|6|0.1429|0.1429|0.1429|
|D|Lỗi vòng lặp|10|10|1|0|0.9091|1.0000|0.9524|
|D|Lỗi mảng/chuỗi|8|8|11|0|0.4211|1.0000|0.5926|
|D|Lỗi hàm|3|0|0|3|0.0000|0.0000|0.0000|
|D|Lỗi edge case|6|0|0|6|0.0000|0.0000|0.0000|
|D|Lỗi thuật toán|2|0|0|2|0.0000|0.0000|0.0000|
|D|Lỗi hard-code|3|1|1|2|0.5000|0.3333|0.4000|
|D|Lỗi style|6|1|4|5|0.2000|0.1667|0.1818|

## Verification và bàn giao

171 tests liên quan pass (test_task3_language_precision*.py, test_task3_two_pass*.py, test_task3_precision.py). Không tuyên bố full pytest xanh. Đã tái hiện riêng test_task3_eval_v2.py::test_v2_plan_preserves_v1_and_does_not_read_prediction_or_public_inputs trên original checkout HEAD35c2915:1 failed tại dòng140. Chỉ1 baseline hash lệch: root predictions.json expected9ba7411c… nhưng actualc30c5c13… đã có trước thí nghiệm. Log và hash diff giữ riêng; không sửa baseline/predictions. Không chạy full Task1/2; historical run còn ghi collection thiếu sklearn ởTask1. Fixture chỉ chứng minh hợp đồng; review dựa output Qwen thật và source.

Independent code review trước freeze tìm2 lỗi bookkeeping runtime: peak mỗi arm lẫn arm trước và resume ghi đè số đo. Đã tái hiện RED→GREEN, reset peak per arm, giữ load/group peaks và snapshots append theo invocation. Final code review phần report tìm3 validation gaps (false/new claims vẫn có thể pass, bỏ đánh giá L3, thiếu coverage dispute), đã RED→GREEN; minor receipt ZIP và repeat scoring cũng xử lý. Không đổi prompt/parser/backend lịch sử để làm arm tốt hơn.

Actual-call audit xác nhận238 messages đúng frozen task/prompt, stage1 VI(A)=VI(C), EN(B)=EN(D) trên đủ30,118 stage2 đúng finding/taxonomy/Level;238 EOS,118 feedback giữ nguyên sau parser cũ.181 artifact run tham chiếu hash nguyên vẹn; shared inference/parser/findings-v1/config cũ không đổi so với35c2915. Original checkout chỉ còn prompt người dùng untracked.

Inference freeze143b78b; code/report commits và final hash được ghi trong git và handoff receipt. ZIP riêng tư chứa toàn bộ raw/rendered/findings/journal/runtime/config/manifest/source/gold/review/per-ID, không chỉ ca lỗi. Chỉ code/config/tests/plan/báo cáo aggregate lên branch thí nghiệm; không push/PR/upload submission/public inference hoặc đổi default/R15.

## Diễn giải ví dụ có nguồn (chi tiết riêng tư)

- Hashbefbbc3e, L3: A/C tìm đúng vòng lặp không tiến và nêu hướng tăng biến; B/D vẫn dự đoán cùng nhãn Vòng lặp nhưng đổi sai điều kiện. Taxonomy exact có thể che chẩn đoán/hướng sửa sai. Đây là ví dụ đi ngược lợi ích EN ở cả precision.
- Hash3f5d48d3, requestedL2: C thêm thao tác kiểm tra n; D mô tả cận5 có căn cứ và không hướng sửa. A/B cũng có chẩn đoánL2 chấp nhận được. Đây là EN ởBF16 cải thiện renderer trên một bài, đồng thời vẫn có Loop/Hard-code và allocation/loaded-region dispute.
- Hash9afc0902, L3: D bỏ claim sai về đưa biến tích lũy ra ngoài routine mà B có; sửa tên file đúng bài hiện tại nhưng generality của filename và capacity vẫn còn điều kiện. Factual tăng ở ví dụ này nhưng không thành joint win.
- Hash954ee5b4, L1: D bịa bỏ phần tử đầu và yêu cầu khởi tạo đã có; B chỉ cảnh báo vòng lặp, factual hơn nhưng vẫn leak vị tríL1. BF16 ởEN không cải thiện đồng đều.
- Hash118a9290, L3: cả bốn bỏ cùng compile blocker; A unresolved được giữ, B/C/D complete nhưng thêm claim sai/hướng sửa sai. C còn nói đọc file thành công dù không có evidence thực thi. Đây là failure không đổi ở lỗi chính, không lọc khỏi bảng.
- Hash0e4fa413, requestedL1: B lặp chính câu placeholder bỏ dấu chấm; chỉ số literal-with-period bằng0 không có nghĩa hết filler. Hash46c7d53d còn minh họa feedback dài hơn sau khi bỏ placeholder nhưng sai nguyên nhân/hướng sửa.

Source quotes nguyên văn, cả4 findings/feedback, lý do từng reviewer và các ca còn lại ở source-examples.private.md/casebook.private.json trong ZIP. Không chép source/gold/review chi tiết lên git.

## Trả lời năm câu hỏi

1. **EN có cải thiện không?** Có giảm placeholder theo review10→5 ởNF4 và7→3 ởBF16; câu nguyên văn có dấu chấm10→0 và7→0 chỉ là một thống kê con. Số finding false/unsupported giảm34/15→27/9 ởNF4 và30/12→24/9 ởBF16, nhưng tổng findings cũng giảm82→68 và74→65. Finding correct bảo thủ giảm21→11 và20→8, disputed tăng12→21 và12→24; recall inventory22/33→15/33 và20/33→17/33. Không gọi mọi disputed là sai chắc chắn. Feedback factual giảm10→6 và10→4. L1 leak tăng2→5 và4→7; L2 leak tăng3→5 và5→6. Level tổng thể5→4 và5→6; L3 actionable4→5 và3→3. Giọng tốt hơn nhưng chưa đủ; EN không giảm vi phạmL1/L2 trên tập này.
2. **BF16 tốt hơn NF4 khi giữ ngôn ngữ không?** VI: micro-F1 giảm0.381→0.330, exact4→1, factual10→10, L1/L2 leak cùng tăng2; EN: micro-F1 tăng0.367→0.442, exact2→2, recall inventory15→17, nhưng factual6→4 và L3 actionable5→3. Complete tăng29→30 cho cả ngôn ngữ. Không có cải thiện chất lượng đồng đều và joint không tăng.
3. **Tương tác language×precision?** Có dấu hiệu mô tả ở gold micro-F1: EN delta−0.0136 tạiNF4 và+0.1120 tạiBF16; interaction+0.1256. Với factual, EN delta−4 và−6 ID (interaction−2), với joint interaction0. Ví dụ rendererL2 tốt lên khiEN/BF16, ví dụ first-element tệ đi khi đổi precision ởEN và missing-increment tệ đi ởEN cả hai precision cho thấy chỉ số không cùng hướng. Không suy significance/generalization từ30 ID/27 code hash đã seen và một seed/lịch chạy.
4. **Chọn cấu hình nào tiếp?** Chưa có arm đủ tốt. D cao nhất gold micro-F1 nhưng không dẫn về finding/feedback đúng; joint-gold0/30 ởcả4, vẫn0 khi bỏ dispute gate; không tăng thật. Joint-source scoring chính cũng0. Không đổi production/R15 hoặc mở public mới. D chỉ đáng giữ như đối chứng taxonomy trong một nghiên cứu mới nếu được yêu cầu, chưa là candidate chuyển default.
5. **Nghiêng về prompt, precision hay giới hạn tác vụ?** Đổi ngôn ngữ có tác động rõ lên hình thức/placeholder và prose, nhưng không cứu factuality/Level; precision có hiệu ứng phụ thuộc ngôn ngữ và không giải quyết các lỗi source lặp lại. Chưa phân biệt được giới hạn prompt nền, grounding/tác vụ và năng lực model. Không đủ bằng chứng quy mọi lỗi choNF4 hayQwen. Tập development đã seen, clone, nguồn tĩnh/compiler unavailable, chỉ3 gold-clean ởL1, không có empirical findings=[], khôngL4, nhiều domain/label dispute và reviewer chưa human-validated giới hạn kết luận.

## Chi phí từng stage và placeholder variants theo Level

|Arm|Stage|Calls|Input tokens|Output tokens|Latency s|
|---|---|---:|---:|---:|---:|
|A|taxonomy|30|28030|7674|90.470|
|A|feedback|29|34390|2032|26.557|
|B|taxonomy|30|26530|6956|82.250|
|B|feedback|29|31968|2532|31.993|
|C|taxonomy|30|28030|6732|85.714|
|C|feedback|30|34710|1937|26.450|
|D|taxonomy|30|26530|5995|76.527|
|D|feedback|30|32863|2464|32.864|

|Arm|Generic placeholder L1/10|L2/10|L3/10|
|---|---:|---:|---:|
|A|8|0|2|
|B|5|0|0|
|C|6|0|1|
|D|3|0|0|

Tổng main run:238 calls/reservations,243.051 input tokens,36.322 output tokens,452.823s generation; không cộng hai lượt reviewer agent thành Qwen inference.

Finding prose English theo primary: A1/29 valid stage1 (3,4%), B26/29 (89,7%), C0/30, D23/30 (76,7%). “mixed” ởA1/29 vàD2/30 có Chinese; D có5/30 findings tiếng Việt dù chỉ dẫnEN. Ngôn ngữ prose là quan sát output của pipeline, không là cơ chế tư duy.
