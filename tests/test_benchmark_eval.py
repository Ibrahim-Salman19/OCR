"""
tests/test_benchmark_eval.py

Comprehensive Unit and Functional Test Suite for Milestone 4:
- Automated Load Benchmark CLI and Synthetic Document Generator (eval/benchmark_load.py)
- Latency Quantiles, Statistical Distributions, and SLA Regression Gating
- Structured JSON Benchmark Scorecards and Prometheus Telemetry
- ResourceMonitor Sampling and Linear Regression Memory Leak Detection (eval/stress_suite.py)
- 1,000-Page Continuous Zero-Leak Workload and FD Stability Testing
- Chaos Fault Injection, Worker Crash Recovery, and Dead-Letter Queue Quarantine
- CLI execution and export verification
"""

import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List

import numpy as np
from PIL import Image
import psutil
import pytest

from eval.benchmark_load import (
    SyntheticDocGenerator,
    LatencyStats,
    calculate_quantiles,
    BenchmarkScorecard,
    MetricsAggregator,
    BenchmarkRunner,
    LoadBenchmarkRunner,
    run_load_benchmark,
)
from eval.stress_suite import (
    ResourceMonitor,
    MemoryLeakDetector,
    compute_ols_slope,
    ChaosInjector,
    StressTestRunner,
    StressSuiteRunner,
)
from blast_ocr.telemetry import (
    TelemetryTracker,
    _get_prometheus_metrics,
    start_metrics_server,
)


@pytest.fixture(autouse=True)
def mock_easyocr_reader_for_tests():
    """No-op override of root conftest easyocr patch to avoid slow torch import."""
    yield


# ============================================================================
# 1. Synthetic Document Generator Tests
# ============================================================================

class TestSyntheticDocGenerator:
    def test_multipage_creation_and_dimensions(self):
        gen = SyntheticDocGenerator(seed=123)
        pages = gen.generate_document_pages(page_count=4, width=640, height=960)
        assert len(pages) == 4
        for p in pages:
            assert isinstance(p, Image.Image)
            assert p.size == (640, 960)
            assert p.mode == "RGB"

    def test_determinism_with_seed(self):
        gen1 = SyntheticDocGenerator(seed=42)
        gen2 = SyntheticDocGenerator(seed=42)
        p1 = gen1.generate_page_numpy(width=400, height=600)
        p2 = gen2.generate_page_numpy(width=400, height=600)
        assert np.array_equal(p1, p2)

    def test_batch_numpy_generation(self):
        gen = SyntheticDocGenerator(seed=99)
        batch = gen.generate_batch_numpy(page_count=3, width=500, height=700)
        assert len(batch) == 3
        for arr in batch:
            assert isinstance(arr, np.ndarray)
            assert arr.shape == (700, 500, 3)
            assert arr.dtype == np.uint8


# ============================================================================
# 2. Latency Stats & Quantiles Tests
# ============================================================================

class TestLatencyStats:
    def test_empty_samples(self):
        stats = LatencyStats.compute([])
        assert stats["count"] == 0
        assert stats["p50"] == 0.0
        assert stats["p95"] == 0.0
        assert stats["mean"] == 0.0

    def test_single_sample(self):
        stats = LatencyStats.compute([0.45])
        assert stats["count"] == 1
        assert stats["p50"] == 0.45
        assert stats["p95"] == 0.45
        assert stats["p99"] == 0.45
        assert stats["min"] == 0.45
        assert stats["max"] == 0.45
        assert stats["mean"] == 0.45

    def test_uniform_distribution_percentiles(self):
        # 100 samples from 0.01 to 1.00s
        samples = [i * 0.01 for i in range(1, 101)]
        stats = LatencyStats.compute(samples)
        assert stats["count"] == 100
        assert pytest.approx(stats["min"], rel=1e-2) == 0.01
        assert pytest.approx(stats["max"], rel=1e-2) == 1.00
        assert pytest.approx(stats["p50"], rel=1e-2) == 0.505
        assert pytest.approx(stats["p75"], rel=1e-2) == 0.7525
        assert pytest.approx(stats["p90"], rel=1e-2) == 0.901
        assert pytest.approx(stats["p95"], rel=1e-2) == 0.9505
        assert pytest.approx(stats["p99"], rel=1e-2) == 0.9901
        assert pytest.approx(stats["mean"], rel=1e-2) == 0.505

    def test_calculate_quantiles_alias(self):
        samples = [0.1, 0.2, 0.3, 0.4, 0.5]
        q = calculate_quantiles(samples)
        assert q["p50"] == 0.3
        assert q["min"] == 0.1
        assert q["max"] == 0.5


