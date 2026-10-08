"""Task 1 evaluator: QWK on total score (primary), MAE, exact-match per dimension, submission format check."""
from __future__ import annotations

from collections import defaultdict

from src.data.loader import DIM_MAX, DIMENSIONS
from src.evaluation.metrics import mean_absolute_error, quadratic_weighted_kappa


def evaluate(gold: dict[str, dict], pred: dict[str, dict], group_of: dict[str, str] | None = None) -> dict:
    """gold/pred: sample_id -> {"rubric": {...}, "total_score": int}. Only ids present in gold count.

    Missing predictions are scored as all-zero (and counted in `n_missing`), mirroring a leaderboard.
    """
    ids = sorted(gold)
    zero = {"rubric": {d: 0 for d in DIMENSIONS}, "total_score": 0}
    n_missing = sum(1 for i in ids if i not in pred)
    P = {i: pred.get(i, zero) for i in ids}
    yt = [gold[i]["total_score"] for i in ids]
    yp = [P[i]["total_score"] for i in ids]
    res = {
        "n": len(ids),
        "n_missing": n_missing,
        "qwk": quadratic_weighted_kappa(yt, yp),
        "mae": mean_absolute_error(yt, yp),
        "exact_total": sum(a == b for a, b in zip(yt, yp)) / len(ids) if ids else float("nan"),
        "within1_total": sum(abs(a - b) <= 1 for a, b in zip(yt, yp)) / len(ids) if ids else float("nan"),
        "bias_total": sum(b - a for a, b in zip(yt, yp)) / len(ids) if ids else float("nan"),
        "exact_match": {},
        "mae_dim": {},
        "bias_dim": {},
    }
    for d in DIMENSIONS:
        gt = [gold[i]["rubric"][d] for i in ids]
        pd_ = [P[i]["rubric"][d] for i in ids]
        res["exact_match"][d] = sum(a == b for a, b in zip(gt, pd_)) / len(ids)
        res["mae_dim"][d] = mean_absolute_error(gt, pd_)
        res["bias_dim"][d] = sum(b - a for a, b in zip(gt, pd_)) / len(ids)
    res["exact_match_mean"] = sum(res["exact_match"].values()) / len(DIMENSIONS)
    res["exact_match_all_dims"] = sum(
        all(gold[i]["rubric"][d] == P[i]["rubric"][d] for d in DIMENSIONS) for i in ids
    ) / len(ids)

    if group_of:
        groups: dict[str, list[str]] = defaultdict(list)
        for i in ids:
            groups[group_of.get(i, "?")].append(i)
        res["by_group"] = {}
        for g, gids in sorted(groups.items()):
            gt = [gold[i]["total_score"] for i in gids]
            gp = [P[i]["total_score"] for i in gids]
            res["by_group"][g] = {
                "n": len(gids),
                "qwk": quadratic_weighted_kappa(gt, gp),
                "mae": mean_absolute_error(gt, gp),
                "exact_total": sum(a == b for a, b in zip(gt, gp)) / len(gids),
                "exact_match": {
                    d: sum(gold[i]["rubric"][d] == P[i]["rubric"][d] for i in gids) / len(gids)
                    for d in DIMENSIONS
                },
            }
    return res


def format_metrics(m: dict) -> str:
    lines = [
        f"n={m['n']}  QWK={m['qwk']:.4f}  MAE={m['mae']:.3f}  exact_total={m['exact_total']:.3f}  "
        f"within1={m['within1_total']:.3f}  bias={m['bias_total']:+.2f}",
        "exact-match: " + "  ".join(f"{d}={v:.2f}" for d, v in m["exact_match"].items())
        + f"  | mean={m['exact_match_mean']:.3f} all-dims={m['exact_match_all_dims']:.3f}",
    ]
    for g, gm in (m.get("by_group") or {}).items():
        lines.append(f"  [{g}] n={gm['n']} QWK={gm['qwk']:.4f} MAE={gm['mae']:.3f} exact={gm['exact_total']:.3f}")
    return "\n".join(lines)


def validate_predictions(preds, expected_ids=None) -> list[str]:
    """Check a Task 1 predictions.json payload; returns a list of errors (empty = valid)."""
    errs = []
    if not isinstance(preds, list):
        return ["top-level must be a list"]
    seen = set()
    for i, p in enumerate(preds):
        sid = p.get("sample_id") if isinstance(p, dict) else None
        if not sid:
            errs.append(f"[{i}] missing sample_id")
            continue
        if sid in seen:
            errs.append(f"{sid}: duplicate")
        seen.add(sid)
        out = p.get("output") or {}
        rub = out.get("rubric")
        if not isinstance(rub, dict) or set(rub) != set(DIMENSIONS):
            errs.append(f"{sid}: rubric must have exactly {DIMENSIONS}")
            continue
        for d in DIMENSIONS:
            if not isinstance(rub[d], int) or not 0 <= rub[d] <= DIM_MAX[d]:
                errs.append(f"{sid}: {d}={rub[d]!r} out of range 0..{DIM_MAX[d]}")
        if out.get("total_score") != sum(rub[d] for d in DIMENSIONS if isinstance(rub[d], int)):
            errs.append(f"{sid}: total_score != sum(rubric)")
    if expected_ids is not None:
        missing = set(expected_ids) - seen
        if missing:
            errs.append(f"missing {len(missing)} sample_ids, e.g. {sorted(missing)[:5]}")
    return errs
