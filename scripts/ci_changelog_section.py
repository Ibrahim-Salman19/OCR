#!/usr/bin/env python3
"""Extract one version's section from CHANGELOG.md, or fail loudly.

Used twice by .github/workflows/release.yml: once in the `verify` job as a
fail-fast precondition (no changelog entry, no release), and once in the
`github-release` job to produce the release body. Sharing one tested
implementation means the check and the thing it is checking cannot disagree.

The "fail loudly" part is the point. The first version of this lived inline in
the workflow and fell back to printing `Release {version}.` when its regex
missed. Run against the real CHANGELOG.md it missed every time -- the pattern
expected a bare version in the heading, while this file uses Keep a Changelog
style, `## [2.1.0] - 2026-08-10`. Every release would have shipped an empty
body, and because the fallback was a valid string, nothing would ever have
failed to say so.

    python scripts/ci_changelog_section.py 2.1.0        # body -> stdout
    python scripts/ci_changelog_section.py 2.1.0 --check-only
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = REPO_ROOT / "CHANGELOG.md"


def extract(text: str, version: str) -> str | None:
    """Return the body under `## [<version>] ...`, up to the next `## ` heading."""
    pattern = re.compile(
        rf"^##\s*\[{re.escape(version)}\][^\n]*\n(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    if match is None:
        return None
    body = match.group(1).strip()
    return body or None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("--changelog", type=Path, default=CHANGELOG)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Exit 0/1 on presence without printing the section body.",
    )
    args = parser.parse_args()

    if not args.changelog.exists():
        print(f"::error::{args.changelog} does not exist", file=sys.stderr)
        return 1

    body = extract(args.changelog.read_text(encoding="utf-8"), args.version)
    if body is None:
        print(
            f"::error::CHANGELOG.md has no non-empty '## [{args.version}]' section. "
            f"Releases are documented, not inferred: rename the current "
            f"'## [Unreleased] - <date>' heading to '## [{args.version}] - <date>' "
            f"and describe what changed before tagging.",
            file=sys.stderr,
        )
        return 1

    if not args.check_only:
        print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
