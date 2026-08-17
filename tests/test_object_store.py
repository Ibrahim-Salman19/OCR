"""
tests/test_object_store.py

Tests for blast_ocr.storage.object_store (Execution Plan v2 Phase 8).

LocalFilesystemStorage is tested directly (no infra needed). S3ObjectStorage
is tested against moto's in-process mocked S3 -- this proves the boto3
call logic is correct without needing a real server, and additionally
against a real MinIO container when Docker is available in this environment
(auto-skipped otherwise) for genuine end-to-end confidence.
"""

import os
import shutil
import subprocess
import time

import pytest


# ─────────────────────────────────────────────────────────────────────────
# LocalFilesystemStorage -- no infra required
# ─────────────────────────────────────────────────────────────────────────

class TestLocalFilesystemStorage:
    def test_put_and_get_roundtrip(self, tmp_path):
        from blast_ocr.storage.object_store import LocalFilesystemStorage

        storage = LocalFilesystemStorage(str(tmp_path / "store"))
        src = tmp_path / "source.txt"
        src.write_text("hello object storage")

        storage.put("jobs/1/source.txt", str(src))
        assert storage.exists("jobs/1/source.txt")

        dest = tmp_path / "fetched.txt"
        storage.get("jobs/1/source.txt", str(dest))
        assert dest.read_text() == "hello object storage"

    def test_delete_removes_object(self, tmp_path):
        from blast_ocr.storage.object_store import LocalFilesystemStorage

        storage = LocalFilesystemStorage(str(tmp_path / "store"))
        src = tmp_path / "source.txt"
        src.write_text("data")
        storage.put("k.txt", str(src))
        assert storage.exists("k.txt")
        storage.delete("k.txt")
        assert not storage.exists("k.txt")

    def test_get_missing_key_raises(self, tmp_path):
        from blast_ocr.storage.object_store import LocalFilesystemStorage

        storage = LocalFilesystemStorage(str(tmp_path / "store"))
        with pytest.raises(FileNotFoundError):
            storage.get("does/not/exist.txt", str(tmp_path / "out.txt"))

    def test_path_traversal_key_rejected(self, tmp_path):
        """
        BUG-PREVENTION: a job_id/filename-derived key must not be able to
        escape the storage root via "../" components.
        """
        from blast_ocr.storage.object_store import LocalFilesystemStorage

        storage = LocalFilesystemStorage(str(tmp_path / "store"))
        src = tmp_path / "source.txt"
        src.write_text("data")
        with pytest.raises(ValueError):
            storage.put("../../etc/passwd", str(src))

    def test_put_bytes_convenience(self, tmp_path):
        from blast_ocr.storage.object_store import LocalFilesystemStorage

        storage = LocalFilesystemStorage(str(tmp_path / "store"))
        storage.put_bytes("raw.bin", b"raw content")
        dest = tmp_path / "out.bin"
        storage.get("raw.bin", str(dest))
        assert dest.read_bytes() == b"raw content"


# ─────────────────────────────────────────────────────────────────────────
# S3ObjectStorage against moto (mocked S3, no server needed)
# ─────────────────────────────────────────────────────────────────────────

@pytest.fixture
def moto_s3():
    moto = pytest.importorskip("moto")
    with moto.mock_aws():
        yield


class TestS3ObjectStorageMoto:
    def test_put_creates_bucket_and_object(self, moto_s3, tmp_path):
        from blast_ocr.storage.object_store import S3ObjectStorage

        storage = S3ObjectStorage(bucket="test-blast-bucket")
        src = tmp_path / "source.txt"
        src.write_text("moto-backed content")

        uri = storage.put("jobs/1/source.txt", str(src))
        assert uri == "s3://test-blast-bucket/jobs/1/source.txt"
        assert storage.exists("jobs/1/source.txt")

    def test_get_roundtrip(self, moto_s3, tmp_path):
        from blast_ocr.storage.object_store import S3ObjectStorage

        storage = S3ObjectStorage(bucket="test-blast-bucket")
        src = tmp_path / "source.txt"
        src.write_text("roundtrip data")
        storage.put("k.txt", str(src))

        dest = tmp_path / "fetched.txt"
        storage.get("k.txt", str(dest))
        assert dest.read_text() == "roundtrip data"

    def test_exists_false_for_missing_key(self, moto_s3):
        from blast_ocr.storage.object_store import S3ObjectStorage

        storage = S3ObjectStorage(bucket="test-blast-bucket")
        assert storage.exists("nothing/here.txt") is False

    def test_delete_removes_object(self, moto_s3, tmp_path):
        from blast_ocr.storage.object_store import S3ObjectStorage

        storage = S3ObjectStorage(bucket="test-blast-bucket")
        src = tmp_path / "source.txt"
        src.write_text("to be deleted")
        storage.put("k.txt", str(src))
        assert storage.exists("k.txt")
        storage.delete("k.txt")
        assert not storage.exists("k.txt")

    def test_factory_selects_backend_from_config(self, moto_s3, monkeypatch):
        from blast_ocr.storage.object_store import get_object_storage, S3ObjectStorage
        from blast_ocr.config import config

        monkeypatch.setattr(config, "storage_backend", "s3")
        monkeypatch.setattr(config, "s3_bucket", "test-blast-bucket")
        storage = get_object_storage()
        assert isinstance(storage, S3ObjectStorage)


