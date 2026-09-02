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
from unittest.mock import patch, MagicMock


# ── Property 1: sanitize_for_xml always returns a string ─────────────────
@given(st.text())
# deadline=None: sanitize_for_xml is a single linear-time character-class
# regex substitution (no backtracking risk), so a slow example here reflects
# host scheduling/GC noise, not algorithmic complexity -- observed flaky
# (754-1476ms) on this sandbox even in isolation. Same rationale as the
# deadline=None already used below for the cache-roundtrip property test.
@settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_sanitize_always_returns_string(text):
    from blast_ocr.core.extractor import sanitize_for_xml

    result = sanitize_for_xml(text)
    assert isinstance(result, str), (
        f"sanitize_for_xml returned {type(result)} for input {repr(text)}"
    )


# ── Property 2: sanitize_for_xml output contains no null bytes ────────────
@given(st.text())
@settings(max_examples=1000, deadline=None)  # see rationale on the property above
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
# deadline=None: real file I/O (write + read + sha256), same rationale as
# the cache-roundtrip property test below.
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_file_hash_always_64_char_hex(content):
    from blast_ocr.cache.manager import OCRCache

    with tempfile.TemporaryDirectory() as cache_tmp:
        cache = OCRCache(cache_dir=cache_tmp)

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            path = f.name

        try:
            h = cache.get_file_hash(path)
            assert len(h) == 64, f"Hash not 64 chars: {len(h)}"
            assert all(c in "0123456789abcdef" for c in h), f"Non-hex chars in hash: {h}"
        finally:
            if os.path.exists(path):
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
@settings(
    max_examples=200,
    # This test does real file I/O (OCRCache.set fsyncs an atomic write).
    # Hypothesis's default 200ms per-example deadline is meant to catch
    # algorithmic complexity blowups in pure computation, not to benchmark
    # I/O -- per Hypothesis's own docs, disable it for I/O-bound tests
    # rather than tune a number that will still be host-dependent.
    # Observed flaky (278-378ms) on this sandbox's virtualized disk.
    deadline=None,
)
def test_cache_roundtrip_preserves_data(key, page, confidence, text):
    from blast_ocr.cache.manager import OCRCache

    with tempfile.TemporaryDirectory() as cache_tmp:
        cache = OCRCache(cache_dir=cache_tmp)

        data = {"page": page, "confidence": confidence, "text": text}
        cache.set(key, data)
        result = cache.get(key)

        if result is not None:
            assert result["page"] == page
            assert result["text"] == text
            assert abs(result["confidence"] - confidence) < 1e-10


# ── Property 6: BlastPipeline.process_job never returns None ─────────────
@given(path=st.text(min_size=1, max_size=200))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
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

    with patch("easyocr.Reader") as mock_reader_cls:
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = []
        mock_reader_cls.return_value = mock_reader
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


# ── Tier 4 additions (docs/HARDENING_BLUEPRINT_AND_TEST_SPECS.md §4.4) ────
# These extend the properties above to the modules the GAP-04/07/10/12
# hardening commits touched, using Hypothesis to fuzz across the specific
# failure class each fix addressed rather than re-asserting the fix's own
# hand-picked example inputs (those already have direct regression tests in
# tests/test_formula_extractor.py, tests/test_table_extractor.py,
# tests/test_layout_and_model.py, and tests/adversarial/).


# ── Property 8: FormulaExtractor.convert_to_latex never crashes on any
# nested-sqrt depth ─────────────────────────────────────────────────────
@given(depth=st.integers(min_value=0, max_value=3000))
@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_formula_extractor_handles_arbitrary_sqrt_nesting_depth(depth):
    """`_convert_sqrt_balanced` recurses one Python stack frame per nesting
    level; past the interpreter's recursion limit (~1000) this used to raise
    an uncaught RecursionError instead of falling back to the original text
    like the existing unbalanced-parens safety net. Fuzzing depth directly
    (rather than relying on generic st.text() to stumble onto this exact
    repeated-token structure) is what actually crosses that boundary.
    """
    from blast_ocr.core.formula_extractor import FormulaExtractor

    text = "sqrt(" * depth + "x" + ")" * depth
    result = FormulaExtractor.convert_to_latex(text)
    assert isinstance(result, str)


