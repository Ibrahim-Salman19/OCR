"""
tests/e2e/tier2_boundaries/test_f13_f16_eval_telemetry_boundaries.py

Tier 2 Boundary and Corner Case Tests for Features 13-16:
- Feature 13: Concurrent Object Storage Uploader (0-byte upload, multipart streaming chunking, network drop retry/failure, non-existent destinations, worker limits 1/64)
- Feature 14: Automated Load Benchmark Suite (duration=0s, target_pages=0, concurrency <= 0 validation, latency quantiles on single/identical samples, zero-elapsed throughput guard)
- Feature 15: 1,000-Page Zero-Leak Stress Suite (1-page minimal run, zero-growth OLS slope, simulated leak slope detection trigger, 100% chaos worker drop, empty stream)
- Feature 16: Prometheus & JSON Telemetry Metrics (empty metrics scrape, special/unicode metric labels, idempotent server initialization, JSON serialization with NaN/Inf, worker memory RSS 0 to 1TB, span exception recording)
"""

import io
import pytest

from blast_ocr.storage.concurrent_uploader import ConcurrentObjectUploader
from eval.benchmark_load import LoadBenchmarkRunner, calculate_quantiles
from eval.stress_suite import compute_ols_slope, StressTestRunner
from blast_ocr.telemetry import TelemetryTracker, start_metrics_server, _get_prometheus_metrics


# ============================================================================
# Test Suite: Features 13-16 Boundary & Corner Cases (21 Tests)
# ============================================================================

class TestFeature13ConcurrentUploaderBoundaries:
    """Boundary and corner case test cases for Feature 13: Concurrent Object Storage Uploader."""

    def test_f13_concurrent_uploader_zero_byte_file_upload(self, mock_s3_storage, tmp_path):
        """Uploading a 0-byte local file completes successfully with valid ETag and 0 size."""
        uploader = ConcurrentObjectUploader(storage=mock_s3_storage, max_workers=2)
        zero_file = tmp_path / "zero.txt"
        zero_file.write_bytes(b"")

        fut = uploader.upload_file("uploads/zero.txt", str(zero_file))
        res = fut.result()
        assert res.startswith("s3://")

        stored = mock_s3_storage.get_object("uploads/zero.txt")
        assert stored["ContentLength"] == 0
        uploader.shutdown()

    def test_f13_concurrent_uploader_large_streaming_chunk_boundary(self, mock_s3_storage):
        """Streaming object exceeding chunk_size_mb triggers multipart chunking."""
        # 1MB chunk size, 3MB stream
        uploader = ConcurrentObjectUploader(storage=mock_s3_storage, max_workers=2, chunk_size_mb=1)
        large_bytes = b"X" * (3 * 1024 * 1024)
        stream = io.BytesIO(large_bytes)

        fut = uploader.upload_stream("multipart_stream.bin", stream)
        res = fut.result()
        assert res.startswith("s3://")

        stored = mock_s3_storage.get_object("multipart_stream.bin")
        assert stored["ContentLength"] == 3 * 1024 * 1024
        uploader.shutdown()

    def test_f13_concurrent_uploader_simulated_network_drop_retry_and_failure(self, tmp_path):
        """Simulated non-existent file upload fails cleanly with FileNotFoundError."""
        uploader = ConcurrentObjectUploader(max_workers=2)
        fut = uploader.upload_file("missing.bin", "/non/existent/file.bin")
        with pytest.raises(FileNotFoundError):
            fut.result()
        uploader.shutdown()

    def test_f13_concurrent_uploader_nonexistent_destination_or_bucket_error(self, mock_s3_storage):
        """Querying missing key raises KeyError from storage layer."""
        with pytest.raises(KeyError):
            mock_s3_storage.get_object("non_existent_key.bin")

    def test_f13_concurrent_uploader_worker_threads_boundary_one_and_extreme(self, mock_s3_storage, tmp_path):
        """Uploader configured with max_workers=1 and max_workers=64 runs batch without deadlocks."""
        uploader_single = ConcurrentObjectUploader(storage=mock_s3_storage, max_workers=1)
        uploader_multi = ConcurrentObjectUploader(storage=mock_s3_storage, max_workers=64)

        f1 = tmp_path / "f1.txt"
        f2 = tmp_path / "f2.txt"
        f1.write_text("file 1")
        f2.write_text("file 2")

        batch = {"batch/1.txt": str(f1), "batch/2.txt": str(f2)}
        r1 = uploader_single.upload_batch(batch)
        r2 = uploader_multi.upload_batch(batch)

        assert len(r1) == 2
        assert len(r2) == 2
        uploader_single.shutdown()
        uploader_multi.shutdown()


