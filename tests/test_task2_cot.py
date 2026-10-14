import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.llm.local_backend import LocalChatBackend
from src.task2.cot_bundle import backend_settings, export_bundle, load_bundle
from src.task2.cot_runner import run_and_report, tee_log
from src.task2.api_experiment import run_api
from src.task2.data import load_task2
from src.task2.labels import LABELS
from src.task2.pipeline import Task2ApiPipeline, parse_cot_labels
from src.task2.prompts_cot import FINAL_MARKER, SYSTEM_COT
from tests._task2 import FakeBackend, make_dataset

COT_CFG = {"name": "t_cot", "prompt": {"style": "cot", "few_shot_k": 0, "max_code_chars": 4000,
                                       "use_aux_signals": True},
           "generation": {"temperature": 0.0, "n": 1, "max_new_tokens": 512}, "retry_on_parse_fail": 1}


def cot_answer(*labels):
    return ("1. Biên dịch: không lỗi.\n3. Vòng lặp: `for (i = 0; i <= n; i++) { s += a[i]; }` lặp thừa.\n"
            f'{FINAL_MARKER} {json.dumps({"taxonomy_error": list(labels)}, ensure_ascii=False)}')


class TestCotParse(unittest.TestCase):
    def test_reads_final_line_despite_code_braces(self):
        self.assertEqual(parse_cot_labels(cot_answer("Lỗi vòng lặp", "Lỗi style")), ["Lỗi vòng lặp", "Lỗi style"])

    def test_empty_list_is_valid(self):
        self.assertEqual(parse_cot_labels(cot_answer()), [])

    def test_fallback_plain_json(self):  # retry answers are bare JSON without the marker
        self.assertEqual(parse_cot_labels('{"taxonomy_error": ["Lỗi hàm"]}'), ["Lỗi hàm"])

    def test_fallback_last_line_with_key(self):
        text = 'phân tích...\n{"taxonomy_error": ["Lỗi logic"]}'
        self.assertEqual(parse_cot_labels(text), ["Lỗi logic"])

    def test_unparseable(self):
        self.assertIsNone(parse_cot_labels("chưa kết luận"))


class TestCotPrompt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ds = load_task2(make_dataset(Path(self.tmp.name), [("A1", "EXA", ["Lỗi logic"]),
                                                                ("A2", "EXA", [])]))
        self.by = self.ds.by_id()
        self.by["A1"].compile_log = "student.cpp:3:5: error: 'x' was not declared in this scope"

    def tearDown(self):
        self.tmp.cleanup()

    def test_messages(self):
        pipe = Task2ApiPipeline(self.ds, None, COT_CFG, demo_pool=self.ds.samples)
        req = pipe.build_request(self.by["A1"])
        self.assertEqual(req["demos"], [])            # zero-shot even if a pool is passed
        self.assertIsNone(req["schema"])
        system, user = req["messages"][0]["content"], req["messages"][1]["content"]
        self.assertEqual(system, SYSTEM_COT)
        self.assertIn("giảng viên", system)
        for lab in LABELS:
            self.assertIn(lab, system)
        self.assertIn("was not declared", user)       # compile_log block
        self.assertIn(FINAL_MARKER, user)
        self.assertIn("7. Style:", user)              # seven grading steps, as a fill-in template
        self.assertNotIn("đúng một dòng", user)      # read as "answer in one line" -> no reasoning
        self.assertLess(user.index("7. Style: <"), user.rindex(FINAL_MARKER))
        self.assertNotIn("feedback", (system + user).lower())

    def test_json_style_unchanged(self):
        cfg = {**COT_CFG, "prompt": {**COT_CFG["prompt"], "style": "json"}}
        req = Task2ApiPipeline(self.ds, None, cfg).build_request(self.by["A1"])
        self.assertIsNotNone(req["schema"])
        self.assertNotIn(FINAL_MARKER, req["messages"][1]["content"])

    def test_infer_and_postprocess_use_cot_parser(self):
        backend = FakeBackend([cot_answer("Lỗi logic"), "rác", '{"taxonomy_error": []}'])
        pipe = Task2ApiPipeline(self.ds, backend, COT_CFG)
        recs = pipe.infer([self.by["A1"], self.by["A2"]])
        p1, p2 = pipe.postprocess(recs[0]), pipe.postprocess(recs[1])
        self.assertEqual(p1["labels"], ["Lỗi logic"])
        self.assertTrue(p2["parse_ok"])               # recovered by the retry
        self.assertEqual(p2["labels"], [])


