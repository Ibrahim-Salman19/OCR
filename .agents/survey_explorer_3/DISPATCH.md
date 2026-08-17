# DISPATCH — survey_explorer_3

**Objective**: Survey memory management, storage streaming, and the test / benchmarking suite.
**Key Focus**:
1. Map out current memory management, buffer chunking, page caching, and document ingestion (PDF, images, PPTX).
2. Investigate streaming buffer chunking and concurrent uploads to local / S3-compatible (MinIO) storage for large-scale batch jobs (1,000+ pages).
3. Investigate existing test suite (`tests/`, `eval/`, 370+ tests) and how to build an automated benchmarking & stress-testing suite in `eval/` measuring throughput (pages/sec), GPU/CPU utilization, peak memory (RAM/VRAM), failure recovery under load, and exporting Prometheus and JSON metrics.
4. Enumerate all required features, dependencies, and interface contracts for R3 & R4.
5. Write your comprehensive survey report to `/mnt/d/code/Projects/Python/OCR_Book/.agents/survey_explorer_3/report.md` and handoff to `/mnt/d/code/Projects/Python/OCR_Book/.agents/survey_explorer_3/handoff.md`.

## 2026-08-15T14:52:16Z
You are survey_explorer_3 (role: teamwork_preview_explorer).
Your task is to survey the B.L.A.S.T. OCR codebase with a focus on Memory Management, Object Storage Streaming, and Automated Benchmarking (Requirements R3 & R4).

1. Read `/mnt/d/code/Projects/Python/OCR_Book/.agents/ORIGINAL_REQUEST.md` and `/mnt/d/code/Projects/Python/OCR_Book/.agents/survey_explorer_3/DISPATCH.md`.
2. Map out existing memory usage patterns, document ingestion (`blast_ocr/core`), storage handling, existing test suite (`tests/`), and evaluation suite (`eval/`).
3. Determine technical design for:
   - Bounded memory consumption during large-scale batch jobs (1,000+ page archives) with streaming buffer chunking and async page caching.
   - Storage abstraction supporting concurrent uploads to local and S3-compatible (MinIO) object storage.
   - End-to-end load testing and latency benchmark suite in `eval/` measuring throughput (pages/sec), GPU/CPU utilization, peak memory (RAM/VRAM), failure recovery, and logging Prometheus/JSON metrics.
4. Enumerate all required features, modules, files, constraints, and dependencies.
5. Save your detailed survey report to `/mnt/d/code/Projects/Python/OCR_Book/.agents/survey_explorer_3/report.md` and your handoff to `/mnt/d/code/Projects/Python/OCR_Book/.agents/survey_explorer_3/handoff.md`.
6. Send a message back to the caller when done.
