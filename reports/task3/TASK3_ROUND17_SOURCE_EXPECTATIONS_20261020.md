# Round17 source expectations — trước khi đọc bất kỳ output Round17 nào

Assistant-reviewed, not human-verified. Source/đề/Level đọc đủ24. Không dùng gold feedback. Gold v2 có nhiễu: MAXDIFF-0005, COUNTEVEN-0010, MAXDIFF-0004 mang[] nhưng P2/P4 chưa làm; style/TODO không chứng minh sai thuật toán. Tất cả verdict theo source, không theo annotation.

| ID (SYN-) | Level | Source expectation |
|---|---:|---|
| BASE2-0004 |1|x1 dựng binary đúng cho n int hợp lệ; TODO/debug nằm comment. Không khen đã test hết hay bịa lỗi style mandatory.|
| COUNTEVEN-0001 |1|vector đọc cặp, P2 đếm chẵn, P3 min b khi n>0, P4 gọi P2 đúng. Main/debug comments không active; n+1 allocation không tự là lỗi.|
| DISTINCT-0005 |1|`if (n == 1) return 0;` sai: một phần tử phải có1 distinct. Chỉ hint L1, taxonomy vẫn độc lập.|
| MAXDIFF-0005 |1|P2 `return 0;`, P4 body rỗng không in tổng.[] v2 không phủ nhận lỗi này. Không praise bài đúng.|
| BASE2-0003 |2|n0 in thêm `cout << " ";`, binary algorithm đúng. Không biết exact-output checker; observation đúng, impact lỗi chưa chắc. Không hướng sửa L2.|
| COUNTEVEN-0010 |2|P2 return0 thay đếmchẵn, P4 rỗng. P3 khởi tạo kq3=dem[0].b rồi so đúng; không yêu cầu phải gọiP2 hoặc dùngglobaltong.|
| DISTINCT-0006 |2|x1 đọc đủ n phần tử, x3 kiểm tra prefix để count distinct đúng. TODO/debug comments không chạy, tênx1/x2 không bị đề cấm. Array1000 là limitation nếu n>1000, không mặc định chưa khởi tạo.|
| FIB-0009 |2|`for (int i = 2; i <= 5; i++)` khiến n>1 luôn trảF5=5, sai n2→1. Không phải thiếu khởi tạo a/b/c.|
| FIB-0015 |2|`long long truoc = 0, sau = 1` thiếu; trướcfor. Diagnostic expected comma or semicolon beforefor, i undeclared là cascade. Chẩn đoán không đưa bước sửa.|
| PALIN-0007 |2|`isPalin(n + 1)` kiểm tra sai số; truebranch inTRUE khácTrue. tmp=n và rev=0 đã khởi tạo. Không đề xuất đổi call/output ở L2.|
| PERFECT-0005 |2|Cộng ước i=1..n-1, guardn>1 đúng semantics 1..1e8. O(n) có thể chậm nhưng không có time limit; không bịa cầnbao gồm n hoặc thiếu1.|
| SUMEVEN-0005 |2|n1 luôn0 trái singleeven (2→0 thay2). Khác oddsingle0 là đúng. s=0 đã khởi tạo, các phần tử đã đọc.|
| BASE2-0010 |3|main chỉreturn0, helperdoiNhiPhan đúng nhưng chưa đọc/gọi/in. Hướng sửa đọc n,gọi helper,in kếtquả cụ thể không fullsolution.|
| MAXDIFF-0004 |3|P2 return0; P4rỗng. Cần tínhsum a-b trên đủrecords rồi in. P3max đúng n>0, P1fixed100 là limitation độc lập.|
| MINA-0015-L3 |3|P1 đếmfilename xongclosefin, fin2 mởdata.csv thayfilename. Hướng sửa fin2.open(filename). Không nói fin2 chưa mở hoặc n chưa gán (n=soDong trướcallocation).|
| PALIN-0003 |3|Chỉ whitespace ở n0; reverse semantics đúng cho miền không overflow. Hướng bỏ coutspace cụ thể, impactcheckerchưađượccho.|
| PERFECT-0003 |3|Dem pairs divisors đúng, n<2false; main in thêm whitespace. Không đổi sqrtbound hoặc điều kiệnprimeperfect. Formatting impact chưa xác minh.|
| PROD-0005 |3|P3 condition `arr[i + 1].a * arr[i].b > kq3` trộnrecords, cuối có thể đọc arr[n] chưa gán; assignmentarr[i].a*arr[i].b đúng. Đổi conditiona vềarr[i].a; fixed500 không được gọi luônvượtallocation khi n<500.|
| SUMEVEN-0010 |3|Loop tổng `for (int k = 1; k < n; k++)` bỏa0. Đổi bắt đầu0, giữ điều kiệnchẵn. ninputloopđọcđủ và i tăngđúng.|
| SUMPAIR-0018-L4 |3|Levelthật3 dùID-L4. P3r=0 vài1 bỏa0, sai toànâm/maxởđầu. Sửa r=a0 vàquét1..n-1 hoặc khởi tạo âm∞/quétđủ; không dùng r=1 hoặc chỉđổi<=n.|
| MINA-0002-L4 |4|P2 i<n-1 bỏa cuối; đổi i<n. Các phần tử đãcopy từvector nên không missinginitialization.|
| PROD-0019-L3 |4|Levelthật4 dùID-L3. P3 `for (int i = 1; i < n; )` thiếuincrement, loopkhôngkếtthúc n>1. Patch i++ giữmax.|
| REVSTR-0008 |4|`tong = tong + s[dem + 1];` đọcindexsize đầu, bỏindex0. C++11 s[size] readNUL hợp lệ, không tựđồngnghĩa memoryOOB/UB. InNULprefix và thiếu ký tự đầu. Patchs[dem].|
| SUMPAIR-0016-L3 |4|Levelthật4, P1ifstreamin(data.csv) bỏfilename. Đổi dùngfilename; P2/3/4 đúng trong miềnfilevalid capacity1000.|

