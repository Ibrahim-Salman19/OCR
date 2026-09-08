Title: CI/CD -- Replacing Advisory Checks With Gates That Can Actually Fail, and Adding the Missing CD Half
Status: accepted
Date: 2026-09-07

Context:
- ADR-0013 stood up the first CI pipeline, and deliberately made several checks advisory
  (`|| true`) rather than gating a brand-new pipeline on a large pre-existing findings
  backlog. That was the right call at the time, and this ADR does not reverse it -- it
  finishes it.
- What the intervening weeks showed is the cost of leaving it there. Commit 1b8ea8f
  ("CI had been silently failing on every push for 8+ days") is the same failure mode one
  level up: a signal that cannot fail, or can only fail invisibly, stops being read.
- Five checks in `.github/workflows/ci.yml` were advisory, and one of them was advisory in a
  way nobody had noticed. The job named "OCR quality regression gate" ran
  `python eval/run.py ... || true` and then a test that *skips* when no fresh scorecard exists.
  A crashed eval harness and flawless OCR quality produced the identical green checkmark.
  The gate was structurally incapable of failing.
- There was also no CD at all. `pyproject.toml` has been publish-ready at version 3.0.0, the
  `Dockerfile` builds and runs, and neither was ever published by automation.

Decision:
- **Every check either hard-gates or ratchets. None are advisory.** Where a re-measurement
  showed the baseline was already clean, the check was simply gated. Where it was not, the
  finding set was recorded in `.github/baselines/` and the gate fails only on findings absent
  from that baseline (`scripts/ci_mypy_gate.py`, `scripts/ci_pip_audit_gate.py`). Existing
  debt is parked; new debt cannot land; moving a baseline is a reviewable diff.
- **`scripts/ci_no_escape_hatches.py` runs in CI's lint job** and fails the build if any
  workflow re-introduces `|| true`, `|| :`, or `continue-on-error: true`. This is the
  property every other gate depends on, so it is itself gated rather than left to discipline.
- **A Python version matrix (3.10, 3.11, 3.12) replaces the single 3.11 job**, and
  `pyproject.toml`'s `requires-python` and classifiers were corrected to match.
- **The 17 `tests/test_playwright_*.py` files now run**, in a dedicated `e2e` job.
- **`.github/workflows/release.yml` adds the CD half**: tag-triggered PyPI publish via Trusted
  Publishing (OIDC, no stored token), GHCR image push with SBOM and signed build provenance,
  and a GitHub Release carrying the CHANGELOG section for that version.
- **Third-party actions are pinned to full commit SHAs**, with `.github/dependabot.yml`
  keeping them current so pinning does not mean going stale.

Real findings from actually running these tools instead of only authoring them:
- **`ruff check .` is clean repo-wide -- the advisory form was protecting nothing.** ADR-0013
  recorded 1170 repo-wide findings and scoped the hard gate to `blast_ocr/` accordingly. Under
  the narrowed rule set that shipped with it (`E722`, `F401`, `F811`, `F841`), the whole
  repository now passes. The `|| true` on `ruff check .` had stopped buying anything and was
  purely hiding future regressions outside `blast_ocr/`. Hard-gated.
- **`mypy blast_ocr/` reports 130 errors across 54 (file, error-code) groups.** Too many to
  hard-gate honestly, which is why it was advisory. Baselined instead. Keying on (file, code)
  rather than a total count matters: a total-count baseline passes when you fix one error and
  introduce another somewhere else. Verified by injecting a deliberate type error into a
  throwaway module -- the gate failed with the expected message, and passed again once removed.
- **`pip-audit` reports 28 known CVEs across streamlit 1.32.0, pillow 10.4.0, protobuf 4.25.9
  and starlette 0.38.6** (the last pulled in transitively via `requirements-production.txt`'s
  `fastapi<0.113.0`, itself pinned for pydantic==2.6.3 compatibility), which `|| true` had been
  hiding since ADR-0013. Every one is downstream of that ADR's deliberate stability pins, so
  none can simply be upgraded away. They are now recorded
  as explicit, reviewed risk acceptances in `.github/baselines/pip-audit.json`, and anything
  outside that set fails the build. Verified in both directions by deleting one entry from a
  copy of the baseline and confirming the gate failed on exactly that advisory.
