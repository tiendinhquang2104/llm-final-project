# Task 3: ghép cặp NF4 và BF16 trên sáu real-val — 20/10/2026

## Kết luận

**Chưa có bằng chứng NF4 4-bit là nguyên nhân chính của blocker chất lượng.** BF16 thay đổi câu trả lời,
nhưng taxonomy của A/B hoàn toàn không đổi, các chẩn đoán sai vẫn tồn tại, B vẫn sinh tiếng Trung và
vi phạm Level 2. C BF16 còn dừng fail-closed ở mẫu cuối. Một phản hồi BF16 hữu ích bị adequacy screen
từ chối cho thấy lỗi của bộ kiểm tra cũng cần được phân biệt với lỗi sinh của model.

Không có cải thiện rõ, nhất quán để kích hoạt thử BF16 trên development rộng hơn trong vòng này.
Không chạy heldout/public, không training, không nộp leaderboard, không push. Sáu ca đã được xem nhiều
lần chỉ là phép chẩn đoán development; không suy ra precision không có ảnh hưởng ở mọi dữ liệu.

## Code, cấu hình và điều kiện ghép cặp

- Bắt đầu tại `aac8c3420ce61714ee64f999290ca37b49d11bcd`, branch `feat/task3-quality-round5`, working tree sạch.
- `d675d9611965d6069a31d81ed4bcf9a85c4c9853`: BF16 loader, kiểm tra dtype/device/revision, telemetry và test.
- `154d83880d1a872641ae02c28a4085ad8af41a03`: lưu run manifest cả khi inference fail-closed.
- **Cả sáu run chính thức dùng cùng commit `154d83880d1a872641ae02c28a4085ad8af41a03`.**
  Thứ tự C NF4 → C BF16 → A NF4 → A BF16 → B NF4 → B BF16; mỗi run là một process riêng, tuần tự.
- NF4: `configs/task3/self_diagnosis_zero_shot_round10.yaml`.
  BF16: `configs/task3/self_diagnosis_zero_shot_round10_bf16.yaml`, kế thừa NF4 và chỉ đổi `load_in_4bit: false`.
  Test và audit resolved config xác nhận chỉ trường này khác nhau trong từng cặp.
