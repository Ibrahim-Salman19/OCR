"""
blast_ocr.core.engines.tesseract_engine

Tesseract OCR Engine Adapter implementation.
Integrates pytesseract when installed on the host system, providing
standard hOCR/image_to_data bounding box parsing into Document Models.
"""

from typing import Dict, Any, List, Optional
import time
import logging
import cv2

from blast_ocr.core.engines.base import BaseOCREngine
from blast_ocr.core.layout import LayoutEngine
from blast_ocr.core.page_signal import estimate_glyph_height

logger = logging.getLogger(__name__)


class TesseractEngine(BaseOCREngine):
    """Adapter for Tesseract OCR via pytesseract."""

    def __init__(self):
        self._pytesseract = None
        self._available = None

    def _init_engine(self):
        if self._available is None:
            try:
                import pytesseract
                # Check version
                _ = pytesseract.get_tesseract_version()
                self._pytesseract = pytesseract
                self._available = True
            except Exception as e:
                logger.warning(f"Tesseract binary or pytesseract library unavailable: {e}")
                self._available = False

    @property
    def engine_name(self) -> str:
        return "tesseract"

    def metadata(self) -> Dict[str, Any]:
        self._init_engine()
        return {
            "engine": self.engine_name,
            "backend": "pytesseract",
            "available": bool(self._available),
        }

    def process_page(
        self,
        image_path: str,
        page_number: int,
        glyph_height: Optional[float] = None,
        languages: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        self._init_engine()
        if not self._available:
            # Fallback to RapidOCR if Tesseract binary is not installed
            from blast_ocr.core.engines.rapidocr_engine import RapidOCREngine
            logger.info("Tesseract unavailable on system, falling back to RapidOCR.")
            rapid = RapidOCREngine()
            res = rapid.process_page(image_path, page_number, glyph_height, languages=languages)
            res["engine"] = f"tesseract_fallback_to_{rapid.engine_name}"
            return res

        start_time = time.monotonic()
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not load image at {image_path}")

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        eff_glyph_height = glyph_height or estimate_glyph_height(gray) or 24.0

        from pytesseract import Output
        data = self._pytesseract.image_to_data(gray, output_type=Output.DICT)

        raw_detections = []
        text_parts = []
        confidences = []
        formatted_details = []

        n_boxes = len(data["text"])
        for i in range(n_boxes):
            text = str(data["text"][i]).strip()
            conf_val = float(data["conf"][i])
            if not text or conf_val < 0:
                continue

            x, y, bw, bh = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            conf = conf_val / 100.0
            bbox = [x, y, x + bw, y + bh]

            raw_detections.append({
                "text": text,
                "confidence": conf,
                "bbox": bbox,
            })
            text_parts.append(text)
            confidences.append(conf)
            formatted_details.append({
                "text": text,
                "conf": conf,
                "bbox": bbox,
            })

        layout_engine = LayoutEngine()
        layout_page = layout_engine.process_page_detections(
            raw_detections=raw_detections,
            page_num=page_number,
            width=w,
            height=h,
            glyph_height=eff_glyph_height,
        )

        extracted_text = layout_page.text if layout_page.text.strip() else " ".join(text_parts)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        elapsed = time.monotonic() - start_time

        return {
            "page": page_number,
            "text": extracted_text,
            "confidence": avg_confidence,
            "bbox_count": len(raw_detections),
            "details": formatted_details,
            "page_model": layout_page.model_dump(),
            "processing_time": elapsed,
            "engine": self.engine_name,
        }
