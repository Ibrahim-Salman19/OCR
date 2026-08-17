# Worker M3 Dispatch Instructions

## Working Directory
`/mnt/d/code/Projects/Python/OCR_Book/.agents/worker_m3_v2`

## Scope
Milestone 3: Memory Management, Streaming Buffer & Tiered Storage Engine
Features:
- F11: Bounded Streaming Buffer (`blast_ocr/core/streaming.py`): `PageStreamGenerator` (yielding $K=8..16$ page windows) and `StreamDocumentWriter` (incremental chunk export with immediate scratch unlinking) bounding RAM $\le 500\text{MB}$ RSS during 1,000+ page runs.
- F12: Tiered OCR Cache (`blast_ocr/cache/tiered_cache.py`): L1 In-Memory LRU Cache + L2 Asynchronous Disk/S3 spooling cache with background worker.
- F13: Concurrent Object Storage Uploader (`blast_ocr/storage/concurrent_uploader.py` and `blast_ocr/storage/object_store.py`): Concurrent multipart S3/MinIO and local object storage streaming with connection pooling and retries.
- Dedicated tests: `tests/test_streaming_storage.py`.

## Reference Files
- `/mnt/d/code/Projects/Python/OCR_Book/.agents/ORIGINAL_REQUEST.md` (MANDATORY TO READ)
- `/mnt/d/code/Projects/Python/OCR_Book/PROJECT.md`
- `/mnt/d/code/Projects/Python/OCR_Book/TEST_READY.md`
- Existing M3 files in `blast_ocr/core/streaming.py`, `blast_ocr/cache/tiered_cache.py`, `blast_ocr/storage/concurrent_uploader.py`, `blast_ocr/storage/object_store.py`.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Completion Criteria
1. Full test coverage in `tests/test_streaming_storage.py` and passing `pytest tests/test_streaming_storage.py -v`.
2. Passing all existing tests in `tests/e2e/tier1_features/test_f11_streaming_buffer.py`, `test_f12_tiered_cache.py`, `test_f13_concurrent_uploader.py`.
3. Complete `handoff.md` with verified test execution commands and results.
