# Task 3 SFT v3 — QLoRA, 26/10/2026

Đã hoàn thành **2 epoch, 480 optimizer steps**, scheduler 480 steps, 1920 train forwards. Checkpoint được khóa từ dev: **step 480** (`/workspace/llm-final-project-arm-d-plus/outputs/task3/sft-v3-qlora-20261026-run1/main/checkpoint-480`). **Không đạt điều kiện promotion**; đây là candidate chẩn đoán theo fallback đã đóng băng, vẫn đánh giá observed-final.

Trên dev, level end-to-end tăng nhưng số bỏ sót lỗi cộng invalid tăng: có đánh đổi tính đúng nhiệm vụ lấy tuân thủ bề mặt; ưu tiên chẩn đoán và khả năng phát hiện lỗi. Oracle fidelity+Level tăng trong khi số chẩn đoán end-to-end có căn cứ không tăng: chẩn đoán vẫn là điểm cần ưu tiên, dù oracle không tạo ra phân rã nhân quả thuần túy. Trên dev, cả hai probe vẫn dưới mục tiêu Level 95%; học diễn đạt theo Level cũng chưa được giải quyết. Cần đọc riêng các Level còn yếu, đồng thời giữ các điều kiện bảo toàn chẩn đoán.

Observed-final, v2 → selected v3: báo lỗi giả clean **72 → 9/80**; faulty miss cộng invalid **5 → 52/80**; chẩn đoán faulty có căn cứ **20 → 7/80**; faulty L3 repair **0 → 0/20**. Đây là hậu kiểm, không thay selection.

Official-Level của selected v3 trên final: **153/160 (95.6%)**; L1/L2/L3/L4 lần lượt 40/40 (100.0%) / 38/40 (95.0%) / 39/40 (97.5%) / 36/40 (90.0%). Đạt 95% tổng. Chưa đạt 95% ở mọi Level.

Joint final tăng 24 → 61/160, trong đó clean tăng 7 → 54/80 nhưng faulty giảm 17 → 7/80. Mức tăng joint tổng không đồng nghĩa chẩn đoán lỗi tốt hơn.

Điểm A **0.3834**, SFT v2 **0.3567**, B **0.3247** là số lịch sử do người dùng báo, không phải phép đo mới. Không chạy public inference/submission và không suy điểm public từ báo cáo này.

## Dữ liệu, hợp đồng và giới hạn diễn giải

Train: 240 nguồn / 960 targets (95 clean, 145 faulty); thay 35 targets, quarantine 0 nguồn. Giữ nguyên source/spec/split và gold lịch sử. Dev: 20 nguồn × 4 Levels = 80 targets/probe/state; final: 40 nguồn × 4 Levels = 160 targets/state. 640 dev + 480 final = 1120 primary outputs.

Dev dùng chọn checkpoint; observed-final là bộ synthetic đã từng được xem, chỉ mở nội dung sau khi khóa selection trong lần chạy này. Hai bộ không độc lập hoặc thật sự unseen. Review nguồn/đề bằng agent, ẩn danh trạng thái nơi khả thi; không phải human gold độc lập. Nhiều Levels và trạng thái dùng lại cùng nguồn nên các targets phụ thuộc; không coi 1120 outputs là 1120 chương trình độc lập.

Hợp đồng chính thức (trích nguyên định nghĩa đã đóng băng):

- **Level 1 - Gợi ý nhẹ**: “Chỉ báo có vấn đề / khen ngợi, không chỉ ra vị trí lỗi.” Cấm: “không nêu nguyên nhân cụ thể, không đưa code sửa.”
- **Level 2 - Chẩn đoán**: “Chỉ ra lỗi ở đâu và nguyên nhân là gì.” Cấm: “không đưa cách sửa cụ thể, không đưa code.”
- **Level 3 - Gợi ý sửa**: “Chẩn đoán + gợi ý hướng sửa.” Cấm: “không đưa lời giải hoàn chỉnh.”
- **Level 4 - Lời giải mẫu**: “Được phép đưa code sửa / lời giải mẫu.” Cấm: “—”

L2 được nhiều câu và chẩn đoán chính xác; không yêu cầu nói mơ hồ. L3 được hướng sửa cục bộ cụ thể, không đưa lời giải hoàn chỉnh. L4 được cung cấp code nhưng vắng code không tự động fail. Clean không cần phát minh lỗi/hướng sửa. Wrong hint được chấm riêng khỏi disclosure. Code đã cung cấp mà sai hoặc chưa được giải quyết làm joint fail.

Joint = valid + chẩn đoán/bao phủ/fidelity có căn cứ + đúng Level + tiếng Việt; faulty L2–L4 cần vị trí/điều kiện; faulty L3 cần hướng sửa đúng hữu ích; L4 cần hữu ích; code được cung cấp cần đúng. Supported faulty diagnosis đòi valid, nhãn lỗi không rỗng, diagnosis+coverage+fidelity đều pass. Repair L3 chỉ tính faulty L3 có assessment và hướng sửa pass. Invalid ở mọi mẫu số và các trục invalid là not_evaluable.

## Dev: end-to-end và oracle

### End-to-end

| Trạng thái | Targets/nguồn | Invalid | Level đúng | Joint | Balanced joint | Fidelity+Level |
| --- | --- | --- | --- | --- | --- | --- |
| base-dev | 80/20 | 16 | 47/80 (58.8%) | 15/80 (18.8%) | 20.8% | 15/80 (18.8%) |
| v2-dev | 80/20 | 8 | 54/80 (67.5%) | 20/80 (25.0%) | 20.0% | 22/80 (27.5%) |
| v3-epoch1-dev | 80/20 | 5 | 71/80 (88.8%) | 27/80 (33.8%) | 45.8% | 28/80 (35.0%) |
| v3-epoch2-dev | 80/20 | 4 | 67/80 (83.8%) | 36/80 (45.0%) | 56.7% | 38/80 (47.5%) |

| Trạng thái | Clean báo lỗi giả | Clean invalid | Faulty miss valid | Faulty invalid | Miss + invalid | Chẩn đoán có căn cứ | Faulty L3 repair |
| --- | --- | --- | --- | --- | --- | --- | --- |
| base-dev | 8/20 (40.0%) | 7/20 (35.0%) | 11/60 (18.3%) | 9/60 (15.0%) | 20/60 (33.3%) | 11/60 (18.3%) | 2/15 (13.3%) |
| v2-dev | 16/20 (80.0%) | 2/20 (10.0%) | 1/60 (1.7%) | 6/60 (10.0%) | 7/60 (11.7%) | 22/60 (36.7%) | 1/15 (6.7%) |
| v3-epoch1-dev | 0/20 (0.0%) | 1/20 (5.0%) | 18/60 (30.0%) | 4/60 (6.7%) | 22/60 (36.7%) | 15/60 (25.0%) | 0/15 (0.0%) |
| v3-epoch2-dev | 0/20 (0.0%) | 1/20 (5.0%) | 7/60 (11.7%) | 3/60 (5.0%) | 10/60 (16.7%) | 22/60 (36.7%) | 1/15 (6.7%) |

### Oracle-assisted (chỉ evaluation)

| Trạng thái | Targets/nguồn | Invalid | Level đúng | Joint | Balanced joint | Fidelity+Level |
| --- | --- | --- | --- | --- | --- | --- |
| base-oracle-dev | 80/20 | 0 | 48/80 (60.0%) | 37/80 (46.2%) | 57.5% | 41/80 (51.2%) |
| v2-oracle-dev | 80/20 | 0 | 51/80 (63.8%) | 31/80 (38.8%) | 52.5% | 31/80 (38.8%) |
| v3-epoch1-oracle-dev | 80/20 | 0 | 63/80 (78.8%) | 50/80 (62.5%) | 75.0% | 50/80 (62.5%) |
| v3-epoch2-oracle-dev | 80/20 | 0 | 66/80 (82.5%) | 52/80 (65.0%) | 75.0% | 55/80 (68.8%) |

| Trạng thái | Clean báo lỗi giả | Clean invalid | Faulty miss valid | Faulty invalid | Miss + invalid | Chẩn đoán có căn cứ | Faulty L3 repair |
| --- | --- | --- | --- | --- | --- | --- | --- |
| base-oracle-dev | 0/20 (0.0%) | 0/20 (0.0%) | 0/60 (0.0%) | 0/60 (0.0%) | 0/60 (0.0%) | 45/60 (75.0%) | 9/15 (60.0%) |
| v2-oracle-dev | 0/20 (0.0%) | 0/20 (0.0%) | 0/60 (0.0%) | 0/60 (0.0%) | 0/60 (0.0%) | 33/60 (55.0%) | 7/15 (46.7%) |
| v3-epoch1-oracle-dev | 0/20 (0.0%) | 0/20 (0.0%) | 0/60 (0.0%) | 0/60 (0.0%) | 0/60 (0.0%) | 40/60 (66.7%) | 9/15 (60.0%) |
| v3-epoch2-oracle-dev | 0/20 (0.0%) | 0/20 (0.0%) | 0/60 (0.0%) | 0/60 (0.0%) | 0/60 (0.0%) | 45/60 (75.0%) | 9/15 (60.0%) |

### Level và mục tiêu 95% (mô tả)

| Trạng thái | Tổng | L1 | L2 | L3 | L4 | Đạt ≥95% tổng + mọi Level |
| --- | --- | --- | --- | --- | --- | --- |
| base-dev | 47/80 (58.8%) | 9/20 (45.0%) | 9/20 (45.0%) | 13/20 (65.0%) | 16/20 (80.0%) | Không |
| base-oracle-dev | 48/80 (60.0%) | 1/20 (5.0%) | 8/20 (40.0%) | 19/20 (95.0%) | 20/20 (100.0%) | Không |
| v2-dev | 54/80 (67.5%) | 20/20 (100.0%) | 9/20 (45.0%) | 11/20 (55.0%) | 14/20 (70.0%) | Không |
| v2-oracle-dev | 51/80 (63.8%) | 7/20 (35.0%) | 5/20 (25.0%) | 19/20 (95.0%) | 20/20 (100.0%) | Không |
| v3-epoch1-dev | 71/80 (88.8%) | 20/20 (100.0%) | 17/20 (85.0%) | 19/20 (95.0%) | 15/20 (75.0%) | Không |
| v3-epoch1-oracle-dev | 63/80 (78.8%) | 17/20 (85.0%) | 8/20 (40.0%) | 18/20 (90.0%) | 20/20 (100.0%) | Không |
| v3-epoch2-dev | 67/80 (83.8%) | 20/20 (100.0%) | 13/20 (65.0%) | 18/20 (90.0%) | 16/20 (80.0%) | Không |
| v3-epoch2-oracle-dev | 66/80 (82.5%) | 14/20 (70.0%) | 12/20 (60.0%) | 20/20 (100.0%) | 20/20 (100.0%) | Không |

Mỗi Level dev có 20 targets, chung 20 nguồn; 95% tương ứng ít nhất 19/20 mỗi Level và 76/80 tổng. Đây là đích mô tả, không phải khoảng tin cậy thống kê hay điều kiện promotion duy nhất.

## Selection đã khóa trước observed-final

| Step | Eligible | Điều kiện không đạt | E2E Level | Balanced joint | Oracle fidelity+Level tie-break | Dev loss |
| --- | --- | --- | --- | --- | --- | --- |
| 240 | Không | faulty_misses_with_invalid, supported_faulty_diagnosis, faulty_l3_correct | 71/80 (88.8%) | 45.8% | 50 | 0.712048 |
| 480 | Không | faulty_misses_with_invalid | 67/80 (83.8%) | 56.7% | 55 | 0.685487 |

So v2 cùng prompt, invalid/clean false alarm/faulty miss cộng invalid không được tăng; supported faulty diagnosis và correct faulty-L3 repair không được giảm. Eligible: ưu tiên Level, balanced joint, oracle joint, loss thấp, checkpoint sớm. Không eligible: ưu tiên balanced joint, diagnosis, Level, checkpoint sớm. Không chọn lại bằng kết quả final. `selection.json` và seal/evidence đã kiểm tra.

## Observed-final end-to-end

| Trạng thái | Targets/nguồn | Invalid | Level đúng | Joint | Balanced joint |
| --- | --- | --- | --- | --- | --- |
| base-final | 160/40 | 0 | 127/160 (79.4%) | 28/160 (17.5%) | 17.5% |
| v2-final | 160/40 | 2 | 121/160 (75.6%) | 24/160 (15.0%) | 15.0% |
| v3-selected-final | 160/40 | 4 | 153/160 (95.6%) | 61/160 (38.1%) | 38.1% |

| Trạng thái | Clean báo lỗi giả | Clean invalid | Faulty miss valid | Faulty invalid | Miss + invalid | Chẩn đoán có căn cứ | Faulty L3 repair |
| --- | --- | --- | --- | --- | --- | --- | --- |
| base-final | 56/80 (70.0%) | 0/80 (0.0%) | 23/80 (28.8%) | 0/80 (0.0%) | 23/80 (28.8%) | 8/80 (10.0%) | 2/20 (10.0%) |
| v2-final | 72/80 (90.0%) | 1/80 (1.2%) | 4/80 (5.0%) | 1/80 (1.2%) | 5/80 (6.2%) | 20/80 (25.0%) | 0/20 (0.0%) |
| v3-selected-final | 9/80 (11.2%) | 2/80 (2.5%) | 50/80 (62.5%) | 2/80 (2.5%) | 52/80 (65.0%) | 7/80 (8.8%) | 0/20 (0.0%) |

