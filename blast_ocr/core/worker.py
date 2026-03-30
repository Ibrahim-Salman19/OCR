import logging
import time
from typing import Dict, Optional

from blast_ocr.core.extractor import RobustOCRExtractor
from blast_ocr.cache.manager import cache_manager

# Global extractor instance for worker threads
# We lazily initialize this to avoid creating it in the main thread if not needed,
# though in threaded mode memory is shared.
_worker_extractor: Optional[RobustOCRExtractor] = None

import threading
_worker_init_lock = threading.Lock()

def get_worker_extractor() -> RobustOCRExtractor:
    global _worker_extractor
    if _worker_extractor is None:
        # BUG-WORKER-RACE-01 Fix: Thread-safe singleton
        with _worker_init_lock:
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
    file_hash = None
    try:
        # get_cached_result hashes internally and returns result or None
        cached = cache_manager.get_cached_result(image_path)
        if cached:
            logger.info(f"Page {page_num}: Cache hit")
            cached['page'] = page_num
            return cached
            
        # miss: we need the hash for saving later
        file_hash = cache_manager.get_file_hash(image_path)
    except Exception as e:
        logger.warning(f"Cache check failed for {image_path}: {e}")
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
