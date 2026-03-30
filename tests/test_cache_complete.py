"""
PHASE 4: OCRCache hash correctness, collision resistance, and edge cases.
"""
import pytest
import os
import tempfile
import hashlib
import json

@pytest.fixture
def cache(tmp_path):
    from blast_ocr.cache.manager import OCRCache
    return OCRCache(cache_dir=str(tmp_path))

# ── Test 1: Different content → different hash ────────────────────────────
def test_hash_different_for_different_content(cache, tmp_path):
    f1 = tmp_path / "a.png"; f1.write_bytes(b"content_A" * 1000)
    f2 = tmp_path / "b.png"; f2.write_bytes(b"content_B" * 1000)
    assert cache.get_file_hash(str(f1)) != cache.get_file_hash(str(f2))

# ── Test 2: Same content → same hash (deterministic) ─────────────────────
def test_hash_deterministic(cache, tmp_path):
    f = tmp_path / "test.png"; f.write_bytes(b"stable_content" * 5000)
    h1 = cache.get_file_hash(str(f))
    h2 = cache.get_file_hash(str(f))
    assert h1 == h2, "Hash is not deterministic"

# ── Test 3: Partial hash — large file uses head+size+tail strategy ────────
def test_partial_hash_large_file(cache, tmp_path):
    """Two files with same first+last 64KB but different middle = different hash?"""
    # HASH_CHUNK_SIZE = 64KB
    chunk = 64 * 1024
    
    # File A: AAA...BBB...CCC (different middle)
    f1 = tmp_path / "large_a.bin"
    f1.write_bytes(b"A" * chunk + b"MIDDLE_A" * 1000 + b"C" * chunk)
    
    # File B: AAA...ZZZ...CCC (same start/end, different middle)
    f2 = tmp_path / "large_b.bin"
    f2.write_bytes(b"A" * chunk + b"MIDDLE_B" * 1000 + b"C" * chunk)
    
    h1 = cache.get_file_hash(str(f1))
    h2 = cache.get_file_hash(str(f2))
    
    # NOTE: With partial hashing (only head+size+tail), these WILL have the same hash
    # if only the middle is different. Document this as a known limitation.
    if h1 == h2:
        pytest.fail(
            "BUG (KNOWN LIMITATION): OCRCache uses partial hashing. "
            "Two large files with identical first 64KB, same size, and identical last 64KB "
            "but different middle content will produce a HASH COLLISION. "
            "The same page could be served stale cached results from a different page. "
            "Fix: use full file hash for files under 10MB, partial only for very large files."
        )

# ── Test 4: Cache miss returns None ──────────────────────────────────────
def test_cache_miss_returns_none(cache):
    result = cache.get("nonexistent_hash_12345")
    assert result is None

# ── Test 5: Cache set then get returns same data ─────────────────────────
def test_cache_set_get_roundtrip(cache):
    data = {"page": 1, "text": "hello world", "confidence": 0.95, "bbox_count": 3}
    cache.set("test_key", data)
    result = cache.get("test_key")
    assert result == data

# ── Test 6: Unicode text survives cache roundtrip ─────────────────────────
def test_cache_unicode_text(cache):
    """Urdu text (the stated use case) must survive JSON serialization."""
    data = {"page": 1, "text": "یہ اردو متن ہے", "confidence": 0.88}
    cache.set("urdu_key", data)
    result = cache.get("urdu_key")
    assert result["text"] == "یہ اردو متن ہے", "Unicode text corrupted in cache"

# ── Test 7: Cache handles corrupted JSON file gracefully ──────────────────
def test_cache_handles_corrupted_json(cache, tmp_path):
    """BUG HYPOTHESIS: Corrupted .json file causes unhandled exception."""
    # Write a bad JSON file directly
    bad_file = tmp_path / "corrupted_hash.json"
    bad_file.write_text("{this is not valid json}")
    
    # get() should return None, not raise
    try:
        result = cache.get("corrupted_hash")
        # Should either return None or raise gracefully — not crash
    except Exception as e:
        # If it raises, the caller (process_page_wrapper) will crash
        pytest.fail(f"Cache.get() raised on corrupted JSON: {e}. Should return None.")

# ── Test 8: Cache on non-existent file path returns fallback hash ─────────
def test_cache_hash_nonexistent_file(cache):
    """BUG HYPOTHESIS: get_file_hash on missing file crashes."""
    try:
        h = cache.get_file_hash("/nonexistent/path/image.png")
        # Should return a fallback hash (of the filepath string), not raise
        assert isinstance(h, str), f"Expected string hash, got {type(h)}"
        assert len(h) == 64, f"Expected 64-char SHA256 hash, got {len(h)} chars"
    except FileNotFoundError as e:
        pytest.fail(
            f"BUG: get_file_hash raises FileNotFoundError on missing file: {e}. "
            f"Should return fallback hash of filepath string instead."
        )

# ── Test 9: save_to_cache and get_cached_result roundtrip ─────────────────
def test_save_to_cache_and_retrieve(cache, tmp_path):
    f = tmp_path / "real_image.png"
    f.write_bytes(b"fake_image_content" * 100)
    
    data = {"page": 2, "text": "cached result", "confidence": 0.7}
    cache.save_to_cache(str(f), data)
    result = cache.get_cached_result(str(f))
    assert result == data

# ── Test 10: invalidate removes cached entry ─────────────────────────────
def test_cache_invalidation(cache, tmp_path):
    f = tmp_path / "to_invalidate.png"
    f.write_bytes(b"some content")
    
    cache.save_to_cache(str(f), {"page": 1, "text": "stale"})
    assert cache.get_cached_result(str(f)) is not None
    
    cache.invalidate(str(f))
    assert cache.get_cached_result(str(f)) is None, \
        "Cache invalidation failed — stale result still returned"
