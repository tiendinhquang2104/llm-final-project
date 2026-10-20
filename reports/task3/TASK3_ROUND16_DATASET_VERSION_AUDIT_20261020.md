# Round 16 — audit dataset v1/v2 trên output cố định, 20/10/2026

**Kết luận không đổi: không có winner.** Toàn bộ selection và F1 Round16 ban đầu dùng **v1**, được chứng minh bằng hash byte và tái tính TP/FP/FN, không suy từ tên thư mục. V2 chỉ được dùng ở lần chấm lại annotation trong audit này. Không inference, public inference, re-selection, đổi prompt/bank/control/predictions hoặc sửa verdict source/Level.

## Hash và chuỗi provenance

| Artifact | SHA-256 |
|---|---|
| ZIP dữ liệu gốc chứa v1 | `8c04e4e01be73952cb255fb5efd707c758205c19457fa651d944fc02780a3e1e` |
| v1 synthetic ZIP, member `data/generate-dataset.zip` trong ZIP gốc | `88eff95f2841efd061ab0203907f9142ad6a2a2b72e266a4d55043a50aedac9c` |
| v1 `generate-dataset/task3_feedback.json` | `122d3736634394741ea8eaddb89dd1f068e4d23cd037f380a94c35b67f04bf4f` |
| v2 `generate-dataset_v2.zip` | `3581498f3db9b55e8bef911609b7829d1928805e66d2956d36a2084b3ca190d0` |
| v2 `generate-dataset/task3_feedback.json` | `9b817d29a2eefab5f4767416b273484695f9746c7e9acd25d4ac2cd1d25672ba` |
| Prepared synthetic-train dùng để chọn24 và chấm F1 ban đầu | `27a00fddb3bf17b0ee6af7ebaac14ffdf3deb6bdc98ebc57233d6cf7aac789e4` |
| Prepared real-train dùng trong pool train/bank selection | `12f2e897c1e374233754bec187de87c903f2142a582e6ad5eb72b81c9f58b1b4` |
| Prepared manifest đối chiếu nguồn v1 | `b311193f5c9fcf683019b1ae97c6e1017cfb4572cbcc1f3dfe2a3d9f3a753ee0` |

ZIP v1 là archive synthetic **nằm trong ZIP gốc**, không phải hash của folder sau giải nén. V2 là byte ZIP được người dùng chỉ đường dẫn `/workspace/llm-final-project/generate-dataset_v2.zip`; archive mới không được giải nén đè dataset prepared. Cả hai có thư mục bên trong mang tên `generate-dataset/`, vì vậy tên thư mục không phân biệt được phiên bản.

Chuỗi bằng chứng: hash `task3_feedback.json` trong ZIP v1 khớp metadata synthetic của prepared manifest và file raw hiện có; hash prepared train khớp `partition_identity` trong **freeze.initial.json** trước inference; cả24 nhãn/code/Level trong prepared khớp v1 archive. Tái tính đủ TP/FP/FN và micro/macro F1 từ annotation ZIP v1 khớp từng giá trị báo cáo Round16 đã commit. Do đó không có bằng chứng trộn v2 vào bước lựa chọn hoặc F1 gốc.

| Bước | Phiên bản thực dùng | Bằng chứng |
|---|---|---|
| Chọn24 ID theo Level/nhóm | v1 | Prepared synthetic-train SHA khớp initial freeze;24 gold khớp ZIP v1 |
| Chọn hai parent train và biên soạn bank giả | v1 | Cùng partition hash; tám parent source/statement hash checks đều pass |
| Render/query A/B/C/D | Source/đề/Level v1 | Cả24 code hash khớp v1; compiler/query cố định, không gold trong prompt |
| F1 common23 ban đầu | v1 | Rescore từ ZIP v1 khớp từng per-label TP/FP/FN và F1 gốc |
| Audit rescore v1 | v1 annotation, output cũ | Không gọi model; cùng common23 |
| Audit rescore v2 | v2 annotation, output cũ | Chỉ thay nhãn tham chiếu; không chọn lại ID hoặc đọc teacher feedback vào inference |

