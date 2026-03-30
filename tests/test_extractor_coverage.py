"""
Sprint 7: Extractor deep coverage tests.
Covers remaining edge cases in blast_ocr/core/extractor.py.
"""

import os
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from importlib import reload

from blast_ocr.core.exceptions import OCREngineError, PageExtractionError


def test_extractor_linux_model_dir_init():
    """Covers lines 17-19 in extractor.py (Linux model directory setup at import)"""
    with patch("sys.platform", "linux"):
        import blast_ocr.core.extractor as ext

        reload(ext)
        assert os.environ.get("EASYOCR_MODULE_PATH") == "/tmp/.EasyOCR"

    # Reload back to normal to not break other things
    reload(ext)


def test_extractor_init_engine_failure():
    """Covers lines 60-62 in extractor.py (Init failure)"""
    from blast_ocr.core.extractor import RobustOCRExtractor

    with patch("easyocr.Reader", side_effect=Exception("Mock Init Fail")):
        with patch("time.sleep"):  # skip backoff sleep
            with pytest.raises(OCREngineError):
                RobustOCRExtractor()


def test_extractor_deskew_angle_less_than_minus_45():
    """Covers line 123-124 angle calculation path."""
    from blast_ocr.core.extractor import RobustOCRExtractor

    e = RobustOCRExtractor.__new__(RobustOCRExtractor)

    # We must mock minAreaRect to return a specific angle
    with patch(
        "blast_ocr.core.extractor.cv2.minAreaRect", return_value=(None, None, -50.0)
    ):
        with patch("blast_ocr.core.extractor.config") as mock_cfg:
            mock_cfg.auto_deskew = True
            mock_cfg.denoise_level = 0
            mock_cfg.contrast_boost = 1.0

            img = np.zeros((100, 100), dtype=np.uint8)
            # Add some white so coords has content
            img[50:60, 50:60] = 255

            out = e.preprocess_image(img)
            assert out is not None


def test_process_page_cache_clearing_exception(tmp_path):
    """Covers lines 215-217 (cache clearing skipping on OS/Import error)"""
    from blast_ocr.core.extractor import RobustOCRExtractor

    e = RobustOCRExtractor.__new__(RobustOCRExtractor)
    e.lock = MagicMock()
    e.reader = MagicMock()
    e.reader.readtext.return_value = []

    img = np.zeros((100, 100, 3), dtype=np.uint8)
    p = str(tmp_path / "test.png")
    import cv2

    cv2.imwrite(p, img)

    # Let's mock builtins.__import__ specifically for 'torch' to throw OSError
    orig_import = __import__

    def mock_import(name, *args):
        if name == "torch":
            raise OSError("DLL load failed")
        return orig_import(name, *args)

    with patch("builtins.__import__", side_effect=mock_import):
        res = e.process_page(p, 1)
        assert res["warning"] == "no_text_detected"


def test_process_page_unexpected_exception(tmp_path):
    """Covers lines 265-267."""
    from blast_ocr.core.extractor import RobustOCRExtractor

    e = RobustOCRExtractor.__new__(RobustOCRExtractor)
    e.lock = MagicMock()

    # Raise a non-OCR, non-ImageLoad error. A KeyError shouldn't typically happen
    # but we can force it.
    with patch("blast_ocr.core.extractor.cv2.imread", side_effect=KeyError("Random")):
        with pytest.raises(PageExtractionError):
            e.process_page("dummy.png", 1)


def test_sanitize_xml_control_char():
    """Covers re.sub in sanitize_for_xml for sure."""
    from blast_ocr.core.extractor import sanitize_for_xml

    # A string with control chars
    s = "hello\x01\x1fworld"
    assert sanitize_for_xml(s) == "helloworld"
