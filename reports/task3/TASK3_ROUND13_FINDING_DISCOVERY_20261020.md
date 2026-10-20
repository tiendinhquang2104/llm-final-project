# Task 3 Round 13 — finding discovery không cần gold, 20/10/2026

Round 13 xây được luồng thí nghiệm không dùng gold: source/statement/compiler → candidate → kiểm chứng quan hệ → finding/taxonomy → projection → completion policy. **Chưa phải phương pháp đầy đủ cho Task 3**. Trên 521 record train thực/synthetic, phương pháp chỉ tìm được 101 finding compiler trên 55 record; chưa có finding semantic ngoài biên dịch được chấp nhận. Tất cả 521 record còn thiếu bằng chứng về độ phủ toàn bài nên strict completion là **0/521**, không đổi unknown thành `[]`.

Trên 15 bài nhân tạo kiểm tra riêng, 6 finding được nhận có bằng chứng sau review; 7 finding đúng theo annotation còn bị bỏ. Cùng renderer Level 2: oracle render được 12/15, predicted 5/15. Khoảng cách chủ yếu nằm ở extractor; repair và Level 4 cũng còn phạm vi rất hẹp. Không dùng acceptance/completion như thước đo factual correctness.

## 1. Phạm vi và provenance

- Tiếp tục cùng branch `feat/task3-quality-round5` từ `24f13ef`. Code/test/plan: **`eda255b`**. Official run `outputs/task3/discovery-round13/train-run-reviewed/` chạy sau commit này, working tree sạch; `frozen-before-check.json` ghi HEAD và hash implementation/fixture/entry point trước khi đọc tập check.
- Chỉ đọc `data/processed/task3/real-train.jsonl` (**26 record**) và `synthetic-train.jsonl` (**495 record**), cộng 7 bài nhân tạo phát triển và 15 bài nhân tạo kiểm tra. Không gọi prepare lại, không đọc/chạy public, real-val hoặc heldout. Không sử dụng lịch sử public để chọn phương pháp/few-shot; không gọi model.
- Các count train là dữ liệu hiện tại; không tái dùng số 505 synthetic trong tài liệu lịch sử. Gold taxonomy chỉ được evaluator đọc **sau** inference để so nhãn. Teacher feedback và synthetic execution report không được dùng cả để tạo finding lẫn oracle fixture.
- `DiscoveryInput` chỉ có code, statement, problem pid/prototype, compiler status/diagnostic. Không truyền toàn bộ `Task3Record`, labels, teacher text, oracle file, provenance hoặc test report vào extractor. Test mutation gold/teacher chứng minh input và kết quả không đổi.
- Renderer Round 12, loader oracle và default pipeline/adequacy không sửa. Không đọc `findings-approved-C2.json` trong Round 13. Projection Round 13 dùng lại `_project` của Round 12 cho Level 1–3, thêm biên kiểm chứng finding và Level 4 riêng. Đây là nhánh code thí nghiệm trên branch hiện tại, không đổi default.
- Inventory metadata ở `outputs/task2`, `checkpoints`, `models` không thấy candidate checkpoint/prediction file cho Task 2. Kiểm tra bổ sung tên artifacts dưới outputs không thấy baseline Task 2 train. Không giả định Qwen base cache hoặc diagnosis A là checkpoint Task 2; **không chạy baseline Task 2** và không tải model.
- Raw source/statement/compiler/findings/feedback, rejected candidates, oracle annotations đã serialize và review chi tiết chỉ ở ignored `outputs/task3/discovery-round13/`. Code fixture tự viết được commit; không stage mã sinh viên. Không sửa dataset/gold, không push.

Run chính thức thực hiện **411 syntax-only compiler calls**, dedup theo exact source hash, chuẩn C++11, timeout mỗi call 3 giây. Không chạy executable sinh viên, không tạo student binary, không tuyên bố đã kiểm tra runtime/đầu ra bài thực. Suite vẫn chạy executable fixture nhân tạo trong sandbox hiện có.

## 2. Hợp đồng finding và biên kiểm chứng

