"""Build the synthetic dataset for all three tasks (synth_plan.md implementation step 7).

Every record follows one verified path:

    verified base -> inject defect(s) / trap -> COMPILE + RUN on the labeling tests (or the
    multi-problem dataset harness) -> label = rulebook(observed behaviour) -> keep only if the
    observed rule matches the slot -> exec_report from the auto-oracle (statement examples only).

So a label never comes from the *intended* defect, and the model input (``exec_report``) never
contains the defect, the rule or the labeling tests. Output layout matches ``sample_dataset``;
held-out exams go to ``heldout/`` (with their own ``heldout/submissions``) and are evaluation-only.

Usage:
    python scripts/build_synth_dataset.py --count                  # full plan allocation (500)
    python scripts/build_synth_dataset.py --count --scale 0.1     # quick check (shares the run cache)
"""

from __future__ import annotations

import argparse
import difflib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.synth import mutators, quota  # noqa: E402
from src.synth.compliance import level_of  # noqa: E402
from src.synth.dedup import dedupe, max_similarity, public_test_signatures, signature  # noqa: E402
from src.synth.feedback import FEEDBACK_LEVELS, feedback_for, multi_feedback, praise  # noqa: E402
from src.synth.labeler import Label, label_multi, label_single  # noqa: E402
from src.synth.multi import is_rec_schema, run_multi_datasets  # noqa: E402
from src.synth.oracle import build_oracle  # noqa: E402
from src.synth.problems import Problem, load_problems  # noqa: E402
from src.synth.taxonomy import DEFECTS, LABEL_SPACE, taxonomy_for  # noqa: E402
from src.synth.verify import TestCase, make_runner, run_single  # noqa: E402

PUBLIC_ROOTS = (
    ROOT / "data" / "raw" / "public_test_release",
    ROOT / "data" / "public-test" / "public_test_release",
)
WORKERS = 8
MAX_ATTEMPTS = 60          # injection attempts per slot before declaring a shortfall
N_VARIANTS = 2             # 1 rename variant per verified base (reference + 4 personas -> 10 bases/exam)
GPP_LOG_SHARE = 0.3        # share of Level 2 compile-error feedback that pastes the g++ log

TASK_META = {
    "task1": {
        "task": "task1_rubric_grading",
        "description": "Input = đề bài + code sinh viên (+ compile_log, exec_report). Output = 6 điểm thành phần và tổng điểm 0-10.",
        "input_fields": ["exam_id", "exam_type", "language", "code_file", "compile_log", "test_report", "exec_report"],
        "output_fields": ["rubric.compilable(0-1)", "rubric.io_format(0-1)", "rubric.logic(0-4)",
                          "rubric.edge_case(0-2)", "rubric.complexity(0-1)", "rubric.code_quality(0-1)",
                          "total_score(0-10)"],
        "metric": "QWK trên total_score; MAE; exact-match từng chiều",
    },
    "task2": {
        "task": "task2_error_taxonomy",
        "description": "Phân loại đa nhãn lỗi của bài nộp. Danh sách rỗng nghĩa là bài không mắc lỗi nào.",
        "label_space": list(LABEL_SPACE),
        "input_fields": ["exam_id", "exam_type", "language", "code_file", "compile_log", "test_report", "exec_report"],
        "output_fields": ["taxonomy_error: list[str] (0..10 nhãn)"],
        "metric": "macro-F1 và micro-F1 trên 10 nhãn",
    },
    "task3": {
        "task": "task3_pedagogical_feedback",
        "description": "Sinh phản hồi tiếng Việt ĐÚNG mức target_feedback_level. Nhãn lỗi không cho sẵn (tự chẩn đoán).",
        "level_definition_ref": "label_space.json -> feedback_level",
        "input_fields": ["exam_id", "exam_type", "language", "code_file", "compile_log", "test_report",
                         "exec_report", "target_feedback_level"],
        "output_fields": ["taxonomy_error", "feedback: str (tiếng Việt)"],
        "metric": "level compliance + độ chính xác chẩn đoán",
    },
}


# ------------------------------------------------------------------------------------------------
# bases
# ------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Base:
    base_id: str
    code: str
    style_ref: str
    fold: str = "synthetic"   # bases repaired from the 32 real submissions carry their exam id


def passes_all(problem: Problem, code: str, runner) -> bool:
    if problem.exam_type == "multi_problem":
        if not is_rec_schema(problem):
            return False
        rep = run_multi_datasets(runner, code, problem)
        return rep.compiles and not rep.timed_out and all(s == "ok" for s in rep.states.values())
    cases = [TestCase(t.input, t.expected, t.group) for t in problem.tests]
    rep = run_single(runner, code, cases, problem.exam_type)
    return bool(rep.results) and all(r.exact for r in rep.results)


def prepare_bases(problem: Problem, runner, bases_dir: Path | None, n_variants: int = N_VARIANTS) -> list[Base]:
    """Reference + persona solutions (if provided) + rename variants; every base passes all tests."""
    if not passes_all(problem, problem.reference, runner):
        raise ValueError(f"{problem.exam_id}: the reference solution fails its own tests")
    seeds = [Base(f"{problem.exam_id}#ref", problem.reference, "reference")]
    if bases_dir is not None and (bases_dir / problem.exam_id).is_dir():
        for path in sorted((bases_dir / problem.exam_id).glob("*.cpp")):
            code = path.read_text(encoding="utf-8")
            if passes_all(problem, code, runner):
                seeds.append(Base(f"{problem.exam_id}#{path.stem}", code, f"persona:{path.stem.split('__')[0]}"))
    bases = list(seeds)
    for seed in seeds:
        for k in range(1, n_variants):
            code = mutators.neutral_variation(seed.code, k)
            if code != seed.code and passes_all(problem, code, runner):
                bases.append(Base(f"{seed.base_id}~v{k}", code, f"{seed.style_ref}+rename-pool-{k}", seed.fold))
    return bases


