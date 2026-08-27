"""
tests/e2e/tier1_features/test_f13_concurrent_uploader.py

Tier 1 Isolated Feature Tests: Feature 13 - Concurrent Object Storage Uploader
Covers:
- Background asynchronous file upload returning Future URI
- Concurrent batch upload across multi-worker thread pool
- Multipart chunked streaming for large artifacts (>8MB)
- Exponential backoff retry on transient upload failures
- Graceful pool shutdown draining pending upload tasks
"""

from concurrent.futures import Future
from pathlib import Path


from blast_ocr.storage.object_store import LocalFilesystemStorage, ObjectStorage


# ============================================================================
# Interface / Reference Implementation for Feature 13 Specification
# ============================================================================

from blast_ocr.storage.concurrent_uploader import ConcurrentObjectUploader


# ============================================================================
# Test Cases (>= 5 Tests)
# ============================================================================

def test_f13_concurrent_upload_file_returns_future_uri(tmp_path):
    """
    Test 1: Tests upload_file schedules a background task and returns a Future
    resolving to the backend storage URI.
    """
    storage = LocalFilesystemStorage(base_dir=str(tmp_path / "store"))
    uploader = ConcurrentObjectUploader(storage=storage, max_workers=2)

    src_file = tmp_path / "artifact_1.pdf"
    src_file.write_text("Sample PDF export content", encoding="utf-8")

    future = uploader.upload_file(key="jobs/42/doc.pdf", local_path=src_file)
    assert isinstance(future, Future)

    result_uri = future.result(timeout=3.0)
    assert result_uri is not None
    assert storage.exists("jobs/42/doc.pdf")
    uploader.shutdown()


def test_f13_upload_batch_parallel_execution(tmp_path):
    """
    Test 2: Tests upload_batch concurrently uploads multiple files in parallel
    across the worker pool and returns mapping of keys to URIs.
    """
    storage = LocalFilesystemStorage(base_dir=str(tmp_path / "store"))
    uploader = ConcurrentObjectUploader(storage=storage, max_workers=4)

    items = {}
    for i in range(4):
        p = tmp_path / f"export_{i}.md"
        p.write_text(f"Markdown output {i}", encoding="utf-8")
        items[f"outputs/book_{i}.md"] = p

    results = uploader.upload_batch(items)
    assert len(results) == 4
    for k in items.keys():
        assert k in results
        assert storage.exists(k)
    uploader.shutdown()


def test_f13_multipart_chunked_streaming_for_large_files(tmp_path, mock_s3_storage):
    """
    Test 3: Tests that files exceeding chunk size trigger multipart upload logic.
    """
    class MockMultipartStorage(ObjectStorage):
        def __init__(self, s3_backend):
            self.s3 = s3_backend
            self.multipart_called = False

        def put(self, key: str, local_path: str) -> str:
            return self.s3.put_object(key, Path(local_path).read_bytes())["Key"]

        def get(self, key: str, dest_path: str) -> str:
            return dest_path

        def exists(self, key: str) -> bool:
            return key in self.s3.objects

        def delete(self, key: str) -> None:
            self.s3.delete_object(key)

        def put_multipart(self, key: str, local_path: str, chunk_size: int) -> str:
            self.multipart_called = True
            upload_id = self.s3.create_multipart_upload(key)
            with open(local_path, "rb") as f:
                part_num = 1
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    self.s3.upload_part(upload_id, part_num, chunk)
                    part_num += 1
            self.s3.complete_multipart_upload(key, upload_id)
            return f"s3://blast-ocr-bucket/{key}"

    storage = MockMultipartStorage(mock_s3_storage)
    # Configure uploader with 1MB chunk size
    uploader = ConcurrentObjectUploader(storage=storage, max_workers=2, chunk_size_mb=1)

    large_file = tmp_path / "large_archive.pdf"
    # Write 2.5 MB file
    large_file.write_bytes(b"A" * (2500 * 1024))

    future = uploader.upload_file("archives/large_archive.pdf", large_file)
    res = future.result(timeout=5.0)

    assert "s3://" in res
    assert storage.multipart_called is True
    assert storage.exists("archives/large_archive.pdf")
    uploader.shutdown()


def test_f13_upload_retry_with_backoff_on_transient_failure(tmp_path):
    """
    Test 4: Tests that transient upload failures (e.g. temporary network error)
    are automatically retried with backoff and succeed on subsequent attempt.
    """
    class FlakyStorage(LocalFilesystemStorage):
        def __init__(self, base_dir: str):
            super().__init__(base_dir)
            self.attempts = 0

        def put(self, key: str, local_path: str) -> str:
            self.attempts += 1
            if self.attempts < 2:
                raise ConnectionResetError("Transient network drop during upload")
            return super().put(key, local_path)

    flaky_storage = FlakyStorage(base_dir=str(tmp_path / "store"))
    uploader = ConcurrentObjectUploader(storage=flaky_storage, max_workers=2, max_retries=3)

    src = tmp_path / "retry_test.txt"
    src.write_text("Resilient upload payload", encoding="utf-8")

    fut = uploader.upload_file("retry/doc.txt", src)
    res = fut.result(timeout=4.0)

    assert res is not None
    assert flaky_storage.attempts == 2
    assert flaky_storage.exists("retry/doc.txt")
    uploader.shutdown()


def test_f13_uploader_graceful_shutdown_drains_queue(tmp_path):
    """
    Test 5: Tests shutdown(wait=True) waits for all in-flight upload tasks
    to complete before shutting down worker pool.
    """
    storage = LocalFilesystemStorage(base_dir=str(tmp_path / "store"))
    uploader = ConcurrentObjectUploader(storage=storage, max_workers=2)

    futures = []
    for i in range(3):
        p = tmp_path / f"drain_{i}.txt"
        p.write_text(f"Drain task {i}", encoding="utf-8")
        futures.append(uploader.upload_file(f"drain/item_{i}.txt", p))

    # Trigger graceful shutdown immediately
    uploader.shutdown(wait=True)

    # All futures should have completed successfully
    for i, fut in enumerate(futures):
        assert fut.done()
        assert storage.exists(f"drain/item_{i}.txt")
