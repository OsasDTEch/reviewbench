"""Command line: load PR cases, score a reviewer, write the report."""

import argparse
import glob
import json
import os
import sys

from .metrics import review_all, score_predictions, sweep, best_row
from .report import write_json, write_html, _headline
from .reviewers import REVIEWERS


def load_cases(data_dir):
    cases = []
    for path in sorted(glob.glob(os.path.join(data_dir, "*.json"))):
        with open(path) as fh:
            cases.append(json.load(fh))
    if not cases:
        sys.exit(f"no PR cases found in {data_dir}")
    return cases


def _pct(x):
    return f"{x * 100:.0f}%"


def run(args):
    cases = load_cases(args.data)
    reviewer = REVIEWERS[args.reviewer]()

    # Review each case once; the baseline and the sweep both reuse these
    # findings so non-deterministic reviewers stay consistent across gates
    # and no redundant reviews run.
    reviewed = review_all(cases, reviewer)

    baseline, per = score_predictions(reviewed, threshold=0.0, line_tol=args.line_tol)
    thresholds = [i / 10 for i in range(0, 10)]
    sweep_rows = sweep(reviewed, thresholds, line_tol=args.line_tol)
    best = best_row(sweep_rows)

    # --- console summary ---
    print(f"\nreviewbench  ·  reviewer={reviewer.name}  ·  {len(cases)} PRs\n")
    print(f"  at gate 0.00 : precision {_pct(baseline['precision'])}  "
          f"recall {_pct(baseline['recall'])}  "
          f"F1 {baseline['f1']:.2f}  "
          f"FP/PR {baseline['fp_per_pr']:.2f}  "
          f"clean-PR noise {baseline['clean_pr_noise']:.2f}")
    print("\n  confidence-gate sweep")
    print("  gate   prec   rec    F1    FP")
    for r in sweep_rows:
        mark = "  <-- best F1" if r["threshold"] == best["threshold"] else ""
        print(f"  {r['threshold']:.2f}   {_pct(r['precision']):>4}  "
              f"{_pct(r['recall']):>4}  {r['f1']:.2f}  {r['fp']:>3}{mark}")
    print("\n  " + _headline(baseline, best) + "\n")

    # --- files ---
    os.makedirs(args.out, exist_ok=True)
    payload = {
        "reviewer": reviewer.name,
        "baseline": baseline,
        "sweep": sweep_rows,
        "best_gate": best,
        "per_case": per,
    }
    write_json(os.path.join(args.out, "report.json"), payload)
    write_html(os.path.join(args.out, "report.html"),
               reviewer.name, baseline, per, sweep_rows, best)
    print(f"  wrote {os.path.join(args.out, 'report.json')}")
    print(f"  wrote {os.path.join(args.out, 'report.html')}\n")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="reviewbench",
                                 description="Score a code-review bot on outcomes.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="score a reviewer over a case set")
    r.add_argument("--data", default="data/cases", help="dir of PR case json files")
    r.add_argument("--out", default="out", help="output dir for report files")
    r.add_argument("--reviewer", default="pattern-v1", choices=list(REVIEWERS),
                   help="which reviewer to score")
    r.add_argument("--line-tol", type=int, default=3,
                   help="line tolerance when matching a finding to a label")
    r.set_defaults(func=run)
    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
