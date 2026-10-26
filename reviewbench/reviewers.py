"""Reviewers: the thing under test.

A Reviewer takes a PR case and returns a list of findings, each with a
confidence in [0, 1]. reviewbench scores whatever a reviewer emits — so you can
point it at this bundled PatternReviewer, at your own detector, or at an LLM.

The bundled PatternReviewer is deliberately imperfect: it catches real security
issues at high confidence AND raises low-value noise (debug prints, TODOs) at
low confidence. That is the point — it gives the harness real false positives to
measure, and makes the confidence-gate sweep tell a true story.
"""

import os
import re

from .diffparse import parse_diff


def _f(al, category, severity, confidence, summary):
    return {
        "file": al.file,
        "line": al.line,
        "category": category,
        "severity": severity,
        "confidence": confidence,
        "summary": summary,
    }


class Reviewer:
    name = "base"

    def review(self, case):  # pragma: no cover - interface
        raise NotImplementedError


class PatternReviewer(Reviewer):
    """A fast, deterministic reviewer. No key, no network, always runs."""

    name = "pattern-v1"

    _SQL_KW = re.compile(r"\b(select|insert|update|delete)\b", re.I)
    _SECRET = re.compile(
        r"(password|secret|api[_-]?key|token)\s*=\s*['\"][^'\"]+['\"]", re.I
    )
    _EVAL = re.compile(r"\b(eval|exec)\s*\(", re.I)

    def review(self, case):
        findings = []
        for al in parse_diff(case["diff"]):
            t = al.text
            low = t.lower()

            # --- high-signal rules (the findings that matter) ---
            dynamic = ('f"' in low or "f'" in low or "%" in t
                       or " + " in t or ".format(" in low)
            if self._SQL_KW.search(low) and dynamic:
                findings.append(_f(al, "sql-injection", "high", 0.92,
                                   "User input appears formatted/concatenated into a SQL statement"))
                continue
            if self._EVAL.search(low):
                findings.append(_f(al, "code-injection", "high", 0.88,
                                   "Dynamic eval/exec on request-influenced data"))
                continue
            if self._SECRET.search(low):
                findings.append(_f(al, "hardcoded-secret", "high", 0.82,
                                   "Hardcoded credential/secret committed to source"))
                continue

            # --- low-signal rules (where false-positive fatigue comes from) ---
            if "print(" in low:
                findings.append(_f(al, "debug-print", "low", 0.30,
                                   "Debug print statement left in code"))
                continue
            if "todo" in low:
                findings.append(_f(al, "todo", "low", 0.25,
                                   "TODO comment added"))
                continue
        return findings


class LLMReviewer(Reviewer):
    """Optional: route the same cases through an LLM (Ollama Cloud).

    Off by default. Set OLLAMA_API_KEY to enable. The point of the harness is
    that you can drop ANY reviewer in here and get a comparable score — this is
    how you'd A/B a prompt change or a new model against pattern-v1.
    """

    name = "llm"

    def __init__(self, model=None):
        self.model = model or os.getenv("OLLAMA_MODEL", "gpt-oss:120b")
        self.key = os.getenv("OLLAMA_API_KEY")

    def review(self, case):
        if not self.key:
            raise RuntimeError(
                "LLMReviewer needs OLLAMA_API_KEY. Run with the default "
                "pattern reviewer, or set the key to enable this path."
            )
        import json
        import urllib.request

        prompt = (
            "You are a code-review detector. Given a unified diff, return ONLY "
            "a JSON array of findings. Each finding: "
            '{"file","line","category","severity","confidence","summary"}. '
            "confidence is 0..1. Flag only real issues; do not invent. "
            "If nothing is wrong, return [].\n\nDIFF:\n" + case["diff"]
        )
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
        }).encode()
        req = urllib.request.Request(
            "https://ollama.com/api/chat",
            data=body,
            headers={"Authorization": f"Bearer {self.key}",
                     "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        content = data.get("message", {}).get("content", "[]")
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                parsed = parsed.get("findings", [])
            out = []
            for p in parsed:
                out.append({
                    "file": p.get("file", "?"),
                    "line": int(p.get("line", 0) or 0),
                    "category": p.get("category", "other"),
                    "severity": p.get("severity", "medium"),
                    "confidence": float(p.get("confidence", 0.5) or 0.5),
                    "summary": p.get("summary", ""),
                })
            return out
        except (ValueError, TypeError):
            return []


REVIEWERS = {"pattern-v1": PatternReviewer, "llm": LLMReviewer}