# ============================================================================
# 3. Scorecard & Metrics Aggregator Tests
# ============================================================================

class TestBenchmarkScorecardAndAggregator:
    def test_scorecard_build_schema_and_json_roundtrip(self, tmp_path):
        latency_stats = {"mean": 0.12, "p50": 0.10, "p95": 0.25, "p99": 0.40}
        time_series = {
            "timestamps": [1.0, 2.0],
            "ram_rss_mb": [150.0, 152.0],
            "cpu_util_pct": [20.0, 25.0],
        }
        scorecard = BenchmarkScorecard.build_scorecard(
            total_pages=200,
            total_duration_sec=25.0,
            throughput_pages_per_sec=8.0,
            latency_stats=latency_stats,
            peak_rss_mb=180.5,
            leak_slope=0.00005,
            zero_leak_verified=True,
            time_series=time_series,
        )

        assert scorecard["schema_version"] == 2
        assert "timestamp" in scorecard
        assert "environment" in scorecard
        assert scorecard["summary"]["total_pages"] == 200
        assert scorecard["summary"]["throughput_pages_per_sec"] == 8.0
        assert scorecard["summary"]["zero_leak_verified"] is True

        # Save and Reload
        out_file = tmp_path / "test_scorecard.json"
        BenchmarkScorecard.save(scorecard, out_file)
        loaded = BenchmarkScorecard.load(out_file)

        assert loaded["schema_version"] == 2
        assert loaded["summary"]["total_pages"] == 200
        assert loaded["summary"]["peak_ram_rss_mb"] == 180.5

    def test_metrics_aggregator(self):
        page_lats = [0.1, 0.2, 0.3]
        rss_s = [100.0, 120.0, 110.0]
        cpu_s = [10.0, 30.0, 20.0]
        duration = 0.5

        agg = MetricsAggregator.aggregate(page_lats, rss_s, cpu_s, duration)
        assert agg["total_pages"] == 3
        assert agg["throughput_pages_per_sec"] == 6.0
        assert agg["peak_rss_mb"] == 120.0
        assert agg["mean_cpu_pct"] == 20.0


# ============================================================================
# 4. Benchmark Runner & SLA Tests
# ============================================================================

class TestBenchmarkRunner:
    def test_sla_passed_condition(self):
        runner = BenchmarkRunner(target_throughput=5.0, max_latency_p95=1.0)
        # 10 pages in 1.5s -> 6.67 p/s (> 5.0), p95 = 0.15s (< 1.0s)
        report = runner.run_benchmark([0.15] * 10, total_duration_sec=1.5)
        assert report["sla_passed"] is True
        assert report["throughput_pages_per_sec"] == 6.67
        assert report["total_pages"] == 10

    def test_sla_latency_violation(self):
        runner = BenchmarkRunner(target_throughput=5.0, max_latency_p95=1.0)
        # 10 pages with p95 = 1.8s
        lats = [0.1] * 9 + [1.8]
        report = runner.run_benchmark(lats, total_duration_sec=1.5)
        assert report["sla_passed"] is False

    def test_sla_throughput_violation(self):
        runner = BenchmarkRunner(target_throughput=5.0, max_latency_p95=1.0)
        # 2 pages in 1.0s -> 2.0 p/s (< 5.0)
        report = runner.run_benchmark([0.1, 0.1], total_duration_sec=1.0)
        assert report["sla_passed"] is False

    def test_run_load_test_execution(self, tmp_path):
        runner = BenchmarkRunner(output_dir=tmp_path)
        report = runner.run_load_test(
            num_pages=6,
            concurrency=2,
            batch_size=2,
            use_synthetic=True,
            save_scorecard=True,
            scorecard_filename="load_test_scorecard.json",
        )
        assert report["total_pages"] == 6
        assert report["total_duration_sec"] > 0
        assert "scorecard" in report
        assert (tmp_path / "load_test_scorecard.json").exists()

    def test_load_benchmark_runner_contract(self):
        runner = LoadBenchmarkRunner(duration_sec=5, concurrency=2, target_pages=10)
        res = runner.run()
        assert res["total_pages"] == 10
        assert res["pages_per_sec"] > 0
        assert "quantiles" in res
        assert "p50" in res["quantiles"]

    def test_load_benchmark_runner_boundaries(self):
        # Zero duration
        r0 = LoadBenchmarkRunner(duration_sec=0)
        assert r0.run()["total_pages"] == 0

        # Invalid concurrency
        with pytest.raises(ValueError, match="concurrency"):
            LoadBenchmarkRunner(concurrency=0)


