"""
blast_ocr.storage.concurrent_uploader

Concurrent multipart S3/MinIO and local storage background uploader.
Enables asynchronous artifact uploads in worker threads with automatic
multipart chunking, exponential backoff retries, and graceful pool draining.
"""

import io
import logging
import os
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, BinaryIO, Dict, Generator, Optional, Union

from blast_ocr.storage.object_store import get_object_storage

logger = logging.getLogger(__name__)


class StreamBufferManager:
    """
    Utility for managing memory-bounded streaming buffers and chunked IO streams.
    """

    @staticmethod
    def create_buffer(initial_bytes: Optional[bytes] = None) -> io.BytesIO:
        """Create an in-memory byte buffer."""
        return io.BytesIO(initial_bytes) if initial_bytes else io.BytesIO()

    @staticmethod
    def stream_chunks(
        stream: BinaryIO, chunk_size: int = 64 * 1024
    ) -> Generator[bytes, None, None]:
        """Yield chunks from a binary stream without loading the entire stream into memory."""
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            yield chunk

    @staticmethod
    def spool_to_temp(
        stream: BinaryIO,
        dest_path: Optional[Union[str, Path]] = None,
        chunk_size: int = 64 * 1024,
    ) -> Path:
        """Spool a stream to a temporary or designated file on disk."""
        if dest_path:
            target = Path(dest_path)
            target.parent.mkdir(parents=True, exist_ok=True)
        else:
            import tempfile
            fd, tmp_name = tempfile.mkstemp(prefix="blast_spool_")
            os.close(fd)
            target = Path(tmp_name)

        with open(target, "wb") as f:
            for chunk in StreamBufferManager.stream_chunks(stream, chunk_size):
                f.write(chunk)
        return target


class ConcurrentObjectUploader:
    """
    Concurrent multipart S3/MinIO and local storage background uploader.
    """

    def __init__(
        self,
        storage: Optional[Any] = None,
        max_workers: int = 4,
        chunk_size_mb: int = 8,
        max_retries: int = 3,
    ):
        self.storage = storage if storage is not None else get_object_storage()
        self.max_workers = max(1, min(max_workers, 128))
        self.chunk_size_bytes = max(1, chunk_size_mb) * 1024 * 1024
        self.max_retries = max(1, max_retries)
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers, thread_name_prefix="ConcurrentUploaderWorker"
        )
        self._is_shutdown = False

    def _get_bucket_name(self) -> str:
        """Determines the target bucket name dynamically from the storage backend or config."""
        from blast_ocr.config import config
        return (
            getattr(self.storage, "bucket_name", None)
            or getattr(self.storage, "bucket", None)
            or getattr(config, "s3_bucket", "blast-ocr-artifacts")
        )

    def _upload_file_task(self, key: str, local_path: Path) -> str:
        """Internal worker task with backoff retry."""
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                file_size = local_path.stat().st_size
                # If file exceeds chunk size threshold and backend supports multipart
                if file_size > self.chunk_size_bytes and hasattr(self.storage, "put_multipart"):
                    return getattr(self.storage, "put_multipart")(key, str(local_path), self.chunk_size_bytes)
                
                if hasattr(self.storage, "put"):
                    return self.storage.put(key, str(local_path))
                elif hasattr(self.storage, "put_object"):
                    # MockS3StorageBackend compatibility
                    self.storage.put_object(key, local_path.read_bytes())
                    return f"s3://{self._get_bucket_name()}/{key}"
                elif hasattr(self.storage, "put_bytes"):
                    return self.storage.put_bytes(key, local_path.read_bytes())
                else:
                    raise AttributeError("Storage backend does not implement put or put_object")
            except Exception as e:
                last_exc = e
                logger.warning(
                    f"Upload attempt {attempt}/{self.max_retries} failed for {key}: {e}"
                )
                if attempt < self.max_retries:
                    time.sleep(0.05 * (2 ** (attempt - 1)))
                else:
                    raise last_exc
        raise RuntimeError("Upload exhausted retries")

    def upload_file(self, key: str, local_path: Union[str, Path]) -> Future:
        """
        Schedule an asynchronous background upload of a local file.
        Returns a concurrent.futures.Future resolving to the backend URI string.
        """
        if self._is_shutdown:
            raise RuntimeError("Uploader is already shut down")

        path = Path(local_path)
        if not path.exists():
            fut: Future = Future()
            fut.set_exception(FileNotFoundError(f"Local file not found: {local_path}"))
            return fut

        return self._executor.submit(self._upload_file_task, key, path)

    def upload_stream(
        self, key: str, stream: BinaryIO, length: Optional[int] = None
    ) -> Future:
        """
        Schedule an asynchronous background upload of a byte stream.
        """
        if self._is_shutdown:
            raise RuntimeError("Uploader is already shut down")

        def _task() -> str:
            raw_bytes = stream.getvalue() if hasattr(stream, "getvalue") else stream.read()
            stream_len = len(raw_bytes)

            if stream_len > self.chunk_size_bytes and hasattr(self.storage, "create_multipart_upload"):
                upload_id = getattr(self.storage, "create_multipart_upload")(key)
                part_num = 1
                for offset in range(0, stream_len, self.chunk_size_bytes):
                    chunk = raw_bytes[offset : offset + self.chunk_size_bytes]
                    getattr(self.storage, "upload_part")(upload_id, part_num, chunk)
                    part_num += 1
                getattr(self.storage, "complete_multipart_upload")(key, upload_id)
                return f"s3://{self._get_bucket_name()}/{key}"
            elif hasattr(self.storage, "put_stream"):
                buf = io.BytesIO(raw_bytes)
                return self.storage.put_stream(key, buf, content_length=stream_len)
            elif hasattr(self.storage, "put_object"):
                self.storage.put_object(key, raw_bytes)
                return f"s3://{self._get_bucket_name()}/{key}"
            elif hasattr(self.storage, "put_bytes"):
                return self.storage.put_bytes(key, raw_bytes)
            else:
                raise AttributeError("Storage backend does not implement put_stream, put_object, or put_bytes")

        return self._executor.submit(_task)

    def upload_batch(self, items: Dict[str, Union[str, Path]]) -> Dict[str, str]:
        """
        Concurrently upload multiple files in parallel across worker threads.
        Returns a mapping of {key: backend_uri}.
        """
        futures = {k: self.upload_file(k, v) for k, v in items.items()}
        results = {}
        for k, fut in futures.items():
            results[k] = fut.result(timeout=15.0)
        return results

    def shutdown(self, wait: bool = True) -> None:
        """Gracefully shut down uploader pool, waiting for in-flight tasks if wait=True."""
        self._is_shutdown = True
        self._executor.shutdown(wait=wait)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(wait=True)
