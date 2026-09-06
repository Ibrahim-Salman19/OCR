# Changelog

All notable changes to the B.L.A.S.T. OCR Engine will be documented in this file.

## [Unreleased] - 2026-09-06

### Fixed (Critical -- CI was not actually running tests)
- **Critical**: `tests/conftest.py` unconditionally registered `tests.playwright_fixtures` as a
  pytest plugin, which imports `playwright.sync_api` at module level; the CI "Unit + integration
  tests" job never installs the `playwright` package. Pytest's plugin loader raised
  `ModuleNotFoundError` before collecting a single test, and pytest aborts an entire session on a
  collection error by default -- **zero tests actually ran in CI for at least 8 days and 5
  consecutive pushes** (confirmed via `gh run list -w ci.yml`), regardless of what the README
  badge or any marketing doc claimed. Fixed by gating plugin registration on `playwright` actually
  being importable and adding `collect_ignore_glob = ["test_playwright_*.py"]` for that
  environment, plus `-m "not playwright"` in `ci.yml`. Verified by reproducing CI's exact
  playwright-less condition locally: 844 non-Playwright tests (842 passed, 2 skipped, 0 failed)
  and, separately, 70/70 Playwright tests with the package restored.
- Fixed a second, independently-failing CI job: bandit's B613 (trojansource) check flagged
  `blast_ocr/security/gateway.py`'s intentional Unicode BiDi-override-character detection list as
  a HIGH-severity finding, with no `# nosec` suppression in place. Added a justified inline
  `# nosec B613` -- the characters are a literal detection list a security module uses to *reject*
  hostile uploads, not obfuscated content hiding from review.
- Streamlit UI (`blast_ocr/ui/web_app.py`): canonical link, meta description, robots directive,
  and OG/Twitter tags were rendered into the app body via `st.markdown(...,
  unsafe_allow_html=True)`, never `<head>` -- Google explicitly ignores a canonical tag found
  outside `<head>`, and the raw pre-JS HTTP response (891 bytes) was invisible to every non-JS
  crawler regardless. Added `_inject_head_tags()` to relocate these into the real
  `document.head` via a Streamlit component iframe; added the previously-missing `og:image`.
  Non-JS crawlers (GPTBot, ClaudeBot, PerplexityBot) still can't read the Streamlit surface --
  that's a Streamlit Community Cloud hosting constraint, not fixable from application code --
  mitigated by a new static GitHub Pages surface (see Added, below).
- `blast_ocr/ui/web_app.py`: `_build_zip_bytes`'s return type annotation referenced `io.BytesIO`
  with `io` only imported inside the function body -- harmless at runtime (`from __future__ import
  annotations` defers evaluation) but a real mypy finding. Moved `import io` to module scope.
- Schema.org JSON-LD had drifted out of sync across its three surfaces: the Streamlit UI graph was
  missing the `Dataset` entity and 3 of 8 `FAQPage` questions that README.md's graph had. All three
  surfaces (plus the new GitHub Pages page) now carry identical entities.
- `llms.txt`/`llms-full.txt` (root and `docs/` copies) had ~20 relative markdown links each,
  inconsistent with the absolute-URL convention used everywhere else in the same files; normalized
  to absolute GitHub URLs. The `docs/` copies were also missing the author E-E-A-T section present
  in the root copies; synced.

### Added
- `index.html` + `.nojekyll`: a static GitHub Pages site (`https://ibrahim-salman19.github.io/OCR/`)
  with real server-rendered `<head>` metadata and JSON-LD, readable by non-JS crawlers -- verified
  live in production with a plain `curl` (no JS execution) after enabling Pages via the GitHub API.
  Serving from the repo root also makes `robots.txt`, `sitemap.xml`, `llms.txt`, `llms-full.txt`,
  `pricing.md`, and `mcp.json` reachable at a real URL for the first time.
- `marketing/assets/og_image.png`: a 1200x630 Open Graph image cropped from the existing landing
  screenshot (there was no `og:image` at all before).

### Corrected (stale claims across marketing docs)
- A "737 tests" figure was repeated across ~19 files (`README.md`, `llms.txt`/`llms-full.txt`,
  `.agents/product-marketing.md`, `gemini.md`, and 12 `docs/marketing/*.md` files); the suite had
  grown to 914 tests since that number was last accurate. Corrected everywhere to the verified
  current figure: 914 tests, 912 passed, 2 skipped, 0 failed.
