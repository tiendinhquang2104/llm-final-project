"""Task 2 Hướng 1: prompt -> LLM -> parse labels -> self-consistency vote -> probabilities and labels."""
from __future__ import annotations

from src.llm.local_backend import OOM_MARK
from src.task2.compile import has_compile_error
from src.task2.labels import LABELS, coerce_labels, normalize_labels
from src.task2.prompts import RESPONSE_SCHEMA, build_messages, select_demos
from src.task2.prompts_cot import build_cot_messages, split_final
from src.task2.split import compile_error_lines, merge_parts, split_submission
from src.utils.json_extractor import extract_json_objects

RETRY_MSG = ("Câu trả lời trên không phải JSON hợp lệ theo schema yêu cầu. "
             "Hãy trả về DUY NHẤT một object JSON hợp lệ, không thêm chữ nào khác.")


def parse_labels(text: str, lenient: bool = False) -> list[str] | None:
    """Labels from the last JSON object with a list `taxonomy_error` (unknown labels dropped); None if none.
    `lenient`: also map short names ("Vòng lặp" -> Lỗi vòng lặp) via coerce_labels."""
    for obj in extract_json_objects(text or ""):
        if isinstance(obj.get("taxonomy_error"), list):
            return (coerce_labels if lenient else normalize_labels)(obj["taxonomy_error"])
    return None


def parse_cot_labels(text: str) -> list[str] | None:
    """CoT answer: labels from the JSON after the last `KẾT LUẬN:` / `CONCLUSION:`; else from the last line naming
    `taxonomy_error`; else anywhere (bare-JSON retry answers). Reasoning may quote code with braces,
    so the whole text is the last resort only."""
    text = text or ""
    tail = split_final(text)[1]
    if tail is not None:
        got = parse_labels(tail, lenient=True)
        if got is not None:
            return got
    lines = [ln for ln in text.splitlines() if "taxonomy_error" in ln]
    if lines:
        got = parse_labels(lines[-1], lenient=True)
        if got is not None:
            return got
    return parse_labels(text, lenient=True)


def vote(label_lists: list[list[str]]) -> dict[str, float]:
    n = len(label_lists)
    return {lab: (sum(lab in ls for ls in label_lists) / n if n else 0.0) for lab in LABELS}


