"""
blast_ocr.core.engines.rapidocr_engine

RapidOCR (ONNXRuntime) Engine Adapter implementation.
Fast CPU OCR using PaddleOCR-compatible ONNX models via rapidocr_onnxruntime.
"""

from typing import Dict, Any, Optional
import time
import logging
import cv2

from blast_ocr.core.engines.base import BaseOCREngine
from blast_ocr.core.layout import LayoutEngine
from blast_ocr.core.page_signal import estimate_glyph_height

logger = logging.getLogger(__name__)


class RapidOCREngine(BaseOCREngine):
    """Adapter for RapidOCR ONNX engine."""

    def __init__(self):
        self._engine = None

    def _init_engine(self):
        if self._engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._engine = RapidOCR()
            except Exception as e:
                logger.error(f"Failed to initialize RapidOCR engine: {e}")
                raise RuntimeError(f"RapidOCR initialization failed: {e}") from e

    @property
    def engine_name(self) -> str:
        return "rapidocr"

    def metadata(self) -> Dict[str, Any]:
        return {
            "engine": self.engine_name,
            "backend": "onnxruntime",
            "device": "cpu",
            "model_detection": "ch_PP-OCRv3_det",
            "model_recognition": "ch_PP-OCRv3_rec",
        }

    def process_page(
        self,
        image_path: str,
        page_number: int,
        glyph_height: Optional[float] = None,
    ) -> Dict[str, Any]:
        self._init_engine()

        start_time = time.monotonic()
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not load image at {image_path}")

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

        eff_glyph_height = glyph_height or estimate_glyph_height(gray) or 24.0

        # RapidOCR returns tuple (result, elapse)
        # result shape: [[bbox, text, score], ...]
        raw_output, _ = self._engine(img)

        raw_detections = []
        text_parts = []
        confidences = []
        char_counts = []
        formatted_details = []

        if raw_output:
            for item in raw_output:
                if not item or len(item) < 3:
                    continue
                bbox_points, text, conf = item[0], str(item[1]).strip(), float(item[2])
                if not text:
                    continue

                raw_detections.append({
                    "text": text,
                    "confidence": conf,
                    "bbox": bbox_points,
                })
                text_parts.append(text)
                confidences.append(conf)
                char_counts.append(len(text))

                # Flat bbox points [x1,y1, x2,y1, x2,y2, x1,y2]
                flat_bbox = [int(c) for pt in bbox_points for c in pt] if isinstance(bbox_points, (list, tuple)) else []
                formatted_details.append({
                    "text": text,
                    "conf": conf,
                    "bbox": flat_bbox,
                })

        # Process layout
        layout_engine = LayoutEngine()
        layout_page = layout_engine.process_page_detections(
            raw_detections=raw_detections,
            page_num=page_number,
            width=w,
            height=h,
            glyph_height=eff_glyph_height,
        )

        extracted_text = layout_page.text if layout_page.text.strip() else " ".join(text_parts)

        total_chars = sum(char_counts)
        if total_chars > 0:
            avg_confidence = sum(c * n for c, n in zip(confidences, char_counts)) / total_chars
        else:
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
