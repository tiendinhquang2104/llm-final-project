"""Style profile from the public test set (synth_plan.md "Quy định dùng public test", step 4a).

The public test release may only be used to describe *aggregate* student style — never to label,
and never copied. ``style_profile.json`` contains statistics and a human-readable persona
description, no source code. Up to three short (<=15 line) snippets are kept in a *separate*
``style_snippets.json`` with their source, so the isolation rule is auditable.

Everything below is pure given a list of code strings, so it is unit-tested without the dataset.
"""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_INCLUDE_RE = re.compile(r'#\s*include\s*[<"]([^>"]+)[>"]')
_FUNC_RE = re.compile(r"[A-Za-z_]\w*\s+[A-Za-z_]\w*\s*\([^;{}]*\)\s*\{")
_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
_VN_HINTS = ("dem", "tong", "tich", "kiemtra", "so", "nguyen", "them", "xoa", "tim", "inra", "chieu", "dai", "gia_tri")


def _decode(raw: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "cp1258", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def count_comments(code: str) -> int:
    return sum(1 for line in code.splitlines() if line.strip().startswith(("//", "/*", "*")) or "//" in line)


def analyze(codes: list[str]) -> dict:
    """Aggregate statistics over a list of submissions. Never returns code."""
    if not codes:
        return {"n_files": 0}
    lengths, comments, funcs = [], [], []
    includes: Counter[str] = Counter()
    flags = Counter()
    vn_files = 0
    for code in codes:
        lines = code.splitlines()
        lengths.append(len(lines))
        comments.append(count_comments(code) / max(len(lines), 1))
        funcs.append(len(_FUNC_RE.findall(code)))
        for inc in _INCLUDE_RE.findall(code):
            includes[inc.split("/")[-1]] += 1
        if re.search(r"\bvoid\s+main\s*\(", code):
            flags["void_main"] += 1
        if "bits/stdc++" in code:
            flags["bits_header"] += 1
        if re.search(r"#\s*define\s+ll\b", code):
            flags["define_ll"] += 1
        if "ifstream" in code or "fopen" in code:
            flags["reads_file"] += 1
        if "getline" in code:
            flags["uses_getline"] += 1
        if "while" in code and (".eof()" in code or "!f.eof" in code):
            flags["while_eof"] += 1
        low = code.lower()
        if any(h in low for h in _VN_HINTS):
            vn_files += 1
    n = len(codes)
    return {
        "n_files": n,
        "lines": {"mean": round(statistics.mean(lengths), 1),
                  "median": round(statistics.median(lengths), 1),
                  "p90": round(sorted(lengths)[int(0.9 * (n - 1))], 1)},
        "comment_line_ratio": round(statistics.mean(comments), 3),
        "function_count": {"mean": round(statistics.mean(funcs), 2),
                           "single_function_ratio": round(sum(f == 1 for f in funcs) / n, 3)},
        "top_includes": [name for name, _ in includes.most_common(8)],
        "flags_ratio": {k: round(v / n, 3) for k, v in sorted(flags.items())},
        "vietnamese_identifier_ratio": round(vn_files / n, 3),
    }


def persona_text(stats: dict) -> str:
    """A one-paragraph description safe to put in a generation prompt (no code)."""
    if not stats.get("n_files"):
        return "Không có dữ liệu văn phong."
    lines = stats["lines"]
    single = stats["function_count"]["single_function_ratio"]
    flags = stats["flags_ratio"]
    bits = [
        f"Sinh viên viết trung bình {lines['mean']} dòng/bài (trung vị {lines['median']})",
        f"tỉ lệ dòng comment khoảng {stats['comment_line_ratio']:.0%}",
        f"{single:.0%} bài dồn hết logic vào một hàm",
    ]
    if flags.get("void_main"):
        bits.append(f"{flags['void_main']:.0%} dùng `void main` kiểu MSVC")
    if flags.get("bits_header"):
        bits.append(f"{flags['bits_header']:.0%} dùng `bits/stdc++.h`")
    if flags.get("define_ll"):
        bits.append(f"{flags['define_ll']:.0%} dùng `#define ll long long`")
    if flags.get("reads_file"):
        bits.append(f"{flags['reads_file']:.0%} đọc file bằng ifstream/fopen")
    if stats.get("vietnamese_identifier_ratio"):
        bits.append(f"{stats['vietnamese_identifier_ratio']:.0%} đặt tên biến tiếng Việt không dấu")
    return "; ".join(bits) + "."


@dataclass
class StyleProfile:
    stats: dict
    persona: str
    snippets: list[dict]

    def to_json(self) -> dict:
        return {"stats": self.stats, "persona": self.persona}


def build_style_profile(public_root: str | Path, out_dir: str | Path, *, max_snippets: int = 3,
                        max_snippet_lines: int = 15) -> StyleProfile:
    """Read public-test submissions, write ``style_profile.json`` (no code) and ``style_snippets.json``."""
    root = Path(public_root)
    files = sorted(p for p in root.rglob("*.cpp") if p.is_file())
    codes = [_decode(p.read_bytes()) for p in files]
    stats = analyze(codes)
    profile = StyleProfile(stats=stats, persona=persona_text(stats), snippets=_pick_snippets(files, codes, max_snippets, max_snippet_lines))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "style_profile.json").write_text(json.dumps(profile.to_json(), ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")
    (out / "style_snippets.json").write_text(json.dumps(profile.snippets, ensure_ascii=False, indent=2) + "\n",
                                             encoding="utf-8")
    return profile


def _pick_snippets(files: list[Path], codes: list[str], k: int, max_lines: int) -> list[dict]:
    """At most k short snippets, each with its source, chosen for diversity of the header region."""
    out, seen = [], set()
    for path, code in zip(files, codes):
        head = [ln for ln in code.splitlines() if not _COMMENT_RE.fullmatch(ln.strip())][:max_lines]
        key = len(head)
        if key in seen or not head:
            continue
        seen.add(key)
        out.append({"source": str(path), "lines": head})
        if len(out) >= k:
            break
    return out
