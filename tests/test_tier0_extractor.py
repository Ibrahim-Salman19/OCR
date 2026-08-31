"""
Unit tests for Tier-0 Native Text Extraction and Routing Layer (Phase 5).
"""

from blast_ocr.core.tier0_extractor import Tier0Extractor
from blast_ocr.core.models import RouteDecision


def test_native_text_quality_scoring():
    # Born-digital clean text
    clean_text = "This is a born-digital document page containing clear printable text for testing Tier-0 extraction."
    score = Tier0Extractor.evaluate_native_text_quality(clean_text)
    assert score >= 0.90

    # Short snippet
    short_text = "Short"
    score_short = Tier0Extractor.evaluate_native_text_quality(short_text)
    assert score_short <= 0.3

    # Corrupted font encoding garbage
    garbage_text = "\ue001\ue002\ue003\ue004\ue005 gibberish \ufffd\ufffd\ufffd\ufffd text layer corruption"
    score_garbage = Tier0Extractor.evaluate_native_text_quality(garbage_text)
    assert score_garbage <= 0.4


def test_missing_tounicode_pua_extraction_routes_to_ocr():
    """GAP-09: a subsetted font with no embedded /ToUnicode CMap makes
    PyMuPDF/pypdfium2 emit Private Use Area (U+E000-U+F8FF) codepoints
    instead of real characters. Text this corrupted must never be routed
    PASS_NATIVE -- doing so would silently ship mojibake as if it were a
    clean extraction.
    """
    pua_dominant_text = "".join(chr(0xE000 + (i % 500)) for i in range(300))
    quality = Tier0Extractor.analyze_native_text_quality(pua_dominant_text)
    assert quality.decision != RouteDecision.PASS_NATIVE
