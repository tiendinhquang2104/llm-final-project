"""Task 2 Hướng 1: prompt -> LLM -> parse labels -> self-consistency vote -> probabilities and labels."""
from __future__ import annotations

from src.task2.labels import LABELS, normalize_labels
from src.task2.prompts import RESPONSE_SCHEMA, build_messages, select_demos
from src.task2.prompts_cot import FINAL_MARKER, build_cot_messages
from src.utils.json_extractor import extract_json_objects

RETRY_MSG = ("Câu trả lời trên không phải JSON hợp lệ theo schema yêu cầu. "
             "Hãy trả về DUY NHẤT một object JSON hợp lệ, không thêm chữ nào khác.")


def parse_labels(text: str) -> list[str] | None:
    """Labels from the last JSON object with a list `taxonomy_error` (unknown labels dropped); None if none."""
    for obj in extract_json_objects(text or ""):
        if isinstance(obj.get("taxonomy_error"), list):
            return normalize_labels(obj["taxonomy_error"])
    return None


def parse_cot_labels(text: str) -> list[str] | None:
    """CoT answer: labels from the JSON after the last `KẾT LUẬN:`; else from the last line naming
    `taxonomy_error`; else anywhere (bare-JSON retry answers). Reasoning may quote code with braces,
    so the whole text is the last resort only."""
    text = text or ""
    if FINAL_MARKER in text:
        got = parse_labels(text.rsplit(FINAL_MARKER, 1)[1])
        if got is not None:
            return got
    lines = [ln for ln in text.splitlines() if "taxonomy_error" in ln]
    if lines:
        got = parse_labels(lines[-1])
        if got is not None:
            return got
    return parse_labels(text)


def vote(label_lists: list[list[str]]) -> dict[str, float]:
    n = len(label_lists)
    return {lab: (sum(lab in ls for ls in label_lists) / n if n else 0.0) for lab in LABELS}


class Task2ApiPipeline:
    def __init__(self, dataset, backend, cfg: dict, demo_pool=()):
        self.ds, self.backend, self.cfg = dataset, backend, cfg
        self.prompt_cfg = cfg.get("prompt", {})
        self.gen_cfg = cfg.get("generation", {})
        self.demo_pool = list(demo_pool)
        self.style = self.prompt_cfg.get("style", "json")
        self.parse = parse_cot_labels if self.style == "cot" else parse_labels

    def build_request(self, sample) -> dict:
        exam = self.ds.exams[sample.exam_id]
        if self.style == "cot":  # zero-shot CoT: no demos, free-text reasoning then the KẾT LUẬN line
            return {"sample": sample, "exam": exam, "demos": [],
                    "messages": build_cot_messages(exam, sample, self.prompt_cfg),
                    "schema": None, "schema_name": "task2_cot"}
        demos = select_demos(self.demo_pool, sample, int(self.prompt_cfg.get("few_shot_k", 0)))
        return {"sample": sample, "exam": exam, "demos": [d.sample_id for d in demos],
                "messages": build_messages(exam, sample, demos, self.prompt_cfg),
                "schema": RESPONSE_SCHEMA, "schema_name": "task2_labels"}

    def infer(self, samples: list) -> list[dict]:
        reqs = [self.build_request(s) for s in samples]
        outs = self.backend.generate(reqs, self.gen_cfg)
        records = [{"sample_id": q["sample"].sample_id, "exam_id": q["sample"].exam_id, "demos": q["demos"],
                    "outputs": texts, "retry_outputs": []} for q, texts in zip(reqs, outs)]
        for _ in range(int(self.cfg.get("retry_on_parse_fail", 1))):
            bad = [i for i, r in enumerate(records)
                   if all(self.parse(t) is None for t in r["outputs"] + r["retry_outputs"])]
            if not bad:
                break
            retry = []
            for i in bad:
                q = dict(reqs[i])
                last = (records[i]["retry_outputs"] or records[i]["outputs"] or [""])[-1]
                if last.strip():  # answered but not valid JSON -> ask to fix the format
                    q["messages"] = q["messages"] + [{"role": "assistant", "content": last[-3000:]},
                                                     {"role": "user", "content": RETRY_MSG}]
                retry.append(q)
            gen = {**self.gen_cfg, "n": 1, "temperature": 0.0, "enable_thinking": False}
            for i, texts in zip(bad, self.backend.generate(retry, gen)):
                records[i]["retry_outputs"].extend(texts)
        return records

    @staticmethod
    def empty_prediction(sample) -> dict:
        return {"sample_id": sample.sample_id, "exam_id": sample.exam_id, "parse_ok": False, "n_parsed": 0,
                "probs": {lab: 0.0 for lab in LABELS}, "labels": []}

    def postprocess(self, record: dict) -> dict:
        parsed = [p for p in map(self.parse, record["outputs"]) if p is not None]
        if not parsed:
            parsed = [p for p in map(self.parse, record.get("retry_outputs", [])) if p is not None]
        if not parsed:
            return {**self.empty_prediction(self.ds.by_id()[record["sample_id"]])}
        probs = vote(parsed)
        return {"sample_id": record["sample_id"], "exam_id": record["exam_id"], "parse_ok": True,
                "n_parsed": len(parsed), "probs": probs, "labels": [lab for lab in LABELS if probs[lab] >= 0.5]}
