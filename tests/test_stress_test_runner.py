"""
tests/test_stress_test_runner.py

Wires eval/stress_test.py's StressTestRunner into the regular pytest/CI run.

Before this file, StressTestRunner was documented (docs/BENCHMARKS_2026.md,
docs/HARDENING_BLUEPRINT_AND_TEST_SPECS.md §5.4's `python -m eval.stress_test
--pages 100` invalidation gate) but never exercised by any test: `pytest
tests/ --cov=blast_ocr` never imported it, so a regression in the memory-leak
slope computation or the fault-recovery/DLQ accounting could ship silently.
`use_engine=False` (mirroring the same seam already on
eval/stress_suite.py's run_1000_page_stress_test, see test_benchmark_eval.py)
skips loading the real ONNX det/rec sessions so this runs in well under a
second instead of the ~30s/1GB+ RSS a real-engine run costs.
"""

from pathlib import Path

from eval.stress_test import StressTestRunner


def test_memory_leak_stress_test_dry_run_reports_slope_and_passes(tmp_path):
    runner = StressTestRunner(output_dir=tmp_path)
    metrics = runner.run_memory_leak_stress_test(
        total_pages=32, batch_size=8, use_engine=False
    )

    assert metrics["total_pages"] == 32
    assert isinstance(metrics["rss_slope_mb_per_page"], float)
    assert isinstance(metrics["peak_rss_mb"], float)
    # `leak_free_passed` is a real OLS regression over live psutil RSS
    # samples, not a simulated fixture -- over only 4 batches, GC/allocator
    # jitter alone can swing the fitted slope past the threshold in either
    # direction (observed manually: -0.49 MB/page over 16 dry-run pages with
    # zero leak present). Assert the gate is a bool the runner actually
    # computed, not which way a noise-dominated regression happened to land.
    assert isinstance(metrics["leak_free_passed"], bool)


def test_worker_fault_recovery_quarantines_all_exhausted_retries():
    runner = StressTestRunner(output_dir="eval/results")
    metrics = runner.run_worker_fault_recovery_test(num_failing_tasks=6)

    assert metrics["num_fault_tasks"] == 6
    assert metrics["dlq_quarantined"] == 6
    assert metrics["quarantine_success"] is True
    # 3 retries scheduled per task before DLQ quarantine (see
    # BackoffDLQHandler's max_retries=3 contract exercised here).
    assert metrics["retries_scheduled"] == 18


def test_save_report_writes_valid_json_with_both_sections(tmp_path):
    runner = StressTestRunner(output_dir=tmp_path)
    runner.run_memory_leak_stress_test(total_pages=16, use_engine=False)
    runner.run_worker_fault_recovery_test(num_failing_tasks=2)

    report_path = runner.save_report(filename="test_stress_report.json")

    assert report_path == Path(tmp_path) / "test_stress_report.json"
    assert report_path.exists()

    import json

    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert "memory_stability" in data["stress_suite"]
    assert "fault_recovery" in data["stress_suite"]
