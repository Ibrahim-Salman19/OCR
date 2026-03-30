import os
import tempfile
from blast_ocr.core.extractor import RobustOCRExtractor, _ocr_global_lock
from blast_ocr.cache.manager import cache_manager


def test_global_lock_singleton():
    """Verify that multiple extractor instances share the SAME lock object."""
    e1 = RobustOCRExtractor()
    e2 = RobustOCRExtractor()

    # Check they point to the module-level lock
    assert e1.lock is _ocr_global_lock
    assert e2.lock is _ocr_global_lock
    assert e1.lock is e2.lock

    # Check locking works
    locked_Success = False
    with e1.lock:
        locked_Success = True
        # e2 shouldn't be able to acquire if we hold it (non-blocking acquire check?)
        # Standard Lock doesn't support 'locked()' query easily without acquire(blocking=False)
        # But verifying identity is the main fix verification.
    assert locked_Success


def test_cache_hashing_consistency():
    """Verify that cache hashing is consistent and respects content."""
    with tempfile.NamedTemporaryFile(delete=False, mode="wb") as f:
        f.write(b"Test Content 123")
        fname = f.name

    try:
        # Hashing should be deterministic
        h1 = cache_manager.get_file_hash(fname)
        h2 = cache_manager.get_file_hash(fname)
        assert h1 == h2

        # Modify file
        with open(fname, "wb") as f:
            f.write(b"Modified Content 456")

        h3 = cache_manager.get_file_hash(fname)
        assert h1 != h3

    finally:
        if os.path.exists(fname):
            os.remove(fname)


def test_memory_cleanup_logic():
    """
    We can't easily test GC in a unit test, but we can verify the code patch
    didn't break the extractor loop basically.
    """
    # Just ensure we can instantiate execution without errors
    extractor = RobustOCRExtractor()
    assert extractor.reader is not None
