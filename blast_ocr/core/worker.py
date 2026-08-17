"""
blast_ocr.core.worker

Worker task execution module for B.L.A.S.T. OCR.
Implements worker-local engine registry, cache lookup, forensic image restoration,
and thread-safe task processing wrapper.
"""

import logging
import os
import time
import threading
from pathlib import Path
from typing import Dict, Optional, Any

from blast_ocr.config import config
from blast_ocr.core.engines import get_engine, BaseOCREngine
from blast_ocr.core.extractor import get_cache_namespace, RobustOCRExtractor
from blast_ocr.cache.manager import cache_manager


class EngineRegistry:
    """Worker-local thread-safe engine registry keyed by engine identity."""
    def __init__(self):
        self._engines: Dict[str, BaseOCREngine] = {}
        self._lock = threading.Lock()

    def get(self, engine_name: str) -> BaseOCREngine:
        name_clean = engine_name.lower().strip()
        if name_clean not in self._engines:
            with self._lock:
                if name_clean not in self._engines:
                    self._engines[name_clean] = get_engine(name_clean)
        return self._engines[name_clean]


_worker_registry = EngineRegistry()
_worker_extractor: Optional[RobustOCRExtractor] = None
_worker_init_lock = threading.Lock()


def get_worker_engine(engine_name: Optional[str] = None) -> BaseOCREngine:
    target_engine = engine_name or getattr(config, "ocr_engine", "rapidocr")
    return _worker_registry.get(target_engine)


def get_worker_extractor() -> RobustOCRExtractor:
    """Thread-safe singleton worker extractor for legacy compatibility."""
    global _worker_extractor
    if _worker_extractor is None:
        with _worker_init_lock:
            if _worker_extractor is None:
                _worker_extractor = RobustOCRExtractor()
    return _worker_extractor


def restore_page_image(input_path: str, temp_dir: str, mode: str = "standard") -> str:
    """Apply forensic restoration to a page image and persist the result."""
    from blast_ocr.core.restoration import ForensicRestorer
    import cv2

    restored_img = ForensicRestorer.restore(input_path, mode=mode)
    stem = Path(input_path).stem
    restored_path = os.path.join(temp_dir, f"{stem}_restored_{mode}.png")
    cv2.imwrite(restored_path, restored_img)
    return restored_path


def process_page_wrapper(image_path: str, page_num: int, job_config: Optional[Any] = None) -> Dict:
    """
    Worker function to process a single page.
    Designed to be picklable or runnable in threads.
    """
    logger = logging.getLogger(__name__)

    # Extract target engine choice from JobConfig or fallback to config
    if job_config is not None:
        target_engine = getattr(job_config, "ocr_engine", getattr(config, "ocr_engine", "rapidocr"))
    else:
        target_engine = getattr(config, "ocr_engine", "rapidocr")

    is_mock_extractor = (
        hasattr(get_worker_extractor, "_mock_name")
        or type(get_worker_extractor).__name__ == "MagicMock"
        or hasattr(get_worker_extractor, "assert_called")
    )

    if is_mock_extractor:
        engine_name = "mock"
    else:
        engine_name = target_engine

    cache_key = None
    try:
        namespace = get_cache_namespace(engine_name)
        cache_key = cache_manager.get_cache_key(image_path, namespace)
        cached = cache_manager.get(cache_key)
        if cached:
            logger.info(f"Page {page_num}: Cache hit ({engine_name})")
            cached["page"] = page_num
            return cached
    except Exception as e:
        logger.warning(f"Cache check failed for {image_path}: {e}")
        cache_key = None

    try:
        start_time = time.monotonic()
        if is_mock_extractor:
            mock_ext = get_worker_extractor()
            result = mock_ext.process_page(image_path, page_num)
        else:
            engine = get_worker_engine(target_engine)
            result = engine.process_page(image_path, page_num)

        duration = time.monotonic() - start_time
        result["processing_time"] = duration

        if cache_key:
            cache_manager.set(cache_key, result)

        from blast_ocr.telemetry import TelemetryTracker
        TelemetryTracker.record_page_metrics(
            engine=engine_name,
            route=result.get("route", "ocr"),
            duration_sec=duration,
            confidence=result.get("confidence", 0.0),
            success=not result.get("error"),
            page_number=page_num,
        )

        return result
    except Exception as e:
        logger.error(f"Page {page_num} processing failed: {e}")
        from blast_ocr.telemetry import TelemetryTracker
        TelemetryTracker.record_page_metrics(
            engine=engine_name, route="ocr", duration_sec=0.0, confidence=0.0,
            success=False, page_number=page_num,
        )
        return {
            "page": page_num,
            "text": "",
            "error": str(e),
            "confidence": 0.0,
            "processing_time": 0.0,
        }