- **The eval regression gate had a second, independent defect beyond the `|| true`.**
  `tests/test_eval_regression.py` picked "the newest scorecard in `eval/results/`" by mtime.
  That heuristic is sound on a developer machine and unsound in CI: immediately after a
  checkout every file carries the same checkout-time mtime, and
  `eval/results/99b9f142f158-dirty.json` is *committed* and does contain a valid `aggregate`
  block. So a CI run whose harness produced nothing could still find a stale scorecard to
  compare and report the OCR quality gate green. Fixed by having CI name the scorecard
  explicitly (`eval/run.py --out`) and pass it via `BLAST_OCR_EVAL_SCORECARD`, removing the
  timestamp dependency entirely. `BLAST_OCR_EVAL_REQUIRE_SCORECARD=1` additionally turns the
  skip-when-missing branch into a failure in CI, where a missing scorecard can only mean the
  step that was supposed to produce it did nothing.
- **The eval harness runs offline in about 4 minutes**, so hard-gating it costs no network
  flakiness: the 14-page corpus and gold transcriptions are committed, and
  `rapidocr_onnxruntime` bundles its ONNX models in the wheel. Verified by a full local run
  (exit 0, scorecard written, regression test passing against `baseline.json`).
- **The declared Python support window was wrong at both ends, and CI would never have caught
  it because CI only tested 3.11.**
  - `blast_ocr/ui/web_app.py` uses `@dataclass(frozen=True, slots=True)` in three places.
    `slots` is 3.10+, so on 3.9 the package fails at import. `requires-python = ">=3.9"` was
    letting pip install a build that could not run. (Measured with `vermin`, which reports the
    package minimum as exactly 3.10.)
  - `requirements.txt`'s `pandas==2.2.1` -- part of the ADR-0013 stability core -- publishes no
    cp313 wheel, so `pip install -r requirements.txt` cannot resolve on 3.13 at all. (Measured
    with `uv pip compile --python-version 3.13 --only-binary :all:`, which fails on pandas;
    3.10, 3.11 and 3.12 all resolve.)
  - Both classifiers were removed and `requires-python` raised to `>=3.10`. The matrix now
    tests exactly the window that is claimed.
- **The 17 Playwright end-to-end test files had never executed in CI, and it was invisible.**
  Not a deliberate exclusion -- the test job simply never installed `playwright`, so
  `tests/conftest.py`'s ImportError fallback set `collect_ignore_glob` and 70 tests vanished
  from the run without a skip message or a warning. They need no external service:
  `tests/playwright_fixtures.py` starts its own Streamlit and FastAPI subprocesses. A
  dedicated `e2e` job now installs Chromium and runs `-m playwright`.
- **Running those 70 tests as a group for the first time immediately found that two of them are
  order-dependent, which is why `e2e` runs but does not yet block merges.** Locally, exactly as
  the job invokes it, `pytest tests/ -m playwright` gives 68 passed / 2 failed. Neither failure
  is a regression this pipeline introduced, and neither is a broken assertion:
  `tests/test_playwright_accessibility.py` passes 4/4 when run as a file and only
  `test_landing_page_aria_landmarks` fails inside the larger run; and the FastAPI `/docs` tests
  time out waiting for the `.swagger-ui` selector, which FastAPI loads from `cdn.jsdelivr.net`
  -- a *different* one of those tests fails on each run, which is a network-timing signature
  rather than a defect. `e2e` is therefore omitted from `ci-passed`'s `needs` list with a
  comment, rather than being made advisory with `continue-on-error` (which
  `scripts/ci_no_escape_hatches.py` would reject anyway, correctly). Adding it back is a
  one-word change once the suite has run green for a stretch of pushes.
