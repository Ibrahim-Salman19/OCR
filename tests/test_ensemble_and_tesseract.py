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


def test_ensemble_keeps_primary_when_secondary_is_not_better(test_image_file):
    """Ensemble always cross-checks against the secondary engine now (see
    ensemble_engine.py's process_page docstring for why the old
    confidence-gated skip was removed -- it was proven not to correlate
    with actual accuracy), but must still end up choosing primary's
    result when the secondary engine doesn't offer a strictly better
    (higher-confidence) result and no mismatch is suspected."""
    eng = ConsensusEnsembleEngine(high_confidence_threshold=0.80)
    mock_primary_res = {
        "page": 1,
        "text": "High Confidence Text",
        "confidence": 0.95,
        "processing_time": 0.1,
        "details": [],
    }
    mock_sec_res = {
        "page": 1,
        "text": "high confidence text",
        "confidence": 0.90,
        "processing_time": 0.2,
        "details": [],
    }
    mock_sec_engine = MagicMock()
    mock_sec_engine.process_page.return_value = mock_sec_res
    eng._secondary = mock_sec_engine

    with patch.object(eng._primary, "process_page", return_value=mock_primary_res):
        res = eng.process_page(test_image_file, 1)
        assert res["confidence"] == 0.95
        assert "rapidocr_selected" in res["engine"]
        assert mock_sec_engine.process_page.called, (
            "BUG: the secondary engine must always be cross-checked, not skipped "
            "based on primary's self-reported confidence."
        )


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


def test_ensemble_suspected_script_mismatch_bypasses_high_confidence_shortcut(test_image_file):
    """A primary result flagged with `script_fallback_error` (RapidOCR
    suspected a script mismatch but couldn't resolve it, e.g. the Arabic
    model was unreachable) must not short-circuit past the secondary
    engine just because its raw confidence looks high -- that's exactly
    the reported bug's shape: only a page number recognized, at high
    confidence, while the rest of the page's text silently vanished."""
    eng = ConsensusEnsembleEngine(high_confidence_threshold=0.80)
    mock_primary_res = {
        "page": 1,
        "text": "12",
        "confidence": 0.99,
        "processing_time": 0.1,
        "details": [],
        "script_fallback_error": "Arabic-script model unavailable (no network)",
    }
    mock_sec_res = {
        "page": 1,
        "text": "Recovered Urdu text",
        "confidence": 0.88,
        "processing_time": 0.3,
        "details": [],
    }

    mock_sec_engine = MagicMock()
    mock_sec_engine.process_page.return_value = mock_sec_res
    eng._secondary = mock_sec_engine

    with patch.object(eng._primary, "process_page", return_value=mock_primary_res):
        res = eng.process_page(test_image_file, 1)

    assert mock_sec_engine.process_page.called, (
        "BUG: high primary confidence bypassed the secondary engine even "
        "though a script mismatch was suspected and unresolved."
    )
    assert res["text"] == "Recovered Urdu text"
    assert "easyocr_selected" in res["engine"]


def test_ensemble_flags_substantial_disagreement_even_with_normal_confidence(test_image_file):
    """Two independently-architected engines producing substantially
    different text for the same page is itself a reliability signal --
    proven necessary because RapidOCR's own confidence does not
    correlate with actual accuracy (measured: 0.91-0.96 confidence
    regardless of whether real CER was 4% or 67%, see the module
    docstring in ensemble_engine.py). Both engines here report
    unremarkable, similar-looking confidence scores; the disagreement
    must still surface."""
    eng = ConsensusEnsembleEngine(high_confidence_threshold=0.80)
    mock_primary_res = {
        "page": 1,
        "text": "The quick brown fox jumps over the lazy dog",
        "confidence": 0.93,
        "processing_time": 0.1,
        "details": [],
    }
    mock_sec_res = {
        "page": 1,
        "text": "Xyzzy plugh wobble frobnicate qux",
        "confidence": 0.91,
        "processing_time": 0.2,
        "details": [],
    }
    mock_sec_engine = MagicMock()
    mock_sec_engine.process_page.return_value = mock_sec_res
    eng._secondary = mock_sec_engine

    with patch.object(eng._primary, "process_page", return_value=mock_primary_res):
        res = eng.process_page(test_image_file, 1)

    assert res.get("engine_disagreement") is True
    assert "engine_agreement_ratio" in res


def test_ensemble_does_not_flag_disagreement_for_near_identical_text(test_image_file):
    """Minor OCR-noise-level differences (case, whitespace) between the
    two engines must not trip the disagreement flag -- only substantial
    divergence should."""
    eng = ConsensusEnsembleEngine(high_confidence_threshold=0.80)
    mock_primary_res = {
        "page": 1,
        "text": "The quick brown fox jumps over the lazy dog.",
        "confidence": 0.93,
        "processing_time": 0.1,
        "details": [],
    }
    mock_sec_res = {
        "page": 1,
        "text": "the quick brown fox jumps over the lazy dog",
        "confidence": 0.80,
        "processing_time": 0.2,
        "details": [],
    }
    mock_sec_engine = MagicMock()
    mock_sec_engine.process_page.return_value = mock_sec_res
    eng._secondary = mock_sec_engine

    with patch.object(eng._primary, "process_page", return_value=mock_primary_res):
        res = eng.process_page(test_image_file, 1)

    assert "engine_disagreement" not in res
