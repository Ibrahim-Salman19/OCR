"""
tests/test_script_mismatch_fallback.py

Coverage for two follow-up fixes to the Urdu/Arabic-script RapidOCR wiring
(see tests/test_rapidocr_arabic.py for the original bug this builds on):

1. `reorder_rtl_visual_to_logical` (blast_ocr.core.script_detection): the
   original fix reversed a detection's ENTIRE text whenever it contained
   any RTL character. That's correct for a pure-RTL line but wrong for a
   mixed line -- an Urdu sentence with an embedded English word or a
   number, which is routine in real Urdu textbooks -- since a blind
   whole-string reversal also scrambles the embedded LTR run's internal
   character order.

2. Automatic per-page script-mismatch fallback in
   `RapidOCREngine.process_page`: the original fix only activates the
   Arabic-script model when `config.ocr_languages` is explicitly set to
   request it. A page whose script doesn't match whatever model is
   *actually* active (e.g. an Urdu scan processed under the default
   English-only config, or an English chapter inside a book processed
   under an explicit Urdu config) still silently loses its text, and the
   confidence score alone can't detect it: RapidOCR drops low-scoring,
   out-of-dictionary detections before they're ever returned, so the
   handful of detections that DO survive (e.g. a page number) can carry a
   perfectly normal confidence while nearly everything else on the page
   vanished. `RapidOCREngine.process_page` now cross-checks recognized
   character yield against `estimate_page_text_signal`'s independent,
   script-agnostic measurement of how much glyph-shaped ink is actually on
   the page, and retries with the other recognition model when the two
   disagree sharply.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from blast_ocr.config import config
from blast_ocr.core.engines.rapidocr_engine import RapidOCREngine, _is_low_yield
from blast_ocr.core.script_detection import reorder_rtl_visual_to_logical

FIXTURE_IMAGE = str(Path(__file__).parent / "fixtures" / "urdu_ocr_sample.png")


@pytest.fixture(autouse=True)
def _restore_ocr_languages():
    original = list(config.ocr_languages)
    yield
    config.ocr_languages = original


# ---------------------------------------------------------------------------
# reorder_rtl_visual_to_logical
# ---------------------------------------------------------------------------


def test_reorder_matches_plain_reversal_for_pure_rtl_text():
    """Degenerate case (single script for the whole string) must produce
    byte-identical output to the original text[::-1] fix."""
    raw = "دورا"
    assert reorder_rtl_visual_to_logical(raw) == raw[::-1]


def test_reorder_preserves_embedded_ltr_word_internally():
    """An English word embedded in an Urdu line must come back with its
    own letters in the correct order, not reversed -- a blind
    text[::-1] would spell it backwards."""
    logical = "کتاب Physics کی"
    # Construct what the CTC recognizer would actually emit for this line:
    # each RTL run internally reversed (visual order), non-RTL runs left
    # as-is, whole run sequence mirrored left-to-right.
    runs = [(True, "کتاب"), (False, " Physics "), (True, "کی")]
    visual = "".join(t[::-1] if is_rtl else t for is_rtl, t in reversed(runs))

    recovered = reorder_rtl_visual_to_logical(visual)

    assert recovered == logical
    assert "Physics" in recovered  # not "scisyhP"


def test_reorder_preserves_embedded_digit_run():
    """A number embedded in an RTL line must keep its digit order --
    mirrors the existing real-model assertion that '12' must not become
    '21'."""
    runs = [(True, "کتاب"), (False, "2024"), (True, "سن")]
    visual = "".join(t[::-1] if is_rtl else t for is_rtl, t in reversed(runs))

    recovered = reorder_rtl_visual_to_logical(visual)

    assert "2024" in recovered
    assert "4202" not in recovered


def test_reorder_empty_string_is_safe():
    assert reorder_rtl_visual_to_logical("") == ""


# ---------------------------------------------------------------------------
# _is_low_yield threshold logic
# ---------------------------------------------------------------------------


def test_low_yield_requires_minimum_ink_signal():
    """A page with too little connected-component signal to trust (per
    page_signal's own cutoff) must never trigger the fallback, regardless
    of how little text came back -- there's no confirmed ink to justify
    a retry."""
    assert _is_low_yield(total_chars=0, ink_component_count=None) is False
    assert _is_low_yield(total_chars=0, ink_component_count=5) is False


def test_low_yield_fires_when_text_is_sparse_relative_to_ink():
    """The reported bug's exact shape: lots of visible glyph-shaped ink,
    almost nothing recognized (e.g. only a page number)."""
    assert _is_low_yield(total_chars=2, ink_component_count=200) is True


def test_low_yield_does_not_fire_for_implausibly_high_ink_component_count():
    """A photographed cloth book cover's fabric weave pattern can itself
    look like thousands of tiny glyph-shaped connected components to
    page_signal's raw-image analysis (measured: 13832 on a real gold-
    corpus cover page, versus a real max of 2370 across every genuine
    text page in the same corpus) -- despite carrying no real text at
    all. An implausibly high count should be treated as untrustworthy
    noise, not as confirmed ink volume that could justify an
    unnecessary (and, for the Arabic-script direction, network-
    dependent) fallback pass on a page that has nothing to do with a
    script mismatch."""
    assert _is_low_yield(total_chars=6, ink_component_count=13832) is False


def test_low_yield_does_not_fire_for_a_normally_recognized_page():
    """A page where recognized character count is proportionate to the
    ink signal must not trigger an unnecessary fallback pass."""
    assert _is_low_yield(total_chars=400, ink_component_count=200) is False


# ---------------------------------------------------------------------------
# RapidOCREngine.process_page: automatic fallback wiring
# ---------------------------------------------------------------------------


def _dual_model_side_effect(default_payload, arabic_payload):
    """Builds a side_effect for a patched `rapidocr_onnxruntime.RapidOCR`
    class constructor that returns a distinct mock instance depending on
    whether it was constructed with the Arabic-script rec_model_path
    kwargs (matching RapidOCREngine._init_arabic_engine) or with no
    kwargs at all (matching _init_engine)."""
    default_mock = MagicMock()
    default_mock.return_value = default_payload
    arabic_mock = MagicMock()
    arabic_mock.return_value = arabic_payload

    def side_effect(*args, **kwargs):
        return arabic_mock if "rec_model_path" in kwargs else default_mock

    return side_effect, default_mock, arabic_mock


def _payload(text, conf=0.9):
    return ([[[[0, 0], [10, 0], [10, 10], [0, 10]], text, conf]], 0.01)


def test_fallback_recovers_text_when_default_model_under_yields():
    """The core new behavior: default English config, but the page is
    actually Urdu. Primary (default) pass recovers almost nothing; the
    ink signal says the page is dense with text; the engine must retry
    with the Arabic-script model and adopt its (better) result."""
    config.ocr_languages = ["en"]

    side_effect, default_mock, arabic_mock = _dual_model_side_effect(
        default_payload=_payload("12", 0.99),  # only the page number "survives"
        arabic_payload=_payload("اردوکتاب", 0.9),
    )

    with patch(
        "blast_ocr.core.engines.rapidocr_engine.estimate_page_text_signal",
        return_value=(24.0, 250, 50000.0),
    ), patch(
        "blast_ocr.core.engines.rapidocr_engine.ensure_arabic_model",
        return_value=("/fake/arabic_rec.onnx", "/fake/arabic_dict.txt"),
    ), patch(
        "rapidocr_onnxruntime.RapidOCR", side_effect=side_effect
    ):
        engine = RapidOCREngine()
        result = engine.process_page(FIXTURE_IMAGE, page_number=1)

    assert result["script_fallback_applied"] is True
    assert "script_fallback_error" not in result
    assert "اردوکتاب"[::-1] in result["text"] or "اردوکتاب" in result["text"]
    assert default_mock.called
    assert arabic_mock.called


def test_fallback_not_attempted_without_enough_ink_signal():
    """A genuinely sparse page (or one page_signal can't measure, e.g. a
    photographed cover) must not trigger a fallback pass, even if very
    little text was recognized."""
    config.ocr_languages = ["en"]

    side_effect, default_mock, arabic_mock = _dual_model_side_effect(
        default_payload=_payload("hi", 0.95),
        arabic_payload=_payload("اردو", 0.9),
    )

    with patch(
        "blast_ocr.core.engines.rapidocr_engine.estimate_page_text_signal",
        return_value=None,
    ), patch(
        "rapidocr_onnxruntime.RapidOCR", side_effect=side_effect
    ):
        engine = RapidOCREngine()
        result = engine.process_page(FIXTURE_IMAGE, page_number=1)

    assert "script_fallback_applied" not in result
    assert not arabic_mock.called
    assert default_mock.call_count == 1


def test_fallback_unavailable_degrades_gracefully():
    """If the Arabic-script model can't be reached (offline, download
    disabled), the page must still return the primary result instead of
    raising -- but the suspected mismatch must be surfaced, not
    swallowed, so the pipeline layer can flag it instead of reporting a
    clean success."""
    from blast_ocr.core.engines.script_models import ArabicModelUnavailableError

    config.ocr_languages = ["en"]

    side_effect, default_mock, _arabic_mock = _dual_model_side_effect(
        default_payload=_payload("12", 0.99),
        arabic_payload=_payload("اردو", 0.9),
    )

    with patch(
        "blast_ocr.core.engines.rapidocr_engine.estimate_page_text_signal",
        return_value=(24.0, 250, 50000.0),
    ), patch(
        "blast_ocr.core.engines.rapidocr_engine.ensure_arabic_model",
        side_effect=ArabicModelUnavailableError("no network"),
    ), patch(
        "rapidocr_onnxruntime.RapidOCR", side_effect=side_effect
    ):
        engine = RapidOCREngine()
        result = engine.process_page(FIXTURE_IMAGE, page_number=1)

    assert "script_fallback_applied" not in result
    assert result["script_fallback_error"] == "no network"
    assert result["details"][0]["text"] == "12"


def test_fallback_is_symmetric_for_explicit_rtl_config():
    """Mirror case: an explicitly Urdu-configured job hits an English (or
    otherwise non-RTL) page -- e.g. an English appendix inside an Urdu
    book. The engine must retry with the default model and adopt it if
    it recovers more text."""
    config.ocr_languages = ["ur"]

    side_effect, default_mock, arabic_mock = _dual_model_side_effect(
        default_payload=_payload("Appendix A: Glossary of Terms", 0.95),
        arabic_payload=_payload("12", 0.99),  # only a stray page-number-like glyph
    )

    with patch(
        "blast_ocr.core.engines.rapidocr_engine.estimate_page_text_signal",
        return_value=(24.0, 250, 50000.0),
    ), patch(
        "blast_ocr.core.engines.rapidocr_engine.ensure_arabic_model",
        return_value=("/fake/arabic_rec.onnx", "/fake/arabic_dict.txt"),
    ), patch(
        "rapidocr_onnxruntime.RapidOCR", side_effect=side_effect
    ):
        engine = RapidOCREngine()
        result = engine.process_page(FIXTURE_IMAGE, page_number=1)

    assert result["script_fallback_applied"] is True
    assert "Appendix A: Glossary of Terms" in result["text"]
    assert default_mock.called
    assert arabic_mock.called
