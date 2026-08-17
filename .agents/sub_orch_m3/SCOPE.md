# Scope: Milestone 3 — Streaming Buffer & Storage Engine

## Architecture & Responsibilities
Milestone 3 delivers high-throughput memory management, bounded document streaming, tiered asynchronous caching, and concurrent object storage uploads.

Key components:
1. **`blast_ocr/core/streaming.py`**:
   - `PageStreamGenerator`: Windowed ingestion ($K=8..16$ pages) for large PDFs and image archives. Manages ephemeral scratch directories `scratch_w_i`, yielding page batches and immediately unlinking scratch files post-batch to bound RSS $\le 500\text{MB}$.
   - `StreamDocumentWriter`: Incremental document writer supporting streaming append of Markdown, Text, Searchable PDF, and JSONL outputs without assembling entire 1,000-page Document models in RAM.
   - `ChunkScratchManager`: Context manager and helper for atomic chunk scratch folder creation, tracking, and deterministic cleanup.
2. **`blast_ocr/cache/tiered_cache.py`**:
   - `TieredOCRCache`: Dual-tier cache with L1 In-Memory LRU (`OrderedDict`, capacity $M=100$ pages) + L2 Asynchronous Disk/S3 spooling cache.
   - `AsyncCacheWriter`: Background queue worker for non-blocking disk persistence, eliminating `fsync` overhead on the OCR critical path.
   - Backward-compatibility integration with `OCRCache` in `blast_ocr/cache/manager.py`.
3. **`blast_ocr/storage/concurrent_uploader.py`**:
   - `ConcurrentObjectUploader`: Thread/async pool for background concurrent uploads of pipeline outputs to S3/MinIO and local storage.
   - Connection pooling, exponential retry with jitter, multipart chunked streaming for large objects ($>8\text{MB}$), and presigned URL generation.
   - Streaming methods on `ObjectStorage` abstraction (`put_stream`, `get_stream`, `put_batch_concurrent`).
4. **`tests/test_streaming_storage.py`**:
   - Comprehensive test suite testing all streaming generator windowing, memory bounding, tiered cache L1/L2 hits/misses/async-flush, concurrent multipart S3/local uploads, retries, and failure modes.

## Feature Inventory Mapping
| # | Feature | Description | Status |
|---|---------|-------------|--------|
| 11 | Bounded Streaming Buffer | Windowed ($K=8..16$) page processing & incremental document writing bounding RSS $\le 500\text{MB}$ | IN_PROGRESS |
| 12 | Tiered OCR Cache | L1 memory LRU cache + L2 asynchronous disk/S3 spooling cache | IN_PROGRESS |
| 13 | Concurrent Object Storage Uploader | Multipart S3/MinIO & local storage streaming uploader with connection pooling | IN_PROGRESS |

## Interface Contracts

### 1. `blast_ocr.core.streaming`
```python
class PageStreamGenerator:
    def __init__(self, source_path: str | Path, chunk_size: int = 8, temp_dir: Optional[str | Path] = None): ...
    def __iter__(self) -> Generator[List[Tuple[int, Path]], None, None]: ...
    def close(self) -> None: ...

class StreamDocumentWriter:
    def __init__(self, output_path: str | Path, format: str): ...
    def write_page(self, page_num: int, text: str, layout: Optional[Dict[str, Any]] = None) -> None: ...
    def finalize(self) -> Path: ...
```

### 2. `blast_ocr.cache.tiered_cache`
```python
class TieredOCRCache:
    def __init__(self, cache_dir: str | Path, l1_capacity: int = 100, backend: Optional[ObjectStorage] = None): ...
    def get(self, key: str) -> Optional[Dict[str, Any]]: ...
    def put(self, key: str, value: Dict[str, Any], sync: bool = False) -> None: ...
    def flush(self) -> None: ...
    def clear(self) -> None: ...
```

### 3. `blast_ocr.storage.concurrent_uploader`
```python
class ConcurrentObjectUploader:
    def __init__(self, storage: ObjectStorage, max_workers: int = 4, chunk_size_mb: int = 8): ...
    def upload_file(self, key: str, local_path: str | Path) -> Future[str]: ...
    def upload_stream(self, key: str, stream: BinaryIO, length: Optional[int] = None) -> Future[str]: ...
    def upload_batch(self, items: Dict[str, str | Path]) -> Dict[str, str]: ...
    def shutdown(self, wait: bool = True) -> None: ...
```