class ScriptedLocal(LocalChatBackend):
    name = "scripted"

    def __init__(self):
        super().__init__("fake-qwen", hardware="test-box")
        self.seen = []

    def _complete(self, messages, temperature, max_tokens, seed):
        self.seen.append((messages[-1]["content"], temperature, max_tokens, seed))
        return f"out{len(self.seen)}", 10, 3


def req(sid):
    return {"sample": SimpleNamespace(sample_id=sid), "messages": [{"role": "user", "content": sid}]}


class TestLocalBackend(unittest.TestCase):
    def test_n_samples_usage_and_info(self):
        b = ScriptedLocal()
        out = b.generate([req("A"), req("B")], {"n": 2, "temperature": 0.7, "max_new_tokens": 64, "seed": 1})
        self.assertEqual(out, [["out1", "out2"], ["out3", "out4"]])
        self.assertEqual(b.usage, {"requests": 4, "prompt_tokens": 40, "output_tokens": 12})
        info = b.info()
        self.assertEqual((info["backend"], info["model"], info["hardware"]), ("scripted", "fake-qwen", "test-box"))
        self.assertIsNone(info["peak_memory_gb"])

    def test_seeds_differ_per_vote_and_are_stable_per_sample(self):
        b1, b2 = ScriptedLocal(), ScriptedLocal()
        gen = {"n": 2, "temperature": 0.7, "seed": 5}
        b1.generate([req("A"), req("B")], gen)
        b2.generate([req("B")], gen)          # same sample in another chunk -> same seeds
        seeds1 = {(c, s) for c, _, _, s in b1.seen}
        self.assertEqual(len({s for _, s in seeds1}), 4)
        self.assertEqual({s for c, s in seeds1 if c == "B"}, {s for _, _, _, s in b2.seen})

    def test_greedy_with_n_gt_1_rejected(self):
        with self.assertRaises(ValueError):
            ScriptedLocal().generate([req("A")], {"n": 3, "temperature": 0.0})


class TestRunApiCot(unittest.TestCase):
    def test_end_to_end_metrics_and_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds = load_task2(make_dataset(Path(tmp) / "d", [("A1", "EXA", ["Lỗi logic"]), ("A2", "EXA", [])]))

            class Answering(ScriptedLocal):
                def _complete(self, messages, temperature, max_tokens, seed):
                    super()._complete(messages, temperature, max_tokens, seed)
                    return cot_answer("Lỗi logic"), 10, 3

            m = run_api(COT_CFG, ds, ds.samples, Answering(), Path(tmp) / "out", registry=None)
            self.assertEqual(m["parse_failures"], 0)
            self.assertIn("macro_f1", m["systems"]["api"])
            res = json.loads((Path(tmp) / "out" / "resources.json").read_text(encoding="utf-8"))
            self.assertEqual(res["hardware"], "test-box")
            self.assertEqual(res["tokens_out"], 6)



