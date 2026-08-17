"""
tests/test_ensemble_and_tesseract.py

Unit tests for ConsensusEnsembleEngine and TesseractEngine adapters.
"""

from unittest.mock import MagicMock, patch
import numpy as np
import cv2
import pytest

from blast_ocr.core.engines import get_engine, TesseractEngine, ConsensusEnsembleEngine


@pytest.fixture
def test_image_file(tmp_path):
    p = tmp_path / "test_engine.png"
    img = np.full((100, 300, 3), 255, dtype=np.uint8)
    cv2.putText(img, "Engine Test Text", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.imwrite(str(p), img)
    return str(p)


def test_tesseract_engine_factory():
    eng = get_engine("tesseract")
    assert isinstance(eng, TesseractEngine)
    assert eng.engine_name == "tesseract"
    meta = eng.metadata()
    assert meta["engine"] == "tesseract"


def test_ensemble_engine_factory():
    eng = get_engine("ensemble")
    assert isinstance(eng, ConsensusEnsembleEngine)
    assert eng.engine_name == "ensemble"
    meta = eng.metadata()
    assert meta["primary"] == "rapidocr"
    assert meta["secondary"] == "easyocr"


def test_ensemble_high_confidence_uses_primary(test_image_file):
    eng = ConsensusEnsembleEngine(high_confidence_threshold=0.80)
    mock_primary_res = {
        "page": 1,
        "text": "High Confidence Text",
        "confidence": 0.95,
        "processing_time": 0.1,
        "details": [],
    }

    with patch.object(eng._primary, "process_page", return_value=mock_primary_res):
        res = eng.process_page(test_image_file, 1)
        assert res["confidence"] == 0.95
        assert "rapidocr_pass" in res["engine"]


def test_ensemble_low_confidence_invokes_secondary(test_image_file):
    eng = ConsensusEnsembleEngine(high_confidence_threshold=0.90)
    mock_primary_res = {
        "page": 1,
        "text": "Low Conf Text",
        "confidence": 0.60,
        "processing_time": 0.1,
        "details": [],
    }
    mock_sec_res = {
        "page": 1,
        "text": "High Conf Recovered Text",
        "confidence": 0.92,
        "processing_time": 0.3,
        "details": [],
    }

    mock_sec_engine = MagicMock()
    mock_sec_engine.process_page.return_value = mock_sec_res
    eng._secondary = mock_sec_engine

    with patch.object(eng._primary, "process_page", return_value=mock_primary_res):
        res = eng.process_page(test_image_file, 1)
        assert res["confidence"] == 0.92
        assert "easyocr_selected" in res["engine"]
