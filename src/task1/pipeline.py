"""Task 1 pipeline: prompt -> LLM -> parse -> (aggregate) -> deterministic rules -> prediction."""
from __future__ import annotations

import statistics

from src.data.loader import DIMENSIONS, Dataset, Sample
from src.task1.prerequisite_rules import RuleConfig, apply_rules, clamp_rubric, policy_from_exam
from src.task1.prompts import build_messages, select_demos
from src.task1.scorer import aggregate, parse_output, round_half_up

RETRY_MSG = (
    "Câu trả lời trên không phải JSON hợp lệ theo schema yêu cầu. "
    "Hãy trả về DUY NHẤT một object JSON hợp lệ, không thêm chữ nào khác."
)


class Task1Pipeline:
    def __init__(self, dataset: Dataset, backend, cfg: dict, demo_pool: list[Sample] | None = None):
        self.ds = dataset
        self.backend = backend
        self.cfg = cfg
        self.prompt_cfg = cfg.get("prompt", {})
        self.gen_cfg = cfg.get("generation", {})
        self.rule_cfg = RuleConfig.from_dict(cfg.get("rules"))
        self.demo_pool = demo_pool or []
        self.policies = {eid: policy_from_exam(e, (cfg.get("policy_overrides") or {}).get(eid))
                         for eid, e in dataset.exams.items()}
        self.fallback = self._fallback_rubrics()
        self._by_id = dataset.by_id()

    # -- fallback when the model never produces parseable output ---------------------------------
    def _fallback_rubrics(self) -> dict[str, dict[str, int]]:
        out = {}
        for eid in self.ds.exams:
            pool = [s for s in self.demo_pool if s.exam_id == eid and s.has_gold]
            if pool:
                out[eid] = {d: round_half_up(statistics.median(s.gold_rubric[d] for s in pool)) for d in DIMENSIONS}
            else:
                out[eid] = {"compilable": 1, "io_format": 1, "logic": 2, "edge_case": 1, "complexity": 1,
                            "code_quality": 1}
        return out

    # -- inference ---------------------------------------------------------------------------------
    def build_request(self, sample: Sample) -> dict:
        exam = self.ds.exams[sample.exam_id]
        k = int(self.prompt_cfg.get("few_shot_k", 0))
        demos = select_demos(self.demo_pool, sample, k, self.prompt_cfg.get("demo_strategy", "spread"))
        return {
            "sample": sample,
            "exam": exam,
            "demos": [d.sample_id for d in demos],
            "messages": build_messages(exam, sample, demos, self.prompt_cfg),
        }

    def infer(self, samples: list[Sample]) -> list[dict]:
        """Run the model; returns raw records (cacheable, rule-agnostic)."""
        reqs = [self.build_request(s) for s in samples]
        outs = self.backend.generate(reqs, self.gen_cfg)
        records = []
        for q, texts in zip(reqs, outs):
            records.append({"sample_id": q["sample"].sample_id, "demos": q["demos"], "outputs": texts,
                            "retry_outputs": []})
        n_retry = int(self.cfg.get("retry_on_parse_fail", 1))
        for _ in range(n_retry):
            bad = [i for i, r in enumerate(records)
                   if not any(parse_output(t).ok for t in r["outputs"] + r["retry_outputs"])]
            if not bad:
                break
            retry_reqs = []
            for i in bad:
                q = dict(reqs[i])
                last = (records[i]["retry_outputs"] or records[i]["outputs"] or [""])[-1]
                if last.strip():  # model answered but not valid JSON -> ask it to fix the format
                    q["messages"] = q["messages"] + [
                        {"role": "assistant", "content": last[-3000:]},
                        {"role": "user", "content": RETRY_MSG},
                    ]
                # else: the request itself failed (empty text) -> resend the original prompt
                retry_reqs.append(q)
            gen = {**self.gen_cfg, "enable_thinking": False, "n": 1, "temperature": 0.0}
            for i, texts in zip(bad, self.backend.generate(retry_reqs, gen)):
                records[i]["retry_outputs"].extend(texts)
        return records

    # -- post-processing (pure; can be re-run with different rule configs) -------------------------
    def postprocess(self, record: dict, rule_cfg: RuleConfig | None = None) -> dict:
        rule_cfg = rule_cfg or self.rule_cfg
        sample = self._by_id[record["sample_id"]]
        parsed = [parse_output(t) for t in record["outputs"]]
        if not any(p.ok for p in parsed):
            parsed += [parse_output(t) for t in record.get("retry_outputs", [])]
        rubric, statuses, rationale = aggregate(parsed)
        fallback = rubric is None
        if fallback:
            rubric = dict(self.fallback[sample.exam_id])
        rubric_llm = clamp_rubric(rubric)
        final, total, trace = apply_rules(rubric, statuses, self.policies[sample.exam_id], rule_cfg)
        return {
            "sample_id": sample.sample_id,
            "exam_id": sample.exam_id,
            "parse_ok": not fallback,
            "n_parsed": sum(p.ok for p in parsed),
            "fallback_used": fallback,
            "problems": statuses,
            "rationale": rationale,
            "rubric_llm": rubric_llm,
            "total_llm": sum(rubric_llm.values()),
            "rubric": final,
            "total_score": total,
            "rule_trace": trace,
        }

    def postprocess_all(self, records: list[dict], rule_cfg: RuleConfig | None = None) -> list[dict]:
        return [self.postprocess(r, rule_cfg) for r in records]

    def run(self, samples: list[Sample]) -> tuple[list[dict], list[dict]]:
        records = self.infer(samples)
        return records, self.postprocess_all(records)


def to_submission(preds: list[dict]) -> list[dict]:
    """Leaderboard format: [{sample_id, output: {rubric, total_score}}]."""
    return [{"sample_id": p["sample_id"], "output": {"rubric": p["rubric"], "total_score": p["total_score"]}}
            for p in preds]
