import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from src.data.synth_fetch import extract, fetch_synth, silver_roots
from tests._task2 import make_dataset


def make_silver_zip(tmp: Path) -> Path:
    """generate-dataset.zip shaped like the real one: silver + heldout/ + macOS junk."""
    src = tmp / "src" / "generate-dataset"
    make_dataset(src, [("S1", "EXA", ["Lỗi logic"]), ("S2", "EXA", [])])
    make_dataset(src / "heldout", [("H1", "EXB", ["Lỗi hàm"])])
    zp = tmp / "data" / "synth" / "v1" / "generate-dataset.zip"
    zp.parent.mkdir(parents=True)
    with zipfile.ZipFile(zp, "w") as zf:
        for f in sorted(src.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(src.parent))
        zf.writestr("__MACOSX/generate-dataset/._exams.json", "junk")
        zf.writestr("generate-dataset/._task2_error_taxonomy.json", "junk")
    return zp


class TestSynthFetch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.zip = make_silver_zip(self.root)
        self.dir = self.zip.parent

    def tearDown(self):
        self.tmp.cleanup()

    def test_extract_skips_mac_junk(self):
        root = extract(self.zip, self.dir)
        self.assertEqual(root, self.dir / "generate-dataset")
        self.assertFalse((self.dir / "__MACOSX").exists())
        self.assertFalse((root / "._task2_error_taxonomy.json").exists())
        self.assertTrue((root / "heldout" / "exams.json").exists())

    def test_extract_refuses_path_escape(self):
        bad = self.root / "bad.zip"
        with zipfile.ZipFile(bad, "w") as zf:
            zf.writestr("../evil.txt", "x")
        with self.assertRaises(ValueError):
            extract(bad, self.root / "out")

    def test_fetch_uses_local_zip_then_folder(self):
        with mock.patch("src.data.synth_fetch.download") as dl:
            roots = silver_roots(self.dir)
            self.assertEqual(fetch_synth(self.dir), roots["silver"])  # second call: folder already there
        dl.assert_not_called()
        self.assertEqual(roots["heldout"], roots["silver"] / "heldout")

    def test_fetch_downloads_when_zip_missing(self):
        target = self.root / "other"
        data = self.zip.read_bytes()

        def fake_download(drive_id, out_path):
            self.assertEqual(drive_id, "abc")
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            Path(out_path).write_bytes(data)
            return Path(out_path)

        with mock.patch.dict(os.environ, {"SILVER_DRIVE_ID": "abc"}), \
                mock.patch("src.data.synth_fetch.download", side_effect=fake_download):
            root = fetch_synth(target)
        self.assertTrue((root / "task2_error_taxonomy.json").exists())

    def test_missing_zip_and_id_is_a_clear_error(self):
        with mock.patch.dict(os.environ, {"SILVER_DRIVE_ID": ""}), self.assertRaises(SystemExit):
            fetch_synth(self.root / "nothing")

    def test_cli_silver_and_heldout(self):
        from src.task2 import cot_cli
        from tests.test_task2_cot import VotingLocal
        project = Path(__file__).resolve().parents[1]
        run_cfg = self.root / "run.yaml"
        run_cfg.write_text("backend: mlx\nmlx: {model: fake/qwen}\nrun: {experiment: x, smoke_sample_ids: [S1], "
                           "predict: false, use_cache: true}\n", encoding="utf-8")
        common = ["--run-config", str(run_cfg), "--no-compile", "--limit", "5", "--silver-dir", str(self.dir),
                  "--output-dir", str(self.root / "out")]
        with mock.patch.object(cot_cli, "make_local_backend", side_effect=lambda k, s: VotingLocal([["Lỗi logic"]] * 9)):
            cot_cli.main(project, "cot_zero_shot", argv=common + ["--silver"])
            cot_cli.main(project, "cot_zero_shot", argv=common + ["--silver-heldout"])
            with self.assertRaises(SystemExit):
                cot_cli.main(project, "cot_zero_shot", argv=common + ["--silver", "--gold-root", "x"])
        silver = self.root / "out" / "task2_cot_zero_shot_silver__mlx__fake-qwen"
        heldout = self.root / "out" / "task2_cot_zero_shot_silver_heldout__mlx__fake-qwen"
        self.assertEqual(json.loads((silver / "config.json").read_text(encoding="utf-8"))["ids"], ["S1", "S2"])
        self.assertEqual(json.loads((heldout / "config.json").read_text(encoding="utf-8"))["ids"], ["H1"])

    def test_cli_fewshot_demos_come_from_gold_and_silver_only(self):
        from src.task2 import cot_cli
        from tests.test_task2_cot import VotingLocal
        project = Path(__file__).resolve().parents[1]
        gold = make_dataset(self.root / "gold", [("G1", "EXA", ["Lỗi logic"]), ("G2", "EXA", [])])
        public = make_dataset(self.root / "pub", [("P1", "EXA", None), ("P2", "EXA", None)])
        run_cfg = self.root / "run.yaml"
        run_cfg.write_text("backend: mlx\nmlx: {model: fake/qwen}\nrun: {experiment: x, smoke_sample_ids: [G1], "
                           "predict: false, use_cache: true}\n", encoding="utf-8")
        argv = ["--run-config", str(run_cfg), "--no-compile", "--limit", "2", "--gold-root", str(gold),
                "--public-root", str(public), "--predict", "--silver-dir", str(self.dir),
                "--output-dir", str(self.root / "out")]
        with mock.patch.object(cot_cli, "make_local_backend", side_effect=lambda k, s: VotingLocal([["Lỗi logic"]] * 9)), \
                mock.patch("src.task2.cot_runner.REGISTRY", self.root / "registry.csv"), \
                mock.patch.object(cot_cli, "REGISTRY", self.root / "registry.csv"):
            cot_cli.main(project, "cot_fewshot", baseline="cot_zero_shot", argv=argv)
        out = self.root / "out"
        demos = []
        for d in out.iterdir():
            for line in (d / "raw_outputs.jsonl").read_text(encoding="utf-8").splitlines():
                demos += json.loads(line)["record"]["demos"]
        ids = {x.split(":")[1] for x in demos}
        self.assertTrue(ids)
        self.assertTrue(ids <= {"G1", "G2", "S1", "S2"})               # never P1/P2, never heldout H1
        for d in out.iterdir():
            for line in (d / "raw_outputs.jsonl").read_text(encoding="utf-8").splitlines():
                rec = json.loads(line)["record"]
                self.assertNotIn(rec["sample_id"], [x.split(":")[1] for x in rec["demos"]])  # never itself


if __name__ == "__main__":
    unittest.main()