# ============================================================================
# 5. Resource Monitor & Memory Leak Detector Tests
# ============================================================================

class TestResourceMonitorAndMemoryLeakDetector:
    def test_resource_monitor_lifecycle(self):
        monitor = ResourceMonitor(interval_sec=0.01)
        monitor.start()
        time.sleep(0.06)
        summary = monitor.stop()

        assert summary["sample_count"] >= 3
        assert summary["peak_rss_mb"] > 0
        assert len(monitor.ram_rss_mb) == summary["sample_count"]
        assert len(monitor.cpu_pct) == summary["sample_count"]

    def test_ols_slope_stable_profile(self):
        detector = MemoryLeakDetector()
        pages = list(range(1, 201))
        # Flat 200MB memory profile with slight noise
        rss = [200.0 + (p * 0.0001) for p in pages]
        res = detector.compute_ols_slope(pages, rss, warmup_pages=50)

        assert res["is_zero_leak"] is True
        assert res["slope_mb_per_page"] <= 0.005
        assert res["analyzed_samples"] == 150

    def test_ols_slope_leaking_profile(self):
        detector = MemoryLeakDetector()
        pages = list(range(1, 201))
        # Leaking profile: 0.08 MB per page
        rss = [200.0 + (p * 0.08) for p in pages]
        res = detector.compute_ols_slope(pages, rss, warmup_pages=50)

        assert res["is_zero_leak"] is False
        assert res["slope_mb_per_page"] > 0.005

    def test_ols_slope_edge_cases(self):
        # Empty arrays
        assert compute_ols_slope([], []) == 0.0
        # Single element
        assert compute_ols_slope([1], [100.0]) == 0.0
        # Zero variance denominator (identical x values)
        assert compute_ols_slope([1, 1, 1], [100.0, 105.0, 110.0]) == 0.0

        # Mismatched lengths
        with pytest.raises(ValueError):
            MemoryLeakDetector.compute_ols_slope([1, 2], [100.0])


# ============================================================================
# 6. Chaos Fault Injection & Stress Suite Tests
# ============================================================================