- Cùng Qwen/Qwen2.5-Coder-7B-Instruct, revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`.
  Tokenizer Qwen2TokenizerFast, cùng revision và chat-template SHA-256
  `cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f`.
- Manifest development giữ nguyên:
  `b311193f5c9fcf683019b1ae97c6e1017cfb4572cbcc1f3dfe2a3d9f3a753ee0`.
  `verify_prepared` xác minh các partition checksum; không prepare lại hoặc sửa dữ liệu/gold.
- Thứ tự ID ở mọi run: EX01-S106, EX01-S111, EX01-S112, EX02-S201, EX02-S211, EX02-S212.
  Seed 42, greedy, context 8192, output 512 tokens, diagnosis 384 tokens, K=0, tối đa hai retry,
  prompt policy 7, guard 2; không sửa prompt, guard, retry, taxonomy hay cơ chế chọn few-shot.
- C dùng gold để cô lập feedback; A tự diagnosis và B tự dự đoán, **không nhận gold**.
  Taxonomy giữ đúng 10 nhóm; không đổi gold hoặc ánh xạ để tăng điểm.

Audit prompt: C có initial messages byte-equivalent trên 6/6 ID. B dùng cùng builder/record/compiler
status; tokenizer audit bằng nhau hoàn toàn và initial messages được dựng lại/hash riêng tư từ cùng
đầu vào. A có initial diagnosis prompt bằng nhau trên 6/6 ID. Feedback prompt A khác ở ba ID EX01-S106,
EX01-S111, EX01-S112 do **diagnosis audit do mỗi model tự sinh**, mặc dù taxonomy cuối cùng đều rỗng.
Ba ID còn lại có initial feedback messages bằng nhau. Vì vậy A là cặp end-to-end cùng đầu vào bên ngoài,
không phải phép cô lập feedback với mọi prompt trung gian giống nhau; **C mới là đối chứng feedback
có prompt được giữ cố định hoàn toàn**. Retry algorithm/giới hạn giữ nguyên; số lần và hint cụ thể có
thể khác do response/validation outcome của model.

Lần kiểm tra đầu tại `d675d96` phát hiện C BF16 fail-closed làm mất peak VRAM vì CLI chưa ghi failure
manifest. Sau test tái hiện, chỉ thêm lưu telemetry khi exception rồi rethrow; không sửa validation.
Toàn bộ sáu run được chạy lại tại `154d838` vào thư mục mới. Raw feedback attempts của cả sáu run,
raw diagnosis attempts của A, và predictions/prefix của lần đầu so với lần chính thức **giống nhau**.
Artifacts đầu không bị ghi đè; chỉ dùng lần chính thức cho bảng runtime dưới đây.

## Xác minh precision và GPU

RTX 5090, 32.607 MiB, driver 590.48.01; Python 3.12.3, torch 2.8.0+cu128, CUDA runtime 12.8,
transformers 4.57.1, tokenizers 0.22.2, bitsandbytes 0.48.1. Model snapshot/cache dùng chung đúng pin.

| Thuộc tính | NF4 | BF16 |
|---|---|---|
| Load | Giữ nguyên BitsAndBytes NF4 double quantization | Không có quantization config; truyền `dtype=torch.bfloat16` tường minh |
| Dtype thực đo | Packed quantized storage `torch.uint8`; phần không lượng tử hóa `torch.float16`; Linear4bit compute BF16 | Toàn bộ 7.615.616.512 phần tử tham số `torch.bfloat16` |
| Quantization thực tế | `is_loaded_in_4bit=true` | `is_loaded_in_4bit=false` |
| Device thực tế | Mọi tham số trên `cuda:0` | Mọi tham số trên `cuda:0` |
| Offload | Không CPU/disk | Không CPU/disk; loader từ chối nếu dtype/device/revision không khớp |
| Revision thực tế | Đúng pin | Đúng pin |

NF4 ở đây là cấu hình mixed storage vốn có; không tự đổi phần không lượng tử hóa sang BF16 để làm
đối chứng khác với baseline. Đây là so sánh hai chế độ precision thực tế, không cô lập riêng từng nguồn
sai số số học bên trong NF4. Manifest ghi requested/actual precision, dtype/device counts, compute dtype,
resolved revision và peak allocator để không nhận nhầm artifact.

Không có OOM hoặc đổi model. GPU memory nền ngoài process thay đổi từ khoảng 4.490 MiB xuống 18 MiB
trong thời gian thực nghiệm; không dừng workload khác. Peak bên dưới là **PyTorch allocator của process**,
không phải peak tổng VRAM của mọi process trên host. Latency có synchronize CUDA; wall time gồm load
và overhead. Thứ tự chạy cố định, cache và workload nền khác nhau: không coi wall-time này là benchmark
tốc độ có kiểm soát hoặc quy toàn bộ chênh lệch thời gian cho precision.

## Kết quả và runtime

| Nhánh / precision | Hoàn tất | Fallback | Taxonomy macro / micro F1; exact | Peak allocated / reserved (MiB) | Feedback mọi attempts (s) | Diagnosis mọi attempts (s) | Wall (s) |
|---|---:|---|---|---:|---:|---:|---:|
| C NF4 | 6/6 | 0/6 | Gold input, không chấm taxonomy model | 6744,0 / 6878,0 | 9,717 | — | 18,630 |
| C BF16 | 5/6; dừng S212 | 1/5 prefix; không phải tỷ lệ toàn split | Không chấm; không có full export | 14988,1 / 15380,0 | 16,630 | — | 20,709 |
| A NF4 | 6/6 | 1/6 | 0 / 0; 2/6 | 6744,0 / 6870,0 | 8,446 | 29,954 | 47,082 |
| A BF16 | 6/6 | 1/6 | 0 / 0; 2/6 | 15052,9 / 15772,0 | 8,184 | 27,394 | 39,592 |
| B NF4 | 6/6 | 0/6 | 0,040 / 0,167; 0/6 | 6744,0 / 6814,0 | 4,473 | — | 13,139 |
| B BF16 | 6/6 | 0/6 | 0,040 / 0,167; 0/6 | 15050,3 / 15716,0 | 6,015 | — | 9,870 |

C BF16 đã sinh cả ba attempts cho S212 nhưng không có accepted final output ở ID đó. Không tính điểm
toàn split hoặc lấy gold taxonomy làm điểm model. Feedback time C BF16 bao gồm cả ba attempts bị từ chối.
A/B taxonomy bằng nhau theo từng ID giữa NF4/BF16, không chỉ bằng nhau về aggregate:

| ID | A ở cả hai precision | B ở cả hai precision | Đối chiếu gold không đổi |
|---|---|---|---|
| EX01-S106 | Rỗng | Lỗi logic | Thiếu Lỗi vòng lặp |
| EX01-S111 | Rỗng | Lỗi nhập/xuất | Gold Lỗi biên dịch |
| EX01-S112 | Rỗng | Lỗi nhập/xuất | Gold Lỗi hard-code |
| EX02-S201 | Rỗng | Lỗi logic | Gold rỗng |
| EX02-S211 | Rỗng | Lỗi logic | Gold rỗng |
| EX02-S212 | Rỗng | Lỗi logic | Gold Lỗi biên dịch + Lỗi vòng lặp |

Rỗng của A là prediction thực tế, không phải code sạch. Compiler vẫn unavailable; pipeline bỏ các compile
findings không có compiler evidence, và một số diagnosis bị từ chối do quote không chính xác. Không thêm
compiler trong vòng này để tránh thay đổi đầu vào bằng chứng của cặp precision. Hai gold rỗng không được
sửa theo ứng viên overflow/stdout đã ghi ở vòng trước.

## Review theo ID: raw generation, final output và guard

Đây là review nguồn của một agent trên development đã xem nhiều lần, không phải human review độc lập.
Bảng chỉ diễn giải findings, không chép source bài làm hoặc raw feedback vào Git. “An toàn” không đồng
nghĩa có độ phủ lỗi; fallback được tính là không cung cấp chẩn đoán hữu ích. Level ở đây là trần tiết lộ,
tách khỏi đúng sự thật, đủ hướng sửa và chất lượng tiếng Việt.

### C oracle — đối chứng feedback chính

| ID | NF4: raw → final | BF16: raw → final | Nhận định ghép cặp |
|---|---|---|---|
| EX01-S106 | Một attempt; phát hiện truy cập bounds có vấn đề nhưng bịa cấp phát n phần tử và câu chuyện previous-node | Một attempt; quy lỗi cho khởi tạo thay vì kích thước cấp phát, vẫn sai về previous-node | Cả hai causal diagnosis không đáng tin, cùng bỏ sót traversal không tiến; BF16 không sửa blocker |
| EX01-S111 | Một attempt; gọi biến đã khai báo là chưa khai báo | Một attempt; đổi sang một biến khác vốn cũng đã khai báo | Cùng sai chẩn đoán; không bao phủ các lỗi cú pháp/redeclaration thật |
| EX01-S112 | Ba attempts; hai lần repair/code disclosure bị từ chối; final nhận ra literal hard-code nhưng trộn tiếng Trung | Ba attempts có finding hard-code đúng kèm overclaim/diễn giải khác thiếu tin cậy và code/repair flags; final fallback | BF16 final an toàn hơn về ngôn ngữ do không còn nội dung; độ phủ final về 0, không tính là cải thiện |
| EX02-S201 | Một attempt; nói gần đúng và cần rà soát | Một attempt; cùng nhận xét, câu ngắn hơn | Không technical disclosure nhưng vẫn praise chưa được chứng minh; không giải thích được overflow candidate |
| EX02-S211 | Một attempt; gần đúng/cần rà soát | Một attempt; gần như cùng nội dung | Cùng không nhận diện stdout dư trong final; không có tín hiệu precision giải quyết lỗi |
| EX02-S212 | Hai attempts; bản đầu quá dài bị từ chối, bản cuối undeclared-bound diagnosis + hướng dùng digit count đúng | Ba attempts, không final: bản đầu diagnosis và hướng thay bound dùng được, guard disclosure pass nhưng adequacy từ chối; lần 2 full solution, lần 3 nhiều dòng code | Lần đầu là ứng viên false negative của adequacy screen; lần 2–3 là vi phạm disclosure thật. Không gọi tất cả là model không biết sửa; vẫn không có BF16 output hợp lệ toàn pipeline |

### A self-diagnosis — taxonomy và feedback end-to-end

| ID | NF4: raw → final | BF16: raw → final | Phủ lỗi / Level / tiếng Việt |
|---|---|---|---|
| EX01-S106 | Một attempt; cùng causal story sai như C | Một attempt; nói memory leak vì không giải phóng trong hàm trả pointer, chưa đủ căn cứ kết luận leak | Cùng bỏ sót lỗi traversal/allocation cốt lõi; đổi câu sai không tạo cải thiện rõ |
| EX01-S111 | Hai attempts: raw sai về allocation, có repair bị từ chối; final sai về index đã khởi tạo và trộn tiếng Trung | Ba attempts cùng claim index chưa khởi tạo; source-claim gate từ chối cả ba → fallback | BF16 raw vẫn sai. Final an toàn hơn nhờ guard, độ phủ 0; không quy cho model chẩn đoán tốt hơn |
| EX01-S112 | Ba attempts finding hard-code đúng nhưng repair leakage → fallback | Một attempt finding hard-code đúng, kèm lời nên thay literal bằng tham số; guard chấp nhận | BF16 tăng phủ lỗi nhưng vi phạm Level 2 lọt guard; không tính giảm fallback ở ID này thành thành công |
| EX02-S201 | Một attempt praise gần đúng | Một attempt praise gần đúng, ngắn hơn | Cùng unsupported praise, trần Level 1 giữ được; không có technical coverage |
| EX02-S211 | Một attempt praise gần đúng | Một attempt praise gần đúng, ngắn hơn | Cùng bỏ sót giải thích lỗi output; không có tín hiệu precision |
| EX02-S212 | Một attempt diagnosis undeclared bound và hướng đúng được chấp nhận | Ba attempts: đầu nhiều code; giữa đề nghị lấy original number làm digit count (sai), bị adequacy từ chối; cuối hướng đúng được chấp nhận | Final hữu ích ở cả hai; BF16 tốn retry và vẫn từng sinh hướng sửa sai |

### B independent direct — không có gold input

| ID | NF4 | BF16 | Review |
|---|---|---|---|
| EX01-S106 | Một attempt bịa pointer assignment | Một attempt nhận ra chỉ cấp phát một node nhưng quy kết pointer subscripting và đề xuất mảng pointer | Có quan sát thật hơn nhưng nguyên nhân/hướng sửa còn sai hoặc không phù hợp; lời sửa Level 2 lọt guard |
| EX01-S111 | Một attempt generic file/path advice | Một attempt generic đọc/phân tích CSV advice | Cùng bỏ qua compile defects và đưa hành động ở Level 2 |
| EX01-S112 | Một attempt tìm literal nhưng nêu sai expected filename | Hai attempts: finding đúng kèm repair bị từ chối; final chuyển phần explanation và repair sang tiếng Trung, guard chấp nhận | Chẩn đoán partial có thật, nhưng ngôn ngữ và trần Level 2 thất bại; không phải cải thiện sạch |
| EX02-S201 | Một attempt chỉ báo cần rà soát | Cùng câu cuối, một attempt | Level 1 đúng trần; generic flag có thể phù hợp với ứng viên lỗi nguồn, taxonomy vẫn sai so với gold |
| EX02-S211 | Một attempt chỉ báo cần rà soát | Cùng câu cuối, một attempt | Level 1 đúng trần; không có giải thích kỹ thuật theo thiết kế, taxonomy vẫn sai |
| EX02-S212 | Một attempt đúng undeclared bound nhưng nhầm quan hệ với original-number variable; hướng digit count đúng | Gần như cùng nội dung, một attempt | Cùng mixed diagnosis, hướng sửa dùng được, nhóm taxonomy vẫn sai |

Manual disclosure ceiling: A NF4 6/6, A BF16 5/6; B NF4 5/6, B BF16 3/6.
C NF4 6/6; C BF16 chỉ có 5 final prefix, không báo tỷ lệ accepted final toàn split.
Heuristic guard chấp nhận mọi final exported row ở cả hai precision; các vi phạm manual trên là guard miss.
Final có CJK: C NF4 1/6, C BF16 0/5 prefix; A NF4 1/6, A BF16 0/6; B NF4 0/6, B BF16 1/6.
Không gộp C prefix với split hoàn chỉnh hoặc dùng việc hết CJK do fallback để kết luận model tốt hơn.

### Latency feedback theo ID

Giây, cộng toàn bộ attempts, kể cả retry bị từ chối. A chưa bao gồm diagnosis trong bảng này
(diagnosis tổng riêng ở bảng runtime). C BF16 S212 không có accepted final dù đã tiêu tốn thời gian.

| ID | C NF4 / BF16 | A NF4 / BF16 | B NF4 / BF16 |
|---|---:|---:|---:|
| EX01-S106 | 1,626 / 1,212 | 1,701 / 0,637 | 1,426 / 1,915 |
| EX01-S111 | 0,522 / 0,513 | 1,378 / 2,249 | 0,677 / 0,655 |
| EX01-S112 | 3,204 / 7,241 | 3,369 / 0,590 | 0,680 / 1,742 |
| EX02-S201 | 0,372 / 0,269 | 0,375 / 0,269 | 0,430 / 0,418 |
| EX02-S211 | 0,363 / 0,260 | 0,368 / 0,261 | 0,429 / 0,417 |
| EX02-S212 | 3,631 / 7,136 | 1,255 / 4,179 | 0,831 / 0,867 |

## Kiểm chứng và bước tiếp theo

Test red/green cho BF16 explicit dtype, NF4 contract, từ chối CPU, config chỉ khác precision;
regression test xác nhận CLI fail-closed lưu precision manifest và không xuất predictions.
Suite Task 3 cuối code: **345 passed, 8 skipped**, zero failures. Các skip vẫn là 5 compiler cases,
1 portable toolchain, 1 opt-in GPU test, 1 datasets-dependent training test. Run GPU thực xác nhận
BF16/NF4 ở trên; test mock không được trình bày như phép đo GPU.

Validator offline pass trên cả **5/5 bundle hoàn chỉnh**, mỗi bundle đúng sáu ID/thứ tự/schema/nhãn;
C BF16 không có bundle hoàn chỉnh nên không được gán validator pass. Failure manifest vẫn ghi được peak
VRAM/dtype và không đổi exception/fail-closed. Không stage predictions, raw prompts/attempts, dữ liệu
hay checkpoint. Artifacts chính thức: ignored `outputs/task3/precision-pair-final/`; lần kiểm tra đầu:
ignored `outputs/task3/precision-pair/`. Audit riêng tư xác nhận commit, config diff, tokenizer, revision,
manifest, ordered IDs, initial prompt equality và stable raw outputs giữa hai lần.

**Precision không giải thích được blocker chính trong phép thử này.** Bước sau nên ưu tiên bằng chứng
nguồn và validation trên train: compiler syntax-only cho các claim compile; kiểm tra chẩn đoán có trích
dẫn đúng và không bịa trạng thái khai báo/khởi tạo; fixtures train-only cho JSON, Level-2 repair đa ngôn
ngữ và adequacy Level 3 có hướng sửa hợp lệ. Cần đánh giá riêng false negative của adequacy trước khi
thay đổi nó; không nới guard để hợp thức hóa các lần full-solution disclosure hoặc hướng sửa sai.
Đây là đề xuất cho vòng sau, chưa triển khai ở vòng precision này. Phương pháp vẫn chưa đủ điều kiện freeze.

## Lệnh tái hiện

Dùng output prefix mới. Mọi command dưới đây chỉ real-val, không public; giữ nguyên dữ liệu chuẩn bị.

```bash
cd /workspace/llm-final-project
export HF_HOME="$PWD/outputs/task3/hf-cache"
.venv-task3/bin/python -m pytest tests/test_task3_*.py -q -rs
for arm in oracle pipeline direct; do
  for precision in nf4 bf16; do
    cfg=configs/task3/self_diagnosis_zero_shot_round10.yaml
    if [ "$precision" = bf16 ]; then
      cfg=configs/task3/self_diagnosis_zero_shot_round10_bf16.yaml
    fi
    if [ "$arm" = direct ]; then
      .venv-task3/bin/python scripts/run_task3_direct_baseline.py --config "$cfg" --split real-val --output "outputs/task3/repro-precision-$arm-$precision.json"
    else
      source=gold
      if [ "$arm" = pipeline ]; then source=self-diagnosis; fi
      .venv-task3/bin/python scripts/run_task3.py --config "$cfg" --split real-val --taxonomy-source "$source" --output "outputs/task3/repro-precision-$arm-$precision.json"
    fi
  done
done
```

C BF16 có thể trả exit 1 do fail-closed; không thêm `set -e` nếu muốn tiếp tục các nhánh độc lập.
Kiểm tra validator chỉ với full export qua `src.task3.submission.validate_submission`, dùng map ID/Level
đọc trực tiếp từ `load_prepared('data/processed/task3', 'real-val')`; không cần requested-level public file.
