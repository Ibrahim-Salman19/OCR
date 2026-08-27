"""
tests/e2e/tier1_features/test_f12_tiered_cache.py

Tier 1 Isolated Feature Tests: Feature 12 - Tiered OCR Cache (L1/L2)
Covers:
- L1 in-memory LRU cache fast-path retrieval
- L1 capacity eviction with transparent L2 disk fallback
- AsyncCacheWriter non-blocking write spooling and flush
- Cache miss handling and dual-tier clear/invalidation
- L2 disk storage quota and size budget pruning
"""

import json
import time
from blast_ocr.cache.tiered_cache import TieredOCRCache


def test_f12_l1_in_memory_cache_hit_fast_path(tmp_path):
    """
    Test 1: Tests that cached OCR page results are retrieved directly from
    L1 in-memory LRU without triggering disk read.
    """
    cache = TieredOCRCache(tmp_path / "cache", l1_capacity=10)
    key = "sha256_page_001"
    payload = {"page": 1, "text": "Instant L1 cache hit", "confidence": 0.99}

    # Store item
    cache.put(key, payload, sync=True)

    # Delete disk file to prove subsequent get() hits L1 in-memory directly
    disk_files = cache._get_disk_paths(key)
    for disk_file in disk_files:
        if disk_file.exists():
            disk_file.unlink()

    # Query key - should succeed via L1 memory
    retrieved = cache.get(key)
    assert retrieved is not None
    assert retrieved["text"] == "Instant L1 cache hit"
    assert retrieved["confidence"] == 0.99
    cache.close()


def test_f12_l1_lru_eviction_to_l2_disk(tmp_path):
    """
    Test 2: Tests that inserting items beyond L1 capacity evicts oldest items from L1,
    but they remain accessible via L2 disk cache and are re-promoted to L1 on read.
    """
    cache = TieredOCRCache(tmp_path / "cache", l1_capacity=2)

    # Insert 3 items into cache with capacity=2
    cache.put("k1", {"val": "item 1"}, sync=True)
    cache.put("k2", {"val": "item 2"}, sync=True)
    cache.put("k3", {"val": "item 3"}, sync=True)

    # k1 was evicted from L1 memory (capacity 2), but persists on L2 disk
    with cache._lock:
        assert "k1" not in cache._l1_cache, "k1 should have been evicted from L1"
        assert "k2" in cache._l1_cache
        assert "k3" in cache._l1_cache

    # Retrieve k1 -> should transparently fetch from L2 disk and re-promote to L1
    res_k1 = cache.get("k1")
    assert res_k1 is not None
    assert res_k1["val"] == "item 1"

    with cache._lock:
        assert "k1" in cache._l1_cache, "k1 should be re-promoted to L1"
    cache.close()


def test_f12_async_cache_writer_nonblocking_and_flush(tmp_path):
    """
    Test 3: Tests that put(key, value, sync=False) delegates disk write to
    AsyncCacheWriter without blocking, and flush() persists all writes to disk.
    """
    cache = TieredOCRCache(tmp_path / "cache", l1_capacity=10)
    
    # Asynchronously queue 5 write items
    for i in range(5):
        cache.put(f"async_k_{i}", {"index": i, "content": f"Async page {i}"}, sync=False)

    # Flush all queued async writes
    cache.flush()

    # Verify all 5 files exist on disk
    for i in range(5):
        disk_path = tmp_path / "cache" / f"async_k_{i}.json"
        assert disk_path.exists(), f"File {disk_path} should exist after flush"
        with open(disk_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["index"] == i
    cache.close()


def test_f12_cache_miss_and_dual_tier_clear(tmp_path):
    """
    Test 4: Tests that cache miss returns None, and clear() empties both
    L1 in-memory cache and L2 disk cache.
    """
    cache = TieredOCRCache(tmp_path / "cache", l1_capacity=10)
    
    # Cache miss
    assert cache.get("non_existent_key") is None

    # Populate cache
    cache.put("entry_1", {"text": "T1"}, sync=True)
    cache.put("entry_2", {"text": "T2"}, sync=True)
    assert cache.get("entry_1") is not None
    assert cache.get("entry_2") is not None

    # Clear dual tier
    cache.clear()
    assert cache.get("entry_1") is None
    assert cache.get("entry_2") is None
    assert len(list(tmp_path.glob("cache/*.json"))) == 0
    cache.close()


def test_f12_l2_cache_quota_pruning(tmp_path):
    """
    Test 5: Tests prune_cache() deletes oldest cache files when total size
    exceeds the configured maximum MB budget.
    """
    cache_dir = tmp_path / "cache"
    cache = TieredOCRCache(cache_dir, l1_capacity=10)

    # Write 4 large dummy cache files (each ~100 KB)
    large_payload = {"data": "X" * (100 * 1024)}
    for i in range(4):
        cache.put(f"large_k_{i}", large_payload, sync=True)
        time.sleep(0.01)  # Ensure distinct mtime

    # Total size is ~400 KB (0.4 MB)
    # Prune with budget 0.2 MB (200 KB) -> should delete 2 oldest files
    pruned = cache.prune_cache(max_size_mb=0.2)
    assert pruned >= 2, f"Expected at least 2 pruned files, got {pruned}"

    # Remaining files should be within budget
    remaining_files = list(cache_dir.glob("*.json"))
    total_remaining_bytes = sum(f.stat().st_size for f in remaining_files)
    assert total_remaining_bytes <= 0.25 * 1024 * 1024
    cache.close()
