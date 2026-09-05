"""
tests/test_tesseract_engine_complete.py

Unit and integration tests for blast_ocr.core.engines.tesseract_engine.
Validates engine initialization, pytesseract detection, metadata reporting,
graceful fallback to RapidOCR when tesseract binary is missing,
corrupted image error handling, and OCR bbox/confidence parsing.
"""

from unittest.mock import patch, MagicMock
from PIL import Image
import pytest

from blast_ocr.core.engines.tesseract_engine import TesseractEngine


def test_tesseract_init_unavailable():
    engine = TesseractEngine()
    with patch.dict("sys.modules", {"pytesseract": None}):
        engine._init_engine()
        assert engine._available is False
        meta = engine.metadata()
        assert meta["engine"] == "tesseract"
        assert meta["available"] is False


def test_tesseract_fallback_to_rapidocr(tmp_path):
    img_path = str(tmp_path / "page.png")
    Image.new("RGB", (100, 100), color="white").save(img_path)

    engine = TesseractEngine()
    engine._available = False

    with patch("blast_ocr.core.engines.rapidocr_engine.RapidOCREngine") as mock_rapid_cls:
        mock_rapid = MagicMock()
        mock_rapid.engine_name = "rapidocr"
        mock_rapid.process_page.return_value = {
            "page": 1,
            "text": "Fallback Text",
            "confidence": 0.95,
            "engine": "rapidocr",
        }
        mock_rapid_cls.return_value = mock_rapid

        result = engine.process_page(img_path, page_number=1)
        assert result["text"] == "Fallback Text"
        assert "tesseract_fallback_to_rapidocr" in result["engine"]


def test_tesseract_process_page_invalid_image():
    engine = TesseractEngine()
    engine._available = True
    with pytest.raises(ValueError, match="Could not load image"):
        engine.process_page("nonexistent_path_xyz.png", page_number=1)


def test_tesseract_process_page_success(tmp_path):
    img_path = str(tmp_path / "valid_page.png")
    Image.new("RGB", (200, 300), color="white").save(img_path)

    engine = TesseractEngine()
    engine._available = True

    mock_pytesseract = MagicMock()
    # Mock image_to_data dictionary
    mock_pytesseract.image_to_data.return_value = {
        "text": ["", "TESSERACT", "   ", "OCR"],
        "conf": ["-1", "95.5", "0", "88.2"],
        "left": [0, 10, 50, 100],
        "top": [0, 20, 20, 25],
        "width": [0, 80, 20, 60],
        "height": [0, 30, 10, 25],
    }
    engine._pytesseract = mock_pytesseract

    result = engine.process_page(img_path, page_number=2, glyph_height=24.0)

    assert result["page"] == 2
    assert "TESSERACT" in result["text"]
    assert result["confidence"] > 0.8
    assert result["bbox_count"] >= 1
    assert result["engine"] == "tesseract"
