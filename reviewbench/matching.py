"""Match predicted findings to the ground-truth findings on a PR.

A predicted finding counts as a true positive when it lands on the same file,
the same category, and within `line_tol` lines of a labelled finding. Matching is
greedy and one-to-one, so two predictions can't both claim the same real bug.
"""


def match(expected, predicted, line_tol=3):
    pred = list(predicted)
    used = set()
    tps, fns = [], []
    for e in expected:
        hit = None
        for i, p in enumerate(pred):
            if i in used:
                continue
            if (p["file"] == e["file"]
                    and p["category"] == e["category"]
                    and abs(p["line"] - e["line"]) <= line_tol):
                hit = i
                break
        if hit is not None:
            used.add(hit)
            tps.append((e, pred[hit]))
        else:
            fns.append(e)
    fps = [p for i, p in enumerate(pred) if i not in used]
    return tps, fps, fns
