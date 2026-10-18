import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.llm.local_backend import OOM_MARK, LocalChatBackend
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
        self.assertIn("8. Style:", user)              # nine grading steps, as a fill-in template
        self.assertNotIn("đúng một dòng", user)      # read as "answer in one line" -> no reasoning
        self.assertLess(user.index("8. Style: <"), user.rindex(FINAL_MARKER))
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

    def test_oom_retry_resends_original_prompt(self):
        backend = FakeBackend([f"{OOM_MARK} CUDA out of memory, prompt ~4000 token", cot_answer("Lỗi logic")])
        pipe = Task2ApiPipeline(self.ds, backend, COT_CFG)
        rec = pipe.infer([self.by["A1"]])[0]
        self.assertEqual(backend.calls[1]["messages"], backend.calls[0]["messages"])  # no "[OOM]" turn, no fix-JSON ask
        self.assertEqual(pipe.postprocess(rec)["labels"], ["Lỗi logic"])


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
        zs = "task2_cot_zero_shot_custom__mlx__fake-qwen"
        sc = "task2_cot_sc_custom__mlx__fake-qwen"
        self.assertEqual(names, sorted([zs, zs + "_predict", sc, sc + "_predict"]))
        cmp_ = json.loads((self.root / "out" / sc / "compare.json").read_text(encoding="utf-8"))
        self.assertEqual(cmp_["baseline"], zs)
        sub = json.loads((self.root / "out" / (sc + "_predict") / "predictions.json").read_text(encoding="utf-8"))
        self.assertEqual([x["sample_id"] for x in sub], ["A1"])     # shard 1/2 of [A1, A2]
        usage = (self.root / "out" / sc / "usage.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(usage), 2 * 5)                          # n=5 votes per sample
        self.assertIn("so sánh", (self.root / "out" / sc / "run.log").read_text(encoding="utf-8"))



class FakeOOM(Exception):
    pass


def oom_backend(fail):
    """HFChatBackend without a model: `_generate` raises FakeOOM when fail(n, seed) is true."""
    from src.llm.local_backend import HFChatBackend
    b = HFChatBackend.__new__(HFChatBackend)
    LocalChatBackend.__init__(b, "fake-hf", hardware="gpu")
    b.oom_error = FakeOOM
    b.torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
    b.tok = SimpleNamespace(apply_chat_template=lambda m, **k: "x" * 300)
    b.memory_report = lambda: "mem"
    b.calls = []

    def gen(messages, temperature, max_tokens, seed, n):
        b.calls.append((n, seed))
        if fail(n, seed):
            raise FakeOOM()
        return [(cot_answer("Lỗi logic"), 100, 5, 0.1)] * n
    b._generate = gen
    return b


class TestOOMFallback(unittest.TestCase):
    def test_batched_oom_falls_back_to_one_by_one(self):
        b = oom_backend(lambda n, seed: n > 1)
        out = b.generate([req("A")], {"n": 3, "temperature": 0.7, "seed": 0})
        self.assertEqual(len(out[0]), 3)
        self.assertEqual([n for n, _ in b.calls], [3, 1, 1, 1])
        self.assertEqual(len({s for n, s in b.calls if n == 1}), 3)    # distinct seeds per vote

    def test_single_oom_gives_placeholder_and_run_continues(self):
        from src.llm.local_backend import OOM_MARK
        b = oom_backend(lambda n, seed: True)
        out = b.generate([req("A"), req("B")], {"n": 1, "temperature": 0.0})
        self.assertTrue(all(o[0].startswith(OOM_MARK) for o in out))
        self.assertIsNone(parse_cot_labels(out[0][0]))                   # never parses -> retried on rerun

    def test_report_flags_oom(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds = load_task2(make_dataset(Path(tmp) / "d", [("A1", "EXA", ["Lỗi logic"])]))
            b = oom_backend(lambda n, seed: True)
            m = run_and_report(COT_CFG, ds, ds.samples, b, Path(tmp) / "out", registry=None)
            self.assertEqual(m["parse_failures"], 1)
            row = json.loads((Path(tmp) / "out" / "debug.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertTrue(row["oom"])



class TestLenientLabels(unittest.TestCase):
    def test_coerce_short_names_and_step_headers(self):
        from src.task2.labels import coerce_labels
        self.assertEqual(coerce_labels(["Vòng lặp", "Hàm", "Logic", "Thuật toán"]),
                         ["Lỗi logic", "Lỗi vòng lặp", "Lỗi hàm", "Lỗi thuật toán"])
        self.assertEqual(coerce_labels(["Vòng lặp và mảng/chuỗi"]), ["Lỗi vòng lặp", "Lỗi mảng/chuỗi"])
        self.assertEqual(coerce_labels(["lỗi STYLE ", "hardcode"]), ["Lỗi hard-code", "Lỗi style"])
        self.assertEqual(coerce_labels(["Lỗi lạ", "Logic và cái gì đó"]), [])
        self.assertEqual(coerce_labels("Lỗi logic"), [])

    def test_cot_parser_maps_short_names(self):
        text = '7. Style: ổn.\nKẾT LUẬN: {"taxonomy_error": ["Vòng lặp", "Lỗi hàm"]}'
        self.assertEqual(parse_cot_labels(text), ["Lỗi vòng lặp", "Lỗi hàm"])


class TestCompileRule(unittest.TestCase):
    LOGS = {"A1": "", "A2": "student.cpp:3:5: error: 'x' was not declared",
            "A3": "student.cpp:9:1: warning: no return statement [-Wreturn-type]",
            "A4": "/usr/bin/ld: undefined reference to `main'\ncollect2: error: ld returned 1 exit status"}

    def run_rule(self, answers, rule=True):
        with tempfile.TemporaryDirectory() as tmp:
            ds = load_task2(make_dataset(Path(tmp), [(k, "EXA", []) for k in self.LOGS]))
            for smp in ds.samples:
                smp.compile_log = self.LOGS[smp.sample_id]
            cfg = {**COT_CFG, "prompt": {**COT_CFG["prompt"], "compile_rule": rule}, "retry_on_parse_fail": 0}
            pipe = Task2ApiPipeline(ds, FakeBackend(answers), cfg)
            return {p["sample_id"]: p for p in map(pipe.postprocess, pipe.infer(ds.samples))}

    def test_rule_overrides_model_both_ways(self):
        preds = self.run_rule([cot_answer("Lỗi biên dịch", "Lỗi logic"), cot_answer(),
                               cot_answer("Lỗi biên dịch"), cot_answer("Lỗi biên dịch")])
        self.assertEqual(preds["A1"]["labels"], ["Lỗi logic"])          # clean log: model's compile label dropped
        self.assertEqual(preds["A1"]["model_compile_vote"], 1.0)
        self.assertEqual(preds["A2"]["labels"], ["Lỗi biên dịch"])      # real error: added
        self.assertEqual(preds["A3"]["labels"], [])                     # warning only
        self.assertEqual(preds["A4"]["labels"], [])                     # missing main (link) does not count

    def test_rule_applies_when_answer_unparsed(self):
        preds = self.run_rule(["rác", "rác", "rác", "rác"])
        self.assertFalse(preds["A2"]["parse_ok"])
        self.assertEqual(preds["A2"]["labels"], ["Lỗi biên dịch"])
        self.assertEqual(preds["A1"]["labels"], [])

    def test_rule_off_keeps_model_vote(self):
        preds = self.run_rule([cot_answer("Lỗi biên dịch")] * 4, rule=False)
        self.assertEqual(preds["A1"]["labels"], ["Lỗi biên dịch"])


LOOP = "#include <iostream>\nint main() {\n  int n, s = 0; std::cin >> n;\n  for (int i = 0; i <= n; i++) s += i;\n" \
       "  std::cout << s;\n}\n"
REC = "#include <iostream>\nint f(int n) { return n ? n + f(n - 1) : 0; }\nint main() { int n; std::cin >> n; " \
      "std::cout << f(n); }\n"


class TestDemoRetriever(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.gold = load_task2(make_dataset(root / "g", [("G1", "EXA", ["Lỗi vòng lặp"]), ("G2", "EXA", [])],
                                            code={"G1": LOOP, "G2": REC}))
        self.silver = load_task2(make_dataset(root / "s", [("S1", "EXA", ["Lỗi logic"]), ("S2", "EXA", ["Lỗi hàm"])],
                                              code={"S1": LOOP + "// s1\n", "S2": REC + "// s2\n"}))

    def tearDown(self):
        self.tmp.cleanup()

    def test_gold_first_then_silver_and_never_self(self):
        from src.task2.cot_demos import DemoRetriever
        r = DemoRetriever(self.gold.samples, self.silver.samples, k=3, min_gold_sim=0.6)
        demos = r.select(self.gold.by_id()["G1"])
        ids = [d.sample.sample_id for d in demos]
        self.assertNotIn("G1", ids)
        self.assertEqual(ids[0], "S1")             # G2 is below min_gold_sim -> silver fills, most similar first
        self.assertEqual([d.source for d in demos], ["silver", "silver"])
        r0 = DemoRetriever(self.gold.samples, self.silver.samples, k=2, min_gold_sim=0.0)
        self.assertEqual([d.source for d in r0.select(self.silver.by_id()["S1"])], ["gold", "gold"])
        self.assertEqual(r.info(), {"k": 3, "min_gold_sim": 0.6, "gold": 2, "silver": 2})

    def test_prompt_shows_demos_and_budget_drops_them(self):
        from src.task2.cot_demos import DemoRetriever
        r = DemoRetriever(self.gold.samples, self.silver.samples, k=2, min_gold_sim=0.0)
        cfg = {**COT_CFG, "prompt": {**COT_CFG["prompt"], "few_shot_k": 2}}
        req = Task2ApiPipeline(self.gold, None, cfg, r).build_request(self.gold.by_id()["G1"])
        user = req["messages"][1]["content"]
        self.assertEqual(len(req["demos"]), 2)
        self.assertTrue(all(d.startswith(("gold:", "silver:")) for d in req["demos"]))
        self.assertIn("VÍ DỤ BÀI ĐÃ ĐƯỢC GIẢNG VIÊN CHẤM", user)
        self.assertLess(user.index("VÍ DỤ"), user.index("BÀI NỘP CẦN PHÂN LOẠI"))
        self.assertNotIn("feedback", user.lower())
        total = sum(len(m["content"]) for m in req["messages"])
        small = {**cfg, "prompt": {**cfg["prompt"], "max_prompt_chars": total - 10}}
        req2 = Task2ApiPipeline(self.gold, None, small, r).build_request(self.gold.by_id()["G1"])
        self.assertEqual(len(req2["demos"]), 1)


    def test_bundle_pins_demo_pools_and_demos(self):
        from src.task2.cot_bundle import check_demo_pools
        from src.task2.cot_demos import DemoRetriever
        r = DemoRetriever(self.gold.samples, self.silver.samples, k=2, min_gold_sim=0.0)
        cfg = {**COT_CFG, "prompt": {**COT_CFG["prompt"], "few_shot_k": 2}}
        out = Path(self.tmp.name) / "run"
        backend = VotingLocal([["Lỗi logic"]] * 4)
        m = run_and_report(cfg, self.gold, self.gold.samples, backend, out, registry=None, demo_pool=r)
        b = export_bundle(Path(self.tmp.name) / "bundle", cfg, "mlx", backend.info(), None, m,
                          demo_pools=r.fingerprint(), run_dir=out, partial=True)
        meta = load_bundle(b)
        self.assertTrue(meta["gold_metrics"]["partial"])
        self.assertEqual(meta["demo_pools"]["gold"]["n"], 2)
        demos = json.loads((b / "demos.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(demos), ["G1", "G2"])
        self.assertIn("demos.json", (b / "README.md").read_text(encoding="utf-8"))
        self.assertEqual(check_demo_pools(meta, r.fingerprint()), [])
        other = DemoRetriever(self.gold.samples, self.silver.samples[:1], k=2)
        self.assertEqual(len(check_demo_pools(meta, other.fingerprint())), 1)   # silver changed
        self.assertTrue(check_demo_pools(meta, None))



class TestPredictScript(unittest.TestCase):
    def test_resolve_bundle_best_name_and_path(self):
        import importlib.util
        from unittest import mock
        path = Path(__file__).resolve().parents[1] / "scripts" / "predict_task2_cot.py"
        spec = importlib.util.spec_from_file_location("predict_task2_cot", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "cot_fewshot_sc").mkdir()
            (root / "BEST").write_text("cot_fewshot_sc\n# note\n", encoding="utf-8")
            with mock.patch.object(mod, "BUNDLES", root):
                self.assertEqual(mod.resolve_bundle("best"), root / "cot_fewshot_sc")
                self.assertEqual(mod.resolve_bundle("cot_zero_shot"), root / "cot_zero_shot")
                self.assertEqual(mod.resolve_bundle(str(root / "cot_fewshot_sc")), root / "cot_fewshot_sc")
        self.assertIn(mod.auto_backend(), ("mlx", "hf"))



class TestStripComments(unittest.TestCase):
    CODE = ("int f(int n) { return n; }\n"
            "// bool isArm(int a)\n"
            "// {\n"
            "//     return a > 0;\n"
            "// }\n"
            "/* old\n   version */ int g() { return 1; }\n"
            'int main() { std::cout << "a // b"; }\n')

    def test_line_numbers_and_literals_kept(self):
        from src.task2.prompts_cot import strip_comments
        out = strip_comments(self.CODE)
        self.assertEqual(out.count("\n"), self.CODE.count("\n"))
        self.assertNotIn("isArm", out)
        self.assertNotIn("old", out)
        self.assertEqual(out.splitlines()[6].strip(), "int g() { return 1; }")   # still line 7
        self.assertIn('"a // b"', out)

    def test_all_commented(self):
        from src.task2.prompts_cot import ALL_COMMENTED, strip_comments
        self.assertEqual(strip_comments("//int main() {}\n/* x */\n"), ALL_COMMENTED)
        self.assertEqual(strip_comments(""), "")

    def test_prompt_and_demos_hide_comments_only_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds = load_task2(make_dataset(Path(tmp), [("A1", "EXA", []), ("A2", "EXA", ["Lỗi logic"])],
                                         code={"A1": self.CODE, "A2": self.CODE}))
            from src.task2.cot_demos import DemoRetriever
            r = DemoRetriever(ds.samples, [], k=1, min_gold_sim=0.0)
            on = {**COT_CFG, "prompt": {**COT_CFG["prompt"], "few_shot_k": 1, "strip_comments": True}}
            user = Task2ApiPipeline(ds, None, on, r).build_request(ds.by_id()["A1"])["messages"][1]["content"]
            self.assertNotIn("isArm", user)                       # neither in the demo nor in the submission
            self.assertIn("   7| ", user)                          # numbering kept
            off = {**on, "prompt": {**on["prompt"], "strip_comments": False}}
            user_off = Task2ApiPipeline(ds, None, off, r).build_request(ds.by_id()["A1"])["messages"][1]["content"]
            self.assertIn("isArm", user_off)
            self.assertEqual(ds.by_id()["A1"].code, self.CODE)     # the dataset itself is untouched



class TestExamRequirements(unittest.TestCase):
    PRIVATE = {  # an unseen exam: other file, other parameter name, other wording
        "exam_id": "PRIV-1", "exam_type": "multi_problem", "data_file": "students-2027.txt",
        "note": "Bài nộp chỉ chứa hàm, không có main.",
        "grading_policy": "Nếu P1 sai thì P2 không được chấm.",
        "statement": "Only `iostream, fstream,` and `string` library is allowed. Do not use `sort`. "
                     "You must work in-place, không dùng thêm mảng phụ.",
        "problems": [{"pid": "P1", "prototype": "Student* readAll(string path_to_file, int& n);",
                      "is_prerequisite_for": ["P2"]},
                     {"pid": "P2", "prototype": "double avg(Student* s, int n);", "constraints": "không được dùng vector"}],
    }

    def test_private_exam_uses_its_own_fields(self):
        from src.task2.prompts_cot import exam_requirements
        r = exam_requirements(self.PRIVATE)
        self.assertIn("`Student* readAll(string path_to_file, int& n);` (điều kiện để chấm P2)", r)
        self.assertIn("`students-2027.txt`", r)
        self.assertIn("tham số `path_to_file`", r)
        self.assertIn("Thư viện được phép: iostream, fstream, string.", r)
        self.assertIn("Hàm bị cấm: `sort`, `vector`.", r)
        self.assertIn("KHÔNG có main là đúng", r)
        for leaked in ("50-best", "prob1", "General", "filename", "thêm"):
            self.assertNotIn(leaked, r)

    def test_missing_fields_give_no_lines(self):
        from src.task2.prompts_cot import exam_requirements
        self.assertEqual(exam_requirements({"exam_id": "X", "exam_type": "single_problem", "statement": "Viết chương trình."}), "")
        r = exam_requirements({"exam_id": "Y", "exam_type": "single_problem",
                               "problems": [{"pid": "P1", "io_mode": "stdin/stdout"}]})
        self.assertIn("stdin", r)
        self.assertNotIn("File dữ liệu", r)
        self.assertNotIn("Hàm bắt buộc", r)

    def test_metadata_fields(self):
        from src.task2.prompts_cot import exam_requirements
        r = exam_requirements({"exam_id": "Z", "exam_type": "single_problem", "language": "cpp11", "topic": ["Hàm"],
                               "learning_outcome": "Vận dụng hàm.", "has_hidden_testcases": True,
                               "bloom_level": ["Analyze"], "difficulty_teacher": "D3 - Trung bình"})
        self.assertIn("Chuẩn ngôn ngữ: C++11.", r)
        self.assertIn("Trọng tâm đề: Vận dụng hàm. (chủ đề: Hàm)", r)
        self.assertIn("test ẩn", r)
        for unused in ("Analyze", "D3"):
            self.assertNotIn(unused, r)
        r = exam_requirements({"exam_id": "W", "exam_type": "multi_problem", "has_hidden_testcases": False})
        self.assertNotIn("test ẩn", r)

    def test_teacher_guide_covers_every_label(self):
        from src.task2.prompts_cot import TEACHER_GUIDE
        self.assertEqual(set(TEACHER_GUIDE), set(LABELS))
        self.assertIn("toàn bộ code của bài nằm trong comment", SYSTEM_COT)

    def test_prompt_has_requirements_and_nine_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds = load_task2(make_dataset(Path(tmp), [("B1", "EXB", [])]))
            user = Task2ApiPipeline(ds, None, COT_CFG).build_request(ds.samples[0])["messages"][1]["content"]
            self.assertIn("## YÊU CẦU CỦA ĐỀ", user)
            self.assertLess(user.index("YÊU CẦU CỦA ĐỀ"), user.index("BÀI NỘP CẦN PHÂN LOẠI"))
            self.assertIn("9. Rà lại: <", user)
            self.assertIn("2. Phạm vi chấm: <", user)


class TestAbstentionVote(unittest.TestCase):
    def test_unparsed_answers_count_against_the_majority(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds = load_task2(make_dataset(Path(tmp), [("A1", "EXA", [])]))
            cfg = {**COT_CFG, "generation": {"temperature": 0.7, "n": 5}, "retry_on_parse_fail": 0}
            answers = [cot_answer("Lỗi logic"), cot_answer("Lỗi logic"), cot_answer(), "rác", "rác"]
            pipe = Task2ApiPipeline(ds, FakeBackend(answers), cfg)
            pred = pipe.postprocess(pipe.infer(ds.samples)[0])
            self.assertAlmostEqual(pred["probs"]["Lỗi logic"], 2 / 5)   # was 2/3 of the parsed answers
            self.assertEqual(pred["labels"], [])


if __name__ == "__main__":
    unittest.main()


class TestPromptLang(unittest.TestCase):
    EN = {**COT_CFG, "prompt": {**COT_CFG["prompt"], "lang": "en", "strip_comments": True}}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ds = load_task2(make_dataset(Path(self.tmp.name), [("B1", "EXB", ["Lỗi logic"])]))
        self.ds.samples[0].compile_log = "student.cpp:3:5: error: 'x' was not declared in this scope"

    def tearDown(self):
        self.tmp.cleanup()

    def test_english_prompt(self):
        from src.task2.prompts_cot import FINAL_MARKER_EN, SYSTEM_COT_EN
        req = Task2ApiPipeline(self.ds, None, self.EN).build_request(self.ds.samples[0])
        system, user = req["messages"][0]["content"], req["messages"][1]["content"]
        self.assertEqual(system, SYSTEM_COT_EN)
        for lab in LABELS:                                  # labels stay the official Vietnamese names
            self.assertIn(f'"{lab}"', system)
        for head in ("## EXAM (", "## EXAM REQUIREMENTS", "## SUBMISSION TO GRADE", "## HOW TO GRADE",
                     "9. Review: <", "2. Scope: <", FINAL_MARKER_EN, "was not declared"):
            self.assertIn(head, user)
        for vi in ("## ĐỀ BÀI", "## BÀI NỘP", "## CÁCH CHẤM", "YÊU CẦU CỦA ĐỀ", FINAL_MARKER):
            self.assertNotIn(vi, user)

    def test_same_rules_in_both_languages(self):
        from src.task2.prompts_cot import STEPS, STEPS_EN, TEACHER_GUIDE_EN, _REQ
        self.assertEqual(len(STEPS), len(STEPS_EN))
        self.assertEqual(set(TEACHER_GUIDE_EN), set(LABELS))
        self.assertEqual(set(_REQ["vi"]), set(_REQ["en"]))

    def test_default_is_vietnamese_and_bad_lang_fails(self):
        req = Task2ApiPipeline(self.ds, None, COT_CFG).build_request(self.ds.samples[0])
        self.assertEqual(req["messages"][0]["content"], SYSTEM_COT)
        bad = {**COT_CFG, "prompt": {**COT_CFG["prompt"], "lang": "fr"}}
        with self.assertRaises(ValueError):
            Task2ApiPipeline(self.ds, None, bad).build_request(self.ds.samples[0])

    def test_parse_english_answer(self):
        text = ('1. Compilation: none.\n4. Loops: `for (;;) {}` never stops.\n'
                'CONCLUSION: {"taxonomy_error": ["Loop error", "Lỗi logic"]}')
        self.assertEqual(parse_cot_labels(text), ["Lỗi logic", "Lỗi vòng lặp"])

    def test_last_marker_of_either_language_wins(self):
        from src.task2.prompts_cot import split_final
        reasoning, tail = split_final('KẾT LUẬN: {"taxonomy_error": []}\nCONCLUSION: {"taxonomy_error": ["Lỗi hàm"]}')
        self.assertIn("KẾT LUẬN", reasoning)
        self.assertIn("Lỗi hàm", tail)
        self.assertEqual(split_final("no marker"), ("no marker", None))

    def test_bundle_records_the_language(self):
        from src.task2.cot_bundle import prompt_sha256
        self.assertNotEqual(prompt_sha256("vi"), prompt_sha256("en"))
        b = export_bundle(Path(self.tmp.name) / "bundle", self.EN, "mlx", {"model": "m"}, None)
        meta = load_bundle(b)
        self.assertTrue(meta["prompt_matches_code"])
        self.assertIn("CONCLUSION", (b / "prompt_instruction.txt").read_text(encoding="utf-8"))