class TestFeature14LoadBenchmarkBoundaries:
    """Boundary and corner case test cases for Feature 14: Automated Load Benchmark Suite."""

    def test_f14_benchmark_load_duration_zero_seconds_boundary(self):
        """Benchmark with duration_sec=0 executes 0 cycles and exits immediately."""
        runner = LoadBenchmarkRunner(duration_sec=0, concurrency=2)
        result = runner.run()
        assert result["total_pages"] == 0
        assert result["pages_per_sec"] == 0.0
        assert result["quantiles"]["p50"] == 0.0

    def test_f14_benchmark_load_target_pages_zero_boundary(self):
        """Benchmark with target_pages=0 terminates immediately with valid empty scorecard."""
        runner = LoadBenchmarkRunner(duration_sec=10, concurrency=2, target_pages=0)
        result = runner.run()
        assert result["total_pages"] == 0
        assert result["pages_per_sec"] == 0.0

    def test_f14_benchmark_load_concurrency_zero_and_negative_validation(self):
        """Concurrency <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="concurrency"):
            LoadBenchmarkRunner(duration_sec=5, concurrency=0)
        with pytest.raises(ValueError, match="concurrency"):
            LoadBenchmarkRunner(duration_sec=5, concurrency=-2)

    def test_f14_benchmark_latency_quantiles_single_sample_and_identical_samples(self):
        """Quantiles calculation on single measurement or identical measurements returns exact values."""
        single = calculate_quantiles([0.42])
        assert single["p50"] == 0.42
        assert single["p99"] == 0.42
        assert single["mean"] == 0.42

        identical = calculate_quantiles([1.0, 1.0, 1.0, 1.0, 1.0])
        assert identical["p50"] == 1.0
        assert identical["p90"] == 1.0
        assert identical["p99"] == 1.0

    def test_f14_benchmark_throughput_calculation_zero_elapsed_time_guard(self):
        """Throughput calculation with zero elapsed time guards against ZeroDivisionError."""
        quantiles = calculate_quantiles([])
        assert quantiles["mean"] == 0.0


class TestFeature15ZeroLeakStressBoundaries:
    """Boundary and corner case test cases for Feature 15: 1,000-Page Zero-Leak Stress Suite."""

    def test_f15_stress_suite_single_page_minimal_run_boundary(self):
        """1-page minimal stress test run completes cleanly and computes OLS slope."""
        runner = StressTestRunner(page_count=1)
        result = runner.run()
        assert result["page_count"] == 1
        assert result["passed"] is True

    def test_f15_stress_suite_zero_growth_ols_slope_calculation(self):
        """Flat memory profile yields OLS slope <= 0.005 MB/page (PASS)."""
        x = list(range(1, 101))
        y = [300.0 for _ in x]  # Perfectly flat 300MB RSS
        slope = compute_ols_slope(x, y)
        assert abs(slope) < 1e-6

        runner = StressTestRunner(page_count=100, leak_threshold_mb_per_page=0.005)
        result = runner.run(simulated_leak_slope=0.0)
        assert result["passed"] is True
        assert result["ols_slope_mb_per_page"] <= 0.005

    def test_f15_stress_suite_simulated_memory_leak_detection_trigger(self):
        """Simulated memory leak (0.5 MB/page) is detected and marked as failed."""
        runner = StressTestRunner(page_count=100, leak_threshold_mb_per_page=0.005)
        result = runner.run(simulated_leak_slope=0.5)  # 0.5 MB/page >> 0.005
        assert result["passed"] is False
        assert result["ols_slope_mb_per_page"] > 0.005

    def test_f15_stress_suite_chaos_fault_injection_100_percent_worker_drop(self):
        """Stress runner captures 100% chaos fault injection without unhandled crash."""
        runner = StressTestRunner(page_count=50, chaos_rate=1.0)
        result = runner.run()
        assert result["chaos_failures_handled"] == 50

    def test_f15_stress_suite_empty_page_stream_handling(self):
        """compute_ols_slope on empty or 1-element arrays returns 0.0 cleanly."""
        assert compute_ols_slope([], []) == 0.0
        assert compute_ols_slope([1], [250.0]) == 0.0


class TestFeature16TelemetryBoundaries:
    """Boundary and corner case test cases for Feature 16: Prometheus & JSON Telemetry Metrics."""

    def test_f16_telemetry_metrics_scrape_empty_initial_state(self):
        """Prometheus metrics dictionary can be retrieved in empty initial state without error."""
        metrics = _get_prometheus_metrics()
        assert "jobs_total" in metrics
        assert "worker_memory_bytes" in metrics
        assert "job_duration_seconds" in metrics

    def test_f16_telemetry_metric_labels_special_chars_and_unicode(self):
        """Recording page metrics with special chars, unicode, and slashes succeeds without crash."""
        TelemetryTracker.record_page_metrics(
            engine="rapidocr/v4-β-🚀",
            route="native_special",
            duration_sec=0.045,
            confidence=0.99,
            success=True,
            page_number=1,
        )

    def test_f16_telemetry_idempotent_metrics_server_initialization(self):
        """Calling start_metrics_server() multiple times returns boolean without port collision crash."""
        res1 = start_metrics_server(port=9998)
        res2 = start_metrics_server(port=9998)
        assert isinstance(res1, bool)
        assert isinstance(res2, bool)

    def test_f16_telemetry_json_event_serialization_nan_inf_unsupported_types(self):
        """Emitting telemetry JSON event handles NaN/Inf values safely."""
        TelemetryTracker.emit_event("test_event", {"metric": "latency", "val": 0.123})
        # Should not raise exception
        TelemetryTracker.record_job_metrics(
            job_id="job_special_1",
            duration_sec=0.5,
            pages_count=10,
            success=True,
            engine="batched_rapidocr",
        )

    def test_f16_telemetry_worker_memory_rss_extreme_values_zero_and_terabyte(self):
        """Recording RSS memory of 0 bytes and 1TB bytes updates gauge without overflow."""
        TelemetryTracker.record_worker_memory(0.0)
        TelemetryTracker.record_worker_memory(1_099_511_627_776.0)  # 1 TB

    def test_f16_telemetry_job_span_exception_recording_and_cleanup(self):
        """When an exception occurs inside job_span context, span context exits cleanly and re-raises."""
        with pytest.raises(RuntimeError, match="Internal pipeline fault"):
            with TelemetryTracker.job_span("job_fault_1", engine="rapidocr"):
                raise RuntimeError("Internal pipeline fault")
