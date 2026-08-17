# Worker M4 Dispatch Instructions

## Working Directory
`/mnt/d/code/Projects/Python/OCR_Book/.agents/worker_m4_v2`

## Scope
Milestone 4: Automated Benchmarking, 1,000-page Stress Suite, and Prometheus/JSON Telemetry
Features:
- F14: Automated Load Benchmark Suite (`eval/benchmark_load.py`):
  - End-to-end load testing CLI measuring throughput (pages/sec), latency quantiles (p50/p90/p95/p99), GPU/CPU utilization, and Prometheus `/metrics` + JSON scorecard export.
  - Multi-worker concurrent load generator with synthetic and real document ingestion.
- F15: 1,000-Page Zero-Leak Stress Suite (`eval/stress_suite.py`):
  - Continuous 1,000-page simulated load test verifying zero memory leaks.
  - Linear regression / OLS slope verification ($\le 0.005\text{MB/page}$, total RSS delta $\le 60\text{MB}$).
  - Chaos fault injection (worker kill / timeout recovery).
- F16: Prometheus & JSON Telemetry (`eval/benchmark_load.py` & `blast_ocr` telemetry):
  - Prometheus metrics exporter (`blast_ocr_throughput_pages_total`, `blast_ocr_page_latency_seconds`, `blast_ocr_worker_rss_bytes`).
  - Structured JSON scorecard generation with timestamp, system metadata, throughput, latency quantiles, and memory metrics.
- Dedicated unit tests: `tests/test_benchmark_eval.py`.

## Reference Files
- `/mnt/d/code/Projects/Python/OCR_Book/.agents/ORIGINAL_REQUEST.md` (MANDATORY TO READ)
- `/mnt/d/code/Projects/Python/OCR_Book/PROJECT.md`
- `/mnt/d/code/Projects/Python/OCR_Book/TEST_READY.md`
- `eval/metrics.py`, `eval/gold_loader.py`
- `tests/e2e/tier1_features/test_f14_load_benchmark.py`, `test_f15_stress_suite.py`, `test_f16_telemetry_metrics.py`

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Completion Criteria
1. Fully working implementations of `eval/benchmark_load.py` and `eval/stress_suite.py`.
2. Dedicated comprehensive unit test suite in `tests/test_benchmark_eval.py`.
3. All tests passing via `pytest tests/test_benchmark_eval.py -v` and `pytest tests/e2e/tier1_features/test_f14_load_benchmark.py tests/e2e/tier1_features/test_f15_stress_suite.py tests/e2e/tier1_features/test_f16_telemetry_metrics.py -v`.
4. Complete `handoff.md` with verified test commands and output.
