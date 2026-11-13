"""Keep a copy of every leaderboard submission and its score (the leaderboard only shows the latest one).

    # before / right after uploading a file
    python scripts/archive_submission.py add outputs/task1_qlora/predict/task1_predictions.json --name qlora_v1 --note "..."
    # once the leaderboard shows the score: paste the row as printed
    python scripts/archive_submission.py score 01 "9 6-Agents 0.7188 2.0305 0.9085 0.8171 0.5945 0.6220 0.8049 0.7683 15:43 19/10/2026"
    python scripts/archive_submission.py list

Everything goes to outputs/submissions/<task>/ (gitignored: test predictions must not reach the public repo).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXACT = ["compilable", "io_format", "logic", "edge_case", "complexity", "code_quality"]
RUN_INFO = ["run_info.json", "progress.json"]  # written next to the predictions by the QLoRA / API pipelines


def index_path(task: str) -> Path:
    return ROOT / "outputs" / "submissions" / task / "submissions.json"


def load(task: str) -> list[dict]:
    path = index_path(task)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def save(task: str, entries: list[dict]) -> None:
    path = index_path(task)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (path.parent / "README.md").write_text(table(entries), encoding="utf-8")


def git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def parse_leaderboard_row(row: str) -> dict:
    """'9 6-Agents 0.7188 2.0305 <6 exact> 15:43 19/10/2026' -> scores (team name may contain spaces)."""
    parts = row.split()
    nums = [i for i, p in enumerate(parts) if p.replace(".", "", 1).isdigit() and "." in p]
    if len(nums) != 2 + len(EXACT):
        raise SystemExit(f"expected QWK, MAE and {len(EXACT)} exact-match values in: {row!r}")
    values = [float(parts[i]) for i in nums]
    rest = parts[nums[-1] + 1:]
    return {"rank": int(parts[0]) if parts[0].isdigit() else None,
            "team": " ".join(parts[1:nums[0]]) or None,
            "qwk": values[0], "mae": values[1], "exact": dict(zip(EXACT, values[2:])),
            "leaderboard_time": " ".join(rest) or None, "row": row.strip()}


def add(args) -> None:
    src = Path(args.file).resolve()
    data = src.read_bytes()
    preds = json.loads(data)
    sha = hashlib.sha256(data).hexdigest()
    entries = load(args.task)
    dup = next((e for e in entries if e["sha256"] == sha), None)
    if dup:
        print(f"already archived as {dup['id']} ({dup['name']}); nothing copied")
        return
    sid = f"{len(entries) + 1:02d}"
    folder = index_path(args.task).parent / f"{sid}_{datetime.now():%Y%m%d-%H%M}_{args.name}"
    folder.mkdir(parents=True)
    shutil.copy(src, folder / "predictions.json")
    for name in RUN_INFO:
        if (src.parent / name).exists():
            shutil.copy(src.parent / name, folder / name)
    totals = [p["output"]["total_score"] for p in preds]
    entries.append({
        "id": sid, "name": args.name, "note": args.note, "folder": folder.name,
        "archived_at": datetime.now().isoformat(timespec="seconds"), "source": str(src.relative_to(ROOT)) if src.is_relative_to(ROOT) else str(src),
        "sha256": sha, "git_commit": git_commit(), "n": len(preds), "mean_total": round(statistics.mean(totals), 3),
        "score": None,
    })
    save(args.task, entries)
    print(f"archived {sid} -> {folder.relative_to(ROOT)}  (n={len(preds)}, mean total {statistics.mean(totals):.2f})")
    print(f"after the leaderboard updates: python scripts/archive_submission.py score {sid} \"<leaderboard row>\"")


def score(args) -> None:
    entries = load(args.task)
    entry = next((e for e in entries if e["id"] == args.id.zfill(2)), None)
    if entry is None:
        raise SystemExit(f"no submission {args.id}; see: python scripts/archive_submission.py list")
    entry["score"] = parse_leaderboard_row(args.row)
    save(args.task, entries)
    print(table([entry]))


def table(entries: list[dict]) -> str:
    head = ["id", "name", "QWK", "MAE", *EXACT, "rank", "leaderboard", "mean total", "note"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for e in entries:
        s = e.get("score") or {}
        ex = s.get("exact", {})
        cells = [e["id"], e["name"], s.get("qwk", "—"), s.get("mae", "—"), *(ex.get(d, "—") for d in EXACT),
                 s.get("rank") or "—", s.get("leaderboard_time") or "—", e["mean_total"], e.get("note") or ""]
        lines.append("| " + " | ".join(map(str, cells)) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", default="task1")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add", help="copy a submitted predictions file into the archive")
    p.add_argument("file")
    p.add_argument("--name", required=True, help="short label, e.g. qlora_v1, api_e2_int")
    p.add_argument("--note", default="")
    p.set_defaults(func=add)
    p = sub.add_parser("score", help="record the leaderboard row of an archived submission")
    p.add_argument("id")
    p.add_argument("row", help="the leaderboard row as shown, in quotes")
    p.set_defaults(func=score)
    p = sub.add_parser("list")
    p.set_defaults(func=lambda a: print(table(load(a.task))))
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
