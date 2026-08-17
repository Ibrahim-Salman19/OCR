## 2026-08-15T15:00:12Z

Investigate and design `blast_ocr/cache/tiered_cache.py`:
1. `TieredOCRCache`: Dual-tier caching architecture with L1 In-Memory LRU cache (`collections.OrderedDict`, configurable capacity $M=100$) and L2 Asynchronous Disk/S3 spooling cache.
2. `AsyncCacheWriter`: Background queue worker (`queue.Queue` + worker thread) for non-blocking disk persistence, eliminating `fsync` overhead on the OCR critical path.
3. Cache serialization, key hashing (deterministic namespace hashing), thread safety with RLock, and cache invalidation / pruning (`prune_cache`).
4. Backward-compatible integration with `blast_ocr/cache/manager.py` (`OCRCache`) and `blast_ocr/config.py`.

Read the existing codebase (`blast_ocr/cache/manager.py`, `blast_ocr/config.py`, `blast_ocr/pipeline.py`, `tests/test_object_store.py`).
Produce your complete technical design and blueprint in `/mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m3/explorer_2/report.md`.
Report back when done via send_message.
