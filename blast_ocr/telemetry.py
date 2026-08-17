"""
blast_ocr.telemetry

Observability layer (Execution Plan v2 Phase 9). Replaces the earlier stub
(same name, `TelemetryTracker.record_job_metrics`, zero callers, and not
real OpenTelemetry despite the docstring claiming otherwise) with:

- Real OpenTelemetry SDK tracing (job spans), console exporter by default
  (needs no infra, output is directly verifiable by running the app), OTLP
  exporter opt-in via config.otel_exporter="otlp" + config.otel_otlp_endpoint.
- A real prometheus_client-backed /metrics HTTP endpoint using the exact
  counter/histogram names EXECUTION_PLAN.md Phase 9 specifies
  (blast_jobs_total, blast_job_duration_seconds, blast_pages_total, etc.).
- Structured JSON log events (job_id/page/engine/route/duration_ms fields),
  kept from the original stub -- this part was already a reasonable idea,
  just never called from anywhere real.

All OpenTelemetry/prometheus_client imports are deferred so importing this
module (or running with the "console"/default exporter and no metrics server
started) never requires those packages to be installed.
"""

import json
import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional

logger = logging.getLogger("blast_ocr.telemetry")

_tracer = None
_prom: Dict[str, Any] = {}
_started_metrics_ports = set()
_metrics_server_started = False


class _NoOpSpan:
    def set_attribute(self, *a, **k):
        pass


class _NoOpTracer:
    @contextmanager
    def start_as_current_span(self, name, **kwargs):
        yield _NoOpSpan()


def _get_tracer():
    """Lazily build (and cache) the OpenTelemetry tracer. Falls back to a
    no-op tracer if opentelemetry-sdk isn't installed or setup fails, so
    tracing is always safe to call even in a minimal install."""
    global _tracer
    if _tracer is not None:
        return _tracer
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor, SimpleSpanProcessor, ConsoleSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from blast_ocr.config import config

        provider = TracerProvider(resource=Resource.create({"service.name": "blast-ocr"}))
        if config.otel_exporter == "otlp" and config.otel_otlp_endpoint:
            # BatchSpanProcessor is correct here: batching amortizes real
            # network request overhead to a remote collector.
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=config.otel_otlp_endpoint)))
        elif config.otel_exporter != "none":
            # SimpleSpanProcessor, not BatchSpanProcessor: the console exporter
            # just prints, so there is no network overhead to amortize by
            # batching, and BatchSpanProcessor's background export thread would
            # otherwise race process/interpreter shutdown -- observed as a
            # `ValueError: I/O operation on closed file` on every test run
            # once the tracer was actually being exercised (see docs/adr/0012).
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("blast_ocr")
    except Exception as e:
        logger.debug(f"OpenTelemetry tracing unavailable, using no-op tracer: {e}")
        _tracer = _NoOpTracer()
    return _tracer


def _get_prometheus_metrics() -> Dict[str, Any]:
    """Lazily create (and cache) the Prometheus metric objects. Metric names
    match EXECUTION_PLAN.md Phase 9's list verbatim."""
    global _prom
    if _prom:
        return _prom
    from prometheus_client import Counter, Histogram, Gauge

    _prom["jobs_total"] = Counter("blast_jobs_total", "Total OCR jobs processed", ["status"])
    _prom["job_duration_seconds"] = Histogram("blast_job_duration_seconds", "Job processing duration (seconds)")
    _prom["pages_total"] = Counter("blast_pages_total", "Total pages processed", ["engine", "route", "status"])
    _prom["page_duration_seconds"] = Histogram("blast_page_duration_seconds", "Page processing duration (seconds)", ["engine"])
    _prom["page_failures_total"] = Counter("blast_page_failures_total", "Page-level failures", ["engine"])
    _prom["tier0_hit_ratio"] = Gauge("blast_tier0_hit_ratio", "Fraction of pages served by Tier-0 native extraction")
    _prom["ocr_fallback_ratio"] = Gauge("blast_ocr_fallback_ratio", "Fraction of pages that required OCR fallback")
    _prom["ocr_confidence"] = Histogram("blast_ocr_confidence", "OCR confidence score distribution", ["engine"])
    _prom["native_quality"] = Histogram("blast_native_quality", "Tier-0 native text quality score distribution")
    _prom["worker_memory_bytes"] = Gauge("blast_worker_memory_bytes", "Worker process RSS memory (bytes)")
    _prom["export_failures_total"] = Counter("blast_export_failures_total", "Export/output write failures")
    _prom["ocr_throughput_pages_total"] = Counter("blast_ocr_throughput_pages_total", "Total throughput pages processed")
    _prom["ocr_page_latency_seconds"] = Histogram("blast_ocr_page_latency_seconds", "Page processing latency in seconds")
    _prom["ocr_worker_rss_bytes"] = Gauge("blast_ocr_worker_rss_bytes", "Worker process RSS memory in bytes")
    return _prom


