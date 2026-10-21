# Task 3 — concrete witness, controlled mechanism test

**Chưa chứng minh Qwen 7B lần theo hành vi code đáng tin hơn R15. Giữ R15; dừng ở diagnosis, không làm renderer.** Trên18 cặp evaluation đã khóa, R15 nhận đúng cả hai thành viên ở3 cặp; candidate vận hành đạt0. Candidate có46 schema errors,1 uncertain và1 diagnosis đủ schema nhưng dùng input không hợp lệ. Lỗi format là nhiễu lớn của thí nghiệm, nên không dùng0/18 để bác bỏ mọi cách dùng witness.

Bằng chứng thực thi vẫn phân xử được một phần nguyên nhân: ngay **trước renderer**, raw diagnosis đã dự đoán hành vi theo yêu cầu đề thay vì code, hoặc chọn input không phân biệt được lỗi. Có một cặp raw witness tính đúng; không đủ lợi ích ổn định để thay production. Không fine-tune, không public inference/submission/leaderboard/push, không sửa source/gold cũ. Các mốc R15 zero-shot0,3834 và DIRECT SFT v1 0,1517 cùng provenance của chúng giữ nguyên; không dùng các điểm đó để chọn thí nghiệm.

## Trạng thái và bảo toàn

Repository `/workspace/llm-final-project`, branch `feat/task3-quality-round5`; HEAD ban đầu **`3214cfcc67b40a259d4c70e1e69b1216586d15ef`**, working tree sạch. Làm trực tiếp tại checkout này, không clone/worktree/project khác. Snapshot bảo vệ2.936 đường dẫn gồm tracked files, dữ liệu và toàn bộ bundle requirement-evidence; SHA bundle trước là `01d3f9a8df3eb3cfc9891a670d1452434bc66aa0dde0a1980815f5853741d029`. Final HEAD/commit/status được ghi sau commit trong private `final-handoff.json`.

R15 native config `r15_selected.yaml` → `r15_zero_shot.yaml` → `r15_common.yaml`, prompt/parser/controller/guard/backend giữ nguyên. Cả hai nhánh dùng **Qwen/Qwen2.5-Coder-7B-Instruct**, revision **`c03e6d358207e414f1eca0bb1891e29f1db0e242`**, chạy thật trên RTX5090, actual NF4 double quant/BF16 compute, toàn bộ weights trên CUDA, không adapter/mock/replay/commercial inference API. Seed42, greedy, context16384, R15 cap1024/tối đa3 attempts, candidate cap1536/tối đa2 schema attempts, generation max_time45s. Tokenizer-template SHA `cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f`. Few-shot0, không dùng bốn case điều tra làm ví dụ.

Train task source là member `generate-dataset/exams.json` trong ZIP root `generate-dataset_v2.zip`, SHA ZIP **`6bda70c29254a3bce91933b65f4a311d73a052e72d181c97e977152e14602f9b`**; mỗi family ghi các ID thuộc prepared synthetic-train làm provenance. Chỉ dùng đề và miền train để viết source giả mới. Không dùng public/heldout statement, source, prediction, attempt hoặc leaderboard cho generation/selection. Public artifacts chỉ được hash để bảo toàn, không parse nội dung. Original annotations/teacher feedback chỉ được đọc riêng cho audit lịch sử sau inference.

## Cách ly thực thi đã hoạt động, với giới hạn cụ thể

`unshare` user/mount/net/PID vẫn `Operation not permitted`; không có Docker/Podman/bwrap/nsjail/firejail hay daemon socket. Không khẳng định đã xác định được chính xác outer seccomp/AppArmor/host userns policy từ trong container. Có sẵn CAP_SYS_CHROOT/SETUID/SETGID/SETPCAP và libseccomp, nên dùng một đường cách ly khác, không thay host và không `--privileged`:

- Chroot vào rootfs chỉ gồm toolchain GCC13 và dependency cần thiết; không mount `/proc`, thiết bị, host project hay filesystem khác. Đổi cwd vào jail, đóng FD ngoài stdin/stdout/stderr.
- Hạ UID/GID về64022 chưa được dùng trong passwd, supplementary groups rỗng; bỏ capability bounding set và kiểm effective/permitted/inheritable đều0; bật `no_new_privs`.
- Seccomp mặc định từ chối: runtime không có socket/connect, fork/clone, mount, ptrace, kill, đổi UID hoặc chroot. File input chỉ mở read-only; chặn create/truncate/append/tmpfile và mọi syscall sửa filesystem. Output chỉ qua các FD kế thừa bị giới hạn.
- Runtime: AS512MiB, CPU soft1/hard2s, wall2s, NPROC1, NOFILE64, CORE0, FSIZE64KiB/file. Compiler cố định: AS512MiB/process, CPU soft4/hard5s, wall10s, NPROC4, FSIZE8MiB/file; clone flags bị thu hẹp, clone3 trả ENOSYS để toolchain fallback. Parent kết thúc process group.

Probe **đã thực thi** xác nhận: UID/groups, không đọc được repository/path cha/proc, socket/fork/setuid/chroot/mount/ptrace bị chặn, tạo file/thư mục bị chặn, CPU bị SIGXCPU, allocation lớn bị từ chối, output bị SIGXFSZ trong64KiB, và input read-only có thể cấp lại an toàn. Ba integration tests kiểm enforcement thực, ngoài unit tests khai báo policy.

Đây là sandbox cho lượt offline tuần tự hữu hạn, **không phải VM/kernel boundary hay dịch vụ multi-tenant chống mọi compiler/kernel exploit**. Compiler phase chạy trusted toolchain với source không tin cậy; giới hạn bộ nhớ/CPU là per-process, tối đa khoảng2GiB AS cộng dồn, **chưa có aggregate compiler disk quota**. Runtime filesystem read-only đóng đường tạo vô hạn file của chương trình sinh. Rootfs tin cậy và UID riêng là giả thiết. Scratch phải cùng filesystem với rootfs do materialize bằng hardlink. Integration test đầu tiên dùng `/tmp` nên lỗi EXDEV; đã sửa vị trí fixture, giữ log lỗi, không sửa protocol/source/oracle sau freeze.