| Trường | Ý nghĩa và giới hạn |
|---|---|
| `finding_id`, `problem_id` | ID từ rule/span/source; PID ánh xạ prototype khi xác định được. `null` là toàn bài/chưa định vị được câu, không bịa PID |
| `taxonomy_group` | Một trong đúng 10 nhóm chính thức; không thêm nhãn mới |
| `source_span` | Offset ký tự, dòng đầu/cuối và exact quote; quote chỉ chứng minh đoạn mã tồn tại |
| `observed_fact` | Điều trực tiếp quan sát: compiler báo error, literal xuất hiện, điều kiện/thân vòng lặp, giá trị return |
| `cause` | Kết luận có phạm vi từ diagnostic hoặc quan hệ source–statement; không biến quote thành chứng minh nguyên nhân |
| `evidence` | Rule, diagnostic severity hoặc statement quote, parameter/function hay proof giới hạn; giữ riêng với fact/cause |
| `confidence` | `direct_compiler` hoặc `bounded_relation`; **không phải xác suất đã calibrate** |
| `status` | Finding được nhận là `supported_error`; candidate không đủ căn cứ thành `hypothesis` kèm lý do loại; result không có finding/certificate là `unknown` |
| `repair_action` | Target/reference, span cần thay, replacement và text; thiếu quan hệ được xác minh thì Level 3 không hoàn tất |

`validate_finding` không chỉ kiểm tra quote: nó tái lập finding từ input và yêu cầu toàn bộ fact/cause/group/span/evidence/action khớp. Thay nguyên nhân, nhãn hay hướng sửa dù quote vẫn đúng sẽ bị từ chối. Đây là kiểm chứng trong họ rule nhỏ, không phải semantic entailment tổng quát hay AST/type checker.

Compiler thành công không tạo clean. Khi có supported findings nhưng chưa chứng minh hết bài, result vẫn `coverage_complete=false`; `taxonomy` lúc ấy là **nhãn đã có bằng chứng, có thể chưa đầy đủ**. Không có finding thì taxonomy là `null`, trừ certificate đặc tả hoàn toàn giới hạn ở mục 6. Các hypotheses không tự trở thành label hay `[]`.

PID compiler chưa xác định được ở **2/9 finding real-train và 41/92 synthetic-train**; code không suy ngược PID từ gold group. Compiler finding hiện chủ yếu chứng minh rejection ở dòng nguồn, **chưa suy được root cause sâu hay hướng sửa**. Do đó factual support của diagnostic không đồng nghĩa chất lượng chẩn đoán cao.

## 3. Candidate → evidence → mapping

Bốn họ được hỗ trợ, không có rule theo student ID hoặc nội dung sáu real-val:

1. **Compiler error → Lỗi biên dịch.** Chỉ nhận fresh diagnostic `error`/`fatal error` của stdin, status compile_error và dòng nguồn hợp lệ. Warning, header bên ngoài, vị trí vượt nguồn và `#line` remapping không đủ chứng minh source span. Warning không được suy thành lỗi cú pháp hay lỗi thuật toán.
2. **Literal/parameter → Lỗi hard-code.** Đặc tả phải trùng một contract đường dẫn giới hạn; hàm phẳng có string parameter tương ứng; body là constructor hoặc `.open` trên receiver `std::ifstream` đã chứng minh trong phạm vi này. Cần compiler thành công và `<fstream>`; namespace/type/alias contexts bị từ chối. `.open` của object bất kỳ, raw string chứa code giả, statement phủ định hoặc mâu thuẫn chỉ là rejected candidate. Không suy “mọi literal file đều sai” và không map máy móc sang I/O.
3. **Invariant loop → Lỗi vòng lặp.** Chỉ nhận dạng hàm value-parameter và thân tăng một biến unsigned khác, không call/exit/alias. Đề phải yêu cầu kết thúc cho mọi/any giá trị integer của tham số đó; miền input chỉ bằng 0 không đủ. Cause cuối cùng là thiếu bảo đảm hành vi kết thúc khi điều kiện khác 0 và không có tiến triển quan sát được, **không khẳng định binary chắc chắn treo**.
4. **Return constant → Lỗi logic.** Chỉ cho đặc tả toàn chương trình giới hạn “Program exit status must be N.”, main chỉ trả literal decimal canonical, giá trị 0..125, compiler thành công. Sai khác được chứng minh trực tiếp; không gọi đây là bộ giải bài logic tổng quát.

