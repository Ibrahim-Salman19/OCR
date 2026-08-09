import time
from functools import wraps
import logging
import asyncio
from typing import Callable, Any, List, Type

from blast_ocr.core.exceptions import (
    BLASTOCRException,
    ImageLoadError,
    PageExtractionError,
    OCREngineError,
)

logger = logging.getLogger(__name__)

FATAL_ERRORS: tuple[Type[BaseException], ...] = (
    ImageLoadError,
    PageExtractionError,
    FileNotFoundError,
    OCREngineError,
    BLASTOCRException,
)


def _is_fatal_error(e: Exception) -> bool:
    """Polymorphic check to determine if an exception is fatal and should not be retried."""
    if isinstance(e, FATAL_ERRORS):
        return True
    # Fallback string check for backwards compatibility with dynamic exceptions
    return type(e).__name__ in [
        "ImageLoadError",
        "PageExtractionError",
        "FileNotFoundError",
        "OCREngineError",
        "BLASTOCRException",
    ]


class SelfHealingOCR:
    """Automatic retry and fallback logic with exponential backoff and fatal error detection."""

    def __init__(self, max_retries: int = 3, backoff_factor: float = 2.0) -> None:
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def retry_with_backoff(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator for synchronous exponential backoff retry."""

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(self.max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if _is_fatal_error(e):
                        logger.error(
                            f"Fatal error in {func.__name__}: {e}. Not retrying."
                        )
                        raise

                    wait_time = self.backoff_factor**attempt
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"All retry attempts exhausted for {func.__name__}"
                        )
                        raise

        return wrapper

    def retry_with_backoff_async(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator for asynchronous exponential backoff retry."""

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(self.max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if _is_fatal_error(e):
                        logger.error(
                            f"Fatal error in {func.__name__}: {e}. Not retrying."
                        )
                        raise

                    wait_time = self.backoff_factor**attempt
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            f"All retry attempts exhausted for {func.__name__}"
                        )
                        raise

        return async_wrapper

    def fallback_chain(
        self, primary_func: Callable[..., Any], fallback_funcs: List[Callable[..., Any]]
    ) -> Callable[..., Any]:
        """Try primary method, fall back to alternatives."""

        def execute(*args: Any, **kwargs: Any) -> Any:
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
    max_retries=config.max_retries, backoff_factor=config.retry_backoff
)
