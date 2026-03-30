"""
PHASE 3: Exhaustive database correctness tests.
Tests schema constraints, transaction rollback on failure,
query correctness, and edge cases in all OCRDatabase methods.
"""

import pytest
import tempfile
import os
import threading
from unittest.mock import patch


@pytest.fixture
def fresh_db():
    db_file = tempfile.mktemp(suffix=".db")
    from blast_ocr.storage.database import OCRDatabase

    db = OCRDatabase(f"sqlite:///{db_file}")
    yield db
    db.close()
    if os.path.exists(db_file):
        os.unlink(db_file)


# ── Test 1: create_job returns auto-incremented unique IDs ────────────────
def test_create_job_unique_ids(fresh_db):
    ids = [fresh_db.create_job(f"file_{i}.pdf", i) for i in range(10)]
    assert len(set(ids)) == 10, f"Duplicate job IDs: {ids}"
    assert all(isinstance(i, int) for i in ids), "Job IDs must be integers"


# ── Test 2: update_job_status — invalid status string validation ──────────
def test_update_job_status_invalid_status_validated(fresh_db):
    """Verify that only allowed statuses are accepted."""
    job_id = fresh_db.create_job("test.pdf", 5)
    with pytest.raises(ValueError, match="Invalid status"):
        fresh_db.update_job_status(job_id, "BANANA_STATUS")


# ── Test 3: update_job_status on nonexistent ID raises ValueError ─────────
def test_update_nonexistent_job_raises_error(fresh_db):
    """Verify that updating a nonexistent job raises ValueError."""
    with pytest.raises(ValueError, match="not found"):
        fresh_db.update_job_status(99999, "completed")


# ── Test 4: save_result with job_id=0 (invalid FK) ──────────────────────
def test_save_result_invalid_fk_job_id(fresh_db):
    """BUG HYPOTHESIS: FK constraint not enforced — orphaned OCRResult created."""
    try:
        fresh_db.save_result(
            job_id=99999,  # Non-existent job
            page_number=1,
            text="orphaned",
            confidence=0.9,
            processing_time=1.0,
        )
        # If we get here without error, FK constraints are not enforced
        pytest.fail(
            "BUG: save_result accepts non-existent job_id without FK violation. "
            "SQLite FK enforcement may not be enabled (PRAGMA foreign_keys=ON). "
            "This creates orphaned OCRResult records that are unqueryable."
        )
    except Exception:
        pass  # Expected — FK should be enforced


# ── Test 5: get_job returns None for nonexistent ID ───────────────────────
def test_get_job_nonexistent_returns_none(fresh_db):
    result = fresh_db.get_job(99999)
    assert result is None, f"Expected None, got {result}"


# ── Test 6: get_results returns empty list for job with no results ────────
def test_get_results_empty_for_new_job(fresh_db):
    job_id = fresh_db.create_job("empty.pdf", 0)
    results = fresh_db.get_results(job_id)
    assert results == [], f"Expected empty list, got {results}"


# ── Test 7: completed_at is only set when status=completed ───────────────
def test_completed_at_only_set_on_completed_status(fresh_db):
    job_id = fresh_db.create_job("test.pdf", 3)
    fresh_db.update_job_status(job_id, "failed")
    job = fresh_db.get_job(job_id)
    # completed_at should NOT be set for failed jobs
    assert job.completed_at is None, (
        "BUG: completed_at set even when status=failed. Should only be set for status=completed."
    )


# ── Test 8: page_count=0 allowed (valid for directory jobs) ──────────────
def test_create_job_zero_page_count(fresh_db):
    job_id = fresh_db.create_job("dir_job", 0)
    job = fresh_db.get_job(job_id)
    assert job.page_count == 0


# ── Test 9: Extremely long error_message does not truncate silently ────────
def test_error_message_very_long(fresh_db):
    long_error = "x" * 100_000
    job_id = fresh_db.create_job("test.pdf", 1)
    fresh_db.update_job_status(job_id, "failed", error_message=long_error)
    job = fresh_db.get_job(job_id)
    assert job.error_message == long_error, (
        f"Error message truncated: got {len(job.error_message)} chars, expected {len(long_error)}"
    )


