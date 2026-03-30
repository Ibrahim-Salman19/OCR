import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict
import logging
import threading

logger = logging.getLogger(__name__)

def _default_cache_dir() -> str:
    """Return a writable cache directory. Uses /tmp on Linux (Streamlit Cloud)."""
    if sys.platform == "win32":
        return "cache/ocr"
    return "/tmp/cache/ocr"

# PERF(phase3): Try to use orjson for faster JSON serialization (2-5x faster)
# Falls back to stdlib json if orjson is not installed
try:
    import orjson
    USE_ORJSON = True
except ImportError:
    USE_ORJSON = False
    logger.debug("orjson not available, using stdlib json (install orjson for 2-5x faster cache)")


class OCRCache:
    """Cache OCR results to avoid reprocessing"""
    
    # PERF(phase3): Chunk size for partial hashing (64KB)
    HASH_CHUNK_SIZE = 64 * 1024  # 64KB
    # FIX: Use full hash for files up to 10MB for safety (typical book page size)
    FULL_HASH_THRESHOLD = 10 * 1024 * 1024 
    
    def __init__(self, cache_dir=None):
        if cache_dir is None:
            cache_dir = _default_cache_dir()
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()  # FIX(phase3): Prevent race conditions on file writes
    
    def get_file_hash(self, filepath: str) -> str:
        """
        Generate hash of file using partial content for performance.
        
        PERF(phase3): HIGH-003 - For large files, reading the entire content
        for hashing is slow. We hash:
        - Whole file if < 10MB (Safe Threshold)
        - Else: First 64KB + file size + last 64KB
        """
        try:
            file_size = os.path.getsize(filepath)
            
            # Use full hash for images under 10MB (most book pages)
            if file_size <= self.FULL_HASH_THRESHOLD:
                with open(filepath, 'rb') as f:
                    return hashlib.sha256(f.read()).hexdigest()
            
            # For very large files, hash first + size + last chunks
            sha256_hash = hashlib.sha256()
            
            with open(filepath, 'rb') as f:
                # Hash first 64KB
                sha256_hash.update(f.read(self.HASH_CHUNK_SIZE))
                
                # Hash file size as bytes
                sha256_hash.update(str(file_size).encode('utf-8'))
                
                # Seek to last 64KB and hash
                f.seek(-self.HASH_CHUNK_SIZE, 2)  # 2 = SEEK_END
                sha256_hash.update(f.read(self.HASH_CHUNK_SIZE))
            
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.warning(f"Failed to hash file {filepath}: {e}")
            # Fallback: hash only the filepath string (safe - no filesystem access)
            fallback_data = str(filepath)
            return hashlib.sha256(fallback_data.encode()).hexdigest()
    
    def get(self, cache_key: str) -> Optional[Dict]:
        """Retrieve cached result by direct key (hash)"""
        try:
            cache_file = self.cache_dir / f"{cache_key}.json"
            if cache_file.exists():
                with open(cache_file, 'rb') as f:
                    data = f.read()
                    # PERF(phase3): Use orjson if available
                    if USE_ORJSON:
                        return orjson.loads(data)
                    else:
                        return json.loads(data.decode('utf-8'))
        except Exception as e:
            logger.warning(f"Cache read failed for key {cache_key}: {e}")
        return None

    def set(self, cache_key: str, result: Dict):
        """Save result by direct key (hash) securely via atomic rewrite"""
        import tempfile
        with self._lock:  # FIX(phase3): Thread-safe write
            try:
                cache_file = self.cache_dir / f"{cache_key}.json"
                fd, temp_path = tempfile.mkstemp(dir=str(self.cache_dir), prefix=".tmp_")
                
                try:
                    # BUG-CACHE-CORRUPTION-01 Fix: Atomic file write
                    if USE_ORJSON:
                        with os.fdopen(fd, 'wb') as f:
                            f.write(orjson.dumps(result, option=orjson.OPT_INDENT_2))
                            f.flush()
                            os.fsync(f.fileno())
                    else:
                        with os.fdopen(fd, 'w', encoding='utf-8') as f:
                            json.dump(result, f, ensure_ascii=False, indent=2)
                            f.flush()
                            os.fsync(f.fileno())
                            
                    # Atomically rename to target
                    # BUG-CACHE-WIN-01 Fix: Handle PermissionError on Windows os.replace
                    max_retries = 3
                    for i in range(max_retries):
                        try:
                            os.replace(temp_path, str(cache_file))
                            break
                        except PermissionError:
                            if i < max_retries - 1:
                                import time
                                time.sleep(0.1)
                            else:
                                raise
                except Exception as e:
                    if 'fd' in locals():
                        os.close(fd)
                    if os.path.exists(temp_path):
                        try: os.remove(temp_path)
                        except OSError: pass
                    raise e

            except Exception as e:
                logger.warning(f"Cache write failed for key {cache_key}: {e}")

    def get_cached_result(self, filepath: str) -> Optional[Dict]:
        """Retrieve cached OCR result if exists (by hashing file)"""
        try:
            file_hash = self.get_file_hash(filepath)
            return self.get(file_hash)
        except Exception as e:
            logger.warning(f"Cache read failed for {filepath}: {e}")
        return None
    
    def save_to_cache(self, filepath: str, result: Dict):
        """Save OCR result to cache (by hashing file)"""
        try:
            file_hash = self.get_file_hash(filepath)
            self.set(file_hash, result)
        except Exception as e:
            logger.warning(f"Cache write failed for {filepath}: {e}")
    
    def invalidate(self, filepath: str):
        """Remove cached result"""
        try:
            file_hash = self.get_file_hash(filepath)
            cache_file = self.cache_dir / f"{file_hash}.json"
            if cache_file.exists():
                cache_file.unlink()
        except Exception as e:
            logger.warning(f"Cache invalidation failed for {filepath}: {e}")

# Global cache instance
cache_manager = OCRCache()
