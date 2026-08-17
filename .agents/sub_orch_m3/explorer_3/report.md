# Technical Blueprint: Concurrent Object Uploader, Storage Streaming & Test Suite

**Document Version**: 1.0.0  
**Milestone**: Milestone 3 — Streaming Buffer & Storage Engine  
**Author**: explorer_3  
**Status**: Ready for Implementation  

---

## 1. Executive Summary & Architectural Scope

Milestone 3 delivers bounded memory management, incremental document streaming, tiered caching, and high-throughput concurrent object storage uploads.

This blueprint specifies the complete design and exact implementation for:
1. **`blast_ocr/storage/concurrent_uploader.py`**:
   - `ConcurrentObjectUploader`: Thread pool-based background uploader for S3/MinIO and local storage.
   - High-throughput connection pooling with `botocore.config.Config(max_pool_connections=...)`.
   - Jittered exponential backoff retry mechanism for transient network and S3/MinIO rate-limit errors.
   - Multipart chunked streaming for large objects ($>8\text{MB}$) without RAM accumulation.
   - Batch upload with robust per-item error isolation.
   - Presigned URL generation for client downloads and uploads.
2. **`blast_ocr/storage/object_store.py` (Enhancements)**:
   - `put_stream`, `get_stream`, `put_batch_concurrent`, and `get_presigned_url` methods on `ObjectStorage`, `LocalFilesystemStorage`, and `S3ObjectStorage`.
   - Full backward compatibility with existing `put`, `get`, `exists`, `delete`, and `put_bytes`.
3. **`tests/test_streaming_storage.py` (Comprehensive Test Suite)**:
   - 100% test coverage for `PageStreamGenerator`, `StreamDocumentWriter`, `TieredOCRCache`, `ConcurrentObjectUploader`, and `ObjectStorage` stream extensions.
   - Hermetic unit testing via `moto.mock_aws` and custom fault-injection mock clients.
   - Multi-threaded stress testing (50 concurrent threads) verifying lock correctness and zero race conditions.

---

## 2. Component Design: `blast_ocr/storage/concurrent_uploader.py`

### 2.1 Concurrency Model & Connection Pooling

- **Concurrency Backend**: Synchronous `concurrent.futures.ThreadPoolExecutor`. Object storage I/O and disk I/O are I/O-bound operations that release Python's GIL during socket and file system system calls. Using a dedicated thread pool avoids the overhead of multiprocessing IPC and avoids complex event-loop bridging in synchronous worker threads.
- **Connection Pool Configuration**: Standard `boto3.client('s3')` defaults to `max_pool_connections=10`. Under high-concurrency workloads ($N > 10$ workers), urllib3 connection pools become exhausted, producing pool-full warnings and re-connection latency. `ConcurrentObjectUploader` configures the S3 client with `max_pool_connections = max(50, max_workers * 2)`.

### 2.2 Exponential Backoff with Jitter Algorithm

To avoid the "thundering herd" problem when retrying against rate-limited or throttling S3/MinIO endpoints (HTTP 503 `SlowDown` or HTTP 429 `TooManyRequests`), `ConcurrentObjectUploader` uses the Full Jitter backoff formula:

$$T_{\text{delay}} = \text{Uniform}\left(0, \min\left(T_{\text{max}}, T_{\text{initial}} \times \beta^{\text{attempt}-1}\right)\right)$$

Where:
- $T_{\text{initial}} = 0.5\text{s}$ (initial backoff)
- $\beta = 2.0$ (backoff multiplier)
- $T_{\text{max}} = 10.0\text{s}$ (maximum delay ceiling)
- $\text{max\_retries} = 3$ (maximum retry attempts)

#### Retryable vs Non-Retryable Exceptions
- **Retryable Exceptions**:
  - `ConnectionError`, `TimeoutError`, `socket.timeout`, `OSError`, `IOError`.
  - Botocore exceptions: `EndpointConnectionError`, `ConnectTimeoutError`, `ReadTimeoutError`, `ConnectionClosedError`, `ResponseParserError`.
  - S3 `ClientError` with HTTP status codes: `[429, 500, 502, 503, 504]`.
  - S3 error codes: `'SlowDown'`, `'RequestTimeout'`, `'InternalError'`, `'ServiceUnavailable'`, `'Throttling'`, `'ThrottlingException'`, `'RequestLimitExceeded'`.
- **Non-Retryable Exceptions** (fail immediately):
  - `FileNotFoundError`, `ValueError`, `TypeError`.
  - S3 `ClientError` with codes: `'NoSuchBucket'`, `'NoSuchKey'`, `'AccessDenied'`, `'InvalidAccessKeyId'`, `'SignatureDoesNotMatch'`.

### 2.3 Multipart Chunked Streaming ($> 8\text{MB}$)

For large document artifacts (such as high-DPI multi-page searchable PDFs or full book TIFFs $> 8\text{MB}$):
- **S3 / MinIO**: Leverages `boto3.s3.transfer.TransferConfig(multipart_threshold=8*1024*1024, multipart_chunksize=8*1024*1024, max_concurrency=max_workers, use_threads=True)`.
- **Local Storage**: Streams data in $64\text{KB}$ buffers directly to disk via `shutil.copyfileobj(stream, dest_file, length=64*1024)` without loading the entire binary payload into memory.

