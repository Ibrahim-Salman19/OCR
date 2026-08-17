"""
blast_ocr.core.engines.easyocr_engine

EasyOCR Engine Adapter implementation wrapping RobustOCRExtractor.
"""

from typing import Dict, Any, Optional
from blast_ocr.core.engines.base import BaseOCREngine
from blast_ocr.core.extractor import RobustOCRExtractor


class EasyOCREngine(BaseOCREngine):
    """Adapter wrapping EasyOCR via RobustOCRExtractor."""

    def __init__(self, extractor: Optional[RobustOCRExtractor] = None):
        self._extractor = extractor

    @property
    def extractor(self) -> RobustOCRExtractor:
        if self._extractor is None:
            from blast_ocr.core.worker import get_worker_extractor
            self._extractor = get_worker_extractor()
        return self._extractor

    @property
    def engine_name(self) -> str:
        return "easyocr"

    def metadata(self) -> Dict[str, Any]:
        return {
            "engine": self.engine_name,
            "backend": "pytorch",
            "device": "cpu",
            "model_detection": "craft",
            "model_recognition": "resnet_crnn",
        }

    def process_page(
        self,
        image_path: str,
        page_number: int,
        glyph_height: Optional[float] = None,
    ) -> Dict[str, Any]:
        res_dict = self.extractor.process_page(image_path, page_number)
        res_dict["engine"] = self.engine_name
        return res_dict
