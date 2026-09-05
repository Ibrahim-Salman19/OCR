"""
tests/test_urdu_accuracy_measurement.py

Real, measured Urdu OCR accuracy -- not just a wiring/mechanism check.

tests/test_rapidocr_arabic.py pins that requesting Urdu routes to the
Arabic-script model and reverses text correctly; it does that against a
single small fixture and (for the real-model tests) checks for two known
words. That proves the *mechanism* works. It says nothing about how
accurate the actual recognized text is, which is the real question when the
declared goal is Urdu OCR reliability.

This file measures actual character error rate (CER, via the same
eval/metrics.compute_cer the project's own eval harness uses for English)
against two committed fixture pages of correctly-shaped Urdu text with known
ground truth:

  tests/fixtures/urdu_synthetic_naskh.png     -- clean print-style Arabic
      script (Noto Naskh Arabic), the style PP-OCRv5's training data is
      predominantly drawn from.
  tests/fixtures/urdu_synthetic_nastaliq.png  -- traditional calligraphic
      Urdu typesetting (Noto Nastaliq Urdu), the conventional style for
      printed Urdu books/newspapers.

Both were rendered via PIL + libraqm (real glyph shaping and bidi
reordering, not naive codepoint drawing) from seven short, grammatically
correct Urdu sentences -- including one with an embedded English word
("Physics") and one with embedded digits ("2024") to exercise the same
mixed-script reading-order fix tests/test_script_mismatch_fallback.py
covers structurally. See docs/adr/ or the session notes for the exact
rendering script if it needs to be regenerated; the committed PNGs are the
source of truth here, not the (uncommitted) font files used to produce
them.

Measured baseline (2026-09-03, PP-OCRv5 Arabic-script model, real
download, no mocking):
    naskh    : CER = 0.31  (WER = 0.65)
    nastaliq : CER = 0.60  (WER = 0.89)

The gap between these two is itself a real, useful finding: this
recognition model is measurably worse on traditional Nastaliq calligraphy
than on plain-print Naskh, which matters because Nastaliq is the
conventional style for printed Urdu books -- a real limitation, not a
solved problem. The assertions below use a generous margin above the
measured baseline (not the CER a user should expect in production) purely
to catch a REGRESSION -- e.g. a future change that breaks Arabic-script
recognition entirely and silently degrades to near-100% CER -- rather than
to claim a tight accuracy guarantee.
"""

from pathlib import Path

import pytest

from blast_ocr.config import config

GOLD_TEXT = (
    "کتاب میز پر ہے۔ میرا نام علی ہے اور میں سکول جاتا ہوں۔ "
    "اردو ایک خوبصورت زبان ہے۔ اس کتاب کا نام Physics ہے۔ "
    "آج کی تاریخ 2024 ہے۔ پاکستان اور بھارت جنوبی ایشیا میں واقع ہیں۔ "
    "علم حاصل کرنا ہر مسلمان پر فرض ہے۔ 12"
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Regression ceilings, not accuracy targets: generous margin above the
# measured baseline in the module docstring above. A real improvement to
# the recognition model or preprocessing should LOWER measured CER well
# below these; these exist only to catch a future regression that breaks
# Arabic-script recognition, not to represent acceptable production
# quality.
_NASKH_CER_CEILING = 0.45
_NASTALIQ_CER_CEILING = 0.75


@pytest.fixture(autouse=True)
def _restore_ocr_languages():
    original = list(config.ocr_languages)
    yield
    config.ocr_languages = original


def _measure(image_name: str) -> dict:
    from blast_ocr.core.engines.rapidocr_engine import RapidOCREngine
    from blast_ocr.core.engines.script_models import ArabicModelUnavailableError, ensure_arabic_model
    from eval.metrics import compute_cer, compute_wer

    try:
        ensure_arabic_model()
    except Exception as e:
        pytest.skip(f"Arabic PP-OCRv5 model unavailable (no network?): {e}")

    path = str(FIXTURES_DIR / image_name)
    engine = RapidOCREngine()
    try:
        result = engine.process_page(path, page_number=1, languages=["ur"])
    except ArabicModelUnavailableError as e:
        pytest.skip(f"Arabic PP-OCRv5 model unavailable (no network?): {e}")

    return {
        "text": result["text"],
        "confidence": result["confidence"],
        "cer": compute_cer(GOLD_TEXT, result["text"]),
        "wer": compute_wer(GOLD_TEXT, result["text"]),
    }


@pytest.mark.real_arabic_model
def test_measured_cer_naskh_within_regression_ceiling():
    m = _measure("urdu_synthetic_naskh.png")
    assert m["cer"] <= _NASKH_CER_CEILING, (
        f"Urdu (Naskh) CER regressed to {m['cer']:.3f} (ceiling "
        f"{_NASKH_CER_CEILING}); measured baseline was 0.31. Recognized: "
        f"{m['text']!r}"
    )


@pytest.mark.real_arabic_model
def test_measured_cer_nastaliq_within_regression_ceiling():
    m = _measure("urdu_synthetic_nastaliq.png")
    assert m["cer"] <= _NASTALIQ_CER_CEILING, (
        f"Urdu (Nastaliq) CER regressed to {m['cer']:.3f} (ceiling "
        f"{_NASTALIQ_CER_CEILING}); measured baseline was 0.60. Recognized: "
        f"{m['text']!r}"
    )


@pytest.mark.real_arabic_model
def test_default_config_auto_detects_and_matches_explicit_language_quality():
    """The auto-fallback mechanism (RapidOCREngine._is_low_yield, see
    tests/test_script_mismatch_fallback.py for the mocked wiring tests)
    must, on a REAL page with REAL confidence numbers, recover
    essentially the same CER as an explicit ocr_languages=["ur"]
    configuration -- proving a user does not need to know or configure
    anything for Urdu content to be recognized correctly."""
    from blast_ocr.core.engines.rapidocr_engine import RapidOCREngine
    from blast_ocr.core.engines.script_models import ArabicModelUnavailableError, ensure_arabic_model
    from eval.metrics import compute_cer

    try:
        ensure_arabic_model()
    except Exception as e:
        pytest.skip(f"Arabic PP-OCRv5 model unavailable (no network?): {e}")

    config.ocr_languages = ["en"]  # default -- no Urdu configured at all
    path = str(FIXTURES_DIR / "urdu_synthetic_naskh.png")
    engine = RapidOCREngine()
    try:
        result = engine.process_page(path, page_number=1)  # no languages override either
    except ArabicModelUnavailableError as e:
        pytest.skip(f"Arabic PP-OCRv5 model unavailable (no network?): {e}")

    assert result.get("script_fallback_applied") is True, (
        "BUG: default English config on a real Urdu page did not trigger the "
        "automatic script-mismatch fallback -- this is the original reported "
        "bug's exact shape."
    )
    cer = compute_cer(GOLD_TEXT, result["text"])
    assert cer <= _NASKH_CER_CEILING, (
        f"Auto-detected CER {cer:.3f} exceeds the same ceiling as the "
        f"explicit-language case; auto-fallback should recover equivalent "
        f"quality, not degraded quality. Recognized: {result['text']!r}"
    )