def start_metrics_server(port: Optional[int] = None) -> bool:
    """
    Start the Prometheus /metrics HTTP endpoint. Idempotent per port (safe to call
    more than once; binds port on first call per port). Returns True
    if the endpoint is (now, or already was) serving.
    """
    global _metrics_server_started, _started_metrics_ports
    from blast_ocr.config import config
    target_port = port or config.prometheus_port

    if target_port in _started_metrics_ports or _metrics_server_started:
        if target_port in _started_metrics_ports:
            return True
    try:
        from prometheus_client import start_http_server

        _get_prometheus_metrics()
        start_http_server(target_port)
        _started_metrics_ports.add(target_port)
        _metrics_server_started = True
        logger.info(f"Prometheus /metrics endpoint listening on :{target_port}")
        return True
    except Exception as e:
        logger.warning(f"Could not start Prometheus metrics server on port {target_port}: {e}")
        return False


class TelemetryTracker:
    """Structured log events + real metrics/tracing for job and page processing."""

    @staticmethod
    def emit_event(event_type: str, payload: Dict[str, Any]) -> None:
        event_record = {"event": event_type, "timestamp": time.time(), "data": payload}
        logger.info(json.dumps(event_record))

    @staticmethod
    @contextmanager
    def job_span(job_id: Any, engine: str):
        """Wraps a job's processing in an OpenTelemetry span for correlated
        trace/log/metric context (job_id/engine as span attributes)."""
        tracer = _get_tracer()
        with tracer.start_as_current_span("blast.job") as span:
            try:
                span.set_attribute("job_id", str(job_id))
                span.set_attribute("engine", engine)
            except Exception:
                pass
            yield span

    @staticmethod
    def record_job_metrics(
        job_id: Any,
        duration_sec: float,
        pages_count: int,
        success: bool,
        engine: str,
    ) -> None:
        status = "success" if success else "failed"
        TelemetryTracker.emit_event(
            "job_completed" if success else "job_failed",
            {
                "job_id": job_id,
                "duration_sec": round(duration_sec, 3),
                "pages_count": pages_count,
                "engine": engine,
            },
        )
        try:
            metrics = _get_prometheus_metrics()
            metrics["jobs_total"].labels(status=status).inc()
            metrics["job_duration_seconds"].observe(duration_sec)
        except Exception as e:
            logger.debug(f"Prometheus job metric recording skipped: {e}")

    @staticmethod
    def record_page_metrics(
        engine: str,
        route: str,
        duration_sec: float,
        confidence: float,
        success: bool,
        page_number: Optional[int] = None,
    ) -> None:
        TelemetryTracker.emit_event(
            "page.complete",
            {
                "page": page_number,
                "engine": engine,
                "route": route,
                "duration_ms": round(duration_sec * 1000, 1),
                "confidence": round(confidence, 4),
                "status": "success" if success else "failed",
            },
        )
        try:
            metrics = _get_prometheus_metrics()
            status = "success" if success else "failed"
            metrics["pages_total"].labels(engine=engine, route=route, status=status).inc()
            metrics["page_duration_seconds"].labels(engine=engine).observe(duration_sec)
            if success:
                metrics["ocr_confidence"].labels(engine=engine).observe(confidence)
            else:
                metrics["page_failures_total"].labels(engine=engine).inc()
            if route == "native":
                metrics["native_quality"].observe(confidence)
        except Exception as e:
            logger.debug(f"Prometheus page metric recording skipped: {e}")

    @staticmethod
    def record_worker_memory(rss_bytes: float) -> None:
        try:
            metrics = _get_prometheus_metrics()
            if "worker_memory_bytes" in metrics:
                metrics["worker_memory_bytes"].set(rss_bytes)
            if "ocr_worker_rss_bytes" in metrics:
                metrics["ocr_worker_rss_bytes"].set(rss_bytes)
        except Exception as e:
            logger.debug(f"Prometheus worker memory metric recording skipped: {e}")
