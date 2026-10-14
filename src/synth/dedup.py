"""Similarity guard (synth_plan.md "Hàng rào kỹ thuật"), implementation step 7.

Two uses, both deterministic:

* ``max_similarity`` against the public test corpus: any synthetic submission with Jaccard >= 0.5
  (normalized token 5-grams) is rejected, so public-test code cannot leak into the dataset.
* intra-synthetic dedup: submissions with Jaccard >= 0.9 are dropped, except within a control pair.

Uses a MinHash signature (num_perm permutations) to estimate Jaccard without O(n^2) set compares.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
_STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
_TOKEN_RE = re.compile(r"[A-Za-z_]\w*|\d+|[-+*/%=<>!&|^~?:;,.()\[\]{}]")
DEFAULT_SNIPPETS = 5
DEFAULT_PERM = 128


def normalize_tokens(code: str, n: int = DEFAULT_SNIPPETS) -> set[str]:
    """Comment/string-stripped token n-grams of a submission."""
    text = _STRING_RE.sub(" S ", _COMMENT_RE.sub(" ", code or ""))
    tokens = _TOKEN_RE.findall(text)
    if len(tokens) < n:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


def minhash(shingles: set[str], num_perm: int = DEFAULT_PERM, seed: int = 0) -> tuple[int, ...]:
    """MinHash signature: for each permutation, the minimum hash over the shingles.

    Code with no tokens (empty / fully commented) gets an empty signature: it carries no content,
    so it can never count as similar to anything (it used to match every empty public file at 1.0)."""
    if not shingles:
        return ()
    sig = []
    for p in range(num_perm):
        best = None
        for sh in shingles:
            h = int.from_bytes(hashlib.blake2b(f"{seed}:{p}:{sh}".encode(), digest_size=8).digest(), "big")
            if best is None or h < best:
                best = h
        sig.append(best)
    return tuple(sig)


def jaccard(sig_a: tuple[int, ...], sig_b: tuple[int, ...]) -> float:
    if not sig_a or not sig_b or len(sig_a) != len(sig_b):
        return 0.0
    return sum(a == b for a, b in zip(sig_a, sig_b)) / len(sig_a)


def signature(code: str, num_perm: int = DEFAULT_PERM, seed: int = 0) -> tuple[int, ...]:
    return minhash(normalize_tokens(code), num_perm, seed)


def max_similarity(sig: tuple[int, ...], corpus: list[tuple[int, ...]]) -> float:
    return max((jaccard(sig, c) for c in corpus), default=0.0)


@dataclass
class DedupResult:
    kept: list[int]
    dropped: list[tuple[int, int, float]]  # (index, similar_to, score)


def dedupe(signatures: list[tuple[int, ...]], threshold: float = 0.9,
           keep_together: list[set[int]] | None = None) -> DedupResult:
    """Drop near-duplicates; indices inside the same group of ``keep_together`` are never split."""
    groups = keep_together or []
    grouping: dict[int, int] = {}
    for gi, g in enumerate(groups):
        for i in g:
            grouping[i] = gi
    kept: list[int] = []
    dropped: list[tuple[int, int, float]] = []
    for i, sig in enumerate(signatures):
        conflict = None
        for j in kept:
            if grouping.get(i) is not None and grouping.get(i) == grouping.get(j):
                continue
            score = jaccard(sig, signatures[j])
            if score >= threshold:
                conflict = (i, j, score)
                break
        if conflict:
            dropped.append(conflict)
        else:
            kept.append(i)
    return DedupResult(kept, dropped)


def public_test_signatures(root, num_perm: int = DEFAULT_PERM, seed: int = 0) -> list[tuple[int, ...]]:
    """Signatures of every *.cpp under a public-test root (for the leakage guard)."""
    from pathlib import Path

    root = Path(root)
    sigs = []
    for path in sorted(root.rglob("*.cpp")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        sigs.append(signature(text, num_perm, seed))
    return sigs
