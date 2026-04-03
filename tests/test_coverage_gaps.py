"""
Tests specifically targeting branches that were uncovered in Phase 11.
"""

import pytest
from unittest.mock import patch


@pytest.mark.real_easyocr
def test_extractor_unsupported_language():
    from blast_ocr.core.extractor import RobustOCRExtractor
    from blast_ocr.config import OCRConfig
    import tempfile
    import cv2
    import numpy as np

    config = OCRConfig(ocr_languages=["xyz"])
    with patch("easyocr.Reader", side_effect=Exception("invalid language")):
        with pytest.raises(Exception):
            extractor = RobustOCRExtractor()
            path = tempfile.mktemp(suffix=".png")
            cv2.imwrite(path, np.zeros((10, 10, 3), dtype=np.uint8))
            extractor.process_page(path, 1)
