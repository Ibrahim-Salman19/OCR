from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from typing import List, Dict, Callable
import logging
from blast_ocr.config import config

logger = logging.getLogger(__name__)


class ParallelOCRProcessor:
    def __init__(self, max_workers=None):
        # FIX(phase2): CRITICAL - Limit workers to prevent memory exhaustion
        # EasyOCR can use 1GB+ per page. With 8 workers, that's 8GB+ RAM.
        # Limiting to 2 workers provides parallelism while staying within memory limits.
        # Note: The global OCR lock serializes OCR anyway, so more workers don't help much.
        if max_workers is None:
            # Use at most 2 workers to prevent OOM
            self.max_workers = min(config.max_workers, 2)
        else:
            self.max_workers = min(max_workers, 2)

    def process_batch_threaded(
        self,
        page_paths: List[str],
        process_func: Callable,
        progress_callback: Callable = None,
    ) -> List[Dict]:
        """
        Thread-based parallelism for page processing.

        PERF(phase3): Analysis of the parallelism situation:
        - The global OCR lock serializes all EasyOCR calls
        - However, preprocessing (cv2 ops) releases the GIL
        - So threads DO provide benefit for overlapping preprocessing with OCR
        - Thread A can preprocess page N+1 while Thread B runs OCR on page N

        Future optimization: Separate preprocessing and OCR into distinct thread pools
        with a queue between them for true pipeline parallelism.
        """
        results = []
        total = len(page_paths)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_page = {
                executor.submit(process_func, path, i + 1): (path, i + 1)
                for i, path in enumerate(page_paths)
            }

            # Collect results with progress bar
            completed_count = 0
            with tqdm(total=total, desc="Processing pages") as pbar:
                for future in as_completed(future_to_page):
                    path, page_num = future_to_page[future]
                    try:
                        # BUG-THREAD-LEAK-01 Fix: Remove timeout from future.result() to prevent thread pool leaks
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Page {page_num} ({path}) failed: {e}")
                        results.append(
                            {
                                "page": page_num,
                                "text": "",
                                "error": str(e),
                                "confidence": 0.0,
                            }
                        )
                    finally:
                        pbar.update(1)
                        completed_count += 1
                        if progress_callback:
                            try:
                                progress_callback(completed_count, total)
                            except Exception as cb_err:
                                # FIX(phase2): BUG-08 - Log instead of silently swallowing
                                logger.debug(f"Progress callback error: {cb_err}")

        return sorted(results, key=lambda x: x["page"])

    # Note: Process-based parallelism requires picklable objects.
    # EasyOCR reader is not easily picklable.
    # For now, we rely on threading which works well for I/O and some numpy ops released by GIL.
