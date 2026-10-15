"""Few-shot demos for the CoT prompt, retrieved by code similarity (docs/task2_prompting.md, "RAG few-shot").

Pools are labelled sets only: the 32 gold and the synthetic silver set; never the public release (instructor
ruling 2026-10-11). Gold comes first: gold samples at least `min_gold_sim` similar to the submission, best first,
then silver fills the remaining slots. The sample being graded is never its own demo (leave-one-out on gold).
Demos show code, a one-line compile status and the teacher's conclusion line; `feedback` is never used."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from src.task2.compile import has_compile_error


@dataclass
class Demo:
    sample: object
    source: str      # "gold" | "silver"
    similarity: float


def compile_status(log: str | None) -> str:
    if log is None:
        return "không có compile_log"
    if has_compile_error(log):
        first = next((ln.strip() for ln in log.splitlines() if "error" in ln), "")
        return f"có lỗi biên dịch ({first[:160]})"
    return "chỉ có cảnh báo (warning), không có lỗi" if log.strip() else "sạch (không lỗi, không cảnh báo)"


class DemoRetriever:
    def __init__(self, gold: list, silver: list, k: int = 3, min_gold_sim: float = 0.3):
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.k, self.min_gold_sim = k, min_gold_sim
        self.pool = [(s, "gold") for s in gold if s.has_gold] + [(s, "silver") for s in silver if s.has_gold]
        self.vec = TfidfVectorizer(token_pattern=r"[A-Za-z_]\w*|[^\sA-Za-z_0-9]", ngram_range=(1, 2),
                                   sublinear_tf=True, min_df=1)
        self.matrix = self.vec.fit_transform([s.code for s, _ in self.pool]) if self.pool else None

    def info(self) -> dict:
        return {"k": self.k, "min_gold_sim": self.min_gold_sim,
                "gold": sum(src == "gold" for _, src in self.pool),
                "silver": sum(src == "silver" for _, src in self.pool)}

    def fingerprint(self) -> dict:
        """Content hash of each pool (sample ids, labels, code; not compile logs, which depend on the compiler):
        a bundle records it so a later run can tell whether the demos can still be the same."""
        out = {}
        for src in ("gold", "silver"):
            items = sorted((s.sample_id, list(s.labels), s.code) for s, so in self.pool if so == src)
            out[src] = {"n": len(items),
                        "sha256": hashlib.sha256(json.dumps(items, ensure_ascii=False).encode("utf-8")).hexdigest()}
        return out

    def select(self, sample) -> list[Demo]:
        if not self.pool or self.k <= 0:
            return []
        sims = (self.matrix @ self.vec.transform([sample.code]).T).toarray().ravel()
        ranked = sorted(((float(sims[i]), s.sample_id, s, src) for i, (s, src) in enumerate(self.pool)
                         if s.sample_id != sample.sample_id), key=lambda t: (-t[0], t[1]))
        gold = [Demo(s, src, sim) for sim, _, s, src in ranked if src == "gold" and sim >= self.min_gold_sim]
        silver = [Demo(s, src, sim) for sim, _, s, src in ranked if src == "silver"]
        return (gold + silver)[:self.k]
