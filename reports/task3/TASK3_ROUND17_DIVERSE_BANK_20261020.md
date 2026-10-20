# Task 3 Round 17 — một lượt one/few-shot với bank đa dạng, 20/10/2026

**Không có cải thiện độ đúng nguồn đủ rõ để chọn prompt mới. Dừng thử prompt sau lượt này; giữ Round15 zero-shot làm control.** One-shot có nhiều claim kỹ thuật sai hơn control (final8 so7 bài), Level2 useful giảm3/5→1/5, Level3 giữ1/6. Few-shot có hai repair Level3 tốt nhưng11 bài final có claim sai và Level2 useful0/5. Không thêm CoT, guard, bank khác, vòng prompt thứ hai hoặc public inference.

Đã chạy đúng một thí nghiệm A/B/C sau khi khóa bank/development/source expectations. Cả ba nhánh cùng24 input, model revision, precision/decoding/compiler; một model load. R15 giữ nguyên prompt/config/controller, không thay control. B/C giữ nguyên core prompt Round16 và schema-only runner, chỉ dùng bank mới. Retry có sẵn của control được giữ nguyên, không thêm guard; B/C không retry nội dung và lần này không cần schema retry. Không push/leaderboard.

## Dữ liệu v2 và development mới

ZIP v2 SHA-256 `3581498f3db9b55e8bef911609b7829d1928805e66d2956d36a2084b3ca190d0`; annotation `task3_feedback.json` SHA-256 `9b817d29a2eefab5f4767416b273484695f9746c7e9acd25d4ac2cd1d25672ba`. V2 taxonomy được gắn **trước mọi phân tầng/chọn ID và tính F1**, không dùng nhãn v1 để chọn development. Không dùng teacher feedback v2 làm reference vì annotation feedback không bảo đảm đúng source.

Eligibility vẫn là fixed synthetic-train membership495 của repo, SHA-256 `27a00fddb3bf17b0ee6af7ebaac14ffdf3deb6bdc98ebc57233d6cf7aac789e4`. Không giải nén đè/preprocess lại splits; đọc code/Level từ train cố định và kiểm tra byte khớp v2 archive trên toàn bộ495 record, sau đó thay gold bằng taxonomy v2 và bỏ gold feedback. Như vậy membership/source provenance có nguồn prepared cũ, còn **mọi taxonomy dùng trong Round17 đều v2**. Source expectations không lấy annotation làm chứng cứ.

24 ID train-only mới, quotaLevel1/2/3/4 **4/8/8/4**. Loại46 candidate trùng R16 theo ID, group, exact hoặc identifier-renamed code; giữ tất cả24 ID sau selection, không chọn lại theo outputs. Dùng12 task family cũ, không trùng family bank. Bank được kiểm tra cách ly với toàn bộ239 record của12 family, không chỉ24. R13 từng xem corpus, các family development từng dùng R15/16; **không gọi benchmark mù hoặc family chưa từng thấy**. Mới là ID/group/code identity so với R16, không phải toàn bộ bài toán mới.

Coverage v2: biên dịch1, nhập/xuất4, logic2, vòng lặp3, mảng/chuỗi2, hàm2, edge case2, hard-code3, style3; **“Lỗi thuật toán” support0**, không chọn thêm ID để bù. Macro-F1 cố định trên10 nhóm chính thức, zero_division0, không bỏ nhóm thiếu support.

Freeze SHA-256 `54102876e6f6598c3aad39ea95526330abfd6e7ef3fdfbb1527d489c4e97df5b`; input SHA-256 `65ef5dc534f6998cf096b5c09dbbb1917ecf65605c695f366e9190489c4dc638`. [Freeze metadata](TASK3_ROUND17_FREEZE_20261020.json) chứa toàn bộ selection policy, ID/hash, configs và protected prior hashes. [Source expectations trước inference](TASK3_ROUND17_SOURCE_EXPECTATIONS_20261020.md) đã được hash-bind vào run manifest trước model loading; đủ24 source/đề/diagnostic đã được đọc trước outputs.

## Bank: tám source, tám family, không re-level cùng code

Bank SHA-256 `b54ee57e2352bc84e192a7b17c3ab49ca1dbc72b81952ad3ccf91a2b298e9c3a`. Mỗi mục dùng một code giả đầy đủ khác nhau, một family train riêng và **chỉ một Level**. Parent chọn bằng fixed family + ID nhỏ nhất trong eligible train, không xét parent/query gold hay feedback. Feedback do assistant biên soạn từ đề và source; provenance **assistant-reviewed, not human-verified**. Tám code C++11 syntax-pass, positive có counterexample và clean có domain/invariant review, không coi compiler pass là proof clean.

