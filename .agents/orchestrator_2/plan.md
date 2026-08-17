# Plan — Orchestrator Generation 2

## Objective
Finalize and rigorously verify the B.L.A.S.T. OCR High-Throughput Distributed Execution Engine.

## Detailed Phase Breakdown

### Step 1: Schedule Heartbeat Cron
Establish a recurring cron to monitor subagents every 10 minutes.

### Step 2: Milestone 3 (Streaming Buffer & Tiered Storage Engine)
- Dispatch `worker_m3_v2` (`teamwork_preview_worker`) with scope:
  - Verify / finalize `blast_ocr/core/streaming.py`, `blast_ocr/cache/tiered_cache.py`, `blast_ocr/storage/concurrent_uploader.py`, `blast_ocr/storage/object_store.py`.
  - Ensure dedicated unit test suite `tests/test_streaming_storage.py` (and related tests) passes 100%.
  - Verify no memory spikes and bounded RSS $\le 500\text{MB}$.

### Step 3: Milestone 4 (Automated Benchmarks & 1,000-page Stress Suite)
- Dispatch `worker_m4_v2` (`teamwork_preview_worker`) with scope:
  - Implement `eval/benchmark_load.py` (load test CLI, throughput, latency quantiles p50/p90/p95/p99, Prometheus metrics export, JSON scorecard).
  - Implement `eval/stress_suite.py` (1,000-page continuous stress test, OLS memory slope verification $\le 0.005\text{MB/page}$, chaos fault recovery).
  - Implement `tests/test_benchmark_eval.py` asserting all CLI features, benchmark metrics, stress suite logic, and reporting.
  - Ensure test suite passes 100%.

### Step 4: Verification & Reviews (M3 & M4)
- Dispatch Reviewers (`teamwork_preview_reviewer`) and Challengers (`teamwork_preview_challenger`) for M3 & M4.
- Dispatch Forensic Auditor (`teamwork_preview_auditor`) to verify zero cheating, zero stubs, and genuine implementations.

### Step 5: Milestone 5 (Full E2E Pass, Hardening & Final Audit)
- Run complete test suite across the whole repository (`pytest`) ensuring 100% pass rate with 0 regressions.
- Dispatch adversarial challengers for coverage hardening.
- Conduct final forensic audit on the entire codebase.

### Step 6: Synthesis & Final Sentinel Notification
- Summarize results, metrics, and architecture.
- Notify Sentinel via `send_message`.
