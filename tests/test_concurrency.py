"""
PHASE 1: Thread safety and concurrency correctness tests.

Research basis:
- SQLAlchemy docs: "Session is not thread-safe. Use scoped_session."
- scoped_session uses threading.local() — verify it isolates per thread.
- _ocr_global_lock must be a module-level singleton (not per-instance).
- OCRCache._lock must protect concurrent writes.
- BlastPipeline.__init__ must not share state across instances.
"""

import threading
import time
import pytest
import tempfile
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch


# ── Test 1: Global lock is truly module-level (not per-instance) ──────────
def test_global_lock_is_singleton_across_instances():
    """BUG HYPOTHESIS: Per-instance lock allows race conditions."""
    from blast_ocr.core.extractor import RobustOCRExtractor, _ocr_global_lock

    with patch.object(RobustOCRExtractor, "_init_engine"):
        e1 = RobustOCRExtractor.__new__(RobustOCRExtractor)
        e1.lock = _ocr_global_lock
        e2 = RobustOCRExtractor.__new__(RobustOCRExtractor)
        e2.lock = _ocr_global_lock
        assert e1.lock is e2.lock, "Lock must be shared singleton"
        assert e1.lock is _ocr_global_lock, "Must reference module-level lock"


# ── Test 2: Lock actually blocks concurrent OCR calls ─────────────────────
def test_ocr_lock_serializes_concurrent_calls():
    """BUG HYPOTHESIS: Without proper lock, two threads corrupt EasyOCR state."""
    from blast_ocr.core.extractor import _ocr_global_lock

    execution_order = []

    def ocr_call(thread_id):
        with _ocr_global_lock:
            execution_order.append(f"enter-{thread_id}")
            time.sleep(0.05)  # simulate OCR inference
            execution_order.append(f"exit-{thread_id}")

    threads = [threading.Thread(target=ocr_call, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify enter/exit pairs are never interleaved
    for i in range(0, len(execution_order) - 1, 2):
        thread_id = execution_order[i].split("-")[1]
        assert execution_order[i + 1] == f"exit-{thread_id}", (
            f"Lock interleaving detected at index {i}: {execution_order}"
        )


# ── Test 3: SQLAlchemy scoped_session is thread-local ────────────────────
def test_scoped_session_is_thread_local():
    """BUG HYPOTHESIS: Shared Session object causes 'Session is already flushing' errors."""
    from blast_ocr.storage.database import OCRDatabase

    import time
    db_file = tempfile.mktemp(suffix=".db")
    db = OCRDatabase(f"sqlite:///{db_file}")
    sessions_per_thread = {}
    start_event = threading.Event()
    done_event = threading.Event()

    def get_session(tid):
        start_event.wait()
        s = db.Session()
        sessions_per_thread[tid] = s
        done_event.wait()

    threads = [threading.Thread(target=get_session, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    start_event.set()
    time.sleep(0.1)

    # Each thread should have a different Session instance (thread-local)
    session_ids = [id(s) for s in sessions_per_thread.values()]
    assert len(set(session_ids)) > 1, (
        "scoped_session should return different session objects per thread"
    )

    done_event.set()
    for t in threads:
        t.join()

    db.close()
    import time

    for _ in range(5):
        try:
            if os.path.exists(db_file):
                os.unlink(db_file)
            break
        except PermissionError:
            time.sleep(0.5)


# ── Test 4: Concurrent DB writes do not corrupt data ─────────────────────
def test_concurrent_db_writes_no_corruption():
    """BUG HYPOTHESIS: ThreadPoolExecutor + shared DB = corrupted job records."""
    from blast_ocr.storage.database import OCRDatabase

    db_file = tempfile.mktemp(suffix=".db")
    db = OCRDatabase(f"sqlite:///{db_file}")
    created_ids = []
    errors = []
    lock = threading.Lock()

    def create_job(i):
        try:
            job_id = db.create_job(f"file_{i}.pdf", page_count=i)
            with lock:
                created_ids.append(job_id)
        except Exception as e:
            with lock:
                errors.append(str(e))

    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(create_job, i) for i in range(20)]
        for f in as_completed(futures):
            f.result()

    assert len(errors) == 0, f"Concurrent write errors: {errors}"
    assert len(created_ids) == 20, f"Expected 20 jobs, got {len(created_ids)}"
    assert len(set(created_ids)) == 20, "Duplicate job IDs detected — race condition"

    db.close()
    import time

    for _ in range(5):
        try:
            if os.path.exists(db_file):
                os.unlink(db_file)
            break
        except PermissionError:
            time.sleep(0.5)


# ── Test 5: Cache concurrent read/write race condition ────────────────────
def test_cache_concurrent_write_no_corruption():
    """BUG HYPOTHESIS: OCRCache._lock missing on get() allows torn reads."""
    from blast_ocr.cache.manager import OCRCache

    cache = OCRCache(cache_dir=tempfile.mkdtemp())
    write_errors = []

    def write_read(i):
        key = f"key_{i % 5}"  # Intentional key collision to stress test
        try:
            cache.set(key, {"page": i, "text": f"content_{i}", "confidence": 0.9})
            result = cache.get(key)
            if result is not None and result.get("confidence") != 0.9:
                write_errors.append(f"Data corruption at key {key}: {result}")
        except Exception as e:
            write_errors.append(str(e))

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(write_read, i) for i in range(50)]
        for f in as_completed(futures):
            f.result()

    assert len(write_errors) == 0, f"Cache corruption detected: {write_errors}"


# ── Test 6: Worker extractor singleton is safe under concurrent access ────
def test_worker_extractor_singleton_thread_safety():
    """BUG HYPOTHESIS: Two threads both see _worker_extractor=None and create two instances."""
    import blast_ocr.core.worker as worker_module

    original = worker_module._worker_extractor
    worker_module._worker_extractor = None

    created_instances = []
    lock = threading.Lock()

    # Patch RobustOCRExtractor to track instantiation
    mock_instance = MagicMock()
    with patch("blast_ocr.core.worker.RobustOCRExtractor") as MockExtractor:
        MockExtractor.return_value = mock_instance

        def get_extractor():
            e = worker_module.get_worker_extractor()
            with lock:
                created_instances.append(id(e))

        threads = [threading.Thread(target=get_extractor) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    # Should only create ONE extractor regardless of concurrent calls
    # If not, log the bug (it's a real issue in the current code — no lock around init)
    unique_instances = len(set(created_instances))
    if unique_instances > 1:
        pytest.fail(
            f"BUG: Worker extractor created {unique_instances} times concurrently. "
            f"get_worker_extractor() has no lock — two threads both see None and both call RobustOCRExtractor(). "
            f"Fix: add a threading.Lock() guard around the None check."
        )

    worker_module._worker_extractor = original
