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
import os
import time
import queue
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Optional, Tuple



# ============================================================================
# Interface / Reference Implementation for Feature 12 Specification
# ============================================================================

class AsyncCacheWriter:
    """
    Background worker queue for non-blocking disk persistence.
    Eliminates fsync latency from the OCR critical path.
    """

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._queue: queue.Queue[Optional[Tuple[str, Dict[str, Any]]]] = queue.Queue()
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    def _worker_loop(self) -> None:
        while self._running:
            try:
                item = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if item is None:  # Sentinel to stop
                self._queue.task_done()
                break

            key, value = item
            try:
                dest = self.cache_dir / f"{key}.json"
                tmp_dest = self.cache_dir / f".tmp_{key}_{time.time_ns()}.json"
                with open(tmp_dest, "w", encoding="utf-8") as f:
                    json.dump(value, f, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_dest, dest)
            except Exception:
                pass
            finally:
                self._queue.task_done()

    def write_async(self, key: str, value: Dict[str, Any]) -> None:
        self._queue.put((key, value))

    def flush(self) -> None:
        self._queue.join()

    def stop(self) -> None:
        self._running = False
        self._queue.put(None)
        self._thread.join(timeout=2.0)


class TieredOCRCache:
    """
    Dual-tier cache: L1 In-Memory LRU + L2 Asynchronous Disk Cache.
    """

    def __init__(self, cache_dir: str | Path, l1_capacity: int = 100):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.l1_capacity = max(1, l1_capacity)
        self._l1_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._async_writer = AsyncCacheWriter(self.cache_dir)

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            # 1. Check L1 in-memory cache
            if key in self._l1_cache:
                self._l1_cache.move_to_end(key)
                return self._l1_cache[key]

        # 2. Check L2 disk cache
        disk_path = self.cache_dir / f"{key}.json"
        if disk_path.exists():
            try:
                with open(disk_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Promote to L1
                with self._lock:
                    self._l1_cache[key] = data
                    if len(self._l1_cache) > self.l1_capacity:
                        self._l1_cache.popitem(last=False)
                return data
            except Exception:
                return None

        return None

    def put(self, key: str, value: Dict[str, Any], sync: bool = False) -> None:
        with self._lock:
            self._l1_cache[key] = value
            self._l1_cache.move_to_end(key)
            if len(self._l1_cache) > self.l1_capacity:
                self._l1_cache.popitem(last=False)

        if sync:
            dest = self.cache_dir / f"{key}.json"
            tmp_dest = self.cache_dir / f".tmp_{key}_{time.time_ns()}.json"
            with open(tmp_dest, "w", encoding="utf-8") as f:
                json.dump(value, f, ensure_ascii=False)
            os.replace(tmp_dest, dest)
        else:
            self._async_writer.write_async(key, value)

    def flush(self) -> None:
        self._async_writer.flush()

    def clear(self) -> None:
        with self._lock:
            self._l1_cache.clear()
        for f in self.cache_dir.glob("*.json"):
            try:
                f.unlink()
            except OSError:
                pass

    def prune_cache(self, max_size_mb: float = 50.0) -> int:
        """Prunes oldest L2 cache files if total directory size exceeds max_size_mb."""
        self.flush()
        files = list(self.cache_dir.glob("*.json"))
        total_bytes = sum(f.stat().st_size for f in files)
        max_bytes = max_size_mb * 1024 * 1024
        
        pruned_count = 0
        if total_bytes > max_bytes:
            # Sort by mtime ascending (oldest first)
            files.sort(key=lambda x: x.stat().st_mtime)
            for f in files:
                sz = f.stat().st_size
                f.unlink()
                total_bytes -= sz
                pruned_count += 1
                if total_bytes <= max_bytes:
                    break
        return pruned_count

    def close(self) -> None:
        self._async_writer.stop()


# ============================================================================
# Test Cases (>= 5 Tests)
# ============================================================================

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
    disk_file = tmp_path / "cache" / f"{key}.json"
    assert disk_file.exists()
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
