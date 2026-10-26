"""Scoring: precision, recall, F1, false-positive load, and a confidence sweep."""

from .matching import match


def _pr(tp, fp, fn):
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def review_all(cases, reviewer):
    """Review each case exactly once.

    Returns a list of (case, findings) pairs so that downstream scoring can
    re-filter by confidence threshold without re-invoking the reviewer. This
    keeps the sweep deterministic for non-deterministic reviewers (e.g. an LLM)
    and avoids redundant work.
    """
    return [(c, reviewer.review(c)) for c in cases]


def score_predictions(reviewed, threshold=0.0, line_tol=3):
    """Score pre-reviewed findings across cases at one confidence gate.

    ``reviewed`` is a list of (case, findings) pairs as produced by
    :func:`review_all`.

    Returns (aggregate_dict, per_case_list).
    """
    per = []
    TP = FP = FN = 0
    clean_fp = 0
    clean_n = 0
    for c, findings in reviewed:
        preds = [p for p in findings if p["confidence"] >= threshold]
        expected = c.get("expected_findings", [])
        tps, fps, fns = match(expected, preds, line_tol)
        TP += len(tps)
        FP += len(fps)
        FN += len(fns)
        p, r, f = _pr(len(tps), len(fps), len(fns))
        if not expected:
            clean_n += 1
            clean_fp += len(preds)
        per.append({
            "id": c["id"],
            "title": c.get("title", ""),
            "tp": len(tps), "fp": len(fps), "fn": len(fns),
            "precision": p, "recall": r, "f1": f,
            "false_positives": fps,
        })
    P, R, F = _pr(TP, FP, FN)
    agg = {
        "tp": TP, "fp": FP, "fn": FN,
        "precision": P, "recall": R, "f1": F,
        "fp_per_pr": FP / len(reviewed) if reviewed else 0.0,
        "clean_pr_noise": clean_fp / clean_n if clean_n else 0.0,
        "n_cases": len(reviewed),
    }
    return agg, per


def score_cases(cases, reviewer, threshold=0.0, line_tol=3):
    """Convenience: review each case once and score at one confidence gate.

    Equivalent to ``score_predictions(review_all(cases, reviewer), threshold,
    line_tol)``. Kept for callers that don't need to reuse predictions across
    multiple gates.
    """
    return score_predictions(review_all(cases, reviewer), threshold, line_tol)


def sweep(reviewed, thresholds, line_tol=3):
    """Score across a range of confidence gates. Returns a list of rows.

    Findings are reviewed once up front (via :func:`review_all`) and re-filtered
    by threshold here, so non-deterministic reviewers are scored consistently
    across gates and no redundant reviews are performed.
    """
    rows = []
    for t in thresholds:
        agg, _ = score_predictions(reviewed, t, line_tol)
        rows.append({
            "threshold": round(t, 2),
            "precision": agg["precision"],
            "recall": agg["recall"],
            "f1": agg["f1"],
            "fp": agg["fp"],
            "fp_per_pr": agg["fp_per_pr"],
        })
    return rows


def best_row(sweep_rows):
    """Pick the gate with the highest F1 (ties broken toward higher recall)."""
    return max(sweep_rows, key=lambda r: (round(r["f1"], 6), r["recall"]))
