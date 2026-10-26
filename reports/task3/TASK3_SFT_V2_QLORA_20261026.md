# Thí nghiệm Task 3 SFT v2 QLoRA — 26/10/2026

Đã hoàn tất 240/240 bước optimizer, một epoch từ cùng base đã pin, sau smoke bốn bước được loại bỏ. Checkpoint được chọn bằng dev: **step 240**. Không có kết quả leaderboard mới trong thí nghiệm này.

Dữ liệu train giữ 160 source gốc và thêm đúng 40 cặp clean/faulty: **240 source / 960 target**, gồm 95 clean và 145 faulty. Ledger ghi **101 thay đổi target gốc** có bản trước/sau, lý do, bằng chứng và phiên bản; không đổi source hoặc đặc tả để giả làm sửa annotation.

Dev giữ nguyên 20 source/80 target; old test giữ nguyên 20/80 và chỉ là regression đã quan sát. Final mới gồm 10 family, 40 source/160 target; đóng băng trước generation, không dùng chọn checkpoint. Đây là dữ liệu synthetic được agent soạn, kiểm và review, không phải gold độc lập.

## So sánh trên cùng dữ liệu

Taxonomy micro F1 bên dưới là metric chẩn đoán **cục bộ**, không phải điểm Task 3 chính thức. Mẫu số gồm mọi target; invalid luôn là invalid, không được đổi thành dự đoán clean. Mỗi source có bốn Level phụ thuộc nhau.

| Split / state | Target / source | F1 cục bộ | Invalid | FA clean target | FA clean source | Joint thành công | L3 faulty sửa đúng | Code L4 qua test |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dev / ar15-dev | 80 / 20 | 0.3810 | 9/80 | 5/20 | 3/5 | 9/80 | 5/15 | 0/20 |
| dev / base-dev | 80 / 20 | 0.2500 | 0/80 | 3/20 | 3/5 | 13/80 | 2/15 | 0/20 |
| dev / v1-dev | 80 / 20 | 0.4480 | 3/80 | 13/20 | 5/5 | 20/80 | 0/15 | 6/20 |
| dev / step-120-dev | 80 / 20 | 0.2857 | 11/80 | 0/20 | 0/5 | 24/80 | 1/15 | 6/20 |
| dev / step-240-dev | 80 / 20 | 0.3111 | 10/80 | 0/20 | 0/5 | 28/80 | 1/15 | 7/20 |
| final / ar15-final | 160 / 40 | 0.4588 | 0/160 | 40/80 | 18/20 | 11/160 | 1/20 | 0/40 |
| final / base-final | 160 / 40 | 0.2136 | 0/160 | 9/80 | 9/20 | 38/160 | 1/20 | 0/40 |
| final / v1-final | 160 / 40 | 0.3939 | 1/160 | 56/80 | 17/20 | 27/160 | 1/20 | 2/40 |
| final / v2-final | 160 / 40 | 0.3519 | 8/160 | 6/80 | 2/20 | 61/160 | 2/20 | 11/40 |
| observed regression / base-regression | 80 / 20 | 0.1143 | 0/80 | 1/20 | 1/5 | 12/80 | 1/15 | 0/20 |
| observed regression / v1-regression | 80 / 20 | 0.4068 | 1/80 | 10/20 | 4/5 | 24/80 | 1/15 | 5/20 |
| observed regression / v2-regression | 80 / 20 | 0.3171 | 0/80 | 0/20 | 0/5 | 23/80 | 2/15 | 5/20 |

Joint yêu cầu cấu trúc hợp lệ, chẩn đoán có bằng chứng, vị trí/điều kiện thiết yếu khi áp dụng, đúng Level và tiếng Việt; faulty L3 thêm hướng sửa đúng, L4 thêm giải thích đúng và code qua kiểm hữu hạn. uncertain/not_evaluable không được tính pass. N/A được giữ riêng theo policy.

## Review từng trục và tính nhất quán

Review do agent đọc đặc tả, source và phản hồi thực; danh tính được che trong packet khi có thể. Không dùng keyword hoặc exact wording để chấm semantic. Casebook nhúng toàn bộ verdict và evidence đã hoàn tất, raw/parsed kể cả invalid, code L4 đã trích và kết quả compiler/runtime.

Đây là re-review theo protocol v2, kể cả các generations base/v1 được reuse nguyên trạng. Số review v1 lịch sử do người dùng nêu (diagnosis 29/80, Level 51/80, L3 1/20, code L4 5/20 trên old test) vẫn thuộc lượt review trước; chênh lệch verdict mới không phải thay đổi model hoặc raw output. Protocol hiện tại cho hướng L3 sai fail cả repair và Level, nên hai trục này không độc lập.

Review chỉ mù một phần: tên phương pháp được ẩn và panel đảo theo source, nhưng agent vẫn giữ lịch sử task và có vai trò author/reviewer. Không có human gold hay review độc lập; bất định và adjudication được giữ trong artifact.

