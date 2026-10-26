# reviewbench

**Score a code-review bot on outcomes, not transcripts.**

A PR-review engine lives or dies on whether developers trust its findings. The
fastest way to lose that trust is a confident flag that isn't real — once a
reviewer mutes the bot, every real finding after it goes unseen. So the number
that matters isn't *how many* issues a detector raises, it's *how few of them are
noise* — and whether you can move that number on purpose.

`reviewbench` measures exactly that. Give it a set of pull requests labelled with
the findings that actually mattered, point it at any reviewer, and it reports
precision, recall, false-positive load per PR, and — the useful part — sweeps a
confidence gate to show where you cut false positives **without losing real
bugs**.

## Run it (no install, no key)

```
python -m reviewbench run --data data/cases --out out
```

Open `out/report.html`. That's it — pure standard library, always runs.

## What you'll see on the bundled cases

Five PRs: a SQL-injection, a hardcoded secret + `eval`, a mixed PR with a real
bug buried in noise, one genuinely clean PR, and one PR with a real
command-injection the reviewer **doesn't** catch. The bundled `pattern-v1`
reviewer catches most real issues at high confidence but also raises low-value
noise (debug prints, TODOs) at low confidence — on purpose, so there's something
real to measure.

Two things the sweep tells you, and both matter:

- **What tuning *can* fix:** a confidence gate at **0.40** takes precision from
  **40% → 100%** with **no recall lost** — every false positive gone, nothing
  real dropped. That's false-positive fatigue, removed with one number.
- **What tuning *can't* fix:** recall sits at **80%** and no gate moves it,
  because the reviewer has no rule for command-injection and misses that bug
  entirely. That's a detector gap, not a threshold problem — and the harness
  tells the two apart, so you don't "fix" a missing rule by lowering a gate and
  drowning in noise.

## Score your own reviewer

A reviewer is anything that takes a PR case and returns findings with a
confidence. Implement the `Reviewer` interface in `reviewbench/reviewers.py`
(there's an `LLMReviewer` stub that routes the same cases through Ollama Cloud),
drop it in `REVIEWERS`, and run with `--reviewer <name>`. Now you can A/B a prompt
change, a model swap, or a new detector against a baseline on the same cases and
see whether it actually got better or just got louder.

## Case format

Each file in `data/cases/` is one PR:

```json
{
  "id": "pr-001",
  "title": "Add user lookup endpoint",
  "diff": "<unified diff>",
  "expected_findings": [
    {"file": "api/users.py", "line": 13, "category": "sql-injection", "severity": "high", "summary": "..."}
  ]
}
```

A clean PR has `"expected_findings": []`. A predicted finding is a true positive
when it matches a labelled finding's file + category within a few lines.

## Layout

```
reviewbench/
  diffparse.py   unified-diff -> added lines with new-file line numbers
  reviewers.py   Reviewer interface, pattern-v1, optional LLMReviewer
  matching.py    predicted findings <-> ground-truth findings
  metrics.py     precision / recall / F1 / FP load / confidence sweep
  report.py      JSON + a self-contained HTML scorecard
  cli.py         python -m reviewbench run
data/cases/      sample labelled PRs
```

Built by Wisdom Omons.