# ------------------------------------------------------------------------------------------------
# records
# ------------------------------------------------------------------------------------------------

@dataclass
class SynthRecord:
    sample_id: str
    problem: Problem
    code: str
    label: Label
    level: str = FEEDBACK_LEVELS[0]
    feedback: str = ""
    compile_log: str = ""      # kept "" like the official inputs; compile status lives in exec_report
    exec_report: str = ""
    heldout: bool = False
    provenance: dict = field(default_factory=dict)

    @property
    def code_file(self) -> str:
        # a Task 3 level-duplicate ("-L<k>") is the same submission: point at the original's file
        sid = self.provenance.get("duplicate_of") or self.sample_id
        return f"submissions/{self.problem.exam_id}/{sid}.cpp"

    def input_dict(self) -> dict:
        return {"exam_id": self.problem.exam_id, "exam_type": self.problem.exam_type,
                "language": self.problem.language, "code_file": self.code_file,
                "compile_log": self.compile_log, "test_report": None, "exec_report": self.exec_report}


def _changed_location(base: str, code: str) -> str:
    """'hàm <name>' of the first changed line (for feedback), or a generic phrase."""
    b, c = base.splitlines(), code.splitlines()
    for tag, i1, _, j1, _ in difflib.SequenceMatcher(None, b, c).get_opcodes():
        if tag == "equal":
            continue
        for line in reversed(c[: j1 + 1]):
            m = re.match(r"^\s*[\w:<>*& ]+?\b(\w+)\s*\([^;]*\)\s*\{?\s*$", line)
            if m and m.group(1) not in ("if", "for", "while", "switch"):
                return f"hàm {m.group(1)}"
        return "đầu chương trình"
    return "trong bài làm"


def _diff_lines(a: str, b: str) -> int:
    return sum(1 for line in difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm="", n=0)
               if line[:1] in "+-" and not line.startswith(("+++", "---")))


_LOOP_HEADER_RE = re.compile(r"\b(for|while)\s*\(")
_LOOP_DEFECTS = {"D04", "D13", "D14b", "D15s", "D16a", "D16b"}


def _touches_loop(base: str, code: str, defects: list[str]) -> bool:
    """True when a loop-boundary defect actually changed a ``for``/``while`` header line."""
    if not _LOOP_DEFECTS & set(defects):
        return False
    b = set(base.splitlines())
    return any(_LOOP_HEADER_RE.search(line) for line in code.splitlines() if line not in b) or "D04" in defects


def _taxonomy(defects: list[str], extra_labels: tuple[str, ...] = ()) -> list[str]:
    known = [d for d in defects if d in DEFECTS]
    labels = set(taxonomy_for(known)) | set(extra_labels) if known or extra_labels else set()
    return sorted(labels, key=LABEL_SPACE.index)


def observe_single(problem: Problem, code: str, runner, *, prompt_trap: bool, style_bad: bool):
    if not code.strip() or all(not l.strip() or l.strip().startswith("//") for l in code.splitlines()):
        from src.synth.labeler import SingleSignals
        sig = SingleSignals(has_code=False, compiles=False)
        return label_single(sig), sig, ""
    cases = [TestCase(t.input, t.expected, t.group) for t in problem.tests]
    rep = run_single(runner, code, cases, problem.exam_type,
                     strip_prefix=mutators.TRAP_PROMPT if prompt_trap else "")
    sig = replace(rep.signals, style_very_bad=style_bad)
    return label_single(sig), sig, rep.compile_log


def try_single(problem: Problem, base: Base, combo: tuple[str, ...], rule: str | None, occurrence: int,
               runner, *, trap: str | None = None, style_stack: bool = False):
    """One injection attempt. Returns (code, label, info) or None when behaviour != slot rule."""
    code = base.code
    ctx = {"occurrence": occurrence}
    example = next((t for t in problem.tests if t.group == "example"), None)
    if example:
        ctx.update(example_in=example.input, example_out=example.expected)
    for i, d in enumerate(combo):
        if d not in mutators.MUTATORS:
            return None
        out = mutators.apply(d, code, {**ctx, "occurrence": occurrence + i})
        if out is None or out == code:
            return None
        code = out
    defects = list(combo)
    if style_stack and combo:
        styled = mutators.apply("D22", code, {})
        if styled:
            code, defects = styled, defects + ["D22"]
    msvc = False
    if trap:
        fn, types = mutators.TRAPS[trap]
        if problem.exam_type not in types:
            return None
        trapped = fn(code, {})
        if trapped is None:
            return None
        msvc = trap == "msvc_style"
        observed_code, code = (code, trapped) if msvc else (trapped, trapped)
    else:
        observed_code = code
    label, sig, compile_log = observe_single(problem, observed_code, runner, prompt_trap=trap == "prompt_input",
                                             style_bad="D23" in defects)
    if rule is not None and label.rule_id != rule:
        return None
    if not combo and label.rule_id != "S6":
        return None
    if msvc:
        # G4: MSVC-only constructs keep compilable=1; we only accept if g++ really rejects it
        if runner.run(code, "", 2.0).compiled:
            return None
        compile_log = runner.run(code, "", 2.0).compile_log
    extra = _single_secondary(label.rule_id, defects)
    # a loop-bound bug is a "Lỗi vòng lặp" when it breaks the logic (S2/S4/...); when it only shows on
    # edge inputs (S8/S10/S11) it is labelled as an edge-case error instead (EX02-S209: loop + logic)
    if label.rule_id not in ("S8", "S10", "S11") and _touches_loop(base.code, observed_code, defects):
        extra += ("Lỗi vòng lặp",)
    taxonomy = _taxonomy(defects, extra)
    if label.rule_id == "S6":
        taxonomy = []
    return code, Label(label.rule_id, label.rubric, label.total, taxonomy), {
        "defects": defects, "signals": sig.__dict__, "compile_log": compile_log}


