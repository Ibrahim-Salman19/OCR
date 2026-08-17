"""
tests/test_telemetry.py

Tests for blast_ocr.telemetry (Execution Plan v2 Phase 9). The Prometheus
endpoint test actually starts a real HTTP server and makes a real HTTP
request against it -- "the /metrics endpoint works" is a claim you verify by
fetching it, not by reading the code that's supposed to serve it.
"""

import urllib.request

import pytest


def test_record_job_metrics_emits_structured_log_and_does_not_raise(caplog):
    from blast_ocr.telemetry import TelemetryTracker
    import logging

    with caplog.at_level(logging.INFO, logger="blast_ocr.telemetry"):
        TelemetryTracker.record_job_metrics(
            job_id=1, duration_sec=1.23, pages_count=5, success=True, engine="rapidocr"
        )
    assert any("job_completed" in r.message for r in caplog.records)


def test_record_page_metrics_emits_structured_log_and_does_not_raise(caplog):
    from blast_ocr.telemetry import TelemetryTracker
    import logging

    with caplog.at_level(logging.INFO, logger="blast_ocr.telemetry"):
        TelemetryTracker.record_page_metrics(
            engine="rapidocr", route="ocr", duration_sec=0.5, confidence=0.9,
            success=True, page_number=3,
        )
    assert any("page.complete" in r.message for r in caplog.records)


def test_job_span_context_manager_does_not_raise():
    from blast_ocr.telemetry import TelemetryTracker

    with TelemetryTracker.job_span(job_id=1, engine="rapidocr") as span:
        assert span is not None


def test_prometheus_metrics_endpoint_actually_serves_real_http(caplog):
    """
    Starts the real Prometheus /metrics HTTP server on a scratch port and
    fetches it with a real HTTP GET -- not asserting on internal state, but
    on what a Prometheus scraper would actually receive.
    """
    pytest.importorskip("prometheus_client")
    from blast_ocr.telemetry import start_metrics_server, TelemetryTracker

    port = 19464  # scratch port, distinct from the config default
    started = start_metrics_server(port=port)
    if not started:
        pytest.skip("Could not bind metrics port in this environment")

    TelemetryTracker.record_job_metrics(
        job_id=99, duration_sec=2.0, pages_count=10, success=True, engine="rapidocr"
    )
    TelemetryTracker.record_page_metrics(
        engine="rapidocr", route="ocr", duration_sec=0.3, confidence=0.95, success=True,
    )

    with urllib.request.urlopen(f"http://localhost:{port}/metrics", timeout=5) as resp:
        body = resp.read().decode("utf-8")

    assert "blast_jobs_total" in body
    assert "blast_job_duration_seconds" in body
    assert "blast_pages_total" in body
    assert 'status="success"' in body
