Title: Streamlit Community Cloud Outage -- Three Stacked Root Causes, and the Fixes/Trade-offs Left Behind
Status: accepted
Date: 2026-09-10

Context:
- ocr-book.streamlit.app started showing Streamlit's generic "Oh no. Error running app."
  crash page to every visitor. That page is the uncaught-exception page, not the "This app has
  gone over its resource limits" message SCC shows for OOM -- a distinction that mattered,
  because the first fix attempt assumed a resource problem without ever seeing a real
  traceback, and was wrong.
- Diagnosis took three passes because there were genuinely three independent, stacked
  problems, and fixing one only exposed the next:
  1. **Wrong entrypoint.** The Dockerfile's `ENTRYPOINT` (and SCC's own launch mechanism) ran
     `blast_ocr/ui/web_app.py` directly instead of the repo-root `streamlit_app.py` that
     already existed specifically to fix this. Streamlit's own bootstrap
     (`streamlit/web/bootstrap.py:_fix_sys_path`) only adds the *entrypoint script's own
     directory* to `sys.path`, not the repo root, so `from blast_ocr...` inside `web_app.py`
     can never resolve when it's the entrypoint itself. This predated this incident (commit
     e836eea9) and was a real, if latent, bug. Fixed by pointing `ENTRYPOINT` at
     `streamlit_app.py` (commit 36b4ede). This was never the cause of the live crash --
     confirmed only after fixing it and watching the crash persist unchanged.
  2. **A genuine, ongoing SCC platform outage**, unrelated to this repo: the base image's apt
     sources include an expired `bullseye-security` Release file, so any app with a
     `packages.txt` fails during dependency installation, before Python ever runs. Confirmed
     via Streamlit's own staff on their forum ("the team is aware... a fix is in flight") and
     multiple independent same-day reports. `packages.txt` was removed to route around it
     (commit 5e0815b), which also required stubbing out `opencv-python` (see Decision) since
     `libgl1` turned out to be load-bearing for the default OCR engine, not just a "some codec
     paths" nicety as an earlier Dockerfile comment speculated.
  3. **Python 3.14 on SCC's dashboard**, which silently overrides this repo's `runtime.txt`
     (`python-3.11`) due to a currently-open upstream bug
     (https://github.com/streamlit/streamlit/issues/15326 -- widely reported by other users
     hitting the same silent-override behavior with 3.13/3.14, not unique to this app). A
     clean `pip install -r requirements.txt` on Python 3.14 cannot resolve
     `rapidocr_onnxruntime` at all -- no version on PyPI supports it. The live app had been
     running on a stale, partially-installed venv left over from before the dashboard drifted
     onto 3.14. This was the layer underneath everything else, and no code-level fix could
     have addressed it; it required manually reselecting Python 3.11 in SCC's Advanced
     Settings dropdown.
- Verification methodology was itself a repeated source of false confidence during this
  incident, worth recording so it isn't relearned:
  - `curl`/HTTP-status-only checks (including CI's own docker smoke test, which only polls
    `/_stcore/health`) prove the Streamlit *server* is up, not that the app's script ran
    without raising -- Streamlit's actual page content is client-rendered over a WebSocket, so
    a plain `curl http://host:8501/` returns the same static SPA shell whether the app is
    healthy or crashed. Every real check in this incident that mattered used a headless
    browser (Playwright) reading actual rendered text, through the real upload -> OCR ->
    extracted-text path, not just the landing page (which rendered fine throughout the entire
    outage and told us nothing).
  - Docker-based reproduction is only valid if it matches production on the *specific*
    dimension being tested. An early verification pass "proved" the app booted under a memory
    cap, but used a Docker image that still had `requirements-easyocr.txt` installed --
    meaning it could never have caught a failure caused by that file being absent, which is
    exactly the change under test.

Decision:
- Keep `streamlit_app.py` as the one true entrypoint everywhere (Dockerfile `ENTRYPOINT`, and
  SCC's dashboard "Main file path", which was independently already correct there).
- Keep `packages.txt` removed rather than restoring it once SCC's mirror is eventually fixed,
  since dropping it forced two real improvements that are worth keeping on their own merits:
  - `vendor/opencv-python-stub/`: a local, empty package registered as `opencv-python`
    version `99.99.99` depending only on `opencv-python-headless`, referenced via
    `--find-links vendor/opencv-python-stub` in requirements.txt. `rapidocr_onnxruntime` hard-
    depends on plain `opencv-python` (needs `libGL`); since it and `opencv-python-headless`
    install to the same `cv2/` path with no reliable way to control which one wins via
    requirements.txt ordering, the fake higher-version release wins dependency resolution
    instead, and `opencv-python-headless` ends up the only real implementation installed.
    Confirmed this matches current OpenCV community guidance (never let both variants
    coexist); the more "native" fix would be a `uv` `[tool.uv] override-dependencies` block,
    but SCC's uv usage is pip-`-r requirements.txt`-compatible only and does not consult a
    project's `pyproject.toml`, so that mechanism can't be relied on there.
  - `blast_ocr/pipeline.py`'s `process_pdf()` (the method the web UI's "EXECUTE OCR ENGINE"
    button actually calls) got a `pypdfium2`-first page-count/render path
    (`_pdf_page_count`/`_render_pdf_pages`), matching the pattern `core/batch_preprocessor.py`
    and `core/streaming.py` already used. It had none before, and was 100% dependent on
    `pdf2image`/poppler -- invisible locally and in CI/Docker, which always have
    `poppler-utils` installed, but a hard failure on every real PDF upload once `packages.txt`
    was gone. This is standard current practice, not an improvised workaround: `pypdfium2`
    bundles its own PDFium binary and needs no system dependency at all, which is exactly why
    it's treated as the modern replacement for poppler-based rendering.

Trade-offs accepted, still in effect:
- **No PDF rendering fallback on the live SCC deployment.** `pypdfium2` is primary and
  `pdf2image`/poppler is the fallback, but poppler isn't installed there anymore, so if
  `pypdfium2` ever fails on some unusual/malformed PDF, there's nothing left to catch it.
  Docker and local dev still install `poppler-utils` (Dockerfile's own `apt-get`, unaffected
  by SCC's outage) and keep the real fallback.
- **`easyocr` and `ensemble` engines remain unavailable on the live site** (predates this
  incident): `requirements.txt` never installs `torch`/`easyocr` there, to stay under SCC's
  free-tier resource cap. The UI hides both options automatically when the package isn't
  importable (`blast_ocr/ui/web_app.py`, `_EASYOCR_AVAILABLE`). Docker/CI/local dev get them
  via `requirements-easyocr.txt`.
- **CI's docker smoke test still only checks `/_stcore/health`.** A real fix needs a headless
  browser wired into that job (installing Playwright + Chromium there, or running the existing
  e2e Playwright suite against the built image instead of a `streamlit run` dev server). Not
  done here -- flagged as a known gap rather than bolted on without buy-in, since it's a real
  scope/cost increase to that job (extra install time, extra job complexity).

See docs/MAINTENANCE_CHECKLIST.md for the recurring checks this incident justifies, most
importantly re-verifying SCC's Python-version dropdown hasn't silently drifted again.
