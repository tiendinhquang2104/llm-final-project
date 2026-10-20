# Task 3 Round 12 — renderer, adequacy và compiler sandbox, 20/10/2026

Renderer xác định có cấu trúc đã tạo được 6/6 bản ghi oracle offline; 5 finding được duyệt trên bốn ca có fact/cause/vị trí được giữ đúng, gồm S111 và quan hệ sửa bound của S212. Đây là **bảo đảm có điều kiện theo finding đầu vào**, không chứng minh hệ thống tự chẩn đoán đúng. Hai ca Level 1 không có finding được cung cấp chỉ nhận lời đáp trung tính, không được tính là đã tìm lỗi hoặc chứng minh bài đúng.

Checker action thử nghiệm giảm false rejection ở một số cách diễn đạt có quan hệ nguồn cụ thể và chặn lời khuyên khai báo chung. Nó vẫn không phát hiện nhiều claim bịa. A/B chưa đủ tin cậy để tạo submission; không đóng băng phương pháp end-to-end, không chạy public/heldout, không sửa gold, không push/nộp leaderboard. Không gọi thêm model, không tìm prompt trên sáu real-val.

## Phạm vi, commit và artifacts

- Branch `feat/task3-quality-round5`; bắt đầu ở `5abf2a63fdc615f730f835304089c90270824f22`, working tree sạch.
- Code/test/config Round 12: **`8cf15aaf6df9ed105f4c6c1721441346971aaac6`**. Official oracle rendering chạy đúng commit này, `git_worktree_dirty=false`. Manifest còn ghi hash code thực tế, cả entry point.
- Baseline C2: `outputs/task3/mechanism-round11/C2-approved-pair.*`, commit `e73dbc2eeac087df3488a8ea8beca0cefa3471f5`; dùng raw/final prefix có sẵn, không tái sinh.
- Cùng `findings-approved-C2.json`, SHA-256 **`f77321ba62c36764dbf00ea4f7158567fff931dedd8e1c87501b2ee93d6f7d57`**; nguồn xác nhận vẫn là **independent assistant review plus source/compiler evidence**, không human-verified.
- Manifest dữ liệu vẫn **`b311193f5c9fcf683019b1ae97c6e1017cfb4572cbcc1f3dfe2a3d9f3a753ee0`**. Approval loader kiểm tra source/statement hash và quote; không sửa gold hoặc annotation.
- Raw nguồn/prompt/attempt, finding và mọi output mới nằm trong ignored **`outputs/task3/renderer-round12/`**. Không đưa trích đoạn mã sinh viên vào Git. Bản pilot `oracle-renderer/` dùng working tree đang phát triển; chỉ dùng **`oracle-renderer-final/`** làm output chính thức.
- C2 cũ: Qwen/Qwen2.5-Coder-7B-Instruct revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`, NF4, greedy seed 42, feedback cap 512, Level/prompt/guard theo Round 11. Renderer mới không dùng model/tokenizer/GPU/decoding; không giả vờ đây là paired model run cùng precision. Không load checkpoint hay cache mới.

## 1. Raw C1/C2 S111/S212: bằng chứng, thứ tự, retry

Báo cáo nội bộ có nguyên văn finding, raw response, severity lines của compiler, hint và decision của **từng attempt**:

- `outputs/task3/renderer-round12/ROUND11_S111_S212_ATTEMPT_AUDIT.md`
- `outputs/task3/renderer-round12/round11-selected-attempts.exact.json`

JSON giữ exact message arrays và SHA; Markdown chỉ trích phần cần đọc. C1 không được supplied finding, chỉ gold groups/source/log. C2 S111 có finding đối số lời gọi sai ở P1; C2 S212 có finding tên chưa khai báo và hướng sửa liên kết bound với digit-count hiện có.

| Run / ID / attempt | Claim thêm hoặc bỏ so với căn cứ | Guard / adequacy / retry thực tế |
|---|---|---|
| C1 S111 / 1 | Bịa lỗi declaration/dấu phẩy của biến chỉ số tại dòng 51; bỏ nguyên nhân danh sách đối số sai. Có một claim so sánh chuỗi/số ở 53 đúng lõi compiler error; các claim conversion, khởi tạo con trỏ, đọc file đặt ở 53 không được hỗ trợ như đã nói | Guard pass; không có retry; accepted dù có claim sai/mixed |
| C2 S111 / 1 | Không render finding được duyệt ở 51; thay bằng các claim chính tả toán tử ở 51/53 và declaration đặt sai vị trí/cause | Guard pass; không retry; accepted dù không grounded vào finding |
| C1 S212 / 1 | Undeclared diagnosis đúng; giữ quan hệ khởi tạo bound từ digit-count hiện có. Cách nói chưa khởi tạo hoặc khai báo hơi lỏng | Disclosure guard pass; `level3_direction_candidate`; chưa có hint retry |
| C1 S212 / 2 | Cùng raw như lượt 1 | Cùng rejection; thêm system hint cần hướng sửa cụ thể |
| C1 S212 / 3 | Cùng raw như lượt 1 | Cùng rejection; hint và prompt giống lượt 2; dừng, không generic Level 3 fallback |
| C2 S212 / 1 | Giữ undeclared diagnosis nhưng bỏ quan hệ digit-count; chỉ khuyên khai báo biến | Guard pass; adequacy reject có căn cứ về thiếu action cụ thể |
| C2 S212 / 2 | Vẫn chỉ khuyên khai báo, không giữ quan hệ sửa được cấp | Reject; system hint như C1 |
| C2 S212 / 3 | Như lượt 2 | Reject; prompt giống lượt 2; dừng |

Chi tiết S111: warning `-Wmultichar` tại 53/64 đứng **trước** error tại 51 và error kiểu toán hạng tại 53 trong log được đưa vào prompt. Multi-character constant trong nguồn liên quan ký tự BC, không phải ký tự trừ. So sánh dùng toán tử được viết đúng nhưng hai kiểu không tương thích; không thể diễn giải warning thành chính tả toán tử sai. Nguồn thực sự còn có redeclaration ở vị trí khác, nên không gọi mọi claim declaration là bịa hoàn toàn: response C2 vẫn sai vị trí/cause và không nói finding được cấp. Log giữ tối đa 8.000 ký tự, không giả định mọi diagnostic về sau đều đã nằm trong prompt.

Một raw A resolved-feedback ở Round 11 còn gọi ký tự trừ là multi-character constant; đó là lỗi đọc warning khác, không được gán sang raw C một cách không có trace. **Không thể chứng minh thứ tự warning là nguyên nhân nhân quả của hallucination** chỉ từ quan sát này; không chạy ablation đổi thứ tự prompt/log.

Thứ tự C2: system → oracle finding message → submission JSON chứa source/log → yêu cầu Level ở cuối message submission. Finding không nằm cuối prompt. Retry bổ sung system hint nguyên văn trong audit nội bộ; không append raw assistant response cũ, không nhắc lại cụ thể quan hệ digit-count. Hai retry của mỗi C cùng prompt. Tách lỗi mất relation do generation C2 khỏi lỗi screen từ chối relation thật của C1.

## 2. Renderer có cấu trúc, không cần sinh tự do

`src/task3/renderer.py` tạo từng unit từ finding được duyệt: finding_id, problem_id, exact quote, code hash, vị trí ký tự/dòng, observed_fact, cause, compiler_support và repair_action. Source quote phải khớp nguyên văn tại đúng một vị trí; PID/official label hợp lệ. Compile finding phải có diagnostic **error** thật tại span, status compile_error; warning đơn độc không đủ. Đây là liên kết bằng chứng, không là proof ngữ nghĩa của mọi cause.

Mọi fact/cause đi vào feedback là trường được duyệt, không cho model paraphrase hoặc thêm claim. Validator kiểm tra unit và projection cuối; thêm claim, thay cause, đổi PID/dòng/action/reference hoặc thêm lời khen/CJK đều bị từ chối. Không chỉ đếm guard pass rồi gọi là factual accuracy.

- Level 1: không xuất vị trí, fact/cause, identifier hay repair. Không có supplied finding thì đáp trung tính; status `no_approved_finding_not_clean` được giữ trong audit.
- Level 2: nêu vị trí/fact/cause; không đưa quote code hoặc repair. Nếu imperative bị chèn vào cause, disclosure guard vẫn từ chối.
- Level 3: cần repair_action có quan hệ target/reference từ source và hướng được duyệt. Chỉ khuyên khai báo không đạt. Không đưa chương trình đầy đủ.
- Chỉ hỗ trợ Level 1–3; Level 4 fail-closed, không tự tạo lời giải từ finding.
- CJK trong prose fact/cause/repair bị chặn. CJK trong source literal vẫn có thể nằm trong private provenance nhưng không được copy ra feedback. Không nhầm chữ Trung trong source với lời model.

`repair_action` hiện hỗ trợ một họ nhỏ: cận for-loop liên kết với giá trị đã có trong source. Thứ tự gán và quan hệ phải có hướng; không tự suy ra một công thức khác, phép trừ hoặc phủ định. Renderer giữ **nguyên ý và qualifier** của hướng được duyệt, chỉ bỏ metadata điều kiện Level ở cuối; không viết lại thành phép thay bound mặc định. Các họ sửa khác chưa được nhận diện sẽ fail-closed, không được nhận điểm actionability nhờ có động từ hành động.

Code review đã tìm một lỗi bản đầu: recognizer dựa trên các từ rời rạc làm mất phủ định/phép trừ/chiều gán, còn renderer viết thành hướng thay bound dương. Ba fixture tái hiện thất bại trước sửa; sau sửa đều bị từ chối, qualifier được giữ. Review lại không còn issue mức Important. Không lấy việc quote đúng hoặc input được duyệt làm lý do bỏ qua lỗi biến đổi ý nghĩa này.

Entry point `scripts/task3_render_oracle.py` chỉ nhận real-train/real-val, yêu cầu approval/hash hợp lệ, từ chối public và output ngoài ignored outputs; từ chối ghi đè thư mục đã có. Kết quả là **oracle diagnostic projection**, tuyệt đối không phải inference public. Taxonomy trong prediction file copy gold để giữ schema, không được chấm là taxonomy model.

## 3. Fixture train-only/artificial và adequacy v4

Không lấy student source hoặc ID real-val làm fixture/quy tắc. Các fixture mới dùng code nhân tạo, tên biến khác, vị trí nguồn tự tính, không gọi model. Bao phủ warning/error cùng xuất hiện, warning-only không đủ, extra invented claim, literal/parameter, vòng lặp không tiến, specific/generic/full-solution, câu đúng bị từ chối, praise chưa xác minh, CJK prose/source, reference chỉ trong comment, action đảo chiều/phủ định/phép tính và qualifier.

Quan hệ nguồn là **surface recognizer**, không proof C++. Nó biết reference có declaration trong code chứ không chỉ comment; không tự chứng minh reference đó đúng về toán học hoặc mọi claim trong đoạn văn đúng. Fixture riêng cố tình thêm claim sai về entry point cạnh một action cụ thể: action recognizer vẫn nhận specificity, trong khi structured projection validator từ chối claim thêm. Đây là giới hạn được kiểm tra, không được lờ đi khi báo chất lượng.

Sau khi fixture phân biệt được action cụ thể/chung/lời giải đầy đủ mới thêm `quality_review_flags(..., version=4)` và opt-in `quality_review_policy_version: 4`. Cấu hình `r12_adequacy_diagnostic.yaml` kế thừa Round 11, chỉ đổi selector này. Prompt, model, decoding, guard disclosure, retry và gold không đổi. Default pipeline vẫn dùng policy cũ. Direct B parser live chưa đổi; replay B dưới đây là giả lập áp dụng screen mới.

| Đo riêng trên fixture đã dùng để phát triển | Legacy | Mới |
|---|---:|---:|
| Action đủ cụ thể: 4 positive / false rejection | 3/4 FR | 0/4 FR |
| Generic, invented reference, full solution, reversed/negative/arithmetic: 8 negative / false acceptance | 3/8 FA | 0/8 FA |
| Mutations của structured document: 8 negative, gồm claim/cause/PID/location/reference/praise/CJK | Không có structured contract | 8/8 bị từ chối, 0/8 FA |

Đây là **12 action fixtures phát triển**, không heldout, không estimate tổng quát. Coverage literal và non-progress ở Level 2 kiểm tra hai finding cùng được giữ; không suy ra đã hỗ trợ hướng sửa mọi loại loop ở Level 3. Factual support của renderer là preservation theo input đã duyệt; recognizer độc lập vẫn ghi `not_assessed`. Artifacts `fixture-metrics.json` và red/green test logs trong ignored outputs.

## 4. Replay 67 lượt: tăng acceptance không phải tăng factual quality

Replay không model và không sửa raw: 27 feedback/direct trong bundle lịch sử; 18 C1/C2 Round 11; 12 B1/B2 Round 11; 10 A1/A2 resolved-feedback. Diagnosis không đi qua adequacy feedback nên không được đếm vào 67 lượt. Khôi phục compiler lịch sử unavailable khi cần. Acceptance legacy replay khớp 67/67 quyết định đã capture; missing B subchecks/prompt capture lịch sử vẫn là giới hạn Round 11, không được biến reconstruction thành capture gốc.

| Chuyển trạng thái | Số lượt | Review nguyên nhân |
|---|---:|---|
| Tổng accept legacy → mới | 42 → 47 | Không phải completion của run mới hoặc factual metric |
| Reject → accept | 8 | BF16 C S212 lượt 1; C1 S212 cả 3; A1/A2 resolved-feedback S212 mỗi nhánh lượt 2–3. Đều có core diagnosis và relation digit-count hữu ích; wording uninitialized/undeclared vẫn cần chú ý |
| Accept → reject | 3 | B1/B2 S212 chỉ khuyên khai báo chung; B NF4 lịch sử có câu ghép biểu đạt binding ngoài grammar hiện hỗ trợ |
| Full/multiline solution BF16 S212 lượt 2–3 | Vẫn reject | Không nới disclosure guard |
| C2 S212 generic, cả 3 lượt | Vẫn reject | Không cứu mất relation bằng từ “khai báo” |

B NF4 lịch sử S212 có **relation sửa hữu ích trong một câu ghép** nhưng cũng có claim/nhãn không nhất quán. Rejection mới ở đây là do grammar hẹp, không phải phát hiện claim sai. Đây là false-rejection candidate của thành phần action, dù toàn feedback không đáng được nhận là đúng. Không thêm grammar khớp lại câu đã thấy sau khi replay để làm đẹp chỉ số.

Danh sách review có 16 final acceptances đã biết sai/mixed/source hoặc taxonomy-finding mismatch từ Round 10/11: mới vẫn nhận **15/16**, chỉ một B lịch sử bị chặn vì giới hạn grammar nói trên. Hai final feedback có CJK vẫn accepted ở cả hai screen tự do; v4 không được gọi là factual/language guard. Một số praise chưa xác minh vẫn warning-only. Do annotation mọi claim/attempt chưa đầy đủ, không báo một FPR/FRR semantic toàn bộ 67 lượt hoặc completion toàn split từ replay.

Artifacts: `adequacy-replay.json`, `retained-false-acceptances.review.json`. Không đưa raw claim/source vào report Git; danh sách chi tiết giữ riêng tư.

## 5. C2 cũ so với renderer mới: cùng finding và Level

Approved set không đổi: S106-loop, S106-allocation, S111-syntax, S112-literal, S212-undeclared; 5 finding/4 ca. S201-overflow và S211-output vẫn gold-disagreement, không đưa vào C2, gold [] giữ nguyên. Không bịa independent loop finding cho S212.

| ID / Level | C2 model Round 11 | Structured renderer Round 12 | Factual/coverage theo phạm vi đã duyệt |
|---|---|---|---|
| S106 / 2 | Nắm hai cơ chế lõi nhưng cách nói range truy cập hơi gộp | Hai unit riêng P3/P2, vị trí nguồn, fact/cause nguyên văn được duyệt; không repair | 2/2 finding được giữ, không thêm nguyên nhân P4 hoặc kích thước cấp phát sai |
| S111 / 2 | Added operator/declaration claims, bỏ finding được cấp; vẫn accepted | Một unit P1 tại dòng 51, đúng thiếu đối số và cause cú pháp; diagnostic error thật ở vị trí đó, không dùng warning để đổi cause | 1/1; khắc phục fabrication tại tầng render bằng cách bỏ sinh tự do, không chứng minh đã sửa khả năng hiểu log của Qwen |
| S112 / 2 | Đúng lõi literal/parameter | Giữ fact/cause được duyệt, không chỉ cách sửa, không khẳng định mọi open đều thất bại | 1/1; không dựa vào tên file đích bịa |
| S212 / 3 | Đúng undeclared nhưng cả 3 lượt chỉ khuyên khai báo; không accepted final | Unit P1 tại dòng 25; repair_action target là bound lỗi, reference là digit-count đã có; giữ hướng được duyệt gắn quan hệ ấy, không full solution | 1/1 diagnosis và relation được giữ, không thêm gold VL không có independent finding |

S201/S211 / Level 1: renderer không tiết lộ kỹ thuật, không khen đúng/gần đúng, giữ status không có supplied finding chứ không clean. Không tính technical coverage cho hai ca này.

| Chiều kết quả | C2 cũ | Renderer mới |
|---|---|---|
| Accepted/output | 5/6 prefix, fail-closed S212; không full prediction export | 6/6 schema-valid oracle projection, gồm hai neutral L1 |
| Coverage approved Level 2 | Prefix 3/4, S111 không đạt | 4/4 preservation |
| Level 3 cụ thể theo approved relation | 0/1 trong raw C2, không final | 1/1 preservation |
| Claim thêm ngoài approved findings | Có ở S111 | Không cho phép bởi closed projection; support conditional |
| L1 disclosure / praise | Không technical disclosure; không phải xác minh clean | 2/2 không technical disclosure, không praise |
| Disclosure Level 2/3 | Guard-pass không bảo đảm factual/adequacy | 4/4 ca có finding qua disclosure và review nội dung; không code solution |
| CJK ở output mới | C2 mới không có; lịch sử khác có | 0/6 prose, source CJK chỉ private provenance nếu có |
| Taxonomy F1/exact | Không chấm oracle | Không chấm oracle, copy gold không phải prediction |

Không tính metric toàn split cho C2 cũ từ prefix. Số 5/5 finding của renderer là preservation theo annotation nhỏ đã xem nhiều lần, không discovery recall của mọi lỗi thật. Không báo fallback 0/6 như quality score: hai câu L1 trung tính không phải feedback tìm lỗi có ích.

Official renderer run wall khoảng **0,505 giây**, gồm syntax-only/preflight/serialization, **model_calls=0, programs_executed=false**. Không có peak VRAM/token/precision đo mới. C2 cũ dùng model nên không lấy chênh lệch wall làm benchmark cùng công việc. Runtime/config/review hash/source hash ở `oracle-renderer-final/run.json`; ledger ở `oracle-renderer-final-ledger.json`.

## 6. Bốn test sandbox: nguyên nhân và sửa quyền hẹp

Tái hiện đủ bốn failure cũ trước sửa. GCC 13.3.0 trả `-print-prog-name` cho cc1plus/collect2 trong **`/usr/libexec/gcc/x86_64-linux-gnu/13/`**; file và ancestor có mode cho phép đọc/chạy thông thường. Landlock chỉ cho compiler đọc/chạy /usr/lib, include và bin; thiếu cây helper /usr/libexec/gcc, nên child báo execv Permission denied trước khi compile fixture. Không phải source lỗi và không phải cần bỏ isolation.

Chỉ thêm read/execute cho **`/usr/libexec/gcc` ở phase compile**. Không mở cả /usr/libexec hoặc /usr, không thêm quyền write, không đổi seccomp/uid/no_new_privs/rlimits/network/fork runtime. Test mới xác nhận runtime không đọc được helper tree này. Các test cũ tiếp tục kiểm tra private include bị cấm, /etc/private read, network/fork bị cấm, write ngoài scratch bị cấm, wall timeout, output limit, loop/flood. Không chạy executable của sinh viên; executable trong test đều là fixture nhân tạo.

Bốn test cũ đã pass trong full suite: `test_actual_cpp11_gcd_inputs_outputs_are_recorded`, `test_cpp11_missing_climits_is_a_useful_compiler_failure`, `test_actual_digits_contract_and_wrong_output_remain_measurements`, `test_cpp_infinite_loop_and_output_flood_are_stopped`. Module riêng sau sửa: 20 passed, 1 skipped; bản full Task 3 không loại module.

## 7. Kiểm tra, tái hiện và quyết định tiếp theo

- **Toàn bộ `tests/test_task3_*.py`: 398 passed, 4 skipped**, 6,55 giây. Renderer artificial/regression: 38 tests trong số đó. Có log red trước sửa và green sau sửa, gồm issue code review.
- `pytest -q` toàn repository đã thử nhưng dừng collect hai module Task 1 (`test_clm_zeroshot_task1.py`, `test_task1_clm_probe.py`) vì môi trường thiếu **sklearn**. Không tự gọi 398 Task 3 là full repository pass; không cài dependency Task 1 ngoài scope để che lỗi.
- Validator offline entry point repo: **VALID 6/6**, Level counts 2/3/1/0, đúng thứ tự sáu ID. Validator không chấm ngữ nghĩa.
- Manifest/finding hashes giữ nguyên, official run worktree clean; diff check trước commit. Chỉ stage code/test/config/report, không stage raw/student code/data/checkpoint/cache/ZIP.

```bash
cd /workspace/llm-final-project
.venv-task3/bin/python -m pytest -q tests/test_task3_*.py
.venv-task3/bin/python scripts/task3_render_oracle.py \
  --config configs/task3/r12_adequacy_diagnostic.yaml \
  --findings outputs/task3/mechanism-round11/findings-approved-C2.json \
  --split real-val --output-dir outputs/task3/renderer-round12/reproduce-oracle
