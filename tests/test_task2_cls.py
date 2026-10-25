"""F-cls: training views, oversampling, decisions, thresholds, checkpoint discovery and a tiny CPU train/resume."""
from __future__ import annotations

import glob
import json
import time
from pathlib import Path

import numpy as np
import pytest

from src.task2.cls_data import eval_records, folds, oversample, pos_weight, sample_weights, train_records
from src.task2.cls_post import cross_fold_thresholds, decide, fixed_thresholds, tuned_thresholds
from src.task2.labels import LABELS, to_vector

PP = {"compile_rule": True, "compile_max_extra": 1, "all_commented_style": True, "max_labels": 3,
      "default_threshold": 0.5, "edge_case_threshold": 0.9}
GCC_ERR = "student.cpp:3:5: error: expected ';' before 'return'"


def rec(i, source, fold=None, labels=(), log=None, commented=False):
    labels = list(labels)
    return {"id": i, "source": source, "exam_id": fold or "SYN", "exam_type": "single_problem", "fold": fold,
            "labels": None if source == "public" else labels, "y": None if source == "public" else to_vector(labels),
            "compile_log": log, "all_commented": commented,
            "messages": [{"role": "system", "content": "s"}, {"role": "user", "content": f"code {i}"}]}


@pytest.fixture
def records():
    return [rec("EX01-S1", "gold", "EX01", ["Lỗi logic"]), rec("EX01-S1~m", "gold_mut", "EX01", ["Lỗi logic", "Lỗi style"]),
            rec("EX02-S2", "gold", "EX02", ["Lỗi hàm"]), rec("EX02-S2~m", "gold_mut", "EX02", ["Lỗi hàm"]),
            rec("SYN-1", "synth", None, ["Lỗi thuật toán"]), rec("SYN-2", "synth", None, []),
            rec("PUB-1", "public")]


def test_fold_views_keep_the_holdout_exam_out(records):
    assert folds(records) == ["EX01", "EX02"]
    ids = {r["id"] for r in train_records(records, "EX01")}
    assert ids == {"EX02-S2", "EX02-S2~m", "SYN-1", "SYN-2"}
    assert {r["id"] for r in eval_records(records, "EX01")} == {"EX01-S1"}
    assert {r["id"] for r in train_records(records, "all")} == {r["id"] for r in records} - {"PUB-1"}
    assert {r["id"] for r in train_records(records, None, use_gold=False, use_mutants=False)} == {"SYN-1", "SYN-2"}


def test_oversample_reaches_min_count_deterministically(records):
    train = train_records(records, "all")
    a = oversample(train, 3, seed=1)
    b = oversample(train, 3, seed=1)
    assert [r["id"] for r in a] == [r["id"] for r in b]
    j = LABELS.index("Lỗi thuật toán")
    assert sum(r["y"][j] for r in a) == 3
    assert max(sum(r["id"] == i for r in a) for i in {r["id"] for r in a}) <= 4  # max_factor
    assert oversample(train, 0) == train


def test_pos_weight_and_source_weight(records):
    train = train_records(records, "all")
    pw = pos_weight(train, cap=2.0)
    assert pw[LABELS.index("Lỗi edge case")] == 1.0  # no positive
    assert pw[LABELS.index("Lỗi thuật toán")] == 2.0  # 5 negatives / 1 positive, capped
    assert sample_weights(train, {"gold": 2.0})[:1] == [2.0]


def probs(kv: dict) -> dict:
    p = {lab: 0.0 for lab in LABELS}
    p.update({LABELS[i]: v for i, v in kv.items()})
    return p


def test_decide_applies_the_gold_rules():
    thr = fixed_thresholds(PP)
    logic, loop, func, style, comp = (LABELS.index(x) for x in
                                      ("Lỗi logic", "Lỗi vòng lặp", "Lỗi hàm", "Lỗi style", "Lỗi biên dịch"))
    edge = LABELS.index("Lỗi edge case")
    clean = {"compile_log": "", "all_commented": False}
    assert decide(probs({logic: 0.8, comp: 0.9}), clean, thr, PP) == ["Lỗi logic"]  # clean log overrides the model
    broken = {"compile_log": GCC_ERR, "all_commented": False}
    assert decide(probs({logic: 0.8, loop: 0.9}), broken, thr, PP) == ["Lỗi biên dịch", "Lỗi vòng lặp"]
    assert decide(probs({logic: 0.9}), {"compile_log": "", "all_commented": True}, thr, PP) == ["Lỗi style"]
    many = probs({logic: 0.9, loop: 0.8, func: 0.7, style: 0.6})
    assert decide(many, clean, thr, PP) == ["Lỗi logic", "Lỗi vòng lặp", "Lỗi hàm"]
    assert decide(probs({edge: 0.85}), clean, thr, PP) == []  # edge case needs >= 0.9
    assert decide(probs({comp: 0.7}), {"compile_log": None, "all_commented": False}, thr, PP) == ["Lỗi biên dịch"]