class Task2ApiPipeline:
    def __init__(self, dataset, backend, cfg: dict, demo_pool=()):
        self.ds, self.backend, self.cfg = dataset, backend, cfg
        self.prompt_cfg = cfg.get("prompt", {})
        self.gen_cfg = cfg.get("generation", {})
        # CoT few-shot takes a retriever (src/task2/cot_demos.DemoRetriever); the JSON style takes a list of samples
        self.retriever = demo_pool if hasattr(demo_pool, "select") else None
        self.demo_pool = [] if self.retriever else list(demo_pool)
        self._by_id = None
        self.style = self.prompt_cfg.get("style", "json")
        self.parse = parse_cot_labels if self.style == "cot" else parse_labels

    def parts(self, sample) -> list | None:
        """Per-question parts when prompt.split_problems is on and the multi_problem submission can be split."""
        if self.style != "cot" or not self.prompt_cfg.get("split_problems"):
            return None
        exam = self.ds.exams[sample.exam_id]
        if exam.get("exam_type") != "multi_problem":
            return None
        return split_submission(sample.code, exam.get("problems") or [])

    def build_request(self, sample) -> dict:
        exam = self.ds.exams[sample.exam_id]
        parts = self.parts(sample)
        if parts:  # one prompt per question, no demos (they are whole submissions); "messages" only keys the cache
            reqs = [{"sample": sample, "exam": exam, "pid": pt.pid, "schema": None, "schema_name": "task2_cot",
                     "messages": build_cot_messages(exam, sample, self.prompt_cfg, (), pt)} for pt in parts]
            return {"sample": sample, "exam": exam, "demos": [], "parts": reqs,
                    "messages": [m for q in reqs for m in q["messages"]], "schema": None, "schema_name": "task2_cot"}
        if self.style == "cot":  # CoT: optional retrieved demos, free-text reasoning then the KẾT LUẬN line
            k = int(self.prompt_cfg.get("few_shot_k", 0))
            demos = self.retriever.select(sample)[:k] if (self.retriever and k > 0) else []
            budget = int(self.prompt_cfg.get("max_prompt_chars", 0))
            messages = build_cot_messages(exam, sample, self.prompt_cfg, demos)
            while demos and budget and sum(len(m["content"]) for m in messages) > budget:
                demos = demos[:-1]  # long submission: drop the least similar demo (GPU memory, see run_cot.yaml)
                messages = build_cot_messages(exam, sample, self.prompt_cfg, demos)
            return {"sample": sample, "exam": exam,
                    "demos": [f"{d.source}:{d.sample.sample_id}:{d.similarity:.2f}" for d in demos],
                    "messages": messages, "schema": None, "schema_name": "task2_cot"}
        demos = select_demos(self.demo_pool, sample, int(self.prompt_cfg.get("few_shot_k", 0)))
        return {"sample": sample, "exam": exam, "demos": [d.sample_id for d in demos],
                "messages": build_messages(exam, sample, demos, self.prompt_cfg),
                "schema": RESPONSE_SCHEMA, "schema_name": "task2_labels"}

    def infer(self, samples: list) -> list[dict]:
        reqs = [self.build_request(s) for s in samples]
        units = []  # (request index, part index or None, backend request): split questions run in the same batch
        for i, q in enumerate(reqs):
            units += [(i, k, pq) for k, pq in enumerate(q["parts"])] if q.get("parts") else [(i, None, q)]
        outs = self.backend.generate([u[2] for u in units], self.gen_cfg)
        res = [{"outputs": texts, "retry_outputs": []} for texts in outs]
        for _ in range(int(self.cfg.get("retry_on_parse_fail", 1))):
            bad = [j for j, r in enumerate(res) if all(self.parse(t) is None for t in r["outputs"] + r["retry_outputs"])]
            if not bad:
                break
            retry = []
            for j in bad:
                q = dict(units[j][2])
                last = (res[j]["retry_outputs"] or res[j]["outputs"] or [""])[-1]
                if last.strip() and not last.startswith(OOM_MARK):  # answered but not valid JSON -> fix the format
                    # (an OOM placeholder is not an answer: resend the original prompt)
                    q["messages"] = q["messages"] + [{"role": "assistant", "content": last[-3000:]},
                                                     {"role": "user", "content": RETRY_MSG}]
                retry.append(q)
            gen = {**self.gen_cfg, "n": 1, "temperature": 0.0, "enable_thinking": False}
            for j, texts in zip(bad, self.backend.generate(retry, gen)):
                res[j]["retry_outputs"].extend(texts)
        records = [{"sample_id": q["sample"].sample_id, "exam_id": q["sample"].exam_id, "demos": q["demos"],
                    "outputs": [], "retry_outputs": []} for q in reqs]
        for (i, k, uq), r in zip(units, res):
            rec = records[i]
            if k is None:
                rec["outputs"], rec["retry_outputs"] = r["outputs"], r["retry_outputs"]
                continue
            rec.setdefault("parts", []).append({"pid": uq["pid"], **r})
            # flattened copies, headed by the question, for the debug report
            rec["outputs"] += [f"### {uq['pid']}\n{t}" for t in r["outputs"]]
            rec["retry_outputs"] += [f"### {uq['pid']}\n{t}" for t in r["retry_outputs"]]
        return records

    @staticmethod
    def empty_prediction(sample) -> dict:
        return {"sample_id": sample.sample_id, "exam_id": sample.exam_id, "parse_ok": False, "n_parsed": 0,
                "probs": {lab: 0.0 for lab in LABELS}, "labels": []}

    def postprocess(self, record: dict) -> dict:
        if record.get("parts"):
            return self._postprocess_parts(record)
        return self._postprocess_one(record)

    def _postprocess_parts(self, record: dict) -> dict:
        """Each question voted on its own; merged along is_prerequisite_for (src/task2/split.merge_parts).
        "Lỗi biên dịch" stays a whole-file property (compile rule); a compiler error inside a question's own lines
        makes that question fail as a prerequisite."""
        sample = self._sample(record["sample_id"])
        exam = self.ds.exams[sample.exam_id]
        rule = bool(self.prompt_cfg.get("compile_rule")) and sample.compile_log is not None
        split = {pt.pid: pt for pt in (split_submission(sample.code, exam.get("problems") or []) or [])}
        err_lines = compile_error_lines(sample.compile_log) if rule else set()
        part_labels, part_probs, info, n_parsed, ok = {}, {}, [], 0, True
        for part in record["parts"]:
            one = self._postprocess_one({"sample_id": record["sample_id"], "exam_id": record["exam_id"],
                                         "outputs": part["outputs"], "retry_outputs": part["retry_outputs"]},
                                        compile_rule=False)
            labs = [lab for lab in one["labels"] if not (rule and lab == "Lỗi biên dịch")]
            part_labels[part["pid"]], part_probs[part["pid"]] = labs, one["probs"]
            n_parsed += one["n_parsed"]
            ok = ok and one["parse_ok"]
            info.append({"pid": part["pid"], "labels": labs, "parse_ok": one["parse_ok"]})
        own_err = {pid for pid, pt in split.items() if pt.own & err_lines}
        labels, graded = merge_parts(exam.get("problems") or [], part_labels, own_err)
        for row in info:
            row["graded"] = row["pid"] in graded
            row["compile_error_here"] = row["pid"] in own_err
        probs = {lab: max([part_probs[pid].get(lab, 0.0) for pid in graded] or [0.0]) for lab in LABELS}
        for lab in LABELS:
            if lab not in labels:
                probs[lab] = min(probs[lab], 0.49)  # a label of a question that is not graded does not count
        out = {"sample_id": record["sample_id"], "exam_id": record["exam_id"], "parse_ok": ok,
               "n_parsed": n_parsed, "probs": probs, "parts": info}
        if rule:
            out["model_compile_vote"] = max((p.get("Lỗi biên dịch", 0.0) for p in part_probs.values()), default=0.0)
            probs["Lỗi biên dịch"] = 1.0 if has_compile_error(sample.compile_log) else 0.0
            out["compile_rule"] = True
        out["labels"] = [lab for lab in LABELS if lab == "Lỗi biên dịch" and probs[lab] >= 0.5 or lab in labels]
        return out

    def _postprocess_one(self, record: dict, compile_rule: bool | None = None) -> dict:
        rule_on = self.prompt_cfg.get("compile_rule") if compile_rule is None else compile_rule
        parsed = [p for p in map(self.parse, record["outputs"]) if p is not None]
        total = len(record["outputs"])
        if not parsed:
            parsed = [p for p in map(self.parse, record.get("retry_outputs", [])) if p is not None]
            total = len(parsed)
        if not parsed:
            out = self.empty_prediction(self._sample(record["sample_id"]))
            log = self._sample(record["sample_id"]).compile_log
            if rule_on and has_compile_error(log):  # the rule needs no model answer
                out["probs"]["Lỗi biên dịch"] = 1.0
                out["labels"] = ["Lỗi biên dịch"]
                out["compile_rule"] = True
            return out
        probs = vote(parsed)
        if self.style == "cot" and total > len(parsed):
            # an unparsed answer is an abstention: a label needs half of ALL answers (3 of 5), not 2 of the 4 parsed
            probs = {lab: v * len(parsed) / total for lab, v in probs.items()}
        out = {"sample_id": record["sample_id"], "exam_id": record["exam_id"], "parse_ok": True,
               "n_parsed": len(parsed), "probs": probs}
        log = self._sample(record["sample_id"]).compile_log
        if rule_on and log is not None:
            # "Lỗi biên dịch" := the self-compiled log has a compiler error (warnings / missing main do not count);
            # the model's vote for it is kept in model_probs for the report
            out["model_compile_vote"] = probs["Lỗi biên dịch"]
            probs["Lỗi biên dịch"] = 1.0 if has_compile_error(log) else 0.0
            out["compile_rule"] = True
        out["labels"] = [lab for lab in LABELS if probs[lab] >= 0.5]
        return out

    def _sample(self, sample_id):
        if self._by_id is None:
            self._by_id = self.ds.by_id()
        return self._by_id[sample_id]
