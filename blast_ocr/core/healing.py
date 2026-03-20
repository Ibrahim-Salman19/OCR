import time
from functools import wraps
import logging
import asyncio

logger = logging.getLogger(__name__)

class SelfHealingOCR:
    """Automatic retry and fallback logic"""
    
    def __init__(self, max_retries=3, backoff_factor=2):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
    
    def retry_with_backoff(self, func):
        """Decorator for exponential backoff retry"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(self.max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Check for fatal errors (by name to avoid circular imports)
                    # FIX(phase2): BUG-02 - Added 'OCREngineError' to prevent retries on memory errors
                    error_type = type(e).__name__
                    if error_type in ['ImageLoadError', 'PageExtractionError', 'FileNotFoundError', 'OCREngineError']:
                        logger.error(f"Fatal error in {func.__name__}: {e}. Not retrying.")
                        raise

                    wait_time = self.backoff_factor ** attempt
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(wait_time)
                    else:
                        logger.error(f"All retry attempts exhausted for {func.__name__}")
                        raise
        return wrapper

    async def retry_with_backoff_async(self, func):
        """Decorator for exponential backoff retry (async ver)"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(self.max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    wait_time = self.backoff_factor ** attempt
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"All retry attempts exhausted for {func.__name__}")
                        raise
        return wrapper
    
    def fallback_chain(self, primary_func, fallback_funcs):
        """Try primary method, fall back to alternatives"""
        def execute(*args, **kwargs):
            try:
                return primary_func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Primary method failed: {e}. Trying fallbacks...")
                for i, fallback in enumerate(fallback_funcs, 1):
                    try:
                        logger.info(f"Attempting fallback {i}/{len(fallback_funcs)}")
                        return fallback(*args, **kwargs)
                    except Exception as fb_error:
                        logger.warning(f"Fallback {i} failed: {fb_error}")
                        continue
                raise Exception("All processing methods failed")
        return execute

# Global healer instance
from blast_ocr.config import config
healer = SelfHealingOCR(
    max_retries=config.max_retries, 
    backoff_factor=config.retry_backoff
)