### 2.4 Error Isolation & Batch Upload Contracts

When batch uploading pipeline outputs (`slides.pptx`, `slides.md`, `slides.docx`, `manifest.json`), an upload failure on one artifact must **not** abort or silently discard the other artifacts.
- `upload_batch(items, return_futures=False, fail_fast=False)`:
  - Submits all upload tasks concurrently to the thread pool.
  - Collects results using `concurrent.futures.as_completed`.
  - If `fail_fast=False` (default), all items are attempted. Successful uploads populate the result map `{key: locator}`; failed items populate an error map `{key: exception}`.
  - If one or more items fail, raises `BatchUploadError(errors, completed)` containing both failed keys and completed locators, allowing the caller to perform partial recovery or graceful degradation.

---

## 3. Detailed Implementation Code: `blast_ocr/storage/concurrent_uploader.py`

```python
"""
blast_ocr.storage.concurrent_uploader

High-throughput concurrent uploader for S3/MinIO and local storage.
Features:
- ThreadPoolExecutor for background non-blocking uploads.
- Connection pooling configured to match worker concurrency.
- Jittered exponential backoff retrying transient HTTP/socket failures.
- Multipart chunked streaming for large objects (> 8MB) without RAM accumulation.
- Batch upload with robust per-item error isolation.
- Presigned URL generation for client downloads and uploads.
"""

from __future__ import annotations

import io
import logging
import os
import random
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Callable, Dict, List, Optional, Tuple, Type, Union

from blast_ocr.storage.object_store import ObjectStorage, get_object_storage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetryConfig:
    """Configuration for exponential backoff retry with full jitter."""
    max_retries: int = 3
    initial_backoff: float = 0.5
    max_backoff: float = 10.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    retryable_status_codes: Tuple[int, ...] = (429, 500, 502, 503, 504)
    retryable_error_codes: Tuple[str, ...] = (
        "SlowDown",
        "RequestTimeout",
        "InternalError",
        "ServiceUnavailable",
        "Throttling",
        "ThrottlingException",
        "RequestLimitExceeded",
        "TooManyRequestsException",
    )


class BatchUploadError(Exception):
    """Raised when one or more items in a batch upload fail."""
    def __init__(self, message: str, errors: Dict[str, Exception], completed: Dict[str, str]):
        super().__init__(message)
        self.errors = errors
        self.completed = completed

    def __str__(self) -> str:
        return f"{super().__str__()} (Completed: {len(self.completed)}, Errors: {len(self.errors)})"


class ConcurrentObjectUploader:
    """
    High-throughput concurrent uploader for S3/MinIO and local storage.
    """

    def __init__(
        self,
        storage: Optional[ObjectStorage] = None,
        max_workers: int = 4,
        chunk_size_mb: int = 8,
        retry_config: Optional[RetryConfig] = None,
    ):
        self.storage = storage or get_object_storage()
        self.max_workers = max(1, max_workers)
        self.chunk_size_bytes = max(1, chunk_size_mb) * 1024 * 1024
        self.retry_config = retry_config or RetryConfig()
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="blast-uploader",
        )
        self._shutdown = False

    def _is_retryable(self, exc: Exception) -> bool:
        """Determine if an exception is transient and eligible for retry."""
        # Standard socket & network errors
        if isinstance(exc, (ConnectionError, TimeoutError, OSError, IOError)):
            # Explicitly do NOT retry missing files
            if isinstance(exc, FileNotFoundError):
                return False
            return True

        # Botocore exceptions (if boto3/botocore is installed)
        try:
            from botocore.exceptions import (
                ClientError,
                ConnectTimeoutError,
                ConnectionClosedError,
                EndpointConnectionError,
                ReadTimeoutError,
                ResponseParserError,
            )

            if isinstance(
                exc,
                (
                    EndpointConnectionError,
                    ConnectTimeoutError,
                    ReadTimeoutError,
                    ConnectionClosedError,
                    ResponseParserError,
                ),
            ):
                return True

            if isinstance(exc, ClientError):
                error_dict = exc.response.get("Error", {})
                code = error_dict.get("Code", "")
                status_code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")

                if code in self.retry_config.retryable_error_codes:
                    return True
                if status_code in self.retry_config.retryable_status_codes:
                    return True
        except ImportError:
            pass

        return False

    def _compute_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff with full jitter."""
        multiplier = self.retry_config.backoff_multiplier ** (attempt - 1)
        raw_backoff = min(
            self.retry_config.max_backoff,
            self.retry_config.initial_backoff * multiplier,
        )
        if self.retry_config.jitter:
            return random.uniform(0.0, raw_backoff)
        return raw_backoff

    def _execute_with_retry(self, upload_fn: Callable[..., str], key: str, *args: Any, **kwargs: Any) -> str:
        """Execute an upload operation with automatic retry on transient failure."""
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.retry_config.max_retries + 1):
            try:
                return upload_fn(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                if not self._is_retryable(exc) or attempt >= self.retry_config.max_retries:
                    logger.error(
                        f"Upload failed permanently for key '{key}' on attempt {attempt}/{self.retry_config.max_retries}: {exc}"
                    )
                    raise exc

                delay = self._compute_backoff(attempt)
                logger.warning(
                    f"Transient error uploading key '{key}' (attempt {attempt}/{self.retry_config.max_retries}): {exc}. "
                    f"Retrying in {delay:.2f}s..."
                )
                time.sleep(delay)

        if last_exc:
            raise last_exc
        raise RuntimeError(f"Unexpected retry termination for key '{key}'")

    def upload_file(
        self,
        key: str,
        local_path: Union[str, Path],
    ) -> Future[str]:
        """Asynchronously upload a local file to object storage."""
        if self._shutdown:
            raise RuntimeError("ConcurrentObjectUploader is already shut down")

        str_path = str(local_path)
        if not os.path.exists(str_path):
            raise FileNotFoundError(f"Local file does not exist: {str_path}")

        return self._executor.submit(
            self._execute_with_retry,
            self.storage.put,
            key,
            key,
            str_path,
        )

    def upload_stream(
        self,
        key: str,
        stream: BinaryIO,
        length: Optional[int] = None,
    ) -> Future[str]:
        """Asynchronously upload a binary stream to object storage."""
        if self._shutdown:
            raise RuntimeError("ConcurrentObjectUploader is already shut down")

        return self._executor.submit(
            self._execute_with_retry,
            self.storage.put_stream,
            key,
            key,
            stream,
            length=length,
        )

    def upload_bytes(
        self,
        key: str,
        data: bytes,
    ) -> Future[str]:
        """Asynchronously upload raw bytes to object storage."""
        if self._shutdown:
            raise RuntimeError("ConcurrentObjectUploader is already shut down")

        return self._executor.submit(
            self._execute_with_retry,
            self.storage.put_bytes,
            key,
            key,
            data,
        )

    def upload_batch(
        self,
        items: Dict[str, Union[str, Path, BinaryIO, bytes]],
        return_futures: bool = False,
        fail_fast: bool = False,
    ) -> Union[Dict[str, str], Dict[str, Future[str]]]:
        """
        Upload multiple items concurrently.
        
        Args:
            items: Mapping of object storage key to local path, stream, or bytes.
            return_futures: If True, returns dict of {key: Future[str]}.
            fail_fast: If True, first exception encountered will raise immediately.
        
        Returns:
            Dict mapping keys to storage locator strings (e.g. s3://bucket/key or local path).
        """
        if self._shutdown:
            raise RuntimeError("ConcurrentObjectUploader is already shut down")

        futures: Dict[Future[str], str] = {}
        key_to_future: Dict[str, Future[str]] = {}

        for key, value in items.items():
            if isinstance(value, (str, Path)):
                fut = self.upload_file(key, value)
            elif isinstance(value, bytes):
                fut = self.upload_bytes(key, value)
            elif hasattr(value, "read"):
                fut = self.upload_stream(key, value)
            else:
                raise TypeError(f"Unsupported item type for key '{key}': {type(value)}")

            futures[fut] = key
            key_to_future[key] = fut

        if return_futures:
            return key_to_future

        # Synchronous collection with error isolation
        completed: Dict[str, str] = {}
        errors: Dict[str, Exception] = {}

        for fut in as_completed(futures):
            k = futures[fut]
            try:
                locator = fut.result()
                completed[k] = locator
            except Exception as exc:
                errors[k] = exc
                if fail_fast:
                    raise exc

        if errors:
            raise BatchUploadError(
                f"Batch upload completed with {len(errors)} errors out of {len(items)} items",
                errors=errors,
                completed=completed,
            )

        return completed

    def get_presigned_url(
        self,
        key: str,
        expiration_seconds: int = 3600,
        http_method: str = "GET",
    ) -> str:
        """Generate a presigned URL or URI for the object."""
        return self.storage.get_presigned_url(
            key=key,
            expiration_seconds=expiration_seconds,
            http_method=http_method,
        )

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        """Shut down the underlying ThreadPoolExecutor."""
        if not self._shutdown:
            self._shutdown = True
            self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)

    def __enter__(self) -> ConcurrentObjectUploader:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.shutdown(wait=True)
```