Chroot hoặc seccomp riêng lẻ không được gọi là sandbox đầy đủ; mô hình kết hợp trên áp cả filesystem, đặc quyền, syscall và resource controls. Căn cứ thiết kế: [Linux seccomp filter documentation](https://www.kernel.org/doc/html/latest/userspace-api/seccomp_filter.html), [Linux chroot manual](https://man7.org/linux/man-pages/man2/chroot.2.html). Kết quả thực thi dựa vào probe/log local, không dựa vào hai tài liệu này để giả định sandbox đã chạy.

## Bộ cặp và oracle khóa trước model

**24 cặp /48 chương trình /24 family**, gồm17 single-problem và7 CSV/function context,21 tên cơ chế. Mỗi mutant là đúng một phép thay thế source đã ghi before/after; baseline và mutant khác hash. Chương trình dùng nhiều cách viết: range loop, iterator, vector/set, Euclidean fold, accumulator, string reversal, state update, STL algorithms;7 CSV case chia sẻ3 parser scaffold, không gọi chúng là24 task độc lập thống kê.

Sáu family development cố định: GEN, PRIME, REVSTR, MAXARR, COUNTGT, SUMB.18 family còn lại evaluation, family-disjoint **trong bộ mới này**. Tất cả family có prior exposure trong lịch sử, nên đây là **controlled mechanism test, không phải benchmark mù**. Audit bank/calibration/fresh/confirmation/requirement-evidence và prepared train:0 exact/renamed-code matches;3 member near≥0,75, thuộc WB22-06/WB22-07; max0,9452. Có2 cặp baseline khác family near≥0,75. Không loại/chọn lại theo output; full nearest IDs/hashes/similarities nằm private. Inventory không chứng minh mọi lượt xem lịch sử đều được ghi đầy đủ.

Mỗi đề được giữ nguyên, thêm miền hữu hạn và semantics của harness. Mọi ID requested **Level2** để R15 có thể chẩn đoán vị trí/nguyên nhân; chưa đo renderer/Level1,3,4. Opaque IDs/order không tiết lộ member role trong prompt. Các test/stdout/expected/role/mutation/counterpart chỉ có trong scorer, không vào model payload.

Oracle Python độc lập theo yêu cầu toán học; không dùng chương trình nền làm oracle. **771 input tests**, mọi baseline compile và khớp oracle trên tất cả test của nó;22 mutant runtime có khác biệt thật,2 mutant compile có diagnostic thật. Tổng **1.507 program executions** trước inference;35 mutant test slots không chạy vì compile error, không gọi chúng là actual runtime output. Mỗi cặp khóa một witness index phân biệt hoặc compile diagnostic, kèm hash source/binary/config và stdout/stderr/exit.

Đây là xác nhận trên danh sách test/harness đã chỉ rõ, **không chứng minh đúng mọi input trong hay ngoài miền**. Một số scalar domain được enumerate hết, còn array/string/CSV chủ yếu test xác định và seed cố định. Multi-problem driver quan sát P4/P2; helper P3 được source-review, chưa mọi helper đều được chạy độc lập. Review oracle/domain vẫn cần người kiểm tra; không coi đồng ý của LLM hay source quote là chứng minh.

Freeze **trước mọi model call**: `pre-inference-freeze.json`, SHA **`36898303bd56092e79e34b65fb90f6d6bb9732f96ba0adc6dbd01deeaf2a18a6`**. Khóa code cặp, split/domain, toàn bộ test/oracle/execution, model input projection, prompt/config/runner/scoring-oracle source và security probes. R15/candidate không nhận actual từ hidden tests. Cả hai được nhận compiler result thật của **chính submission đang xét**, vốn pipeline có thể lấy ở inference; compiler pass không được coi là đúng logic.

## Candidate duy nhất và việc gate thất bại

Một lượt diagnosis yêu cầu tự chọn input, dự đoán stdout/termination bằng phép toán code, suy expected riêng từ đề, rồi nêu P/quote/requirement/mechanism/taxonomy chính thức. Không đưa source counterpart, hidden witness/oracle, mutation label, gold hoặc teacher. Hai attempts chỉ để sửa JSON/schema; không dùng oracle để retry, không semantic repair guard/few-shot/fallback. Không có renderer trong code chạy.

Protocol khóa yêu cầu structured output11 trường, `files` map, official taxonomy và quote substring chính xác. **Đây vẫn là gánh nặng format đáng kể**, dù chỉ có một finding, và là giới hạn thiết kế quan trọng của vòng này. Không sửa prompt/parser hoặc cứu output sau khi thấy thất bại.

|Kết quả vận hành /48 ID|R15|Witness diagnosis|
|---|---:|---:|
|Mọi ID được xử lý|48/48|48/48|
|Final đúng native output schema|48|1 defect +1 uncertain|
|Schema errors sau2 attempts|0|46|
|Input hợp lệ trong output đủ schema, phân xử được|không yêu cầu witness|0|
|Fallback|0|0|
|Raw calls|56|96|
|Output tokens|4.257|19.479|
|Generation latency quan sát|56,60s|250,05s|
|Runtime model errors|0|0|

Load6,16s; peak allocated7,07GB, reserved7,21GB; không phải throughput benchmark độc quyền GPU. Output defect đủ schema duy nhất ở mutant WB22-23 vẫn có file sai miền và finding về compile/P1 không có căn cứ. Uncertain giữ nguyên trạng thái, không biến thành clean/taxonomy rỗng. Schema-valid không được dùng làm điểm nội dung.

First failing check trong96 attempts: thiếu/không đúng taxonomy47, thiếu input stdin/files24, quote không match19, expected rỗng3, trạng thái clean mâu thuẫn nhãn1;2 accepted. Trong19 quote rejects, **17 token-equivalent nhưng khác whitespace**. Vì vậy tỷ lệ schema error không thể được diễn giải thành tỷ lệ model không hiểu code. Ngược lại, vượt schema không chứng minh behavior đúng.

Gate trước inference đòi≥12/18 paired successes, hơn R15≥4 cặp, không tăng mutant false-clean, và witness thực sự hợp lệ/actual/expected/mechanism đúng. Uncertain/schema/error/fallback là thất bại trong mẫu số. Gate thất bại rõ, nên **không xây renderer, không thêm guard, không fine-tune hoặc chạy public**.

## Paired accuracy và khả năng lần theo behavior

Pair R15 đạt khi baseline không bị bịa lỗi, mutant được nêu đúng cơ chế trọng tâm và taxonomy khác rỗng. Unknown không được thưởng. Nhóm taxonomy chính xác/Level2 leakage được ghi riêng; pair này đo diagnosis, không phải điểm submission. Ví dụ compile mechanism đúng nhưng label quá rộng vẫn được ghi core-correct kèm dispute, không sửa proposed reference để tăng điểm.

Candidate vận hành còn cần output hợp lệ và witness đáng tin. Không có baseline candidate nào hoàn tất non-uncertain, nên0 cặp, độc lập với việc đặt thêm điều kiện numerical. Các bảng hậu kiểm dưới đây được tách để thấy nội dung bị lỗi format che khuất.

|Cặp đạt /toàn bộ mẫu số|Development6|Evaluation18|Tất cả24|
|---|---:|---:|---:|
|R15: clean member +đúng cơ chế mutant|1/6|3/18|4/24|
|Candidate vận hành|0/6|0/18|0/24|
|Raw-first: decision +core mechanism, **bỏ qua** schema/input/numerics — hậu kiểm|2/6|6/18|8/24|
|Raw-first: thêm input hợp lệ, actual/expected đúng, witness phân biệt — hậu kiểm|0/6|1/18|1/24|

Hai dòng raw **không phải candidate đã hoàn tất**, không thay gate, không chọn best-of retries. Chỉ đọc **attempt1 của mọi ID**, không chọn response đẹp. Với task stdin-only, thiếu `files` được hiểu `{}` **chỉ để quan sát hậu kiểm**; không áp vào pipeline. Có tín hiệu nhận diện cơ chế cục bộ tốt hơn trong raw-core, nhưng phần lớn lợi ích biến mất khi yêu cầu witness thật. Không gọi đây là bằng chứng khái quát lên public.

|Raw-first hậu kiểm, mẫu số giữ nguyên|Tất cả48|Baseline24|Mutant24|
|---|---:|---:|---:|
|Input hợp lệ|30/48|15/24|15/24|
|Predicted actual khớp execution/diagnostic|22/48|14/24|8/24|
|Predicted expected khớp oracle|21/48|14/24|7/24|
|Cả actual và expected đúng|16/48|13/24|3/24|
|Task-paraphrase thay vì mô tả phép toán, review tác giả|29/48|17/24|12/24|
|False-clean **decision** trên mutant|13/24 mutant|—|13/24|
|False accusation trên baseline|1/24 baseline|1/24|—|

Invalid/unknown không vào tử số đúng, không bị loại khỏi mẫu số. Trong30 valid input,28 được chạy thật;2 dựa trên real compiler diagnostics. Chỉ12/24 mutant raw proposals dùng input thực sự phân biệt; nhiều input còn invalid hoặc tình cờ không lộ lỗi. `no_defect_in_scope` trên mutant là false-negative decision đối với bộ cặp đã biết có phản ví dụ; không tự gọi mọi câu đó là lời khen đúng tuyệt đối. R15 có13/24 baseline taxonomy khác rỗng,5/24 mutant taxonomy rỗng,11/24 mutant cơ chế đúng và1/24 còn tranh luận.

Bằng chứng quan trọng không chỉ là field thiếu:

- WB22-04, WB22-07, WB22-14: input model chọn hợp lệ, predicted expected đúng, nhưng predicted actual không khớp execution. Model gán kết quả đề yêu cầu cho chương trình có phép so sánh/cận xử lý khác. Lỗi xuất hiện ngay ở diagnosis, chưa có renderer.
- WB22-12, WB22-17: input chọn không kích hoạt lỗi; actual/expected trùng nhau trên input đó không chứng minh chương trình nền và mutant tương đương.
- WB22-09, WB22-10, WB22-11: nêu được một phần lỗi nhưng termination/số lần cập nhật/thứ tự chữ số bị suy sai. Có finding gần đúng không đồng nghĩa actual prediction đúng.
- WB22-16: raw witness thực sự khớp actual/expected và cơ chế, nhưng thiếu field nên không là operational completion. Đây là thành công cục bộ được giữ đầy đủ trong packet.
- Toàn bộ7 CSV pair: raw-first dùng file phân cách whitespace, trái scope dấu phẩy; nhiều giá trị còn vượt bound. Không chạy những input invalid để cộng điểm. Có cả lỗi phép tính đơn giản và mô tả P2 theo đề dù source đã đổi phép gán/toán hạng/field.

## Từng cặp và cơ chế — đã lược source/test nhạy cảm

`D` là development, `E` evaluation. Candidate vận hành0 ở mọi hàng; bảng ghi R15 paired success và nội dung raw-first hậu kiểm. Metric theo đủ21 cơ chế nằm trong Results JSON, không chỉ các ca tốt.

|Pair /family|Split|Cơ chế cài|R15 pair|Raw witness thất bại/giúp ở đâu|
|---|---|---|---:|---|
|WB22-01 /SUMEVEN|E|Sai predicate|0|Actual đúng nhưng expected sai; source finding có căn cứ|
|WB22-02 /COUNTUPPER|E|Counter đi ngược|1|Nhận cơ chế, nhưng input quá dài và actual prediction không theo số lần cập nhật|
|WB22-03 /COUNTVOWEL|E|Bỏ computation/call|0|Biết output hằng, vẫn decision clean; expected là placeholder, retry uncertain|
|WB22-04 /PALIN|E|Đảo phép so sánh|0|Sao chép kết quả mong muốn vào actual; execution bác bỏ|
|WB22-05 /REVSTR|D|Thiếu token cú pháp|1|Compile diagnostic đúng; expected không phải output cụ thể|
|WB22-06 /PRIME|D|Boundary primality|0|Input ngoài scoped domain và không chạm boundary gây lỗi|
|WB22-07 /PERFECT|E|Tính cả self-divisor|0|Đọc định nghĩa perfect-number thay cho hành vi vòng lặp|
|WB22-08 /FACT|E|Entry-point type|1|Thấy compile cause nhưng prose tự mâu thuẫn, expected không cụ thể|
|WB22-09 /FIB|E|Initial state sai|1|Sai termination và output dù nêu đúng biến khởi tạo|
|WB22-10 /DIGITSUM|E|Ghi đè accumulator|0 /unknown cause|Nhận thiếu cộng dồn, dự đoán sai chữ số còn lại|
|WB22-11 /POWER|E|Thiếu lượt nhân|0|Dự đoán theo lũy thừa đề yêu cầu, thêm claim không liên quan|
|WB22-12 /MAXARR|D|Sentinel sai|0|Chọn input làm sentinel vô hại, bỏ sót miền kích hoạt lỗi|
|WB22-13 /SECONDMAX|E|Gọi nhầm khi xuất|0|Bịa thứ tự/index ở baseline; mutant vẫn sai actual dù thấy callee|
|WB22-14 /DISTINCT|E|Đọc thiếu input cuối|0|Nói đã đọc đủ số lượng đề yêu cầu, trái execution|
|WB22-15 /GCDARR|E|Bỏ reduction cuối|0|Trace phần đã xử lý đúng nhưng input không phân biệt|
|WB22-16 /ARM|E|Exponent cố định|0|Một raw witness numerical+mechanism thành công; chưa đúng operational schema|
|WB22-17 /BASE2|E|Bỏ đổi thứ tự digit|0|Input đối xứng nên không lộ mutation|
|WB22-18 /GEN|D|Parser bỏ separator|0|Input CSV invalid; mô tả đọc thành công theo yêu cầu|
|WB22-19 /PROD|E|Ghi đè tích lũy|0|Input invalid, số học sai, behavior mô tả cộng toàn bộ|
|WB22-20 /SUMPAIR|E|Thiếu toán hạng|0|Input invalid; không nối việc chỉ cộng một field với yêu cầu hai field|
|WB22-21 /SUMB|D|Sai field|0|Input invalid; vẫn mô tả field đề yêu cầu|
|WB22-22 /MINA|E|Comparator ngược|0|Input invalid; gọi thao tác chọn maximum là minimum|
|WB22-23 /COUNTGT|D|Equality boundary|0|Raw thấy comparator, input invalid; retry đổi sang finding compile/P1 vô căn cứ|
|WB22-24 /RANGE|E|Gọi nhầm khi xuất|0|Input invalid, call chain/so sánh bị suy sai hoặc chỉ khen chung|

R15 cũng có lỗi thật bị feedback/Level làm mất tác dụng: WB22-02/WB22-09 nêu đúng cause nhưng khuyên thay cụ thể ở Level2; WB22-08 core compile cause đúng nhưng taxonomy là nhóm hàm. Không dùng những thiếu sót đó để cộng điểm cho candidate. Ở vòng này **không có renderer để đo corruption mới**; packet lịch sử giữ các finding/render đã hỏng của vòng trước, chỉ làm điều tra.

## Audit annotation và bốn case đã thấy

Original source/gold/teacher bytes giữ nguyên. Private audit có source, hash, harness nếu cần, compiler/stdout và đề xuất dưới đây, **author-agent review, not human-verified**:

|ID|Source evidence|Annotation gốc /teacher|Đề xuất bản dẫn xuất|Confidence /tranh luận|
|---|---|---|---|---|
|SYN-COUNT-0004|Probe P3 sau P1, input hợp lệ; kết quả hằng không đạt yêu cầu minimum|Taxonomy `[]`; teacher đã ghi P3 chưa làm|Giữ nhận xét teacher đó; quarantine target cặp nhãn mâu thuẫn, chỉ sửa taxonomy ở version dẫn xuất sau reviewer|Cao về defect P3; separator/capacity P1 là tranh luận riêng, không dùng để chứng minh P3|
|SYN-PERFECT-0000|Real C++11 diagnostic non-int entry point; không có runtime output|Gold compile-error; teacher khen đúng|Giữ taxonomy có căn cứ; quarantine lời khen khỏi derived train target chờ review|Cao về compile issue; chưa kết luận logic/performance sau sửa|

Bốn case `L2D-COUNT-03`, `L2D-PROD-02`, `L2D-PROD-03`, `L2D-SUMPAIR-03` chỉ thuộc `historical-investigation.private.json`, **không** là48 ID benchmark/few-shot. Lượt này có compiler diagnostic hoặc executed probes với harness ghi rõ, xác nhận cơ chế mà review tĩnh trước từng đề xuất. Với parser fail, harness tôn trọng prerequisite và báo đọc thất bại, không chạy hàm cần dữ liệu chưa có. Không coi chúng là bốn ca mới độc lập hay human-verified.

## Các giới hạn làm kết luận phải hẹp

Oracle/execution đủ kiểm tra phản ví dụ cụ thể; blocker hiện tại không còn đơn thuần là thiếu sandbox. Tuy nhiên format11 trường, exact quote, domain English nối vào đề Vietnamese và original filename khác driver `data.csv` làm instruction-following lẫn vào đo tracing. WB22-19/22/24 có context-dispute ở R15, được ghi riêng; không giấu bất đồng hoặc đổi source sau output. Bản review có addendum minh bạch phân biệt “trace cụ thể nhưng sai” với “chỉ paraphrase”; không đổi oracle/output/primary status/gate.

Vì vậy có thể nói **candidate vận hành này thất bại và diagnosis tự nó đã tạo claim sai**, nhưng chưa thể nói mọi thiết kế concrete-witness đều vô ích. Raw-core có tín hiệu tốt hơn vài ca, song witness/numerics không giữ được lợi ích đó. Không chọn candidate vì ít accusation, schema pass, hay metric đã cứu bằng sửa parser hậu kiểm. Chưa có cơ sở train từ findings chưa được reviewer xác nhận hoặc dự đoán leaderboard>0,5.

## Handoff, test và tái hiện

Private ignored root: **`outputs/task3/witness-behavior-20261022/`**. Archive **`review-bundle.tar.gz`**, sidecar **`review-bundle.tar.gz.sha256`**, manifest **`MANIFEST.sha256`**. Không đưa rootfs/binary/jail vào archive; giữ source, toolchain hashes, compile diagnostics và actual traces để review. Mọi payload/raw/testcase/model witness/expected/actual chỉ nằm private.

|Nội dung|File trong private root|
|---|---|
|Pre-model freeze và split|`pre-inference-freeze.json`, `frozen-selection.private.json`, `selection-rule.json`|
|Nguồn train,24 source pairs, mutation/domain/oracle cases|`authored-pairs.private.json`, `dedup.private.json`|
|Actual compiler/runtime trước inference, mọi pair/test|`pair-execution.private.json`|
|Mọi R15 ID/output/raw/trace|`R15/predictions.json`, `R15/attempts.jsonl`, `R15/traces.json`, `R15/run.json`|
|Mọi diagnosis ID/output/error/raw|`diagnosis/results.private.json`, `diagnosis/attempts.jsonl`|
|Bảng pair đầy đủ đề/code/expected/actual/prediction/review|`paired-ledger-reviewed.private.json`, `paired-members.private.csv`|
|Primary và raw-first numerical checks|`witness-scores.private.json`, `schema-audit.private.json`|
|Review gốc, addendum, authority|`semantic-review.private.json`, `review-freeze.json`, `review-addendum.private.json`|
|Lịch sử4 ca và annotation audit riêng|`historical-investigation.private.json`, `annotation-audit.private.json`|
|Mọi metric/split/mechanism/time/token|`metrics.json`|
|Sandbox/security/resource/toolchain|`security-enforcement.json`, `resource-enforcement.json`, `toolchain-provenance.json`, `integration-tests-green.log`|
|Config/model/dependencies/code snapshots|`resolved-config.json`, `runtime-before.json`, `run.json`, `implementation/`|
|Preservation/staging/commit/status/test|`verification.json`, `final-handoff.json`|

**171 focused regression tests passed**, gồm actual confinement integration probes và regression của R15/requirement-evidence. Log EXDEV ban đầu và các red→green tests được giữ; không gọi toàn bộ project suite đã chạy. Code reviewer độc lập chỉ review phạm vi code được giao; source/oracle/semantic verdict và bundle được tác giả audit, không gọi là human hoặc independent semantic review.

Rà soát mã hậu kiểm đã sửa scorer khi `stdout` sai kiểu; thêm kiểm ASCII/whitespace theo C locale trước oracle/execution, vì mathematical helper đã freeze có thể nhận Unicode digit qua Python. Đây là kiểm miền **sau inference**, không thêm guard vào candidate hay cứu output. Replay cả49 quan sát primary/raw-first trên actual đã lưu cho kết quả đúng/sai không đổi; không chạy model lại. Báo cáo nay áp addendum từ review gốc đã seal, kiểm parent hash, đủ48 ID/role/family và split6/18, tính xác nhận baseline/mutant từ execution thay vì hằng số, và không thưởng clean trên witness có divergence. Frozen source/oracle/prompt/config không đổi; mọi correction và test có trong bundle.

Lệnh không gọi model, từ repository:

```bash
.venv-task3/bin/python scripts/task3_witness_infer.py --verify-only
.venv-task3/bin/python scripts/task3_witness_report.py
TASK3_CPP_SANDBOX_ROOT=/workspace/llm-final-project/outputs/task3/witness-behavior-20261022/sandbox-template .venv-task3/bin/python -m pytest tests/test_task3_cpp_sandbox.py tests/test_task3_witness_oracles.py tests/test_task3_witness_diagnosis.py tests/test_task3_witness_scoring.py tests/test_task3_witness_report.py tests/test_task3_requirement_evidence.py tests/test_task3_requirement_report.py tests/test_task3_round15.py tests/test_task3_round15_runner.py tests/test_task3_round15_disclosure.py tests/test_task3_round15_selection.py tests/test_task3_feedback_prompt.py tests/test_task3_feedback_prompt_report.py tests/test_task3_level2_prompt.py -q
.venv-task3/bin/python outputs/task3/witness-behavior-20261022/audit.private.py
```

Lệnh inference đã chạy sau freeze: `.venv-task3/bin/python scripts/task3_witness_infer.py`; CLI cố ý không chạy đè completed study. Các script author/verify/freeze/probe, inputs, prompts, packages và code snapshot có trong bundle; raw source không commit. Sandbox root cần được dựng từ trusted local GCC13 trước các executable tests nếu chuyển máy. Không xóa marker hay chọn lại response để tái chạy. Reviewer nên kiểm tra các cặp có actual≠model prediction, cặp raw-core tốt nhưng witness sai, hai audit annotation và các context-disputes trước khi quyết định một protocol khác.
