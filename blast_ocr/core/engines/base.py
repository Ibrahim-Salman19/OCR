"""
blast_ocr.core.engines.base

Abstract Base Class (ABC) for modular OCR Engine Adapters in B.L.A.S.T. OCR Protocol.
Provides a uniform interface returning structured extraction result dictionaries.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union, Sequence


class BaseOCREngine(ABC):
    """
    Abstract interface for pluggable OCR engines (EasyOCR, RapidOCR, PP-OCR, etc.).
    All implementations must consume standard page images and return a uniform dict:
    {
        "page": int,
        "text": str,
        "confidence": float,
        "bbox_count": int,
        "details": list,
        "page_model": dict,
        "processing_time": float,
        "engine": str,
    }
    """

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Unique identifier string for the engine (e.g. 'easyocr', 'rapidocr')."""
        pass

    @abstractmethod
    def metadata(self) -> Dict[str, Any]:
        """Return engine metadata, backend version, models, and device info."""
        pass

    def healthcheck(self) -> bool:
        """Verify engine readiness and model availability."""
        try:
            m = self.metadata()
            return bool(m.get("engine"))
        except Exception:
            return False

    def warmup(self) -> None:
        """Warm up engine weights and memory cache."""
        pass

    def close(self) -> None:
        """Dispose engine resources."""
        pass

    @abstractmethod
    def process_page(
        self,
        image_path: str,
        page_number: int,
        glyph_height: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Process a single image page and return result dictionary containing extracted
        text, confidence, details, processing time, and structured page_model.
        """
        pass

    def process_batch(
        self,
        images: Sequence[Union[str, Any]],
        page_numbers: Optional[Sequence[int]] = None,
        glyph_heights: Optional[Sequence[Optional[float]]] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """
        Batched inference interface processing multiple pages simultaneously.
        Default implementation falls back to sequential process_page calls.
        """
        import os
        import tempfile
        import numpy as np

        if page_numbers is None:
            page_numbers = list(range(1, len(images) + 1))
        if glyph_heights is None:
            glyph_heights = [None] * len(images)

        results: List[Dict[str, Any]] = []
        for img, page_num, gh in zip(images, page_numbers, glyph_heights):
            if isinstance(img, str):
                res = self.process_page(img, page_num, gh)
            elif isinstance(img, np.ndarray):
                import cv2

                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp_path = tmp.name
                try:
                    cv2.imwrite(tmp_path, img)
                    res = self.process_page(tmp_path, page_num, gh)
                finally:
                    if os.path.exists(tmp_path):
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
            else:
                raise TypeError(f"Unsupported image type: {type(img)}")
            results.append(res)
        return results

