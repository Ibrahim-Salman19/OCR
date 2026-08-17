"""
blast_ocr.cache.tiered_cache

Tiered OCR Cache: L1 In-Memory LRU Cache + L2 Asynchronous Disk Cache.
Eliminates fsync latency from the OCR critical path by spooling disk writes
to a background daemon thread while providing sub-millisecond in-memory lookups.
"""

import hashlib
import json
import logging
import os
import queue
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# PERF: Try to use orjson for high-throughput JSON serialization
try:
    import orjson
    USE_ORJSON = True
except ImportError:
    USE_ORJSON = False


class AsyncCacheWriter:
    """
    Background worker queue for non-blocking disk persistence.
    Eliminates fsync latency from the OCR critical path.
    """

    def __init__(self, cache_dir: Union[str, Path]):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._queue: queue.Queue[Optional[Tuple[str, Dict[str, Any]]]] = queue.Queue()
        self._running = True
        self._thread = threading.Thread(
            target=self._worker_loop, name="AsyncCacheWriterWorker", daemon=True
        )
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
                tmp_dest = self.cache_dir / f".tmp_{key}_{os.getpid()}_{time.time_ns()}.json"
                
                if USE_ORJSON:
                    with open(tmp_dest, "wb") as f:
                        f.write(orjson.dumps(value, option=orjson.OPT_INDENT_2))
                        f.flush()
                        os.fsync(f.fileno())
                else:
                    with open(tmp_dest, "w", encoding="utf-8") as f:
                        json.dump(value, f, ensure_ascii=False, indent=2)
                        f.flush()
                        os.fsync(f.fileno())

                os.replace(tmp_dest, dest)
            except Exception as e:
                logger.warning(f"Async cache write failed for key {key}: {e}")
            finally:
                self._queue.task_done()

    def write_async(self, key: str, value: Dict[str, Any]) -> None:
        """Enqueue a key-value write operation."""
        if self._running:
            self._queue.put((key, value))

    def flush(self) -> None:
        """Wait for all pending writes in the queue to complete."""
        self._queue.join()

    def stop(self) -> None:
        """Stop background worker gracefully."""
        if self._running:
            self._running = False
            self._queue.put(None)
            self._thread.join(timeout=2.0)


