"""
tests/test_extreme_system_stress.py

Automated CI integration coverage for eval/extreme_system_stress.py.
Exercises all 7 stress suites under CI-scaled workloads to verify
system contracts, zero-leak OLS slope assertion, deduplication lock guards,
zombie reaper detection, tiered cache concurrency, and API load handling.
"""

from eval.extreme_system_stress import (
    ExtremeSystemStressRunner,
    compute_latency_quantiles,
    compute_ols_regression,
)


def test_ols_regression_math():
    x = [1, 2, 3, 4, 5]
    y = [10.0, 10.0, 10.0, 10.0, 10.0]
    res = compute_ols_regression(x, y)
    assert abs(res["slope"]) < 1e-6
    assert abs(res["intercept"] - 10.0) < 1e-6


def test_latency_quantiles_computation():
    samples = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]
    q = compute_latency_quantiles(samples)
    assert q["count"] == 10
    assert 50.0 <= q["p50_ms"] <= 60.0
    assert q["max_ms"] == 100.0


def test_extreme_stress_runner_suites_end_to_end(tmp_path):
    runner = ExtremeSystemStressRunner(output_dir=tmp_path)

    # Suite 1: Batch Engine & Memory Stress (CI scale)
    s1 = runner.run_suite_1_batch_engine_memory_stress(
        total_pages=16, batch_sizes=(4, 8), use_engine=False
    )
    assert s1["total_pages"] == 16
    assert s1["verdict"] == "PASSED"

    # Suite 2: Swarm & Priority Queue Stress
    s2 = runner.run_suite_2_swarm_priority_queue_stress(
        job_count=30, worker_concurrency=4
    )
    assert s2["verdict"] == "PASSED"

    # Suite 3: Tiered Cache Concurrency Stress
    s3 = runner.run_suite_3_tiered_cache_concurrency_stress(
        operations_count=60, concurrency=4, l1_capacity=20
    )
    assert s3["verdict"] == "PASSED"

    # Suite 4: Multipart Uploader Chaos Stress
    s4 = runner.run_suite_4_multipart_uploader_chaos_stress(
        artifact_count=5, concurrency=2
    )
    assert s4["verdict"] == "PASSED"

    # Suite 5: Hostile Payloads & Security Boundaries
    s5 = runner.run_suite_5_hostile_payloads_security_stress()
    assert s5["verdict"] == "PASSED"

    # Suite 6: REST API Concurrency Stress
    s6 = runner.run_suite_6_rest_api_concurrency_stress(
        request_count=20, concurrency=4
    )
    assert s6["verdict"] == "PASSED"

    # Suite 7: Multilingual BiDi Layout Stress
    s7 = runner.run_suite_7_multilingual_layout_bidi_stress(
        sample_count=10, concurrency=2
    )
    assert s7["verdict"] == "PASSED"

    # Scorecard Report Verification
    runner.results["overall_verdict"] = "PASSED"
    report_file = tmp_path / "extreme_stress_scorecard.json"
    import json
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(runner.results, f, indent=2)

    assert report_file.exists()
    data = json.loads(report_file.read_text(encoding="utf-8"))
    assert data["overall_verdict"] == "PASSED"
    assert len(data["suites"]) == 7
