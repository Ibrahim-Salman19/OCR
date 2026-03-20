# Changelog

All notable changes to the B.L.A.S.T. OCR Engine will be documented in this file.

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