- `README.md` and `docs/GEO_AND_SEO_OPTIMIZATION.md` claimed "187 repository files" for the Ruff
  clean-lint figure; the real git-tracked count is 245. Also added the caveat that the configured
  ruff scope is 4 rule categories (`E722`/`F401`/`F811`/`F841`), not the full default rule set.
  `docs/marketing/13_TECHNICAL_SEO_AUDIT.md`'s self-assigned "98/100 (Exceptional)" score was
  removed in favor of naming what was actually verified and what remains open.
  `docs/marketing/16_SCHEMA_MARKUP_VALIDATION.md` corrected two rich-result eligibility claims:
  Google restricted FAQ rich results to gov/health sites and discontinued HowTo rich results
  entirely in August 2023 -- the schema is still valid for GEO/AI-answer extraction, just not for
  a Google SERP rich card.

### Fixed (found only once CI could actually run)
- `blast_ocr/core/engines/tesseract_engine.py`: `process_page()` did `from pytesseract import
  Output` as a fresh top-level import, bypassing the already-resolved `self._pytesseract`
  reference entirely -- the method required the real `pytesseract` package even when a caller had
  supplied a working mock/reference. Broke in CI (which doesn't install `pytesseract`; it's not a
  project dependency -- RapidOCR is the default, Tesseract an optional fallback); masked locally
  because `pytesseract` happened to already be installed there. Fixed to read `Output.DICT` off
  `self._pytesseract`.
- `tests/test_ui_deep_coverage.py::test_resource_snapshot` unpacked `_resource_snapshot()`'s
  return value as `cpu, mem = ...`, but the function returns `(memory_mb, cpu_percent)` in that
  order -- the swapped names inverted the assertions (it was really checking `cpu_percent > 0.0`,
  not a safe invariant, while never checking that RSS is positive). Only failed in CI when a quiet
  moment made `cpu_percent` read exactly `0.0`.
- Confirmed via `gh run watch` on two live GitHub Actions runs (not just local reproduction): the
  first surfaced the two bugs above; the second, after fixing them, was fully green -- all 6 CI
  jobs passing, 840 passed / 3 skipped / 0 failed.

## [Unreleased] - 2026-08-13

### Fixed (Correctness -- ADR 0009)
- **Critical**: Fixed a cross-job OCR-engine race condition where concurrent jobs requesting
  different engines (RapidOCR vs. EasyOCR) could silently use the wrong engine, because
  `ParallelOCRProcessor.process_batch_threaded` never forwarded the per-job `JobConfig` to
  worker calls despite `JobConfig` existing specifically to prevent this. Added a real
  regression test (`TestCrossJobEngineIsolation`) that runs two concurrent jobs through real
  threads and asserts zero cross-contamination.
- Wired `IngestionGateway` (security validation), `JobStateMachine` (validated job lifecycle),
  and `RunManifest` (auditable provenance) into the actual request path -- all three existed as
  unit-tested modules with zero real callers before this fix.
- Fixed `blast_ocr/storage/alembic/env.py` and `alembic.ini`: Alembic migrations were entirely
  non-functional (`alembic upgrade head` failed immediately on a malformed `[logging]` section),
  and a second bug meant a database bootstrapped via `create_all()` had no `alembic_version`
  stamp, so a later migration would fail on "table already exists." Both fixed and covered by
  `tests/test_alembic_migration.py` running the real Alembic CLI.

### Added (Production Infrastructure)
- **Durable queue** (`blast_ocr/queue/`, opt-in via `BLAST_OCR_QUEUE_BACKEND=redis`): Redis + RQ
  job processing that survives the web process restarting or a browser tab closing. See
  ADR 0010.
- **Object storage** (`blast_ocr/storage/object_store.py`, opt-in via
  `BLAST_OCR_STORAGE_BACKEND=s3`): S3/MinIO-compatible artifact mirroring. See ADR 0011.
- **Real observability** (`blast_ocr/telemetry.py`, rewritten): OpenTelemetry tracing (console
  exporter by default, OTLP opt-in) and a real Prometheus `/metrics` endpoint with the metric
  set EXECUTION_PLAN.md Phase 9 specifies. See ADR 0012.