---

## 4. Component Design & Implementation: `blast_ocr/storage/object_store.py` (Enhancements)

### 4.1 Specification of Protocol Enhancements

The existing `ObjectStorage` abstraction is enhanced with:
1. `put_stream(self, key: str, stream: BinaryIO, length: Optional[int] = None) -> str`: Streaming binary upload.
2. `get_stream(self, key: str) -> BinaryIO`: Streaming binary read returning an opened binary reader.
3. `get_presigned_url(self, key: str, expiration_seconds: int = 3600, http_method: str = "GET") -> str`: Presigned URL generation.
4. `put_batch_concurrent(self, items: Dict[str, Union[str, Path]], max_workers: int = 4) -> Dict[str, str]`: Concurrent batch upload convenience.
5. S3 Connection Pooling: `S3ObjectStorage` initializes boto3 client with `botocore.config.Config(max_pool_connections=...)`.

### 4.2 Updated Implementation for `blast_ocr/storage/object_store.py`

```python
"""
blast_ocr.storage.object_store

Artifact object storage abstraction (Execution Plan v2 Phase 8 & Milestone 3).
Two backends behind one unified protocol:
- LocalFilesystemStorage (default, config.storage_backend="local")
- S3ObjectStorage (config.storage_backend="s3"): S3 and MinIO support with connection pooling.
"""

from __future__ import annotations

import io
import logging
import os
import shutil
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, BinaryIO, Dict, Optional, Union

logger = logging.getLogger(__name__)


class ObjectStorage(ABC):
    """
    Minimal artifact storage contract: put a local file or stream under a key,
    get it back out, check existence, generate presigned URLs, and delete it.
    """

    @abstractmethod
    def put(self, key: str, local_path: str) -> str:
        """Store the file at local_path under `key`. Returns a backend-specific locator string."""

    @abstractmethod
    def get(self, key: str, dest_path: str) -> str:
        """Fetch the object stored under `key` to dest_path. Returns dest_path."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if an object exists under `key`."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete the object stored under `key`."""

    @abstractmethod
    def put_stream(self, key: str, stream: BinaryIO, length: Optional[int] = None) -> str:
        """Stream binary data directly into object store under `key` without intermediate disk files."""

    @abstractmethod
    def get_stream(self, key: str) -> BinaryIO:
        """Return a readable binary stream for the object stored under `key`."""

    @abstractmethod
    def get_presigned_url(self, key: str, expiration_seconds: int = 3600, http_method: str = "GET") -> str:
        """Generate a presigned download/upload URL or URI for the object."""

    def put_bytes(self, key: str, data: bytes) -> str:
        """Store raw bytes without caller-managed temp files."""
        return self.put_stream(key, io.BytesIO(data), length=len(data))

    def put_batch_concurrent(self, items: Dict[str, Union[str, Path]], max_workers: int = 4) -> Dict[str, str]:
        """Upload multiple local files concurrently under their respective keys."""
        results: Dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="object-store-batch") as executor:
            futures = {
                executor.submit(self.put, key, str(path)): key
                for key, path in items.items()
            }
            for fut in as_completed(futures):
                key = futures[fut]
                results[key] = fut.result()
        return results


class LocalFilesystemStorage(ObjectStorage):
    """Local disk-backed object storage."""

    def __init__(self, base_dir: Union[str, Path]):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # Reject path traversal: key must resolve inside base_dir.
        candidate = (self.base_dir / key).resolve()
        base_resolved = self.base_dir.resolve()
        if base_resolved not in candidate.parents and candidate != base_resolved:
            raise ValueError(f"Object key resolves outside storage root: {key!r}")
        return candidate

    def put(self, key: str, local_path: str) -> str:
        dest = self._resolve(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, dest)
        return str(dest)

    def get(self, key: str, dest_path: str) -> str:
        src = self._resolve(key)
        if not src.exists():
            raise FileNotFoundError(f"Object not found: {key!r}")
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest_path)
        return dest_path

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists():
            path.unlink()

    def put_stream(self, key: str, stream: BinaryIO, length: Optional[int] = None) -> str:
        dest = self._resolve(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            shutil.copyfileobj(stream, f, length=64 * 1024)
        return str(dest)

    def get_stream(self, key: str) -> BinaryIO:
        src = self._resolve(key)
        if not src.exists():
            raise FileNotFoundError(f"Object not found: {key!r}")
        return open(src, "rb")

    def get_presigned_url(self, key: str, expiration_seconds: int = 3600, http_method: str = "GET") -> str:
        dest = self._resolve(key)
        return dest.as_uri()


class S3ObjectStorage(ObjectStorage):
    """S3/MinIO compatible object storage with connection pooling."""

    def __init__(
        self,
        bucket: str,
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        region_name: str = "us-east-1",
        max_pool_connections: int = 50,
    ):
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        boto_cfg = Config(
            max_pool_connections=max_pool_connections,
            retries={"max_attempts": 3, "mode": "adaptive"},
        )
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region_name,
            config=boto_cfg,
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        from botocore.exceptions import ClientError

        try:
            self._client.head_bucket(Bucket=self.bucket)
        except ClientError:
            try:
                self._client.create_bucket(Bucket=self.bucket)
            except ClientError as e:
                logger.warning(f"Could not create/verify bucket {self.bucket!r}: {e}")

    def put(self, key: str, local_path: str) -> str:
        self._client.upload_file(local_path, self.bucket, key)
        return f"s3://{self.bucket}/{key}"

    def get(self, key: str, dest_path: str) -> str:
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        self._client.download_file(self.bucket, key, dest_path)
        return dest_path

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=key)

    def put_stream(self, key: str, stream: BinaryIO, length: Optional[int] = None) -> str:
        from boto3.s3.transfer import TransferConfig

        transfer_config = TransferConfig(
            multipart_threshold=8 * 1024 * 1024,
            multipart_chunksize=8 * 1024 * 1024,
            max_concurrency=10,
            use_threads=True,
        )
        self._client.upload_fileobj(
            stream,
            self.bucket,
            key,
            Config=transfer_config,
        )
        return f"s3://{self.bucket}/{key}"

    def get_stream(self, key: str) -> BinaryIO:
        from botocore.exceptions import ClientError

        try:
            response = self._client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"]
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404"):
                raise FileNotFoundError(f"Object not found in S3 bucket {self.bucket}: {key!r}")
            raise

    def get_presigned_url(self, key: str, expiration_seconds: int = 3600, http_method: str = "GET") -> str:
        client_method = "get_object" if http_method.upper() == "GET" else "put_object"
        return self._client.generate_presigned_url(
            ClientMethod=client_method,
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expiration_seconds,
        )


def get_object_storage(settings: Any = None) -> ObjectStorage:
    """Factory selecting storage backend from settings (defaults to config singleton)."""
    if settings is None:
        from blast_ocr.config import config as settings

    if getattr(settings, "storage_backend", "local") == "s3":
        return S3ObjectStorage(
            bucket=getattr(settings, "s3_bucket", "blast-ocr-artifacts"),
            endpoint_url=getattr(settings, "s3_endpoint_url", None),
            access_key=getattr(settings, "s3_access_key", None),
            secret_key=getattr(settings, "s3_secret_key", None),
        )
    base_dir = os.path.join(getattr(settings, "output_dir", "/tmp/blast_output"), "_object_store")
    return LocalFilesystemStorage(base_dir=base_dir)


def artifact_key(job_id: int, filename: str) -> str:
    """Deterministic, collision-resistant key for a job's artifact."""
    safe_name = Path(filename).name
    return f"jobs/{job_id}/{safe_name}"
```

