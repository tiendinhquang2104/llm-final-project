import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from src.data.loader import load_task1
from src.synth.problems import load_problems

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_synth_dataset", ROOT / "scripts" / "build_synth_dataset.py")
BUILD = importlib.util.module_from_spec(SPEC)
sys.modules["build_synth_dataset"] = BUILD
SPEC.loader.exec_module(BUILD)

BANK = ROOT / "src" / "synth" / "problems" / "demo.yaml"
HAS_CXX = bool(shutil.which("g++"))


@unittest.skipUnless(HAS_CXX, "labels come from real execution: needs g++")
class TestBuildEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "v1"
        empty = Path(cls.tmp.name) / "no_public"
        empty.mkdir()
        cls.stats = BUILD.build(load_problems(BANK), cls.out, seed=42, scale=0.06, heldout_scale=0.04,
                                public_root=empty, n_task3_dup=10, max_attempts=4)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _json(self, name, split=""):
        return json.loads(((self.out / split) / name).read_text(encoding="utf-8"))

    def _prov(self):
        return [json.loads(l) for l in (self.out / "provenance.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_required_files_exist(self):
        for name in ("exams.json", "label_space.json", "task1_grading.json", "task2_error_taxonomy.json",
                     "task3_feedback.json", "exec_reports.jsonl", "provenance.jsonl", "build_stats.json"):
            self.assertTrue((self.out / name).exists(), name)
        self.assertTrue((self.out / "heldout" / "task1_grading.json").exists())

    def test_task_files_share_sample_ids(self):
        t1 = {s["sample_id"] for s in self._json("task1_grading.json")["samples"]}
        t2 = {s["sample_id"] for s in self._json("task2_error_taxonomy.json")["samples"]}
        t3 = {s["sample_id"] for s in self._json("task3_feedback.json")["samples"]}
        self.assertTrue(t1)
        self.assertEqual(t1, t2)
        self.assertTrue(t1 <= t3)

    def test_level_duplicates_share_the_original_code_file(self):
        t3 = {s["sample_id"]: s for s in self._json("task3_feedback.json")["samples"]}
        dups = [sid for sid in t3 if sid.rsplit("-", 1)[-1].startswith("L") and sid.rsplit("-", 1)[0] in t3]
        self.assertTrue(dups)
        for sid in dups:
            orig = sid.rsplit("-", 1)[0]
            self.assertEqual(t3[sid]["input"]["code_file"], t3[orig]["input"]["code_file"])
            self.assertNotEqual(t3[sid]["input"]["target_feedback_level"], t3[orig]["input"]["target_feedback_level"])
            self.assertFalse((self.out / "submissions" / t3[sid]["input"]["exam_id"] / f"{sid}.cpp").exists())

    def test_task3_input_has_no_taxonomy(self):
        for s in self._json("task3_feedback.json")["samples"]:
            self.assertNotIn("taxonomy_error", s["input"])
            self.assertIn("exec_report", s["input"])

    def test_exec_report_never_leaks_the_label(self):
        for line in (self.out / "exec_reports.jsonl").read_text(encoding="utf-8").splitlines():
            report = json.loads(line)["exec_report"]
            self.assertNotRegex(report, r"(?im)^\s*(defect|rule|label)\s*:")
            self.assertNotIn("labeling only", report)
            self.assertRegex(report, r"^compile: (OK|FAIL)")

    def test_every_record_is_verified_and_rule_matches_template(self):
        prov = {p["sample_id"]: p for p in self._prov()}
        for s in self._json("task1_grading.json")["samples"]:
            p = prov[s["sample_id"]]
            self.assertTrue(p["verified"])
            self.assertEqual(s["output"]["total_score"], sum(s["output"]["rubric"].values()))
            if p["intended_rule"]:
                self.assertEqual(p["rule"], p["intended_rule"])
            if p["intended_total"] is not None:
                self.assertEqual(s["output"]["total_score"], p["intended_total"])

    def test_identical_code_never_has_two_labels(self):
        seen = {}
        for s in self._json("task1_grading.json")["samples"]:
            code = (self.out / s["input"]["code_file"]).read_text(encoding="utf-8")
            label = s["output"]["total_score"]
            self.assertEqual(seen.setdefault(code, label), label, s["sample_id"])

    def test_no_generation_artefacts(self):
        for s in self._json("task1_grading.json")["samples"]:
            code = (self.out / s["input"]["code_file"]).read_text(encoding="utf-8")
            self.assertNotRegex(code, r"\b[A-Za-z]+_v\d+\b")
            self.assertNotRegex(code, r"#include\s*<(x\d|=)")

    def test_heldout_is_separate(self):
        train_ids = {e["exam_id"] for e in self._json("exams.json")["exams"]}
        held_ids = {e["exam_id"] for e in self._json("exams.json", "heldout")["exams"]}
        self.assertFalse(train_ids & held_ids)
        for s in self._json("task1_grading.json", "heldout")["samples"]:
            self.assertTrue((self.out / "heldout" / s["input"]["code_file"]).exists())
            self.assertFalse((self.out / s["input"]["code_file"]).exists())

    def test_all_generated_feedback_is_compliant(self):
        from src.synth.compliance import check
        for s in self._json("task3_feedback.json")["samples"]:
            res = check(s["output"]["feedback"], s["input"]["target_feedback_level"])
            self.assertTrue(res.ok, f"{s['sample_id']}: {res.violations}")

    def test_output_is_readable_by_existing_loader(self):
        ds = load_task1(self.out)
        self.assertTrue(ds.samples)

    def test_pairs_have_two_members_with_different_labels(self):
        t1 = {s["sample_id"]: s["output"]["total_score"] for s in self._json("task1_grading.json")["samples"]}
        pairs = {}
        for p in self._prov():
            if p.get("pair_id") and p["sample_id"] in t1:
                pairs.setdefault(p["pair_id"], []).append(p["sample_id"])
        for pid, members in pairs.items():
            self.assertEqual(len(members), 2, pid)
            self.assertNotEqual(t1[members[0]], t1[members[1]], pid)

    def test_multi_records_carry_observed_states(self):
        rows = [p for p in self._prov() if p["exam_type"] == "multi_problem"]
        self.assertTrue(rows)
        self.assertTrue(all(r["observed_states"] for r in rows))


@unittest.skipUnless(HAS_CXX, "needs g++")
class TestBases(unittest.TestCase):
    def test_reference_failing_its_tests_is_rejected(self):
        problem = load_problems(BANK)["SYN-ARM"]
        problem.reference = problem.reference.replace("p = p * digit;", "p = p * 2;")
        from src.synth.verify import make_runner
        with self.assertRaises(ValueError):
            BUILD.prepare_bases(problem, make_runner(), None)

    def test_persona_bases_are_used_when_valid(self):
        problem = load_problems(BANK)["SYN-ARM"]
        from src.synth.verify import make_runner
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "SYN-ARM"
            d.mkdir()
            (d / "exam_style__0.cpp").write_text(problem.reference.replace("countDigits", "demChuSo"), encoding="utf-8")
            (d / "broken__0.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
            bases = BUILD.prepare_bases(problem, make_runner(), Path(tmp), n_variants=1)
            refs = {b.style_ref for b in bases}
            self.assertIn("persona:exam_style", refs)
            self.assertNotIn("persona:broken", refs)


@unittest.skipUnless(HAS_CXX, "needs g++")
class TestPublicGuard(unittest.TestCase):
    def test_exact_public_match_is_dropped(self):
        problems = load_problems(BANK)
        with tempfile.TemporaryDirectory() as tmp:
            pub = Path(tmp) / "pub" / "EX"
            pub.mkdir(parents=True)
            (pub / "leak.cpp").write_text(problems["SYN-ARM"].reference, encoding="utf-8")
            stats = BUILD.build(problems, Path(tmp) / "v1", seed=1, scale=0.04, heldout_scale=0.02,
                                public_root=Path(tmp) / "pub", n_task3_dup=2, max_attempts=2)
            self.assertGreaterEqual(stats["guards"]["train"]["dropped_public"], 1)


class TestProblemBank(unittest.TestCase):
    def test_directory_loads_all_exams(self):
        problems = load_problems(BANK.parent)
        self.assertGreaterEqual(len(problems), 7)
        self.assertTrue(all(p.reference for p in problems.values()))

    def test_armstrong_uses_power_of_digit_count(self):
        arm = load_problems(BANK)["SYN-ARM"]
        self.assertNotIn("lập phương", arm.statement)
        expected = {t.input: t.expected for t in arm.tests}
        self.assertEqual(expected["1634"], "True")   # 1^4+6^4+3^4+4^4, wrong under a "cube" definition
        self.assertEqual(expected["9474"], "True")


if __name__ == "__main__":
    unittest.main()