| Trạng thái | L1 | L2 | L3 | L4 | Đạt ≥95% tổng + mọi Level |
| --- | --- | --- | --- | --- | --- |
| base-final | 34/40 (85.0%) | 32/40 (80.0%) | 21/40 (52.5%) | 40/40 (100.0%) | Không |
| v2-final | 40/40 (100.0%) | 23/40 (57.5%) | 20/40 (50.0%) | 38/40 (95.0%) | Không |
| v3-selected-final | 40/40 (100.0%) | 38/40 (95.0%) | 39/40 (97.5%) | 36/40 (90.0%) | Không |

Mỗi Level final có 40 targets/40 nguồn, nên 95% là 38/40; tổng 152/160. Tất cả kết quả final ở trên là mô tả regression sau selection, không phải một lần chọn mô hình mới.

## Biểu đạt và chẩn đoán: độ lớn thay đổi

Selected v3 so v2 trên dev: E2E Level **+16.2 điểm phần trăm**; oracle fidelity+Level **+30.0 điểm phần trăm**; supported faulty diagnosis **+0 targets**; faulty misses cộng invalid **+3 targets**.

Trên dev, level end-to-end tăng nhưng số bỏ sót lỗi cộng invalid tăng: có đánh đổi tính đúng nhiệm vụ lấy tuân thủ bề mặt; ưu tiên chẩn đoán và khả năng phát hiện lỗi. Oracle fidelity+Level tăng trong khi số chẩn đoán end-to-end có căn cứ không tăng: chẩn đoán vẫn là điểm cần ưu tiên, dù oracle không tạo ra phân rã nhân quả thuần túy. Trên dev, cả hai probe vẫn dưới mục tiêu Level 95%; học diễn đạt theo Level cũng chưa được giải quyết. Cần đọc riêng các Level còn yếu, đồng thời giữ các điều kiện bảo toàn chẩn đoán.

Target và prompt cùng đổi; oracle cung cấp dữ kiện và đổi nhiệm vụ. Không coi chênh lệch hai probe là phân rã nhân quả hoặc dự báo điểm public.

Oracle fidelity+Level (tie-break `oracle_joint`) đòi valid, supported diagnosis/coverage/fidelity, Level, tiếng Việt, vị trí/điều kiện khi cần và code đã cung cấp đúng; không gồm cổng L3 repair/L4 usefulness. Full oracle task joint trong bảng đòi thêm hai cổng đó. Định nghĩa vận hành này được đóng băng trước primary dev output trong `oracle-metric-definition.json`. Oracle được cho findings đúng đã review, end-to-end chỉ nhận đề/source/mode/syntax log/Level. Thành công oracle không được gọi là thành công production. Thí nghiệm này không tự động đổi pipeline production thành hai bước, không tự động v4 hoặc huấn luyện thêm.

## Ví dụ cải thiện và regression có bằng chứng

### dev: v2 → selected v3

**Joint cải thiện**: 22 cặp target. Xếp example_id tăng dần, tối đa ba nguồn khác nhau; ví dụ mô tả, không phải mẫu đại diện thống kê.

