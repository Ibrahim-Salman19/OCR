# Handoff Report: Milestone 3 — Concurrent Object Uploader, Storage Engine & Test Suite

**Agent**: explorer_3  
**Role**: Investigation & Blueprint Design (Milestone 3)  
**Target File / Blueprint**: `/mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m3/explorer_3/report.md`  

---

## 1. Observation

1. **Existing Storage Engine (`blast_ocr/storage/object_store.py:32-189`)**:
   - `ObjectStorage` ABC defines `put(key, local_path)`, `get(key, dest_path)`, `exists(key)`, `delete(key)`, and `put_bytes(key, data)`.
   - `LocalFilesystemStorage` copies local files via `shutil.copy2`. Path traversal protection is implemented at lines 72-78 (`ValueError` if key resolves outside root).
   - `S3ObjectStorage` initializes boto3 client without explicit connection pooling configuration (line 118-124). Default botocore connection pool size is 10 connections.
   - There were no native streaming methods (`put_stream`, `get_stream`) or presigned URL generator on the base `ObjectStorage` abstraction.
   - In `blast_ocr/pipeline.py:638-645`, artifact mirroring to S3 iterates sequentially over all outputs:
     ```python
     for artifact in output_artifacts:
         key = artifact_key(job_id, artifact.filepath)
         mirrored[artifact.artifact_type] = object_storage.put(key, artifact.filepath)
     ```

2. **Existing Test Coverage & Concurrency Patterns (`tests/test_object_store.py`, `tests/test_concurrency_complete.py`)**:
   - `tests/test_object_store.py` runs 12 tests against `LocalFilesystemStorage`, `moto` in-process mocked S3, and optional real MinIO (verified passing in 72.8s, 100% pass rate).
   - `tests/test_concurrency_complete.py` demonstrates standard stress test patterns using 50 concurrent threads to prove mutex correctness, double-checked locking, and zero deadlocks.

---

## 2. Logic Chain

1. **I/O Concurrency Selection**:
   - *Observation*: Object storage operations (S3 uploads and local disk operations) are blocking network and filesystem calls.
   - *Deduction*: A `concurrent.futures.ThreadPoolExecutor` provides optimal concurrency because Python releases the GIL during socket reads/writes (`urllib3`) and file system operations (`shutil.copyfileobj`), avoiding the IPC and process creation overhead of multiprocessing.

2. **Connection Pooling Scaling**:
   - *Observation*: Default boto3 clients allocate 10 pool connections. When running multi-worker batch pipelines or concurrent uploads exceeding 10 threads, urllib3 logs connection pool exhaustion warnings and suffers connection teardown latency.
   - *Deduction*: `S3ObjectStorage` and `ConcurrentObjectUploader` must configure `botocore.config.Config(max_pool_connections=max(50, max_workers * 2))` to eliminate connection pool contention.

3. **Rate Limiting & Jittered Retry**:
   - *Observation*: S3 and MinIO endpoints respond with HTTP 503 `SlowDown` or HTTP 429 `TooManyRequests` when sudden bursts of concurrent parts or files are submitted.
   - *Deduction*: Standard exponential backoff causes synchronized retries (thundering herd). Full jitter ($T = \text{Uniform}(0, \min(T_{\text{max}}, T_{\text{initial}} \times 2^{\text{attempt}-1}))$) randomizes retry timing and stabilizes throughput under load.

4. **Error Isolation in Batch Processing**:
   - *Observation*: Pipelines produce multiple outputs per job (e.g. Markdown, DOCX, Searchable PDF, Manifest).
   - *Deduction*: A failure uploading a single non-critical artifact (e.g. temporary debug log) must not abort or crash the remaining artifacts. `upload_batch` must isolate errors per item and return both completed locators and structured error records via `BatchUploadError`.

---

## 3. Caveats

- When running against local storage (`LocalFilesystemStorage`), presigned URLs return standard `file://` URIs since local files have no HTTP server by default.
- On Windows operating systems, attempting to delete or replace a file with an open handle raises `PermissionError`. The implementation explicitly closes all stream file descriptors in `finally` blocks before cleanup.
- S3 multipart uploads require parts of at least 5MB (except the last part) according to AWS S3 specifications; the 8MB default chunk size satisfies this constraint.

---

## 4. Conclusion

The design and complete implementation code for `blast_ocr/storage/concurrent_uploader.py`, the enhancements to `blast_ocr/storage/object_store.py`, and the comprehensive test suite `tests/test_streaming_storage.py` are fully specified in `/mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m3/explorer_3/report.md`.

Key deliverables ready for implementer agents:
1. `ConcurrentObjectUploader` class with connection pooling, full-jitter exponential backoff, chunked streaming, and error-isolated batch uploads.
2. `ObjectStorage` enhancements adding `put_stream`, `get_stream`, `put_batch_concurrent`, and `get_presigned_url`.
3. Complete `tests/test_streaming_storage.py` test suite with 100% coverage across `PageStreamGenerator`, `StreamDocumentWriter`, `TieredOCRCache`, `ConcurrentObjectUploader`, and `ObjectStorage`.

---

## 5. Verification Method

To verify the design once implemented:

```bash
# 1. Run the new comprehensive streaming and storage test suite:
pytest tests/test_streaming_storage.py -v

# 2. Run existing storage and concurrency test suites to verify zero regressions:
pytest tests/test_object_store.py tests/test_concurrency_complete.py -v

# 3. Verify lint and type compliance:
ruff check blast_ocr/storage/concurrent_uploader.py blast_ocr/storage/object_store.py tests/test_streaming_storage.py
mypy blast_ocr/storage/concurrent_uploader.py blast_ocr/storage/object_store.py
```