Cả24 ID có source byte, statement, problems, grading policy, exam ID và requested Level **giống hệt giữa v1/v2**. Compiler diagnostic và toàn bộ model input/raw/retry/final gốc giữ nguyên; không compile lại. Hash từng source và các phép so sánh nằm trong JSON provenance.

## Paired F1 v1-v2

Giữ nguyên24 ID; common23 loại đúng `SYN-REVSTR-0003` vì B/C không có final hợp lệ. Cả9 ID đổi nhãn đều còn trong common23. Bảng chấm **final taxonomy**, không parse lại raw hỏng hoặc tự thay bằng []. Raw/retry/final vẫn giữ byte nguyên vẹn. Macro lấy trung bình cố định trên **10 nhóm chính thức**, F1=0 khi mẫu số0, kể cả “Lỗi thuật toán” có support0 trong v2; không bỏ nhóm để tăng macro.

| Nhánh | Micro v1 | Micro v2 | Macro v1 | Macro v2 | Exact set v1 → v2 |
|---|---:|---:|---:|---:|---:|
| A — R15 control | 0.090909 | 0.205128 | 0.150000 | 0.172222 | 5/23 → 7/23 |
| B — one-shot | 0.083333 | 0.139535 | 0.109091 | 0.117391 | 1/23 → 3/23 |
| C — few-shot | 0.085106 | 0.142857 | 0.110000 | 0.119048 | 1/23 → 3/23 |
| D — evidence CoT | 0.153846 | 0.212766 | 0.129683 | 0.139624 | 2/23 → 4/23 |

**Mọi chênh lệch là do đổi annotation trên cùng prediction**, không phải model cải thiện hoặc evidence tốt hơn. Ví dụ B/C có thể trùng nhãn logic mới ở REVSTR nhưng counterexample feedback vẫn sai; hai hàm `return 0;` được v2 bỏ nhãn không chứng minh chúng tính đúng yêu cầu.

## Per-label trên common23 — v1

Mỗi ô nhánh là **TP / FP / FN**; support là số gold positive, dùng chung cho cả bốn nhánh.

| Nhóm | Support | A | B | C | D |
|---|---:|---:|---:|---:|---:|
| Lỗi biên dịch | 1 | 1 / 0 / 0 | 1 / 0 / 0 | 1 / 0 / 0 | 1 / 3 / 0 |
| Lỗi nhập/xuất | 2 | 1 / 1 / 1 | 0 / 1 / 2 | 0 / 2 / 2 | 1 / 1 / 1 |
| Lỗi logic | 1 | 0 / 16 / 1 | 1 / 20 / 0 | 1 / 18 / 0 | 1 / 16 / 0 |
| Lỗi vòng lặp | 1 | 0 / 0 / 1 | 0 / 0 / 1 | 0 / 0 / 1 | 0 / 1 / 1 |
| Lỗi mảng/chuỗi | 5 | 0 / 0 / 5 | 0 / 0 / 5 | 0 / 0 / 5 | 1 / 1 / 4 |
| Lỗi hàm | 3 | 0 / 0 / 3 | 0 / 0 / 3 | 0 / 0 / 3 | 0 / 0 / 3 |
| Lỗi edge case | 7 | 0 / 0 / 7 | 0 / 0 / 7 | 0 / 0 / 7 | 0 / 0 / 7 |
| Lỗi thuật toán | 1 | 0 / 0 / 1 | 0 / 0 / 1 | 0 / 0 / 1 | 0 / 0 / 1 |
| Lỗi hard-code | 3 | 0 / 0 / 3 | 0 / 0 / 3 | 0 / 0 / 3 | 0 / 0 / 3 |
| Lỗi style | 1 | 0 / 0 / 1 | 0 / 0 / 1 | 0 / 0 / 1 | 0 / 1 / 1 |
| Tổng label positives | 25 | 2 / 17 / 23 | 2 / 21 / 23 | 2 / 20 / 23 | 4 / 23 / 21 |

## Per-label trên common23 — v2

Mỗi ô nhánh là **TP / FP / FN**; support là số gold positive, dùng chung cho cả bốn nhánh.

