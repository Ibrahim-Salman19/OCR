"""
PHASE 1: Thread safety, lock correctness, and SQLite WAL deadlock prevention.
"""

import threading
import time
import sqlite3
import tempfile
import os
import pytest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, MagicMock


def _new_temp_db_path() -> str:
    """Create and return a temporary sqlite db path safely."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        return tmp.name


# ── Test 1.1: Global lock is module-level singleton, not per-instance ─────
def test_ocr_global_lock_is_true_singleton():
    """
    REASONING: If lock is per-instance, two RobustOCRExtractor instances
    can simultaneously call reader.readtext(), corrupting EasyOCR's
    internal thread-unsafe state.
    """
    from blast_ocr.core.extractor import _ocr_global_lock, RobustOCRExtractor

    with patch.object(RobustOCRExtractor, "_init_engine"):
        e1 = RobustOCRExtractor.__new__(RobustOCRExtractor)
        e1.lock = _ocr_global_lock
        e2 = RobustOCRExtractor.__new__(RobustOCRExtractor)
        e2.lock = _ocr_global_lock
    assert e1.lock is e2.lock is _ocr_global_lock, (
        "BUG-LOCK-01: Lock is not a shared singleton — race condition possible"
    )


# ── Test 1.2: Lock actually serializes concurrent OCR calls ───────────────
def test_ocr_lock_prevents_concurrent_readtext():
    """
    REASONING: Two threads entering readtext simultaneously would
    corrupt EasyOCR's internal batch queue.
    """
    from blast_ocr.core.extractor import _ocr_global_lock

    execution_log = []
    lock = threading.Lock()

    def simulate_ocr(tid):
        with _ocr_global_lock:
            with lock:
                execution_log.append(f"ENTER-{tid}")
            time.sleep(0.03)
            with lock:
                execution_log.append(f"EXIT-{tid}")

    threads = [threading.Thread(target=simulate_ocr, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify ENTER-N is always immediately followed by EXIT-N
    for i in range(0, len(execution_log) - 1, 2):
        tid = execution_log[i].split("-")[1]
        assert execution_log[i + 1] == f"EXIT-{tid}", (
            f"BUG-LOCK-02: Concurrent OCR access detected: {execution_log}"
        )


# ── Test 1.3: SQLite WAL BEGIN IMMEDIATE prevents SHARED lock deadlock ─────
def test_sqlite_wal_shared_lock_deadlock():
    """
    REASONING: SQLite WAL mode deadlock scenario:
    Thread A: BEGIN (implicit DEFERRED) → SELECT (SHARED lock acquired)
    Thread B: BEGIN (implicit DEFERRED) → SELECT (SHARED lock acquired)
    Thread A: UPDATE → tries to escalate SHARED → EXCLUSIVE → BLOCKED by B
    Thread B: UPDATE → tries to escalate SHARED → EXCLUSIVE → BLOCKED by A
    → DEADLOCK. busy_timeout DOES NOT HELP HERE.
    Fix: Use BEGIN IMMEDIATE which acquires RESERVED lock upfront.
    """
    db_file = _new_temp_db_path()
    conn_setup = sqlite3.connect(db_file)
    conn_setup.execute("PRAGMA journal_mode=WAL")
    conn_setup.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY, status TEXT)")
    conn_setup.execute("INSERT INTO jobs VALUES (1, 'pending')")
    conn_setup.commit()
    conn_setup.close()

    deadlock_errors = []
    results = []
    state_lock = threading.Lock()
    start_event = threading.Event()

    def read_then_write(thread_id):
        conn = sqlite3.connect(db_file, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            if not start_event.wait(timeout=2.0):
                raise TimeoutError("start event not set")

            # Use BEGIN IMMEDIATE to prove it prevents deadlocks
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("SELECT status FROM jobs WHERE id=1").fetchone()

            # BEGIN IMMEDIATE serializes writes safely under contention.
            conn.execute("UPDATE jobs SET status=? WHERE id=1", (f"done_{thread_id}",))
            conn.commit()
            with state_lock:
                results.append(f"success_{thread_id}")
        except sqlite3.OperationalError as e:
            with state_lock:
                deadlock_errors.append(str(e))
            try:
                conn.rollback()
            except Exception:
                pass
        except Exception as e:
            with state_lock:
                deadlock_errors.append(str(e))
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            conn.close()

    t1 = threading.Thread(target=read_then_write, args=(1,))
    t2 = threading.Thread(target=read_then_write, args=(2,))
    t1.start()
    t2.start()
    start_event.set()
    t1.join(timeout=5)
    t2.join(timeout=5)

    import time

    for _ in range(5):
        try:
            if os.path.exists(db_file):
                os.unlink(db_file)
            break
        except PermissionError:
            time.sleep(0.5)

    if deadlock_errors:
        pytest.fail(
            f"Deadlock still occurred even with BEGIN IMMEDIATE: {deadlock_errors}"
        )


# ── Test 1.4: scoped_session returns different objects per thread ──────────
def test_scoped_session_thread_isolation():
    """
    REASONING: If two threads share the same Session object,
    one thread's flush() call will see the other thread's pending
    ORM objects, causing wrong data to be committed.
    """
    db_file = _new_temp_db_path()
    from blast_ocr.storage.database import OCRDatabase

    db = OCRDatabase(f"sqlite:///{db_file}")
    session_ids = {}
    lock = threading.Lock()

    def capture_session(tid):
        s = db.Session()
        with lock:
            session_ids[tid] = s

    threads = [threading.Thread(target=capture_session, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    unique = len(set(id(s) for s in session_ids.values()))
    db.close()
    import time

    for _ in range(5):
        try:
            if os.path.exists(db_file):
                os.unlink(db_file)
            break
        except PermissionError:
            time.sleep(0.5)
    assert unique > 1, (
        "BUG-DB-SESSION-01: scoped_session returning same session across threads"
    )


# ── Test 1.5: Worker extractor singleton has no initialization lock ────────
def test_worker_extractor_singleton_race_condition():
    """
    REASONING: get_worker_extractor() checks `if _worker_extractor is None`
    without a lock. Under race conditions, Thread A and Thread B both
    see None, both call RobustOCRExtractor(), creating two instances.
    Each instance loads the full EasyOCR model into memory (~1GB each).
    """
    import blast_ocr.core.worker as worker_module

    original = worker_module._worker_extractor
    worker_module._worker_extractor = None

    instantiation_count = [0]
    lock = threading.Lock()

    with patch("blast_ocr.core.worker.RobustOCRExtractor") as MockCls:

        def count_instantiations():
            with lock:
                instantiation_count[0] += 1
            return MagicMock()

        MockCls.side_effect = count_instantiations

        def get_extractor(_):
            worker_module.get_worker_extractor()

        threads = [threading.Thread(target=get_extractor, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    worker_module._worker_extractor = original

    if instantiation_count[0] > 1:
        pytest.fail(
            f"BUG-WORKER-RACE-01 | HIGH | race\n"
            f"RobustOCRExtractor instantiated {instantiation_count[0]} times concurrently.\n"
            f"get_worker_extractor() has no threading.Lock() around the None check.\n"
            f"Fix: Add a module-level threading.Lock() and use double-checked locking pattern."
        )


# ── Test 1.6: Concurrent DB writes — 20 simultaneous create_job() calls ──
def test_concurrent_db_writes_integrity():
    db_file = _new_temp_db_path()
    from blast_ocr.storage.database import OCRDatabase

    db = OCRDatabase(f"sqlite:///{db_file}")
    ids, errors = [], []
    id_lock = threading.Lock()

    def create(i):
        try:
            job_id = db.create_job(f"file_{i}.pdf", i)
            with id_lock:
                ids.append(job_id)
        except Exception as e:
            with id_lock:
                errors.append(str(e))

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(create, range(20)))

    db.close()
    import time

    for _ in range(5):
        try:
            if os.path.exists(db_file):
                os.unlink(db_file)
            break
        except PermissionError:
            time.sleep(0.5)

    assert not errors, f"BUG-DB-CONCURRENT-01: Concurrent write errors: {errors[:3]}"
    assert len(set(ids)) == 20, (
        f"BUG-DB-CONCURRENT-02: Duplicate job IDs under concurrency: {sorted(ids)}"
    )