def test_thresholds_tuned_per_label_and_cross_fold():
    rng = np.random.default_rng(0)
    Y = rng.integers(0, 2, size=(20, len(LABELS)))
    P = np.clip(Y * 0.3 + 0.1 + rng.random((20, len(LABELS))) * 0.1, 0, 1)  # positives score 0.4-0.5
    t = tuned_thresholds(P, Y, PP)
    assert t["Lỗi edge case"] == 0.9
    assert all(0.1 <= t[lab] <= 0.45 for lab in LABELS if lab != "Lỗi edge case" and Y[:, LABELS.index(lab)].any())
    cross = cross_fold_thresholds({"A": [0], "B": [1]}, {"A": P[:10], "B": P[10:]}, {"A": Y[:10], "B": Y[10:]}, PP)
    assert set(cross) == {"A", "B"} and cross["A"] == tuned_thresholds(P[10:], Y[10:], PP)


def test_find_checkpoint_prefers_the_latest_complete_one(tmp_path):
    from src.training.task2_cls import find_checkpoint

    def ck(base, step, complete=True):
        d = base / "checkpoints" / f"checkpoint-{step}"
        d.mkdir(parents=True)
        if complete:
            (d / "trainer_state.json").write_text("{}")
            (d / "adapter_model.safetensors").write_text("x")
        return d

    run = tmp_path / "work" / "runA"
    ck(run, 25)
    ck(run, 50, complete=False)  # interrupted while saving
    prev = tmp_path / "input" / "old-version" / "outputs" / "runA"
    ck(prev, 75)
    ck(tmp_path / "input" / "x" / "runB", 100)  # another run: ignored
    assert find_checkpoint(run, "runA").name == "checkpoint-25"
    got = find_checkpoint(run, "runA", [tmp_path / "input"])
    assert got == run / "checkpoints" / "checkpoint-75" and (got / "trainer_state.json").exists()


def _qwen_tokenizer_dir():
    hits = glob.glob(str(Path.home() / ".cache/huggingface/hub/models--*Qwen2.5-Coder-7B-Instruct*/snapshots/*"))
    return next((h for h in hits if Path(h, "tokenizer.json").exists()), None)


def test_tiny_model_pauses_at_deadline_resumes_and_predicts(tmp_path, records):
    pytest.importorskip("peft")
    tok_dir = _qwen_tokenizer_dir()
    if tok_dir is None:
        pytest.skip("no Qwen2.5 tokenizer in the local HF cache")
    from transformers import AutoTokenizer, Qwen2Config, Qwen2ForSequenceClassification

    from src.training.task2_cls import predict, read_status, train_run

    tok = AutoTokenizer.from_pretrained(tok_dir)
    model_dir = tmp_path / "tiny"
    cfg_m = Qwen2Config(vocab_size=len(tok), hidden_size=32, intermediate_size=64, num_hidden_layers=2,
                        num_attention_heads=4, num_key_value_heads=2, num_labels=len(LABELS),
                        pad_token_id=tok.pad_token_id)
    Qwen2ForSequenceClassification(cfg_m).save_pretrained(model_dir)
    tok.save_pretrained(model_dir)
    cfg = {"seed": 42, "model": {"name": str(model_dir), "load_in_4bit": False, "max_length": 64},
           "lora": {"r": 4, "alpha": 8, "dropout": 0.0, "target_modules": ["q_proj", "v_proj"]},
           "train": {"epochs": 2, "lr": 1e-3, "batch_size": 1, "grad_accum": 2, "save_steps": 1,
                     "save_total_limit": 2, "logging_steps": 1}}
    train = train_records(records, "all")
    w, pw = sample_weights(train), pos_weight(train)
    run = tmp_path / "run"
    st = train_run(cfg, train, w, pw, run, deadline=time.time())  # deadline already reached: 1 step then pause
    assert st["state"] == "paused" and st["global_step"] == 1
    assert (run / "checkpoints" / "checkpoint-1" / "trainer_state.json").exists()
    st = train_run(cfg, train, w, pw, run)  # resumes from checkpoint-1
    assert st["state"] == "done" and st["global_step"] == st["max_steps"] == 6
    assert (run / "adapter" / "adapter_config.json").exists()
    log = [json.loads(x) for x in (run / "train_log.jsonl").read_text().splitlines()]
    assert any("loss" in row for row in log)
    assert train_run(cfg, train, w, pw, run)["state"] == "done"  # finished run: no-op
    assert read_status(run)["state"] == "done"
    out = predict(cfg, [r for r in records if r["source"] == "public"] + train[:2], run / "adapter", batch_size=2)
    assert len(out) == 3 and all(0.0 <= v <= 1.0 for o in out for v in o["probs"].values())


def test_head_accepts_half_hidden_states_when_kept_in_fp32():
    """Prediction has no autocast: fp16 hidden states must not hit the fp32 head (Kaggle EX01 crash)."""
    import torch
    from src.training.task2_cls import cast_head_inputs

    class Tiny(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.body = torch.nn.Linear(4, 4).half()
            self.score = torch.nn.Linear(4, 3)  # fp32 head

        def forward(self, x):
            return self.score(self.body(x))

    m = Tiny()
    assert cast_head_inputs(m) == 1
    out = m(torch.randn(2, 4).half())
    assert out.dtype == torch.float32 and out.shape == (2, 3)
    assert cast_head_inputs(m) == 0  # idempotent