.venv-task3/bin/python scripts/validate_task3_submission.py \
  --predictions outputs/task3/renderer-round12/oracle-renderer-final/predictions.json \
  --requested-levels outputs/task3/mechanism-round11/requested-levels.real-val.json
PYTHONPATH=. .venv-task3/bin/python outputs/task3/renderer-round12/replay_adequacy.py
PYTHONPATH=. .venv-task3/bin/python outputs/task3/renderer-round12/fixture_metrics.py
```

Renderer CLI từ chối ghi đè thư mục; dùng tên mới khi tái hiện. Hai script audit/metrics cuối là công cụ nội bộ nằm trong ignored outputs cùng raw input; cần giữ cả artifacts Round 10/11 để replay, không tái dựng finding từ gold taxonomy. `audit_inputs.py` tạo báo cáo nội bộ raw tám attempt và không gọi model.

**Tầng đã cải thiện:** projection khi finding đã đúng; giữ vị trí/fact/cause/action, trần Level; compiler-evidence severity; fixture isolation; một phạm vi nhận diện action cụ thể có regression test. Có thể giữ interface renderer có điều kiện này làm đối chứng oracle ổn định trong phạm vi đã hỗ trợ.

**Tầng chưa giải quyết:** tự tìm finding, entailment của cause, known-clean vs unknown, mapping finding→taxonomy đầy đủ, diagnosis schema/truncation của A, false positive/mismatch B, và factual/language guard cho text sinh tự do. Opt-in v4 còn từ chối họ câu/repair chưa hỗ trợ; không thay default toàn hệ thống hoặc gọi nó đủ mạnh để dùng public.

Trọng tâm tiếp theo là finding **không cần gold trên train-only/artificial fixtures**, giữ compiler error tách warning, yêu cầu observed fact/cause có entailment và binding repair trước khi đi vào renderer. Không tiếp tục tìm prompt trên sáu ca này. Chỉ đánh giá heldout một lần sau khi đóng băng **toàn bộ** cách tạo finding và render; Round 12 chưa thỏa điều kiện đóng băng A/B nên chưa chạy heldout. Không suy ra chất lượng tổng quát từ preservation của năm oracle findings.

## 8. Xác minh khi tiếp tục trên branch hiện tại

Tiếp tục từ `d175a4c` trên cùng branch, working tree ban đầu sạch; code/test Round 12 đã có trong `8cf15aa`, báo cáo trong `d175a4c`. Không viết lại implementation hoặc chạy tìm prompt mới.

- Chạy lại **đầy đủ Task 3: 398 passed, 4 skipped, 6,52 giây**, gồm `test_task3_cpp_checks.py`; log `outputs/task3/renderer-round12/tests-task3-resume-verification.log`.
- Tái hiện renderer oracle với cùng approved file/config: 6 bản ghi, không gọi model; `documents.json` bằng chính xác run chính thức trước đó. Validator: VALID 6/6. Artifacts mới ở `outputs/task3/renderer-round12/oracle-resume-verification/`, không ghi đè raw/source/prompt/attempts.
- Replay lại 67 attempts khớp toàn bộ quyết định legacy; acceptance 42 → 47, gồm 8 reject → accept và 3 accept → reject. Fixture action vẫn có 0/8 false acceptance và 0/4 false rejection; đây là fixture phát triển, không estimate heldout. Giới hạn factual của text tự do ở mục 4 vẫn giữ nguyên.
- Không chạy public/heldout, không sửa gold, không push. Oracle findings/raw và outputs mới vẫn ignored; chỉ bổ sung xác minh vào báo cáo đã commit.

Renderer đủ ổn định làm đối chứng có điều kiện cho họ action đã hỗ trợ. Bước nghiên cứu kế tiếp chuyển sang tạo finding không cần gold trên train-only/artificial fixtures, với factual support và coverage đo riêng; chưa đóng băng A/B end-to-end và chưa đánh giá heldout.
