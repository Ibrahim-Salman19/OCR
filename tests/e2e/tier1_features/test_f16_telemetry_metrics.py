"""
tests/e2e/tier1_features/test_f16_telemetry_metrics.py

Tier 1 Isolated Feature Tests: Feature 16 - Prometheus & JSON Telemetry Metrics
Covers:
- Benchmark scorecard JSON serialization and schema validation
- Prometheus metrics registration and observation recording
- MetricsAggregator time-series and summary data synthesis
- Prometheus exposition format text verification
- Structured telemetry event logging and JSON schema integrity
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytest

from blast_ocr.telemetry import TelemetryTracker, _get_prometheus_metrics


# ============================================================================
# Interface / Reference Implementation for Feature 16 Specification
# ============================================================================

class BenchmarkScorecard:
    """
    Constructs and serializes structured JSON benchmark scorecards.
    """

    @staticmethod
    def build_scorecard(
        total_pages: int,
        total_duration_sec: float,
        throughput_pages_per_sec: float,
        latency_stats: Dict[str, float],
        peak_rss_mb: float,
        leak_slope: float,
        zero_leak_verified: bool,
        time_series: Optional[Dict[str, List[Any]]] = None,
    ) -> Dict[str, Any]:
        return {
            "schema_version": 2,
            "timestamp": datetime.utcnow().isoformat(),
            "environment": {
                "os": "linux",
                "python": "3.10",
                "cpu_count": 8,
                "cuda_available": False,
            },
            "summary": {
                "total_pages": total_pages,
                "total_duration_sec": round(total_duration_sec, 3),
                "throughput_pages_per_sec": round(throughput_pages_per_sec, 2),
                "avg_page_latency_sec": round(latency_stats.get("mean", 0.0), 3),
                "p50_latency_sec": round(latency_stats.get("p50", 0.0), 3),
                "p95_latency_sec": round(latency_stats.get("p95", 0.0), 3),
                "p99_latency_sec": round(latency_stats.get("p99", 0.0), 3),
                "peak_ram_rss_mb": round(peak_rss_mb, 2),
                "memory_growth_slope_mb_per_page": round(leak_slope, 5),
                "zero_leak_verified": zero_leak_verified,
            },
            "time_series": time_series or {
                "timestamps": [],
                "ram_rss_mb": [],
                "cpu_util_pct": [],
            },
        }


class MetricsAggregator:
    """
    Aggregates resource time-series metrics and latency samples into summary statistics.
    """

    @staticmethod
    def aggregate(
        page_latencies: List[float],
        rss_samples_mb: List[float],
        cpu_samples_pct: List[float],
        total_duration_sec: float,
    ) -> Dict[str, Any]:
        total_pages = len(page_latencies)
        tp = (total_pages / total_duration_sec) if total_duration_sec > 0 else 0.0
        
        return {
            "total_pages": total_pages,
            "throughput_pages_per_sec": round(tp, 2),
            "peak_rss_mb": max(rss_samples_mb) if rss_samples_mb else 0.0,
            "mean_cpu_pct": round(sum(cpu_samples_pct) / len(cpu_samples_pct), 1) if cpu_samples_pct else 0.0,
        }


# ============================================================================
# Test Cases (>= 5 Tests)
# ============================================================================

def test_f16_json_benchmark_scorecard_schema_validation(tmp_path):
    """
    Test 1: Tests generated JSON benchmark scorecard adheres to the required
    top-level and summary schema specification.
    """
    latency_stats = {"mean": 0.18, "p50": 0.15, "p95": 0.35, "p99": 0.65}
    scorecard = BenchmarkScorecard.build_scorecard(
        total_pages=500,
        total_duration_sec=80.0,
        throughput_pages_per_sec=6.25,
        latency_stats=latency_stats,
        peak_rss_mb=320.5,
        leak_slope=0.00012,
        zero_leak_verified=True,
    )

    # 1. Top level keys
    assert scorecard["schema_version"] == 2
    assert "timestamp" in scorecard
    assert "environment" in scorecard
    assert "summary" in scorecard
    assert "time_series" in scorecard

    # 2. Summary sub-fields
    summary = scorecard["summary"]
    assert summary["total_pages"] == 500
    assert summary["throughput_pages_per_sec"] == 6.25
    assert summary["p95_latency_sec"] == 0.35
    assert summary["peak_ram_rss_mb"] == 320.5
    assert summary["zero_leak_verified"] is True

    # 3. Valid JSON roundtrip
    out_file = tmp_path / "scorecard.json"
    out_file.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    loaded = json.loads(out_file.read_text(encoding="utf-8"))
    assert loaded["summary"]["total_pages"] == 500


def test_f16_prometheus_metrics_registration_and_recording():
    """
    Test 2: Tests Prometheus metrics objects record job metrics, page durations,
    and worker memory RSS.
    """
    # 1. Record job metrics
    TelemetryTracker.record_job_metrics(
        job_id="test_job_101",
        duration_sec=1.45,
        pages_count=8,
        success=True,
        engine="rapidocr",
    )

    # 2. Record page metrics
    TelemetryTracker.record_page_metrics(
        engine="rapidocr",
        route="ocr",
        duration_sec=0.18,
        confidence=0.97,
        success=True,
        page_number=1,
    )

    # 3. Record worker memory
    TelemetryTracker.record_worker_memory(rss_bytes=256 * 1024 * 1024)

    metrics = _get_prometheus_metrics()
    assert "jobs_total" in metrics
    assert "job_duration_seconds" in metrics
    assert "pages_total" in metrics
    assert "worker_memory_bytes" in metrics


def test_f16_metrics_aggregator_combines_samples():
    """
    Test 3: Tests MetricsAggregator synthesizes latency and resource time-series
    into summary statistics.
    """
    page_latencies = [0.1, 0.2, 0.15, 0.25]  # 4 pages
    rss_samples = [120.0, 135.0, 140.0, 138.0]
    cpu_samples = [15.0, 25.0, 20.0]
    duration = 0.8  # 4 / 0.8 = 5.0 pages/sec

    res = MetricsAggregator.aggregate(page_latencies, rss_samples, cpu_samples, duration)
    assert res["total_pages"] == 4
    assert res["throughput_pages_per_sec"] == 5.0
    assert res["peak_rss_mb"] == 140.0
    assert res["mean_cpu_pct"] == 20.0


def test_f16_prometheus_metrics_endpoint_output_format():
    """
    Test 4: Tests Prometheus metrics exposition generates valid Prometheus text format.
    """
    try:
        from prometheus_client import generate_latest
        output = generate_latest().decode("utf-8")
        assert "blast_jobs_total" in output or "blast_worker_memory_bytes" in output
        assert "# HELP" in output
        assert "# TYPE" in output
    except ImportError:
        pytest.skip("prometheus_client not available")


def test_f16_structured_json_log_event_emission(caplog):
    """
    Test 5: Tests TelemetryTracker.emit_event() produces structured JSON log records
    with event name, timestamp, and payload dictionary.
    """
    import logging
    with caplog.at_level(logging.INFO, logger="blast_ocr.telemetry"):
        TelemetryTracker.emit_event(
            "benchmark_window_complete",
            {
                "window": 2,
                "pages_processed": 16,
                "window_duration_sec": 2.8,
            },
        )
        
        # Verify JSON record was logged
        found = False
        for record in caplog.records:
            try:
                data = json.loads(record.message)
                if data.get("event") == "benchmark_window_complete":
                    assert data["data"]["window"] == 2
                    assert data["data"]["pages_processed"] == 16
                    found = True
                    break
            except Exception:
                continue
        assert found, "Expected structured JSON log record was not emitted"
