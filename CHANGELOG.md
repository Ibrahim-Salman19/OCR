# Changelog

All notable changes to the B.L.A.S.T. OCR Engine will be documented in this file.

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