class TestChaosAndStressSuite:
    def test_chaos_corrupt_page_faults(self):
        res = ChaosInjector.simulate_corrupt_page_faults(total_pages=12, corrupt_indices=[2, 5, 9])
        assert res["total_pages"] == 12
        assert res["successful_count"] == 9
        assert res["failed_count"] == 3
        assert res["failed_pages"] == [2, 5, 9]
        assert res["isolation_verified"] is True

    def test_chaos_worker_fault_and_retry(self):
        res = ChaosInjector.simulate_worker_fault_and_retry(num_fault_tasks=5, max_retries=3)
        assert res["num_fault_tasks"] == 5
        assert res["dlq_quarantined"] == 5
        assert res["retries_scheduled"] == 15  # 3 retries * 5 tasks
        assert res["quarantine_success"] is True

    def test_stress_test_runner_simulated_contract(self):
        runner = StressTestRunner(page_count=50, leak_threshold_mb_per_page=0.005)
        # Stable run
        r_pass = runner.run(simulated_leak_slope=0.0)
        assert r_pass["passed"] is True
        assert r_pass["ols_slope_mb_per_page"] <= 0.005

        # Leaking run
        r_fail = runner.run(simulated_leak_slope=0.02)
        assert r_fail["passed"] is False

    def test_fd_stability_test(self, tmp_path):
        runner = StressTestRunner(output_dir=tmp_path)
        res = runner.run_fd_stability_test(iterations=10, tmp_dir=tmp_path)
        assert res["passed"] is True
        assert res["delta_fds"] <= 2

    def test_1000_page_continuous_stress_simulation(self, tmp_path):
        runner = StressTestRunner(output_dir=tmp_path, max_rss_growth_mb=80.0)
        # Run 200 pages in windows of 16 for fast unit testing
        res = runner.run_1000_page_stress_test(
            total_pages=200,
            chunk_size=16,
            sample_interval=40,
            warmup_pages=40,
            use_engine=False,
        )
        assert res["total_pages"] == 200
        assert res["zero_leak_passed"] is True
        assert res["ols_slope_mb_per_page"] <= 0.005
        assert res["net_growth_mb"] <= 80.0

    def test_full_stress_suite_and_report_save(self, tmp_path):
        runner = StressSuiteRunner(output_dir=tmp_path)
        res = runner.run_full_stress_suite(total_pages=100, use_engine=False)
        assert "1000_page_stress" in res["stress_suite"]
        assert "fault_recovery" in res["stress_suite"]
        assert "fd_stability" in res["stress_suite"]

        report_file = runner.save_report("test_stress_report.json")
        assert report_file.exists()
        loaded = json.loads(report_file.read_text(encoding="utf-8"))
        assert "stress_suite" in loaded


# ============================================================================
# 7. Prometheus & Telemetry Integration Tests
# ============================================================================

class TestPrometheusTelemetryIntegration:
    def test_prometheus_metrics_registry(self):
        metrics = _get_prometheus_metrics()
        assert "jobs_total" in metrics
        assert "job_duration_seconds" in metrics
        assert "pages_total" in metrics
        assert "page_duration_seconds" in metrics
        assert "worker_memory_bytes" in metrics

    def test_record_telemetry_events(self):
        TelemetryTracker.record_job_metrics(
            job_id="test_job_eval_1",
            duration_sec=0.25,
            pages_count=4,
            success=True,
            engine="rapidocr",
        )
        TelemetryTracker.record_page_metrics(
            engine="rapidocr",
            route="onnx_batched",
            duration_sec=0.06,
            confidence=0.99,
            success=True,
            page_number=1,
        )
        TelemetryTracker.record_worker_memory(rss_bytes=128 * 1024 * 1024)

    def test_structured_log_emission(self, caplog):
        with caplog.at_level(logging.INFO, logger="blast_ocr.telemetry"):
            TelemetryTracker.emit_event("benchmark_milestone_4", {"status": "verified"})
            found = False
            for record in caplog.records:
                try:
                    data = json.loads(record.message)
                    if data.get("event") == "benchmark_milestone_4":
                        assert data["data"]["status"] == "verified"
                        found = True
                        break
                except Exception:
                    continue
            assert found


# ============================================================================
# 8. CLI Functional Tests
# ============================================================================

class TestBenchmarkAndStressCLI:
    def test_benchmark_load_cli_execution(self, tmp_path):
        scorecard_file = tmp_path / "cli_scorecard.json"
        cmd = [
            sys.executable,
            "-m",
            "eval.benchmark_load",
            "--pages",
            "8",
            "--concurrency",
            "2",
            "--batch-size",
            "4",
            "--output",
            str(tmp_path),
            "--dry-run",
            "--scorecard-file",
            str(scorecard_file.name),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        assert result.returncode == 0
        assert scorecard_file.exists()
        loaded = json.loads(scorecard_file.read_text(encoding="utf-8"))
        assert loaded["summary"]["total_pages"] == 8

    def test_stress_suite_cli_execution(self, tmp_path):
        report_file = tmp_path / "cli_stress.json"
        cmd = [
            sys.executable,
            "-m",
            "eval.stress_suite",
            "--pages",
            "50",
            "--chunk-size",
            "10",
            "--output",
            str(tmp_path),
            "--chaos",
            "--dry-run",
            "--report-file",
            str(report_file.name),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0
        assert report_file.exists()
        loaded = json.loads(report_file.read_text(encoding="utf-8"))
        assert "stress_suite" in loaded