class TieredOCRCache:
    """
    Dual-tier cache: L1 In-Memory LRU + L2 Asynchronous Disk Cache.
    """

    HASH_CHUNK_SIZE = 64 * 1024  # 64KB
    FULL_HASH_THRESHOLD = 10 * 1024 * 1024  # 10MB

    def __init__(
        self,
        cache_dir: Union[str, Path],
        l1_capacity: int = 100,
        backend: Optional[Any] = None,
    ):
        self.cache_dir = Path(cache_dir)
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create cache directory {self.cache_dir}: {e}")

        self.l1_capacity = max(0, l1_capacity)
        self._l1_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.backend = backend
        self._lock = threading.Lock()
        self._async_writer = AsyncCacheWriter(self.cache_dir)

    @property
    def l1_cache(self) -> OrderedDict[str, Dict[str, Any]]:
        """Backwards-compatible access to the L1 cache dictionary."""
        return self._l1_cache

    def _compute_key_hash(self, key: str) -> str:
        """Compute SHA256 hash of a string key."""
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def _get_disk_paths(self, key: str) -> List[Path]:
        """Return candidate disk file paths for a given key."""
        paths = []
        paths.append(self.cache_dir / f"{key}.json")
        hashed = self._compute_key_hash(key)
        if hashed != key:
            paths.append(self.cache_dir / f"{hashed}.json")
        return paths

    def get_file_hash(self, filepath: str) -> str:
        """Generate hash of file using partial/full content for performance."""
        try:
            file_size = os.path.getsize(filepath)
            if file_size <= self.FULL_HASH_THRESHOLD:
                with open(filepath, "rb") as f:
                    return hashlib.sha256(f.read()).hexdigest()

            sha256_hash = hashlib.sha256()
            with open(filepath, "rb") as f:
                sha256_hash.update(f.read(self.HASH_CHUNK_SIZE))
                sha256_hash.update(str(file_size).encode("utf-8"))
                f.seek(-self.HASH_CHUNK_SIZE, os.SEEK_END)
                sha256_hash.update(f.read(self.HASH_CHUNK_SIZE))
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.warning(f"Failed to hash file {filepath}: {e}")
            return hashlib.sha256(str(filepath).encode("utf-8")).hexdigest()

    def get_cache_key(self, filepath: str, namespace: str = "") -> str:
        """Cache key combining file content hash with namespace fingerprint."""
        file_hash = self.get_file_hash(filepath)
        if not namespace:
            return file_hash
        combined = f"{file_hash}:{namespace}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached result by key (L1 memory fast-path -> L2 disk fallback)."""
        with self._lock:
            if self.l1_capacity > 0 and key in self._l1_cache:
                self._l1_cache.move_to_end(key)
                return self._l1_cache[key]

        # Check L2 disk cache
        for disk_path in self._get_disk_paths(key):
            if disk_path.exists():
                try:
                    with open(disk_path, "rb") as f:
                        data_bytes = f.read()
                    data = orjson.loads(data_bytes) if USE_ORJSON else json.loads(data_bytes.decode("utf-8"))

                    evicted = None
                    if self.l1_capacity > 0:
                        with self._lock:
                            self._l1_cache[key] = data
                            self._l1_cache.move_to_end(key)
                            if len(self._l1_cache) > self.l1_capacity:
                                evicted = self._l1_cache.popitem(last=False)
                    if evicted is not None:
                        self._write_sync(evicted[0], evicted[1])
                    return data
                except Exception as e:
                    logger.warning(f"Failed to read L2 disk cache at {disk_path}: {e}")

        # Flush in-flight async writes and re-check
        self._async_writer.flush()
        for disk_path in self._get_disk_paths(key):
            if disk_path.exists():
                try:
                    with open(disk_path, "rb") as f:
                        data_bytes = f.read()
                    data = orjson.loads(data_bytes) if USE_ORJSON else json.loads(data_bytes.decode("utf-8"))

                    evicted = None
                    if self.l1_capacity > 0:
                        with self._lock:
                            self._l1_cache[key] = data
                            self._l1_cache.move_to_end(key)
                            if len(self._l1_cache) > self.l1_capacity:
                                evicted = self._l1_cache.popitem(last=False)
                    if evicted is not None:
                        self._write_sync(evicted[0], evicted[1])
                    return data
                except Exception as e:
                    logger.warning(f"Failed to read L2 disk cache at {disk_path}: {e}")

        return None

    def put(self, key: str, value: Dict[str, Any], sync: bool = False) -> None:
        """Save result to L1 memory and L2 disk cache (sync or async spool)."""
        evicted = None
        with self._lock:
            if self.l1_capacity > 0:
                self._l1_cache[key] = value
                self._l1_cache.move_to_end(key)
                if len(self._l1_cache) > self.l1_capacity:
                    evicted = self._l1_cache.popitem(last=False)

        if evicted is not None:
            self._write_sync(evicted[0], evicted[1])

        if sync or self.l1_capacity == 0:
            self._write_sync(key, value)
        else:
            self._async_writer.write_async(key, value)

    def _write_sync(self, key: str, value: Dict[str, Any]) -> None:
        """Synchronous atomic disk write."""
        try:
            dest = self.cache_dir / f"{key}.json"
            tmp_dest = self.cache_dir / f".tmp_{key}_{os.getpid()}_{time.time_ns()}.json"
            if USE_ORJSON:
                with open(tmp_dest, "wb") as f:
                    f.write(orjson.dumps(value, option=orjson.OPT_INDENT_2))
                    f.flush()
                    os.fsync(f.fileno())
            else:
                with open(tmp_dest, "w", encoding="utf-8") as f:
                    json.dump(value, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
            os.replace(tmp_dest, dest)
        except Exception as e:
            logger.warning(f"Synchronous cache write failed for key {key}: {e}")

    def get_cached_result(self, filepath: str, namespace: str = "") -> Optional[Dict[str, Any]]:
        """Retrieve cached result by hashing filepath + namespace."""
        key = self.get_cache_key(filepath, namespace)
        return self.get(key)

    def save_to_cache(self, filepath: str, result: Dict[str, Any], namespace: str = "", sync: bool = False) -> None:
        """Save OCR result to cache by hashing filepath + namespace."""
        key = self.get_cache_key(filepath, namespace)
        self.put(key, result, sync=sync)

    def invalidate(self, filepath: str, namespace: str = "") -> None:
        """Remove cached result from L1 and L2."""
        key = self.get_cache_key(filepath, namespace)
        with self._lock:
            if key in self._l1_cache:
                del self._l1_cache[key]

        for disk_path in self._get_disk_paths(key):
            if disk_path.exists():
                try:
                    disk_path.unlink()
                except OSError:
                    pass

    def flush(self) -> None:
        """Flush all pending async writes to L2 disk."""
        self._async_writer.flush()

    def clear(self) -> None:
        """Clear both L1 in-memory cache and L2 disk cache."""
        with self._lock:
            self._l1_cache.clear()
        self.flush()
        if self.cache_dir.exists():
            for f in self.cache_dir.glob("*.json"):
                try:
                    f.unlink()
                except OSError:
                    pass

    def prune_cache(self, max_size_mb: float = 50.0) -> int:
        """Prunes oldest L2 cache files if total directory size exceeds max_size_mb."""
        self.flush()
        if not self.cache_dir.exists():
            return 0

        files = [f for f in self.cache_dir.glob("*.json") if not f.name.startswith(".tmp_")]
        total_bytes = sum(f.stat().st_size for f in files)
        max_bytes = max_size_mb * 1024 * 1024

        pruned_count = 0
        if total_bytes > max_bytes:
            files.sort(key=lambda x: x.stat().st_mtime)
            for f in files:
                sz = f.stat().st_size
                try:
                    f.unlink()
                    total_bytes -= sz
                    pruned_count += 1
                except OSError:
                    pass
                if total_bytes <= max_bytes:
                    break
        return pruned_count

    def close(self) -> None:
        """Close cache and stop async write workers."""
        self.flush()
        self._async_writer.stop()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
