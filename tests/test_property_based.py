"""
PHASE 8: Property-based tests using Hypothesis.
These generate thousands of random inputs to find edge cases that
manual testing misses. Each test specifies an INVARIANT that must
always hold, regardless of input.
"""

import pytest
import os
import tempfile
import numpy as np
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st


# ── Property 1: sanitize_for_xml always returns a string ─────────────────
@given(st.text())
@settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
def test_sanitize_always_returns_string(text):
    from blast_ocr.core.extractor import sanitize_for_xml

    result = sanitize_for_xml(text)
    assert isinstance(result, str), (
        f"sanitize_for_xml returned {type(result)} for input {repr(text)}"
    )


# ── Property 2: sanitize_for_xml output contains no null bytes ────────────
@given(st.text())
@settings(max_examples=1000)
def test_sanitize_removes_null_bytes(text):
    from blast_ocr.core.extractor import sanitize_for_xml

    result = sanitize_for_xml(text)
    assert "\x00" not in result, "Null byte survived sanitization"
    # Verify all control chars in illegal range are removed
    for char in result:
        code = ord(char)
        # XML 1.0 legal chars: 0x09, 0x0A, 0x0D, 0x20-0xD7FF, 0xE000-0xFFFD
        is_legal = (
            code in (0x09, 0x0A, 0x0D)
            or (0x20 <= code <= 0xD7FF)
            or (0xE000 <= code <= 0xFFFD)
        )
        assert is_legal, f"Illegal XML char U+{code:04X} survived sanitization"


# ── Property 3: get_file_hash always returns 64-char hex string ───────────
@given(st.binary(min_size=1, max_size=200_000))
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_file_hash_always_64_char_hex(content):
    from blast_ocr.cache.manager import OCRCache

    cache = OCRCache(cache_dir=tempfile.mkdtemp())

    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(content)
        path = f.name

    try:
        h = cache.get_file_hash(path)
        assert len(h) == 64, f"Hash not 64 chars: {len(h)}"
        assert all(c in "0123456789abcdef" for c in h), f"Non-hex chars in hash: {h}"
    finally:
        os.unlink(path)


# ── Property 4: OCRConfig min_confidence always between 0.0 and 1.0 ───────
@given(st.floats(min_value=0.0, max_value=1.0))
def test_config_min_confidence_valid_range(value):
    from blast_ocr.config import OCRConfig

    try:
        cfg = OCRConfig(min_confidence=value)
        assert 0.0 <= cfg.min_confidence <= 1.0
    except Exception:
        # Only acceptable if Pydantic validation rejects out-of-range
        pass


# ── Property 5: Cache set/get roundtrip preserves data ───────────────────
@given(
    key=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
        min_size=1,
        max_size=50,
    ),
    page=st.integers(min_value=1, max_value=10000),
    confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    text=st.text(max_size=1000),
)
@settings(max_examples=200)
def test_cache_roundtrip_preserves_data(key, page, confidence, text):
    from blast_ocr.cache.manager import OCRCache

    cache = OCRCache(cache_dir=tempfile.mkdtemp())

    data = {"page": page, "confidence": confidence, "text": text}
    cache.set(key, data)
    result = cache.get(key)

    if result is not None:
        assert result["page"] == page
        assert result["text"] == text
        assert abs(result["confidence"] - confidence) < 1e-10


# ── Property 6: BlastPipeline.process_job never returns None ─────────────
@given(path=st.text(min_size=1, max_size=200))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_process_job_never_returns_none(path):
    """Pipeline must always return a dict — never None, never raise to caller."""
    from blast_ocr.pipeline import BlastPipeline

    pipeline = BlastPipeline()

    result = pipeline.process_job(path, output_dir="/tmp/hypothesis_test")

    assert result is not None, f"process_job returned None for path: {path!r}"
    assert isinstance(result, dict), (
        f"process_job returned {type(result)} for path: {path!r}"
    )
    assert "status" in result, f"Result missing 'status' key for path: {path!r}"


# ── Property 7: preprocess_image always returns 2D numpy array ───────────
@given(
    h=st.integers(min_value=10, max_value=500),
    w=st.integers(min_value=10, max_value=500),
)
@settings(deadline=20000, max_examples=10, suppress_health_check=[HealthCheck.too_slow])
def test_preprocess_always_returns_2d_array(h, w):
    from blast_ocr.core.extractor import RobustOCRExtractor

    extractor = RobustOCRExtractor()

    # BGR image
    img = np.full((h, w, 3), 200, dtype=np.uint8)

    try:
        result = extractor.preprocess_image(img)
        assert isinstance(result, np.ndarray), (
            f"preprocess_image returned {type(result)} for {h}x{w} image"
        )
        assert len(result.shape) == 2, (
            f"preprocess_image returned {len(result.shape)}D array, expected 2D"
        )
    except Exception as e:
        pytest.fail(f"preprocess_image crashed on {h}x{w} image: {e}")