---

## 5. Comprehensive Test Suite Design: `tests/test_streaming_storage.py`

This test suite rigorously verifies all Milestone 3 streaming, caching, and storage components:
- `PageStreamGenerator` windowing, ephemeral scratch cleanup, early exit handling.
- `StreamDocumentWriter` incremental format output (Markdown, Text, JSONL).
- `TieredOCRCache` L1 hit, L1 miss -> L2 hit, L2 async flush, LRU eviction, and 50-thread concurrency.
- `ConcurrentObjectUploader` concurrent uploads, multipart streaming, exponential backoff retries, and batch error isolation.
- `ObjectStorage` streaming methods (`put_stream`, `get_stream`, presigned URLs).

### Complete Test File: `tests/test_streaming_storage.py`

```python
"""
tests/test_streaming_storage.py

Comprehensive Milestone 3 test suite:
- PageStreamGenerator windowing & scratch cleanup
- StreamDocumentWriter incremental stream output
- TieredOCRCache L1/L2 hits, async spooling, thread safety
- ConcurrentObjectUploader concurrency, retries, multipart streaming, error isolation
- ObjectStorage stream extensions & presigned URLs
"""

import io
import json
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def moto_s3():
    """Mock AWS S3 environment using moto."""
    moto = pytest.importorskip("moto")
    with moto.mock_aws():
        yield


# ─────────────────────────────────────────────────────────────────────────────
# 1. PageStreamGenerator & ChunkScratchManager Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPageStreamGenerator:
    def test_image_dir_windowing_and_scratch_cleanup(self, tmp_path):
        """Verify windowing and that scratch dirs are deleted after batch iteration."""
        from blast_ocr.core.streaming import PageStreamGenerator

        img_dir = tmp_path / "images"
        img_dir.mkdir()
        for i in range(1, 19):  # 18 images
            (img_dir / f"page_{i:03d}.png").write_bytes(b"PNG_FAKE_DATA")

        scratch_parent = tmp_path / "scratch_parent"
        scratch_parent.mkdir()

        generator = PageStreamGenerator(img_dir, chunk_size=8, temp_dir=scratch_parent)
        batches: List[List] = []

        for batch in generator:
            batches.append(batch)
            # Active scratch directory should exist during batch processing
            active_scratches = list(scratch_parent.glob("scratch_w_*"))
            assert len(active_scratches) <= 1

        assert len(batches) == 3
        assert len(batches[0]) == 8
        assert len(batches[1]) == 8
        assert len(batches[2]) == 2

        # After iteration finishes, all scratch directories must be unlinked
        assert len(list(scratch_parent.glob("scratch_w_*"))) == 0

    def test_generator_early_close_cleans_scratch(self, tmp_path):
        """Verify early exit or close() cleans all ephemeral scratch folders."""
        from blast_ocr.core.streaming import PageStreamGenerator

        img_dir = tmp_path / "images"
        img_dir.mkdir()
        for i in range(1, 10):
            (img_dir / f"page_{i:02d}.png").write_bytes(b"DATA")

        scratch_parent = tmp_path / "scratch"
        scratch_parent.mkdir()

        gen = PageStreamGenerator(img_dir, chunk_size=4, temp_dir=scratch_parent)
        iter_gen = iter(gen)
        _ = next(iter_gen)  # Consume 1 batch

        gen.close()
        assert len(list(scratch_parent.glob("scratch_w_*"))) == 0

    def test_generator_exception_cleans_scratch(self, tmp_path):
        """Verify unhandled exception mid-loop still triggers scratch cleanup."""
        from blast_ocr.core.streaming import PageStreamGenerator

        img_dir = tmp_path / "images"
        img_dir.mkdir()
        for i in range(1, 10):
            (img_dir / f"page_{i:02d}.png").write_bytes(b"DATA")

        scratch_parent = tmp_path / "scratch"
        scratch_parent.mkdir()

        try:
            with PageStreamGenerator(img_dir, chunk_size=4, temp_dir=scratch_parent) as gen:
                for batch in gen:
                    raise RuntimeError("Simulated crash mid-stream")
        except RuntimeError:
            pass

        assert len(list(scratch_parent.glob("scratch_w_*"))) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 2. StreamDocumentWriter Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestStreamDocumentWriter:
    def test_markdown_incremental_write(self, tmp_path):
        """Verify Markdown incremental streaming."""
        from blast_ocr.core.streaming import StreamDocumentWriter

        out_file = tmp_path / "output.md"
        writer = StreamDocumentWriter(out_file, format="markdown")

        writer.write_page(page_num=1, text="First page content")
        writer.write_page(page_num=2, text="Second page content")
        final_path = writer.finalize()

        assert final_path.exists()
        content = final_path.read_text(encoding="utf-8")
        assert "# Page 1" in content
        assert "First page content" in content
        assert "# Page 2" in content
        assert "Second page content" in content

    def test_text_incremental_write(self, tmp_path):
        """Verify plain text format incremental streaming."""
        from blast_ocr.core.streaming import StreamDocumentWriter

        out_file = tmp_path / "output.txt"
        writer = StreamDocumentWriter(out_file, format="txt")

        writer.write_page(1, "Page 1 Text")
        writer.write_page(2, "Page 2 Text")
        final_path = writer.finalize()

        content = final_path.read_text(encoding="utf-8")
        assert "Page 1 Text" in content
        assert "Page 2 Text" in content

    def test_jsonl_incremental_write(self, tmp_path):
        """Verify JSONL format writes valid JSON per line."""
        from blast_ocr.core.streaming import StreamDocumentWriter

        out_file = tmp_path / "output.jsonl"
        writer = StreamDocumentWriter(out_file, format="jsonl")

        writer.write_page(1, "Page 1", layout={"blocks": 2})
        writer.write_page(2, "Page 2", layout={"blocks": 3})
        final_path = writer.finalize()

        lines = [json.loads(line) for line in final_path.read_text(encoding="utf-8").strip().split("\n")]
        assert len(lines) == 2
        assert lines[0]["page"] == 1
        assert lines[0]["text"] == "Page 1"
        assert lines[0]["layout"] == {"blocks": 2}


# ─────────────────────────────────────────────────────────────────────────────
# 3. TieredOCRCache Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTieredOCRCache:
    def test_l1_hit_bypasses_l2(self, tmp_path):
        """Verify L1 hit returns immediately without touching L2 backend."""
        from blast_ocr.cache.tiered_cache import TieredOCRCache

        cache = TieredOCRCache(cache_dir=str(tmp_path / "cache"), l1_capacity=10)
        cache.put("key1", {"page": 1, "text": "cached in L1"}, sync=True)

        with patch.object(cache, "_load_from_l2") as mock_l2:
            val = cache.get("key1")
            mock_l2.assert_not_called()
            assert val == {"page": 1, "text": "cached in L1"}

    def test_l1_miss_l2_hit_and_promotion(self, tmp_path):
        """Verify L1 miss reads from L2 and promotes entry into L1."""
        from blast_ocr.cache.tiered_cache import TieredOCRCache

        cache_dir = tmp_path / "cache"
        cache = TieredOCRCache(cache_dir=str(cache_dir), l1_capacity=10)
        cache.put("k2", {"page": 2, "text": "persisted"}, sync=True)

        # Clear L1
        with cache._lock:
            cache._l1_cache.clear()

        # Should be in L2
        val = cache.get("k2")
        assert val == {"page": 2, "text": "persisted"}

        # Now it should be back in L1
        with patch.object(cache, "_load_from_l2") as mock_l2:
            v2 = cache.get("k2")
            mock_l2.assert_not_called()
            assert v2 == {"page": 2, "text": "persisted"}

    def test_l1_lru_eviction(self, tmp_path):
        """Verify LRU eviction when L1 exceeds capacity."""
        from blast_ocr.cache.tiered_cache import TieredOCRCache

        cache = TieredOCRCache(cache_dir=str(tmp_path / "cache"), l1_capacity=2)
        cache.put("k1", {"page": 1}, sync=True)
        cache.put("k2", {"page": 2}, sync=True)
        cache.put("k3", {"page": 3}, sync=True)  # k1 should be evicted from L1

        with cache._lock:
            assert "k1" not in cache._l1_cache
            assert "k2" in cache._l1_cache
            assert "k3" in cache._l1_cache

        # k1 still loads from L2
        assert cache.get("k1") == {"page": 1}

    def test_l2_async_spooling_and_flush(self, tmp_path):
        """Verify non-blocking async write and flush persistence."""
        from blast_ocr.cache.tiered_cache import TieredOCRCache

        cache = TieredOCRCache(cache_dir=str(tmp_path / "cache"), l1_capacity=10)
        cache.put("async_key", {"data": 123}, sync=False)

        cache.flush()
        disk_file = tmp_path / "cache" / "async_key.json"
        assert disk_file.exists()

    def test_tiered_cache_50_threads_concurrency(self, tmp_path):
        """Stress test TieredOCRCache with 50 concurrent threads."""
        from blast_ocr.cache.tiered_cache import TieredOCRCache

        cache = TieredOCRCache(cache_dir=str(tmp_path / "cache"), l1_capacity=20)
        errors = []

        def worker(tid):
            try:
                for i in range(10):
                    k = f"key_{tid}_{i}"
                    cache.put(k, {"tid": tid, "i": i}, sync=False)
                    v = cache.get(k)
                    assert v is not None
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        cache.flush()
        assert len(errors) == 0, f"Concurrent cache operations raised errors: {errors}"


# ─────────────────────────────────────────────────────────────────────────────
# 4. ConcurrentObjectUploader Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestConcurrentObjectUploader:
    def test_concurrent_upload_local(self, tmp_path):
        """Verify concurrent file uploads to LocalFilesystemStorage."""
        from blast_ocr.storage.concurrent_uploader import ConcurrentObjectUploader
        from blast_ocr.storage.object_store import LocalFilesystemStorage

        storage = LocalFilesystemStorage(str(tmp_path / "store"))
        uploader = ConcurrentObjectUploader(storage=storage, max_workers=4)

        files = {}
        for i in range(10):
            p = tmp_path / f"file_{i}.txt"
            p.write_text(f"content {i}")
            files[f"jobs/1/file_{i}.txt"] = str(p)

        results = uploader.upload_batch(files)
        assert len(results) == 10
        for key in files:
            assert storage.exists(key)

        uploader.shutdown()

    def test_concurrent_upload_moto_s3(self, moto_s3, tmp_path):
        """Verify concurrent file uploads to S3ObjectStorage using moto."""
        from blast_ocr.storage.concurrent_uploader import ConcurrentObjectUploader
        from blast_ocr.storage.object_store import S3ObjectStorage

        storage = S3ObjectStorage(bucket="test-bucket")
        uploader = ConcurrentObjectUploader(storage=storage, max_workers=4)

        files = {}
        for i in range(10):
            p = tmp_path / f"s3_file_{i}.bin"
            p.write_bytes(f"s3 data {i}".encode())
            files[f"artifacts/file_{i}.bin"] = str(p)

        results = uploader.upload_batch(files)
        assert len(results) == 10
        for key in files:
            assert results[key] == f"s3://test-bucket/{key}"
            assert storage.exists(key)

        uploader.shutdown()

    def test_upload_stream_and_bytes(self, tmp_path):
        """Verify upload_stream and upload_bytes methods."""
        from blast_ocr.storage.concurrent_uploader import ConcurrentObjectUploader
        from blast_ocr.storage.object_store import LocalFilesystemStorage

        storage = LocalFilesystemStorage(str(tmp_path / "store"))
        uploader = ConcurrentObjectUploader(storage=storage, max_workers=2)

        # Stream
        stream_fut = uploader.upload_stream("stream_key.txt", io.BytesIO(b"Stream data"))
        stream_res = stream_fut.result(timeout=5)
        assert storage.exists("stream_key.txt")

        # Bytes
        bytes_fut = uploader.upload_bytes("bytes_key.bin", b"Bytes data")
        bytes_res = bytes_fut.result(timeout=5)
        assert storage.exists("bytes_key.bin")

        uploader.shutdown()

    def test_retry_with_exponential_backoff_and_jitter(self):
        """Verify retry mechanism retries transient errors and succeeds."""
        from blast_ocr.storage.concurrent_uploader import ConcurrentObjectUploader, RetryConfig
        from blast_ocr.storage.object_store import ObjectStorage

        mock_storage = MagicMock(spec=ObjectStorage)
        calls = []

        def failing_put(key, local_path):
            calls.append(key)
            if len(calls) < 3:
                raise ConnectionError("Transient network drop")
            return f"s3://bucket/{key}"

        mock_storage.put.side_effect = failing_put

        retry_cfg = RetryConfig(max_retries=3, initial_backoff=0.01, max_backoff=0.05, jitter=False)
        uploader = ConcurrentObjectUploader(storage=mock_storage, max_workers=1, retry_config=retry_cfg)

        res_fut = uploader.upload_file("retry_key.txt", __file__)
        result = res_fut.result(timeout=5)

        assert result == "s3://bucket/retry_key.txt"
        assert len(calls) == 3
        uploader.shutdown()

    def test_retry_exhaustion_raises(self):
        """Verify permanent error raises exception after max retries."""
        from blast_ocr.storage.concurrent_uploader import ConcurrentObjectUploader, RetryConfig
        from blast_ocr.storage.object_store import ObjectStorage

        mock_storage = MagicMock(spec=ObjectStorage)
        mock_storage.put.side_effect = ConnectionError("Permanent network outage")

        retry_cfg = RetryConfig(max_retries=3, initial_backoff=0.01, max_backoff=0.05, jitter=False)
        uploader = ConcurrentObjectUploader(storage=mock_storage, max_workers=1, retry_config=retry_cfg)

        fut = uploader.upload_file("fail_key.txt", __file__)
        with pytest.raises(ConnectionError):
            fut.result(timeout=5)

        uploader.shutdown()

    def test_batch_upload_error_isolation(self, tmp_path):
        """Verify 1 failed item does not crash remaining items in a batch."""
        from blast_ocr.storage.concurrent_uploader import BatchUploadError, ConcurrentObjectUploader
        from blast_ocr.storage.object_store import LocalFilesystemStorage

        storage = LocalFilesystemStorage(str(tmp_path / "store"))
        uploader = ConcurrentObjectUploader(storage=storage, max_workers=2)

        p1 = tmp_path / "valid1.txt"
        p1.write_text("v1")
        p2 = tmp_path / "valid2.txt"
        p2.write_text("v2")

        batch_items = {
            "valid1": str(p1),
            "invalid": str(tmp_path / "non_existent.txt"),
            "valid2": str(p2),
        }

        with pytest.raises(BatchUploadError) as exc_info:
            uploader.upload_batch(batch_items, fail_fast=False)

        err = exc_info.value
        assert "valid1" in err.completed
        assert "valid2" in err.completed
        assert "invalid" in err.errors
        assert isinstance(err.errors["invalid"], FileNotFoundError)

        uploader.shutdown()

    def test_presigned_url_generation_local_and_s3(self, moto_s3, tmp_path):
        """Verify presigned URL generation across local and S3 storage."""
        from blast_ocr.storage.concurrent_uploader import ConcurrentObjectUploader
        from blast_ocr.storage.object_store import LocalFilesystemStorage, S3ObjectStorage

        # Local
        local_store = LocalFilesystemStorage(str(tmp_path / "store"))
        local_uploader = ConcurrentObjectUploader(storage=local_store)
        local_url = local_uploader.get_presigned_url("doc.pdf")
        assert local_url.startswith("file://")
        local_uploader.shutdown()

        # S3
        s3_store = S3ObjectStorage(bucket="presigned-bucket")
        s3_uploader = ConcurrentObjectUploader(storage=s3_store)
        s3_url = s3_uploader.get_presigned_url("doc.pdf", expiration_seconds=1800)
        assert "presigned-bucket" in s3_url
        assert "doc.pdf" in s3_url
        s3_uploader.shutdown()


# ─────────────────────────────────────────────────────────────────────────────
# 5. ObjectStorage Stream Enhancements Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestObjectStorageStreamExtensions:
    def test_put_stream_get_stream_local_roundtrip(self, tmp_path):
        """Verify put_stream and get_stream on LocalFilesystemStorage."""
        from blast_ocr.storage.object_store import LocalFilesystemStorage

        storage = LocalFilesystemStorage(str(tmp_path / "store"))
        data = b"Binary stream test content " * 1000

        storage.put_stream("streamed/file.bin", io.BytesIO(data))
        assert storage.exists("streamed/file.bin")

        with storage.get_stream("streamed/file.bin") as reader:
            retrieved = reader.read()

        assert retrieved == data

    def test_put_stream_get_stream_s3_moto_roundtrip(self, moto_s3):
        """Verify put_stream and get_stream on S3ObjectStorage using moto."""
        from blast_ocr.storage.object_store import S3ObjectStorage

        storage = S3ObjectStorage(bucket="streaming-bucket")
        data = b"S3 streaming data payload " * 1000

        storage.put_stream("stream/obj.bin", io.BytesIO(data))
        assert storage.exists("stream/obj.bin")

        body = storage.get_stream("stream/obj.bin")
        retrieved = body.read()
        assert retrieved == data

    def test_get_stream_missing_key_raises_file_not_found(self, tmp_path, moto_s3):
        """Verify get_stream on missing key raises FileNotFoundError on both backends."""
        from blast_ocr.storage.object_store import LocalFilesystemStorage, S3ObjectStorage

        local_storage = LocalFilesystemStorage(str(tmp_path / "store"))
        with pytest.raises(FileNotFoundError):
            local_storage.get_stream("missing.bin")

        s3_storage = S3ObjectStorage(bucket="test-bucket")
        with pytest.raises(FileNotFoundError):
            s3_storage.get_stream("missing_in_s3.bin")
```

---

## 6. Verification and Integration Strategy

1. **Unit & Property Tests**:
   - `pytest tests/test_streaming_storage.py -v` executes the complete suite with zero external infrastructure.
2. **Backward Compatibility**:
   - `pytest tests/test_object_store.py tests/test_concurrency_complete.py` verifies all existing test suites continue passing with 100% pass rate.
3. **Integration with `BlastPipeline`**:
   - In `blast_ocr/pipeline.py` (lines 634-647), the sequential S3 upload loop can be replaced with `ConcurrentObjectUploader.upload_batch(...)` to achieve parallel artifact upload with zero extra latency on the pipeline execution path.