- **CI/CD**: `.github/workflows/ci.yml` (lint, type-check, tests with a real Redis service
  container, dependency + SAST scanning, OCR quality regression gate, container build),
  `Dockerfile` (multi-stage, non-root), `docker-compose.yml` (app + optional
  queue/storage/observability profiles). See ADR 0013.
- `pyproject.toml` with pinned core dependencies plus `queue`/`storage`/`observability`/`dev`
  optional-dependency groups; `requirements-production.txt` and `requirements-dev.txt` split out
  from `requirements.txt` after a real `docker build` caught a dependency conflict between
  `opentelemetry-exporter-otlp` and the pinned `streamlit==1.32.0`.
- `docs/COMPETITIVE_LANDSCAPE.md`: researched comparison against Docling, Marker, MinerU,
  PaddleOCR, olmOCR, AWS Textract/Google Document AI/Azure Document Intelligence/Mistral OCR, and
  the VLM-vs-traditional-OCR trend, with a prioritized gap list.

## [Unreleased] - 2026-08-11

### Added
- **Tier-0 Native Text Routing**: Added `Tier0Extractor` module (`blast_ocr/core/tier0_extractor.py`) using `pypdfium2` (Apache-2.0) for native PDF text extraction and quality plausibility scoring.
- **Book Intelligence Module**: Implemented `BookProcessor` (`blast_ocr/core/book_intelligence.py`) for repeating header/footer stripping, cross-line dehyphenation, paragraph reflow, and semantic EPUB export.
- **Engine Adapter Architecture**: Introduced pluggable `BaseOCREngine` interface in `blast_ocr/core/engines/base.py`, `EasyOCREngine`, `RapidOCREngine` (ONNXRuntime), and factory function `get_engine()`.
- **Architecture Decision Records**: Added `docs/adr/0005-phase3-engine-bakeoff.md`, `docs/adr/0006-phase4-book-intelligence.md`, and `docs/adr/0007-phase5-tier0-native-extraction.md`.

### Changed
- **Production Engine Default**: Promoted `RapidOCR` to default engine. Full-corpus evaluation showed a **~7.7x CPU speedup** (~15s/page vs ~118s/page) and an 18% relative reduction in Character Error Rate (CER `0.1916` vs `0.2338`).
- **Cache Key Fingerprinting**: Updated `get_cache_namespace(engine_name)` to isolate engine-specific cache entries.

### Added
- **Typed Document Model**: Introduced `Document`, `Page`, `Block`, `Line`, `Span`, and `BoundingBox` Pydantic models in `blast_ocr/core/document_model.py` (Docling-inspired schema).
- **Layout Analysis Engine**: Implemented `LayoutEngine` (`blast_ocr/core/layout.py`) featuring dual-page spread detection/gutter splitting, Recursive XY-Cut column segmentation, and adaptive glyph-height line clustering.
- **ADR 0004**: Added `docs/adr/0004-phase2-layout-and-document-model.md` documenting layout resurrection and document model architecture.

### Changed
- **OCR Reading Order & Bounding Box Preservation**: Integrated `LayoutEngine` into `RobustOCRExtractor.process_page`, driving CER down from 0.4944 to 0.2338 (-52.7%), WER from 0.7248 to 0.4968 (-31.5%), reading order tau from 0.6822 to 0.9641, and fact pass rate from 29.8% to 44.7%. Attached full `page_model` to extraction results.

### Removed
- **Dead Code Cleanup**: Deleted legacy, unused `_regroup_text_by_layout()` row-grouping function from `pipeline.py`.


## [2.1.0] - 2026-08-10

### Added
- **Evaluation Harness & Ground Truth Dataset**: Added `eval/run.py` 14-page gold dataset, CER/WER/Tau/Fact-check evaluators (`eval/metrics.py`), and regression gate (`tests/test_eval_regression.py`). (Phase 0)
- **ADR 0003**: Added `docs/adr/0003-phase1-preprocessing-fixes.md` detailing image preprocessing fixes and empirical verification.

### Fixed
- **Phase 1 Image Preprocessing**:
  - Replaced arbitrary max_dim downscaling with glyph-height estimation (`_estimate_glyph_height`) and targeted resizing to avoid interpolating phantom detail.
  - Replaced rigid -45° to +45° deskew search with projection-profile search bounded to ±7.5° for 10x faster execution and 0 false rotates.
  - Made CLAHE and sharpening strictly conditional to `mode="reflexion"`, leaving standard grayscale uncrushed and eliminating contrast artifacts on cloth-weave paper.
  - Made Immerkaer noise variance denoise conditional (`noise_sigma > 2.0`), preserving clean text letterforms.
  - Halved page-processing latency (~60s -> ~33s) while improving CER (0.4992 -> 0.4944) and WER (0.7288 -> 0.7248).