| Level | Family / parent train | Ví dụ | Source review chính |
|---|---|---|---|
|1|COUNTVOWEL / SYN-COUNTVOWEL-0002|Lỗi: chỉ đếm a|Input e ra0 thay1; feedback chỉ gợi ý nhẹ|
|1|FACT / SYN-FACT-0002|Clean factorial|0!/1! đúng; tích lũy tới20!, vừa unsigned64|
|2|POWER / SYN-POWER-0002|Lỗi: a*b thay a^b|2,3 ra6 thay8; chẩn đoán, không hướng sửa|
|2|SECONDMAX / SYN-SECONDMAX-0002|Clean streaming second-max|Dãy distinct n>=2, invariant hai giá trị lớn nhất, xử lý số âm|
|3|COUNTUPPER / SYN-COUNTUPPER-0002|Lỗi: đếm lowercase|aBC ra1 thay2; đổi predicate sang A..Z|
|3|MAXARR / SYN-MAXARR-0002|Clean streaming max|Dãy không rỗng, best được input trước dùng, invariant max prefix|
|4|DIGITSUM / SYN-DIGITSUM-0003|Lỗi: nhân chữ số, init1|12 ra2 thay3,0 ra1 thay0; reference có hàm sửa sum0/+=|
|4|PRIME / SYN-PRIME-0003|Clean primality|x<2false; divisor<=x/divisor đủ căn và tránh bình phương tràn|

Inference chọn ví dụ **chỉ theo requested Level**: B lấy mục lỗi đầu tiên cố định, C lấy cả mục lỗi+clean của Level ấy. Không nearest retrieval theo code/label, không dùng gold/query feedback. Bank/source selection không bị đổi sau khi xem kết quả. Query luôn đủ đề/prototypes/grading policy/source/compiler và Level, không có gold/test report/teacher feedback.

Giới hạn còn lại: chỉ thử **một bank**, không khảo sát nhiều cách chọn ví dụ; COUNTVOWEL/COUNTUPPER cùng motif duyệt ký tự/đếm và MAXARR/SECONDMAX cùng chủ đề extrema nhưng khác source/requirements/family, không tuyên bố tám thuật toán hoàn toàn không liên quan. Bốn reference có lỗi đều được assistant gán “Lỗi logic”, nên diversity taxonomy của reference dương còn hạn chế; không sửa lại nhãn/prompt sau kết quả. Kết quả kiểm tra tám source/family độc lập, không phải khẳng định mọi dạng diversity đã được thử. Không tách được tác động số shot khỏi nội dung clean example thêm vào.

## Điều kiện chạy và kết quả

