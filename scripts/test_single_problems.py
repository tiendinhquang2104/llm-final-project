"""Run test cases against compilable single_problem student submissions to diagnose runtime errors."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.task2.data import load_task2

def test_final_1():
    ds = load_task2("data/public_test_release")
    samples = [s for s in ds.samples if s.exam_id == "Class03-Final-1"]
    test_cases = [
        ("harry potter\n", "hap"),
        ("tom riddle\n", "tomr"),
        ("alex bob\n", "ab"),
        ("a a\n", "aa"),
    ]
    print(f"Testing {len(samples)} samples for Class03-Final-1...")
    
    with tempfile.TemporaryDirectory() as td:
        for s in samples:
            src = os.path.join(td, "sub.cpp")
            exe = os.path.join(td, "sub.exe")
            Path(src).write_text(s.code, encoding="utf-8")
            cp = subprocess.run(["g++", "-std=c++11", src, "-o", exe], capture_output=True, text=True)
            if cp.returncode != 0:
                print(f"[{s.sample_id}] COMPILE ERROR")
                continue
            
            passed = 0
            outputs = []
            crashed = False
            timed_out = False
            for inp, exp in test_cases:
                try:
                    run = subprocess.run([exe], input=inp, capture_output=True, text=True, timeout=2)
                    out = run.stdout.strip()
                    outputs.append((inp.strip(), out, exp))
                    if out == exp:
                        passed += 1
                except subprocess.TimeoutExpired:
                    timed_out = True
                except Exception:
                    crashed = True
            
            status = "PERFECT" if passed == len(test_cases) else f"FAILED ({passed}/{len(test_cases)})"
            if timed_out:
                status += " TIMEOUT"
            if crashed:
                status += " CRASH"
            print(f"[{s.sample_id}] {status} -> {outputs[:2]}")

if __name__ == "__main__":
    test_final_1()