# ─────────────────────────────────────────────────────────────────────────
# S3ObjectStorage against a REAL MinIO container, when Docker is available
# ─────────────────────────────────────────────────────────────────────────

def _docker_available() -> bool:
    try:
        return subprocess.run(
            ["docker", "info"], capture_output=True, timeout=10
        ).returncode == 0
    except Exception:
        return False


@pytest.fixture(scope="module")
def real_minio():
    if not _docker_available() or not shutil.which("docker"):
        pytest.skip("Docker not available; skipping real-MinIO verification")

    container_name = "blast-ocr-test-minio"
    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
    proc = subprocess.run(
        [
            "docker", "run", "-d", "--rm", "--name", container_name,
            "-p", "19000:9000",
            "-e", "MINIO_ROOT_USER=testadmin",
            "-e", "MINIO_ROOT_PASSWORD=testadmin123",
            "minio/minio", "server", "/data",
        ],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        pytest.skip(f"Could not start MinIO container: {proc.stderr}")

    try:
        # Wait for MinIO to accept connections.
        import socket
        deadline = time.time() + 30
        up = False
        while time.time() < deadline:
            try:
                with socket.create_connection(("localhost", 19000), timeout=1):
                    up = True
                    break
            except OSError:
                time.sleep(1)
        if not up:
            pytest.skip("MinIO container did not become ready in time")
        yield {
            "endpoint_url": "http://localhost:19000",
            "access_key": "testadmin",
            "secret_key": "testadmin123",
        }
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)


class TestPipelineObjectStorageMirror:
    """
    Proves BlastPipeline.process_job() actually calls the object storage
    abstraction when storage_backend="s3", not just that the abstraction
    exists in isolation -- the same "wired vs. merely present" gap found and
    fixed for IngestionGateway/JobStateMachine/RunManifest in ADR 0009.
    """

    def test_process_job_mirrors_outputs_to_s3_when_enabled(self, moto_s3, tmp_path):
        from unittest.mock import MagicMock, patch
        from blast_ocr.pipeline import BlastPipeline
        from blast_ocr.storage.object_store import S3ObjectStorage

        pptx_path = tmp_path / "slides.pptx"
        pptx_path.write_bytes(b"PK\x03\x04placeholder")

        db = MagicMock()
        db.create_job.return_value = 1
        db.update_job_status.return_value = None
        db.save_result.return_value = None
        db.save_metric.return_value = None

        pipeline = BlastPipeline()
        pipeline.db = db
        pipeline._config.storage_backend = "s3"
        pipeline._config.s3_bucket = "test-blast-bucket"

        with patch("blast_ocr.pipeline.extract_from_pptx", return_value="Slide text"), \
             patch(
                 "blast_ocr.pipeline.save_output",
                 return_value=(str(tmp_path / "o.md"), str(tmp_path / "o.docx")),
             ):
            (tmp_path / "o.md").write_text("Slide text")
            (tmp_path / "o.docx").write_bytes(b"docx-bytes")
            result = pipeline.process_job(str(pptx_path), output_dir=str(tmp_path))

        assert result["status"] == "success"

        # If the mirror step ran, the manifest (always generated) must exist
        # under the job's key in the real (moto-mocked) S3 bucket.
        storage = S3ObjectStorage(bucket="test-blast-bucket")
        job_id = result["job_id"]
        assert storage.exists(f"jobs/{job_id}/{pptx_path.stem}_manifest.json")


class TestS3ObjectStorageRealMinIO:
    def test_put_get_delete_roundtrip_against_real_minio(self, real_minio, tmp_path):
        from blast_ocr.storage.object_store import S3ObjectStorage

        storage = S3ObjectStorage(
            bucket="blast-real-test",
            endpoint_url=real_minio["endpoint_url"],
            access_key=real_minio["access_key"],
            secret_key=real_minio["secret_key"],
        )

        src = tmp_path / "source.txt"
        src.write_text("real minio content")
        uri = storage.put("jobs/1/source.txt", str(src))
        assert uri == "s3://blast-real-test/jobs/1/source.txt"
        assert storage.exists("jobs/1/source.txt")

        dest = tmp_path / "fetched.txt"
        storage.get("jobs/1/source.txt", str(dest))
        assert dest.read_text() == "real minio content"

        storage.delete("jobs/1/source.txt")
        assert not storage.exists("jobs/1/source.txt")
