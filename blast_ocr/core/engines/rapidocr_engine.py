"""
blast_ocr.core.engines.rapidocr_engine

RapidOCR (ONNXRuntime) Engine Adapter implementation.
Fast CPU OCR using PaddleOCR-compatible ONNX models via rapidocr_onnxruntime.
"""

from typing import Dict, Any, Optional
import time
import logging
import cv2

from blast_ocr.config import config
from blast_ocr.core.engines.base import BaseOCREngine
from blast_ocr.core.engines.script_models import (
    RTL_SCRIPT_LANGUAGES,
    ArabicModelUnavailableError,
    contains_rtl_script,
    ensure_arabic_model,
)
from blast_ocr.core.layout import LayoutEngine
from blast_ocr.core.page_signal import estimate_glyph_height

logger = logging.getLogger(__name__)

# Languages the bundled default model (ch_PP-OCRv4, Chinese+English trained)
# can actually recognize, plus the RTL scripts handled via the Arabic-script
# model swap below. Anything outside this set silently degrades to
# empty/garbage output for that text -- callers should prefer the `easyocr`
# engine (which loads a language pack per request) for other scripts.
_SUPPORTED_LANGUAGES = {"en", "zh", "ch_sim", "ch_tra"} | RTL_SCRIPT_LANGUAGES


class RapidOCREngine(BaseOCREngine):
    """Adapter for RapidOCR ONNX engine."""

    def __init__(self):
        self._engine = None
        self._arabic_engine = None
        self._active_is_arabic = False

    def _wants_rtl_script(self) -> bool:
        return any(lang in RTL_SCRIPT_LANGUAGES for lang in config.ocr_languages)

    def _warn_if_unsupported_language(self) -> None:
        unsupported = [
            lang for lang in config.ocr_languages if lang not in _SUPPORTED_LANGUAGES
        ]
        if unsupported:
            logger.warning(
                "OCR language(s) %s requested but not supported by the "
                "'rapidocr' engine's models -- text in that script will come "
                "back empty or garbage. Use ocr_engine='easyocr' for this "
                "language instead.",
                unsupported,
            )

    def _init_engine(self):
        if self._engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._engine = RapidOCR()
            except Exception as e:
                logger.error(f"Failed to initialize RapidOCR engine: {e}")
                raise RuntimeError(f"RapidOCR initialization failed: {e}") from e

    def _init_arabic_engine(self):
        if self._arabic_engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                rec_model_path, rec_keys_path = ensure_arabic_model()
                self._arabic_engine = RapidOCR(
                    rec_model_path=rec_model_path, rec_keys_path=rec_keys_path
                )
            except ArabicModelUnavailableError:
                raise
            except Exception as e:
                logger.error(f"Failed to initialize Arabic-script RapidOCR engine: {e}")
                raise RuntimeError(
                    f"Arabic-script RapidOCR initialization failed: {e}"
                ) from e

    def _active_engine(self):
        self._warn_if_unsupported_language()
        if self._wants_rtl_script():
            self._init_arabic_engine()
            self._active_is_arabic = True
            return self._arabic_engine
        self._init_engine()
        self._active_is_arabic = False
        return self._engine

    @property
    def engine_name(self) -> str:
        return "rapidocr"

    def metadata(self) -> Dict[str, Any]:
        if self._active_is_arabic:
            return {
                "engine": self.engine_name,
                "backend": "onnxruntime",
                "device": "cpu",
                "model_detection": "ch_PP-OCRv4_det",
                "model_recognition": "arabic_PP-OCRv5_rec",
            }
        return {
            "engine": self.engine_name,
            "backend": "onnxruntime",
            "device": "cpu",
            "model_detection": "ch_PP-OCRv4_det",
            "model_recognition": "ch_PP-OCRv4_rec",
        }

    def process_page(
        self,
        image_path: str,
        page_number: int,
        glyph_height: Optional[float] = None,
    ) -> Dict[str, Any]:
        engine = self._active_engine()
        is_rtl = self._active_is_arabic

        start_time = time.monotonic()
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not load image at {image_path}")

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

        eff_glyph_height = glyph_height or estimate_glyph_height(gray) or 24.0

        # RapidOCR returns tuple (result, elapse)
        # result shape: [[bbox, text, score], ...]
        raw_output, _ = engine(img)

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
                if is_rtl and contains_rtl_script(text):
                    # The Arabic-script recognition model emits each line in
                    # raw left-to-right pixel/visual order (a CTC decoding
                    # artifact of the underlying CRNN, not a logical reading
                    # order) -- reversing per line restores correct RTL
                    # reading order. Confirmed empirically against a known
                    # Urdu ground-truth sample: the model's raw output only
                    # matches the source text after this reversal. Guarded by
                    # contains_rtl_script() because the same page can carry
                    # pure-Latin/digit detections (page numbers, footnote
                    # markers) that must NOT be reversed.
                    text = text[::-1]

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