Qwen/Qwen2.5-Coder-7B-Instruct revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`, NF4 double-quant compute BF16 trên CUDA; runtime xác nhận đúng precision/revision và không offload. Cùng seed42, greedy, context16384, cap1024/L4 1536, soft max_time45s và tối đa3 attempts có sẵn. C++11 syntax-only, không chạy chương trình sinh viên. Preflight worst retry: tối đa1805 input tokens, không drop ví dụ/truncate query. Không tải/thay checkpoint.

| Metric trên cùng24 ID | A R15 control | B one-shot | C few-shot |
|---|---:|---:|---:|
|Final JSON hoàn tất|24/24|24/24|24/24|
|First raw JSON hợp lệ|24/24|24/24|24/24|
|Schema-failed attempts / unresolved IDs|0 / 0|0 / 0|0 / 0|
|Attempts, gồm retry|28|24|24|
|Feedback fallback|0|0|0|
|Taxonomy v2 micro-F1|0,2000|0,1304|0,0909|
|Taxonomy v2 macro-F1, đủ10 nhóm|0,1598|0,1182|0,0767|
|Exact set|6/24|2/24|3/24|
|Compiler TP / FP / FN|1 / 0 / 0|1 / 0 / 0|1 / 1 / 0|
|Output tokens mọi attempt|1988|1683|1374|
|First raw có claim kỹ thuật bị source bác bỏ|6/24|8/24|11/24|
|Có claim bị source bác bỏ ở bất kỳ raw attempt|8/24|8/24|11/24|
|Final có claim kỹ thuật bị source bác bỏ|7/24|8/24|11/24|
|False-clean assurance trên bài có lỗi xác nhận, đếm riêng|2|0|0|
|Hợp final falseclaim hoặc false-clean|9/24|8/24|11/24|
|L1 disclosure first / final|2/4 / 1/4|2/4 / 2/4|2/4 / 2/4|
|L2 concrete repair leak|1/8|3/8|1/8|
|L2 strict useful, confirmed-defect denominator|3/5|1/5|0/5|
|L3 strict cause+feasible direction, confirmed-defect denominator|1/6|1/6|2/6|

Manual unit là **record có ít nhất một material contradiction**, không phải atomic claim precision. Raw và final được review riêng, kể cả cả bốn control retry; raw→final A chỉ thay qua model retry, B/C không thay nội dung. Disagreement với noisy taxonomy v2 không tự là source false claim; false compiler classification được tính vì có diagnostic thật. Generic “không có lỗi rõ ràng” trên defect đã xác nhận được ghi riêng false-clean, tránh coi bỏ sót là bịa technical cause. Supported và false có thể đồng thời tồn tại. [Ledger72 judgement](TASK3_ROUND17_MANUAL_REVIEW_20261020.json) bind exact raw/final hashes; [results JSON](TASK3_ROUND17_RESULTS_20261020.json) có per-label F1/TP/FP/FN và danh sách false IDs.

Nếu gộp false-clean, B có8 bài sai/assurance so với A9. **Không coi chênh một record này là source improvement rõ:** B tăng technical false claims first6→8/final7→8, giảm mạnh L2 useful3→1 và không tăng L3. B thực sự có ba code sửa Level4 hữu ích (MINA, PROD, REVSTR), đã giữ trong bảng bên dưới; lợi ích cục bộ ấy không bù lỗi ở hai Level ưu tiên. C tăng một repair Level3 nhưng làm tăng false claims và sai L2 nhiều hơn. Không chọn theo F1/độ dài/fallback hoặc một metric thuận lợi.

Denominator source khóa trước inference: L2 có5 actual semantic/compile defects (COUNTEVEN0010,FIB0009,FIB0015,PALIN0007,SUMEVEN0005), một whitespace-only chưa rõ checker và hai bài DISTINCT/PERFECT chưa xác nhận lỗi semantics. L3 có6 defects; PALIN/PERFECT chỉ whitespace, báo riêng. Gold[] v2 ở COUNTEVEN/MAXDIFF không chứng minh source đúng; style gold ở DISTINCT/PERFECT không bắt model bịa cause/repair.

Boundary sensitivity: L2 “Cần sửa vòng lặp” không cho edit/bound cụ thể được coi advice chung, không concrete repair; nếu cấm cả câu đó, A useful3→2, vẫn không đổi quyết định. L3 task-restatement “Cần sửa để tính tổng a-b” không thành concrete direction. C SUMPAIR có sửa bỏa0 nhưng r=0 vẫn sai dãy toàn âm: ghi partial, không strict pass. Nếu coi B/C phát biểu “Fibonacci cho n<=5” là không đầy đủ thay vì contradicted, số false final B/C giảm một, vẫn không có improvement rõ ở hai Level ưu tiên. Không dùng keyword gate cho các judgement này.

## Bảng từng ID

Tên rút gọn trong cột ID có tiền tố `SYN-`. “Sai” nói về nội dung source, không chỉ taxonomy; verdict final, khi raw khác có ghi riêng. Evidence là đoạn active source/diagnostic, không lấy teacher feedback.

|ID|Level|Evidence/expectation|A control|B one-shot|C few-shot|
|---|---:|---|---|---|---|
|BASE2-0004|1|x1 dựng binary; TODO comment|Không thấy lỗi rõ, hợp source|Negative generic, thiếu căn cứ|Khen đúng miền int hợp lệ|
|COUNTEVEN-0001|1|P1vector, P2chẵn/P3min/P4call đúng|Final hợp; retry2 bịa data.csv từ comment|Nêu file-fail cause, vượtL1|Khen có căn cứ miền hợp lệ|
|DISTINCT-0005|1|`if (n == 1) return 0;` sai|False-clean, bỏ lỗi|Hint đúng nhưng lộ tong|Nêu sai count+lộ tong|
|MAXDIFF-0005|1|P2return0, P4rỗng, P3max đúng|First đúng nhưng lộ; final bịa thêm thiếu max|Hint nhẹ đúng|Lộ P2/P4|
|BASE2-0003|2|n0 `cout << " ";`|Observation đúng; impact chưa rõ|Observation đúng; impact chưa rõ|Observation đúng; impact chưa rõ|
|COUNTEVEN-0010|2|P2return0, P4rỗng; P3độc lập|**Useful** chẩn đoán đúng|Đúngcause, nhưng advice implement đếm|Sai: nói P2 khiến P3/P4 hỏng|
|DISTINCT-0006|2|x3 kiểm tra prefix dưới `i<k` đúng|Sai: tăng khi new lại bị gọi là lỗi|Sai: bịa chưa kiểmtra duplicate|Sai: bịa cận inclusive k|
|FIB-0009|2|Loop `i<=5` bất kể n>1|**Useful** fixedF5 thayF(n)|Sai/phạm vi thiếu: n2 đãra5|Cùng sai phạm vi n<=5|
|FIB-0015|2|`truoc=0, sau=1` thiếu`;`; cascadei|Sai dấuphẩy/i chưa khai báo|Cùng sai rootcause|Cùng sai rootcause|
|PALIN-0007|2|main `isPalin(n+1)`, outputTRUE|**Useful** cause+location đúng|**Useful** cause+location đúng|Cause đúng nhưng gán nhầm vịtrí helper|
|PERFECT-0005|2|Sumproperdivisors và `n>1` đúng|Nhận xét semantics có căn cứ|Advice dời guard thừa, vượtL2|Sai: khẳng định1 là perfect|
|SUMEVEN-0005|2|n1return0 sai singleeven|False-clean, bỏ lỗi|Cause đúng nhưng chỉ sửa vượtL2|Sai: n1 bị nói không có phần tử|
|BASE2-0010|3|main chỉreturn0, helper đúng|Nhập n: partial, thiếu call/in|Sai: bịa nmain dùng chưa init|Stdoutempty đúng, thiếu direction|
|MAXDIFF-0004|3|P2return0, P4rỗng|Đúngcause, chưa hướng sửa|Đúngcause, advicegeneric|Đúngcause, taskrestatement|
|MINA-0015-L3|3|`fin2.open("data.csv")` thayfilename|Sai “ma.csv khai báo trongP1”; sửa hardcode khác|Sai: bịa ma.csv ởP4|Sai: bịa filename ởP4|
|PALIN-0003|3|n0 in space rồiTrue; elseFalsecó|Bỏ whitespace khảthi, impact chưa rõ|Sai: nói in space thayTrue, thiếuelse|Repair dời if không xóa coutspace|
|PERFECT-0003|3|Pairs divisors từ2/s1 đúng; space|Observation đúng, thiếu direction|Sai: nhiềuước làm s quá lớn|Sai/thừa: đòi bắtđầu2 khi loop đã2/s1đúng|
|PROD-0005|3|Condition `arr[i+1].a*arr[i].b`|Sai: luôn vượt allocation500|Checkbounds mơ hồ, thiếu patch|**Useful:** đổi condition về i/i|
|SUMEVEN-0010|3|Loop tổng bắtđầu1, bỏa0|**Useful:** start0|**Useful:** start0|**Useful:** start0|
|SUMPAIR-0018-L4|3|P3r0/i1 sai với âm/firstmax|Chẩn đoán đúng, thiếu sửa|Sai requirement: maxa+b|Start0 partial, r0 vẫn sai âm|
|MINA-0002-L4|4|P2i<n-1 bỏcuối|Sai: đòi lưu result trướccoutcall|**Patch đúng:** initarr0, i1..n-1|Chẩn đoán đúng, chưa patch|
|PROD-0019-L3|4|P3for không increment|Concern capacity100 đúng có điều kiện; bỏ loopbug|**Patch đúng:** thêmi++|Compilerlabel false; bỏ loopbug|
|REVSTR-0008|4|`s[dem+1]` đọcNUL đầu, bỏs0|Sai: nóidem0 index1 vượtchuỗi|**Patch đúng:** reverse len-1..0|**Patch đúng:** dùngs[dem]|
|SUMPAIR-0016-L3|4|P1hardcodeddata.csv thayfilename|Observation đúng|Observation đúng|Observation đúng; advice chưa cụ thể|

Không suy Level từ suffix ID: SUMPAIR-0018-L4 thật Level3; các ID PROD/SUMPAIR đuôiL3 cuối bảng thật Level4. Đánh giá theo requested Level thật trong frozen input.

C++11 `s[size]` đọc NUL sentinel được phép; B/C nói “ngoài phạm vi” không kèm explicit UB được ghi thuật ngữ mơ hồ khi direction đúng, không tự nâng thành material memory-safety claim sai. A nói cụ thể ởdem0 thìindex1 vượtchuỗi là sai. Allocation500 còn chỗ nhưng arr[n] chưa được gán không đồng nghĩa luôn vượtallocation.

## Raw/final và bằng chứng quan trọng

- A COUNTEVEN-0001: first raw khuyên thêm main (vượtL1); retry2 nói active code mởdata.csv nhưng literal đó chỉ nằm trong main comment; final generic không lặp lại claim ấy. Đây là model retry sai, không phải postprocessor tự tạo lỗi.
- A MAXDIFF-0005: first raw chỉ đúng P2/P4 chưa làm, qua disclosure retries final lại đòi cả logic max a-b dù P3 đã có. Ít disclosure hơn không chứng minh đúng nguồn hơn.
- B/C COUNTEVEN-0010: A chỉ đúng P2return0; B thêm “logic đếm” vượtL2; C bịa dependency làm P3 sai dù P3 không gọi P2. B/C raw=final, không guard thay nội dung.
- C PERFECT-0005: raw/final giữ nguyên claim “1 là số hoàn hảo”, trái định nghĩa sum proper divisors. Không cần gold để bác bỏ.
- C PROD-0005 và cả ba SUMEVEN-0010: raw/final giữ nguyên hai hướng sửa Level3 có căn cứ. Không bỏ lợi ích cục bộ vì kết luận tổng thể không winner.
- B SUMPAIR-0018-L4: đòi maxa+b trái yêu cầu maxa. C chỉ start0 nhưng với a=[-5,-2], r vẫn0 thay-2; syntax-pass không chứng minh sửa đủ.

Sáu patch cụ thể được syntax-check C++11, tất cả pass; gồm SUMPAIR partial vẫn sai logic. Không chạy student executable. Chi tiết ignored `outputs/task3/round17/review/repair-syntax.json`. Không thêm source-extractor, factual gate hoặc auto-repair. Không có ca chắc chắn mang identifier/task của ví dụ sang query; không coi điều đó chứng minh không có ảnh hưởng ví dụ. Suy luận causal về nội dung bank vẫn hạn chế ở một run.

## Artifact, kiểm tra và tái hiện

- Raw trước parse, mọi retry/reason, rendered prompt/token counts, final/unresolved: `outputs/task3/round17/{control,one_shot,few_shot}/` và `review/raw-final.private.json`.
- Bank đầy đủ/source/query/compiler/gold v2: ignored `train-examples.json`, `development.private.json`, `inputs.private.json`.
- Code opt-in: `round17.py`, `round17_bank.py`, `scripts/task3_round17.py`, hai configr17. R15/R16 code/config/output giữ nguyên.
- **631 passed, 4 skipped** trong toàn bộ Task3. Test mới pin diversity không lặp family/source và selection loại identity R16. Reviewer độc lập không thấy lỗi critical/important, xác minh9 test R16/R17, không xem outputs để tune bank. Full-repo Task1 environment/test limitations đã ghi ở Round16, không tuyên bố toàn repo green.
- Kiểm tra69 protected artifact hashes trước/sau: R16 bank/input/raw/final/code/config và public candidates R14/R15 không đổi. Không public inference hoặc leaderboard.

Tái hiện offline summary trên đúng outputs đã review:

```bash
.venv-task3/bin/python scripts/task3_round17_review.py
.venv-task3/bin/python -m pytest tests/test_task3*.py -q
```

Hai bước thực thi thí nghiệm đã dùng là `scripts/task3_round17.py --prepare` rồi `scripts/task3_round17.py`. Prepare từ chối overwrite freeze; run resume không phát sinh generation cho ID đã hoàn tất. **Không chạy một run mới để tìm kết quả tốt hơn**: kết thúc prompt trials theo điều kiện người dùng. Chỉ lần này có model inference; summary/report là offline, không gọi model. Working tree code/config/bank metadata/report được commit, raw/source sinh viên/model outputs vẫn ignored.

[Verification metadata](TASK3_ROUND17_VERIFICATION_20261020.json) ghi các kiểm tra hash, isolation, v2 metadata, actual NF4/BF16 runtime, paired metrics và test cuối.
