"""
blast_ocr.core.engines package

Provides OCR engine adapters and factory lookup functions.
"""

from typing import Dict, Type
from blast_ocr.core.engines.base import BaseOCREngine
from blast_ocr.core.engines.easyocr_engine import EasyOCREngine
from blast_ocr.core.engines.rapidocr_engine import RapidOCREngine
from blast_ocr.core.engines.batched_rapidocr import BatchedRapidOCREngine
from blast_ocr.core.engines.tesseract_engine import TesseractEngine
from blast_ocr.core.engines.ensemble_engine import ConsensusEnsembleEngine

_ENGINE_REGISTRY: Dict[str, Type[BaseOCREngine]] = {
    "easyocr": EasyOCREngine,
    "rapidocr": RapidOCREngine,
    "batched_rapidocr": BatchedRapidOCREngine,
    "tesseract": TesseractEngine,
    "ensemble": ConsensusEnsembleEngine,
}


def get_engine(engine_name: str = "easyocr") -> BaseOCREngine:
    """
    Factory function retrieving an initialized OCR Engine instance by name.
    
    Args:
        engine_name: 'easyocr', 'rapidocr', 'batched_rapidocr', 'tesseract', or 'ensemble'.
        
    Returns:
        Instance of BaseOCREngine subclass.
    """
    name_clean = engine_name.lower().strip()
    if name_clean not in _ENGINE_REGISTRY:
        raise ValueError(
            f"Unknown OCR engine '{engine_name}'. Available engines: {list(_ENGINE_REGISTRY.keys())}"
        )
    return _ENGINE_REGISTRY[name_clean]()


__all__ = [
    "BaseOCREngine",
    "EasyOCREngine",
    "RapidOCREngine",
    "BatchedRapidOCREngine",
    "TesseractEngine",
    "ConsensusEnsembleEngine",
    "get_engine",
]

