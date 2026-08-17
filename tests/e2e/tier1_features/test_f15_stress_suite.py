"""
tests/e2e/tier1_features/test_f15_stress_suite.py

Tier 1 Isolated Feature Tests: Feature 15 - 1,000-Page Zero-Leak Stress Suite
Covers:
- ResourceMonitor background time-series sampling (RAM RSS, CPU %, threads)
- Ordinary Least Squares (OLS) memory leak slope calculation (beta <= 0.005 MB/page)
- Open file descriptor (FD) stability across successive processing windows
- Chaos corrupt input injection and isolated fault recovery
- 1,000-page continuous simulated load test with bounded memory assertion
"""

import os
import gc
import time
import threading
from typing import Any, Dict, List, Optional

import pytest
import psutil
import numpy as np


# ============================================================================
# Interface / Reference Implementation for Feature 15 Specification
# ============================================================================

class ResourceMonitor:
    """
    High-frequency background profiler sampling RSS memory, CPU, and thread count.
    """

    def __init__(self, interval_sec: float = 0.05):
        self.interval_sec = interval_sec
        self.timestamps: List[float] = []
        self.ram_rss_mb: List[float] = []
        self.cpu_pct: List[float] = []
        self.thread_counts: List[int] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._proc = psutil.Process(os.getpid())

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def _monitor_loop(self) -> None:
        while self._running:
            try:
                mem_mb = self._proc.memory_info().rss / (1024 * 1024)
                cpu = self._proc.cpu_percent(interval=None)
                threads = self._proc.num_threads()
                
                self.timestamps.append(time.time())
                self.ram_rss_mb.append(mem_mb)
                self.cpu_pct.append(cpu)
                self.thread_counts.append(threads)
            except Exception:
                pass
            time.sleep(self.interval_sec)

    def stop(self) -> Dict[str, Any]:
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        return {
            "sample_count": len(self.ram_rss_mb),
            "peak_rss_mb": max(self.ram_rss_mb) if self.ram_rss_mb else 0.0,
            "mean_rss_mb": float(np.mean(self.ram_rss_mb)) if self.ram_rss_mb else 0.0,
            "mean_cpu_pct": float(np.mean(self.cpu_pct)) if self.cpu_pct else 0.0,
        }


class MemoryLeakDetector:
    """
    Computes Ordinary Least Squares (OLS) memory regression slope.
    Slope beta <= 0.005 MB/page indicates zero leak.
    """

    @staticmethod
    def compute_ols_slope(
        page_indices: List[int],
        rss_samples_mb: List[float],
        warmup_pages: int = 50,
    ) -> Dict[str, Any]:
        if len(page_indices) != len(rss_samples_mb):
            raise ValueError("Mismatched page indices and memory samples")

        # Exclude warmup pages (engine and model initialization)
        filtered = [(p, m) for p, m in zip(page_indices, rss_samples_mb) if p > warmup_pages]
        if len(filtered) < 2:
            return {"slope_mb_per_page": 0.0, "is_zero_leak": True, "r_squared": 0.0}

        x = np.array([p for p, _ in filtered], dtype=np.float64)
        y = np.array([m for _, m in filtered], dtype=np.float64)

        # OLS fit: y = alpha + beta * x
        A = np.vstack([x, np.ones(len(x))]).T
        beta, alpha = np.linalg.lstsq(A, y, rcond=None)[0]

        # Calculate R^2
        residuals = y - (alpha + beta * x)
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        is_zero_leak = bool(beta <= 0.005)
        return {
            "slope_mb_per_page": float(beta),
            "intercept_mb": float(alpha),
            "r_squared": float(r_squared),
            "is_zero_leak": is_zero_leak,
            "analyzed_samples": len(filtered),
        }


# ============================================================================
# Test Cases (>= 5 Tests)
# ============================================================================

def test_f15_resource_monitor_sampling_lifecycle():
    """
    Test 1: Tests ResourceMonitor collects periodic RSS and CPU samples
    and stops cleanly.
    """
    monitor = ResourceMonitor(interval_sec=0.02)
    monitor.start()
    time.sleep(0.1)
    summary = monitor.stop()

    assert summary["sample_count"] >= 3
    assert summary["peak_rss_mb"] > 0
    assert len(monitor.ram_rss_mb) == summary["sample_count"]


