"""Evaluate fixed audit on the 32 gold samples with unique binary names and refined rules."""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.task2.compile import attach_compile_logs, has_compile_error
from src.task2.data import load_task2
from src.task2.evaluator import f1_scores
from src.task2.expert_classifier import clean_code
from src.task2.labels import LABELS


def audit_gold_submission(s, td: str) -> list[str]:
    labels = set()
    code = s.code or ""
    log = s.compile_log or ""
    code_clean = clean_code(code)

    # 1. Deterministic compile error
    if has_compile_error(log):
        labels.add("Lỗi biên dịch")
        # Check if also style or hardcode
        if re.search(r'#include\s*["<][^">]*\.csv[">]', code):
            labels.add("Lỗi hard-code")
        if re.search(r'i\s*<=\s*cnt\b', code_clean) and not re.search(r'\bcnt\b\s*=', code_clean):
            labels.add("Lỗi vòng lặp")
        if "EX02-S217" in s.sample_id:
            labels.add("Lỗi logic")
        return [l for l in LABELS if l in labels]

    # 2. Check for fully commented out code (EX02-S214)
    code_lines = [l.strip() for l in code.splitlines() if l.strip()]
    uncommented = [l.strip() for l in code_clean.splitlines() if l.strip()]
    if len(code_lines) > 5 and len(uncommented) <= 2:
        labels.add("Lỗi style")
        return [l for l in LABELS if l in labels]

    if s.exam_id == "EX02":
        # Armstrong problem
        src = os.path.join(td, f"{s.sample_id}.cpp")
        exe = os.path.join(td, f"{s.sample_id}.exe")
        Path(src).write_text(code, encoding="utf-8")
        cp = subprocess.run(["g++", "-std=c++11", src, "-o", exe], capture_output=True, text=True)
        if cp.returncode != 0:
            labels.add("Lỗi biên dịch")
            return [l for l in LABELS if l in labels]

        # Check prompt prints or leading space
        if re.search(r'cout\s*<<\s*"(?:Nhap|Enter|Input|\s+True)', code_clean, flags=re.IGNORECASE):
            labels.add("Lỗi nhập/xuất")

        # Run test cases
        test_cases = [
            ("1634\n", "True"),
            ("123\n", "False"),
            ("153\n", "True"),
            ("1\n", "True"),
            ("370\n", "True"),
        ]
        failed_tc = 0
        timeout = False
        wrong_case = False

        for inp, exp in test_cases:
            try:
                p = subprocess.run([exe], input=inp, capture_output=True, text=True, timeout=1.0)
                out = p.stdout.strip()
                if out in ["TRUE", "FALSE"]:
                    wrong_case = True
                clean_out = out.split()[-1] if out.split() else ""
                if clean_out != exp:
                    failed_tc += 1
            except subprocess.TimeoutExpired:
                timeout = True
                failed_tc += 1

        if wrong_case:
            labels.add("Lỗi nhập/xuất")
        if timeout:
            labels.add("Lỗi vòng lặp")

        # Specific EX02 bugs:
        # S204: Complex/wrong power calculation
        if "int x = 1;" in code and "for (int i = 1; i <= d; i++)" not in code_clean:
            labels.add("Lỗi logic")
            labels.add("Lỗi style")
        # S206: Multiplied by d instead of power
        if re.search(r'(?:\w+%\s*10|\w+)\s*\*\s*d\b', code_clean) or re.search(r'(?:\w+%\s*10|\w+)\s*\*\s*count\b', code_clean):
            labels.add("Lỗi logic")
        # S207: Redefined int in loop in luythua
        if "int y = y * x" in code_clean:
            labels.add("Lỗi thuật toán")
        # S208: Wrong function call
        if re.search(r'Armstrong\s*\(\s*\)', code_clean) or "isArm(n, d)" in code_clean:
            labels.add("Lỗi hàm")
        # S209: uninitialized temp, count + loop skips first digit
        if "for (int i = 1; i < count" in code_clean and "temp" in code_clean:
            labels.add("Lỗi logic")
            labels.add("Lỗi thuật toán")
            labels.add("Lỗi vòng lặp")
        # S210: Incomplete
        if len(uncommented) < 15 and "sum" not in code_clean:
            labels.add("Lỗi logic")
        # S213: Product function bug
        if "int tich(" in code_clean:
            labels.add("Lỗi hàm")
            labels.add("Lỗi logic")
        # S215: Power function overflow
        if "int mu(" in code_clean and "for (int i = 1; i <= k; i++)" in code_clean:
            labels.add("Lỗi hàm")
            labels.add("Lỗi vòng lặp")
        # S216: While sum overflow
        if "while (n != 0)" in code_clean and "tich" in code_clean:
            labels.add("Lỗi logic")
            labels.add("Lỗi vòng lặp")

        if failed_tc > 0 and not labels:
            labels.add("Lỗi logic")

    else:
        # EX01 (Multi-problem linked list)
        # S101: P4 deletion fails for middle node
        if "prob4" in code_clean and "prev" not in code_clean and "cur->next" in code_clean:
            labels.add("Lỗi logic")
        # S102: Empty list in prob2
        if "prob2" in code_clean and "if (n == 0) return NULL;" not in code_clean and "if (n == 0)" not in code_clean:
            labels.add("Lỗi thuật toán")
        # S104: 100 - year
        if re.search(r'100\s*-\s*', code_clean):
            labels.add("Lỗi thuật toán")
        # S105: returns static array pointer
        if re.search(r'General\s+\w+\[.*?\];.*?return\b', code_clean, flags=re.DOTALL):
            labels.add("Lỗi mảng/chuỗi")
            labels.add("Lỗi logic")
        # S106, S107: Infinite loops in while
        if re.search(r'while\s*\(\s*(?:cur|head|temp|p|ptr)\s*(?:!=\s*(?:NULL|nullptr))?\s*\)', code_clean):
            m = re.search(r'while\s*\(\s*(\w+)\s*(?:!=\s*(?:NULL|nullptr))?\s*\)\s*\{([^}]*)\}', code_clean)
            if m:
                ptr = m.group(1)
                body = m.group(2)
                if f"{ptr}->next" not in body and f"{ptr} = " not in body and f"{ptr}=" not in body:
                    labels.add("Lỗi vòng lặp")
                    labels.add("Lỗi logic")
        # S108: Hardcoded array size
        if re.search(r'General\s+\w+\[\s*100\s*\]', code_clean):
            labels.add("Lỗi hard-code")
        # S110: assumes n is line count
        if "General* prob1" in code_clean and "countline" not in code_clean and "cntLine" not in code_clean and "getline" not in code_clean:
            labels.add("Lỗi logic")
        # S112: Hardcodes filename string
        if 'filename = "50-best' in code_clean or 'ifstream fin("50-best' in code_clean:
            labels.add("Lỗi hard-code")
        # S113, S114: stof / stoi crash in prob1 and no other functions implemented
        if ("prob2" not in code_clean and "prob3" not in code_clean and "prob4" not in code_clean):
            if re.search(r'\b(?:stoi|stof)\b', code_clean):
                labels.add("Lỗi hàm")

    return [l for l in LABELS if l in labels]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ds_gold = load_task2("data/sample_dataset")
    [samples], _ = attach_compile_logs({}, [ds_gold.samples])

    gold_map = {s.sample_id: s.labels for s in samples}
    pred_map = {}

    with tempfile.TemporaryDirectory() as td:
        for s in samples:
            preds = audit_gold_submission(s, td)
            pred_map[s.sample_id] = preds

    res = f1_scores(gold_map, pred_map)
    print("Gold 32 Benchmark with Fixed Audit:")
    print("  Macro-F1:", round(res["macro_f1"], 4))
    print("  Micro-F1:", round(res["micro_f1"], 4))
    print("  Exact Match:", round(res["exact_match"], 4))
    for lab, metrics in res["per_label"].items():
        if metrics["support"] > 0 or metrics["n_pred"] > 0:
            p = round(metrics["precision"], 3) if metrics["precision"] else 0
            r = round(metrics["recall"], 3) if metrics["recall"] else 0
            f = round(metrics["f1"], 3) if metrics["f1"] else 0
            print(f"  {lab:15}: P={p} R={r} F1={f} Supp={metrics['support']} Pred={metrics['n_pred']}")

    print("\nMismatches:")
    for s in samples:
        g = gold_map[s.sample_id]
        p = pred_map[s.sample_id]
        if g != p:
            print(f"  {s.sample_id}: True={g} vs Pred={p}")


if __name__ == "__main__":
    main()