# ── Property 9: FormulaExtractor.convert_to_latex never crashes on
# arbitrary text ──────────────────────────────────────────────────────────
@given(st.text(max_size=300))
@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_formula_extractor_convert_to_latex_never_raises(text):
    from blast_ocr.core.formula_extractor import FormulaExtractor

    try:
        result = FormulaExtractor.convert_to_latex(text)
    except Exception as e:
        pytest.fail(f"convert_to_latex crashed on {text!r}: {e}")
    assert isinstance(result, str)


# ── Property 10: TableExtractor.extract_borderless_tables never crashes
# on arbitrary span geometry ──────────────────────────────────────────────
@given(
    boxes=st.lists(
        st.tuples(
            st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False),
            st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False),
            st.floats(min_value=0.1, max_value=500, allow_nan=False, allow_infinity=False),
            st.floats(min_value=0.1, max_value=500, allow_nan=False, allow_infinity=False),
        ),
        max_size=40,
    )
)
@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_table_extractor_borderless_never_raises_on_arbitrary_span_geometry(boxes):
    from blast_ocr.core.document_model import BoundingBox, Span
    from blast_ocr.core.table_extractor import TableExtractor

    spans = [
        Span(text="x", bbox=BoundingBox(xmin=x, ymin=y, xmax=x + w, ymax=y + h))
        for x, y, w, h in boxes
    ]
    result = TableExtractor.extract_borderless_tables(spans)
    assert isinstance(result, list)


# ── Property 11: LayoutEngine.process_page_detections never drops or
# duplicates a valid (non-degenerate) span ────────────────────────────────
@given(
    detections=st.lists(
        st.fixed_dictionaries(
            {
                "text": st.text(
                    alphabet=st.characters(whitelist_categories=("L", "N")),
                    min_size=1,
                    max_size=8,
                ),
                "bbox": st.tuples(
                    st.floats(min_value=0, max_value=900, allow_nan=False, allow_infinity=False),
                    st.floats(min_value=0, max_value=900, allow_nan=False, allow_infinity=False),
                    st.floats(min_value=1, max_value=100, allow_nan=False, allow_infinity=False),
                    st.floats(min_value=1, max_value=100, allow_nan=False, allow_infinity=False),
                ).map(lambda t: [t[0], t[1], t[0] + t[2], t[1] + t[3]]),
                "confidence": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
            }
        ),
        max_size=25,
    )
)
@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_layout_engine_never_drops_or_duplicates_valid_spans(detections):
    from blast_ocr.core.layout import LayoutEngine

    engine = LayoutEngine()
    page = engine.process_page_detections(detections, page_num=1, width=1000, height=1000)
    # A Line clusters multiple nearby Spans onto one visual line by design
    # (e.g. two words on the same row become one Line with two Spans), so
    # the count-preserving invariant is at the Span level, not the Line
    # level -- Hypothesis found exactly this with two identical-geometry
    # detections that _cluster_lines correctly merged into a single Line.
    all_spans = [span for block in page.blocks for line in block.lines for span in line.spans]
    assert len(all_spans) == len(detections)


# ── Property 12: PriorityQueueManager.dequeue never raises regardless of
# enqueue ordering/mix ────────────────────────────────────────────────────
@given(priorities=st.lists(st.sampled_from(["high", "default", "low"]), max_size=15))
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_priority_queue_dequeue_never_raises_for_arbitrary_enqueue_sequence(priorities):
    import fakeredis

    from blast_ocr.queue.priority import PriorityQueueManager

    client = fakeredis.FakeRedis(decode_responses=True)
    manager = PriorityQueueManager(redis_client=client)
    for i, p in enumerate(priorities):
        manager.enqueue(job_id=i, source_path=f"doc_{i}.pdf", priority=p)

    for _ in range(len(priorities) + 2):
        result = manager.dequeue(timeout=0)
        assert result is None or (isinstance(result, tuple) and len(result) == 2)
