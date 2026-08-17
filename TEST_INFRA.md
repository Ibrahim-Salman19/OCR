# E2E Test Infra: B.L.A.S.T. OCR High-Throughput Distributed Execution Engine

## Test Philosophy
- Opaque-box, requirement-driven. No dependency on implementation internals.
- Verification mechanism follows the 4-tier methodology (Category-Partition, Boundary Value Analysis, Pairwise Combinatorial Testing, Real-World Workload Testing).
- Tests assert against SLA targets: sub-1s single-page latency, >= 5.0 pages/sec batched throughput, bounded memory footprint, zero leaks on 1,000 pages, clean multi-worker distributed scaling, and automatic DLQ retry with backoff.

## Feature Inventory
| # | Feature | Source (Requirement) | Tier 1 (Features) | Tier 2 (Boundaries) | Tier 3 (Pairwise) | Tier 4 (Real-World) |
|---|---------|---------------------|:-----------------:|:-------------------:|:-----------------:|:-------------------:|
| 1 | Vectorized Batch Image Preprocessor | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 2 | Dynamic Batched ONNX Tensor Inference | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 3 | Multi-Page Tensor Decoding (CTC / DBNet) | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 4 | Execution Provider Hierarchy (GPU/CPU) | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 5 | 3-Tier Priority Queue Scheduling | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 6 | Distributed Multi-Worker Swarm | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 7 | Worker Heartbeat & Health Monitoring | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 8 | Zombie Job Reaper & Failover | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 9 | Exponential Backoff & DLQ Handling | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 10 | FastAPI Priority & Swarm Endpoints | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 11 | Bounded Streaming Buffer Chunking | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |
| 12 | Tiered OCR Cache (L1/L2) | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |
| 13 | Concurrent Object Storage Uploader | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |
| 14 | Automated Load Benchmark Suite | ORIGINAL_REQUEST §R4 | 5 | 5 | ✓ | ✓ |
| 15 | 1,000-Page Zero-Leak Stress Suite | ORIGINAL_REQUEST §R4 | 5 | 5 | ✓ | ✓ |
| 16 | Prometheus & JSON Telemetry Metrics | ORIGINAL_REQUEST §R4 | 5 | 5 | ✓ | ✓ |

## Test Architecture
- Test runner: `pytest tests/e2e/ -v`
- Directory layout:
  - `tests/e2e/tier1_features/`: Feature-level isolated requirement tests (>=5 per feature)
  - `tests/e2e/tier2_boundaries/`: Boundary value, zero/extreme/corrupt inputs (>=5 per feature)
  - `tests/e2e/tier3_combinations/`: Cross-feature combinatorial interactions (queue + GPU + streaming + storage)
  - `tests/e2e/tier4_real_world/`: High-volume multi-page book processing, swarm failover under load, S3 streaming archive uploads

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | 1,000-Page Large Archive Book Processing | F1, F2, F3, F11, F12, F13, F15 | High |
| 2 | High-Concurrency Mixed Priority Burst (Interactive vs Bulk) | F5, F6, F7, F10, F14 | High |
| 3 | Worker Crash & Network Outage Fault Recovery | F7, F8, F9, F13, F15 | High |
| 4 | Multi-Provider Dynamic Fallback (GPU -> CPU) Under Heavy Load | F2, F4, F14, F16 | Medium |
| 5 | Distributed Multi-Worker S3 Streaming Pipeline | F6, F10, F11, F13, F16 | High |

## Coverage Thresholds
- Tier 1: ≥5 test cases per feature ($5 \times 16 = 80$ test cases)
- Tier 2: ≥5 test cases per feature ($5 \times 16 = 80$ test cases)
- Tier 3: ≥16 pairwise combination test cases
- Tier 4: ≥8 real-world application workload test cases
- **Total Minimum Test Count: ≥ 184 E2E Test Cases**
