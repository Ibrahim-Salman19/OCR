# Changelog

All notable changes to the B.L.A.S.T. OCR Engine will be documented in this file.

## [Unreleased] - 2026-04-06

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
