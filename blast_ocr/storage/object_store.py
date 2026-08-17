"""
blast_ocr.storage.object_store

Artifact object storage abstraction (Execution Plan v2 Phase 8 & Milestone 3).
Supports both LocalFilesystemStorage and S3ObjectStorage (AWS S3 / MinIO) behind
a unified protocol with streaming, multipart uploads, concurrent batching,
and presigned URL generation.
"""

import io
import logging
import os
import shutil
import tempfile
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import BinaryIO, Dict, Optional, Union

logger = logging.getLogger(__name__)


class ObjectStorage(ABC):
    """Artifact storage contract: put, get, exists, delete, streaming, and batching."""

    @abstractmethod
    def put(self, key: str, local_path: str) -> str:
        """Store the file at local_path under `key`. Returns backend-specific locator URI."""

    @abstractmethod
    def get(self, key: str, dest_path: str) -> str:
        """Fetch the object stored under `key` to dest_path. Returns dest_path."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if an object exists under `key`."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete object stored under `key`."""

    def put_bytes(self, key: str, data: bytes) -> str:
        """Convenience: store raw bytes without caller-managed temp file."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
            tmp_path = f.name
        try:
            return self.put(key, tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def put_stream(self, key: str, stream: BinaryIO, content_length: Optional[int] = None) -> str:
        """Stream data into storage under `key` (default fallback)."""
        data = stream.read()
        return self.put_bytes(key, data)

    def get_stream(self, key: str) -> BinaryIO:
        """Return a readable byte stream for object under `key` (default fallback)."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp_path = f.name
        try:
            self.get(key, tmp_path)
            with open(tmp_path, "rb") as f:
                data = f.read()
            return io.BytesIO(data)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def put_batch_concurrent(self, items: Dict[str, str], max_concurrency: int = 4) -> Dict[str, str]:
        """Concurrently upload a dictionary of {key: local_path}."""
        results = {}
        with ThreadPoolExecutor(max_workers=max(1, max_concurrency)) as executor:
            future_to_key = {executor.submit(self.put, k, p): k for k, p in items.items()}
            for fut in as_completed(future_to_key):
                key = future_to_key[fut]
                results[key] = fut.result()
        return results

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned access URL for the object."""
        return f"file://{key}"

    def put_multipart(self, key: str, local_path: str, chunk_size: int = 8 * 1024 * 1024) -> str:
        """Multipart upload fallback for large files."""
        return self.put(key, local_path)


class LocalFilesystemStorage(ObjectStorage):
    def __init__(self, base_dir: Union[str, Path]):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # Reject path traversal: a key must resolve to a path inside base_dir.
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

    def put_stream(self, key: str, stream: BinaryIO, content_length: Optional[int] = None) -> str:
        dest = self._resolve(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            shutil.copyfileobj(stream, f)
        return str(dest)

    def get_stream(self, key: str) -> BinaryIO:
        src = self._resolve(key)
        if not src.exists():
            raise FileNotFoundError(f"Object not found: {key!r}")
        return open(src, "rb")

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        dest = self._resolve(key)
        return f"file://{dest}"

    def put_multipart(self, key: str, local_path: str, chunk_size: int = 8 * 1024 * 1024) -> str:
        dest = self._resolve(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "rb") as src, open(dest, "wb") as dst:
            while True:
                buf = src.read(chunk_size)
                if not buf:
                    break
                dst.write(buf)
        return str(dest)


class S3ObjectStorage(ObjectStorage):
    """S3-compatible storage with MinIO path-style support, streaming, and connection pooling."""

    def __init__(
        self,
        bucket: str,
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        region_name: str = "us-east-1",
    ):
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        # Configure path-style addressing and adaptive retries for MinIO / S3 compatibility
        s3_config = {
            "addressing_style": "path",
        } if endpoint_url else {}

        config = Config(
            max_pool_connections=25,
            retries={"max_attempts": 5, "mode": "adaptive"},
            s3=s3_config,
        )

        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region_name,
            config=config,
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
        except Exception as e:
            logger.warning(f"Head/create bucket connection warning for {self.bucket!r}: {e}")

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

    def put_stream(self, key: str, stream: BinaryIO, content_length: Optional[int] = None) -> str:
        self._client.upload_fileobj(stream, self.bucket, key)
        return f"s3://{self.bucket}/{key}"

    def get_stream(self, key: str) -> BinaryIO:
        response = self._client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"]

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def put_multipart(self, key: str, local_path: str, chunk_size: int = 8 * 1024 * 1024) -> str:
        """Stream multipart upload for large objects."""
        from boto3.s3.transfer import TransferConfig
        transfer_config = TransferConfig(
            multipart_threshold=chunk_size,
            multipart_chunksize=chunk_size,
            max_concurrency=4,
            use_threads=True,
        )
        self._client.upload_file(
            local_path,
            self.bucket,
            key,
            Config=transfer_config,
        )
        return f"s3://{self.bucket}/{key}"


def get_object_storage(settings=None) -> ObjectStorage:
    """
    Factory selecting a backend from `settings` (OCRConfig-shaped object).
    """
    if settings is None:
        from blast_ocr.config import config as settings

    if settings.storage_backend == "s3":
        return S3ObjectStorage(
            bucket=settings.s3_bucket,
            endpoint_url=settings.s3_endpoint_url,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
        )
    return LocalFilesystemStorage(base_dir=os.path.join(settings.output_dir, "_object_store"))


def artifact_key(job_id: int, filename: str) -> str:
    """Deterministic, collision-resistant key for a job's artifact."""
    safe_name = Path(filename).name
    return f"jobs/{job_id}/{safe_name}"