| Nhóm | Support | A | B | C | D |
|---|---:|---:|---:|---:|---:|
| Lỗi biên dịch | 1 | 1 / 0 / 0 | 1 / 0 / 0 | 1 / 0 / 0 | 1 / 3 / 0 |
| Lỗi nhập/xuất | 2 | 1 / 1 / 1 | 0 / 1 / 2 | 0 / 2 / 2 | 1 / 1 / 1 |
| Lỗi logic | 2 | 2 / 14 / 0 | 2 / 19 / 0 | 2 / 17 / 0 | 2 / 15 / 0 |
| Lỗi vòng lặp | 3 | 0 / 0 / 3 | 0 / 0 / 3 | 0 / 0 / 3 | 0 / 1 / 3 |
| Lỗi mảng/chuỗi | 5 | 0 / 0 / 5 | 0 / 0 / 5 | 0 / 0 / 5 | 1 / 1 / 4 |
| Lỗi hàm | 1 | 0 / 0 / 1 | 0 / 0 / 1 | 0 / 0 / 1 | 0 / 0 / 1 |
| Lỗi edge case | 2 | 0 / 0 / 2 | 0 / 0 / 2 | 0 / 0 / 2 | 0 / 0 / 2 |
| Lỗi thuật toán | 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Lỗi hard-code | 3 | 0 / 0 / 3 | 0 / 0 / 3 | 0 / 0 / 3 | 0 / 0 / 3 |
| Lỗi style | 1 | 0 / 0 / 1 | 0 / 0 / 1 | 0 / 0 / 1 | 0 / 1 / 1 |
| Tổng label positives | 20 | 4 / 15 / 16 | 3 / 20 / 17 | 3 / 19 / 17 | 5 / 22 / 15 |

## Các tập nhãn thay đổi trong24 ID

**9 đổi,15 không đổi; không chọn lại ID.** Chỉ thay thứ tự nhãn không tính là thay tập.

| ID | Gold v1 | Gold v2 |
|---|---|---|
| SYN-PALIN-0008 | Lỗi nhập/xuất, Lỗi logic, Lỗi mảng/chuỗi | Lỗi mảng/chuỗi, Lỗi nhập/xuất |
| SYN-MAXDIFF-0002 | Lỗi hàm | [] |
| SYN-MINA-0005-L2 | Lỗi hàm | [] |
| SYN-REVSTR-0004-L2 | Lỗi edge case | Lỗi logic |
| SYN-SUMPAIR-0003 | Lỗi edge case | Lỗi logic |
| SYN-DISTINCT-0008-L3 | Lỗi edge case | Lỗi vòng lặp |
| SYN-SUMPAIR-0011 | Lỗi mảng/chuỗi, Lỗi edge case, Lỗi thuật toán | Lỗi vòng lặp, Lỗi mảng/chuỗi |
| SYN-DISTINCT-0016 | Lỗi edge case | Lỗi vòng lặp |
| SYN-SUMEVEN-0014 | Lỗi vòng lặp, Lỗi hard-code | Lỗi hard-code |

“24 bài đủ10 nhóm gold” **chỉ đúng với v1**. V2 có9 nhóm trên cả24 và common23; “Lỗi thuật toán” support0. Đã kiểm tra thêm toàn bộ612 record synthetic root và65 record heldout v2: đều không còn positive “Lỗi thuật toán”, trong khi label_space chính thức vẫn giữ đủ10 nhóm, hash không đổi. ID `SYN-SUMPAIR-0011` là record duy nhất mang nhóm này trong24 v1 và đã đổi sang vòng lặp+mảng/chuỗi. Không sửa gold, không bù ID khác.

## Giới hạn bank và kết luận nội dung

Bank có **8 mục theo Level nhưng chỉ2 source code và2 family độc lập**, từ parent `SYN-UPPER-0006`/`SYN-GCDARR-0007`. Cùng hai code giả lặp ở bốn Level; chỉ reference feedback/Level thay đổi. B chỉ thử một ví dụ uppercase có lỗi cho mỗi Level; C thử đúng cặp uppercase lỗi + GCD clean. Không có sweep nhiều source, nhiều lỗi hay nhiều cách chọn ví dụ. Không tuyên bố đã thử ví dụ đa dạng.

