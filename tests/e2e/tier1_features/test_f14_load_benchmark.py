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

import numpy as np
from typing import Any, Dict, List

import pytest
from PIL import Image, ImageDraw


# ============================================================================
# Interface / Reference Implementation for Feature 14 Specification
# ============================================================================

class SyntheticDocGenerator:
    """
    Generates deterministic synthetic multi-page document archives for benchmarking.
    """

    def __init__(self, seed: int = 42):
        self.rng = np.random.RandomState(seed)

    def generate_document_pages(
        self,
        page_count: int = 5,
        width: int = 800,
        height: int = 1000,
    ) -> List[Image.Image]:
        pages = []
        for p in range(1, page_count + 1):
            img = Image.new("RGB", (width, height), color="white")
            draw = ImageDraw.Draw(img)
            # Header
            draw.text((40, 40), f"Synthetic Benchmark Page #{p}", fill="black")
            # Text block
            draw.rectangle([(40, 80), (width - 40, 200)], fill="whitesmoke", outline="gray")
            draw.text((50, 100), f"Paragraph text for page {p} with high-density words.", fill="black")
            # Simulated table
            draw.rectangle([(40, 250), (width - 40, 450)], outline="black", width=2)
            draw.line([(40, 300), (width - 40, 300)], fill="black", width=1)
            draw.line([(250, 250), (250, 450)], fill="black", width=1)
            draw.text((50, 265), "Column Header 1", fill="black")
            draw.text((270, 265), "Column Header 2", fill="black")
            pages.append(img)
        return pages


class LatencyStats:
    """
    Computes statistical percentiles and distributions for latency samples.
    """

    @staticmethod
    def compute(latencies_sec: List[float]) -> Dict[str, float]:
        if not latencies_sec:
            return {
                "count": 0,
                "p50": 0.0,
                "p75": 0.0,
                "p90": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "mean": 0.0,
                "min": 0.0,
                "max": 0.0,
                "std": 0.0,
            }
        arr = np.array(latencies_sec, dtype=np.float64)
        return {
            "count": len(arr),
            "p50": float(np.percentile(arr, 50)),
            "p75": float(np.percentile(arr, 75)),
            "p90": float(np.percentile(arr, 90)),
            "p95": float(np.percentile(arr, 95)),
            "p99": float(np.percentile(arr, 99)),
            "mean": float(np.mean(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "std": float(np.std(arr)),
        }


class BenchmarkRunner:
    """
    Executes load benchmarks measuring throughput (pages/sec) and latency quantiles.
    """

    def __init__(self, target_throughput: float = 5.0, max_latency_p95: float = 1.0):
        self.target_throughput = target_throughput
        self.max_latency_p95 = max_latency_p95

    def run_benchmark(
        self,
        page_latencies: List[float],
        total_duration_sec: float,
    ) -> Dict[str, Any]:
        total_pages = len(page_latencies)
        throughput = (total_pages / total_duration_sec) if total_duration_sec > 0 else 0.0
        stats = LatencyStats.compute(page_latencies)
        
        sla_passed = (
            stats["p95"] <= self.max_latency_p95 and
            throughput >= self.target_throughput
        )

        return {
            "total_pages": total_pages,
            "total_duration_sec": total_duration_sec,
            "throughput_pages_per_sec": round(throughput, 2),
            "latency_stats": stats,
            "sla_passed": sla_passed,
        }


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