### Added
- **OCR Transition Documentation**: Added deep documentation set for safe OCR engine migration planning:
  - `docs/OCR_ENGINE_EVALUATION_2026.md`
  - `docs/OCR_ENGINE_TRANSITION_PLAYBOOK.md`
  - `docs/OCR_ENGINE_INTEGRATION_MAP.md`

### Changed
- **Docs Navigation**: Updated README and core docs to cross-link migration references, deployment notes, integration constraints, and CPU-only benchmark guidance.

## [2.0.2] - 2026-04-04

### Fixed
- **Pipeline Reliability**: Stabilized PDF/image/PPTX processing paths with stronger batching behavior, safer temp-file lifecycle handling, and deterministic post-processing across routes.
- **OCR Stability**: Hardened extractor inference flow for lower memory pressure and improved resilience during long-running jobs.
- **Database Robustness**: Improved default job creation behavior and cleanup query correctness for lifecycle maintenance paths.
- **Web UI Runtime Safety**: Hardened upload/session flows, background-job guards, and non-runtime fallback behavior to reduce Streamlit context-related failures.

### Added
- **Best-Practice Tests**: Added targeted reliability coverage for pipeline redaction behavior and large-document worker restoration (`tests/test_pipeline_best_practices.py`).

### Changed
- **Debugging Operations**: Upgraded project OCR debugging skill guidance to a structured, end-to-end incident workflow for faster triage and safer fixes.
- **Test Architecture**: Standardized mocking and concurrency/memory test behavior for more deterministic CI/local outcomes.

## [2.0.1] - 2026-04-04

### Fixed
- **Warning Gate Hardening**: Enforced strict warning discipline in tests with explicit third-party suppression policy and marker registration.
- **Resource Cleanup**: Fixed logging handler teardown to close file descriptors cleanly and prevent unraisable/resource warning failures.
- **Flake Reduction**: Stabilized memory/property-based tests under stricter warning policy and host variability.

### Added
- **Decision Framework**: Added `skills/decision_engineering.md` for mitigation-first, OODA, RICE, and ADR-driven execution.
- **Architecture Record**: Added `docs/adr/0001-stabilization-warning-and-memory-policy.md` documenting reliability decisions and verification gates.

## [2.0.0] - 2026-03-26

### Fixed (Forensic Remediation)
- **Database**: Implemented `scoped_session` and `IMMEDIATE` isolation to prevent SQLite WAL deadlocks and transaction poisoning (BUG-DB-ROLLBACK-01, BUG-DB-DEADLOCK-01).
- **Concurrency**: Added module-level `_ocr_global_lock` to serialize EasyOCR calls and fixed worker singleton race conditions (BUG-WORKER-RACE-01).
- **Security**: Patched XXE/DoS vulnerabilities in PPTX/DOCX using `defusedxml` (BUG-XXE-LFD-01).
- **Security**: Resolved cross-user session data bleeding by enforcing per-session UUID output directories (BUG-DATA-BLEED-01).
- **Resources**: Hardened Windows file handle cleanup with retry loops and explicit GC triggers (BUG-TEMPDIR-WIN-01, BUG-MEM-GC-01).
- **Stability**: Resolved 110/110 test suite regressions including environment-specific flakes on Windows.

## [Unreleased] - 2026-02-04

### Fixed
- **Critical**: Resolved `FileNotFoundError` when running the CLI on files in the root directory without specifying an output folder.
- **Regression**: Fixed `AttributeError` in logging configuration by correcting `datetime` imports.
- **Deprecation**: Updated `datetime.utcnow()` to `datetime.now(timezone.utc)` across all modules.
- **Cleanup**: Removed duplicate imports in `web_app.py`.

### Added
- **Docs**: Added comprehensive `README.md`, `ARCHITECTURE.md`, and `CONTRIBUTING.md`.
- **Docs**: Added `CHANGELOG.md`.

### Removed
- **Cleanup**: Deleted temporary test artifacts (`test_output/`, `gui_output/`) and `__pycache__` directories.
