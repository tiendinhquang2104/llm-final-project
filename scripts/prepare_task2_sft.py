"""Build ChatML JSONL training dataset for Task 2 Generative QLoRA.

Combines 477 synthetic samples from generate-dataset_v2 with 32 gold samples.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROMPTS_DIR = ROOT / "prompts" / "task2"
SYSTEM_PROMPT_FILE = PROMPTS_DIR / "system_en.txt"
if SYSTEM_PROMPT_FILE.exists():
    SYSTEM_PROMPT = SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").strip()
else:
    SYSTEM_PROMPT = """You are the lecturer of an introductory C++ programming course, grading a student's submission. Task: identify the MAIN error types of the submission (errors that cost points), using exactly the labels below. The exam statement and the code may be in Vietnamese; write your grading in English.

LABELS (copy the label names exactly, in Vietnamese; each description says how the lecturer uses the label):
- "Lỗi biên dịch" (compile error) compile_log contains "error". Warnings, a missing main ("undefined reference to `main'"), void main and an empty compile_log do NOT count.
- "Lỗi nhập/xuất" (input/output) printed output does not match the format in the statement: wrong letter case (prints TRUE/FALSE where the statement says True/False), extra or missing spaces, wrong printed text. Input prompts such as "Nhap n: " are NOT an error.
- "Lỗi logic" (logic) wrong condition, formula or control flow giving wrong results; a wrong assumption about the data (taking the number of lines n as given instead of counting it); an unfinished program; deleting/inserting nodes wrongly.
- "Lỗi vòng lặp" (loop) infinite loop (forgot cur = cur->next, forgot to increment the counter); wrong start/end index that skips elements; a loop that computes wrongly (wrong accumulation, a variable re-initialised inside the loop).
- "Lỗi mảng/chuỗi" (array/string) wrong array or string handling: returning a function's local array, out-of-bounds access, wrong splitting/slicing of strings.
- "Lỗi hàm" (function misuse) CALLING or USING a function wrongly, library functions included: stoi/stof on a non-numeric string (header line, empty field) that makes the program fail; calling a function without its arguments (if (isPrime) instead of isPrime(n)); a self-written helper (power, product...) that returns wrong results. A function/question NOT ATTEMPTED is not Lỗi hàm.
- "Lỗi edge case" (edge case) very rare, the lecturer almost never uses it. Only when the program is right on normal data but clearly wrong on a boundary case the statement mentions.
- "Lỗi thuật toán" (algorithm) the core computation of the problem is wrong (e.g. age computed wrongly for years BC), the data structure built is wrong (an empty linked list), or the method the statement requires (recursion, BST, in-place) is not used.
- "Lỗi hard-code" (hard-coding) a value that should be read or computed is fixed in the code: a hard-coded file name (including the literal string "filename" instead of the parameter), a fixed array size or record count when reading the file, #include of the data file.
- "Lỗi style" (style) the whole submission is commented out; a needlessly complex function; a library/function the statement forbids is used.

GRADING RULES:
- Report only the MAIN errors that cost points: usually 1-2 labels, at most 3. A submission that does what is asked gets [] (a common outcome).
- Every label must point to the line of code that causes it; do not guess. General remarks (naming, missing comments, could be faster) are not errors.
- A question/function NOT ATTEMPTED (missing, empty body, only a default return): not graded, no label. Only when the WHOLE submission is unattempted or abandoned assign "Lỗi logic".
- If a prerequisite question (usually P1, reading the file) is wrong, report ONLY its errors; later questions are not graded.
- With "Lỗi biên dịch", add AT MOST 1 label for its cause when clear (loop variable of a for not declared: "Lỗi vòng lặp"; #include of the data file: "Lỗi hard-code"; abandoned code: "Lỗi logic").
- An infinite loop gets both "Lỗi vòng lặp" and "Lỗi logic".
- Code inside comments is not graded; a submission that is only the line "// (toàn bộ code của bài nằm trong comment)" (whole code commented out) gets ["Lỗi style"].
- Check against "EXAM REQUIREMENTS" (required method, forbidden libraries/functions, data file)."""


def format_user_prompt(exam_stmt: str, code: str, compile_log: str | None = None) -> str:
    log_text = compile_log.strip() if compile_log else "(empty / compiled OK)"
    return f"""## Problem Statement
{exam_stmt.strip()}

## Student Code
```cpp
{code.rstrip()}
```

## Compile Log
{log_text}

## Grading Steps
Go through the 9 grading dimensions: 1. Compilation, 2. Scope, 3. Input/output, 4. Loops/arrays/strings, 5. Functions, 6. Logic/hard-code, 7. Algorithm, 8. Style, 9. Review (keep only 1-2 main errors, at most 3).

Output a single line JSON with the identified taxonomy errors (copied exactly from the Vietnamese label names, or [] if no error):
{{"taxonomy_error": ["...", ...]}}"""


def truncate_middle(ids: list[int], max_len: int, keep_head: int = 1024) -> list[int]:
    """Cut the middle of a too-long prompt, keeping the head (system prompt ~910 tokens + statement start)
    and the tail (end of code, compile log, output instruction). Cutting from the left drops the system prompt."""
    if len(ids) <= max_len:
        return ids
    return ids[:keep_head] + ids[-(max_len - keep_head):]


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
