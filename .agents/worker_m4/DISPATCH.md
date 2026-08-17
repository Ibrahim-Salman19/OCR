# DISPATCH — worker_m4

## 2026-08-15T18:54:35Z

**Task**: Implement Milestone 4 (Automated Benchmarking & Stress-Testing Suite in `eval/`)
**Working Directory**: `/mnt/d/code/Projects/Python/OCR_Book/.agents/worker_m4`
**Scope Document**: `/mnt/d/code/Projects/Python/OCR_Book/PROJECT.md`
**Original Request**: `/mnt/d/code/Projects/Python/OCR_Book/.agents/ORIGINAL_REQUEST.md`
**Survey Blueprint**: `/mnt/d/code/Projects/Python/OCR_Book/.agents/survey_explorer_3/report.md`

### Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

### Implementation Checklist
1. `eval/benchmark_load.py`:
   - Synthetic multi-modal document generator (1 to 1,000 pages with realistic text, headings, tables).
   - Concurrent worker load tester (1..N workers) with warm-up runs and high-precision timing.
   - Latency quantile calculations: p50, p90, p95, p99, and overall throughput (pages/sec).
   - High-frequency resource monitor sampling CPU %, RSS RAM (MB), VRAM (if GPU available), and open file descriptors.
   - Prometheus metrics generation and structured JSON scorecard export to `eval/results/benchmark_<timestamp>.json`.
   - CLI flags: `--pages`, `--workers`, `--batch-size`, `--duration`, `--output-json`, `--export-prometheus`.
2. `eval/stress_suite.py`:
   - 1,000-page continuous simulated load test verifying bounded memory and zero leaks.
   - Memory leak detection using Ordinary Least Squares (OLS) linear regression on RSS over page count (assert slope $\le 0.005\text{MB/page}$ and absolute delta $\le 60\text{MB}$).
   - Chaos fault recovery harness (worker kill simulation, corrupt image handling, network drop, S3 retry recovery).
   - CLI flags: `--continuous-pages`, `--assert-zero-leak`, `--chaos-failures`, `--output-report`.
3. `tests/test_benchmark_eval.py`:
   - Unit and integration tests for `eval/benchmark_load.py` and `eval/stress_suite.py` ensuring CLI execution, JSON schema output validity, quantile calculations, and OLS regression analysis.
4. Run `pytest tests/test_benchmark_eval.py -v` and `pytest` for 0 regressions.
5. Write `handoff.md` and report completion.