Confirmed semantic defect denominator: L2 5/8 (COUNTEVEN0010,FIB0009,FIB0015,PALIN0007,SUMEVEN0005); formatting-only BASE2 excluded and DISTINCT/PERFECT không códefectconfirmed ngoài capacity/performance condition. L3 6/8: BASE2,MAXDIFF,MINA,PROD,SUMEVEN,SUMPAIR; hai whitespace-only PALIN/PERFECT báo riêng. Không đổi denominator để theo output.

L2 useful strict: location+correct cause/consequence, không thêmfalseclaim hoặc repair. L3 useful strict: đúngcause+direction cụ thể khảthi, không sửa sai chỗ/gâybugmới; không chỉkhuyênkiểmtralại. Raw malformed vẫn review. L1 khônglocation/cause/identifier/repair, praise cầnsource. So sánh first raw rồifinal; không cho điểm style nếu sai. Source false counted theo sốrecords cóít nhất1 claimcontradicted; supported vàfalse cóthểđồngthời, unassessed khôngđếmfalse.

Contamination review: câu counterexample từ POWER/COUNTUPPER, uppercase/vowel/factorial/prime/secondmax/digitsum identifiers/task/repair bị mang sangquery; generic n/main không tựlàcontamination. Không dùng cue này đểrejectresponse.

Bank review: tám source khác nhau/támfamily; từngcode compilerC++11pass, positive cócounterexample, clean cóinvariant/domain rõ trong freeze. MAXARR/SECONDMAX cùng chủđềextrema nhưng khácsource/problemfamily vàkhôngrelevelcode. Không tuyênbố8 thuậttoán hoàn toàn khôngliênquan hoặc thửnhiềubank. Không sửa bank sauoutputs. Nếu sourceaccuracykhôngcảithiện, dừng prompt trials.