Kết quả chỉ mô tả **hai cấu hình ví dụ cố định** này. Không tách được hiệu ứng số shot khỏi nội dung ví dụ GCD được thêm vào; không đủ căn cứ kết luận tổng quát one-shot/few-shot, hoặc rằng bank đa dạng sẽ có cùng kết quả. Contamination đã quan sát ở bank hẹp vẫn có giá trị case study; causal attribution vẫn chỉ probable. Không đổi bank theo nhãn v2.

**Giữ nguyên verdict source/Level:** CoT có **23/47 finding bị bác bỏ**; few-shot có **hai Level3 repair hữu ích**, vẫn có false claims và một ID không hoàn tất. Source/đề/Level không đổi, nên đổi annotation không tự thay các verdict ấy. Không chuyển một claim source sai thành đúng vì nhãn mới trùng taxonomy model.

**Quyết định Round16 không đổi: không có winner; giữ R15 zero-shot làm control.** V2 chỉ cập nhật cách diễn giải taxonomy agreement và provenance; không cấp bằng chứng mới để chọn B/C/D thay A.

## Bảo toàn và kiểm tra

Đã hash và đối chiếu trước/sau **69 file được bảo vệ**: toàn bộ outputs/task3/round16 (bank,24 ID, raw/retry/final/checkpoint/manifest), prompt/runner/config A/B/C/D, hai public predictions, manual source/Level ledger, evidence ledger và source expectations. Không byte nào đổi. Không chạy inference, public, model loading, compiler, fine-tune, push hoặc leaderboard. Chỉ cập nhật báo cáo và provenance; số liệu Round16 gốc vẫn được giữ như kết quả v1 lịch sử.

Kiểm tra độc lập bằng công thức set trên archive labels tái hiện F1 v1; đối chiếu tiếp bằng hàm `taxonomy_metrics` hiện có cho v1/v2 trên cùng23 ID. Các assert yêu cầu đủ24 ID, cùng source/đề/Level, cùng common23,9 changed IDs, support thuật toán v2=0 và toàn bộ protected hashes không đổi. Không cần chạy lại model hoặc suite inference để cập nhật tài liệu.

[Provenance JSON đầy đủ](TASK3_ROUND16_DATASET_VERSION_AUDIT_20261020.json) có hash archive/metadata,24 nhãn v1/v2,23 ID, per-label metrics và69 protected hashes; chỉ là metadata, không chứa raw student source hoặc raw model output.

## Tái tính offline, không gọi model

Đoạn sau đọc trực tiếp hai ZIP và checkpoint final cũ; không ghi đè dataset/output:

```bash
.venv-task3/bin/python - <<'PY_AUDIT'
import io, json, zipfile
from dataclasses import replace
from pathlib import Path
from src.task3.dataset import load_prepared
from src.task3.round14_eval import taxonomy_metrics
root = Path('.')
audit = json.loads((root/'reports/task3/TASK3_ROUND16_DATASET_VERSION_AUDIT_20261020.json').read_text())
outer = zipfile.ZipFile(root/'data-20261017T044357Z-1-001.zip')
archives = {
    'v1': zipfile.ZipFile(io.BytesIO(outer.read('data/generate-dataset.zip'))),
    'v2': zipfile.ZipFile(root/'generate-dataset_v2.zip'),
}
common = set(audit['common23_ids'])
records = [r for r in load_prepared(root/'data/processed/task3', 'synthetic-train') if r.sample_id in common]
assert len(records) == 23
for version, archive in archives.items():
    metadata = json.loads(archive.read('generate-dataset/task3_feedback.json'))
    gold = {r['sample_id']: r['output']['taxonomy_error'] for r in metadata['samples']}
    scored = [replace(r, gold_taxonomy=gold[r.sample_id]) for r in records]
    for condition in ('control', 'one_shot', 'few_shot', 'evidence_cot'):
        state = json.loads((root/f'outputs/task3/round16/{condition}/progress.json').read_text())
        predictions = [{'sample_id': r.sample_id, 'output': state['completed'][r.sample_id]['output']} for r in scored]
        metrics = taxonomy_metrics(scored, predictions)
        print(version, condition, metrics['micro_f1'], metrics['macro_f1'])
        print(metrics['per_group'])
PY_AUDIT
```
