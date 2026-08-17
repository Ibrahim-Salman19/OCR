Title: Phase 1 v2 -- Closing the Architecture-vs-Reality Gap (Wiring, Concurrency Fix, Correctness)
Status: accepted
Date: 2026-08-13

Context:
- ADR 0008 declared "100% of execution plan phases (Phase 0 through Phase 6) complete," but
  that referred to the original 5-phase plan. A subsequent, more rigorous production
  architecture review (`docs/EXECUTION_PLAN.md`, "Production Architecture Plan v2") found
  that several P0 modules built to satisfy its requirements existed on disk with isolated
  unit tests, but were never called from the real request path:
  - `blast_ocr/security/gateway.py` (`IngestionGateway`) -- zero callers.
  - `blast_ocr/core/job_state.py` (`JobStateMachine`, `JobFingerprint`, retry taxonomy) -- zero callers.
  - `blast_ocr/core/manifest.py` (`RunManifest`) -- zero callers; `pipeline.py` hand-rolled its
    own manifest dict instead.
  - `blast_ocr/telemetry.py` -- zero callers, and not real OpenTelemetry despite the docstring.
- Worse, the flagship bug EXECUTION_PLAN.md section 1.1 was written to fix -- concurrent jobs
  requesting different OCR engines silently cross-contaminating via mutable global config --
  was still live. `JobConfig` existed and was threaded through tier0-routing and
  confidence-threshold decisions, but `ParallelOCRProcessor.process_batch_threaded` never
  forwarded it to `process_page_wrapper`, so engine selection always fell back to the global
  `config.ocr_engine` singleton. No test asserted cross-job engine isolation.

Decision:
- `blast_ocr/core/parallel.py`: `process_batch_threaded` now accepts and forwards `job_config`
  to every `executor.submit()` call. `blast_ocr/pipeline.py`'s three call sites updated to pass
  `self.job_config`. New regression tests in `tests/test_concurrency_complete.py`
  (`TestCrossJobEngineIsolation`) run two concurrent jobs with different engines through real
  threads and assert zero cross-contamination -- the test that should have existed originally.
- `BlastPipeline.process_job()` now calls `IngestionGateway.validate_and_ingest()` on every
  file-based job before any processing, writing the validated copy to a per-job `_ingest/`
  subdirectory (not the shared system temp root) and retaining the SHA-256 fingerprint for the
  run manifest. `web_app.py`'s upload handler now imports its allowlist from
  `IngestionGateway.ALLOWED_EXTENSIONS` instead of a separately hand-maintained list that had
  drifted (missing `.bmp`/`.tiff`, silently rejecting files the pipeline actually supports).
- `OCRJob.status` now stores `JobState` enum values, validated through
  `JobStateMachine.validate_transition()` on every write. `process_job()` walks the real
  lifecycle (RECEIVED -> VALIDATING -> QUEUED -> PROCESSING -> POST_PROCESSING -> EXPORTING ->
  SUCCEEDED/SUCCEEDED_WITH_WARNINGS/FAILED); jobs with any page-level error land in
  SUCCEEDED_WITH_WARNINGS rather than a blanket SUCCEEDED, per the plan's "no silent page
  failures" principle. Legacy string aliases (`"pending"`/`"processing"`/`"completed"`/
  `"failed"`) are still accepted by `update_job_status()` for backward compatibility, mapped
  onto their `JobState` equivalents. No Alembic migration was required: `status` was already
  an unconstrained `String(50)` column, so this is a widening of validated values, not a schema
  change. `web_app.py`'s status-color map and completion gate were updated to recognize the
  fuller vocabulary -- without this, jobs reaching `SUCCEEDED` (rather than the old `"completed"`
  string) would have rendered as an unrecognized status and never shown their results.
- `pipeline.py`'s hand-rolled manifest dict replaced with `RunManifest`, populated with the
  ingestion SHA-256, real per-artifact SHA-256 hashes (computed after `output_map` is resolved,
  not before), routing counts (native vs. OCR pages), and git commit SHA.
- `blast_ocr/core/router.py`'s `apply_auto_routing()` mutated `pipeline_instance._config`
  directly -- the same class of shared-mutable-state bug as the engine-selection race, for
  language routing instead of engine choice. It has zero callers outside its own test (unlike
  the engine bug, this one was never live), but the mutation was removed regardless: the
  function now only returns the computed language list, so a future caller can fold it into an
  immutable per-job `JobConfig` instead of reintroducing the hazard.
- Added `blast_ocr.core.job_state.classify_exception()` to bridge the two previously-unrelated
  exception hierarchies (`core/exceptions.py`'s domain exceptions, raised by the extractor, vs.
  `job_state.py`'s `RetryableJobError`/`NonRetryableJobError` taxonomy). `process_job()`'s
  top-level except block now classifies every job failure and returns `retryable: bool` in its
  result dict -- groundwork for Phase 2's queue retry policy, which needs this classification to
  avoid retrying deterministic failures (bad input) as if they were transient ones (worker crash).

Consequences:
- Positive:
  - The concurrency bug the plan was originally written to fix is now actually fixed and
    regression-tested, not just modeled in an unused dataclass.
  - Every file the pipeline touches now passes through one real security boundary, not a
    second, looser, independently-drifting check in the UI layer.
  - Job status is a validated state machine, not free-form strings a caller could set to
    anything.
  - Manifests carry real, verifiable hashes instead of being an audit record that can't
    actually be used to detect tampering.
- Negative / follow-up:
  - `JobFingerprint`-based idempotency (dedup identical repeated jobs) is still not wired in --
    deferred to Phase 2, where a durable queue makes idempotency checks meaningful (a
    synchronous pipeline has no double-submission window to protect against).
  - The three sequential `update_job_status()` calls (VALIDATING/QUEUED/PROCESSING) on every
    job add minor DB write overhead in exchange for lifecycle auditability; acceptable for a
    SQLite-backed single-node deployment, worth revisiting if status writes become a bottleneck.