| State | Diagnosis pass | Location pass / N/A | Không có defect vô căn cứ pass | Level pass | Tiếng Việt pass | Giải thích L4 pass | Code L4 đúng nhưng giải thích non-pass |
|---|---:|---:|---:|---:|---:|---:|---:|
| ar15-dev | 26/80 | 18 / 22 | 41/80 | 15/80 | 71/80 | 5/20 | 0 |
| base-dev | 38/80 | 20 / 30 | 66/80 | 30/80 | 80/80 | 9/20 | 0 |
| v1-dev | 28/80 | 4 / 24 | 40/80 | 37/80 | 77/80 | 4/20 | 5 |
| step-120-dev | 32/80 | 4 / 32 | 55/80 | 37/80 | 69/80 | 1/20 | 5 |
| step-240-dev | 33/80 | 13 / 26 | 59/80 | 51/80 | 70/80 | 5/20 | 3 |
| ar15-final | 32/160 | 9 / 48 | 64/160 | 25/160 | 158/160 | 3/40 | 0 |
| base-final | 72/160 | 9 / 80 | 130/160 | 63/160 | 160/160 | 14/40 | 0 |
| v1-final | 53/160 | 6 / 57 | 76/160 | 65/160 | 159/160 | 7/40 | 2 |
| v2-final | 67/160 | 14 / 76 | 128/160 | 102/160 | 152/160 | 8/40 | 4 |
| base-regression | 23/80 | 6 / 32 | 70/80 | 32/80 | 80/80 | 6/20 | 0 |
| v1-regression | 31/80 | 11 / 23 | 42/80 | 39/80 | 79/80 | 2/20 | 4 |
| v2-regression | 27/80 | 5 / 31 | 60/80 | 49/80 | 80/80 | 4/20 | 3 |

Mọi pass/fail/uncertain/not_applicable/not_evaluable theo từng Level nằm trong analysis.json; các cột pass giữ toàn bộ target làm mẫu số khi nêu tỷ lệ. L3 đúng và code L4 được tách riêng ở bảng trên. Bảng sau chỉ đo nhất quán taxonomy giữa bốn Level; nhất quán không đồng nghĩa chính xác.

| State | Source đủ bốn Level | Có invalid | Nhất quán và đủ/hợp lệ | Không nhất quán đủ/hợp lệ | Thiếu Level |
|---|---:|---:|---:|---:|---:|
| ar15-dev | 20/20 | 5 | 3 | 12 | 0 |
| base-dev | 20/20 | 0 | 4 | 16 | 0 |
| v1-dev | 20/20 | 2 | 8 | 10 | 0 |
| step-120-dev | 20/20 | 11 | 8 | 1 | 0 |
| step-240-dev | 20/20 | 10 | 10 | 0 | 0 |
| ar15-final | 40/40 | 0 | 7 | 33 | 0 |
| base-final | 40/40 | 0 | 18 | 22 | 0 |
| v1-final | 40/40 | 1 | 19 | 20 | 0 |
| v2-final | 40/40 | 8 | 26 | 6 | 0 |
| base-regression | 20/20 | 0 | 10 | 10 | 0 |
| v1-regression | 20/20 | 1 | 3 | 16 | 0 |
| v2-regression | 20/20 | 0 | 13 | 7 | 0 |

## Chọn checkpoint và phạm vi so sánh

Điều kiện sơ bộ: FA clean target và invalid không vượt native base dev. Các bước đủ điều kiện: `[]`. Checkpoint step 240 **được chọn theo fallback và không đạt điều kiện sơ bộ để đề nghị nâng cấp**.

Trong nhóm đủ điều kiện, tối đa joint; hòa thì ít FA hơn, nhiều faulty-L3 đúng hơn, loss dev thấp hơn, rồi bước sớm hơn. Nếu không có bước đủ điều kiện, ít FA được ưu tiên trước joint, sau đó giữ các tiêu chí hòa còn lại. Quyết định được lưu và kiểm hash trước khi mở final outputs; final và old regression không đổi quyết định.

Native base, v1 và v2 dùng byte-identical prompt native cho mỗi case dùng chung, cùng parser và greedy/Level token/max_time policy. A/R15 là **system comparator lịch sử chính xác theo snapshot**: prompt/controller/parser/guard/fallback và tối đa ba lần gọi được giữ riêng; không gọi đây là so sánh chỉ thay adapter. Các khác biệt backend, EOS/context và mapping input được ghi nguyên trong manifest:

```json
{
  "runtime": "historical Round15 snapshot from original git blobs; import namespace only",
  "input_mapping": "new source/spec plus syntax-only compiler status; problems=[], grading_policy=None; no private witnesses",
  "backend": "original HFBackend, NF4 double quant BF16 compute; default nonquantized storage differs from prepared native profile",
  "policy": "original Vietnamese zero-shot prompt, parser, disclosure guard, at most3 attempts, deterministic L1/L2 fallback; context16384; original model EOS list",
  "administrative_adaptation": "reservation prompt digest corrected to historical runner.digest; shared global physical budget; scientific renderer/backend/controller unchanged"
}
```

## Recipe, hash và kiểm dữ liệu

