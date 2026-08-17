"""
eval module: B.L.A.S.T. OCR Evaluation, Load Benchmarking, and Stress Suite.
"""

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
from eval.metrics import (
    compute_cer,
    compute_wer,
    reading_order_tau,
    run_fact_checks,
    compute_teds,
    FactCheckResult,
)
from eval.benchmark_suite import BenchmarkSuite
from eval.gold_loader import normalize_whitespace, tokenize

__all__ = [
    "SyntheticDocGenerator",
    "LatencyStats",
    "calculate_quantiles",
    "BenchmarkScorecard",
    "MetricsAggregator",
    "BenchmarkRunner",
    "LoadBenchmarkRunner",
    "run_load_benchmark",
    "ResourceMonitor",
    "MemoryLeakDetector",
    "compute_ols_slope",
    "ChaosInjector",
    "StressTestRunner",
    "StressSuiteRunner",
    "compute_cer",
    "compute_wer",
    "reading_order_tau",
    "run_fact_checks",
    "compute_teds",
    "FactCheckResult",
    "BenchmarkSuite",
    "normalize_whitespace",
    "tokenize",
]
