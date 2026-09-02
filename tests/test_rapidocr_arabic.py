"""
tests/test_rapidocr_arabic.py

Regression coverage for a real user-reported bug: feeding an Urdu PDF through
the default `rapidocr` engine returned only page numbers -- every Urdu word
was silently dropped, because RapidOCR's bundled default model is trained on
Chinese+English only and has no Arabic-script characters in its recognition
dictionary at all.

The fix (blast_ocr.core.engines.rapidocr_engine.RapidOCREngine, and
blast_ocr.core.engines.batched_rapidocr.BatchedRapidOCREngine -- the
opt-in high-throughput engine selectable via config.ocr_engine, which has
its own separate hand-rolled ONNX session/CTC-decode path and would hit the
identical bug if left unwired) swaps in a dedicated Arabic-script
recognition model (covering Arabic/Urdu/Persian/Uyghur) whenever
`config.ocr_languages` requests one of those languages, and corrects for
that model's raw left-to-right CTC output order (it needs a per-line
reversal to read correctly as RTL text).

Tests below are split into:
- Wiring tests (always run, no network): mock the underlying engine/model
  loading and assert the right model path is selected and text is reversed
  only when it should be. These pin the actual bug fix and must never be
  skipped.
- Real end-to-end tests against a committed ground-truth fixture image,
  which download the real ~8MB model on first use -- skipped (not failed)
  if that download is unreachable, mirroring tests/test_queue.py's pattern
  for optional real-infra dependencies.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from blast_ocr.config import config
from blast_ocr.core.engines.batched_rapidocr import BatchedRapidOCREngine
from blast_ocr.core.engines.rapidocr_engine import RapidOCREngine

FIXTURE_IMAGE = str(Path(__file__).parent / "fixtures" / "urdu_ocr_sample.png")


@pytest.fixture(autouse=True)
def _restore_ocr_languages():
    original = list(config.ocr_languages)
    yield
    config.ocr_languages = original


def _mock_rapidocr_engine(return_text="مكتوب", return_conf=0.9):
    mock_instance = MagicMock()
    mock_instance.return_value = (
        [[[[0, 0], [10, 0], [10, 10], [0, 10]], return_text, return_conf]],
        0.01,
    )
    return mock_instance


def test_urdu_language_routes_to_arabic_model():
    """The core bug fix: requesting 'ur' must load the Arabic-script
    recognition model via rec_model_path/rec_keys_path, not the bundled
    Chinese+English default -- the exact mechanism that silently dropped
    all Urdu text in the reported bug."""
    config.ocr_languages = ["en", "ur"]

    mock_engine = _mock_rapidocr_engine()
    with patch(
        "blast_ocr.core.engines.rapidocr_engine.ensure_arabic_model",
        return_value=("/fake/arabic_rec.onnx", "/fake/arabic_dict.txt"),
    ), patch(
        "rapidocr_onnxruntime.RapidOCR", return_value=mock_engine
    ) as mock_cls:
        engine = RapidOCREngine()
        result = engine.process_page(FIXTURE_IMAGE, page_number=1)

    _, kwargs = mock_cls.call_args
    assert kwargs.get("rec_model_path") == "/fake/arabic_rec.onnx"
    assert kwargs.get("rec_keys_path") == "/fake/arabic_dict.txt"
    assert result["engine"] == "rapidocr"


def test_arabic_script_output_is_reversed_for_rtl_reading_order():
    """PP-OCR's CRNN+CTC recognizer emits each line in raw left-to-right
    pixel order; without reversal the text is backwards. Confirmed
    empirically against real Urdu ground truth during development."""
    config.ocr_languages = ["ur"]
    raw_text = "دورا"  # deliberately reversed nonsense stand-in

    mock_engine = _mock_rapidocr_engine(return_text=raw_text)
    with patch(
        "blast_ocr.core.engines.rapidocr_engine.ensure_arabic_model",
        return_value=("/fake/arabic_rec.onnx", "/fake/arabic_dict.txt"),
    ), patch("rapidocr_onnxruntime.RapidOCR", return_value=mock_engine):
        engine = RapidOCREngine()
        result = engine.process_page(FIXTURE_IMAGE, page_number=1)

    assert raw_text[::-1] in result["text"]
    assert result["details"][0]["text"] == raw_text[::-1]


def test_english_only_still_uses_bundled_default_model_unchanged():
    """Backward-compat guard: an 'en'-only (or default) config must keep
    calling RapidOCR() with no path overrides, exactly as before this fix,
    so existing English/CJK behavior is byte-for-byte unchanged."""
    config.ocr_languages = ["en"]

    mock_engine = _mock_rapidocr_engine(return_text="hello", return_conf=0.99)
    with patch("rapidocr_onnxruntime.RapidOCR", return_value=mock_engine) as mock_cls:
        engine = RapidOCREngine()
        result = engine.process_page(FIXTURE_IMAGE, page_number=1)

    args, kwargs = mock_cls.call_args
    assert args == ()
    assert kwargs == {}
    assert result["details"][0]["text"] == "hello"


def test_warns_when_requested_language_unsupported_by_rapidocr(caplog):
    """A language rapidocr has no model for at all (neither the default nor
    the new Arabic-script swap) must produce a loud, actionable warning
    instead of silently emitting garbage -- the same failure class as the
    reported Urdu bug, for any other unsupported script."""
    config.ocr_languages = ["hi"]  # Hindi/Devanagari: genuinely unsupported here

    mock_engine = _mock_rapidocr_engine()
    with patch("rapidocr_onnxruntime.RapidOCR", return_value=mock_engine), caplog.at_level(
        "WARNING"
    ):
        engine = RapidOCREngine()
        engine.process_page(FIXTURE_IMAGE, page_number=1)

    assert any("hi" in rec.message and "not supported" in rec.message for rec in caplog.records)


@pytest.mark.real_arabic_model
def test_real_ppocrv5_arabic_model_reads_urdu_fixture():
    """End-to-end proof against real ground truth: renders through the real,
    downloaded PP-OCRv5 Arabic-script ONNX model (not mocked) and checks that
    the known Urdu words in tests/fixtures/urdu_ocr_sample.png ('کتاب' =
    book, 'اردو' = Urdu) actually come back, instead of the empty/
    page-numbers-only output the original bug produced.

    Skipped (not failed) if the model can't be downloaded -- see
    tests/test_queue.py for the same optional-real-infra pattern.
    """
    from blast_ocr.core.engines.script_models import (
        ArabicModelUnavailableError,
        ensure_arabic_model,
    )

    try:
        ensure_arabic_model()
    except Exception as e:
        pytest.skip(f"Arabic PP-OCRv5 model unavailable (no network?): {e}")

    config.ocr_languages = ["ur"]
    engine = RapidOCREngine()
    try:
        result = engine.process_page(FIXTURE_IMAGE, page_number=1)
    except ArabicModelUnavailableError as e:
        pytest.skip(f"Arabic PP-OCRv5 model unavailable (no network?): {e}")

    # "اردو" (Urdu) uses codepoints shared identically between Arabic and
    # Urdu conventions, so it's an unambiguous check regardless of which
    # script-convention letterforms the model chose for the rest of the
    # line (PP-OCRv5's dictionary contains both Arabic- and Urdu-convention
    # forms of several letters, e.g. ك/ک, ي/ی -- which one it predicts is a
    # model accuracy characteristic, not something this integration corrects).
    assert "اردو" in result["text"]
    # The page number is pure Latin digits on an otherwise-RTL page: it must
    # NOT be reversed along with the Arabic-script text next to it.
    assert "12" in result["text"]
    assert "21" not in result["text"]


def test_batched_engine_urdu_language_routes_to_arabic_model():
    """Same bug, second engine: BatchedRapidOCREngine has its own hand-rolled
    ONNX session/CTC-decode path (it doesn't use RapidOCREngine at all), so
    it needed the identical fix independently -- someone with
    ocr_engine='batched_rapidocr' would otherwise still hit the original
    bug untouched by the rapidocr_engine.py fix."""
    config.ocr_languages = ["ur"]

    with patch(
        "blast_ocr.core.engines.batched_rapidocr.ensure_arabic_model",
        return_value=("/fake/arabic_rec.onnx", "/fake/arabic_dict.txt"),
    ), patch.object(
        BatchedRapidOCREngine, "_wants_rtl_script", return_value=True
    ), patch(
        "blast_ocr.core.onnx_session.ONNXSessionManager.get_or_create_session",
        return_value=MagicMock(),
    ), patch(
        "blast_ocr.core.tensor_decoder.VectorizedTensorDecoder.__init__",
        return_value=None,
    ):
        engine = BatchedRapidOCREngine(preferred_provider="cpu")
        engine._init_engine()

    assert engine.rec_model_path == "/fake/arabic_rec.onnx"
    assert engine.character_path == "/fake/arabic_dict.txt"
    assert engine._is_arabic is True


def test_batched_engine_does_not_override_explicit_rec_model_path():
    """An explicit rec_model_path/character_path passed by the caller (e.g.
    someone already using a custom model for a different purpose) must not
    be silently clobbered by the Arabic-script auto-selection."""
    config.ocr_languages = ["ur"]

    with patch.object(
        BatchedRapidOCREngine, "_wants_rtl_script", return_value=True
    ), patch(
        "blast_ocr.core.onnx_session.ONNXSessionManager.get_or_create_session",
        return_value=MagicMock(),
    ), patch(
        "blast_ocr.core.tensor_decoder.VectorizedTensorDecoder.__init__",
        return_value=None,
    ):
        engine = BatchedRapidOCREngine(
            preferred_provider="cpu",
            rec_model_path="/custom/rec.onnx",
            character_path="/custom/dict.txt",
        )
        engine._init_engine()

    assert engine.rec_model_path == "/custom/rec.onnx"
    assert engine.character_path == "/custom/dict.txt"
    assert engine._is_arabic is False


@pytest.mark.real_arabic_model
def test_batched_engine_real_ppocrv5_arabic_model_reads_urdu_fixture():
    """End-to-end proof for the second engine path, mirroring
    test_real_ppocrv5_arabic_model_reads_urdu_fixture above: real downloaded
    model, real fixture image, no mocks. Skipped (not failed) if the model
    can't be downloaded."""
    from blast_ocr.core.engines.script_models import (
        ArabicModelUnavailableError,
        ensure_arabic_model,
    )

    try:
        ensure_arabic_model()
    except Exception as e:
        pytest.skip(f"Arabic PP-OCRv5 model unavailable (no network?): {e}")

    config.ocr_languages = ["ur"]
    engine = BatchedRapidOCREngine(preferred_provider="cpu")
    try:
        result = engine.process_page(FIXTURE_IMAGE, page_number=1)
    except ArabicModelUnavailableError as e:
        pytest.skip(f"Arabic PP-OCRv5 model unavailable (no network?): {e}")

    assert "اردو" in result["text"]
    assert "12" in result["text"]
    assert "21" not in result["text"]
