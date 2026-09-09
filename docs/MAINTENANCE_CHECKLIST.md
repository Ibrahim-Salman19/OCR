# 🩺 Maintenance Checklist

A periodic health check for this project's live deployment, CI, and growth. Run through
this end to end every couple of months, or any time the live app misbehaves and you're not
sure why. Each section says what to check, how to check it, and what "healthy" looks like.
See `docs/adr/0015-scc-outage-triple-root-cause-and-maintenance.md` for the incident that
made this checklist necessary -- read it once before your first review so the "why" behind
each item isn't a mystery.

## 1. Is the live app actually working?

Do not trust the landing page loading. It rendered fine through the *entire* September 2026
outage documented in ADR-0015 while every real upload failed behind it. The only real test:

1. Open https://ocr-book.streamlit.app
2. Click "ENTER MISSION CONTROL"
3. Upload any real PDF or image
4. Click "EXECUTE OCR ENGINE"
5. Confirm it says "MISSION ACCOMPLISHED" with real extracted text, not "MISSION FAILED"

If it fails, check "Manage app" -> the terminal log for a Python traceback before guessing.

## 2. Has Streamlit Community Cloud's Python version silently drifted?

This is the single most likely thing to break next, and it fails silently: SCC's dashboard
Python-version dropdown can override this repo's `runtime.txt` without warning
(https://github.com/streamlit/streamlit/issues/15326, open/unresolved as of this writing).

1. On share.streamlit.io, open this app's Settings.
2. Check the **Python version** field.
3. It should be **3.11** (matches `runtime.txt` and what CI actually tests: 3.10/3.11/3.12).
   If it has drifted to something else -- especially a version newer than what CI tests --
   change it back, save, and reboot, then redo the check in section 1.

## 3. Is CI actually green?

```
gh run list --limit 5
gh run view <run-id>
```

All of these must pass: Lint, Security, Type check, CodeQL, Tests (3.10/3.11/3.12), Container
build + smoke test, OCR quality regression gate, and the `CI passed` gate job itself.

Two known, pre-existing flakes are **not** regressions if you see them alone:
- `tests/test_extreme_system_stress.py::test_extreme_stress_runner_suites_end_to_end` -- a
  resource-contention-sensitive memory measurement, documented in
  `docs/adr/0014-ci-cd-gates-that-can-actually-fail.md`.
- `tests/test_playwright_responsive_and_docs.py::test_fastapi_redoc_ui` -- a CDN-timing flake
  in the (non-gating) `e2e` job.

If either of those is failing *along with something else*, or a *different* test is failing,
treat it as real and investigate.

## 4. Dependency and security housekeeping

- `pip-audit` and `mypy` run as ratchet gates in CI (`.github/baselines/`) -- they only fail on
  *new* findings, so existing debt doesn't silently grow. Check whether it's worth spending
  time shrinking either baseline.
- Check whether `rapidocr_onnxruntime` has shipped a release supporting a newer Python yet
  (`pip index versions rapidocr_onnxruntime`), since that's the actual blocker keeping this
  project off Python 3.13/3.14, not a preference.
- Skim Dependabot PRs (`.github/dependabot.yml` keeps pinned Action SHAs current) rather than
  letting them pile up unreviewed.

## 5. Is the app growing?

Baseline recorded 2026-09-10, the day this checklist was written (after the LinkedIn launch
post and the outage above):

| Metric | Value | How to check again |
|---|---|---|
| GitHub stars | 0 | `gh repo view Ibrahim-Salman19/OCR --json stargazerCount` |
| GitHub forks | 0 | `gh repo view Ibrahim-Salman19/OCR --json forkCount` |
| Repo views (last 14d) | 12 (4 unique) | `gh api repos/Ibrahim-Salman19/OCR/traffic/views` |
| Repo clones (last 14d) | 336 (61 unique) | `gh api repos/Ibrahim-Salman19/OCR/traffic/clones` |

Notes on reading these:
- GitHub's traffic API only retains 14 days of history, so you cannot look back further than
  that in one query -- record the numbers each time you check if you want a real trend line.
- Clone counts include CI/automation checkouts, not just human interest; a spike lines up with
  active development days, not necessarily real adoption. Uniques matter more than raw counts.
- These are proxy signals, not the real metric. The things that would actually confirm growth
  and aren't checkable from here:
  - Streamlit Community Cloud's own app viewer/visitor count, visible in "Manage app".
  - LinkedIn post engagement (views, likes, comments, click-throughs) on the launch post in
    `marketing/linkedin_launch.md`, visible in LinkedIn's own analytics on the published post.
  - Any direct signups/usage if this app ever gains its own accounts or analytics.

Update the table above with fresh numbers every time you run this checklist, so growth (or
its absence) is visible over time instead of re-derived from scratch each visit.

## A note on scheduling this

I (Claude) can't reliably promise to come back and run this automatically. Scheduled/cron
tasks in this environment are session-scoped: they're lost if the session ends, and recurring
ones auto-expire after 7 days regardless. Neither survives a two-month gap. The practical
options are: set your own calendar reminder to ask a future Claude Code session to "run
docs/MAINTENANCE_CHECKLIST.md," or just run it yourself using the commands above.
