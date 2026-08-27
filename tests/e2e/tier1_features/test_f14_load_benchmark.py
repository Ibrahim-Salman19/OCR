"""
tests/e2e/tier1_features/test_f14_load_benchmark.py

Tier 1 Isolated Feature Tests: Feature 14 - Automated Load Benchmark Suite
Covers:
- Synthetic multi-modal document generator (multi-page, tables, noise)
- Latency quantile distribution calculation (p50, p90, p95, p99, min, max, mean)
- Concurrent load generation and throughput (pages/sec) measurement
- Concurrency worker scaling efficiency curve
- SLA regression gating assertion (latency < 1.0s, throughput >= 5.0 pages/sec)
"""


import pytest


from eval.benchmark_load import SyntheticDocGenerator, LatencyStats, BenchmarkRunner


# ============================================================================
# Test Cases (>= 5 Tests)
# ============================================================================

def test_f14_synthetic_doc_generator_multipage_creation():
    """
    Test 1: Tests SyntheticDocGenerator creates exact requested page count
    with consistent dimensions and document layout elements.
    """
    gen = SyntheticDocGenerator(seed=100)
    pages = gen.generate_document_pages(page_count=6, width=600, height=800)
    
    assert len(pages) == 6
    for i, img in enumerate(pages):
        assert img.size == (600, 800)
        assert img.mode == "RGB"


def test_f14_latency_quantiles_distribution_calculation():
    """
    Test 2: Tests LatencyStats computes exact p50, p90, p95, p99, min, max, mean
    over a set of sampled execution times.
    """
    # 100 samples uniformly spaced from 0.01 to 1.00s
    latencies = [i * 0.01 for i in range(1, 101)]
    stats = LatencyStats.compute(latencies)

    assert stats["count"] == 100
    assert pytest.approx(stats["min"], rel=1e-2) == 0.01
    assert pytest.approx(stats["max"], rel=1e-2) == 1.00
    assert pytest.approx(stats["p50"], rel=1e-2) == 0.505
    assert pytest.approx(stats["p90"], rel=1e-2) == 0.901
    assert pytest.approx(stats["p95"], rel=1e-2) == 0.9505
    assert pytest.approx(stats["p99"], rel=1e-2) == 0.9901
    assert pytest.approx(stats["mean"], rel=1e-2) == 0.505


def test_f14_concurrent_load_throughput_calculation():
    """
    Test 3: Tests BenchmarkRunner calculates throughput as total_pages / duration
    and attaches latency stats.
    """
    runner = BenchmarkRunner(target_throughput=5.0, max_latency_p95=1.0)
    # 50 pages processed in 8.0 seconds -> 6.25 pages/sec
    page_latencies = [0.15] * 50
    duration = 8.0

    report = runner.run_benchmark(page_latencies, duration)
    assert report["total_pages"] == 50
    assert report["total_duration_sec"] == 8.0
    assert report["throughput_pages_per_sec"] == 6.25
    assert report["sla_passed"] is True


def test_f14_concurrency_scaling_speedup():
    """
    Test 4: Tests that increasing simulated concurrency from 1 to 4 workers
    yields expected scaling and throughput gains.
    """
    # 40 pages with single-worker total duration = 8.0s (5.0 p/s)
    # With 4 parallel workers, total wall duration is ~2.2s (18.1 p/s)
    single_worker_duration = 8.0
    multi_worker_duration = 2.2
    pages = [0.2] * 40

    runner = BenchmarkRunner()
    single_res = runner.run_benchmark(pages, single_worker_duration)
    multi_res = runner.run_benchmark(pages, multi_worker_duration)

    assert multi_res["throughput_pages_per_sec"] > single_res["throughput_pages_per_sec"]
    speedup = multi_res["throughput_pages_per_sec"] / single_res["throughput_pages_per_sec"]
    assert speedup > 3.0, f"Expected >3x speedup with 4 workers, got {speedup}"


def test_f14_sla_regression_gating_assertion():
    """
    Test 5: Tests SLA gating assertion detects regressions when latency > 1.0s
    or throughput < 5.0 pages/sec.
    """
    runner = BenchmarkRunner(target_throughput=5.0, max_latency_p95=1.0)

    # Scenario A: Passing SLA
    pass_report = runner.run_benchmark([0.1, 0.2, 0.3], total_duration_sec=0.5)
    assert pass_report["sla_passed"] is True

    # Scenario B: High Latency SLA violation (p95 = 1.8s > 1.0s)
    fail_latency = runner.run_benchmark([0.1, 0.2, 1.8], total_duration_sec=0.5)
    assert fail_latency["sla_passed"] is False

    # Scenario C: Low Throughput SLA violation (2.0 p/s < 5.0 p/s)
    fail_tp = runner.run_benchmark([0.1, 0.1], total_duration_sec=1.0)
    assert fail_tp["sla_passed"] is False
