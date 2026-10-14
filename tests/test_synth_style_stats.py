import json
import tempfile
import unittest
from pathlib import Path

from src.synth.style_stats import StyleProfile, analyze, build_style_profile, persona_text

C1 = "#include <iostream>\n// dem so\nvoid main(){ int dem = 0; cout << dem; }\n"
C2 = "#include <bits/stdc++.h>\n#define ll long long\nint main(){ ifstream f(\"a.csv\"); string s; while(!f.eof()){ getline(f, s); } }\n"
C3 = "#include <iostream>\nusing namespace std;\nint tong(int n){ int s = 0; for(int i=1;i<=n;i++) s+=i; return s; }\n"


class TestAnalyze(unittest.TestCase):
    def test_flags_and_includes(self):
        stats = analyze([C1, C2, C3])
        self.assertEqual(stats["n_files"], 3)
        self.assertAlmostEqual(stats["flags_ratio"]["void_main"], 1 / 3, places=3)
        self.assertAlmostEqual(stats["flags_ratio"]["bits_header"], 1 / 3, places=3)
        self.assertAlmostEqual(stats["flags_ratio"]["reads_file"], 1 / 3, places=3)
        self.assertAlmostEqual(stats["flags_ratio"]["define_ll"], 1 / 3, places=3)
        self.assertIn("iostream", stats["top_includes"])

    def test_persona_mentions_stats(self):
        text = persona_text(analyze([C1, C2, C3]))
        self.assertIn("dòng", text)

    def test_empty(self):
        self.assertEqual(analyze([]), {"n_files": 0})
        self.assertIn("Không có", persona_text({"n_files": 0}))


class TestBuildProfile(unittest.TestCase):
    def test_writes_profile_without_code_and_bounded_snippets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "public"
            (root / "submissions" / "EX").mkdir(parents=True)
            for i, code in enumerate([C1, C2, C3, C3]):
                (root / "submissions" / "EX" / f"s{i}.cpp").write_text(code, encoding="utf-8")
            out = Path(tmp) / "profile"
            profile = build_style_profile(root, out)
            self.assertIsInstance(profile, StyleProfile)
            profile_json = json.loads((out / "style_profile.json").read_text(encoding="utf-8"))
            flat = json.dumps(profile_json, ensure_ascii=False)
            self.assertNotIn("dem = 0", flat)  # no source code in the profile
            self.assertIn("persona", profile_json)
            snippets = json.loads((out / "style_snippets.json").read_text(encoding="utf-8"))
            self.assertLessEqual(len(snippets), 3)
            for s in snippets:
                self.assertLessEqual(len(s["lines"]), 15)
                self.assertIn("source", s)


if __name__ == "__main__":
    unittest.main()