class TestReportAndBundle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ds = load_task2(make_dataset(self.root / "d", [("A1", "EXA", ["Lỗi logic"]),
                                                           ("A2", "EXA", ["Lỗi hàm"])]))

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self):
        class Answering(ScriptedLocal):
            def _complete(self, messages, temperature, max_tokens, seed):
                super()._complete(messages, temperature, max_tokens, seed)
                return cot_answer("Lỗi logic") + "\n</script><b>x</b>", 10, 3

        backend = Answering()
        m = run_and_report(COT_CFG, self.ds, self.ds.samples, backend, self.root / "out", registry=None)
        return backend, m

    def test_debug_rows_and_html(self):
        self._run()
        rows = [json.loads(x) for x in (self.root / "out" / "debug.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r["sample_id"] for r in rows], ["A1", "A2"])
        self.assertEqual((rows[0]["tp"], rows[0]["fp"], rows[0]["fn"]), (["Lỗi logic"], [], []))
        self.assertEqual((rows[1]["fp"], rows[1]["fn"]), (["Lỗi logic"], ["Lỗi hàm"]))
        self.assertEqual(rows[0]["output_tokens"], 3)
        self.assertFalse(rows[0]["no_reasoning"])
        self.assertIn("#include", rows[0]["code"])
        page = (self.root / "out" / "report.html").read_text(encoding="utf-8")
        self.assertEqual(page.count("</script>"), 2)   # model text cannot close the data tag
        self.assertNotIn("__DATA__", page)

    def test_flags_answer_without_reasoning(self):
        from src.task2.cot_report import build_rows
        out = self.root / "nr"
        out.mkdir()
        rec = {"sample_id": "A1", "exam_id": "EXA", "demos": [],
               "outputs": [f'{FINAL_MARKER} {{"taxonomy_error": []}}'], "retry_outputs": []}
        (out / "raw_outputs.jsonl").write_text(json.dumps({"sample_id": "A1", "key": "k", "record": rec}) + "\n",
                                                encoding="utf-8")
        pipe = Task2ApiPipeline(self.ds, None, COT_CFG)
        rows = build_rows(out, self.ds.samples[:1], pipe.postprocess)
        self.assertTrue(rows[0]["no_reasoning"])
        self.assertEqual(rows[0]["reasoning_chars"], 0)

    def test_report_from_interrupted_run(self):
        self._run()
        (self.root / "out" / "predictions_full.json").unlink()   # as if the run died before the end
        from src.task2.cot_report import write_debug_report
        pipe = Task2ApiPipeline(self.ds, None, COT_CFG)
        write_debug_report(self.root / "out", self.ds.samples, "t", postprocess=pipe.postprocess)
        rows = [json.loads(x) for x in (self.root / "out" / "debug.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(rows[0]["pred"], ["Lỗi logic"])

    def test_bundle_roundtrip(self):
        backend, m = self._run()
        saved = []
        b = export_bundle(self.root / "bundle", COT_CFG, "hf", {**backend.info(), "revision": "abc123"},
                          {"enabled": True, "source": "dataset"}, m, weights_saver=saved.append)
        self.assertEqual(saved, [b / "model"])
        meta = load_bundle(b)
        self.assertTrue(meta["prompt_matches_code"])
        self.assertEqual(meta["experiment"]["prompt"]["style"], "cot")
        self.assertEqual(backend_settings(meta), ("hf", {"hf": {"model": str(b / "model")}}))
        self.assertIn("giảng viên", (b / "prompt_system.txt").read_text(encoding="utf-8"))
        meta.pop("weights_path")
        meta["weights"] = None
        self.assertEqual(backend_settings(meta), ("hf", {"hf": {"model": "fake-qwen", "revision": "abc123"}}))
        self.assertEqual(backend_settings(meta, "mlx")[1]["mlx"]["model"],
                         "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit")

    def test_tee_log(self):
        with tee_log(self.root / "logs" / "run.log"):
            print("xin chào log")
        self.assertIn("xin chào log", (self.root / "logs" / "run.log").read_text(encoding="utf-8"))



SC_CFG = {**COT_CFG, "name": "t_sc", "generation": {"temperature": 0.7, "top_p": 0.9, "n": 3, "max_new_tokens": 64}}


class VotingLocal(ScriptedLocal):
    """Answers cycle through `script` (one label list per call)."""

    def __init__(self, script):
        super().__init__()
        self.script = list(script)

    def _complete(self, messages, temperature, max_tokens, seed):
        super()._complete(messages, temperature, max_tokens, seed)
        return cot_answer(*self.script.pop(0)), 10, 3


class TestSelfConsistency(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ds = load_task2(make_dataset(self.root / "d", [("A1", "EXA", ["Lỗi logic"]), ("A2", "EXA", [])]))

    def tearDown(self):
        self.tmp.cleanup()

    def test_batched_override_called_once_per_sample(self):
        class Batched(ScriptedLocal):
            def _complete_n(self, messages, temperature, max_tokens, seed, n):
                self.seen.append((n, self.top_p, seed))
                return [(f"a{k}", 10, 3 + k, 0.5) for k in range(n)]

        b = Batched()
        out = b.generate([req("A")], {"n": 3, "temperature": 0.7, "top_p": 0.9, "max_new_tokens": 5})
        self.assertEqual(out, [["a0", "a1", "a2"]])
        self.assertEqual([(n, tp) for n, tp, _ in b.seen], [(3, 0.9)])
        self.assertEqual([e["vote"] for e in b.ledger], [0, 1, 2])
        self.assertEqual([e["hit_max_tokens"] for e in b.ledger], [False, False, True])
        self.assertEqual(b.usage["output_tokens"], 12)

    def test_majority_vote_and_report(self):
        script = [["Lỗi logic"], ["Lỗi logic", "Lỗi style"], ["Lỗi logic"],   # A1: logic 3/3, style 1/3
                  ["Lỗi hàm"], [], ["Lỗi hàm"]]                               # A2: hàm 2/3
        m = run_and_report(SC_CFG, self.ds, self.ds.samples, VotingLocal(script), self.root / "out", registry=None)
        self.assertEqual(m["parse_failures"], 0)
        rows = [json.loads(x) for x in (self.root / "out" / "debug.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(rows[0]["pred"], ["Lỗi logic"])
        self.assertEqual(rows[0]["split_labels"], ["Lỗi style"])
        self.assertAlmostEqual(rows[0]["probs"]["Lỗi style"], 1 / 3)
        self.assertEqual(rows[0]["output_labels"][1], ["Lỗi logic", "Lỗi style"])
        self.assertEqual(rows[1]["pred"], ["Lỗi hàm"])
        self.assertEqual(rows[1]["fp"], ["Lỗi hàm"])
        self.assertIn("Phiếu chia rẽ", (self.root / "out" / "report.html").read_text(encoding="utf-8"))


class TestCotCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse_shard(self):
        from src.task2.cot_cli import parse_shard
        self.assertEqual(parse_shard("2/3"), (2, 3))
        self.assertIsNone(parse_shard(None))
        with self.assertRaises(SystemExit):
            parse_shard("4/3")

    def test_compare_writes_json(self):
        from src.task2.cot_cli import compare

        def fake_run(name, macro):
            d = self.root / name
            d.mkdir()
            per = {lab: {"f1": macro} for lab in LABELS}
            (d / "metrics.json").write_text(json.dumps({"systems": {"api": {
                "macro_f1": macro, "micro_f1": macro, "exact_match": 0.0, "per_label": per}}}), encoding="utf-8")
            (d / "config.json").write_text(json.dumps({"ids": ["A1", "A2"]}), encoding="utf-8")
            return d

        out = compare(fake_run("sc", 0.4), fake_run("zs", 0.3))
        self.assertEqual(out["overall"]["macro_f1"], {"run": 0.4, "baseline": 0.3})
        self.assertTrue(out["same_ids"])
        self.assertTrue((self.root / "sc" / "compare.json").exists())
        self.assertIsNone(compare(self.root / "sc", self.root / "missing"))

    def test_cli_end_to_end_with_fake_backend(self):
        from unittest import mock

        from src.task2 import cot_cli
        project = Path(__file__).resolve().parents[1]
        data = make_dataset(self.root / "d", [("A1", "EXA", ["Lỗi logic"]), ("A2", "EXA", [])])
        run_cfg = self.root / "run.yaml"
        run_cfg.write_text("backend: mlx\nmlx: {model: fake/qwen}\nrun: {experiment: x, smoke_sample_ids: [A1], "
                           "predict: false, use_cache: true}\n", encoding="utf-8")
        argv = ["--run-config", str(run_cfg), "--gold-root", str(data), "--no-compile", "--limit", "2",
                "--output-dir", str(self.root / "out"), "--public-root", str(data), "--public-shard", "1/2"]
        with mock.patch.object(cot_cli, "make_local_backend",
                               side_effect=lambda kind, st: VotingLocal([["Lỗi logic"]] * 20)):
            cot_cli.main(project, "cot_zero_shot", argv=argv)
            cot_cli.main(project, "cot_self_consistency", baseline="cot_zero_shot", argv=argv)
        names = sorted(p.name for p in (self.root / "out").iterdir())
        zs = "task2_cot_zero_shot_silver__mlx__fake-qwen"
        sc = "task2_cot_sc_silver__mlx__fake-qwen"
        self.assertEqual(names, sorted([zs, zs + "_predict", sc, sc + "_predict"]))
        cmp_ = json.loads((self.root / "out" / sc / "compare.json").read_text(encoding="utf-8"))
        self.assertEqual(cmp_["baseline"], zs)
        sub = json.loads((self.root / "out" / (sc + "_predict") / "predictions.json").read_text(encoding="utf-8"))
        self.assertEqual([x["sample_id"] for x in sub], ["A1"])     # shard 1/2 of [A1, A2]
        usage = (self.root / "out" / sc / "usage.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(usage), 2 * 5)                          # n=5 votes per sample
        self.assertIn("so sánh", (self.root / "out" / sc / "run.log").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