def _single_secondary(rule: str, defects: list[str]) -> tuple[str, ...]:
    """Observed-behaviour labels the defect map alone would miss."""
    extra = []
    if rule in ("S10", "S11", "S8"):
        extra.append("Lỗi edge case")
    if rule in ("S1", "S0"):
        extra.append("Lỗi biên dịch")
    if rule in ("S2", "S3", "S9"):
        extra.append("Lỗi logic")  # S3/S9: wrong token AND wrong answers (EX02-S206: nhập/xuất + logic)
    return tuple(extra)


_MULTI_FUNCS = {"P1": "prob1", "P2": "prob2", "P3": "prob3", "P4": "prob4"}


def try_multi(problem: Problem, base: Base, plan: dict, target_total: int | None, runner, *,
              trap: str | None = None, style_stack: bool = False):
    """plan = {"global": defect | None, "questions": {pid: defect}}. Label = harness observation."""
    code = base.code
    defects, per_q = [], {}
    occ = plan.get("occurrence", 0)
    g = plan.get("global")
    if g == "D01":
        code = mutators.apply("D01", code, {"occurrence": occ})
    elif g == "D02":
        code = mutators.apply("D02", code, {"occurrence": occ})
    elif g == "D15":
        code = mutators.apply("D15", code, {"literal": '"data.csv"'})
        per_q["P1"] = ["D15"]
    if code is None:
        return None
    if g:
        defects.append(g)
    for pid, d in plan.get("questions", {}).items():
        out = mutators.apply_in_function(d, code, _MULTI_FUNCS[pid], {"occurrence": occ})
        if out is None or out == code:
            return None
        code = out
        defects.append(d)
        per_q.setdefault(pid, []).append(d)
    if style_stack and defects:
        styled = mutators.apply("D22", code, {})
        if styled:
            code, defects = styled, defects + ["D22"]
    if trap:
        fn, types = mutators.TRAPS[trap]
        if problem.exam_type not in types:
            return None
        code = fn(code, {}) or None
        if code is None:
            return None
    if not code.strip() or all(not l.strip() or l.strip().startswith("//") for l in code.splitlines()):
        return None
    rep = run_multi_datasets(runner, code, problem)
    label = label_multi(rep.signals)
    if target_total is not None and label.total != target_total:
        return None
    if not defects and label.total != 10:
        return None
    if g == "D04" or any(d == "D04" for d in defects):
        if label.rule_id != "M2":
            return None
    states = rep.states
    extra = []
    if label.rule_id == "M4":
        later = list(states.values())[1:]
        if any(s == "edge" for s in later):
            extra.append("Lỗi edge case")
        own = _taxonomy([d for d in defects if d != "D22"])
        if any(s in ("partial", "fail", "crash") for s in later) and not (set(own) - {"Lỗi edge case"}):
            extra.append("Lỗi logic")  # wrong answer with no more specific defect label
        if any(s == "missing" for s in later) and "Lỗi hàm" not in own:
            extra.append("Lỗi hàm")    # unimplemented function (D12)
    elif label.rule_id == "M1":
        extra.append("Lỗi biên dịch")
    elif label.rule_id == "M2":
        extra += ["Lỗi vòng lặp", "Lỗi logic"]
    breaks_logic = any(st in ("partial", "fail", "crash") for st in list(states.values())[1:])
    if breaks_logic and _touches_loop(base.code, code, defects):
        extra.append("Lỗi vòng lặp")
    taxonomy = [] if label.total == 10 else _taxonomy(defects, tuple(extra))
    return code, Label(label.rule_id, label.rubric, label.total, taxonomy), {
        "defects": defects, "states": states, "per_question_defects": per_q, "compile_log": rep.compile_log}


# ------------------------------------------------------------------------------------------------
# scheduling
# ------------------------------------------------------------------------------------------------