Model `Qwen/Qwen2.5-Coder-7B-Instruct`, revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`, seed `42`. NF4 double quantization, BF16 compute; LoRA r16/alpha32/dropout0.05, q/k/v/o/gate/up/down; LR 2e-5, một epoch, batch1/accumulation4, max length8192, không packing/truncation, assistant-only equal-example mean loss weight1. V2 khởi tạo từ base, không tiếp tục adapter v1.

Cấu hình thực của Trainer, config frozen, model/tokenizer/code/data/checkpoint hashes và versions được giữ trong analysis.json và manifest.json. Cấu hình optimizer/scheduler/warmup/clipping thực:

```json
{
  "per_device_train_batch_size": 1,
  "gradient_accumulation_steps": 4,
  "learning_rate": 2e-05,
  "max_grad_norm": 1.0,
  "num_train_epochs": 1,
  "lr_scheduler_type": "cosine",
  "warmup_ratio": 0.03,
  "seed": 42,
  "remove_unused_columns": false,
  "optim": "adamw_torch",
  "skip_memory_metrics": true
}
```

Bằng chứng kiểm dữ liệu mới (private; không được đưa vào prompt):

```json
{
  "train": {
    "source_count": 80,
    "target_count": 320,
    "clean_count": 40,
    "faulty_count": 40,
    "verification_pass_count": 80,
    "repair_pass_count": 80,
    "bounded_runtime_cases": 771,
    "mechanisms": {
      "actual_use_before_initialization": 1,
      "helper_predicate_inversion": 1,
      "unit_step_cost_invariant": 1,
      "half_open_run_length": 1,
      "seen_state_persistence": 1,
      "digit_exponent_off_by_one": 1,
      "closed_endpoint_membership": 1,
      "word_transition_invariant": 1,
      "equal_range_endpoint_identity": 1,
      "multi_function_erase_omission": 1,
      "multi_function_definition_omission": 1,
      "exact_bytes_separator": 1,
      "unclosed_parenthesis_postcondition": 1,
      "checked_one_based_capacity": 1,
      "missing_program_entry_point": 1,
      "gcd_recursive_base_value": 1,
      "lcm_zero_identity": 1,
      "sieve_composite_elimination": 1,
      "product_partition_coverage": 1,
      "fibonacci_two_predecessors": 1,
      "digit_character_identity": 1,
      "reverse_vs_sort_order": 1,
      "adjacent_pair_scan_progress": 1,
      "run_terminator_exclusion": 1,
      "flat_input_row_mapping": 1,
      "transpose_coordinate_mapping": 1,
      "clockwise_coordinate_mapping": 1,
      "distinct_rank_initialization": 1,
      "domain_upper_endpoint": 1,
      "merge_multiplicity_preservation": 1,
      "closed_query_iterator_range": 1,
      "lower_bound_equality_condition": 1,
      "prior_frequency_order": 1,
      "product_sign_parity": 1,
      "fraction_sign_xor": 1,
      "gregorian_century_correction": 1,
      "zero_one_item_progress": 1,
      "unlimited_denomination_quantity": 1,
      "closed_interval_contact": 1,
      "unique_substring_stopping_condition": 1
    },
    "failed": [],
    "limits": "Finite deterministic tests; synthetic agent author/review; existing family identities and some standard algorithm patterns overlap intentionally; no independent human gold. Uninitialized-use runtime observations are not a deterministic witness.",
    "clean_sources_verified": 40,
    "faulty_sources_with_observed_runtime_failure": 37,
    "faulty_sources_with_link_failure": 2,
    "faulty_sources_with_uninitialized_diagnostic": 1,
    "uninitialized_runtime_policy": "Runtime outcomes of the uninitialized mutant are preserved as observations, excluded from deterministic wrong-answer/failure counts; the actual compiler diagnostic is its primary evidence.",
    "passed": true
  },
  "final": {
    "passed": true,
    "sources": 40,
    "targets": 160,
    "clean_sources": 20,
    "defective_sources": 20,
    "clean_all_tests_passed": 20,
    "faults_witnessed": 20,
    "l4_verified": 40,
    "repair_all_tests_passed": 40,
    "syntax_only_compile_calls": 40,
    "compile_link_calls": 40,
    "runtime_calls": 752,
    "elapsed_seconds": 28.830685092136264,
    "failures": [],
    "model_calls": 0,
    "independent_human_review": false,
    "runner": "src.task3.cpp_sandbox.CppSandbox",
    "template": "/workspace/llm-final-project/outputs/task3/round23-20261022/sandbox-template",
    "template_ready_sha256": "71fdd607f11792ec5a4f8fc9024e80cc8ece98ef498cc1f609941130882d6c2c",
    "confinement": "chroot + uid/gid/groups/capability drop + no_new_privs + seccomp allowlist + rlimits",
    "runtime_limits": {
      "wall_seconds": 2,
      "cpu_soft_seconds": 1,
      "cpu_hard_seconds": 2,
      "address_space_mib": 512,
      "processes": 1,
      "open_fds": 64,
      "output_file_bytes": 65536
    },
    "compiler_limits": {
      "wall_seconds": 10,
      "cpu_soft_seconds": 4,
      "cpu_hard_seconds": 5,
      "address_space_mib": 512,
      "processes": 4,
      "open_fds": 64,
      "output_file_bytes": 8388608
    },
    "evidence_separation": "Runtime witnesses, oracles, repairs, and author verdicts private; only syntax_only may be rendered as compiler input.",
    "limitation": "Finite bounded checks do not prove all-input correctness; synthetic agent-reviewed annotations, not independent gold."
  }
}
```

Kiểm overlap gồm exact/normalized/structural và review family. Không phát hiện exact duplicate mới theo screen; báo cáo lưu mọi near match và giới hạn. Cấu trúc/idiom thông dụng và sự tương đồng trong family train còn lại; kiểm hữu hạn và similarity heuristic không chứng minh độc lập ngữ nghĩa hoặc đúng tuyệt đối.

## Chi phí và bộ nhớ

```json
{
  "physical_reservations": 1038,
  "physical_ceiling": 1442,
  "fresh_native_primary_reservations": 720,
  "ar15_physical_reservations": 316,
  "ar15_logical_requests_with_attempts": 240,
  "ar15_internal_retries_reserved": 76,
  "smoke_reservations": 2,
  "completed_physical_calls": 1038,
  "reserved_without_completion": [],
  "completed_generation_wall_s": 1510.6765487194061,
  "completed_generation_output_tokens": 72876,
  "known_completed_generation_input_token_sum": 423948,
  "completion_events_missing_input_token_count": 316,
  "ar15_input_token_journal_limit": "A/R15 input tokens are retained in request reservations/generation rows; completion events alone may omit them.",
  "reused_states": [
    "base-dev",
    "base-regression",
    "v1-dev",
    "v1-regression"
  ],
  "whole_experiment_wall_s_available": false,
  "wall_scope": "Sum of completed physical generation latencies only; excludes loading, training, authoring, idle time and reused generation cost."
}
```

1280 record được trình bày trong casebook; trong đó các state dev và regression có reuse được ghi riêng. Budget logic gốc tối đa1120 gồm dev400, final640 và80 output v2 regression mới;160 output base/v1 regression lịch sử chỉ được trình bày thêm, không tính thành generation mới. Call budget frozen:

```json
{
  "logical_total": 1120,
  "verified_reuse": 160,
  "fresh_logical": 960,
  "native_primary": 720,
  "ar15_logical": 240,
  "ar15_attempts_per_request": 3,
  "ar15_physical": 720,
  "primary_physical": 1440,
  "smoke": 2,
  "physical_total": 1442
}
```

| State | Chi phí generation lịch sử được reuse? | Input / output token | Tổng / median giây generation | Mean loss |
|---|---|---:|---:|---:|
| ar15-dev | không | 85657 / 7804 | 100.9130 / 1.0269 | N/A |
| base-dev | có | 46308 / 3883 | 62.2288 / 0.6875 | 2.2238 |
| v1-dev | có | 46308 / 5741 | 124.4189 / 0.7381 | 0.9020 |
| step-120-dev | không | 46308 / 6089 | 131.3087 / 0.8443 | 1.0701 |
| step-240-dev | không | 46308 / 6447 | 136.8332 / 0.7856 | 1.0241 |
| ar15-final | không | 142317 / 15709 | 349.3101 / 1.7514 | N/A |
| base-final | không | 95552 / 7502 | 110.6869 / 0.5287 | 2.0827 |
| v1-final | không | 95552 / 10113 | 232.0439 / 0.6207 | 1.3884 |
| v2-final | không | 95552 / 13333 | 312.2143 / 0.9034 | 1.1594 |
| base-regression | có | 43520 / 3538 | 53.5251 / 0.4865 | 2.2451 |
| v1-regression | có | 43520 / 5486 | 124.9212 / 0.7653 | 0.9457 |
| v2-regression | không | 43520 / 5819 | 135.9713 / 0.9229 | 1.0638 |

Các chi phí generation trong state có reuse là chi phí lịch sử; không cộng vào chi phí mới. Tổng journal là latency các physical calls hoàn tất, không phải wall toàn thí nghiệm; không cộng thêm checkpoint eval đã nằm trong thời gian main. Reservation thiếu completion được giữ để thể hiện bất định, không âm thầm gọi lại.

Phạm vi thời gian/bộ nhớ main được ghi đúng như runtime đo:

```json
{
  "wall_s": 585.78618937172,
  "training_wall_excluding_checkpoint_evaluation_s": 300.8877201974392,
  "checkpoint_evaluation_wall_s": 284.89846917428076,
  "wall_measurement_scope": "Current main Trainer invocation; wall excluding evaluation subtracts both nested checkpoint callbacks in this invocation.",
  "peak_allocated_bytes": 11452375040,
  "peak_reserved_bytes": 12358516736,
  "peak_memory_scope": "Entire main Trainer interval in this process, including nested checkpoint evaluation; one reset before train.",
  "peak_counter_resets_this_invocation": 1,
  "trajectory_observed_peak_allocated_bytes": 11452375040,
  "trajectory_observed_peak_reserved_bytes": 12358516736,
  "trajectory_peak_scope": "Current whole-main interval plus persisted step-boundary peaks from earlier resumed intervals; an interrupted interval after its last journal entry is not recoverable.",
  "resumed_from_step": 0
}
```

Các peak từng eval và smoke nằm trong analysis.json và artifact gốc. Nếu có resume, peak quan sát từ interval trước lấy ở ranh giới journal; phần interval bị ngắt sau entry cuối không thể khôi phục. Không suy diễn chi phí tiền tệ khi không có đơn giá.

## Ví dụ có bằng chứng


Nhãn ví dụ FA đã sửa/mới xuất hiện chỉ xét taxonomy false alarm. Văn xuôi vẫn có thể chứa chẩn đoán vô căn cứ; đọc verdict và evidence đi kèm để đánh giá nội dung.

### Taxonomy false alarm clean đã sửa

`V2E01-C1-L1` (final), [casebook](/workspace/llm-final-project-arm-d-plus/outputs/task3/sft-v2-qlora-20261026-run1/final-paired.html#V2E01-C1-L1).

Đặc tả: Đọc một dòng CSV hợp lệ dài tối đa 100 ký tự ASCII. Bản ghi có ít nhất một trường; dòng rỗng là một trường rỗng. Trường không đặt trong nháy chỉ chứa chữ cái và dấu cách. Trường đặt trong nháy kép có thể chứa thêm dấu phẩy; dấu nháy kép bên trong được viết thành hai dấu nháy kép liên tiếp. Các trường cách nhau bằng dấu phẩy; không có ký tự ngoài trường nháy trước dấu phẩy. In số trường ở dòng đầu; mỗi dòng sau in độ dài trường đã giải mã, dấu hai chấm, rồi nội dung trường.
Nộp chương trình C++11 đầy đủ có main. Output phải khớp từng byte, gồm LF cuối mỗi dòng.

Source được đối chiếu:

```cpp
#include <bits/stdc++.h>
using namespace std;
int main(){
    string s; getline(cin,s); vector<string> fields; string field; bool quoted=false;
    for(size_t i=0;i<s.size();++i){
        if(s[i]=='"'){
            if(quoted && i+1<s.size() && s[i+1]=='"'){field += '"'; ++i;}
            else quoted=!quoted;
        } else if(s[i]==',' && !quoted){fields.push_back(field); field.clear();}
        else field+=s[i];
    }
    fields.push_back(field); cout<<fields.size()<<'\n';
    for(const string& f:fields) cout<<f.size()<<':'<<f<<'\n';
}
```

**v1-final** — status `valid`, joint `False`, L3 `not_applicable`, giải thích L4 `not_applicable`; code `N/A`.

Evidence: The source meets the valid-CSV and exact-output contract, so this faulty status is an unsupported clean false alarm; the brief L1 form itself is respected.

Trích phản hồi thực (tối đa1200 ký tự; bản đầy đủ trong casebook):

~~~~
Bài làm còn có lỗi cần kiểm tra.
~~~~

**v2-final** — status `valid`, joint `True`, L3 `not_applicable`, giải thích L4 `not_applicable`; code `N/A`.

Evidence: The quoted-state scan decodes doubled quotes, splits only unquoted commas, and pushes the final field. The concise clean L1 verdict is supported.

Trích phản hồi thực (tối đa1200 ký tự; bản đầy đủ trong casebook):

~~~~
Bài làm đáp ứng yêu cầu của đề.
~~~~

### Taxonomy false alarm clean mới xuất hiện

`V2E06-C1-L1` (final), [casebook](/workspace/llm-final-project-arm-d-plus/outputs/task3/sft-v2-qlora-20261026-run1/final-paired.html#V2E06-C1-L1).

Đặc tả: Đọc n (1<=n<=7), rồi n số nguyên trong [0,3], có thể trùng. In dãy nhỏ nhất theo thứ tự từ điển lớn hơn dãy đầu vào và có cùng đa tập phần tử. Nếu không tồn tại, in dãy nhỏ nhất của đa tập đó.
Nộp chương trình C++11 đầy đủ có main. Output so theo token, phân biệt hoa thường.

Source được đối chiếu:

```cpp
#include <bits/stdc++.h>
using namespace std;
int main(){
    int n;cin>>n;vector<int>a(n);for(int&x:a)cin>>x;
    next_permutation(a.begin(),a.end());
    for(int x:a)cout<<x<<' ';cout<<'\n';
}
```

**base-final** — status `valid`, joint `True`, L3 `not_applicable`, giải thích L4 `not_applicable`; code `N/A`.

Evidence: Chương trình đầy đủ dùng next_permutation hợp lệ C++11, cú pháp không lỗi; status biên dịch thành công phù hợp clean source và L1 chỉ status.

Trích phản hồi thực (tối đa1200 ký tự; bản đầy đủ trong casebook):

~~~~
Chương trình đã được biên dịch thành công.
~~~~

**v2-final** — status `valid`, joint `False`, L3 `not_applicable`, giải thích L4 `not_applicable`; code `N/A`.

Evidence: std::next_permutation đúng successor nhỏ nhất hoặc wrap nhỏ nhất, nên status lỗi là false alarm trên source clean; L1 form đúng.

Trích phản hồi thực (tối đa1200 ký tự; bản đầy đủ trong casebook):

~~~~
Bài làm còn có lỗi cần kiểm tra.
~~~~

### Hướng L3 đúng

`V2E06-D1-L3` (final), [casebook](/workspace/llm-final-project-arm-d-plus/outputs/task3/sft-v2-qlora-20261026-run1/final-paired.html#V2E06-D1-L3).

Đặc tả: Đọc n (1<=n<=7), rồi n số nguyên trong [0,3], có thể trùng. In dãy nhỏ nhất theo thứ tự từ điển lớn hơn dãy đầu vào và có cùng đa tập phần tử. Nếu không tồn tại, in dãy nhỏ nhất của đa tập đó.
Nộp chương trình C++11 đầy đủ có main. Output so theo token, phân biệt hoa thường.

Source được đối chiếu:

```cpp
#include <bits/stdc++.h>
using namespace std;
int main(){
    int n;cin>>n;vector<int>a(n);for(int&x:a)cin>>x;
    prev_permutation(a.begin(),a.end());
    for(int x:a)cout<<x<<' ';cout<<'\n';
}
```

**v2-final** — status `valid`, joint `True`, L3 `pass`, giải thích L4 `not_applicable`; code `N/A`.

Evidence: Replacing prev_permutation with next_permutation is a concrete correct operation that also implements required wrap to the minimum and handles duplicates. The short L3 hint gives useful direction without a full program.

Trích phản hồi thực (tối đa1200 ký tự; bản đầy đủ trong casebook):

~~~~
prev_permutation tìm một dãy nhỏ hơn theo thứ tự từ điển. Để tìm dãy lớn hơn, hãy dùng next_permutation thay.
~~~~

### Hướng L3 sai hoặc chưa chắc

`V2E01-D1-L3` (final), [casebook](/workspace/llm-final-project-arm-d-plus/outputs/task3/sft-v2-qlora-20261026-run1/final-paired.html#V2E01-D1-L3).

Đặc tả: Đọc một dòng CSV hợp lệ dài tối đa 100 ký tự ASCII. Bản ghi có ít nhất một trường; dòng rỗng là một trường rỗng. Trường không đặt trong nháy chỉ chứa chữ cái và dấu cách. Trường đặt trong nháy kép có thể chứa thêm dấu phẩy; dấu nháy kép bên trong được viết thành hai dấu nháy kép liên tiếp. Các trường cách nhau bằng dấu phẩy; không có ký tự ngoài trường nháy trước dấu phẩy. In số trường ở dòng đầu; mỗi dòng sau in độ dài trường đã giải mã, dấu hai chấm, rồi nội dung trường.
Nộp chương trình C++11 đầy đủ có main. Output phải khớp từng byte, gồm LF cuối mỗi dòng.

Source được đối chiếu:

```cpp
#include <bits/stdc++.h>
using namespace std;
int main(){
    string s; getline(cin,s); vector<string> fields; string field; bool quoted=false;
    for(size_t i=0;i<s.size();++i){
        if(s[i]=='"'){
            if(quoted && i+1<s.size() && s[i+1]=='"'){field += ""; ++i;}
            else quoted=!quoted;
        } else if(s[i]==',' && !quoted){fields.push_back(field); field.clear();}
        else field+=s[i];
    }
    fields.push_back(field); cout<<fields.size()<<'\n';
    for(const string& f:fields) cout<<f.size()<<':'<<f<<'\n';
}
```

**v2-final** — status `valid`, joint `False`, L3 `fail`, giải thích L4 `not_applicable`; code `N/A`.

Evidence: quoted và dấu phẩy phần lớn được xử lý đúng, nhưng thiếu ký tự nháy ở nhánh escape nên không thể kết luận không cần sửa. L3 không có thao tác thêm nháy vào field.

Trích phản hồi thực (tối đa1200 ký tự; bản đầy đủ trong casebook):

~~~~
Bài làm đáp ứng yêu cầu về phân tích các trường của bản ghi CSV. Vòng duyệt chuỗi duy trì trạng thái ngoặc nháy và tách các trường dựa trên dấu phẩy. Không có lỗi cần sửa.
~~~~

### Chẩn đoán thay đổi giữa Level

`V2E05-D2-L1` (final), [casebook](/workspace/llm-final-project-arm-d-plus/outputs/task3/sft-v2-qlora-20261026-run1/final-paired.html#V2E05-D2-L1).

Đặc tả: Đọc hai số nguyên a,b với -1000<=a<=1000, -30<=b<=30 và b khác 0. In floor(a/b), tức số nguyên lớn nhất không vượt thương toán học, kể cả khi thương âm.
Nộp chương trình C++11 đầy đủ có main. Output so theo token, phân biệt hoa thường.

Source được đối chiếu:

```cpp
#include <bits/stdc++.h>
using namespace std;
int main(){
    int a,b;cin>>a>>b;int A=abs(a),B=abs(b),result;
    if((a<0)==(b<0))result=A/B;
    else result=-A/B;
    cout<<result<<'\n';
}
```

**v2-final** — status `valid`, joint `True`, L3 `not_applicable`, giải thích L4 `not_applicable`; code `N/A`.

Evidence: Nhánh trái dấu -A/B chưa làm tròn xuống khi có dư nên có lỗi thật; thông báo trạng thái đúng và phù hợp L1.

Trích phản hồi thực (tối đa1200 ký tự; bản đầy đủ trong casebook):

~~~~
Bài làm còn có lỗi cần kiểm tra.
~~~~

Taxonomy từng Level: {"1": ["Lỗi logic"], "2": ["Lỗi logic"], "3": ["Lỗi logic"], "4": []}

### Code L4 qua test nhưng giải thích sai

`V2E04-C1-L4` (final), [casebook](/workspace/llm-final-project-arm-d-plus/outputs/task3/sft-v2-qlora-20261026-run1/final-paired.html#V2E04-C1-L4).

Đặc tả: Đọc w, k, x với 1<=w<=16, 0<=k<=100, 0<=x<2^w. Xem x là chuỗi nhị phân đúng w bit, kể cả các bit 0 đầu. Xoay vòng chuỗi sang trái k vị trí và in giá trị thập phân của chuỗi kết quả.
Nộp chương trình C++11 đầy đủ có main. Output so theo token, phân biệt hoa thường.

Source được đối chiếu:

```cpp
#include <bits/stdc++.h>
using namespace std;
int main(){
    unsigned w,k,x;cin>>w>>k>>x;k%=w;unsigned mask=(1u<<w)-1;
    unsigned answer=((x<<k)|(x>>(w-k)))&mask;
    cout<<answer<<'\n';
}
```

**v1-final** — status `valid`, joint `False`, L3 `not_applicable`, giải thích L4 `fail`; code `all_authored_tests_passed`.

Evidence: The supplied program is equivalent to the original and complete, so L4 form passes. Its explanation is false: width5 value8 is01000, not00010, and rotating it left2 gives00001=1, not20. Correct/equivalent code does not override these false diagnosis and numeric claims.

Trích phản hồi thực (tối đa1200 ký tự; bản đầy đủ trong casebook):

~~~~
Bài làm còn chứa lỗi về cách xoay chuỗi nhị phân. Ví dụ, với w=5, k=2, x=8 (bên phải là 00010), đáp án cần phải là 20 (bên phải là 10100). Tuy nhiên, đoạn mã thực hiện phép xoay sai. Để giải quyết vấn đề này, hãy áp dụng kỹ thuật xoay vòng trái trong phần tử biểu diễn số học. Dưới đây là bản sửa đổi phù hợp cho bài làm.

```cpp
#include <bits/stdc++.h>
using namespace std;
int main(){
    unsigned w,k,x;cin>>w>>k>>x;k%=w;unsigned mask=(1u<<w)-1;
    unsigned left=x>>(w-k);unsigned right=x<<(k);
    unsigned answer=(left|right)&mask;
    cout<<answer<<'\n';
}
```
~~~~

### Output invalid được giữ nguyên

`V2E01-D1-L4` (final), [casebook](/workspace/llm-final-project-arm-d-plus/outputs/task3/sft-v2-qlora-20261026-run1/final-paired.html#V2E01-D1-L4).

Đặc tả: Đọc một dòng CSV hợp lệ dài tối đa 100 ký tự ASCII. Bản ghi có ít nhất một trường; dòng rỗng là một trường rỗng. Trường không đặt trong nháy chỉ chứa chữ cái và dấu cách. Trường đặt trong nháy kép có thể chứa thêm dấu phẩy; dấu nháy kép bên trong được viết thành hai dấu nháy kép liên tiếp. Các trường cách nhau bằng dấu phẩy; không có ký tự ngoài trường nháy trước dấu phẩy. In số trường ở dòng đầu; mỗi dòng sau in độ dài trường đã giải mã, dấu hai chấm, rồi nội dung trường.
Nộp chương trình C++11 đầy đủ có main. Output phải khớp từng byte, gồm LF cuối mỗi dòng.

Source được đối chiếu:

```cpp
#include <bits/stdc++.h>
using namespace std;
int main(){
    string s; getline(cin,s); vector<string> fields; string field; bool quoted=false;
    for(size_t i=0;i<s.size();++i){
        if(s[i]=='"'){
            if(quoted && i+1<s.size() && s[i+1]=='"'){field += ""; ++i;}
            else quoted=!quoted;
        } else if(s[i]==',' && !quoted){fields.push_back(field); field.clear();}
        else field+=s[i];
    }
    fields.push_back(field); cout<<fields.size()<<'\n';
    for(const string& f:fields) cout<<f.size()<<':'<<f<<'\n';
}
```

**v1-final** — status `malformed_json`, joint `False`, L3 `not_evaluable`, giải thích L4 `not_evaluable`; code `not_evaluable`.

Evidence: Packet ghi malformed_json, không có feedback hợp lệ; toàn bộ bảy trục không đánh giá được.

Trích phản hồi thực (tối đa1200 ký tự; bản đầy đủ trong casebook):

~~~~
{"taxonomy_error":["Lỗi logic"],"feedback":"Bài làm còn có lỗi cần kiểm tra. Vui lòng xem xét các yêu cầu về định dạng của bản ghi CSV trong đề. Một ví dụ về lỗi có thể xuất hiện như sau:\n\nDữ liệu mẫu: \"abc\",\"def\"\nKết quả nhận được: 2:abc\n2:def\nKết quả đúng: 2:abc\n2:def\n\nBạn hãy tìm hiểu nguyên nhân gây ra sự khác biệt này và sửa lại phần xử lý trường trong đoạn mã.\n\nĐây là một gợi ý để bạn hoàn thiện phần xử lý trường trong đoạn mã:\n\nstring field;\nbool quoted = false;\nfor (size_t i = 0; i < s.size(); ++i) {\n    if (s[i] == \'"\') {\n        if (quoted && i + 1 < s.size() && s[i + 1] == \'"\') {\n            field += \"\";\n            ++i;\n        }\n        else {\n            quoted = !quoted;\n        }\n    }\n    else if (s[i] == ',' && !quoted) {\n        fields.push_back(field);\n        field.clear();\n    }\n    else {\n        field += s[i];\n    }\n}\nfields.push_back(field);\n\nTrong đoạn mã trên, chúng ta duyệt qua tất cả các ký tự trong chuỗi đầu vào. Nếu gặp dấu nháy kép, chúng ta kiểm tra xem nó có phải là cặp dấu nháy kép đặc biệt hay không. Nếu không phải, chúng ta chuyển đổi trạng thái giữa có đang trong chuỗi hoặc không. Nếu gặp dấu phẩy và 
~~~~

### A/R15 tốt hơn trên case

`V2E06-C1-L1` (final), [casebook](/workspace/llm-final-project-arm-d-plus/outputs/task3/sft-v2-qlora-20261026-run1/final-paired.html#V2E06-C1-L1).

Đặc tả: Đọc n (1<=n<=7), rồi n số nguyên trong [0,3], có thể trùng. In dãy nhỏ nhất theo thứ tự từ điển lớn hơn dãy đầu vào và có cùng đa tập phần tử. Nếu không tồn tại, in dãy nhỏ nhất của đa tập đó.
Nộp chương trình C++11 đầy đủ có main. Output so theo token, phân biệt hoa thường.

Source được đối chiếu:

```cpp
#include <bits/stdc++.h>
using namespace std;
int main(){
    int n;cin>>n;vector<int>a(n);for(int&x:a)cin>>x;
    next_permutation(a.begin(),a.end());
    for(int x:a)cout<<x<<' ';cout<<'\n';
}
```

**ar15-final** — status `valid`, joint `True`, L3 `not_applicable`, giải thích L4 `not_applicable`; code `N/A`.

Evidence: Source next_permutation đáp ứng đề cả duplicates và wrap; clean status chưa thấy lỗi phù hợp L1.

Trích phản hồi thực (tối đa1200 ký tự; bản đầy đủ trong casebook):

~~~~
Bài này chưa có lỗi rõ ràng.
~~~~

**v2-final** — status `valid`, joint `False`, L3 `not_applicable`, giải thích L4 `not_applicable`; code `N/A`.

Evidence: std::next_permutation đúng successor nhỏ nhất hoặc wrap nhỏ nhất, nên status lỗi là false alarm trên source clean; L1 form đúng.

Trích phản hồi thực (tối đa1200 ký tự; bản đầy đủ trong casebook):

~~~~
Bài làm còn có lỗi cần kiểm tra.
~~~~

## Nhận định và giới hạn

Giữ A/R15 hiện dùng. Các số đo final này chưa tạo bằng chứng đủ mạnh để thay hệ thống bằng v2; không mở thêm epoch, v3 hay tìm hyperparameter trong lượt này.

Final joint: A/R15 11/160, v2 61/160. H1/H2/H3 là giả thuyết của thay đổi gộp dữ liệu và cách viết target; thí nghiệm không cô lập nguyên nhân từng thay đổi. Không quy kết NF4, kích thước model hay thời lượng train nếu thiếu đối chứng phù hợp.

Điểm leaderboard lịch sử do người dùng báo, tách khỏi mọi số đo local bên trên: A/R15 0.3834; B 0.3247; strict cũ 0.1547. Không có phép đo public mới hoặc cam kết tăng leaderboard. Test hữu hạn không chứng minh lời giải tổng quát; source/Level không độc lập, final synthetic nhỏ và reviewer có thể sai.

## Tái tạo báo cáo offline

```bash
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_report.py --run /workspace/llm-final-project-arm-d-plus/outputs/task3/sft-v2-qlora-20261026-run1
```

Lệnh chỉ đọc generation/review/L4 đã hoàn tất và ghi analysis.json, ba paired casebook cùng báo cáo này. Không gọi model, GPU, compiler hoặc tự sinh verdict. Thiếu review/evidence, thiếu state hoặc summary không khớp record sẽ dừng thay vì tuyên bố hoàn tất.
