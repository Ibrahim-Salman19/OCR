import logging
import time
from typing import Dict, Optional

from blast_ocr.core.extractor import RobustOCRExtractor
from blast_ocr.cache.manager import cache_manager

# Global extractor instance for worker threads
# We lazily initialize this to avoid creating it in the main thread if not needed,
# though in threaded mode memory is shared.
_worker_extractor: Optional[RobustOCRExtractor] = None

def get_worker_extractor() -> RobustOCRExtractor:
    global _worker_extractor
    if _worker_extractor is None:
        _worker_extractor = RobustOCRExtractor()
    return _worker_extractor

def process_page_wrapper(image_path: str, page_num: int) -> Dict:
    """
    Worker function to process a single page.
    Designed to be picklable or runnable in threads.
    """
    logger = logging.getLogger(__name__)
    
    # 1. Check Cache
    # We use the cache manager directly
    try:
        file_hash = cache_manager.get_file_hash(image_path)
        if file_hash:
            cached = cache_manager.get_cached_result(file_hash) # Using public API
            # Or if main used .get(key), we use .get here. 
            # manager.py has 'get_cached_result(filepath)' which hashes internally, 
            # and 'set(key, val)'. 
            # Let's use the efficient get_file_hash + direct key lookup if possible, 
            # but manager.py's get_cached_result does both.
            
            # Re-reading manager.py: 
            # get_cached_result(filepath) -> returns dict or None.
            # It handles hashing internally.
            cached = cache_manager.get_cached_result(image_path)
            if cached:
                logger.info(f"Page {page_num}: Cache hit")
                cached['page'] = page_num
                return cached
            
            # If not in cache, we need the hash for saving later
            # (get_cached_result calculates it but doesn't return it if miss)
            # So let's calculate it once.
            file_hash = cache_manager.get_file_hash(image_path)
    except Exception as e:
        logger.warning(f"Cache check failed: {e}")
        file_hash = None

    # 2. Extract
    try:
        start_time = time.time()
        extractor = get_worker_extractor()
        result = extractor.process_page(image_path, page_num)
        
        # Add processing time (Fixing TODO)
        duration = time.time() - start_time
        result['processing_time'] = duration
        
        # 3. Save to Cache
        if file_hash:
            cache_manager.set(file_hash, result)
            
        return result
    except Exception as e:
        logger.error(f"Page {page_num} processing failed: {e}")
        return {
            "page": page_num, 
            "text": "", 
            "error": str(e), 
            "confidence": 0.0,
            "processing_time": 0.0
        }
