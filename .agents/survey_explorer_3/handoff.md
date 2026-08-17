# 🤝 Handoff Report — survey_explorer_3 (Requirements R3 & R4)

**Agent**: `survey_explorer_3`  
**Role**: `teamwork_preview_explorer`  
**Recipient**: `parent` (orchestrator)  
**Date**: 2026-08-15  
**Topic**: Memory Management, Streaming Storage Abstraction, and Automated Benchmarking & Stress-Testing Suite (Requirements R3 & R4)

---

## 1. Observation

Direct code observations across the B.L.A.S.T. OCR codebase:

- **PDF Batch Rendering and Scratch Disk Allocation**:
  - In `blast_ocr/pipeline.py:196-256`, `process_pdf()` allocates a single temporary directory `temp_dir = tempfile.mkdtemp()` for the entire PDF.
  - In `line 207-214`, `convert_from_path()` renders batches of 10 pages (`batch_size = 10`) to `temp_dir` with `paths_only=True`.
  - In `line 233`, all results are accumulated in RAM via `all_results.extend(batch_results)`.
  - `temp_dir` is only deleted in the `finally:` block (`line 257-277`) after all pages finish. For 1,000 pages, 3–5 GB of raw rendered PNGs accumulate simultaneously in `temp_dir`.
- **Image Directory Ingestion**:
  - In `blast_ocr/pipeline.py:412-445`, directory inputs create `restore_temp_dir`, restore all images at once into that folder, and pass the entire list to `process_batch_threaded`.
- **Document Model Assembly & String Concatenation**:
  - In `blast_ocr/pipeline.py:477-488`, `doc_model = Document(title=source.stem, pages=pages_list)` instantiates all `Page` objects simultaneously in RAM.
  - In `blast_ocr/pipeline.py:511`, `full_text = ... "\n\n---\n\n".join([r.get("text", "") for r in results])` creates a monolithic string of the entire archive.
- **Engine Memory Cleanup**:
  - In `blast_ocr/core/extractor.py:469-489`, `RobustOCRExtractor.process_page()` explicitly runs `del processed_img`, `del image`, `gc.collect()`, and `torch.cuda.empty_cache()` (if CUDA is available).
  - In `blast_ocr/core/extractor.py:503-509`, `_confidence_to_float()` detaches PyTorch tensors before storing results.
  - In `blast_ocr/core/parallel.py:18-20`, `ParallelOCRProcessor` caps worker threads at `min(config.max_workers, 2)`.
- **Storage Abstraction**:
  - In `blast_ocr/storage/object_store.py:32-65`, `ObjectStorage` defines synchronous `put()`, `get()`, `exists()`, `delete()`, `put_bytes()`.
  - In `blast_ocr/pipeline.py:634-647`, artifacts are mirrored to S3 synchronously one file at a time at the very end of `process_job()`.
- **Evaluation & Benchmarking Suite**:
  - `eval/run.py:77-135` evaluates CER, WER, Kendall's tau (`reading_order_tau`), and fact checks on hand-transcribed gold pages.
  - `eval/teds_evaluator.py:1-202` evaluates table tree edit distance ($TEDS_{\text{struct}}$ and $TEDS_{\text{content}}$).
  - `benchmark.py:84-150` measures single image and 5-page PDF with `tracemalloc`.
  - `blast_ocr/telemetry.py:85-128` defines Prometheus metrics (`blast_jobs_total`, `blast_job_duration_seconds`, `blast_pages_total`, `blast_page_duration_seconds`, `blast_worker_memory_bytes`).

---

## 2. Logic Chain

1. **Step 1 (Memory Bottleneck)**:
   - *Observation*: Monolithic storage of `all_results`, `pages_list`, full text strings, and persistent `temp_dir` scratch files over the entire job.
   - *Inference*: A 1,000-page job will experience continuous RAM growth ($\approx 1\text{MB}$ per page model + string representations $= 1\text{GB}+$ RAM) and disk consumption ($3–5\text{GB}$ in `/tmp`).
   - *Design*: Introduce `PageStreamGenerator` (yielding $K=8..16$ page windows), `StreamDocumentWriter` (incremental output writer), and immediate scratch unlinking per window to bound peak memory to $O(K) \le 500\text{MB}$ RSS.