class Builder:
    def __init__(self, problems: dict[str, Problem], runner, rng: random.Random, bases_dir: Path | None,
                 oracle_mode: str = "minimal", max_attempts: int = MAX_ATTEMPTS):
        self.max_attempts = max_attempts
        self.problems = problems
        self.runner = runner
        self.rng = rng
        with ThreadPoolExecutor(WORKERS) as ex:
            prepared = list(ex.map(lambda p: prepare_bases(p, runner, bases_dir), problems.values()))
        self.bases: dict[str, list[Base]] = dict(zip(problems, prepared))
        self.oracles = {eid: build_oracle(p, runner, mode=oracle_mode) for eid, p in problems.items()}
        self.counters: Counter = Counter()
        self.shortfall: Counter = Counter()

    def _record(self, problem: Problem, base: Base, result, slot: dict, trap: str | None, heldout: bool) -> SynthRecord:
        code, label, info = result
        eid = problem.exam_id
        sid = f"{eid}-{self.counters[eid]:04d}"
        self.counters[eid] += 1
        prov = {"sample_id": sid, "exam_id": eid, "exam_type": problem.exam_type,
                "intended_rule": slot.get("rule"), "intended_total": slot.get("total"),
                "rule": label.rule_id, "defects": info["defects"],
                "defect": info["defects"][0] if info["defects"] else "CLEAN",
                "observed_states": info.get("states"), "per_question_defects": info.get("per_question_defects"),
                "verified": True, "base_id": base.base_id, "style_ref": base.style_ref, "fold": base.fold,
                "trap": trap, "pair_id": None, "heldout": heldout, "seed": self.rng.randint(0, 1 << 30)}
        rec = SynthRecord(sid, problem, code, label, heldout=heldout, provenance=prov)
        rec.exec_report = self.oracles[eid].exec_report(code)
        rec._compile_log = info.get("compile_log", "")
        rec._base_code = base.code
        return rec

    def fill_single(self, slot: dict, exams: list[Problem], start: int, *, trap=None, style_stack=False,
                    heldout=False, base_offset: int | None = None) -> SynthRecord | None:
        boff = start if base_offset is None else base_offset
        for attempt in range(self.max_attempts):
            problem = exams[(start + attempt) % len(exams)]
            bases = self.bases[problem.exam_id]
            base = bases[(boff + attempt // len(exams)) % len(bases)]
            combo = slot["combos"][attempt % len(slot["combos"])]
            res = try_single(problem, base, combo, slot["rule"], attempt // len(slot["combos"]), self.runner,
                             trap=trap, style_stack=style_stack)
            if res:
                return problem, base, res, slot, trap, heldout
        return None

    def fill_multi(self, slot: dict, exams: list[Problem], start: int, *, trap=None, style_stack=False,
                   heldout=False, base_offset: int | None = None) -> SynthRecord | None:
        total = slot["total"]
        boff = start if base_offset is None else base_offset
        budget = self.max_attempts * (4 if total == 8 else 2)  # multi search space is larger; 8 is rarest
        for attempt in range(budget):
            problem = exams[(start + attempt) % len(exams)]
            bases = self.bases[problem.exam_id]
            base = bases[(boff + attempt // len(exams)) % len(bases)]
            plan = self._multi_plan(total, attempt, start)
            res = try_multi(problem, base, plan, total, self.runner, trap=trap,
                            style_stack=style_stack and total not in (10, 0))
            if res:
                return problem, base, res, slot, trap, heldout
        return None

    def _multi_plan(self, total: int, attempt: int, start: int = 0) -> dict:
        r = random.Random(f"{total}:{attempt}")
        if total == 10:
            return {}
        if total == 0:
            return {"global": ("D01", "D02")[attempt % 2], "occurrence": attempt}
        if total == 1:  # P1 broken; alternate hard-coded file name (D15) and a parsing bug, per slot
            if (start + attempt) % 3 != 2:
                return {"global": "D15"}
            return {"questions": {"P1": r.choice(("D13", "D14b", "D20"))}, "occurrence": attempt}
        if total == 2:
            return {"questions": {r.choice(("P2", "P3")): "D04"}, "occurrence": attempt}
        plans = quota.MULTI_STATE_PLANS.get(total)
        qs = {}
        if plans:
            states = list(r.choice(plans))
            r.shuffle(states)
            for pid, st in zip(("P2", "P3", "P4"), states):
                d = r.choice(quota.STATE_DEFECTS[st])
                if d:
                    qs[pid] = d
        else:
            for pid in ("P2", "P3", "P4"):
                d = r.choice(quota.MULTI_QUESTION_DEFECTS)
                if d:
                    qs[pid] = d
        return {"questions": qs, "occurrence": r.randint(0, 2)} if qs else {"questions": {"P2": "D12"}}


def schedule_and_build(builder: Builder, exams: dict[str, Problem], *, scale: float, heldout: bool,
                       n_traps_ten=quota.N_TRAPS_TEN, n_traps_other=quota.N_TRAPS_OTHER,
                       n_style=quota.N_STYLE_STACK) -> list[SynthRecord]:
    singles = [p for p in exams.values() if p.exam_type == "single_problem"]
    multis = [p for p in exams.values() if p.exam_type == "multi_problem" and is_rec_schema(p)]
    rng = builder.rng
    records: list[SynthRecord] = []
    trap_single = [t for t, (_, ty) in mutators.TRAPS.items() if "single_problem" in ty]
    trap_multi = [t for t, (_, ty) in mutators.TRAPS.items() if "multi_problem" in ty]
    s_slots = quota.single_slots(scale) if singles else []
    m_slots = quota.multi_slots(scale) if multis else []
    # traps: first n in 10-point buckets, then spread over other buckets
    ten_s = [i for i, s in enumerate(s_slots) if s["rule"] == "S6"][: round(n_traps_ten[0] * scale)]
    ten_m = [i for i, s in enumerate(m_slots) if s["total"] == 10][: round(n_traps_ten[1] * scale)]
    other_s = [i for i, s in enumerate(s_slots) if s["rule"] in ("S4", "S5", "S10", "S11", "S7")]
    other_s = rng.sample(other_s, min(len(other_s), round(n_traps_other * scale)))
    style_s = [i for i, s in enumerate(s_slots) if s["rule"] in ("S4", "S9", "S3", "S8", "S2")]
    style_m = [i for i, s in enumerate(m_slots) if s["total"] in (2, 4, 5, 6, 7, 8, 9)]
    n_style_s = round(n_style * scale * 0.6)
    style_s = set(rng.sample(style_s, min(len(style_s), n_style_s)))
    style_m = set(rng.sample(style_m, min(len(style_m), round(n_style * scale) - len(style_s))))
    trap_of = {("s", i): trap_single[k % len(trap_single)] for k, i in enumerate(ten_s + other_s)}
    trap_of.update({("m", i): trap_multi[k % len(trap_multi)] for k, i in enumerate(ten_m)})
    s_groups: dict[str, list[int]] = {}
    for i, sl in enumerate(s_slots):
        s_groups.setdefault(_slot_key(sl), []).append(i)
    m_groups: dict[str, list[int]] = {}
    for i, sl in enumerate(m_slots):
        m_groups.setdefault(_slot_key(sl), []).append(i)
    groups = [("s", k, v) for k, v in s_groups.items()] + [("m", k, v) for k, v in m_groups.items()]
    results: dict[tuple[str, int], tuple] = {}
    done = [0]
    total_slots = len(s_slots) + len(m_slots)

    def group_job(kind: str, key: str, idxs: list[int]):
        """Slots of one bucket, in order; each exam takes at most cap of them (least-used first)."""
        pool = singles if kind == "s" else multis
        slots = s_slots if kind == "s" else m_slots
        fill = builder.fill_single if kind == "s" else builder.fill_multi
        cap = exam_cap(len(idxs), len(pool), key)
        used: Counter = Counter()
        out = {}
        for k, i in enumerate(idxs):
            rotated = pool[k % len(pool):] + pool[:k % len(pool)]
            order = sorted([p for p in rotated if used[p.exam_id] < cap], key=lambda p: used[p.exam_id])
            found = None
            if order:
                style = i in (style_s if kind == "s" else style_m)
                trap = trap_of.get((kind, i))
                found = fill(slots[i], order, 0, trap=trap, style_stack=style, heldout=heldout, base_offset=i)
                if found is None and trap:
                    found = fill(slots[i], order, 0, style_stack=style, heldout=heldout, base_offset=i)
            if found is not None:
                used[found[0].exam_id] += 1
            out[(kind, i)] = found
            done[0] += 1
            if done[0] % 25 == 0 or done[0] == total_slots:
                print(f"[build] {'heldout' if heldout else 'train'} {done[0]}/{total_slots} slots", file=sys.stderr, flush=True)
        return out

    with ThreadPoolExecutor(WORKERS) as ex:
        for part in ex.map(lambda g: group_job(*g), groups):
            results.update(part)
    for kind, slots in (("s", s_slots), ("m", m_slots)):  # slot order -> deterministic sample ids
        for i, slot in enumerate(slots):
            found = results.get((kind, i))
            if found is None:
                builder.shortfall[("heldout:" if heldout else "") + _slot_key(slot)] += 1
                continue
            records.append(builder._record(*found))
    return records


def exam_cap(n_slots: int, n_exams: int, key: str = "") -> int:
    """At most ceil(n/exams) + 1 records of one bucket per exam (keeps exams balanced).

    Buckets that only a few exams can produce (quota.RARE_BUCKETS) get a doubled cap, trading a
    little balance for not losing those records altogether."""
    cap = -(-n_slots // max(1, n_exams)) + 1
    return cap * 2 if key in quota.RARE_BUCKETS else cap


def _slot_key(slot: dict) -> str:
    return f"single:{slot['rule']}" if slot["exam_type"] == "single_problem" else f"multi:{slot['total']}"


def _record_key(r: SynthRecord) -> str:
    p = r.provenance
    return f"single:{p['intended_rule']}" if r.problem.exam_type == "single_problem" else f"multi:{p['intended_total']}"


def top_up(builder: Builder, exams: dict[str, Problem], records: list[SynthRecord], *, scale: float,
           heldout: bool, public_root: Path | None, rounds: int = 2) -> tuple[list[SynthRecord], dict]:
    """Refill buckets emptied by the guards (dedup / public similarity) from other exams/bases."""
    singles = [p for p in exams.values() if p.exam_type == "single_problem"]
    multis = [p for p in exams.values() if p.exam_type == "multi_problem" and is_rec_schema(p)]
    want = Counter(_slot_key(sl) for sl in (quota.single_slots(scale) if singles else [])
                   + (quota.multi_slots(scale) if multis else []))
    records, stats = apply_guards(records, public_root)
    added = 0
    for rnd in range(1, rounds + 1):
        have = Counter(_record_key(r) for r in records)
        jobs = []
        for key, n in want.items():
            kind, val = key.split(":")
            slot = next(sl for sl in (quota.single_slots(1.0) if kind == "single" else quota.multi_slots(1.0))
                        if _slot_key(sl) == key)
            jobs += [(kind, slot, 1000 * rnd + 37 * k) for k in range(max(0, n - have.get(key, 0)))]
        if not jobs:
            break

        per_key_exam = Counter((_record_key(r), r.problem.exam_id) for r in records)
        by_key: dict[str, list] = {}
        for kind, slot, start in jobs:
            by_key.setdefault(_slot_key(slot), []).append((kind, slot, start))

        def key_job(items):
            out = []
            kind = items[0][0]
            pool = singles if kind == "single" else multis
            key = _slot_key(items[0][1])
            cap = exam_cap(want[key], len(pool), key)
            used = Counter({e: c for (k, e), c in per_key_exam.items() if k == key})
            for _, slot, start in items:
                order = sorted([p for p in pool if used[p.exam_id] < cap], key=lambda p: used[p.exam_id])
                if not order:
                    break
                fill = builder.fill_single if kind == "single" else builder.fill_multi
                f = fill(slot, order, 0, heldout=heldout, base_offset=start)
                if f is not None:
                    used[f[0].exam_id] += 1
                    out.append(f)
            return out

        with ThreadPoolExecutor(WORKERS) as ex:
            found = [f for part in ex.map(key_job, by_key.values()) for f in part]
        new = [builder._record(*f) for f in found]
        added += len(new)
        records, stats = apply_guards(records + new, public_root)
    stats["top_up_added"] = added
    return records, stats


# ------------------------------------------------------------------------------------------------
# feedback, pairs, task 3
# ------------------------------------------------------------------------------------------------

def assign_feedback(records: list[SynthRecord], rng: random.Random) -> None:
    i = 0
    for r in records:
        if r.label.total == 10 and not r.label.taxonomy:
            r.level = FEEDBACK_LEVELS[0]
        else:
            r.level = quota.level_for(i)
            i += 1
        r.feedback = render_feedback(r, r.level, rng)


def _gpp_log(log: str) -> str:
    lines = [l for l in (log or "").splitlines() if l.strip()]
    for k, line in enumerate(lines):
        if re.search(r":\d+:\d+: (?:fatal )?error:", line):
            head = re.sub(r"^\S*/(?=[\w.-]+\.cpp:)", "", line)
            return "\n".join([head, *lines[k + 1:k + 3]])
    return ""


def render_feedback(r: SynthRecord, level: str, rng: random.Random) -> str:
    defects = [d for d in r.provenance["defects"] if d in DEFECTS]
    if r.problem.exam_type == "multi_problem" and r.label.rule_id == "M4":
        states = r.provenance.get("observed_states") or {}
        perq = r.provenance.get("per_question_defects") or {}
        per = [(pid, perq.get(pid, []) or (["D13"] if st in ("partial", "fail") else ["D14"] if st == "edge" else []), st)
               for pid, st in states.items()]
        return multi_feedback(per, level, rng=rng)
    if not defects or r.label.total == 10:
        return praise(level, rng, multi=r.problem.exam_type == "multi_problem")
    if r.label.rule_id == "M3" and level_of(level) >= 2:
        per = [("P1", defects[:1], "fail"), ("P2", [], "ok"), ("P3", [], "ok"), ("P4", [], "ok")]
        text = multi_feedback(per, level, rng=rng)
        return text.replace("P2 đúng; P3 đúng; P4 đúng;", "các câu sau không được chấm.")
    log = _gpp_log(getattr(r, "_compile_log", "")) if rng.random() < GPP_LOG_SHARE else ""
    order = sorted(defects, key=lambda d: d == "D22")  # the behavioural defect first
    return feedback_for(order, level, location=_changed_location(getattr(r, "_base_code", r.code), r.code),
                        compile_log=log, rng=rng)


def assign_pairs(records: list[SynthRecord], max_pairs: int = 50, max_diff: int = 3) -> int:
    """Control pairs: same base, <= max_diff changed lines, different Task 1 label."""
    by_base = defaultdict(list)
    for r in records:
        by_base[r.provenance["base_id"]].append(r)
    pairs = 0
    for group in by_base.values():
        group.sort(key=lambda r: (r.label.total, r.sample_id))
        used = set()
        for a in group:
            for b in group:
                if pairs >= max_pairs:
                    return pairs
                if a is b or id(a) in used or id(b) in used or a.label.total == b.label.total:
                    continue
                if a.provenance["trap"] or b.provenance["trap"]:
                    continue
                if _diff_lines(a.code, b.code) <= max_diff:
                    pid = f"pair-{pairs:03d}"
                    a.provenance["pair_id"] = b.provenance["pair_id"] = pid
                    used |= {id(a), id(b)}
                    pairs += 1
    return pairs


def task3_records(records: list[SynthRecord], n_dup: int, rng: random.Random) -> list[SynthRecord]:
    """Original records + n_dup clones at another level, then rebalance to 30/40/20/10."""
    defective = [r for r in records if r.label.taxonomy]
    picks = rng.sample(defective, min(n_dup, len(defective)))
    clones = []
    for r in picks:
        new_level = FEEDBACK_LEVELS[level_of(r.level) % 4]
        c = SynthRecord(f"{r.sample_id}-L{level_of(new_level)}", r.problem, r.code, r.label, new_level, "",
                        r.compile_log, r.exec_report, r.heldout,
                        {**r.provenance, "duplicate_of": r.sample_id, "duplicate_level": new_level})
        c._compile_log, c._base_code = getattr(r, "_compile_log", ""), getattr(r, "_base_code", r.code)
        c.feedback = render_feedback(c, new_level, rng)
        clones.append(c)
    allr = records + clones
    n = len(allr)
    target = [round(w * n) for w in (0.30, 0.40, 0.20, 0.10)]
    clean = [r for r in allr if not r.label.taxonomy]           # praise, always Level 1
    rest = [r for r in allr if r.label.taxonomy]
    pool = ([FEEDBACK_LEVELS[0]] * max(0, target[0] - len(clean)) + [FEEDBACK_LEVELS[1]] * target[1]
            + [FEEDBACK_LEVELS[2]] * target[2] + [FEEDBACK_LEVELS[3]] * target[3])
    pool = (pool + [FEEDBACK_LEVELS[1]] * len(rest))[: len(rest)]
    rng.shuffle(pool)
    for r, lvl in zip(rest, pool):
        r.level, r.feedback = lvl, render_feedback(r, lvl, rng)
    # a clone must differ from its original's level
    by_id = {r.sample_id: r for r in records}
    for c in clones:
        orig = by_id[c.provenance["duplicate_of"]]
        if c.level == orig.level:
            c.level = FEEDBACK_LEVELS[level_of(orig.level) % 4]
            c.feedback = render_feedback(c, c.level, rng)
        c.provenance["duplicate_level"] = c.level
    return allr


# ------------------------------------------------------------------------------------------------
# guards, writing
# ------------------------------------------------------------------------------------------------

def apply_guards(records: list[SynthRecord], public_root: Path | None, *,
                 public_threshold: float = 0.5, dup_threshold: float = 0.9) -> tuple[list[SynthRecord], dict]:
    stats = {"n_in": len(records), "public_root": str(public_root) if public_root else None,
             "dropped_public": 0, "dropped_dup": 0, "max_public_similarity": 0.0}
    if not records:
        stats["n_out"] = 0
        return records, stats
    sigs = [signature(r.code) for r in records]
    if public_root is not None and public_root.exists():
        corpus = public_test_signatures(public_root)
        keep, sims = [], []
        for i, sig in enumerate(sigs):
            sim = max_similarity(sig, corpus)
            sims.append(sim)
            (keep.append(i) if sim < public_threshold else None)
        stats["dropped_public"] = len(records) - len(keep)
        stats["max_public_similarity"] = round(max(sims), 3) if sims else 0.0
        records, sigs = [records[i] for i in keep], [sigs[i] for i in keep]
    groups: dict[str, set[int]] = {}
    for i, r in enumerate(records):
        for key in ("pair_id", "base_id"):
            if r.provenance.get(key):
                groups.setdefault(f"{key}:{r.provenance[key]}", set()).add(i)
    res = dedupe(sigs, threshold=dup_threshold, keep_together=[g for g in groups.values() if len(g) > 1])
    stats["dropped_dup"] = len(res.dropped)
    records = [records[i] for i in res.kept]
    stats["n_out"] = len(records)
    return records, stats


def _write_split(directory: Path, problems: list[Problem], records: list[SynthRecord],
                 t3: list[SynthRecord]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "exams.json").write_text(
        json.dumps({"exams": [_exam_dict(p) for p in problems]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for r in {r.code_file: r for r in [*records, *t3]}.values():  # one file per submission
        path = directory / r.code_file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(r.code, encoding="utf-8")
    payloads = {
        "task1_grading.json": [{"sample_id": r.sample_id, "input": r.input_dict(),
                                "output": {"rubric": r.label.rubric, "total_score": r.label.total}} for r in records],
        "task2_error_taxonomy.json": [{"sample_id": r.sample_id, "input": r.input_dict(),
                                       "output": {"taxonomy_error": r.label.taxonomy}} for r in records],
        "task3_feedback.json": [{"sample_id": r.sample_id, "input": {**r.input_dict(), "target_feedback_level": r.level},
                                 "output": {"taxonomy_error": r.label.taxonomy, "feedback": r.feedback}} for r in t3],
    }
    for name, samples in payloads.items():
        meta = TASK_META[name.split("_")[0]]
        (directory / name).write_text(json.dumps({**meta, "n_samples": len(samples), "samples": samples},
                                                 ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = list({r.sample_id: r for r in [*records, *t3]}.values())
    (directory / "exec_reports.jsonl").write_text(
        "".join(json.dumps({"sample_id": r.sample_id, "exec_report": r.exec_report}, ensure_ascii=False) + "\n"
                for r in rows), encoding="utf-8")
    (directory / "provenance.jsonl").write_text(
        "".join(json.dumps({**r.provenance, "sample_id": r.sample_id, "feedback_level": r.level},
                           ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _exam_dict(p: Problem) -> dict:
    out = p.exam_dict()
    out.setdefault("grading_policy", "Nếu P1 (đọc file) sai thì các câu P2–P4 không được chấm."
                   if p.exam_type == "multi_problem" else "Chấm trên một bài duy nhất; điểm rubric là điểm của cả bài.")
    if p.exam_type == "multi_problem" and p.data_files:
        out.setdefault("data_file", next(iter(p.data_files)))
    return out


def _label_space() -> dict:
    for src in (ROOT / "data" / "raw" / "sample_dataset" / "label_space.json",
                ROOT / "data" / "public-test" / "sample_dataset" / "label_space.json"):
        if src.exists():
            return json.loads(src.read_text(encoding="utf-8"))
    return {"rubric": {"dimensions": [{"name": d, "range": [0, m]} for d, m in
                                      [("compilable", 1), ("io_format", 1), ("logic", 4), ("edge_case", 2),
                                       ("complexity", 1), ("code_quality", 1)]], "total_range": [0, 10]},
            "taxonomy_error": list(LABEL_SPACE),
            "feedback_level": [{"level": lvl} for lvl in FEEDBACK_LEVELS]}


def _find_public_root() -> Path | None:
    return next((p for p in PUBLIC_ROOTS if p.exists()), None)


def build(problems: dict[str, Problem], out_dir: str | Path, *, seed: int = 42, runner=None,
          public_root: str | Path | None = None, bases_dir: str | Path | None = None, scale: float = 1.0,
          heldout_scale: float = 80 / 500, oracle_mode: str = "minimal", n_task3_dup: int = 150,
          max_attempts: int = MAX_ATTEMPTS, cache_path: str | Path | None = None) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    runner = runner or make_runner(cache_path=cache_path)
    if runner is None:
        raise SystemExit("a C++ compiler is required: labels and exec_report come from real execution")
    rng = random.Random(seed)
    public_root = Path(public_root) if public_root else _find_public_root()
    builder = Builder(problems, runner, rng, Path(bases_dir) if bases_dir else None, oracle_mode, max_attempts)
    train = {e: p for e, p in problems.items() if not p.heldout}
    held = {e: p for e, p in problems.items() if p.heldout}

    records = schedule_and_build(builder, train, scale=scale, heldout=False)
    heldout_records = schedule_and_build(builder, held, scale=heldout_scale, heldout=True,
                                         n_traps_ten=(0, 0), n_traps_other=0, n_style=0)
    records, train_guard = top_up(builder, train, records, scale=scale, heldout=False, public_root=public_root)
    heldout_records, held_guard = top_up(builder, held, heldout_records, scale=heldout_scale, heldout=True,
                                         public_root=public_root)
    # shortfall = what is still missing after top-up (not the first-pass misses)
    builder.shortfall = Counter()
    for split, recs, sc, ex in (("", records, scale, train), ("heldout:", heldout_records, heldout_scale, held)):
        has_s = any(p.exam_type == "single_problem" for p in ex.values())
        has_m = any(p.exam_type == "multi_problem" for p in ex.values())
        want = Counter(_slot_key(sl) for sl in (quota.single_slots(sc) if has_s else []) + (quota.multi_slots(sc) if has_m else []))
        have = Counter(_record_key(r) for r in recs)
        for key, n in want.items():
            if have.get(key, 0) < n:
                builder.shortfall[split + key] = n - have.get(key, 0)
    assign_feedback(records, rng)
    assign_feedback(heldout_records, rng)
    n_pairs = assign_pairs(records)
    t3 = task3_records(records, round(n_task3_dup * scale), rng)

    _write_split(out, list(train.values()), records, t3)
    _write_split(out / "heldout", list(held.values()), heldout_records, heldout_records)
    (out / "label_space.json").write_text(json.dumps(_label_space(), ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")
    data_dir = out / "data_files"
    data_dir.mkdir(exist_ok=True)
    for p in problems.values():
        for name, content in p.data_files.items():
            (data_dir / name).write_text(content, encoding="utf-8")
    stats = {"n_train_records": len(records), "n_task3_records": len(t3), "n_heldout_records": len(heldout_records),
             "n_train_exams": len(train), "n_heldout_exams": len(held), "pairs": n_pairs,
             "traps": sum(1 for r in records if r.provenance["trap"]),
             "bases_per_exam": {e: len(b) for e, b in builder.bases.items()},
             "shortfall": dict(builder.shortfall), "quota": quota.bucket_summary(),
             "oracle_mode": oracle_mode, "runner": getattr(runner, "runner_id", "?"),
             "run_cache": runner.stats() if hasattr(runner, "stats") else None,
             "guards": {"train": train_guard, "heldout": held_guard}, "out": str(out)}
    (out / "build_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if hasattr(runner, "close"):
        runner.close()
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--problems-dir", default=str(ROOT / "src" / "synth" / "problems"))
    ap.add_argument("--out", default=str(ROOT / "data" / "synth" / "v1"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--bases-dir", default=str(ROOT / "src" / "synth" / "persona_bases"),
                    help="hand-written persona solutions: <dir>/<exam_id>/<persona>__k.cpp (each must pass all tests)")
    ap.add_argument("--public-root", default=None, help="public test release for the similarity guard")
    ap.add_argument("--no-guard", action="store_true")
    ap.add_argument("--oracle-mode", choices=("minimal", "full"), default="minimal")
    ap.add_argument("--count", action="store_true", help="full plan allocation (300 single + 200 multi)")
    ap.add_argument("--scale", type=float, default=None, help="fraction of the allocation (quick runs)")
    ap.add_argument("--cache", default=str(ROOT / "data" / "synth" / "run_cache.sqlite"),
                    help="persistent compile/run cache (SQLite); unchanged code is never re-executed")
    ap.add_argument("--no-cache", action="store_true", help="execute everything (e.g. after a compiler change)")
    a = ap.parse_args()
    problems = load_problems(a.problems_dir)
    if not problems:
        sys.exit(f"no problems found in {a.problems_dir}")
    scale = a.scale if a.scale is not None else (1.0 if a.count else 0.1)
    stats = build(problems, a.out, seed=a.seed, public_root=None if a.no_guard else a.public_root,
                  bases_dir=a.bases_dir, scale=scale, oracle_mode=a.oracle_mode,
                  cache_path=None if a.no_cache else a.cache)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
