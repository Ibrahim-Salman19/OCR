# Project: B.L.A.S.T. OCR High-Throughput Distributed Execution Engine

## Architecture
B.L.A.S.T. OCR (Benchmark-calibrated, Layout-aware, Accelerated, Scalable, Trustworthy OCR) is an enterprise-scale document processing and OCR engine.
The architecture comprises:
1. **Engine & Batch Inference Core (`blast_ocr.core`)**:
   - `batch_preprocessor`: Zero-disk in-memory PDF/image rasterization, SIMD tensor normalization, dynamic aspect-ratio crop bucketing.
   - `onnx_session`: Pluggable ONNX Runtime execution provider hierarchy (`TensorrtExecutionProvider` -> `CUDAExecutionProvider` -> `DmlExecutionProvider` -> `CPUExecutionProvider`) with intra/inter-op thread tuning.
   - `tensor_decoder`: Concurrent DBNet polygon extraction and vectorized CTC greedy decoding.
   - `engines.batched_rapidocr`: Batched RapidOCR engine implementing `process_batch` contract with dynamic batching.
2. **Distributed Queue & Multi-Worker Swarm (`blast_ocr.queue`)**:
   - `client`: 3-Tier priority queue client (`blast_ocr:queue:high`, `blast_ocr:queue:default`, `blast_ocr:queue:low`) with atomic Redis dequeuing.
   - `swarm`: SwarmSupervisor and SwarmWorker process pool for multi-worker management, graceful shutdown, and dynamic scaling.
   - `heartbeat`: Worker Heartbeat daemon monitoring worker health, CPU, memory RSS, and active task status.
   - `reaper`: Zombie Job Reaper for dead worker failover, zombie detection, and automatic requeuing.
   - `tasks`: Resilient execution wrapper with `classify_exception` exponential backoff retry and Dead-Letter Queue (DLQ) quarantine.
3. **Memory Management & Storage Streaming (`blast_ocr.core.streaming`, `blast_ocr.cache`, `blast_ocr.storage`)**:
   - `streaming`: `PageStreamGenerator` (yielding $K=8..16$ page windows) and `StreamDocumentWriter` (incremental chunk export with immediate scratch unlinking) bounding RAM $\le 500\text{MB}$ RSS during 1,000+ page runs.
   - `tiered_cache`: L1 In-Memory LRU Cache + L2 Asynchronous Disk/S3 spooling cache with background worker.
   - `concurrent_uploader`: Concurrent multipart S3/MinIO and local object storage streaming with connection pooling and retries.
4. **FastAPI Enterprise API (`blast_ocr.api`)**:
   - Priority job dispatching (`POST /v1/ocr/jobs`), worker monitoring (`/v1/workers`), queue inspection (`/v1/queues`), and DLQ retry/replay (`POST /v1/ocr/jobs/{id}/retry`).
5. **Evaluation, Benchmarking & Stress Testing (`eval/`)**:
   - `benchmark_load`: End-to-end load testing CLI measuring throughput (pages/sec), latency quantiles (p50/p90/p95/p99), GPU/CPU utilization, and Prometheus `/metrics` + JSON scorecard export.
   - `stress_suite`: 1,000-page continuous stress test verifying zero memory leaks (OLS slope $\le 0.005\text{MB/page}$) and chaos failure recovery.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Vectorized Image Preprocessor | Zero-disk in-memory PDF rasterization, SIMD tensor normalization & aspect-ratio bucketing | M1 | Survey 1 (R1) |
| 2 | Pluggable ONNX Provider Hierarchy | TensorRT -> CUDA -> DirectML -> CPU fallback with execution provider autodiscovery | M1 | Survey 1 (R1) |
| 3 | Batched RapidOCR Engine | PP-OCRv4 dynamic batch detection & recognition with `process_batch` contract | M1 | Survey 1 (R1) |
| 4 | Vectorized Tensor Decoding | Concurrent DBNet polygon extraction and vectorized CTC greedy decoding | M1 | Survey 1 (R1) |
| 5 | 3-Tier Priority Queue System | Strict priority multiplexing (`high`, `default`, `low`) for sub-1s interactive jobs vs bulk archives | M2 | Survey 2 (R2) |
| 6 | Swarm Supervisor & Workers | Multi-worker process manager with automatic respawn and graceful shutdown | M2 | Survey 2 (R2) |
| 7 | Worker Heartbeat & Registry | Redis worker heartbeat daemon with live status, CPU, and RSS tracking | M2 | Survey 2 (R2) |
| 8 | Zombie Job Reaper & Failover | Automatic zombie detection and requeuing for crashed workers | M2 | Survey 2 (R2) |
| 9 | Exponential Backoff & DLQ | Failure taxonomy-based retry ($2^n + \text{jitter}$) and Dead-Letter Queue quarantine | M2 | Survey 2 (R2) |
| 10 | FastAPI Queue Integration & API | Priority job submission, worker management, queue inspection & DLQ replay endpoints | M2 | Survey 2 (R2) |
| 11 | Bounded Streaming Buffer | Windowed ($K=8..16$) page processing & incremental document writing bounding RSS $\le 500\text{MB}$ | M3 | Survey 3 (R3) |
| 12 | Tiered OCR Cache | L1 memory LRU cache + L2 asynchronous disk/S3 spooling cache | M3 | Survey 3 (R3) |
| 13 | Concurrent Object Storage Uploader | Multipart S3/MinIO & local storage streaming uploader with connection pooling | M3 | Survey 3 (R3) |
| 14 | Automated Load Benchmark Suite | Synthetic doc generator, concurrent worker load tester, latency quantiles & throughput metrics | M4 | Survey 3 (R4) |
| 15 | 1,000-Page Zero-Leak Stress Suite | 1,000-page continuous stress test with OLS memory slope verification and chaos fault injection | M4 | Survey 3 (R4) |
| 16 | Prometheus & JSON Telemetry | Metrics exporter for throughput, latency histograms, worker RSS, and benchmark scorecards | M4 | Survey 3 (R4) |
| 17 | Comprehensive E2E Verification | 100% pass across all existing (378+) and new tests, followed by adversarial coverage hardening | M5 | Survey 1-3 |

## Milestones
| # | Name | Scope | Dependencies | Status | Assigned Worker |
|---|------|-------|-------------|--------|-----------------|
| M1 | Batch Engine & GPU Acceleration | Features 1, 2, 3, 4 | none | DONE | worker_m1 (7014921c-0df3-49c5-a63c-fc0fa7741e8c) |
| M2 | Distributed Queue & Worker Swarm | Features 5, 6, 7, 8, 9, 10 | M1 interface contracts | DONE | worker_m2 (7f7bf0ba-6345-4101-9170-9fc58e05b0f7) |
| M3 | Streaming Buffer & Storage Engine | Features 11, 12, 13 | M1 | DONE | worker_m3_v2 (c8b7d68a-6a60-4ec0-b558-e0ec50ea6fa3) |
| M4 | Automated Benchmarks & Stress Suite | Features 14, 15, 16 | M1, M2, M3 | DONE | worker_m4_v2 (ec0beceb-6d87-436b-9f69-1ca87c4f4632) |
| M5 | Final Milestone: 100% E2E Pass & Hardening | Feature 17 | M1, M2, M3, M4, TEST_READY | DONE | orchestrator_4 (Reviewers, Challengers, Auditor APPROVED/CLEAN) |
| E2E | E2E Testing Track | Tiers 1-4 Test Suite (190 tests) & TEST_READY.md | none | DONE | worker_e2e (6e343b33-b672-49d8-a490-71dfb698e076) |

## Interface Contracts
*(Preserved as documented)*
