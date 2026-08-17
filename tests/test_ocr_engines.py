"""
Unit tests for modular OCR Engine Adapters (Phase 3).
"""

import pytest
import numpy as np
import cv2

from blast_ocr.core.engines import get_engine, EasyOCREngine, RapidOCREngine


def test_engine_factory():
    easy_engine = get_engine("easyocr")
    assert isinstance(easy_engine, EasyOCREngine)
    assert easy_engine.engine_name == "easyocr"

    rapid_engine = get_engine("rapidocr")
    assert isinstance(rapid_engine, RapidOCREngine)
    assert rapid_engine.engine_name == "rapidocr"

    with pytest.raises(ValueError, match="Unknown OCR engine"):
        get_engine("unsupported_engine_xyz")


def test_easyocr_engine_interface(tmp_path):
    img = np.full((100, 300, 3), 255, dtype=np.uint8)
    cv2.putText(img, "TEST OK", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    img_path = str(tmp_path / "test_easy.png")
    cv2.imwrite(img_path, img)

    engine = EasyOCREngine()
    res_dict = engine.process_page(img_path, page_number=1)

    assert isinstance(res_dict, dict)
    assert res_dict["page"] == 1
    assert "text" in res_dict
    assert "confidence" in res_dict
    assert "details" in res_dict
    assert res_dict.get("engine") == "easyocr"


def test_rapidocr_engine_interface(tmp_path):
    img = np.full((100, 300, 3), 255, dtype=np.uint8)
    cv2.putText(img, "RAPID TEST", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    img_path = str(tmp_path / "test_rapid.png")
    cv2.imwrite(img_path, img)

    engine = RapidOCREngine()
    res_dict = engine.process_page(img_path, page_number=1)

    assert isinstance(res_dict, dict)
    assert res_dict["page"] == 1
    assert "text" in res_dict
    assert "confidence" in res_dict
    assert "details" in res_dict
    assert res_dict.get("engine") == "rapidocr"