- **Two "failures" during verification were self-inflicted and worth recording as a measurement
  hazard.** `tests/test_extreme_system_stress.py::test_extreme_stress_runner_suites_end_to_end`
  failed once, and passed on a clean re-run: it had been sharing the machine with a second full
  pytest session. A test that asserts on system resource headroom cannot be measured while
  something else is consuming that headroom.
- **The measured coverage number depends on which suite you measure.** A local `pytest tests/`
  reports 81% *including* the Playwright tests, but the `test` job excludes them, so that
  figure would have been the wrong basis for `--cov-fail-under`. Measured the matching way
  (`--ignore-glob='tests/test_playwright_*.py'`) it is 7357/9069 lines = 81.1%, and the floor
  is set at 80.
- **`docker-build` built an image and never ran it.** A missing runtime apt package, a wrong
  `ENV` path, or a permissions mistake under the non-root `blast` user all build cleanly and
  fail on first start. The job now starts the container, polls the same `/_stcore/health`
  endpoint the Dockerfile's `HEALTHCHECK` uses, dumps `docker logs` on failure, and separately
  asserts the image does not run as root -- a promise `docs/SECURITY_HARDENING.md` makes and
  nothing verified.
- **CI was downloading the CUDA build of torch on every run.** `easyocr` depends on `torch`
  without pinning a CPU/GPU variant, so a plain `pip install -r requirements.txt` on Linux
  resolves multiple GB of `nvidia_*` wheels onto a runner with no GPU. The `Dockerfile` already
  works around this by installing the CPU wheel from PyTorch's own index first; CI did not.
  The shared `.github/actions/python-env` composite action now applies the same fix everywhere,
  which is also why it is a composite action rather than copy-pasted into five jobs.

Consequences:
- A green CI run now means something it did not mean before, and the number of jobs that can
  fail went from three to nine. The first runs after this change may well be red; that is the
  point, and each failure is a real finding rather than a flaky gate.
- Baselines require maintenance. `.github/baselines/*.json` should shrink over time; both gate
  scripts print an explicit "fixed since the baseline" note and the command to lock the
  improvement in.
- `release.yml`'s PyPI job requires a one-time manual registration on pypi.org that only the
  project owner can perform (Trusted Publishing, documented in the workflow header). Until it
  is done, that job fails. This was chosen over storing a `PYPI_API_TOKEN` secret precisely
  because it leaves no long-lived credential in the repository.
- `ci-passed` is a single aggregate job intended as the one required status check for branch
  protection, so adding a job to `ci.yml` never silently escapes the protected-branch rules.
  It enforces nothing on its own, though: nobody has yet set it as a required status check
  under Settings -> Branches on GitHub.com, which -- like the PyPI Trusted Publishing
  registration above -- only the repository owner can do. Until that setting is made, a red
  `ci-passed` does not block a merge.

Addendum (2026-09-08): a rollback path for the container image.
- The original version of this ADR shipped a CD pipeline that could only move forward: publish
  a new version, move `:latest` to point at it. There was no way back, which is exactly the gap
  a standard CI/CD checklist calls out under "every deployment should be reversible."
- `.github/workflows/rollback.yml` closes it for the GHCR image: a `workflow_dispatch` job that
  re-points `:latest` at an already-published version via `docker buildx imagetools create`,
  pulling no image bytes and rebuilding nothing. It verifies the target version exists before
  retagging and verifies the resulting digest matches after.
- PyPI is deliberately not covered. A published sdist/wheel filename can never be reused (the
  reason `release.yml`'s tag/version check exists at all), and there is no equivalent safe,
  automatable operation the way retagging is for a container. The correct action for a bad PyPI
  release is to yank it from https://pypi.org/manage/project/blast-ocr/releases/, which marks a
  version undesirable without deleting it or breaking anyone already pinned to it -- a manual,
  owner-only step, the same category as the two already listed above in Consequences.
