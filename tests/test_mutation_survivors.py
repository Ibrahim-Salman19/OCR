"""
Tests to kill mutants that survived Phase 10.
"""
import pytest

def test_cache_fallback_hash():
    from blast_ocr.cache.manager import OCRCache
    import tempfile
    cache = OCRCache(tempfile.mkdtemp())
    h = cache.get_file_hash("/invalid/path/that/does/not/exist.png")
    assert isinstance(h, str)
    assert len(h) == 64

def test_database_init_failure():
    from blast_ocr.storage.database import OCRDatabase
    import tempfile
    # An invalid URL should fail initialization
    with pytest.raises(Exception):
        OCRDatabase("sqlite:////invalid/dir/db.sqlite")
