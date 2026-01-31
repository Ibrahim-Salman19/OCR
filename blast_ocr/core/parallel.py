from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from tqdm import tqdm
import multiprocessing as mp
from typing import List, Dict, Callable
import logging
from blast_ocr.config import config

logger = logging.getLogger(__name__)

class ParallelOCRProcessor:
    def __init__(self, max_workers=None):
        self.max_workers = max_workers or config.max_workers
    
    def process_batch_threaded(self, page_paths: List[str], process_func: Callable) -> List[Dict]:
        """Thread-based parallelism (I/O-bound tasks)"""
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_page = {
                executor.submit(process_func, path, i+1): (path, i+1)
                for i, path in enumerate(page_paths)
            }
            
            # Collect results with progress bar
            with tqdm(total=len(page_paths), desc="Processing pages") as pbar:
                for future in as_completed(future_to_page):
                    path, page_num = future_to_page[future]
                    try:
                        result = future.result(timeout=config.timeout_per_page)
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Page {page_num} ({path}) failed: {e}")
                        results.append({"page": page_num, "text": "", "error": str(e), "confidence": 0.0})
                    finally:
                        pbar.update(1)
        
        return sorted(results, key=lambda x: x['page'])
    
    # Note: Process-based parallelism requires picklable objects. 
    # EasyOCR reader is not easily picklable. 
    # For now, we rely on threading which works well for I/O and some numpy ops released by GIL.
