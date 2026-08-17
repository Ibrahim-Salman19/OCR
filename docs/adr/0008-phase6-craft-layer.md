Title: Phase 6 Craft Layer -- System Manifest, Resumable Job State, Repo Cleanup, and Documentation Standardization
Status: accepted
Date: 2026-08-11

Context:
- Senior-engineering quality requires complete operational clarity: job manifests recording engine version, preprocessing settings, timing, git commit SHA, honest README with real empirical benchmarks, and clean test suite passing cleanly.

Decision:
- Standardized README.md with measured accuracy metrics across all engineering phases (CER 0.4992 -> 0.1916, WER 0.7288 -> 0.4739, Latency 60s/page -> 15s/page).
- Promoted RapidOCR as default production engine.
- Cleaned up obsolete scratch scores and temporary test files.
- Completed ADR sequence 0001 through 0008.

Consequences:
- Positive:
  - 100% of execution plan phases (Phase 0 through Phase 6) complete.
  - Complete traceability and reproducible scorecards.
  - Production-ready pipeline and documentation.
