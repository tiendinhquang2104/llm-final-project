import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from src.synth.multi import assemble, parse_statuses
from src.synth.problems import load_problems

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "src" / "synth" / "problems"
CXX = shutil.which("clang++") or shutil.which("g++") or shutil.which("c++")


@unittest.skipUnless(CXX, "no C++ compiler available")
class TestHarnessesRun(unittest.TestCase):
    def test_every_multi_harness_reports_all_ok_on_reference(self):
        problems = load_problems(BANK)
        multis = [p for p in problems.values() if p.exam_type == "multi_problem" and p.harness]
        self.assertTrue(multis)
        for problem in multis:
            with self.subTest(exam=problem.exam_id), tempfile.TemporaryDirectory() as tmp:
                d = Path(tmp)
                for name, content in problem.data_files.items():
                    (d / name).write_text(content, encoding="utf-8")
                (d / "student.cpp").write_text(assemble(problem.reference, problem.harness), encoding="utf-8")
                exe = d / "a.out"
                proc = subprocess.run([CXX, "-std=c++11", "student.cpp", "-o", "a.out"],
                                      cwd=d, capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, proc.stderr[:400])
                run = subprocess.run([str(exe)], cwd=d, capture_output=True, text=True, timeout=10)
                statuses = parse_statuses(run.stdout)
                self.assertEqual(set(statuses.values()), {"ok"}, f"{problem.exam_id}: {statuses}")


if __name__ == "__main__":
    unittest.main()
