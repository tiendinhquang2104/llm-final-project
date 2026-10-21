"""Build ChatML JSONL training dataset for Task 2 Generative QLoRA.

Combines 477 synthetic samples from generate-dataset_v2 with 32 gold samples.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SYSTEM_PROMPT = """Bạn là trợ giảng chấm thi môn Lập trình C++ của trường đại học.
Nhiệm vụ: Phân tích bài nộp của sinh viên và xác định TẤT CẢ các loại lỗi có trong bài theo danh sách taxonomy bên dưới.
Nếu bài làm hoàn toàn đúng, trả về danh sách rỗng.

Danh sách 10 loại lỗi:
- Lỗi biên dịch: Code không biên dịch được dưới chuẩn g++ C++11.
- Lỗi nhập/xuất: Đọc/ghi sai định dạng, in sai hoa/thường (TRUE thay vì True), thừa dấu cách.
- Lỗi logic: Sai điều kiện, sai luồng xử lý hoặc giá trị biến khiến kết quả sai.
- Lỗi vòng lặp: Vòng lặp vô hạn, sai bước nhảy, off-by-one.
- Lỗi mảng/chuỗi: Truy cập ngoài biên mảng a[n], lỗi bộ nhớ, trả về mảng cục bộ.
- Lỗi hàm: Dùng/gọi hàm sai, stoi/stof crash, truyền tham trị thay vì tham chiếu.
- Lỗi edge case: Bỏ sót trường hợp biên (n=0, n=1, mảng rỗng, chuỗi rỗng).
- Lỗi thuật toán: Chọn giải thuật hoặc công thức toán học cốt lõi sai.
- Lỗi hard-code: Gán cứng kích thước mảng nhỏ hơn ràng buộc đề, gán cứng tên file, gán cứng return.
- Lỗi style: Toàn bộ code bị comment, trình bày lộn xộn, biến thừa."""


def format_user_prompt(exam_stmt: str, code: str, compile_log: str | None = None) -> str:
    log_text = compile_log.strip() if compile_log else "(rỗng / biên dịch OK)"
    return f"""## Đề bài
{exam_stmt.strip()}

## Code sinh viên
```cpp
{code.rstrip()}
```

## Compile log
{log_text}

Hãy xuất đúng một dòng JSON chứa danh sách lỗi:
{{"taxonomy_error": ["...", ...]}}"""


def main():
    out_file = ROOT / "data" / "processed" / "task2_sft_train.jsonl"
    synth_dir = ROOT.parent / "generate-dataset_v2" / "generate-dataset"
    if not synth_dir.exists():
        synth_dir = ROOT / "data" / "synth" / "v1" / "generate-dataset"

    if not synth_dir.exists():
        if out_file.exists() and out_file.stat().st_size > 10000:
            print(f"[INFO] Existing dataset found at {out_file} ({out_file.stat().st_size} bytes). Skipping regeneration.")
            return
        raise FileNotFoundError(f"Synthetic dataset directory not found at {synth_dir}")

    records = []
    
    # 1. Load synthetic dataset (477 samples)
    synth_tax = json.loads((synth_dir / "task2_error_taxonomy.json").read_text(encoding="utf-8"))
    synth_exams = {e["exam_id"]: e for e in json.loads((synth_dir / "exams.json").read_text(encoding="utf-8"))["exams"]}
    for s in synth_tax["samples"]:
        inp = s["input"]
        code_file = synth_dir / inp["code_file"]
        if not code_file.exists():
            continue
        code = code_file.read_text(encoding="utf-8", errors="replace")
        exam = synth_exams.get(inp["exam_id"], {})
        stmt = exam.get("statement", "")
        labels = s.get("output", {}).get("taxonomy_error", [])
        target = json.dumps({"taxonomy_error": labels}, ensure_ascii=False)
        
        records.append({
            "sample_id": s["sample_id"],
            "exam_id": inp["exam_id"],
            "is_gold": False,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": format_user_prompt(stmt, code, inp.get("compile_log"))},
                {"role": "assistant", "content": target},
            ]
        })

    # 2. Load Gold dataset (32 samples)
    gold_dir = ROOT / "data" / "sample_dataset"
    if gold_dir.exists():
        gold_tax = json.loads((gold_dir / "task2_error_taxonomy.json").read_text(encoding="utf-8"))
        gold_exams = {e["exam_id"]: e for e in json.loads((gold_dir / "exams.json").read_text(encoding="utf-8"))["exams"]}
        for s in gold_tax["samples"]:
            inp = s["input"]
            code_file = gold_dir / inp["code_file"]
            if not code_file.exists():
                continue
            code = code_file.read_text(encoding="utf-8", errors="replace")
            exam = gold_exams.get(inp["exam_id"], {})
            stmt = exam.get("statement", "")
            labels = s.get("output", {}).get("taxonomy_error", [])
            target = json.dumps({"taxonomy_error": labels}, ensure_ascii=False)
            
            # Gold samples can be upweighted x2
            for _ in range(2):
                records.append({
                    "sample_id": s["sample_id"],
                    "exam_id": inp["exam_id"],
                    "is_gold": True,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": format_user_prompt(stmt, code, inp.get("compile_log"))},
                        {"role": "assistant", "content": target},
                    ]
                })

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"[OK] Generated {len(records)} ChatML training records to {out_file}")


if __name__ == "__main__":
    main()