2. **Step 2 (Storage Throughput)**:
   - *Observation*: Sequential single-file `put()` operations block the main pipeline completion, and large files lack multipart chunking.
   - *Inference*: Uploading multi-page PDFs, searchable PDFs, and markdown bundles adds significant serialized latency.
   - *Design*: Implement `ConcurrentObjectUploader` and `put_stream()` with multipart chunking and connection pooling, enabling asynchronous background upload while subsequent pages are processed.
3. **Step 3 (Caching Scalability)**:
   - *Observation*: `OCRCache` performs synchronous disk writes with `os.fsync()`.
   - *Inference*: Disk I/O latency adds overhead to worker threads on high-throughput jobs.
   - *Design*: Implement `TieredOCRCache` with an L1 memory LRU cache ($M=100$ items) and an asynchronous background disk/S3 spooling queue.
4. **Step 4 (Automated Benchmarking & Stress Testing)**:
   - *Observation*: `eval/` currently tests only accuracy (CER/WER/TEDS) and `benchmark.py` only tests 5 pages.
   - *Inference*: The project lacks automated regression testing for throughput (pages/sec), latency quantiles (p50/p95/p99), GPU/CPU utilization, zero memory leak verification, and chaos failure recovery.
   - *Design*: Build `eval/benchmark_load.py` and `eval/stress_suite.py` with synthetic multi-modal document generation (1 to 1000 pages), high-frequency `ResourceMonitor` (100ms sampling of RAM, VRAM, CPU, FDs), chaos fault injection (worker kill, corrupt page, S3 drop), and JSON / Prometheus scorecard exports.

---

## 3. Caveats

1. **GPU Availability in CI**: CUDA/GPU hardware may not be available in standard CI runners (e.g. GitHub Actions). The benchmark suite must automatically detect device capabilities, testing CPU-only baselines and mocking or skipping GPU-specific VRAM assertions when CUDA is absent.
2. **Windows Path & File Locking**: Windows handles locked files strictly (e.g. `pdftoppm.exe` or open image handles). All streaming scratch managers and temporary directory cleanups must use explicit retry loops and context managers.
3. **Streamlit Cloud Memory Ceiling**: Streamlit Community Cloud enforces a strict ~1GB RAM ceiling. The streaming chunk size $K=8$ and single-worker default in that environment must remain strictly enforced.

---

## 4. Conclusion

Requirements R3 (Memory Management & Object Storage Streaming) and R4 (Automated Benchmarking & Stress-Testing Suite) are fully scoped and technically architected:
- **R3 Deliverables**:
  1. `blast_ocr/core/streaming.py`: Streaming window generator, incremental document writer, immediate scratch unlinking.
  2. `blast_ocr/cache/tiered_cache.py`: L1 Memory LRU + L2 Async Disk/S3 Cache with background worker.
  3. `blast_ocr/storage/concurrent_uploader.py`: Concurrent multi-part S3/MinIO streaming uploader with connection pooling and retries.
- **R4 Deliverables**:
  1. `eval/benchmark_load.py`: Load testing CLI measuring throughput, latency quantiles (p50/p90/p95/p99), CPU/GPU utilization, and Prometheus/JSON export.
  2. `eval/stress_suite.py`: 1,000-page continuous stress test, zero memory leak regression assertion, and chaos failure recovery harness.
  3. `tests/test_streaming_memory.py`, `tests/test_storage_concurrent.py`, `tests/test_benchmark_suite.py`: Complete test coverage.

Full architectural specifications, data flows, and component designs are documented in `.agents/survey_explorer_3/report.md`.

---

## 5. Verification Method

To independently verify these findings and test the proposed designs once implemented:

1. **Verify Existing Tests Pass**:
   ```bash
   pytest tests/test_memory.py tests/test_vram_memory.py tests/test_object_store.py tests/test_concurrency_complete.py -v
   ```
2. **Verify Memory Management & Streaming**:
   - Inspect `blast_ocr/pipeline.py:196-256` and compare against `blast_ocr/core/streaming.py` streaming windowing.
   - Run memory leak verification:
     ```bash
     pytest tests/test_memory.py tests/test_vram_memory.py -v
     ```
3. **Verify Load Benchmarks & Stress Suite**:
   - Execute benchmark suite CLI:
     ```bash
     python -m eval.benchmark_load --pages 50 --workers 4 --output-json eval/results/benchmark_test.json
     ```
   - Execute 1,000-page stress run:
     ```bash
     python -m eval.stress_suite --continuous-pages 1000 --assert-zero-leak
     ```