# ── Test 10: Filename with special characters (SQL injection vector) ──────
def test_create_job_sql_injection_in_filename(fresh_db):
    """Security: SQL injection via filename."""
    malicious = "'; DROP TABLE ocr_jobs; --"
    job_id = fresh_db.create_job(malicious, 1)
    job = fresh_db.get_job(job_id)
    assert job is not None, "Job creation failed"
    assert job.filename == malicious, (
        "Filename was modified (should be stored verbatim)"
    )
    # Verify the table still exists
    all_jobs = fresh_db.get_results(job_id)
    assert all_jobs == []


# ── Test 11: Two OCRDatabase instances targeting same file ────────────────
def test_two_database_instances_same_file():
    """BUG HYPOTHESIS: Two pipelines targeting same DB file cause SQLITE_BUSY."""
    db_file = tempfile.mktemp(suffix=".db")
    from blast_ocr.storage.database import OCRDatabase

    try:
        db1 = OCRDatabase(f"sqlite:///{db_file}")
        db2 = OCRDatabase(f"sqlite:///{db_file}")

        errors = []

        def write_to_db(db, prefix, n=10):
            for i in range(n):
                try:
                    db.create_job(f"{prefix}_file_{i}.pdf", i)
                except Exception as e:
                    errors.append(str(e))

        t1 = threading.Thread(target=write_to_db, args=(db1, "db1"))
        t2 = threading.Thread(target=write_to_db, args=(db2, "db2"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        if errors:
            pytest.fail(
                f"Two OCRDatabase instances on same file caused errors: {errors[:3]}"
            )
    finally:
        try:
            db1.close()
            db2.close()
            import time

            for _ in range(5):
                try:
                    if os.path.exists(db_file):
                        os.unlink(db_file)
                    break
                except PermissionError:
                    time.sleep(0.5)
        except:
            pass


# ── Test 12: BEGIN IMMEDIATE transaction enforcement ────────────────────────
def test_database_uses_begin_immediate():
    """
    REASONING: All write paths must use BEGIN IMMEDIATE to prevent
    SQLite WAL SHARED lock upgrade deadlocks confirmed in Phase 1.
    """
    from pathlib import Path

    source = Path("blast_ocr/storage/database.py").read_text()
    # SQLAlchemy: isolation_level="IMMEDIATE" or BEGIN IMMEDIATE
    uses_immediate = (
        "IMMEDIATE" in source or "isolation_level" in source or "begin_nested" in source
    )
    if not uses_immediate:
        pytest.fail(
            "BUG-DB-ISOLATION-01 | HIGH | race\n"
            "Database does not use BEGIN IMMEDIATE isolation.\n"
            "Under concurrent load, SQLite WAL deadlocks are guaranteed.\n"
            "Fix: create_engine(db_url, connect_args={'isolation_level': 'IMMEDIATE'})"
        )


# ── Test 13: session.commit() Exceptions Trigger Rollback ─────────────────────
def test_database_exceptions_trigger_rollback(fresh_db):
    """Covers lines 90-92, 117-119, 134-136 in database.py"""
    job_id = fresh_db.create_job("test_rb.pdf", 1)

    with patch.object(
        fresh_db.session, "commit", side_effect=Exception("Mock Commit Error")
    ):
        with patch.object(fresh_db.session, "rollback") as mock_rb:
            with pytest.raises(Exception, match="Mock Commit Error"):
                fresh_db.create_job("fail.pdf", 1)
            mock_rb.assert_called_once()

        with patch.object(fresh_db.session, "rollback") as mock_rb:
            with pytest.raises(Exception, match="Mock Commit Error"):
                fresh_db.update_job_status(job_id, "processing")
            mock_rb.assert_called_once()

        with patch.object(fresh_db.session, "rollback") as mock_rb:
            with pytest.raises(Exception, match="Mock Commit Error"):
                fresh_db.save_result(job_id, 1, "text", 0.9, 1.0)
            mock_rb.assert_called_once()


# ── Test 14: __del__ ignores Exceptions ──────────────────────────────────────
def test_database_del_exception_handled():
    """Covers lines 164-165 in database.py (Exception catch in __del__)"""
    db_file = tempfile.mktemp(suffix=".db")
    from blast_ocr.storage.database import OCRDatabase

    db = OCRDatabase(f"sqlite:///{db_file}")

    with patch.object(db, "close", side_effect=Exception("Close Error")):
        # This shouldn't raise out
        db.__del__()

    if os.path.exists(db_file):
        try:
            os.unlink(db_file)
        except OSError:
            pass