Mỗi candidate bị loại có rule/quote/reason/status. Candidate chưa được sinh ra thuộc họ chưa hỗ trợ không được giả vờ là đã xác minh rồi loại; missed finding được tính từ reference evaluation riêng.

Review tìm ra các lỗi có test đỏ/xanh: octal source bị hiểu như decimal; spec số có số 0 đầu gây replacement octal; raw string bị nhận như call; lời nhắc trong đề không entail yêu cầu; receiver `.open` không phải file; nested namespace giả `std`; thiếu miền input hợp lệ; `#line` làm lệch source span. Pilot còn nói quá về infinite loop, **cả oracle fixture cũng có lỗi ấy**. Pilot giữ nguyên, annotation nhân tạo cuối đã sửa qualifier. Không sửa gold dataset.

C++11 cho phép implementation dựa trên giả định thread cuối cùng kết thúc hoặc tạo tiến triển quan sát được, nên không được suy binary chắc chắn lặp vô hạn chỉ từ local increment. Cause cuối giữ giới hạn này. [C++11 draft N3337, intro.multithread §24](https://timsong-cpp.github.io/cppwp/n3337/intro.multithread#24).

## 4. Thiết kế tập kiểm tra và metric

Bảy bài development và 15 bài independent train check có disjoint exam/problem family, group, canonical code hash và identifier-renamed code hash; kiểm tra tự động trước experiment. Không chỉ đổi tên biến rồi gọi là independent. Tập check có đủ 10 nhóm, clean, distractor warning, nhiều lỗi và được chiếu ở cả Level 1–4. Đây là tập nhân tạo do assistant tự viết, nhỏ và không blind với người viết pipeline; không phải heldout hoặc ước lượng tổng quát. Pilot/check được đọc và tái chạy trong review; không gọi kết quả cuối là một lần test mù chưa từng xem. Không thêm họ extractor để khớp các ca bị bỏ sau khi xem check.

Ba phép đo tách biệt:

- **Group/span agreement:** `score_findings` ghép đúng group và span giao nhau. Hàm ghi rõ `taxonomy_and_span_agreement_not_semantic_correctness`. Test cố ý cho claim sai nhưng cùng group/span vẫn khớp, để không biến metric này thành factual verifier.
- **Factual support:** reviewer assistant độc lập đọc source, statement, diagnostics và từng claim ở các bài nhân tạo được nhận. Pilot: 7/11 fully supported, 4 loop cause quá mạnh. Cuối: development **5/5**, check **6/6** accepted claims được hỗ trợ trong phạm vi; false accepted claim quan sát được **0/11**. Đây không phải human verification hay chứng minh tỷ lệ lỗi bằng 0 trên bài mới.
- **Taxonomy precision/recall:** trên train thực/synthetic chỉ so nhãn đã có bằng chứng với annotation để đếm TP/FP/FN. Không lấy cùng label làm chứng minh cause đúng. Không có source-level oracle độc lập đầy đủ cho 521 record nên factual P/R và số finding thực đúng bị bỏ ở đó là **unassessed**.

### Per-group trên independent artificial train check

TP/FP/FN ở đây là group/span agreement; factual support của 6 accepted claim được review riêng như trên. Dấu “—” nghĩa không có prediction để tính precision.

| Nhóm chính thức | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Lỗi biên dịch | 2 | 0 | 0 | 100% | 100% |
| Lỗi nhập/xuất | 0 | 0 | 1 | — | 0% |
| Lỗi logic | 1 | 0 | 0 | 100% | 100% |
| Lỗi vòng lặp | 2 | 0 | 0 | 100% | 100% |
| Lỗi mảng/chuỗi | 0 | 0 | 1 | — | 0% |
| Lỗi hàm | 0 | 0 | 1 | — | 0% |
| Lỗi edge case | 0 | 0 | 2 | — | 0% |
| Lỗi thuật toán | 0 | 0 | 1 | — | 0% |
| Lỗi hard-code | 1 | 0 | 0 | 100% | 100% |
| Lỗi style | 0 | 0 | 1 | — | 0% |

Tổng: **6/13 finding được tìm, 7 bị bỏ**, group/span precision 6/6 và recall 6/13 (46,2%). Mapping–finding mismatch quan sát trong 6 predicted finding là 0 sau review. Không biến các nhóm không hỗ trợ thành clean. Unknown không có supported finding là **9/15 (60%)**; coverage chưa đầy đủ **13/15 (86,7%)**. Hai record có certificate toàn bộ chỉ thuộc họ return-constant.

Development: 5/5 finding được tìm, 0 FP/FN theo annotation; 2/7 unknown không có finding, 5/7 coverage incomplete. Kết quả development chỉ kiểm tra implementation.

### Per-group taxonomy trên train thực/synthetic

Mỗi ô là TP/FP/FN, không phải số source-level findings. Nhãn không dự đoán có precision không xác định; recall là 0 nếu có support. Không tính accuracy bằng cách âm thầm export unknown thành `[]`.

| Nhóm | real-train (26) | synthetic-train (495) | Precision / recall |
|---|---:|---:|---|
| Lỗi biên dịch | 4/0/0 | 51/0/0 | 100% / 100% ở cả hai |
| Lỗi nhập/xuất | 0/0/2 | 0/0/55 | — / 0% |
| Lỗi logic | 0/0/11 | 0/0/83 | — / 0% |
| Lỗi vòng lặp | 0/0/4 | 0/0/69 | — / 0% |
| Lỗi mảng/chuỗi | 0/0/1 | 0/0/70 | — / 0% |
| Lỗi hàm | 0/0/5 | 0/0/89 | — / 0% |
| Lỗi edge case | 0/0/0 | 0/0/127 | — / — real; — / 0% synth |
| Lỗi thuật toán | 0/0/4 | 0/0/47 | — / 0% |
| Lỗi hard-code | 0/0/2 | 0/0/57 | — / 0% |
| Lỗi style | 0/0/2 | 0/0/64 | — / 0% |

Có **9 compiler findings/4 real record**, **92/51 synthetic record**. Nhãn có bằng chứng không nằm trong annotation: 0/101 finding; đây là agreement với gold, **không phải factual FA=0** hay taxonomy discovery đã đầy đủ. Generic diagnostic chưa giải thích root cause; không đếm thành 101 chẩn đoán semantic đã xác minh độc lập.

Unknown không có finding: real **22/26 (84,6%)**, synthetic **444/495 (89,7%)**. Coverage toàn bài chưa xác minh: **26/26 và 495/495**. Candidate bị loại: 4 real, 47 synthetic; lý do/quote nằm trong raw outputs. Thiếu căn cứ không bị map sang nhãn sạch.

## 5. Oracle finding → cùng renderer so với predicted finding

Oracle là annotation nhân tạo tự viết độc lập với extractor, từ source/statement/defect mechanism; không sinh oracle bằng cách gọi extractor, không lấy teacher feedback. `project` là biên nhận contract đã có authority; evaluator đưa oracle qua biên đó. Đường inference `render` bắt buộc validate/rederive trước cùng projection; `complete` chỉ nhận input, không nhận oracle. Không có cờ fallback đưa oracle vào inference.

### Cùng 15 bài check, cùng Level, không model

| Level | Oracle render được | Predicted render được | Ý nghĩa |
|---|---:|---:|---|
| 1 | 15/15 | 15/15 | Câu trung tính/nhắc rà soát; không chứng minh đã chẩn đoán hay clean |
| 2 | 12/15 | 5/15 | Thiếu 7 finding ở extractor; ba bài không finding không tự nhận clean |
| 3 | 2/15 | 2/15 | Chỉ literal/parameter và return-constant có action được chứng minh; các finding khác thiếu repair |
| 4 | 2/15 | 2/15 | Chỉ certificate return-constant; còn lại abstain kể cả oracle đúng |

Phần finding đã được predicted tìm và review đúng không bị đổi fact/cause khi project; thêm claim bị contract chặn. Không có bằng chứng renderer làm sai 6 accepted findings ở đây. Tuy nhiên bằng chứng này có điều kiện và nhỏ. Level 3/4 thấp cả ở oracle cho thấy **thiếu repair/solution certificate và độ phủ Level**, không thể quy mọi thất bại cho extractor.

Development tương ứng L1 7/7 cả hai; L2 4/7; L3 2/7; L4 2/7. Không gộp oracle và predicted vào một điểm.

Paired source-level oracle đầy đủ **chưa có cho 521 bài train thực/synthetic**; không thay thế nó bằng gold taxonomy hoặc feedback giảng viên. Paired experiment ở trên chỉ có ý nghĩa trên phạm vi train-only nhân tạo được annotate. Đây là giới hạn cần giải quyết trước khi đưa ra kết luận oracle-gap cho toàn dataset.

### Khả năng render ở Level yêu cầu trên dataset train

| Level | real-train | synthetic-train |
|---|---:|---:|
| 1 | 2/2 | 123/123 |
| 2 | 3/15 | 22/207 |
| 3 | 0/9 | 0/143 |
| 4 | không có | 0/22 |

Các câu L1 trung tính không được đếm là finding hữu ích. Render được cũng chưa đủ để export taxonomy đầy đủ.

## 6. Completion policy và Level 4

`abstain` là policy mặc định của nhánh R13: chỉ tạo object submission khi coverage toàn đặc tả đã chứng minh và Level render thành công. `supported_partial` chỉ cho phép xem nhãn có bằng chứng và feedback tương ứng, luôn giữ `submission=null` nếu coverage incomplete. Không thay B làm fallback, không chuyển hypothesis/unknown thành `[]`, không gọi partial list là taxonomy hoàn chỉnh.

| Phạm vi / policy | Feedback + nhãn có thể xem | Exact label-set trong phần được chọn | Submission exportable |
|---|---:|---:|---:|
| real-train / abstain | 0/26 | không xác định | 0/26 |
| real-train / supported_partial | 3/26 | **1/3** | 0/26 |
| synthetic-train / abstain | 0/495 | không xác định | 0/495 |
| synthetic-train / supported_partial | 32/495 | **32/32** | 0/495 |

32/32 trên synthetic chỉ là label agreement trong phần đã chọn, gồm các ca Level 1 không technical feedback; không chứng minh finding completeness hoặc semantic feedback quality. Chênh lệch real 1/3 chỉ ra partial compiler labels bỏ nhóm lỗi khác trong cùng bài. Đây là coverage–accuracy tradeoff được quan sát, không lấy completion cưỡng ép để làm đẹp số.

Trên 15 bài check, strict exportable theo L1/L2/L3/L4 lần lượt **2/1/1/2** (13,3%/6,7%/6,7%/13,3%), label-set đúng trong tất cả phần được xuất. Partial có feedback lần lượt **6/5/2/2**, exportable vẫn 2/1/1/2. Không tuyên bố tập này đủ đa dạng để chọn threshold thực tế.

**Level 4 đã có chiến lược và fixture dương/âm**, nhưng chưa đầy đủ: chỉ phát sinh chương trình đầy đủ khi cả source lẫn toàn statement nằm trong contract return-constant 0..125. Chứng nhận dựa vào việc cả chương trình khớp grammar và phép tính giá trị, không phải compiler pass. Số thập phân trong prose được canonicalize trước khi thành literal C++; source octal bị từ chối certificate. Test compile lời giải và patch literal dùng C++11, không chạy binary.

Một patch file I/O biên dịch được vẫn bị chặn Level 4 vì không chứng minh nó giải toàn bài. Hai certificate ở mỗi bộ artificial gồm một bài sai được sửa và một bài đã đáp ứng contract; trường hợp sau mới có thể xuất `[]` dựa trên chứng minh bounded specification. Các Level khác chưa hỗ trợ prose clean cho mọi certificate; không suy ra đã hoàn thiện hệ thống chỉ từ đường Level 4 nhỏ này.

Các ca không thể xuất được ghi bằng reason: không có supported finding/certificate; finding có nhưng thiếu verified repair; không có complete-solution certificate; hoặc coverage chưa đầy đủ dù render được. Dataset thực còn có **22 ca Level 4 đều bị chặn**. Không tạo full submission train để ngầm che các ca đó.

## 7. Kiểm tra, artifacts và tái hiện

Full Task 3 suite: **434 passed, 4 skipped, 6,61 giây**, gồm toàn bộ `test_task3_cpp_checks.py`; tăng 36 test so với Round 12. Không gọi đây là full repository pass. Có red/green logs cho contract, Level/completion và các issue review. Reviewer cuối không còn Important issue trong phạm vi hẹp đã review; không chứng nhận C++ parser tổng quát.

Artifacts chính:

- `outputs/task3/discovery-round13/train-run-reviewed/frozen-before-check.json`: commit/hash trước run.
- `summary.json`, `completion-analysis.json`: metrics tách riêng và SHA-256 hai file train.
- `development.raw.json`, `independent_train_check.raw.json`: oracle/predicted source/claims/render/policies trên cùng bài và từng Level.
- `real-train.raw.json`, `synthetic-train.raw.json`: source, statement, compiler, hypothesis/rejection reason, finding, feedback, policy và gold taxonomy **evaluation only**; không chứa teacher feedback.
- `artificial-semantic-adjudication.json`: provenance review độc lập, pilot overclaims và verdict cuối; không human-verified.
- `tests-task3-final-reviewed-2.log` và các `tests-*-red/green.log`: evidence tests. `train-run-1`/`train-run-final` giữ lại như pilot; **chỉ `train-run-reviewed` là official committed-code run**.

```bash
cd /workspace/llm-final-project
.venv-task3/bin/python -m pytest -q tests/test_task3_*.py
.venv-task3/bin/python scripts/task3_discover_train.py \
  --data-dir data/processed/task3 \
  --output-dir outputs/task3/discovery-round13/reproduce-new
```

Runner chỉ có hai train partitions hard-coded, kiểm tra record split/source, từ chối output đã tồn tại hoặc ngoài outputs. Không nhận đường dẫn oracle, taxonomy hay teacher làm inference parameter. Tái hiện cần giữ dữ liệu train hiện tại; thư mục output phải là tên mới. `completion-analysis.json` là phép tổng hợp hậu kiểm từ policies và expected labels trong raw, không một run inference khác.

## 8. Quyết định theo từng tầng

| Tầng | Đã đạt | Blocker còn lại |
|---|---|---|
| Extractor | API loại gold; severity và candidate rejection rõ; 6 accepted artificial check claims có evidence sau review | Chỉ compiler trên train thực; thiếu parsing/dataflow/statement entailment ngoài grammar nhỏ; 7/13 finding check bị bỏ |
| Taxonomy mapping | Đúng 10 nhóm; evidence→group tách khỏi annotation; không suy warning thành error | Chỉ 4 họ rule; sáu nhóm chưa hỗ trợ; nhãn compiler không đại diện toàn bài; PID một phần chưa biết |
| Renderer | Cùng projection oracle/predicted; giữ fact/cause, chặn claim thêm bằng rederivation | Hiệu quả có điều kiện theo finding; diagnostic generic còn ít giá trị giải thích; chưa có paired oracle đầy đủ cho train thực |
| Level | L1–3 disclosure; repair có target/reference; Level 4 bounded certificate và fixture dương/âm | L3 thiếu repair cho phần lớn finding; 0/22 Level 4 dataset; chưa phải Task 3 đầy đủ |
| Completion | Unknown không thành clean/[]; strict abstain; partial có nhãn rõ là chưa export được | Strict 0/521 actual train; cần chứng minh coverage và chính sách xử lý unknown hữu ích, không fallback B |
| Freeform / adequacy v4 | Không thay default; vẫn tách khỏi nhánh deterministic | Round 12 vẫn nhận 15/16 final feedback sai/mixed; v4 không phải factual verifier |

Chưa đóng băng toàn bộ luồng không dùng oracle để đánh giá cuối. Tiếp tục train-only vào extractor/statement–cause verification và annotation audit độc lập; không mở một vòng tìm prompt trên sáu real-val. Chỉ đánh giá heldout một lần sau khi extractor, mapping, rendering cả Level 4 và completion đã được đóng băng; Round 13 chưa đạt điều kiện đó.