- `F23-C-L2` (clean); xem [dev casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/dev-paired-casebook.html#F23-C-L2).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <iostream>
2: #include <string>
3: using namespace std;
4: 
5: int main() {
6: string s;getline(cin,s);bool ok=true;
7: for(int i=0;i<(int)s.size()/2;++i) if(s[i]!=s[s.size()-1-i])ok=false;
8: cout<<(ok?"YES":"NO")<<"\n";
9: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. Source line 6 uses getline and line 7 checks every distinct symmetric pair i<floor(size/2), preserving case and spaces; empty/singleton lines are valid. Existing tests 0..10 pass. The response truthfully assesses this clean source. The alleged incorrect order from traversing half the string is unsupported: symmetric pairs suffice and the actual comparison order is correct. Response under review: {"taxonomy_error": ["Lỗi logic"], "feedback": "Bài kiểm tra đảo chuỗi sai thứ tự của hai phần còn lại khi chỉ duyệt nửa chiều."}. Code evidence status=absent.

> Bài kiểm tra đảo chuỗi sai thứ tự của hai phần còn lại khi chỉ duyệt nửa chiều.

**v3**: status `valid`, joint `pass`; review: Source-grounded agent review, not independent human gold. Source line 6 uses getline and line 7 checks every distinct symmetric pair i<floor(size/2), preserving case and spaces; empty/singleton lines are valid. Existing tests 0..10 pass. The response truthfully assesses this clean source. The assessment and supplied explanation/direction agree with the source mechanism. Disclosure is appropriate at this Level; clean sources require no invented defect/repair, and L4 does not require code. Response under review: {"taxonomy_error": [], "feedback": "Bài làm đáp ứng đúng yêu cầu về kiểm tra chuỗi palindrome trong đề."}. Code evidence status=absent.

> Bài làm đáp ứng đúng yêu cầu về kiểm tra chuỗi palindrome trong đề.

- `F23-D1-L1` (faulty); xem [dev casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/dev-paired-casebook.html#F23-D1-L1).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <iostream>
2: #include <string>
3: using namespace std;
4: 
5: int main() {
6: string s;cin>>s;bool ok=true;
7: for(int i=0;i<(int)s.size()/2;++i) if(s[i]!=s[s.size()-1-i])ok=false;
8: cout<<(ok?"YES":"NO")<<"\n";
9: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. F23-D1 (data/raw/task3-sft-v2/sources/F23-D1.cpp). Faulty status is true, but Lỗi vòng lặp is unsupported: i<size/2 checks all palindrome pairs. The actual defect is formatted input truncating spaces. L1 form itself is compliant.

> Bài làm còn có lỗi cần kiểm tra.

**v3**: status `valid`, joint `pass`; review: Source-grounded agent review, not independent human gold. F23-D1 (data/raw/task3-sft-v2/sources/F23-D1.cpp). A spaced-line input exposes a valid input-handling case defect, so broad edge-case taxonomy is semantically supportable here. The feedback states only faulty status and satisfies L1.

> Bài làm còn có lỗi cần kiểm tra.

- `F29-C-L1` (clean); xem [dev casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/dev-paired-casebook.html#F29-C-L1).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <iostream>
2: #include <map>
3: using namespace std;
4: 
5: int main() {
6: int n;cin>>n;map<int,int> freq;for(int i=0;i<n;++i){int x;cin>>x;++freq[x];}
7: int best=0,count=-1;for(auto p:freq)if(p.second>count){count=p.second;best=p.first;}
8: cout<<best<<"\n";
9: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. F29-C (data/raw/task3-sft-v2/sources/F29-C.cpp). The source has no logic defect under n>=1 and the given tie rule. The L1 status form is compliant, but its positive error label is a false alarm.

> Bài làm còn có lỗi cần kiểm tra.

**v3**: status `valid`, joint `pass`; review: Source-grounded agent review, not independent human gold. F29-C (data/raw/task3-sft-v2/sources/F29-C.cpp). The accumulation and ordered strict-update invariant prove the clean result. L1 gives only truthful praise.

> Bài làm đáp ứng yêu cầu của đề.

**Joint regression**: 6 cặp target. Xếp example_id tăng dần, tối đa ba nguồn khác nhau; ví dụ mô tả, không phải mẫu đại diện thống kê.

- `F23-D1-L2` (faulty); xem [dev casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/dev-paired-casebook.html#F23-D1-L2).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <iostream>
2: #include <string>
3: using namespace std;
4: 
5: int main() {
6: string s;cin>>s;bool ok=true;
7: for(int i=0;i<(int)s.size()/2;++i) if(s[i]!=s[s.size()-1-i])ok=false;
8: cout<<(ok?"YES":"NO")<<"\n";
9: }
```

**v2**: status `valid`, joint `pass`; review: Source-grounded agent review, not independent human gold. F23-D1 (data/raw/task3-sft-v2/sources/F23-D1.cpp). The response locates the input-reading stage and identifies the actual loss of the rest of the line. It diagnoses truncation without prescribing a replacement.

> Bài đọc đầu vào nhưng bỏ qua phần còn lại của dòng.

**v3**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. F23-D1 (data/raw/task3-sft-v2/sources/F23-D1.cpp). The source is faulty on spaced lines, so a broad conditional-input label is plausible; generic 'has an error/check' gives no actual location or cause required at L2.

> Bài làm còn có lỗi cần kiểm tra.

- `F29-D1-L1` (faulty); xem [dev casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/dev-paired-casebook.html#F29-D1-L1).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <iostream>
2: #include <map>
3: using namespace std;
4: 
5: int main() {
6: int n;cin>>n;map<int,int> freq;for(int i=0;i<n;++i){int x;cin>>x;++freq[x];}
7: int best=0,count=-1;for(auto p:freq)if(p.second>=count){count=p.second;best=p.first;}
8: cout<<best<<"\n";
9: }
```

**v2**: status `valid`, joint `pass`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v2/sources/F29-D1.cpp: Faulty status is supported by the tie counterexample; no location or specific cause is disclosed at L1.

> Bài làm còn có lỗi cần kiểm tra.

**v3**: status `valid`, joint `fail`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v2/sources/F29-D1.cpp: False clean status is contradicted by n=2, values 1 2, where the source prints 2 instead of 1.

> Bài làm đáp ứng yêu cầu của đề.

- `F32-D2-L4` (faulty); xem [dev casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/dev-paired-casebook.html#F32-D2-L4).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <iostream>
2: #include <vector>
3: #include <algorithm>
4: using namespace std;
5: 
6: int main() {
7: int n;cin>>n;vector<int>a(n);for(int &x:a)cin>>x;
8: sort(a.begin(),a.end());for(int x:a)if(x<0)cout<<x<<" ";for(int x:a)if(x>=0)cout<<x<<" ";cout<<"\n";
9: }
```

**v2**: status `valid`, joint `pass`; review: Source-grounded agent review, not independent human gold. F32-D2 (data/raw/task3-sft-v2/sources/F32-D2.cpp). The response diagnoses the offending sorting and directs storing the two groups while preserving their internal order, then emitting negatives followed by nonnegatives. This equivalent conceptual stable-partition repair is useful without full code.

> Bài làm còn có lỗi về sắp xếp nên chưa đáp ứng yêu cầu của đề. Để giữ thứ tự trong từng nhóm, hãy dùng hai vùng riêng để lưu số âm và số không âm, rồi ghép chúng lại khi xuất kết quả.

**v3**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. F32-D2 (data/raw/task3-sft-v2/sources/F32-D2.cpp). The supplied program still sorts a before collecting the groups, contrary to the prose claim that original data/order is retained. Its own -1,-2 example would print -2,-1. Bounded code evidence fails tests 3,4,6.

> Bài làm còn có lỗi cần kiểm tra. Em hãy đọc kỹ yêu cầu về thứ tự của từng nhóm và sắp xếp lại phần tử đã phân loại. Trong lời giải bên dưới, dữ liệu gốc được giữ nguyên khi xuất nên thứ tự tương đối vẫn được bảo toàn. Ví dụ, với dữ liệu "5\n-1 -2 0 3 4", kết quả cần nhận là "-1 -2 0 3 4 ".
> 
> ```cpp
> #include <iostream>
> #include <vector>
> #include <algorithm>
> using namespace std;
> 
> int main() {
> int n;cin>>n;vector<int>a(n);for(int &x:a)cin>>x;
> sort(a.begin(),a.end());vector<int>pos,neg;for(int x:a){if(x<0)neg.push_back(x);else pos.push_back(x);}for(int x:neg)cout<<x<<" ";for(int x:pos)cout<<x<<" ";cout<<"\n";
> }
> ```

**Level cải thiện**: 21 cặp target. Xếp example_id tăng dần, tối đa ba nguồn khác nhau; ví dụ mô tả, không phải mẫu đại diện thống kê.

- `F23-D2-L3` (faulty); xem [dev casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/dev-paired-casebook.html#F23-D2-L3).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <iostream>
2: #include <string>
3: using namespace std;
4: 
5: int main() {
6: string s;getline(cin,s);bool ok=true;
7: for(int i=0;i<(int)s.size()/2;++i) if(s[i]!=s[s.size()-1-i])ok=false;else ok=true;
8: cout<<(ok?"YES":"NO")<<"\n";
9: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v2/sources/F23-D2.cpp: With fewer than two characters the loop does not execute and YES is correct. No inverted assignment occurs on that path, and no repair is offered.

> Biến ok bị gán ngược trong vòng duyệt nên luôn đúng khi có ít hơn hai ký tự.

**v3**: status `valid`, joint `fail`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v2/sources/F23-D2.cpp: The diagnosis that ok retains only the current comparison is accurate. Recommending two pointers does not repair this source, which already compares s[i] with s[size-1-i]; persistence or early exit is missing.

> Biến ok bị gán lại trong mỗi lần so sánh nên chỉ giữ trạng thái của cặp đầu cuối đang xét. Em hãy dùng hai con trỏ duyệt từ hai đầu về giữa để kiểm tra toàn bộ dãy.

- `F23-D3-L3` (faulty); xem [dev casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/dev-paired-casebook.html#F23-D3-L3).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <iostream>
2: #include <string>
3: using namespace std;
4: 
5: int main() {
6: string s;getline(cin,s);bool ok=true;
7: for(int i=0;i<(int)s.size()/2-1;++i) if(s[i]!=s[s.size()-1-i])ok=false;
8: cout<<(ok?"YES":"NO")<<"\n";
9: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. Source line 7 uses i<floor(size/2)-1, omitting the innermost required symmetric pair for every length>=2. A wrong acceptance requires that omitted pair to mismatch while checked pairs match; existing tests 4 (abca), 5 (abc), 6 (Aba), and 9 fail. Empty/singleton strings remain safe and correct. The final missed comparison and half-minus-one cause are correctly diagnosed, but L3 supplies no repair direction at all. Response under review: {"taxonomy_error": ["Lỗi vòng lặp"], "feedback": "Bài kiểm tra có lỗi trong vòng duyệt nửa chuỗi. Vị trí so sánh cuối cùng bị bỏ qua khi chỉ duyệt đến nửa chuỗi trừ một."}. Code evidence status=absent.

> Bài kiểm tra có lỗi trong vòng duyệt nửa chuỗi. Vị trí so sánh cuối cùng bị bỏ qua khi chỉ duyệt đến nửa chuỗi trừ một.

**v3**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. Source line 7 uses i<floor(size/2)-1, omitting the innermost required symmetric pair for every length>=2. A wrong acceptance requires that omitted pair to mismatch while checked pairs match; existing tests 4 (abca), 5 (abc), 6 (Aba), and 9 fail. Empty/singleton strings remain safe and correct. The response wrongly says the defect is skipping the odd-length center; the center is self-equal and not required. Extending comparisons toward the middle is a potentially useful bound hint, but does not validate that false diagnosis. Response under review: {"taxonomy_error": ["Lỗi vòng lặp"], "feedback": "Vòng kiểm tra đảo dừng trước nửa chuỗi nên bỏ qua ký tự giữa khi độ dài lẻ. Em hãy duyệt tới vị trí trung tâm của chuỗi để xử lý cả hai trường hợp."}. Code evidence status=absent.

> Vòng kiểm tra đảo dừng trước nửa chuỗi nên bỏ qua ký tự giữa khi độ dài lẻ. Em hãy duyệt tới vị trí trung tâm của chuỗi để xử lý cả hai trường hợp.

- `F29-C-L2` (clean); xem [dev casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/dev-paired-casebook.html#F29-C-L2).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <iostream>
2: #include <map>
3: using namespace std;
4: 
5: int main() {
6: int n;cin>>n;map<int,int> freq;for(int i=0;i<n;++i){int x;cin>>x;++freq[x];}
7: int best=0,count=-1;for(auto p:freq)if(p.second>count){count=p.second;best=p.first;}
8: cout<<best<<"\n";
9: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. F29-C (data/raw/task3-sft-v2/sources/F29-C.cpp). No modal-value error exists: best is updated on strictly larger frequency in increasing key order. The vague invented logic fault is unsupported and supplies no L2 cause.

> Bài làm còn có lỗi về tính chất của giá trị xuất hiện nhiều nhất.

**v3**: status `valid`, joint `pass`; review: Source-grounded agent review, not independent human gold. F29-C (data/raw/task3-sft-v2/sources/F29-C.cpp). The source correctly computes frequencies and prints the smallest modal value; the response's clean assessment is supported.

> Bài làm đáp ứng đúng yêu cầu về tần suất xuất hiện của dãy số trong đề.

**Level regression**: 8 cặp target. Xếp example_id tăng dần, tối đa ba nguồn khác nhau; ví dụ mô tả, không phải mẫu đại diện thống kê.

- `F23-D1-L2` (faulty); xem [dev casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/dev-paired-casebook.html#F23-D1-L2).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <iostream>
2: #include <string>
3: using namespace std;
4: 
5: int main() {
6: string s;cin>>s;bool ok=true;
7: for(int i=0;i<(int)s.size()/2;++i) if(s[i]!=s[s.size()-1-i])ok=false;
8: cout<<(ok?"YES":"NO")<<"\n";
9: }
```

**v2**: status `valid`, joint `pass`; review: Source-grounded agent review, not independent human gold. F23-D1 (data/raw/task3-sft-v2/sources/F23-D1.cpp). The response locates the input-reading stage and identifies the actual loss of the rest of the line. It diagnoses truncation without prescribing a replacement.

> Bài đọc đầu vào nhưng bỏ qua phần còn lại của dòng.

**v3**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. F23-D1 (data/raw/task3-sft-v2/sources/F23-D1.cpp). The source is faulty on spaced lines, so a broad conditional-input label is plausible; generic 'has an error/check' gives no actual location or cause required at L2.

> Bài làm còn có lỗi cần kiểm tra.

- `F23-D2-L2` (faulty); xem [dev casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/dev-paired-casebook.html#F23-D2-L2).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <iostream>
2: #include <string>
3: using namespace std;
4: 
5: int main() {
6: string s;getline(cin,s);bool ok=true;
7: for(int i=0;i<(int)s.size()/2;++i) if(s[i]!=s[s.size()-1-i])ok=false;else ok=true;
8: cout<<(ok?"YES":"NO")<<"\n";
9: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v2/sources/F23-D2.cpp: The flag is not always true: ab produces NO. The specific claimed cause and outcome are false, although the answer has the form of an L2 diagnosis.

> Biến ok bị gán ngược trong vòng duyệt nên luôn đúng.

**v3**: status `valid`, joint `fail`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v2/sources/F23-D2.cpp: ok is indeed assigned on each comparison, but assignment alone is normal; the answer omits the harmful reset after a prior mismatch, so it does not explain the actual cause/trigger sufficiently for L2.

> Biến ok bị gán lại trong mỗi lần so sánh.

- `F32-D1-L3` (faulty); xem [dev casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/dev-paired-casebook.html#F32-D1-L3).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <iostream>
2: #include <vector>
3: using namespace std;
4: 
5: int main() {
6: int n;cin>>n;vector<int>a(n);for(int &x:a)cin>>x;
7: for(int x:a)if(x<0)cout<<x<<" ";for(int x:a)if(x>0)cout<<x<<" ";cout<<"\n";
8: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. Line 7 has two independent forward passes, x<0 then x>0. They preserve each printed group's input order and never duplicate a value; the sole functional defect is omitting zero from both predicates. Any input zero is missing from output (test 1 expects 0 but gets only LF; tests 3 and 5 also fail). Token whitespace and misleading-indentation warnings do not create another defect. Its input declares n=5 but supplies four values, and its claimed original output includes zero although this source never prints zero. Two separate loops already preserve order; repeating that instruction misses the actual boundary defect. Response under review: {"taxonomy_error": ["Lỗi logic"], "feedback": "Bài làm còn có lỗi về thứ tự xuất. Ví dụ, với đầu vào \"5 -1 2 0 -3\", kết quả của bạn sẽ là \"-1 -3 2 0 \". Để đảm bảo thứ tự trong mỗi nhóm, hãy dùng hai vòng duyệt riêng biệt."}. Code evidence status=absent.

> Bài làm còn có lỗi về thứ tự xuất. Ví dụ, với đầu vào "5 -1 2 0 -3", kết quả của bạn sẽ là "-1 -3 2 0 ". Để đảm bảo thứ tự trong mỗi nhóm, hãy dùng hai vòng duyệt riêng biệt.

**v3**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. Line 7 has two independent forward passes, x<0 then x>0. They preserve each printed group's input order and never duplicate a value; the sole functional defect is omitting zero from both predicates. Any input zero is missing from output (test 1 expects 0 but gets only LF; tests 3 and 5 also fail). Token whitespace and misleading-indentation warnings do not create another defect. Reading group-order requirements and generally rearranging output does not identify or repair the actual zero omission. Relative order within both printed groups already holds, so the suggested target of repair is also misleading. Response under review: {"taxonomy_error": ["Lỗi logic"], "feedback": "Bài làm còn có lỗi cần kiểm tra. Em hãy đọc kỹ yêu cầu về thứ tự của hai nhóm và sắp xếp lại phần xuất để giữ nguyên thứ tự tương đối trong mỗi nhóm."}. Code evidence status=absent.

> Bài làm còn có lỗi cần kiểm tra. Em hãy đọc kỹ yêu cầu về thứ tự của hai nhóm và sắp xếp lại phần xuất để giữ nguyên thứ tự tương đối trong mỗi nhóm.

**Assessment cải thiện**: 24 cặp target. Xếp example_id tăng dần, tối đa ba nguồn khác nhau; ví dụ mô tả, không phải mẫu đại diện thống kê.

- `F23-C-L2` (clean); xem [dev casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/dev-paired-casebook.html#F23-C-L2).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <iostream>
2: #include <string>
3: using namespace std;
4: 
5: int main() {
6: string s;getline(cin,s);bool ok=true;
7: for(int i=0;i<(int)s.size()/2;++i) if(s[i]!=s[s.size()-1-i])ok=false;
8: cout<<(ok?"YES":"NO")<<"\n";
9: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. Source line 6 uses getline and line 7 checks every distinct symmetric pair i<floor(size/2), preserving case and spaces; empty/singleton lines are valid. Existing tests 0..10 pass. The response truthfully assesses this clean source. The alleged incorrect order from traversing half the string is unsupported: symmetric pairs suffice and the actual comparison order is correct. Response under review: {"taxonomy_error": ["Lỗi logic"], "feedback": "Bài kiểm tra đảo chuỗi sai thứ tự của hai phần còn lại khi chỉ duyệt nửa chiều."}. Code evidence status=absent.

> Bài kiểm tra đảo chuỗi sai thứ tự của hai phần còn lại khi chỉ duyệt nửa chiều.

**v3**: status `valid`, joint `pass`; review: Source-grounded agent review, not independent human gold. Source line 6 uses getline and line 7 checks every distinct symmetric pair i<floor(size/2), preserving case and spaces; empty/singleton lines are valid. Existing tests 0..10 pass. The response truthfully assesses this clean source. The assessment and supplied explanation/direction agree with the source mechanism. Disclosure is appropriate at this Level; clean sources require no invented defect/repair, and L4 does not require code. Response under review: {"taxonomy_error": [], "feedback": "Bài làm đáp ứng đúng yêu cầu về kiểm tra chuỗi palindrome trong đề."}. Code evidence status=absent.

> Bài làm đáp ứng đúng yêu cầu về kiểm tra chuỗi palindrome trong đề.

- `F23-D1-L1` (faulty); xem [dev casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/dev-paired-casebook.html#F23-D1-L1).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <iostream>
2: #include <string>
3: using namespace std;
4: 
5: int main() {
6: string s;cin>>s;bool ok=true;
7: for(int i=0;i<(int)s.size()/2;++i) if(s[i]!=s[s.size()-1-i])ok=false;
8: cout<<(ok?"YES":"NO")<<"\n";
9: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. F23-D1 (data/raw/task3-sft-v2/sources/F23-D1.cpp). Faulty status is true, but Lỗi vòng lặp is unsupported: i<size/2 checks all palindrome pairs. The actual defect is formatted input truncating spaces. L1 form itself is compliant.

> Bài làm còn có lỗi cần kiểm tra.

**v3**: status `valid`, joint `pass`; review: Source-grounded agent review, not independent human gold. F23-D1 (data/raw/task3-sft-v2/sources/F23-D1.cpp). A spaced-line input exposes a valid input-handling case defect, so broad edge-case taxonomy is semantically supportable here. The feedback states only faulty status and satisfies L1.

> Bài làm còn có lỗi cần kiểm tra.

- `F23-D2-L3` (faulty); xem [dev casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/dev-paired-casebook.html#F23-D2-L3).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <iostream>
2: #include <string>
3: using namespace std;
4: 
5: int main() {
6: string s;getline(cin,s);bool ok=true;
7: for(int i=0;i<(int)s.size()/2;++i) if(s[i]!=s[s.size()-1-i])ok=false;else ok=true;
8: cout<<(ok?"YES":"NO")<<"\n";
9: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v2/sources/F23-D2.cpp: With fewer than two characters the loop does not execute and YES is correct. No inverted assignment occurs on that path, and no repair is offered.

> Biến ok bị gán ngược trong vòng duyệt nên luôn đúng khi có ít hơn hai ký tự.

**v3**: status `valid`, joint `fail`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v2/sources/F23-D2.cpp: The diagnosis that ok retains only the current comparison is accurate. Recommending two pointers does not repair this source, which already compares s[i] with s[size-1-i]; persistence or early exit is missing.

> Biến ok bị gán lại trong mỗi lần so sánh nên chỉ giữ trạng thái của cặp đầu cuối đang xét. Em hãy dùng hai con trỏ duyệt từ hai đầu về giữa để kiểm tra toàn bộ dãy.

**Assessment regression**: 10 cặp target. Xếp example_id tăng dần, tối đa ba nguồn khác nhau; ví dụ mô tả, không phải mẫu đại diện thống kê.

- `F23-D1-L2` (faulty); xem [dev casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/dev-paired-casebook.html#F23-D1-L2).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <iostream>
2: #include <string>
3: using namespace std;
4: 
5: int main() {
6: string s;cin>>s;bool ok=true;
7: for(int i=0;i<(int)s.size()/2;++i) if(s[i]!=s[s.size()-1-i])ok=false;
8: cout<<(ok?"YES":"NO")<<"\n";
9: }
```

**v2**: status `valid`, joint `pass`; review: Source-grounded agent review, not independent human gold. F23-D1 (data/raw/task3-sft-v2/sources/F23-D1.cpp). The response locates the input-reading stage and identifies the actual loss of the rest of the line. It diagnoses truncation without prescribing a replacement.

> Bài đọc đầu vào nhưng bỏ qua phần còn lại của dòng.

**v3**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. F23-D1 (data/raw/task3-sft-v2/sources/F23-D1.cpp). The source is faulty on spaced lines, so a broad conditional-input label is plausible; generic 'has an error/check' gives no actual location or cause required at L2.

> Bài làm còn có lỗi cần kiểm tra.

- `F23-D3-L3` (faulty); xem [dev casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/dev-paired-casebook.html#F23-D3-L3).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <iostream>
2: #include <string>
3: using namespace std;
4: 
5: int main() {
6: string s;getline(cin,s);bool ok=true;
7: for(int i=0;i<(int)s.size()/2-1;++i) if(s[i]!=s[s.size()-1-i])ok=false;
8: cout<<(ok?"YES":"NO")<<"\n";
9: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. Source line 7 uses i<floor(size/2)-1, omitting the innermost required symmetric pair for every length>=2. A wrong acceptance requires that omitted pair to mismatch while checked pairs match; existing tests 4 (abca), 5 (abc), 6 (Aba), and 9 fail. Empty/singleton strings remain safe and correct. The final missed comparison and half-minus-one cause are correctly diagnosed, but L3 supplies no repair direction at all. Response under review: {"taxonomy_error": ["Lỗi vòng lặp"], "feedback": "Bài kiểm tra có lỗi trong vòng duyệt nửa chuỗi. Vị trí so sánh cuối cùng bị bỏ qua khi chỉ duyệt đến nửa chuỗi trừ một."}. Code evidence status=absent.

> Bài kiểm tra có lỗi trong vòng duyệt nửa chuỗi. Vị trí so sánh cuối cùng bị bỏ qua khi chỉ duyệt đến nửa chuỗi trừ một.

**v3**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. Source line 7 uses i<floor(size/2)-1, omitting the innermost required symmetric pair for every length>=2. A wrong acceptance requires that omitted pair to mismatch while checked pairs match; existing tests 4 (abca), 5 (abc), 6 (Aba), and 9 fail. Empty/singleton strings remain safe and correct. The response wrongly says the defect is skipping the odd-length center; the center is self-equal and not required. Extending comparisons toward the middle is a potentially useful bound hint, but does not validate that false diagnosis. Response under review: {"taxonomy_error": ["Lỗi vòng lặp"], "feedback": "Vòng kiểm tra đảo dừng trước nửa chuỗi nên bỏ qua ký tự giữa khi độ dài lẻ. Em hãy duyệt tới vị trí trung tâm của chuỗi để xử lý cả hai trường hợp."}. Code evidence status=absent.

> Vòng kiểm tra đảo dừng trước nửa chuỗi nên bỏ qua ký tự giữa khi độ dài lẻ. Em hãy duyệt tới vị trí trung tâm của chuỗi để xử lý cả hai trường hợp.

- `F29-D1-L1` (faulty); xem [dev casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/dev-paired-casebook.html#F29-D1-L1).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <iostream>
2: #include <map>
3: using namespace std;
4: 
5: int main() {
6: int n;cin>>n;map<int,int> freq;for(int i=0;i<n;++i){int x;cin>>x;++freq[x];}
7: int best=0,count=-1;for(auto p:freq)if(p.second>=count){count=p.second;best=p.first;}
8: cout<<best<<"\n";
9: }
```

**v2**: status `valid`, joint `pass`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v2/sources/F29-D1.cpp: Faulty status is supported by the tie counterexample; no location or specific cause is disclosed at L1.

> Bài làm còn có lỗi cần kiểm tra.

**v3**: status `valid`, joint `fail`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v2/sources/F29-D1.cpp: False clean status is contradicted by n=2, values 1 2, where the source prints 2 instead of 1.

> Bài làm đáp ứng yêu cầu của đề.

### final: v2 → selected v3

**Joint cải thiện**: 49 cặp target. Xếp example_id tăng dần, tối đa ba nguồn khác nhau; ví dụ mô tả, không phải mẫu đại diện thống kê.

- `V2E01-C1-L1` (clean); xem [final casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/final-paired-casebook.html#V2E01-C1-L1).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <bits/stdc++.h>
2: using namespace std;
3: int main(){
4:     string s; getline(cin,s); vector<string> fields; string field; bool quoted=false;
5:     for(size_t i=0;i<s.size();++i){
6:         if(s[i]=='"'){
7:             if(quoted && i+1<s.size() && s[i+1]=='"'){field += '"'; ++i;}
8:             else quoted=!quoted;
9:         } else if(s[i]==',' && !quoted){fields.push_back(field); field.clear();}
10:         else field+=s[i];
11:     }
12:     fields.push_back(field); cout<<fields.size()<<'\n';
13:     for(const string& f:fields) cout<<f.size()<<':'<<f<<'\n';
14: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. Source V2E01-C1: The quote-state scan treats commas as separators only outside quoted fields; inside quotes it decodes a doubled quote to one literal quote and skips the second source character. Every completed field and the final field are emitted, preserving empty/trailing fields and spaces. Essential conditions: Input is guaranteed valid CSV, length at most 100 ASCII bytes; no invalid-CSV validation is required. Empty input is one empty field. A quoted comma stays content, and a doubled quote must become one quote. Output is exact bytes with a final LF per line. Historical evidence data/raw/task3-sft-v2/authoring/final-verification/execution.private.json key V2E01-C1; selected test indices 0,1,3,4,6,7,8,9,11,12,13. The source satisfies valid CSV parsing and byte formatting; nonempty edge-case taxonomy and generic fault status are a false alarm, although status-only L1 form is appropriate. Actual response: {"taxonomy_error": ["Lỗi edge case"], "feedback": "Bài làm còn có lỗi cần kiểm tra."}. Mechanical code evidence status=absent.

> Bài làm còn có lỗi cần kiểm tra.

**v3**: status `valid`, joint `pass`; review: Source-grounded agent review, not independent human gold. Source V2E01-C1: The quote-state scan treats commas as separators only outside quoted fields; inside quotes it decodes a doubled quote to one literal quote and skips the second source character. Every completed field and the final field are emitted, preserving empty/trailing fields and spaces. Essential conditions: Input is guaranteed valid CSV, length at most 100 ASCII bytes; no invalid-CSV validation is required. Empty input is one empty field. A quoted comma stays content, and a doubled quote must become one quote. Output is exact bytes with a final LF per line. Historical evidence data/raw/task3-sft-v2/authoring/final-verification/execution.private.json key V2E01-C1; selected test indices 0,1,3,4,6,7,8,9,11,12,13. This response gives a supported, consistent assessment of the actual source. Its explanation/hint (where supplied) agrees with the mechanism; clean truthful status needs no invented defect/repair. Disclosure is appropriate at this Level and code absence alone is not penalized at L4. Actual response: {"taxonomy_error": [], "feedback": "Bài làm đáp ứng yêu cầu của đề."}. Mechanical code evidence status=absent.

> Bài làm đáp ứng yêu cầu của đề.

- `V2E01-C2-L1` (clean); xem [final casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/final-paired-casebook.html#V2E01-C2-L1).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <bits/stdc++.h>
2: using namespace std;
3: int main(){
4:     string s; getline(cin,s); vector<string> values; size_t pos=0;
5:     for(;;){
6:         string out;
7:         if(pos<s.size() && s[pos]=='"'){
8:             ++pos;
9:             while(pos<s.size()){
10:                 if(s[pos]!='"'){out+=s[pos++];}
11:                 else if(pos+1<s.size() && s[pos+1]=='"'){out.push_back('"');pos+=2;}
12:                 else {++pos;break;}
13:             }
14:         } else while(pos<s.size() && s[pos]!=',') out+=s[pos++];
15:         values.push_back(out);
16:         if(pos==s.size()) break;
17:         ++pos;
18:     }
19:     cout<<values.size()<<'\n';
20:     for(auto v:values)cout<<v.length()<<':'<<v<<'\n';
21: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v3/sources/V2E01-C2.cpp: Unsupported edge-case alarm: the clean cursor parser retains initial, interior and trailing empty fields, including the empty line as one empty field.

> Bài làm còn có lỗi cần kiểm tra.

**v3**: status `valid`, joint `pass`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v3/sources/V2E01-C2.cpp: Truthful clean status: quoted commas, doubled quotes and empty fields are handled by the cursor branches, with exact length/content output.

> Bài làm đáp ứng yêu cầu của đề.

- `V2E02-C1-L1` (clean); xem [final casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/final-paired-casebook.html#V2E02-C1-L1).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <bits/stdc++.h>
2: using namespace std;
3: int main(){
4:     string s,part;cin>>s; stringstream stream(s); int count=0; bool ok=s.back()!='.';
5:     while(getline(stream,part,'.')){
6:         ++count; bool local=!part.empty() && part.size()<=3;
7:         int value=0;
8:         for(char c:part){if(c<'0'||c>'9')local=false;else if(part.size()<=3)value=value*10+c-'0';}
9:         if(part.size()>1 && part[0]=='0') local=false;
10:         if(!(value<=255))local=false;
11:         ok=ok&&local;
12:     }
13:     cout<<(ok && count==4?"YES":"NO")<<'\n';
14: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. V2E02-C1; full source/specification and own canonical source review were checked. The source's component checks and sticky global validity satisfy the specification; this unsupported L1 error claim is a false alarm, although its status-only form is compliant.

> Bài làm còn có lỗi cần kiểm tra.

**v3**: status `valid`, joint `pass`; review: Source-grounded agent review, not independent human gold. V2E02-C1; full source/specification and own canonical source review were checked. Every component is nonempty, digit-only, <=3 digits, <=255 and canonically zero-formatted; exactly four components and no trailing dot are required. Clean L1 praise is supported.

> Bài làm đáp ứng yêu cầu của đề.

**Joint regression**: 12 cặp target. Xếp example_id tăng dần, tối đa ba nguồn khác nhau; ví dụ mô tả, không phải mẫu đại diện thống kê.

- `V2E01-D1-L1` (faulty); xem [final casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/final-paired-casebook.html#V2E01-D1-L1).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <bits/stdc++.h>
2: using namespace std;
3: int main(){
4:     string s; getline(cin,s); vector<string> fields; string field; bool quoted=false;
5:     for(size_t i=0;i<s.size();++i){
6:         if(s[i]=='"'){
7:             if(quoted && i+1<s.size() && s[i+1]=='"'){field += ""; ++i;}
8:             else quoted=!quoted;
9:         } else if(s[i]==',' && !quoted){fields.push_back(field); field.clear();}
10:         else field+=s[i];
11:     }
12:     fields.push_back(field); cout<<fields.size()<<'\n';
13:     for(const string& f:fields) cout<<f.size()<<':'<<f<<'\n';
14: }
```

**v2**: status `valid`, joint `pass`; review: Source-grounded agent review, not independent human gold. V2E01-D1; full source/specification and own canonical source review were checked. Escaped-double-quote inputs form a supported conditional CSV case defect, so broad edge-case taxonomy is plausible. The text reports only faulty status, as L1 requires.

> Bài làm còn có lỗi cần kiểm tra.

**v3**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. V2E01-D1; full source/specification and own canonical source review were checked. False clean praise: escaped quote pairs are consumed by field += "" without emitting a decoded quote; historical test "a""b" loses the quote and prints length 2 instead of 3. L1 status form is compliant.

> Bài làm đáp ứng yêu cầu của đề.

- `V2E01-D2-L1` (faulty); xem [final casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/final-paired-casebook.html#V2E01-D2-L1).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <bits/stdc++.h>
2: using namespace std;
3: int main(){
4:     string s; getline(cin,s); vector<string> values; size_t pos=0;
5:     for(;;){
6:         string out;
7:         if(pos<s.size() && s[pos]=='"'){
8:             ++pos;
9:             while(pos<s.size()){
10:                 if(s[pos]!='"'){out+=s[pos++];}
11:                 else if(pos+1<s.size() && s[pos+1]=='"'){out.push_back(',');pos+=2;}
12:                 else {++pos;break;}
13:             }
14:         } else while(pos<s.size() && s[pos]!=',') out+=s[pos++];
15:         values.push_back(out);
16:         if(pos==s.size()) break;
17:         ++pos;
18:     }
19:     cout<<values.size()<<'\n';
20:     for(auto v:values)cout<<v.length()<<':'<<v<<'\n';
21: }
```

**v2**: status `valid`, joint `pass`; review: Source-grounded agent review, not independent human gold. Source V2E01-D2: The escaped-double-quote branch appends a comma instead of a literal double quote. Field lengths and field counts may remain correct, but decoded content is corrupted at every escaped quote. Essential conditions: A valid quoted field containing an escaped doubled quote is necessary and sufficient for a content mismatch here. Quoted fields containing commas without escaped quotes, empty fields, and unquoted fields are handled by otherwise valid parsing; these can mask the defect. Exact-byte output compares the corrupted quote/comma character even when decoded length is unchanged. Historical evidence data/raw/task3-sft-v2/authoring/final-verification/execution.private.json key V2E01-D2; selected test indices 3,4,6,8,10,11. This response gives a supported, consistent assessment of the actual source. Its explanation/hint (where supplied) agrees with the mechanism; clean truthful status needs no invented defect/repair. Disclosure is appropriate at this Level and code absence alone is not penalized at L4. Actual response: {"taxonomy_error": ["Lỗi edge case"], "feedback": "Bài làm còn có lỗi cần kiểm tra."}. Mechanical code evidence status=absent.

> Bài làm còn có lỗi cần kiểm tra.

**v3**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. Source V2E01-D2: The escaped-double-quote branch appends a comma instead of a literal double quote. Field lengths and field counts may remain correct, but decoded content is corrupted at every escaped quote. Essential conditions: A valid quoted field containing an escaped doubled quote is necessary and sufficient for a content mismatch here. Quoted fields containing commas without escaped quotes, empty fields, and unquoted fields are handled by otherwise valid parsing; these can mask the defect. Exact-byte output compares the corrupted quote/comma character even when decoded length is unchanged. Historical evidence data/raw/task3-sft-v2/authoring/final-verification/execution.private.json key V2E01-D2; selected test indices 3,4,6,8,10,11. Full-correctness praise and empty taxonomy miss the escaped-quote corruption; disclosure is still status-only L1. Actual response: {"taxonomy_error": [], "feedback": "Bài làm đáp ứng yêu cầu của đề."}. Mechanical code evidence status=absent.

> Bài làm đáp ứng yêu cầu của đề.

- `V2E02-D1-L1` (faulty); xem [final casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/final-paired-casebook.html#V2E02-D1-L1).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <bits/stdc++.h>
2: using namespace std;
3: int main(){
4:     string s,part;cin>>s; stringstream stream(s); int count=0; bool ok=s.back()!='.';
5:     while(getline(stream,part,'.')){
6:         ++count; bool local=!part.empty() && part.size()<=3;
7:         int value=0;
8:         for(char c:part){if(c<'0'||c>'9')local=false;else if(part.size()<=3)value=value*10+c-'0';}
9:         if(part.size()>1 && part[0]=='0') local=false;
10:         if(!(value<=256))local=false;
11:         ok=ok&&local;
12:     }
13:     cout<<(ok && count==4?"YES":"NO")<<'\n';
14: }
```

**v2**: status `valid`, joint `pass`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v3/sources/V2E02-D1.cpp: Truthful faulty status, supported by 256.1.2.3 being accepted despite the required maximum 255; no cause/location is disclosed at L1.

> Bài làm còn có lỗi cần kiểm tra.

**v3**: status `valid`, joint `fail`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v3/sources/V2E02-D1.cpp: False clean status: 256.1.2.3 prints YES instead of NO.

> Bài làm đáp ứng yêu cầu của đề.

**Level cải thiện**: 37 cặp target. Xếp example_id tăng dần, tối đa ba nguồn khác nhau; ví dụ mô tả, không phải mẫu đại diện thống kê.

- `V2E01-C1-L3` (clean); xem [final casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/final-paired-casebook.html#V2E01-C1-L3).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <bits/stdc++.h>
2: using namespace std;
3: int main(){
4:     string s; getline(cin,s); vector<string> fields; string field; bool quoted=false;
5:     for(size_t i=0;i<s.size();++i){
6:         if(s[i]=='"'){
7:             if(quoted && i+1<s.size() && s[i+1]=='"'){field += '"'; ++i;}
8:             else quoted=!quoted;
9:         } else if(s[i]==',' && !quoted){fields.push_back(field); field.clear();}
10:         else field+=s[i];
11:     }
12:     fields.push_back(field); cout<<fields.size()<<'\n';
13:     for(const string& f:fields) cout<<f.size()<<':'<<f<<'\n';
14: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. Source V2E01-C1: The quote-state scan treats commas as separators only outside quoted fields; inside quotes it decodes a doubled quote to one literal quote and skips the second source character. Every completed field and the final field are emitted, preserving empty/trailing fields and spaces. Essential conditions: Input is guaranteed valid CSV, length at most 100 ASCII bytes; no invalid-CSV validation is required. Empty input is one empty field. A quoted comma stays content, and a doubled quote must become one quote. Output is exact bytes with a final LF per line. Historical evidence data/raw/task3-sft-v2/authoring/final-verification/execution.private.json key V2E01-C1; selected test indices 0,1,3,4,6,7,8,9,11,12,13. Empty fields are already preserved; the claimed defect is false. This L3 text is diagnosis only and gives no repair direction for the fault it alleges. Actual response: {"taxonomy_error": ["Lỗi edge case"], "feedback": "Bài làm còn thiếu xử lý trường rỗng trong dòng đầu."}. Mechanical code evidence status=absent.

> Bài làm còn thiếu xử lý trường rỗng trong dòng đầu.

**v3**: status `valid`, joint `pass`; review: Source-grounded agent review, not independent human gold. Source V2E01-C1: The quote-state scan treats commas as separators only outside quoted fields; inside quotes it decodes a doubled quote to one literal quote and skips the second source character. Every completed field and the final field are emitted, preserving empty/trailing fields and spaces. Essential conditions: Input is guaranteed valid CSV, length at most 100 ASCII bytes; no invalid-CSV validation is required. Empty input is one empty field. A quoted comma stays content, and a doubled quote must become one quote. Output is exact bytes with a final LF per line. Historical evidence data/raw/task3-sft-v2/authoring/final-verification/execution.private.json key V2E01-C1; selected test indices 0,1,3,4,6,7,8,9,11,12,13. This response gives a supported, consistent assessment of the actual source. Its explanation/hint (where supplied) agrees with the mechanism; clean truthful status needs no invented defect/repair. Disclosure is appropriate at this Level and code absence alone is not penalized at L4. Actual response: {"taxonomy_error": [], "feedback": "Bài làm đáp ứng yêu cầu của đề. Trạng thái nháy giữ trạng thái mở đóng giữa hai dấu nháy liền nhau. Dấu phẩy ngoài nháy được xử lý như phần tử tách biệt. Không có lỗi cần sửa trong phạm vi yêu cầu đã nêu."}. Mechanical code evidence status=absent.

> Bài làm đáp ứng yêu cầu của đề. Trạng thái nháy giữ trạng thái mở đóng giữa hai dấu nháy liền nhau. Dấu phẩy ngoài nháy được xử lý như phần tử tách biệt. Không có lỗi cần sửa trong phạm vi yêu cầu đã nêu.

- `V2E01-C2-L3` (clean); xem [final casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/final-paired-casebook.html#V2E01-C2-L3).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <bits/stdc++.h>
2: using namespace std;
3: int main(){
4:     string s; getline(cin,s); vector<string> values; size_t pos=0;
5:     for(;;){
6:         string out;
7:         if(pos<s.size() && s[pos]=='"'){
8:             ++pos;
9:             while(pos<s.size()){
10:                 if(s[pos]!='"'){out+=s[pos++];}
11:                 else if(pos+1<s.size() && s[pos+1]=='"'){out.push_back('"');pos+=2;}
12:                 else {++pos;break;}
13:             }
14:         } else while(pos<s.size() && s[pos]!=',') out+=s[pos++];
15:         values.push_back(out);
16:         if(pos==s.size()) break;
17:         ++pos;
18:     }
19:     cout<<values.size()<<'\n';
20:     for(auto v:values)cout<<v.length()<<':'<<v<<'\n';
21: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v3/sources/V2E01-C2.cpp: The empty line is already processed once and pushed as an empty string. The response invents missing empty-field handling and supplies no actual useful repair direction despite L3.

> Bài làm còn thiếu xử lý trường rỗng trong dòng đầu. Trong khi đó, phần tử đầu tiên của vector luôn được tạo nên nên vẫn có thể truy cập được.

**v3**: status `valid`, joint `pass`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v3/sources/V2E01-C2.cpp: The clean assessment and field-output description are supported: unquoted fields stop at separators, the quoted branch decodes literal quotes and removes its closing quote, and each decoded field is emitted with its length.

> Bài làm đáp ứng yêu cầu của đề. Trong main, vòng tách trường dừng khi gặp dấu phẩy hoặc hết chuỗi. Trường trong nháy giữ dấu nháy kép bên trong và bỏ dấu nháy khi kết thúc. Vòng xuất lần lượt độ dài và nội dung của tất cả các trường đã phân tách.

- `V2E01-D1-L3` (faulty); xem [final casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/final-paired-casebook.html#V2E01-D1-L3).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <bits/stdc++.h>
2: using namespace std;
3: int main(){
4:     string s; getline(cin,s); vector<string> fields; string field; bool quoted=false;
5:     for(size_t i=0;i<s.size();++i){
6:         if(s[i]=='"'){
7:             if(quoted && i+1<s.size() && s[i+1]=='"'){field += ""; ++i;}
8:             else quoted=!quoted;
9:         } else if(s[i]==',' && !quoted){fields.push_back(field); field.clear();}
10:         else field+=s[i];
11:     }
12:     fields.push_back(field); cout<<fields.size()<<'\n';
13:     for(const string& f:fields) cout<<f.size()<<':'<<f<<'\n';
14: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. V2E01-D1; full source/specification and own canonical source review were checked. Empty fields are already retained by pushing field at each separator and once after the loop, including the empty record. The alleged missing empty-field handling is false and no concrete L3 repair is given.

> Bài làm còn thiếu xử lý trường rỗng trong dòng đầu.

**v3**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. V2E01-D1; full source/specification and own canonical source review were checked. The parser does use quoted state, but drops escaped quote characters. Its no-error assertion misses the actual defect; a truthful clean explanation would be allowed at L3, so disclosure is assessed separately.

> Bài làm đáp ứng yêu cầu của đề. Trong main, chuỗi đọc từ dòng đầu dùng để tách các trường dựa trên trạng thái nháy và dấu phẩy. Không có lỗi cần sửa trong phạm vi yêu cầu đã nêu.

**Level regression**: 5 cặp target. Xếp example_id tăng dần, tối đa ba nguồn khác nhau; ví dụ mô tả, không phải mẫu đại diện thống kê.

- `V2E01-C2-L4` (clean); xem [final casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/final-paired-casebook.html#V2E01-C2-L4).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <bits/stdc++.h>
2: using namespace std;
3: int main(){
4:     string s; getline(cin,s); vector<string> values; size_t pos=0;
5:     for(;;){
6:         string out;
7:         if(pos<s.size() && s[pos]=='"'){
8:             ++pos;
9:             while(pos<s.size()){
10:                 if(s[pos]!='"'){out+=s[pos++];}
11:                 else if(pos+1<s.size() && s[pos+1]=='"'){out.push_back('"');pos+=2;}
12:                 else {++pos;break;}
13:             }
14:         } else while(pos<s.size() && s[pos]!=',') out+=s[pos++];
15:         values.push_back(out);
16:         if(pos==s.size()) break;
17:         ++pos;
18:     }
19:     cout<<values.size()<<'\n';
20:     for(auto v:values)cout<<v.length()<<':'<<v<<'\n';
21: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v3/sources/V2E01-C2.cpp: The empty record is already retained. values is not initialized with a permanently empty first element: every decoded out is pushed, and its first value depends on input. The proposed vague start-position check addresses an invented defect.

> Bài làm còn thiếu xử lý trường rỗng trong dòng đầu. Trong khi đó, phần tử đầu tiên của vector values luôn giữ giá trị khởi tạo rỗng nên vẫn thỏa yêu cầu về trường rỗng. Để đảm bảo tính toàn vẹn, hãy kiểm tra lại vị trí bắt đầu của chuỗi trước khi đọc trường mới.

**v3**: status `malformed_json`, joint `fail`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v3/sources/V2E01-C2.cpp: Invalid response: all semantic axes are not evaluable, and supplied code cannot be adjudicated as absent.

> {"taxonomy_error": [], "feedback": "Bài làm đáp ứng yêu cầu của đề. Trong main, vòng tách trường dừng khi gặp dấu phẩy hoặc hết chuỗi; trường trong nháy giữ dấu nháy kép bên trong. Vòng xuất lần lượt độ dài và nội dung của tất cả các trường đã phân tách. Không có lỗi cần sửa trong phạm vi yêu cầu đã nêu.\n\n```cpp\n#include <bits/stdc++.h>\nusing namespace std;\nint main(){\n    string s; getline(cin,s); vector<string> values; size_t pos=0;\n    for(;;){\n        string out;\n        if(pos<s.size() && s[pos]=='\"'){\n            ++pos;\n            while(pos<s.size()){\n                if(s[pos]!=\'\"\'){out+=s[pos++];}\n                else if(pos+1<s.size() && s[pos+1]==\'\"\'){out.push_back(\'\\"\');pos+=2;}\n                else {++pos;break;}\n            }\n        } else while(pos<s.size() && s[pos]!=\',\') out+=s[pos++];\n        values.push_back(out);\n        if(pos==s.size()) break;\n        ++pos;\n    }\n    cout<<values.size()<<'\\n';\n    for(auto v:values)cout<<v.length()<<':'<v<<'\\n';\n}\n```"}

- `V2E01-D2-L4` (faulty); xem [final casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/final-paired-casebook.html#V2E01-D2-L4).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <bits/stdc++.h>
2: using namespace std;
3: int main(){
4:     string s; getline(cin,s); vector<string> values; size_t pos=0;
5:     for(;;){
6:         string out;
7:         if(pos<s.size() && s[pos]=='"'){
8:             ++pos;
9:             while(pos<s.size()){
10:                 if(s[pos]!='"'){out+=s[pos++];}
11:                 else if(pos+1<s.size() && s[pos+1]=='"'){out.push_back(',');pos+=2;}
12:                 else {++pos;break;}
13:             }
14:         } else while(pos<s.size() && s[pos]!=',') out+=s[pos++];
15:         values.push_back(out);
16:         if(pos==s.size()) break;
17:         ++pos;
18:     }
19:     cout<<values.size()<<'\n';
20:     for(auto v:values)cout<<v.length()<<':'<<v<<'\n';
21: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. Source V2E01-D2: The escaped-double-quote branch appends a comma instead of a literal double quote. Field lengths and field counts may remain correct, but decoded content is corrupted at every escaped quote. Essential conditions: A valid quoted field containing an escaped doubled quote is necessary and sufficient for a content mismatch here. Quoted fields containing commas without escaped quotes, empty fields, and unquoted fields are handled by otherwise valid parsing; these can mask the defect. Exact-byte output compares the corrupted quote/comma character even when decoded length is unchanged. Historical evidence data/raw/task3-sft-v2/authoring/final-verification/execution.private.json key V2E01-D2; selected test indices 3,4,6,8,10,11. The parser already retains empty fields. The claim that the first vector element is always empty is also false (plain abc produces abc). The actual wrong out.push_back(',') escape branch is missed. Actual response: {"taxonomy_error": ["Lỗi edge case"], "feedback": "Bài làm còn thiếu xử lý trường rỗng trong dòng đầu. Trong khi đó, phần tử đầu tiên của vector values luôn giữ giá trị khởi tạo rỗng nên vẫn thỏa yêu cầu về trường rỗng. Để đảm bảo cả hai trường hợp đều đúng, hãy kiểm tra độ dài chuỗi trước khi thêm vào vector."}. Mechanical code evidence status=absent.

> Bài làm còn thiếu xử lý trường rỗng trong dòng đầu. Trong khi đó, phần tử đầu tiên của vector values luôn giữ giá trị khởi tạo rỗng nên vẫn thỏa yêu cầu về trường rỗng. Để đảm bảo cả hai trường hợp đều đúng, hãy kiểm tra độ dài chuỗi trước khi thêm vào vector.

**v3**: status `malformed_json`, joint `fail`; review: Source-grounded agent review, not independent human gold. Source V2E01-D2: The escaped-double-quote branch appends a comma instead of a literal double quote. Field lengths and field counts may remain correct, but decoded content is corrupted at every escaped quote. Essential conditions: A valid quoted field containing an escaped doubled quote is necessary and sufficient for a content mismatch here. Quoted fields containing commas without escaped quotes, empty fields, and unquoted fields are handled by otherwise valid parsing; these can mask the defect. Exact-byte output compares the corrupted quote/comma character even when decoded length is unchanged. Historical evidence data/raw/task3-sft-v2/authoring/final-verification/execution.private.json key V2E01-D2; selected test indices 3,4,6,8,10,11. Malformed JSON is invalid; all semantic axes not_evaluable, code uncertain, irrespective of visible attempted code. Raw invalid response is preserved in the assigned packet; status=malformed_json.

> {"taxonomy_error": [], "feedback": "Bài làm đáp ứng yêu cầu của đề. Trong main, vòng tách trường dừng khi gặp dấu phẩy hoặc hết chuỗi; trường trong nháy giữ dấu phẩy và bỏ dấu nháy khi kết thúc. Số lượng và nội dung của tất cả các trường đều được xuất đúng định dạng. Không có lỗi cần sửa trong phạm vi yêu cầu đã nêu.\n\n```cpp\n#include <bits/stdc++.h>\nusing namespace std;\nint main(){\n    string s; getline(cin,s); vector<string> values; size_t pos=0;\n    for(;;){\n        string out;\n        if(pos<s.size() && s[pos]=='\"'){\n            ++pos;\n            while(pos<s.size()){\n                if(s[pos]!=\'\"\'){out+=s[pos++];}\n                else if(pos+1<s.size() && s[pos+1]==\'\"\'){out.push_back(\',\');pos+=2;}\n                else {++pos;break;}\n            }\n        } else while(pos<s.size() && s[pos]!=\',\') out+=s[pos++];\n        values.push_back(out);\n        if(pos==s.size()) break;\n        ++pos;\n    }\n    cout<<values.size()<<'\\n';\n    for(auto v:values)cout<<v.length()<<':'<v<<'\\n';\n}\n```"}

- `V2E06-C1-L3` (clean); xem [final casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/final-paired-casebook.html#V2E06-C1-L3).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <bits/stdc++.h>
2: using namespace std;
3: int main(){
4:     int n;cin>>n;vector<int>a(n);for(int&x:a)cin>>x;
5:     next_permutation(a.begin(),a.end());
6:     for(int x:a)cout<<x<<' ';cout<<'\n';
7: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v3/sources/V2E06-C1.cpp: next_permutation wraps a maximal sequence to the sorted minimum, which is exactly required. Preserving the original maximal sequence instead would violate the contract.

> next_permutation chỉ tìm các hoán vị kế tiếp theo thứ tự từ điển. Khi đã duyệt hết tất cả các hoán vị, nó sẽ đặt lại dãy ban đầu. Để giữ dãy ban đầu khi không có hoán vị kế tiếp, hãy kiểm tra kết quả trước khi xuất.

**v3**: status `valid`, joint `fail`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v3/sources/V2E06-C1.cpp: next_permutation does not merely sort: for 0 1 2 it produces 0 2 1, a larger immediate successor. The generic request to check ordering supplies no useful concrete L3 direction for the invented defect.

> next_permutation sắp xếp tăng nên kết quả luôn nhỏ hơn hoặc bằng đầu vào. Em hãy kiểm tra lại thứ tự xuất hiện của các phần tử khi duyệt các hoán vị.

**Assessment cải thiện**: 49 cặp target. Xếp example_id tăng dần, tối đa ba nguồn khác nhau; ví dụ mô tả, không phải mẫu đại diện thống kê.

- `V2E01-C1-L1` (clean); xem [final casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/final-paired-casebook.html#V2E01-C1-L1).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <bits/stdc++.h>
2: using namespace std;
3: int main(){
4:     string s; getline(cin,s); vector<string> fields; string field; bool quoted=false;
5:     for(size_t i=0;i<s.size();++i){
6:         if(s[i]=='"'){
7:             if(quoted && i+1<s.size() && s[i+1]=='"'){field += '"'; ++i;}
8:             else quoted=!quoted;
9:         } else if(s[i]==',' && !quoted){fields.push_back(field); field.clear();}
10:         else field+=s[i];
11:     }
12:     fields.push_back(field); cout<<fields.size()<<'\n';
13:     for(const string& f:fields) cout<<f.size()<<':'<<f<<'\n';
14: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. Source V2E01-C1: The quote-state scan treats commas as separators only outside quoted fields; inside quotes it decodes a doubled quote to one literal quote and skips the second source character. Every completed field and the final field are emitted, preserving empty/trailing fields and spaces. Essential conditions: Input is guaranteed valid CSV, length at most 100 ASCII bytes; no invalid-CSV validation is required. Empty input is one empty field. A quoted comma stays content, and a doubled quote must become one quote. Output is exact bytes with a final LF per line. Historical evidence data/raw/task3-sft-v2/authoring/final-verification/execution.private.json key V2E01-C1; selected test indices 0,1,3,4,6,7,8,9,11,12,13. The source satisfies valid CSV parsing and byte formatting; nonempty edge-case taxonomy and generic fault status are a false alarm, although status-only L1 form is appropriate. Actual response: {"taxonomy_error": ["Lỗi edge case"], "feedback": "Bài làm còn có lỗi cần kiểm tra."}. Mechanical code evidence status=absent.

> Bài làm còn có lỗi cần kiểm tra.

**v3**: status `valid`, joint `pass`; review: Source-grounded agent review, not independent human gold. Source V2E01-C1: The quote-state scan treats commas as separators only outside quoted fields; inside quotes it decodes a doubled quote to one literal quote and skips the second source character. Every completed field and the final field are emitted, preserving empty/trailing fields and spaces. Essential conditions: Input is guaranteed valid CSV, length at most 100 ASCII bytes; no invalid-CSV validation is required. Empty input is one empty field. A quoted comma stays content, and a doubled quote must become one quote. Output is exact bytes with a final LF per line. Historical evidence data/raw/task3-sft-v2/authoring/final-verification/execution.private.json key V2E01-C1; selected test indices 0,1,3,4,6,7,8,9,11,12,13. This response gives a supported, consistent assessment of the actual source. Its explanation/hint (where supplied) agrees with the mechanism; clean truthful status needs no invented defect/repair. Disclosure is appropriate at this Level and code absence alone is not penalized at L4. Actual response: {"taxonomy_error": [], "feedback": "Bài làm đáp ứng yêu cầu của đề."}. Mechanical code evidence status=absent.

> Bài làm đáp ứng yêu cầu của đề.

- `V2E01-C2-L1` (clean); xem [final casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/final-paired-casebook.html#V2E01-C2-L1).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <bits/stdc++.h>
2: using namespace std;
3: int main(){
4:     string s; getline(cin,s); vector<string> values; size_t pos=0;
5:     for(;;){
6:         string out;
7:         if(pos<s.size() && s[pos]=='"'){
8:             ++pos;
9:             while(pos<s.size()){
10:                 if(s[pos]!='"'){out+=s[pos++];}
11:                 else if(pos+1<s.size() && s[pos+1]=='"'){out.push_back('"');pos+=2;}
12:                 else {++pos;break;}
13:             }
14:         } else while(pos<s.size() && s[pos]!=',') out+=s[pos++];
15:         values.push_back(out);
16:         if(pos==s.size()) break;
17:         ++pos;
18:     }
19:     cout<<values.size()<<'\n';
20:     for(auto v:values)cout<<v.length()<<':'<<v<<'\n';
21: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v3/sources/V2E01-C2.cpp: Unsupported edge-case alarm: the clean cursor parser retains initial, interior and trailing empty fields, including the empty line as one empty field.

> Bài làm còn có lỗi cần kiểm tra.

**v3**: status `valid`, joint `pass`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v3/sources/V2E01-C2.cpp: Truthful clean status: quoted commas, doubled quotes and empty fields are handled by the cursor branches, with exact length/content output.

> Bài làm đáp ứng yêu cầu của đề.

- `V2E02-C1-L1` (clean); xem [final casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/final-paired-casebook.html#V2E02-C1-L1).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <bits/stdc++.h>
2: using namespace std;
3: int main(){
4:     string s,part;cin>>s; stringstream stream(s); int count=0; bool ok=s.back()!='.';
5:     while(getline(stream,part,'.')){
6:         ++count; bool local=!part.empty() && part.size()<=3;
7:         int value=0;
8:         for(char c:part){if(c<'0'||c>'9')local=false;else if(part.size()<=3)value=value*10+c-'0';}
9:         if(part.size()>1 && part[0]=='0') local=false;
10:         if(!(value<=255))local=false;
11:         ok=ok&&local;
12:     }
13:     cout<<(ok && count==4?"YES":"NO")<<'\n';
14: }
```

**v2**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. V2E02-C1; full source/specification and own canonical source review were checked. The source's component checks and sticky global validity satisfy the specification; this unsupported L1 error claim is a false alarm, although its status-only form is compliant.

> Bài làm còn có lỗi cần kiểm tra.

**v3**: status `valid`, joint `pass`; review: Source-grounded agent review, not independent human gold. V2E02-C1; full source/specification and own canonical source review were checked. Every component is nonempty, digit-only, <=3 digits, <=255 and canonically zero-formatted; exactly four components and no trailing dot are required. Clean L1 praise is supported.

> Bài làm đáp ứng yêu cầu của đề.

**Assessment regression**: 15 cặp target. Xếp example_id tăng dần, tối đa ba nguồn khác nhau; ví dụ mô tả, không phải mẫu đại diện thống kê.

- `V2E01-D1-L1` (faulty); xem [final casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/final-paired-casebook.html#V2E01-D1-L1).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <bits/stdc++.h>
2: using namespace std;
3: int main(){
4:     string s; getline(cin,s); vector<string> fields; string field; bool quoted=false;
5:     for(size_t i=0;i<s.size();++i){
6:         if(s[i]=='"'){
7:             if(quoted && i+1<s.size() && s[i+1]=='"'){field += ""; ++i;}
8:             else quoted=!quoted;
9:         } else if(s[i]==',' && !quoted){fields.push_back(field); field.clear();}
10:         else field+=s[i];
11:     }
12:     fields.push_back(field); cout<<fields.size()<<'\n';
13:     for(const string& f:fields) cout<<f.size()<<':'<<f<<'\n';
14: }
```

**v2**: status `valid`, joint `pass`; review: Source-grounded agent review, not independent human gold. V2E01-D1; full source/specification and own canonical source review were checked. Escaped-double-quote inputs form a supported conditional CSV case defect, so broad edge-case taxonomy is plausible. The text reports only faulty status, as L1 requires.

> Bài làm còn có lỗi cần kiểm tra.

**v3**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. V2E01-D1; full source/specification and own canonical source review were checked. False clean praise: escaped quote pairs are consumed by field += "" without emitting a decoded quote; historical test "a""b" loses the quote and prints length 2 instead of 3. L1 status form is compliant.

> Bài làm đáp ứng yêu cầu của đề.

- `V2E01-D2-L1` (faulty); xem [final casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/final-paired-casebook.html#V2E01-D2-L1).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <bits/stdc++.h>
2: using namespace std;
3: int main(){
4:     string s; getline(cin,s); vector<string> values; size_t pos=0;
5:     for(;;){
6:         string out;
7:         if(pos<s.size() && s[pos]=='"'){
8:             ++pos;
9:             while(pos<s.size()){
10:                 if(s[pos]!='"'){out+=s[pos++];}
11:                 else if(pos+1<s.size() && s[pos+1]=='"'){out.push_back(',');pos+=2;}
12:                 else {++pos;break;}
13:             }
14:         } else while(pos<s.size() && s[pos]!=',') out+=s[pos++];
15:         values.push_back(out);
16:         if(pos==s.size()) break;
17:         ++pos;
18:     }
19:     cout<<values.size()<<'\n';
20:     for(auto v:values)cout<<v.length()<<':'<<v<<'\n';
21: }
```

**v2**: status `valid`, joint `pass`; review: Source-grounded agent review, not independent human gold. Source V2E01-D2: The escaped-double-quote branch appends a comma instead of a literal double quote. Field lengths and field counts may remain correct, but decoded content is corrupted at every escaped quote. Essential conditions: A valid quoted field containing an escaped doubled quote is necessary and sufficient for a content mismatch here. Quoted fields containing commas without escaped quotes, empty fields, and unquoted fields are handled by otherwise valid parsing; these can mask the defect. Exact-byte output compares the corrupted quote/comma character even when decoded length is unchanged. Historical evidence data/raw/task3-sft-v2/authoring/final-verification/execution.private.json key V2E01-D2; selected test indices 3,4,6,8,10,11. This response gives a supported, consistent assessment of the actual source. Its explanation/hint (where supplied) agrees with the mechanism; clean truthful status needs no invented defect/repair. Disclosure is appropriate at this Level and code absence alone is not penalized at L4. Actual response: {"taxonomy_error": ["Lỗi edge case"], "feedback": "Bài làm còn có lỗi cần kiểm tra."}. Mechanical code evidence status=absent.

> Bài làm còn có lỗi cần kiểm tra.

**v3**: status `valid`, joint `fail`; review: Source-grounded agent review, not independent human gold. Source V2E01-D2: The escaped-double-quote branch appends a comma instead of a literal double quote. Field lengths and field counts may remain correct, but decoded content is corrupted at every escaped quote. Essential conditions: A valid quoted field containing an escaped doubled quote is necessary and sufficient for a content mismatch here. Quoted fields containing commas without escaped quotes, empty fields, and unquoted fields are handled by otherwise valid parsing; these can mask the defect. Exact-byte output compares the corrupted quote/comma character even when decoded length is unchanged. Historical evidence data/raw/task3-sft-v2/authoring/final-verification/execution.private.json key V2E01-D2; selected test indices 3,4,6,8,10,11. Full-correctness praise and empty taxonomy miss the escaped-quote corruption; disclosure is still status-only L1. Actual response: {"taxonomy_error": [], "feedback": "Bài làm đáp ứng yêu cầu của đề."}. Mechanical code evidence status=absent.

> Bài làm đáp ứng yêu cầu của đề.

- `V2E02-D1-L1` (faulty); xem [final casebook](../../outputs/task3/sft-v3-qlora-20261026-run1/final-paired-casebook.html#V2E02-D1-L1).

  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):

```cpp
1: #include <bits/stdc++.h>
2: using namespace std;
3: int main(){
4:     string s,part;cin>>s; stringstream stream(s); int count=0; bool ok=s.back()!='.';
5:     while(getline(stream,part,'.')){
6:         ++count; bool local=!part.empty() && part.size()<=3;
7:         int value=0;
8:         for(char c:part){if(c<'0'||c>'9')local=false;else if(part.size()<=3)value=value*10+c-'0';}
9:         if(part.size()>1 && part[0]=='0') local=false;
10:         if(!(value<=256))local=false;
11:         ok=ok&&local;
12:     }
13:     cout<<(ok && count==4?"YES":"NO")<<'\n';
14: }
```

**v2**: status `valid`, joint `pass`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v3/sources/V2E02-D1.cpp: Truthful faulty status, supported by 256.1.2.3 being accepted despite the required maximum 255; no cause/location is disclosed at L1.

> Bài làm còn có lỗi cần kiểm tra.

**v3**: status `valid`, joint `fail`; review: Source-grounded agent review; not independent human gold. data/raw/task3-sft-v3/sources/V2E02-D1.cpp: False clean status: 256.1.2.3 prints YES instead of NO.

> Bài làm đáp ứng yêu cầu của đề.

## Chi phí thực tế và phạm vi đo

Journal: 1120 primary reservations, 1120 completion keys; 2 smoke reservations, 2 smoke completion keys; 0 reservations chưa có completion. Reservations không đồng nghĩa chắc chắn đã chạy nếu bị ngắt; raw missing/invalid vẫn giữ nguyên.

| Pha | Wall s | Steps/calls | Input/full tokens | Output/completion tokens | Peak allocated GiB | Peak reserved GiB | Phạm vi |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Main training | 696.360 | 480 | 1319060 | 178852 | 10.803 | 11.537 | Main Trainer training interval only; checkpoint generation/loss evaluation occurs after train; one reset before train. |
| Smoke training | 5.778 | 4 | 11396 | 1536 | 10.305 | 11.492 | Chỉ khoảng Trainer smoke; không bao gồm reload/generation |
| Smoke generations | 1.441 | 2 | 1234 | 58 | không đo riêng | không đo riêng | Hai lần kiểm tra save/reload; không dùng cập nhật smoke cho main |
| Model loading | 17.380 | 3 | — | — | không đo riêng | không đo riêng | Không có đỉnh VRAM đo riêng cho nạp model; không gán đỉnh train/eval cho nạp. |
| base-dev | 105.110 | 80 | 49428 | 5466 | 8.531 | 10.717 | this evaluation phase |
| base-oracle-dev | 122.620 | 80 | 69116 | 6391 | 8.596 | 10.717 | this evaluation phase |
| v2-dev | 157.337 | 80 | 49428 | 5254 | 8.685 | 10.824 | this evaluation phase |
| v2-oracle-dev | 172.713 | 80 | 69116 | 7006 | 8.751 | 10.824 | this evaluation phase |
| v3-epoch1-dev | 160.088 | 80 | 49428 | 6638 | 8.685 | 10.824 | this evaluation phase |
| v3-epoch1-oracle-dev | 109.587 | 80 | 69116 | 4099 | 8.751 | 10.824 | this evaluation phase |
| v3-epoch2-dev | 163.259 | 80 | 49428 | 6685 | 8.685 | 10.824 | this evaluation phase |
| v3-epoch2-oracle-dev | 107.711 | 80 | 69116 | 3982 | 8.751 | 10.824 | this evaluation phase |
| base-final | 185.447 | 160 | 101792 | 11626 | 8.553 | 10.717 | this evaluation phase |
| v2-final | 262.716 | 160 | 101792 | 10074 | 8.706 | 10.824 | this evaluation phase |
| v3-selected-final | 366.609 | 160 | 101792 | 15219 | 8.706 | 10.824 | this evaluation phase |

| Evaluation | Generation calls | Generation s | Teacher-forced forwards | Teacher-forced s | Input tokens | Output tokens | TF completion tokens |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev | 640 | 1007.729 | 640 | 73.555 | 474176 | 45521 | 55592 |
| final | 480 | 751.761 | 480 | 43.767 | 305376 | 36919 | 43611 |

Không cộng thời gian stage với các pha con. Tổng pha là các phạm vi đã đo, không phải tổng GPU billing; đỉnh VRAM lấy max, không cộng. Chi phí review bằng agent không được telemetry GPU này đo.

Qwen được huấn luyện/sinh cục bộ, không gọi API thương mại cho các lượt Qwen. Không có đơn giá điện/thuê GPU hoặc telemetry chi phí/token của các agent Codex, nên không suy ra tổng chi phí tiền tệ.

Smoke: 4 optimizer steps, 2 generations; reload passed=True, max |logit difference|=0.0. Main dùng adapter mới; smoke updates bị bỏ, optimizer/scheduler/RNG khởi tạo lại theo bằng chứng `main-freshness.json`. Không yêu cầu mọi LoRA tensor có gradient khác không ở bước đầu.

Chi phí code audit (không Qwen, không semantic retry): {   "targets": 1120,   "statuses": {     "absent": 1002,     "not_evaluable": 39,     "compile_error": 17,     "authored_test_failure": 24,     "all_authored_tests_passed": 37,     "partial_or_unextractable": 1   },   "compile_calls": 78,   "runtime_calls": 840 }

## Cấu hình, checkpoint và bảo toàn

Phần cứng thực tế: {   "gpus": "NVIDIA GeForce RTX 5090, 32607 MiB, 590.48.01",   "torch": "2.8.0+cu128",   "cuda_build": "12.8",   "python": "3.12.3",   "selected_device": 0 }.

Pinned `Qwen/Qwen2.5-Coder-7B-Instruct` revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`. NF4 double quant/BF16; LoRA r16/alpha32/dropout0.05; q/k/v/o/gate/up/down. LR2e-5, AdamW weight_decay0, cosine/warmup0.03/clip1, batch1/accum4/seed42. Train8192 không packing/truncation, assistant-only loss gồm termination, equal-example mean/loss_weight1, remove_unused_columns=False. Evaluation32768, không đổi RoPE/tokenizer, greedy một lần; L1–3 tối đa1024, L4 tối đa1536, max_time45s. Actual arguments: `main/actual-training-arguments.json`; manifest lưu đủ giá trị và phiên bản thư viện.

| Checkpoint | Files trong identity | Identity SHA256 | Được chọn |
| --- | --- | --- | --- |
| 240 | 6 | 0963d1b1e59e636cc25a3e1e15e14e1889577d69dbde385b8e69157e2bb6d515 | Không |
| 480 | 6 | b351cfc574eac8492edfb6794b31a14a1aa58704b5b9ff6c6b17574b5c28242e | Có |

Manifest SHA256 `98b6a02afd7cdc5d1ce9fc7b758351a9736d7ae7cee4f5e8d3de6decd7e66db9`; selection SHA256 `40adb1d61db0ed147f59bbf41bdb157e49ccc1a154e4da5c7b72e6471fb93063`. HEAD `7ad8fd4a66b82f72579170618db3370eaf7dee14`, branch `fix/task3-strict-feedback`. Preservation-after passed=True; root predictions SHA256 `7fe92a9e5a99ab41c2bdc840c53e574793df8fa05aa0cc8e01e2c5d105cadcf8`. Initial file hashes và historical indices được giữ; báo cáo không sửa chúng.

Tất cả data/model/tokenizer/chat-template/code/adapter/checkpoint hashes, generation/state/review/code-evidence hashes và actual arguments được nhúng trong `analysis.json` hoặc identity/manifest được liên kết bằng SHA256. `analysis.json` giữ nguyên đầy đủ manifest và initial-workspace-state; các đối tượng này không được chỉnh sửa.

## Kiểm tra và lệnh tái lập

Bộ Task3 cuối: 1992 passed, 15 skipped trong 12.43s; safeguards liên quan: 37 passed trong 3.43s. Log: pytest-task3-final.log và pytest-final-relevant.log. Kiểm tra report tables/HTML/invalid coverage pass; regression bảo toàn dữ liệu khi xuất report đã quan sát RED rồi GREEN (audit/report-integrity-red.log và report-integrity-green.log).

Full pytest đã thử nhưng collection có 2 lỗi thiếu `sklearn` ở hai file Task1 (và 5 skipped); đây không phải bằng chứng toàn bộ repository pass. Log gốc: `pytest-full.log`. Script báo cáo kiểm tra đủ verdicts, population, manifest/selection seal, generation bindings và bảo toàn trước khi ghi; không chạy model/C++.

Các lệnh đã dùng theo thứ tự. Không chạy lại trên workspace đã hoàn tất: prepare cố ý từ chối dataset v3 đã tồn tại. Tái lập trong môi trường riêng cần source/spec/split, ba audit train, oracle audit đã đóng băng và initial-workspace-state mới hợp lệ trước prepare/freeze. Review thủ công bằng agent phải hoàn tất giữa packets và metrics/select; không có lệnh tự động tạo human gold:

```bash
cd /workspace/llm-final-project-arm-d-plus
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v3_prepare.py --out outputs/task3/sft-v3-qlora-20261026-run1
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v3_experiment.py freeze --out outputs/task3/sft-v3-qlora-20261026-run1
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v3_experiment.py train-dev --out outputs/task3/sft-v3-qlora-20261026-run1
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v3_review.py code --split dev --out outputs/task3/sft-v3-qlora-20261026-run1
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v3_review.py packets --split dev --out outputs/task3/sft-v3-qlora-20261026-run1
# Hoàn tất source-grounded agent review 640 dev targets vào quality/dev-*.json.
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v3_review.py metrics --split dev --out outputs/task3/sft-v3-qlora-20261026-run1
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v3_review.py select --out outputs/task3/sft-v3-qlora-20261026-run1
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v3_experiment.py final --out outputs/task3/sft-v3-qlora-20261026-run1
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v3_review.py code --split final --out outputs/task3/sft-v3-qlora-20261026-run1
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v3_review.py packets --split final --out outputs/task3/sft-v3-qlora-20261026-run1
# Hoàn tất source-grounded agent review 480 final targets vào quality/final-*.json.
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v3_review.py metrics --split final --out outputs/task3/sft-v3-qlora-20261026-run1
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v3_experiment.py verify --out outputs/task3/sft-v3-qlora-20261026-run1
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v3_report.py --out outputs/task3/sft-v3-qlora-20261026-run1
```

## Phụ lục: mọi mẫu số theo Level và clean/faulty

### dev

| Trạng thái | L | Clean n/nguồn | Faulty n/nguồn | Clean Level | Faulty Level | Clean false alarm / invalid | Faulty miss / invalid | Faulty diagnosis | Faulty L3 repair | Clean joint | Faulty joint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base-dev | 1 | 5/5 | 15/15 | 4/5 (80.0%) | 5/15 (33.3%) | 0 / 1 (n=5) | 11 / 2 (n=15) | 1/15 (6.7%) | 0/0 (không áp dụng) | 4/5 (80.0%) | 0/15 (0.0%) |
| base-dev | 2 | 5/5 | 15/15 | 2/5 (40.0%) | 7/15 (46.7%) | 3 / 2 (n=5) | 0 / 3 (n=15) | 2/15 (13.3%) | 0/0 (không áp dụng) | 0/5 (0.0%) | 2/15 (13.3%) |
| base-dev | 3 | 5/5 | 15/15 | 3/5 (60.0%) | 10/15 (66.7%) | 3 / 2 (n=5) | 0 / 2 (n=15) | 2/15 (13.3%) | 2/15 (13.3%) | 0/5 (0.0%) | 2/15 (13.3%) |
| base-dev | 4 | 5/5 | 15/15 | 3/5 (60.0%) | 13/15 (86.7%) | 2 / 2 (n=5) | 0 / 2 (n=15) | 6/15 (40.0%) | 0/0 (không áp dụng) | 1/5 (20.0%) | 6/15 (40.0%) |
| base-oracle-dev | 1 | 5/5 | 15/15 | 1/5 (20.0%) | 0/15 (0.0%) | 0 / 0 (n=5) | 0 / 0 (n=15) | 12/15 (80.0%) | 0/0 (không áp dụng) | 1/5 (20.0%) | 0/15 (0.0%) |
| base-oracle-dev | 2 | 5/5 | 15/15 | 5/5 (100.0%) | 3/15 (20.0%) | 0 / 0 (n=5) | 0 / 0 (n=15) | 9/15 (60.0%) | 0/0 (không áp dụng) | 5/5 (100.0%) | 2/15 (13.3%) |
| base-oracle-dev | 3 | 5/5 | 15/15 | 5/5 (100.0%) | 14/15 (93.3%) | 0 / 0 (n=5) | 0 / 0 (n=15) | 13/15 (86.7%) | 9/15 (60.0%) | 5/5 (100.0%) | 9/15 (60.0%) |
| base-oracle-dev | 4 | 5/5 | 15/15 | 5/5 (100.0%) | 15/15 (100.0%) | 0 / 0 (n=5) | 0 / 0 (n=15) | 11/15 (73.3%) | 0/0 (không áp dụng) | 5/5 (100.0%) | 10/15 (66.7%) |
| v2-dev | 1 | 5/5 | 15/15 | 5/5 (100.0%) | 15/15 (100.0%) | 3 / 0 (n=5) | 1 / 0 (n=15) | 13/15 (86.7%) | 0/0 (không áp dụng) | 2/5 (40.0%) | 13/15 (86.7%) |
| v2-dev | 2 | 5/5 | 15/15 | 1/5 (20.0%) | 8/15 (53.3%) | 5 / 0 (n=5) | 0 / 1 (n=15) | 2/15 (13.3%) | 0/0 (không áp dụng) | 0/5 (0.0%) | 2/15 (13.3%) |
| v2-dev | 3 | 5/5 | 15/15 | 3/5 (60.0%) | 8/15 (53.3%) | 5 / 0 (n=5) | 0 / 1 (n=15) | 5/15 (33.3%) | 1/15 (6.7%) | 0/5 (0.0%) | 1/15 (6.7%) |
| v2-dev | 4 | 5/5 | 15/15 | 3/5 (60.0%) | 11/15 (73.3%) | 3 / 2 (n=5) | 0 / 4 (n=15) | 2/15 (13.3%) | 0/0 (không áp dụng) | 0/5 (0.0%) | 2/15 (13.3%) |
| v2-oracle-dev | 1 | 5/5 | 15/15 | 4/5 (80.0%) | 3/15 (20.0%) | 0 / 0 (n=5) | 0 / 0 (n=15) | 12/15 (80.0%) | 0/0 (không áp dụng) | 4/5 (80.0%) | 3/15 (20.0%) |
| v2-oracle-dev | 2 | 5/5 | 15/15 | 5/5 (100.0%) | 0/15 (0.0%) | 0 / 0 (n=5) | 0 / 0 (n=15) | 7/15 (46.7%) | 0/0 (không áp dụng) | 4/5 (80.0%) | 0/15 (0.0%) |
| v2-oracle-dev | 3 | 5/5 | 15/15 | 5/5 (100.0%) | 14/15 (93.3%) | 0 / 0 (n=5) | 0 / 0 (n=15) | 9/15 (60.0%) | 7/15 (46.7%) | 4/5 (80.0%) | 7/15 (46.7%) |
| v2-oracle-dev | 4 | 5/5 | 15/15 | 5/5 (100.0%) | 15/15 (100.0%) | 0 / 0 (n=5) | 0 / 0 (n=15) | 5/15 (33.3%) | 0/0 (không áp dụng) | 4/5 (80.0%) | 5/15 (33.3%) |
| v3-epoch1-dev | 1 | 5/5 | 15/15 | 5/5 (100.0%) | 15/15 (100.0%) | 0 / 0 (n=5) | 5 / 0 (n=15) | 10/15 (66.7%) | 0/0 (không áp dụng) | 5/5 (100.0%) | 10/15 (66.7%) |
| v3-epoch1-dev | 2 | 5/5 | 15/15 | 5/5 (100.0%) | 12/15 (80.0%) | 0 / 0 (n=5) | 5 / 0 (n=15) | 2/15 (13.3%) | 0/0 (không áp dụng) | 5/5 (100.0%) | 2/15 (13.3%) |
| v3-epoch1-dev | 3 | 5/5 | 15/15 | 5/5 (100.0%) | 14/15 (93.3%) | 0 / 0 (n=5) | 5 / 0 (n=15) | 2/15 (13.3%) | 0/15 (0.0%) | 2/5 (40.0%) | 0/15 (0.0%) |
| v3-epoch1-dev | 4 | 5/5 | 15/15 | 4/5 (80.0%) | 11/15 (73.3%) | 0 / 1 (n=5) | 3 / 4 (n=15) | 1/15 (6.7%) | 0/0 (không áp dụng) | 2/5 (40.0%) | 1/15 (6.7%) |
| v3-epoch1-oracle-dev | 1 | 5/5 | 15/15 | 5/5 (100.0%) | 12/15 (80.0%) | 0 / 0 (n=5) | 0 / 0 (n=15) | 15/15 (100.0%) | 0/0 (không áp dụng) | 5/5 (100.0%) | 12/15 (80.0%) |
| v3-epoch1-oracle-dev | 2 | 5/5 | 15/15 | 5/5 (100.0%) | 3/15 (20.0%) | 0 / 0 (n=5) | 0 / 0 (n=15) | 10/15 (66.7%) | 0/0 (không áp dụng) | 5/5 (100.0%) | 3/15 (20.0%) |
| v3-epoch1-oracle-dev | 3 | 5/5 | 15/15 | 5/5 (100.0%) | 13/15 (86.7%) | 0 / 0 (n=5) | 0 / 0 (n=15) | 9/15 (60.0%) | 9/15 (60.0%) | 5/5 (100.0%) | 9/15 (60.0%) |
| v3-epoch1-oracle-dev | 4 | 5/5 | 15/15 | 5/5 (100.0%) | 15/15 (100.0%) | 0 / 0 (n=5) | 0 / 0 (n=15) | 6/15 (40.0%) | 0/0 (không áp dụng) | 5/5 (100.0%) | 6/15 (40.0%) |
| v3-epoch2-dev | 1 | 5/5 | 15/15 | 5/5 (100.0%) | 15/15 (100.0%) | 0 / 0 (n=5) | 2 / 0 (n=15) | 13/15 (86.7%) | 0/0 (không áp dụng) | 5/5 (100.0%) | 13/15 (86.7%) |
| v3-epoch2-dev | 2 | 5/5 | 15/15 | 5/5 (100.0%) | 8/15 (53.3%) | 0 / 0 (n=5) | 2 / 0 (n=15) | 3/15 (20.0%) | 0/0 (không áp dụng) | 5/5 (100.0%) | 3/15 (20.0%) |
| v3-epoch2-dev | 3 | 5/5 | 15/15 | 5/5 (100.0%) | 13/15 (86.7%) | 0 / 0 (n=5) | 2 / 0 (n=15) | 3/15 (20.0%) | 1/15 (6.7%) | 4/5 (80.0%) | 1/15 (6.7%) |
| v3-epoch2-dev | 4 | 5/5 | 15/15 | 4/5 (80.0%) | 12/15 (80.0%) | 0 / 1 (n=5) | 1 / 3 (n=15) | 3/15 (20.0%) | 0/0 (không áp dụng) | 2/5 (40.0%) | 3/15 (20.0%) |
| v3-epoch2-oracle-dev | 1 | 5/5 | 15/15 | 5/5 (100.0%) | 9/15 (60.0%) | 0 / 0 (n=5) | 0 / 0 (n=15) | 14/15 (93.3%) | 0/0 (không áp dụng) | 5/5 (100.0%) | 9/15 (60.0%) |
| v3-epoch2-oracle-dev | 2 | 5/5 | 15/15 | 5/5 (100.0%) | 7/15 (46.7%) | 0 / 0 (n=5) | 0 / 0 (n=15) | 10/15 (66.7%) | 0/0 (không áp dụng) | 5/5 (100.0%) | 6/15 (40.0%) |
| v3-epoch2-oracle-dev | 3 | 5/5 | 15/15 | 5/5 (100.0%) | 15/15 (100.0%) | 0 / 0 (n=5) | 0 / 0 (n=15) | 11/15 (73.3%) | 9/15 (60.0%) | 4/5 (80.0%) | 9/15 (60.0%) |
| v3-epoch2-oracle-dev | 4 | 5/5 | 15/15 | 5/5 (100.0%) | 15/15 (100.0%) | 0 / 0 (n=5) | 0 / 0 (n=15) | 10/15 (66.7%) | 0/0 (không áp dụng) | 5/5 (100.0%) | 9/15 (60.0%) |

### final

| Trạng thái | L | Clean n/nguồn | Faulty n/nguồn | Clean Level | Faulty Level | Clean false alarm / invalid | Faulty miss / invalid | Faulty diagnosis | Faulty L3 repair | Clean joint | Faulty joint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base-final | 1 | 20/20 | 20/20 | 18/20 (90.0%) | 16/20 (80.0%) | 0 / 0 (n=20) | 20 / 0 (n=20) | 0/20 (0.0%) | 0/0 (không áp dụng) | 18/20 (90.0%) | 0/20 (0.0%) |
| base-final | 2 | 20/20 | 20/20 | 17/20 (85.0%) | 15/20 (75.0%) | 19 / 0 (n=20) | 0 / 0 (n=20) | 3/20 (15.0%) | 0/0 (không áp dụng) | 1/20 (5.0%) | 2/20 (10.0%) |
| base-final | 3 | 20/20 | 20/20 | 15/20 (75.0%) | 6/20 (30.0%) | 20 / 0 (n=20) | 0 / 0 (n=20) | 3/20 (15.0%) | 2/20 (10.0%) | 0/20 (0.0%) | 2/20 (10.0%) |
| base-final | 4 | 20/20 | 20/20 | 20/20 (100.0%) | 20/20 (100.0%) | 17 / 0 (n=20) | 3 / 0 (n=20) | 2/20 (10.0%) | 0/0 (không áp dụng) | 3/20 (15.0%) | 2/20 (10.0%) |
| v2-final | 1 | 20/20 | 20/20 | 20/20 (100.0%) | 20/20 (100.0%) | 15 / 0 (n=20) | 4 / 0 (n=20) | 16/20 (80.0%) | 0/0 (không áp dụng) | 5/20 (25.0%) | 16/20 (80.0%) |
| v2-final | 2 | 20/20 | 20/20 | 14/20 (70.0%) | 9/20 (45.0%) | 19 / 0 (n=20) | 0 / 0 (n=20) | 2/20 (10.0%) | 0/0 (không áp dụng) | 1/20 (5.0%) | 1/20 (5.0%) |
| v2-final | 3 | 20/20 | 20/20 | 10/20 (50.0%) | 10/20 (50.0%) | 20 / 0 (n=20) | 0 / 0 (n=20) | 2/20 (10.0%) | 0/20 (0.0%) | 0/20 (0.0%) | 0/20 (0.0%) |
| v2-final | 4 | 20/20 | 20/20 | 19/20 (95.0%) | 19/20 (95.0%) | 18 / 1 (n=20) | 0 / 1 (n=20) | 0/20 (0.0%) | 0/0 (không áp dụng) | 1/20 (5.0%) | 0/20 (0.0%) |
| v3-selected-final | 1 | 20/20 | 20/20 | 20/20 (100.0%) | 20/20 (100.0%) | 1 / 0 (n=20) | 14 / 0 (n=20) | 6/20 (30.0%) | 0/0 (không áp dụng) | 19/20 (95.0%) | 6/20 (30.0%) |
| v3-selected-final | 2 | 20/20 | 20/20 | 20/20 (100.0%) | 18/20 (90.0%) | 3 / 0 (n=20) | 12 / 0 (n=20) | 1/20 (5.0%) | 0/0 (không áp dụng) | 16/20 (80.0%) | 1/20 (5.0%) |
| v3-selected-final | 3 | 20/20 | 20/20 | 19/20 (95.0%) | 20/20 (100.0%) | 3 / 0 (n=20) | 12 / 0 (n=20) | 0/20 (0.0%) | 0/20 (0.0%) | 15/20 (75.0%) | 0/20 (0.0%) |
| v3-selected-final | 4 | 20/20 | 20/20 | 18/20 (90.0%) | 18/20 (90.0%) | 2 / 2 (n=20) | 12 / 2 (n=20) | 0/20 (0.0%) | 0/0 (không áp dụng) | 4/20 (20.0%) | 0/20 (0.0%) |

### Phong cách tùy chọn, tách khỏi official Level

| Trạng thái | Median ký tự L1/L2/L3/L4 | Nguồn đủ 4 valid | Độ dài tăng nghiêm ngặt |
| --- | --- | --- | --- |
| base-dev | 59/128/200.0/215.0 | 12 | 2 |
| base-final | 44.0/158.5/167.5/245.0 | 40 | 14 |
| base-oracle-dev | 194.5/198.5/204.5/203.5 | 20 | 1 |
| v2-dev | 32.0/81/145/346.5 | 14 | 11 |
| v2-final | 32.0/81.0/115.0/296.0 | 38 | 23 |
| v2-oracle-dev | 111.0/204.0/227.0/282.0 | 20 | 5 |
| v3-epoch1-dev | 31.5/68.0/175.5/546 | 15 | 14 |
| v3-epoch1-oracle-dev | 32.0/128.5/152.0/163.5 | 20 | 3 |
| v3-epoch2-dev | 32.0/63.0/162.0/580.0 | 16 | 11 |
| v3-epoch2-oracle-dev | 32.0/89.0/163.5/170.0 | 20 | 2 |
| v3-selected-final | 31.0/70.0/179.0/687.0 | 36 | 36 |

Đếm câu trong analysis là xấp xỉ (có thể gặp dấu câu trong code); độ dài và thứ tự độ dài không làm pass/fail Level, không chọn checkpoint. Báo cáo/casebook giữ mọi invalid và phán quyết uncertain; hữu hạn test code không chứng minh mọi input đúng. Dữ liệu synthetic có thể không đại diện phân bố public; agent review và việc gold từng được xem hạn chế khả năng khái quát.

Công cụ hỗ trợ: Codex/GPT-6 viết mã, audit target và thực hiện source-grounded agent review; Qwen/Qwen2.5-Coder-7B-Instruct là mô hình được huấn luyện/đánh giá. Review là hậu kiểm thí nghiệm, không can thiệp hoặc sửa output suy luận.

Artifact: `analysis.json`, `dev-paired-casebook.html`, `final-paired-casebook.html` trong thư mục run; các casebooks hoạt động offline, không tải tài nguyên mạng.
