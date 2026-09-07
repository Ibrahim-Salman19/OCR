#!/usr/bin/env python3
"""Fail if a CI workflow re-introduces a `|| true` (or `continue-on-error`) gate.

This repository has already lived through the failure this guards against:
commit 1b8ea8f, "CI had been silently failing on every push for 8+ days".
The mechanism is always the same and always reasonable in the moment -- a check
gets noisy, someone appends `|| true` to unblock a release, and from then on
the job is green no matter what the tool reports. The check still runs, still
prints, still costs a runner minute, and can no longer fail. A decoration.

.github/workflows/ci.yml carried five of these. They are gone; where a check
could not honestly be hard-gated, it is ratcheted against a committed baseline
instead (scripts/ci_mypy_gate.py, scripts/ci_pip_audit_gate.py), so existing
debt is parked without also parking everything that comes later.

This script exists so that stays true. It deliberately ignores comment lines,
because the workflows explain at length *why* the escape hatches were removed
and that prose contains the literal string.

    python scripts/ci_no_escape_hatches.py
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

PATTERNS = [
    (
        re.compile(r"\|\|\s*true\b"),
        "`|| true` swallows the exit status, so the step can never fail.",
    ),
    (
        re.compile(r"\|\|\s*:\s*$"),
        "`|| :` is `|| true` spelled differently.",
    ),
    (
        re.compile(r"^\s*continue-on-error:\s*true\b"),
        "`continue-on-error: true` makes the whole step advisory.",
    ),
]

# Steps that are legitimately advisory, keyed by the workflow-relative reason.
# Each entry needs a justification, so adding one is a visible decision rather
# than a quiet re-opening of the hole.
ALLOWLIST = {
    # Uploading SARIF is a reporting side-effect, not a gate: GitHub rejects
    # the upload on forks and on repos without Advanced Security, and a failed
    # *upload* must not mask the bandit run that already passed or failed on
    # its own line immediately above.
    ("ci.yml", "Upload bandit SARIF"),
}


def is_comment(line: str) -> bool:
    return line.lstrip().startswith("#")


def main() -> int:
    if not WORKFLOW_DIR.is_dir():
        print(f"No workflow directory at {WORKFLOW_DIR}")
        return 0

    violations: list[str] = []
    for path in sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml")):
        current_step = ""
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            name_match = re.match(r"^\s*-?\s*name:\s*(.+?)\s*$", raw)
            if name_match:
                current_step = name_match.group(1)
            if is_comment(raw):
                continue
            if (path.name, current_step) in ALLOWLIST:
                continue
            for pattern, reason in PATTERNS:
                if pattern.search(raw):
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}:{lineno}: {reason}\n"
                        f"    step: {current_step or '(unnamed)'}\n"
                        f"    {raw.strip()}"
                    )
                    break

    if violations:
        print("CI escape hatches found -- these make a job green regardless of the result:\n")
        for violation in violations:
            print(violation)
        print(
            "\nIf the check genuinely cannot be hard-gated yet, ratchet it against a\n"
            "committed baseline the way scripts/ci_mypy_gate.py and\n"
            "scripts/ci_pip_audit_gate.py do, so existing findings are parked but new\n"
            "ones still fail. If a step is legitimately advisory (a reporting\n"
            "side-effect, not a gate), add it to ALLOWLIST in this file with a reason."
        )
        return 1

    print("No CI escape hatches: every step in .github/workflows/ can fail its job.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