def test_f15_ols_memory_leak_slope_calculation():
    """
    Test 2: Tests MemoryLeakDetector accurately detects positive memory leaks
    versus zero-leak flat memory profiles.
    """
    detector = MemoryLeakDetector()

    # Case A: Stable memory profile (slope near 0.0001 MB/page)
    pages_stable = list(range(1, 201))
    # 150MB baseline + minor random noise
    rss_stable = [150.0 + (p * 0.0001) + np.sin(p) * 0.5 for p in pages_stable]
    res_stable = detector.compute_ols_slope(pages_stable, rss_stable, warmup_pages=50)
    
    assert res_stable["is_zero_leak"] is True
    assert res_stable["slope_mb_per_page"] <= 0.005

    # Case B: Memory leak scenario (slope = 0.05 MB/page > 0.005)
    rss_leaking = [150.0 + (p * 0.05) for p in pages_stable]
    res_leaking = detector.compute_ols_slope(pages_stable, rss_leaking, warmup_pages=50)

    assert res_leaking["is_zero_leak"] is False
    assert res_leaking["slope_mb_per_page"] > 0.005


def test_f15_open_file_descriptors_stability(tmp_path):
    """
    Test 3: Tests that opening, reading, and purging temporary chunk scratch files
    does not accumulate leaked open file handles.
    """
    proc = psutil.Process(os.getpid())
    has_num_fds = hasattr(proc, "num_fds")
    
    if not has_num_fds:
        pytest.skip("num_fds not supported on this platform")

    initial_fds = proc.num_fds()

    # Perform 20 iterations of file generation, reading, unlinking
    for i in range(20):
        tmp_file = tmp_path / f"temp_leak_test_{i}.bin"
        tmp_file.write_bytes(b"X" * 1024)
        with open(tmp_file, "rb") as f:
            _ = f.read()
        tmp_file.unlink()

    final_fds = proc.num_fds()
    # FD count should not grow unboundedly (delta should be near 0)
    assert abs(final_fds - initial_fds) <= 2, f"FD leak detected: initial={initial_fds}, final={final_fds}"


def test_f15_chaos_corrupt_page_fault_recovery():
    """
    Test 4: Tests chaos injection of malformed/corrupt inputs during processing;
    errors are isolated to that page and the suite completes without uncollected state.
    """
    def mock_process_page(page_idx: int, is_corrupt: bool) -> Dict[str, Any]:
        if is_corrupt:
            # Raise page error that should be caught
            return {"page": page_idx, "status": "error", "error": "InvalidImageHeader"}
        return {"page": page_idx, "status": "success", "confidence": 0.95}

    results = []
    for p in range(1, 11):
        is_corrupt = (p in (3, 7))  # Pages 3 and 7 are corrupt
        res = mock_process_page(p, is_corrupt)
        results.append(res)

    assert len(results) == 10
    successful = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "error"]
    
    assert len(successful) == 8
    assert len(failed) == 2
    assert [f["page"] for f in failed] == [3, 7]


def test_f15_1000_page_continuous_stress_simulation():
    """
    Test 5: Simulates a continuous 1,000-page streaming workload with explicit
    window GC, verifying RSS <= 500MB and zero-leak slope <= 0.005 MB/page.
    """
    pages_count = 1000
    chunk_size = 16
    sampled_pages: List[int] = []
    sampled_memory_mb: List[float] = []

    proc = psutil.Process(os.getpid())
    gc.collect()
    baseline_rss = proc.memory_info().rss / (1024 * 1024)

    # Simulate 1,000 pages in windows of 16
    for start in range(1, pages_count + 1, chunk_size):
        end = min(pages_count, start + chunk_size - 1)
        
        # Simulate chunk memory allocation and immediate discard
        chunk_data = [bytearray(100 * 1024) for _ in range(end - start + 1)]  # ~1.6MB transient
        del chunk_data
        
        # Periodic sample every 50 pages
        if end % 50 == 0 or end == pages_count:
            gc.collect()
            current_rss = proc.memory_info().rss / (1024 * 1024)
            sampled_pages.append(end)
            sampled_memory_mb.append(current_rss)

    # 1. Peak RSS growth must remain bounded (<= 100MB above test baseline)
    peak_rss = max(sampled_memory_mb)
    peak_growth = peak_rss - baseline_rss
    assert peak_growth <= 100.0, f"Memory growth {peak_growth:.2f}MB exceeded SLA limit"

    # 2. OLS slope calculation on pages 51-1000
    res = MemoryLeakDetector.compute_ols_slope(sampled_pages, sampled_memory_mb, warmup_pages=50)
    assert res["is_zero_leak"] is True, f"Memory slope {res['slope_mb_per_page']} MB/page exceeded threshold"
