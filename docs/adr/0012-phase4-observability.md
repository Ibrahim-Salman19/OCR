Title: Phase 4 -- Real OpenTelemetry Tracing, Prometheus Metrics, and Structured Logs
Status: accepted
Date: 2026-08-13

Context:
- EXECUTION_PLAN.md Phase 9 states "logger.info() is not production observability" and specifies
  an exact list of required metrics (`blast_jobs_total`, `blast_job_duration_seconds`,
  `blast_pages_total`, `blast_tier0_hit_ratio`, `blast_ocr_confidence`, etc.), correlated
  structured logs, and OpenTelemetry-based tracing.
- `blast_ocr/telemetry.py` already existed with a `TelemetryTracker.record_job_metrics()`
  method and a docstring claiming "OpenTelemetry and Structured Logging Integration" -- but it
  contained zero `opentelemetry` imports (it only serialized a dict to a JSON log line) and, per
  ADR 0009's audit, had zero callers anywhere in the codebase. It satisfied the letter of "a
  module named telemetry.py exists" while satisfying none of the actual requirement.

Decision:
- Rewrote `blast_ocr/telemetry.py` with three real, independently-verified layers:
  1. **OpenTelemetry tracing**: a lazily-constructed `TracerProvider`, `ConsoleSpanExporter` by
     default (needs no infra, output is directly inspectable by running the app -- this was
     deliberately chosen over defaulting to an OTLP exporter that silently drops spans when no
     collector is listening), OTLP exporter opt-in via `config.otel_exporter="otlp"` +
     `config.otel_otlp_endpoint`. `TelemetryTracker.job_span()` wraps a job's processing in a
     span carrying `job_id`/`engine` attributes.
  2. **Prometheus metrics**: `blast_ocr/telemetry.py`'s `_get_prometheus_metrics()` creates the
     exact counter/histogram/gauge set EXECUTION_PLAN.md Phase 9 names, and
     `start_metrics_server(port)` starts a real `prometheus_client` HTTP endpoint.
     `tests/test_telemetry.py::test_prometheus_metrics_endpoint_actually_serves_real_http` starts
     this server on a scratch port and issues a real `urllib` GET against it, asserting the
     response body contains the expected metric names and label values -- proving the endpoint
     is fetchable, not just that the code compiles.
  3. **Structured logs**: `blast_ocr/logging_config.py`'s `JSONFormatter` already supported two
     hardcoded extra fields (`page_number`, `confidence`); widened to the full field set Phase 9
     specifies (`job_id`, `document_id`, `page`, `engine`, `route`, `duration_ms`, `event`),
     populated via `TelemetryTracker.emit_event()`.
- Wired both layers into the real request path (the same gap closed for security/job-state/
  manifest in ADR 0009): `blast_ocr/core/worker.py`'s `process_page_wrapper()` now calls
  `TelemetryTracker.record_page_metrics()` on every page (both success and failure branches);
  `blast_ocr/pipeline.py`'s `process_job()` now calls `TelemetryTracker.record_job_metrics()` on
  both the success and failure return paths, timed from a `job_start_time` captured immediately
  before the job's `try` block.
- All `opentelemetry`/`prometheus_client` imports are deferred into function bodies, so importing
  `blast_ocr.telemetry` (which several other modules now do unconditionally) never requires
  those packages to be installed -- tracing/metrics recording silently no-ops (falls back to a
  `_NoOpTracer`, or logs at DEBUG and continues) rather than breaking a minimal install that
  hasn't opted into the observability extras.

Consequences:
- Positive:
  - Every job and every page processed now emits a real, independently-verified metric and a
    structured log event with correlated context -- genuinely fetchable via `/metrics`, not
    merely modeled in an unused class.
  - The console span exporter default means tracing is inspectable with zero extra
    infrastructure -- useful even for a single-developer local run, not just a full OTel
    Collector deployment.
- Negative / follow-up:
  - No OTel Collector / Prometheus / Grafana services were added to the (not-yet-written)
    Docker Compose stack in this ADR -- that's Phase 5's containerization work. This ADR covers
    the application-side instrumentation; wiring it into a scrapeable multi-container deployment
    is tracked separately.
  - Initially used `BatchSpanProcessor` for the console exporter, whose background export
    thread raced process/interpreter shutdown once the tracer was actually being exercised
    (`ValueError: I/O operation on closed file`, reproduced on every full test suite run after
    telemetry was wired into the real request path). Fixed by switching the console exporter to
    `SimpleSpanProcessor` (synchronous, no background thread) -- the correct choice regardless,
    since `BatchSpanProcessor`'s batching exists to amortize real network overhead to a remote
    collector, which a console exporter has none of. `BatchSpanProcessor` is still used for the
    OTLP exporter path, where that batching is genuinely doing something useful.
