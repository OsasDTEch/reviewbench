"""Render results to JSON and a small self-contained HTML page."""

import json


def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def _pct(x):
    return f"{x * 100:.0f}%"


def _headline(baseline, best):
    """One sentence a founder can read in five seconds. Baseline is gate 0.0."""
    if best["threshold"] <= 0.0:
        return ("At gate 0.00 the reviewer runs at "
                f"{_pct(baseline['precision'])} precision / {_pct(baseline['recall'])} recall.")
    dp = best["precision"] - baseline["precision"]
    dr = baseline["recall"] - best["recall"]
    lost = "no recall lost" if dr <= 1e-9 else f"{_pct(dr)} recall lost"
    return (f"A confidence gate at {best['threshold']:.2f} lifts precision "
            f"{_pct(baseline['precision'])} → {_pct(best['precision'])} "
            f"(+{_pct(dp)}) with {lost} — that is false-positive fatigue, measured.")


def write_html(path, reviewer_name, baseline, per_case, sweep_rows, best):
    H = []
    H.append("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
    H.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    H.append("<title>reviewbench report</title><style>")
    H.append("""
:root{--bg:#0f1117;--card:#171a22;--line:#262a35;--ink:#e6e8ee;--mute:#9aa0ad;--good:#1f8a70;--bad:#d4634a;--accent:#48b89c;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;padding:32px 20px}
.wrap{max-width:860px;margin:0 auto}
h1{font-size:22px;margin:0 0 2px}.sub{color:var(--mute);margin:0 0 22px;font-size:13px}
.headline{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:10px;padding:16px 18px;margin-bottom:22px;font-size:16px}
.grid{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:24px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;min-width:120px;flex:1}
.stat .n{font-size:24px;font-weight:700}.stat .l{color:var(--mute);font-size:12px;margin-top:2px}
h2{font-size:14px;text-transform:uppercase;letter-spacing:.06em;color:var(--mute);margin:26px 0 10px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);font-size:13px}
th{color:var(--mute);font-weight:600}tr:last-child td{border-bottom:none}
.best{background:rgba(72,184,156,.12)}
.good{color:var(--good)}.bad{color:var(--bad)}.mono{font-variant-numeric:tabular-nums}
.foot{color:var(--mute);font-size:12px;margin-top:26px}
.bar{height:6px;background:var(--line);border-radius:3px;overflow:hidden;margin-top:4px}
.bar>span{display:block;height:100%;background:var(--accent)}
</style></head><body><div class='wrap'>""")

    H.append("<h1>reviewbench &mdash; review-finding scorecard</h1>")
    H.append(f"<p class='sub'>reviewer: <b>{reviewer_name}</b> &middot; {baseline['n_cases']} pull requests &middot; scored on outcomes, not transcript text</p>")

    H.append(f"<div class='headline'>{_headline(baseline, best)}</div>")

    def stat(n, label, cls=""):
        return f"<div class='stat'><div class='n {cls}'>{n}</div><div class='l'>{label}</div></div>"

    H.append("<div class='grid'>")
    H.append(stat(_pct(baseline["precision"]), "precision (gate 0.0)"))
    H.append(stat(_pct(baseline["recall"]), "recall (gate 0.0)"))
    H.append(stat(f"{baseline['fp_per_pr']:.2f}", "false positives / PR", "bad"))
    H.append(stat(f"{baseline['clean_pr_noise']:.2f}", "flags on clean PRs", "bad"))
    H.append("</div>")

    H.append("<h2>Confidence-gate sweep</h2>")
    H.append("<table><tr><th>gate</th><th>precision</th><th>recall</th><th>F1</th><th>false positives</th></tr>")
    for r in sweep_rows:
        cls = " class='best'" if r["threshold"] == best["threshold"] else ""
        H.append(
            f"<tr{cls}><td class='mono'>{r['threshold']:.2f}</td>"
            f"<td class='mono'>{_pct(r['precision'])}</td>"
            f"<td class='mono'>{_pct(r['recall'])}</td>"
            f"<td class='mono'>{r['f1']:.2f}</td>"
            f"<td class='mono'>{r['fp']}</td></tr>"
        )
    H.append("</table>")

    H.append("<h2>Per-pull-request</h2>")
    H.append("<table><tr><th>PR</th><th>TP</th><th>FP</th><th>FN</th><th>precision</th><th>recall</th></tr>")
    for c in per_case:
        pcls = "good" if c["precision"] >= 0.99 else ("bad" if c["precision"] < 0.6 else "")
        rcls = "good" if c["recall"] >= 0.99 else ("bad" if c["recall"] < 0.6 else "")
        H.append(
            f"<tr><td>{c['id']} &middot; <span style='color:var(--mute)'>{c['title']}</span></td>"
            f"<td class='mono'>{c['tp']}</td>"
            f"<td class='mono'>{c['fp']}</td>"
            f"<td class='mono'>{c['fn']}</td>"
            f"<td class='mono {pcls}'>{_pct(c['precision'])}</td>"
            f"<td class='mono {rcls}'>{_pct(c['recall'])}</td></tr>"
        )
    H.append("</table>")

    H.append("<p class='foot'>reviewbench &middot; scores findings on whether they match the issues that actually mattered. "
             "Swap in your own reviewer or an LLM and compare on the same cases.</p>")
    H.append("</div></body></html>")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(H))
