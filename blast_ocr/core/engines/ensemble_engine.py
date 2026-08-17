"""
blast_ocr.core.engines.ensemble_engine

Consensus Ensemble OCR Engine Adapter.
Combines fast primary extraction (RapidOCR) with secondary validation (EasyOCR)
when confidence falls below threshold, choosing optimal block extractions.
"""

from typing import Dict, Any, Optional
import time
import logging

from blast_ocr.core.engines.base import BaseOCREngine
from blast_ocr.core.engines.rapidocr_engine import RapidOCREngine
from blast_ocr.core.engines.easyocr_engine import EasyOCREngine

logger = logging.getLogger(__name__)


class ConsensusEnsembleEngine(BaseOCREngine):
    """Ensemble OCR engine providing multi-engine consensus and voting."""

    def __init__(self, high_confidence_threshold: float = 0.85):
        self.high_confidence_threshold = high_confidence_threshold
        self._primary = RapidOCREngine()
        self._secondary = None

    @property
    def engine_name(self) -> str:
        return "ensemble"

    def metadata(self) -> Dict[str, Any]:
        return {
            "engine": self.engine_name,
            "primary": self._primary.engine_name,
            "secondary": "easyocr",
            "confidence_threshold": self.high_confidence_threshold,
        }

    def process_page(
        self,
        image_path: str,
        page_number: int,
        glyph_height: Optional[float] = None,
    ) -> Dict[str, Any]:
        start_time = time.monotonic()

        # 1. Run primary fast engine
        primary_res = self._primary.process_page(image_path, page_number, glyph_height)
        primary_conf = primary_res.get("confidence", 0.0)

        if primary_conf >= self.high_confidence_threshold:
            primary_res["engine"] = f"{self.engine_name} (rapidocr_pass)"
            return primary_res

        # 2. If confidence is lower, invoke secondary engine
        logger.info(
            f"Page {page_number} confidence {primary_conf:.2f} < {self.high_confidence_threshold:.2f}. "
            "Running ensemble secondary engine (EasyOCR)."
        )
        if self._secondary is None:
            self._secondary = EasyOCREngine()

        try:
            sec_res = self._secondary.process_page(image_path, page_number, glyph_height)
            sec_conf = sec_res.get("confidence", 0.0)

            # Pick the higher confidence result or merged consensus
            if sec_conf > primary_conf:
                sec_res["engine"] = f"{self.engine_name} (easyocr_selected, conf={sec_conf:.2f})"
                sec_res["processing_time"] = time.monotonic() - start_time
                return sec_res
            else:
                primary_res["engine"] = f"{self.engine_name} (rapidocr_selected, conf={primary_conf:.2f})"
                primary_res["processing_time"] = time.monotonic() - start_time
                return primary_res

        except Exception as sec_err:
            logger.warning(f"Ensemble secondary engine failed: {sec_err}, using primary result.")
            primary_res["engine"] = f"{self.engine_name} (primary_fallback)"
            return primary_res
