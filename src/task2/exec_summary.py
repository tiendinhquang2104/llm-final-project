"""Execution signals as a short text block for the F-cls prompt (src/task2/cls_data.py), the same at training and
at inference.

The block summarises what src/task2/exec_oracle.py observed on the exam's test suite: per test group, how many
tests pass and how the others fail (single_problem), or the state of every problem (multi_problem). Where there is
no suite the block says so, which is also what the model sees during training for a share of the records
(train.signal_dropout), so that it learns both cases.

Suites per source (never a public-test file in training):
- public (inference only): the suites the local LLM generated from the statements (scripts/gen_task2_tests.py);
- gold and gold mutants: the suites generated the same way from the gold statements;
- synth: the tests of the problem bank (src/synth/problems/*.yaml) the synthetic set was generated from.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from src.task2.exec_oracle import ExecResult
from src.task2.test_gen import Suite

_TEXT = {
    "vi": {"head": "### Kết quả chạy bộ test của đề", "none": "Không có bộ test chạy được cho bài này.",
           "nocompile": "Không chạy: bài không biên dịch được.", "commented": "Không chạy: toàn bộ code nằm trong comment.",
           "nobuild": "Không chạy được: bài không ghép được với chương trình gọi hàm của bộ test.",
           "total": "Tổng: {ok}/{n} test đúng.", "group": "- nhóm {g}: {ok}/{n} đúng{rest}",
           "problem": "- {pid}: {state}", "prereq": "Câu tiên quyết: {pid} (theo grading_policy).",
           "variant": "{pid} đúng trên file dữ liệu của đề nhưng sai khi file có số dòng khác.",
           "static": "Kiểm tra tĩnh {pid}: {what}.", "size": "mảng kích thước hằng số",
           "file": "tên file viết cứng", "stoi": "có dùng stoi/atoi"},
    "en": {"head": "### Results on the exam's test suite", "none": "No runnable test suite for this submission.",
           "nocompile": "Not run: the submission does not compile.", "commented": "Not run: the whole code is commented out.",
           "nobuild": "Not run: the submission does not build with the suite's driver.",
           "total": "Total: {ok}/{n} tests right.", "group": "- group {g}: {ok}/{n} right{rest}",
           "problem": "- {pid}: {state}", "prereq": "Prerequisite problem: {pid} (grading_policy).",
           "variant": "{pid} is right on the exam data file but wrong on a file with another number of rows.",
           "static": "Static check of {pid}: {what}.", "size": "constant-size array",
           "file": "hard-coded file name", "stoi": "uses stoi/atoi"},
}
OK = ("pass", "prompt_then_pass")
GROUPS = ("example", "edge", "normal")


def _group(g: str) -> str:
    """Bank groups (edge:min, perf, ...) and generated ones on the scale training sees: example / edge / normal."""
    g = g.split(":")[0]
    return {"perf": "normal", "listed": "normal"}.get(g, g)  # generated "listed" inputs: not a bank group


def summary_text(r: ExecResult | None, lang: str = "vi") -> str:
    t = _TEXT[lang]
    lines = [t["head"]]
    if r is None:
        lines.append(t["none"])
    elif not r.compiles:
        lines.append(t["nocompile"])
    elif r.all_commented:
        lines.append(t["commented"])
    elif r.kind is None:
        lines.append(t["none"])
    elif not r.harness_ok:
        lines.append(t["nobuild"])
    elif r.states:
        pre = next((p for p in r.states if r.prereq.get(p)), next(iter(r.states)))
        lines.append(t["prereq"].format(pid=pre))
        lines += [t["problem"].format(pid=p, state=s) for p, s in r.states.items()]
        if r.p1_variant_fail:
            lines.append(t["variant"].format(pid=pre))
        what = [t[k] for k, on in (("size", r.hardcode_size), ("file", r.hardcode_file), ("stoi", r.uses_stoi)) if on]
        if what:
            lines.append(t["static"].format(pid=pre, what=", ".join(what)))
    else:
        st = list(r.statuses.values())
        lines.append(t["total"].format(ok=sum(s in OK for s in st), n=len(st)))
        by = {}
        for k, s in r.statuses.items():
            by.setdefault(_group(r.groups.get(k, "normal")), []).append(s)
        for g in sorted(by, key=lambda x: GROUPS.index(x) if x in GROUPS else len(GROUPS)):
            ss = by[g]
            bad = Counter(s for s in ss if s not in OK)
            rest = (" (" + ", ".join(f"{s} {n}" for s, n in bad.most_common()) + ")") if bad else ""
            lines.append(t["group"].format(g=g, ok=sum(s in OK for s in ss), n=len(ss), rest=rest))
    return "\n".join(lines) + "\n"


def bank_suites(problems_dir) -> dict[str, Suite]:
    """single_problem suites from the tests of the synthetic problem bank (its own expected outputs)."""
    import yaml

    out = {}
    for f in sorted(Path(problems_dir).glob("*.yaml")):
        for p in (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("problems_meta") or []:
            tests = p.get("tests") or []
            if p.get("exam_type") != "single_problem" or not tests:
                continue
            out[p["exam_id"]] = Suite(p["exam_id"], "single_problem", "bank", None, tests=[
                {"id": f"t{k:02d}", "group": _group(t.get("group") or "normal"),
                 "stdin": t["input"] if str(t["input"]).endswith("\n") else f"{t['input']}\n",
                 "expected": str(t["expected"])} for k, t in enumerate(tests)])
    return out
