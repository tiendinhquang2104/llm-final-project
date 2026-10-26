# Tái lập và kiểm chứng Task3 SFT v2 public

Run đã hoàn tất: `outputs/task3/sft-v2-public-20261026-run1/`. Báo cáo: [TASK3_SFT_V2_PUBLIC_20261026.md](../reports/task3/TASK3_SFT_V2_PUBLIC_20261026.md). Partial320/328, không submit. Tám context failure không được retry hoặc điền thêm. Không train hay chọn lại checkpoint.

Từ worktree `/workspace/llm-final-project-arm-d-plus`, môi trường có sẵn:

```bash
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_public.py verify
/workspace/llm-final-project/.venv-task3/bin/python -m pytest -q tests/test_task3_sft_v2_public.py tests/test_task3_sft_v2_public_runtime.py tests/test_task3_sft_v2_public_compare.py tests/test_task3_sft_v2_posthoc.py tests/test_task3_sft_v2_report.py tests/test_task3_sft_v1_evaluation.py tests/test_task3_submission.py
```

Kiểm toàn bộ artifact cục bộ sau bàn giao (không gọi model/compiler):

```bash
cd outputs/task3/sft-v2-public-20261026-run1
sha256sum --check artifact-sha256.txt
```

`verify` đối chiếu freeze, source/tokenizer/code/checkpoint/selection, index và artifact lịch sử. `infer` có khóa process; trên run hoàn tất sẽ khôi phục từ journal và không load model/gọi lại. Reservation thiếu completion luôn còn uncertain, không tự thử lại. Không chạy `prepare` hoặc export đè run hiện có; các lệnh từ chối ghi đè artifact đã freeze/export.

Recipe tái lập từ đầu chỉ dùng khi được giao một lượt inference mới. Phải chọn output mới trong `outputs/task3`, lưu request và snapshot HEAD/branch/status/hash ban đầu cùng cấu trúc `initial-workspace-state.json` của run này; branch/HEAD/root predictions và artifact lịch sử phải khớp. Điểm vào:

Khởi tạo chính xác từ baseline đã bàn giao, chỉ khi đã được giao lượt mới:

```bash
/workspace/llm-final-project/.venv-task3/bin/python - <<'PY'
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from src.task3.sft_v1 import sha256
from src.task3.sft_v1_experiment import write_json
repo = Path.cwd()
old = repo / 'outputs/task3/sft-v2-public-20261026-run1'
new = repo / 'outputs/task3/NEW-RUN'
baseline = json.loads((old / 'initial-workspace-state.json').read_text())
head = subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip()
branch = subprocess.check_output(['git','branch','--show-current'], text=True).strip()
assert head == baseline['head'] and branch == 'fix/task3-strict-feedback'
assert sha256(repo / 'predictions.json') == baseline['root_predictions_sha256']
for name, expected in baseline['files'].items():
    assert sha256(repo / name) == expected, name
new.mkdir()  # Từ chối dùng lại thư mục cũ.
baseline.update(utc=datetime.now(timezone.utc).isoformat(), head=head, branch=branch,
                git_status=subprocess.check_output(['git','status','--short'], text=True))
write_json(new / 'initial-workspace-state.json', baseline)
(new / 'historical-verification-before.json').write_bytes(
    (old / 'historical-verification-before.json').read_bytes())
(new / 'request.txt').write_bytes((old / 'request.txt').read_bytes())
(new / 'ar15-audit').mkdir()
(new / 'ar15-audit/comparator-manifest.json').write_bytes(
    (old / 'ar15-audit/comparator-manifest.json').read_bytes())
PY
```

```bash
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_public.py prepare --out outputs/task3/NEW-RUN
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_public.py verify --out outputs/task3/NEW-RUN
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_public.py infer --out outputs/task3/NEW-RUN
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_public.py export --out outputs/task3/NEW-RUN
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_public_compare.py --out outputs/task3/NEW-RUN
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_public_costs.py --out outputs/task3/NEW-RUN
```

Không chạy các lệnh tạo lượt mới như phần kiểm chứng offline. `prepare` dùng native renderer/system/parser, official ZIP/requested mapping, local tokenizer pinned và sandbox compiler có sẵn; không mạng, không weights. Context8192 là guard thực tế trong native generation; không thay bằng context lịch sử A/R15. `infer` chỉ gọi mẫu đủ context, một lần, greedy, settings V2 giữ nguyên.

Tái tính hậu kiểm offline trên đích mới:

```bash
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_posthoc.py --historical-run outputs/task3/sft-v2-qlora-20261026-run1 --dataset data/raw/task3-sft-v2 --out outputs/task3/NEW-POSTHOC
```

Nguồn semantic review mới ở `review-progress/`; review cũ và đề xuất errata tách riêng. Casebook giữ full source/yêu cầu và nguyên phản hồi; A/B key chỉ dùng sau adjudication. Không có public gold hoặc public L4, không suy điểm/accuracy từ taxonomy transitions hoặc risk slice.
