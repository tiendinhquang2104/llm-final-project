import json

import numpy as np

from src.data.loader import DIM_MAX, DIMENSIONS
from src.task1.clm_probe import RubricProbe, finalize, load_rubrics, run_task1_clm, to_rubric
from src.task1.evaluator import validate_predictions
from src.task2.clm.encoder import CachedEncoder
from src.task2.clm.text import build_state_texts
from src.task2.data import load_task2
from tests._task2 import EXAMS, FakeEncoder, make_dataset

ZERO_STMT = "Nhận 0 điểm nếu: vi phạm quy định, giống bài người khác, không biên dịch được"


def _write_task1(root, rows):
    samples = []
    for sid, eid, rub in rows:
        s = {"sample_id": sid, "input": {"exam_id": eid}}
        if rub is not None:
            s["output"] = {"rubric": rub, "total_score": sum(rub.values())}
        samples.append(s)
    (root / "task1_grading.json").write_text(json.dumps({"task": "task1", "samples": samples}), encoding="utf-8")


def _rubric(i):
    return {"compilable": i % 2, "io_format": (i // 2) % 2, "logic": i % 5, "edge_case": i % 3,
            "complexity": i % 2, "code_quality": (i // 3) % 2}


def _setup(tmp_path):
    gold_ids = [(f"g{i}", "EXA" if i % 2 else "EXB") for i in range(8)]
    pub_ids = [(f"p{i}", "EXA" if i % 2 else "EXB") for i in range(4)]
    g = make_dataset(tmp_path / "gold", [(s, e, []) for s, e in gold_ids])
    p = make_dataset(tmp_path / "pub", [(s, e, None) for s, e in pub_ids])
    _write_task1(g, [(s, e, _rubric(i)) for i, (s, e) in enumerate(gold_ids)])
    _write_task1(p, [(s, e, None) for s, e in pub_ids])
    return g, p, [s for s, _ in pub_ids]


def test_probe_linear_and_constant():
    rng = np.random.default_rng(0)
    X = rng.standard_normal((20, 3))
    R = np.stack([X[:, 0] * 2 + 1, np.full(20, 3.0)], axis=1)
    pr = RubricProbe(alpha=1e-6).fit(X, R)
    P = pr.predict(X)
    assert np.allclose(P[:, 0], R[:, 0], atol=1e-3)
    assert np.allclose(P[:, 1], 3.0)


def test_to_rubric_rounds_and_clamps():
    r = to_rubric([0.4, 1.6, 4.7, -0.4, 9, 0.5])
    assert r == {"compilable": 0, "io_format": 1, "logic": 4, "edge_case": 0, "complexity": 1, "code_quality": 1}
    assert all(isinstance(v, int) and 0 <= v <= DIM_MAX[d] for d, v in r.items())


def test_finalize_compile_gate():
    rub = {"compilable": 0, "io_format": 1, "logic": 3, "edge_case": 1, "complexity": 1, "code_quality": 1}
    zero_exam = {**EXAMS["exams"][0], "statement": "x\n" + ZERO_STMT}
    r, t = finalize(rub, zero_exam)
    assert t == 0 and set(r.values()) == {0}
    r, t = finalize(rub, EXAMS["exams"][0])
    assert r["code_quality"] == 1 and r["logic"] == 0 and t == 1
    assert finalize(rub, zero_exam, compile_gate=False)[1] == 7


def test_run_end_to_end(tmp_path):
    g, p, pub_ids = _setup(tmp_path)
    gold, public = load_task2(g), load_task2(p)
    rubrics = load_rubrics(g)
    assert len(rubrics) == 8
    cfg = {"name": "task1_test", "text": {"max_tokens": 512}, "task1": {"alphas": [0.1, 1.0, 10.0]},
           "cv": {"folds": 4}}
    enc = CachedEncoder(FakeEncoder(), tmp_path / "cache")
    reg = tmp_path / "reg.csv"
    m = run_task1_clm(cfg, enc, gold, rubrics, public, pub_ids, tmp_path / "out", registry=reg)
    preds = json.loads((tmp_path / "out" / "predictions.json").read_text())
    assert validate_predictions(preds, set(pub_ids)) == []
    assert {x["sample_id"] for x in preds} == set(pub_ids)
    assert m["systems"]["ridge"]["n"] == 8
    assert m["chosen_alpha"] in cfg["task1"]["alphas"]
    assert set(m["alpha_selection"]) == {"0.1", "1.0", "10.0"}
    assert "mean_baseline" in m["systems"]
    assert "task1" in reg.read_text()


def test_context_text_matches_task2(tmp_path):
    g, p, pub_ids = _setup(tmp_path)
    gold = load_task2(g)
    seen = []

    class Rec(FakeEncoder):
        def embed(self, texts):
            seen.extend(texts)
            return super().embed(texts)

    from src.task1.clm_probe import embed_contexts
    text_cfg = {"max_tokens": 512}
    enc = Rec()
    X = embed_contexts(gold.samples, gold.exams, enc, text_cfg)
    want = [build_state_texts(gold.exams[s.exam_id], s, enc.tokenizer, **text_cfg)["context"] for s in gold.samples]
    assert seen == want
    assert X.shape == (8, 17) and set(X[:, -1]) == {0.0}
