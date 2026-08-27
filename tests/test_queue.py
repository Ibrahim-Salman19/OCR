"""
tests/test_queue.py

Integration tests for blast_ocr.queue (Redis + RQ durable queue, Execution Plan
v2 Phase 5/8). These run against a REAL redis-server + a real RQ SimpleWorker
process (in-process, synchronous execution of one queued job) rather than
mocking redis/rq -- the point of a queue backend is durability across process
boundaries, which a mock can't meaningfully verify.

Requires `redis-server` reachable at BLAST_OCR_REDIS_URL (default
redis://localhost:6379/0). Skipped automatically if unreachable, so this file
does not fail CI/dev environments without Redis installed.
"""

import pytest


try:
    from blast_ocr.queue.client import is_queue_available
    _REDIS_UP = is_queue_available()
except Exception:
    _REDIS_UP = False

pytestmark = pytest.mark.skipif(
    not _REDIS_UP, reason="redis-server not reachable; queue integration tests skipped"
)


def _unique_queue_name():
    import uuid
    return f"blast_ocr_test_{uuid.uuid4().hex[:8]}"


def test_redis_reachable():
    """Sanity check: the fixture skip logic above actually detected a live Redis."""
    from blast_ocr.queue.client import get_redis_connection
    conn = get_redis_connection()
    assert conn.ping() is True


def test_enqueue_creates_db_job_and_rq_job(tmp_path):
    """enqueue_job() must create a durable DB row *before* returning, so a
    caller has a job_id to poll even if the worker hasn't picked it up yet."""
    from blast_ocr.queue.client import enqueue_job, get_queue
    from blast_ocr.storage.database import OCRDatabase

    src = tmp_path / "sample.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 50)

    q = get_queue()
    q.empty()  # isolate from any leftover jobs on the shared default queue

    result = enqueue_job(str(src), output_dir=str(tmp_path))
    assert result["job_id"] is not None
    assert result["rq_job_id"] is not None

    db = OCRDatabase()
    job = db.get_job(result["job_id"])
    assert job is not None
    assert job.status == "received"

    assert len(q) >= 1


def test_worker_processes_queued_job_end_to_end(tmp_path):
    """
    Full real round trip: enqueue a job onto the real Redis queue, run an
    actual RQ worker (SimpleWorker: synchronous, in this process, no fork --
    appropriate for a short-lived test) to drain it, and confirm the DB
    reflects a terminal state. Uses a throwaway queue name so this test
    doesn't race concurrently-run test workers on the shared default queue.
    """
    from rq import Queue, SimpleWorker
    from unittest.mock import patch

    from blast_ocr.queue.client import get_redis_connection
    from blast_ocr.queue.tasks import run_ocr_job
    from blast_ocr.storage.database import OCRDatabase

    src = tmp_path / "sample.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 50)

    db = OCRDatabase()
    job_id = db.create_job(src.name, page_count=0)

    conn = get_redis_connection()
    queue_name = _unique_queue_name()
    q = Queue(queue_name, connection=conn)

    # Mock the actual OCR engine call so this test doesn't require a real
    # RapidOCR/EasyOCR model load -- it is verifying queue plumbing (a real
    # worker process pulling and executing a real job), not OCR accuracy.
    fake_page_result = {
        "page": 1, "text": "hello world", "confidence": 0.95, "processing_time": 0.01,
    }
    with patch("blast_ocr.core.worker.process_page_wrapper", return_value=fake_page_result), \
         patch("blast_ocr.pipeline.process_page_wrapper", return_value=fake_page_result):
        rq_job = q.enqueue(run_ocr_job, str(src), str(tmp_path), job_id, None)

        worker = SimpleWorker([q], connection=conn)
        worker.work(burst=True)  # process everything currently queued, then return

    rq_job.refresh()
    assert rq_job.is_finished, f"RQ job did not finish cleanly: status={rq_job.get_status()}"

    job = db.get_job(job_id)
    assert job.status in ("succeeded", "succeeded_with_warnings", "failed"), (
        f"Job left in a non-terminal state after worker.work(burst=True): {job.status}"
    )
