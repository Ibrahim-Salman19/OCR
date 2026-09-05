"""
blast_ocr.core.engines.rapidocr_engine

RapidOCR (ONNXRuntime) Engine Adapter implementation.
Fast CPU OCR using PaddleOCR-compatible ONNX models via rapidocr_onnxruntime.
"""

from typing import Dict, Any, List, Optional, Tuple
import time
import logging
import cv2

from blast_ocr.config import config
from blast_ocr.core.engines.base import BaseOCREngine
from blast_ocr.core.engines.script_models import (
    RTL_SCRIPT_LANGUAGES,
    ArabicModelUnavailableError,
    contains_rtl_script,
    ensure_arabic_model,
)
from blast_ocr.core.layout import LayoutEngine
from blast_ocr.core.page_signal import estimate_page_text_signal
from blast_ocr.core.script_detection import reorder_rtl_visual_to_logical

logger = logging.getLogger(__name__)

# Languages the bundled default model (ch_PP-OCRv4, Chinese+English trained)
# can actually recognize, plus the RTL scripts handled via the Arabic-script
# model swap below. Anything outside this set silently degrades to
# empty/garbage output for that text -- callers should prefer the `easyocr`
# engine (which loads a language pack per request) for other scripts.
_SUPPORTED_LANGUAGES = {"en", "zh", "ch_sim", "ch_tra"} | RTL_SCRIPT_LANGUAGES

# Script-mismatch fallback thresholds (see `_is_low_yield` below): only
# trust the ink-coverage signal once there are at least this many
# glyph-shaped components on the page (matches page_signal's own
# "not enough signal" cutoff), and only call the yield "suspiciously low"
# when recognized characters come in far under what that much visible ink
# would plausibly produce even in the sparsest legitimate case.
#
# Calibrated against two real measurements, not just mocked unit tests:
#
# 1. This project's own 14-page English gold corpus (eval/pages +
#    eval/gold): component counts range ~100-2400 per page, and actual
#    gold transcript length is consistently 0.95x-1.35x the component
#    count (Latin glyphs are mostly one connected component each).
#
# 2. A synthetic Urdu test page (correctly-shaped via raqm + Noto
#    Naskh/Nastaliq, real ground truth, real PP-OCRv5 Arabic model --
#    see tests/test_urdu_accuracy_measurement.py), run through this
#    engine under BOTH the correct (Arabic) and wrong (default) model to
#    measure real chars-recognized/ink-component ratios in both
#    directions:
#      correct model,  clean Naskh recognition   : ratio ~1.02
#      correct model,  harder Nastaliq recognition: ratio ~0.72
#      wrong model,    Naskh page                 : ratio ~0.13
#      wrong model,    Nastaliq page               : ratio ~0.14
#    An earlier, uncalibrated ratio (0.05) was proven too lenient by
#    this measurement: on the mixed Urdu/English page, the default
#    (wrong) model correctly recognized only its few embedded Latin
#    fragments ("Physics", "2024", a page number) while silently
#    dropping the entire Urdu majority of the page -- and that alone was
#    enough total_chars to clear a 5%-of-components bar, so the fallback
#    never fired and the original reported bug (Urdu text vanishing
#    while a normal-looking result is returned) reproduced even with
#    this mechanism in place. 0.4 sits with wide, real margin below every
#    correct-model measurement above (0.72, 1.02, and every English page)
#    and above every wrong-model measurement (0.13, 0.14) -- catching
#    the case the old threshold missed without risking a false positive
#    on a genuinely-hard-but-correctly-routed page.
_LOW_YIELD_MIN_INK_COMPONENTS = 20
_LOW_YIELD_MAX_CHARS_ABS = 5
_LOW_YIELD_MAX_CHARS_RATIO = 0.4

# Upper bound on how much the ink-component count is trusted at all.
# Measured on this project's own gold corpus: every genuine text page's
# component count tops out around 2370 (its densest body-prose page);
# a photographed cloth book cover (eval/pages/p097.png) measured 13832 --
# the fabric weave pattern itself is full of small, glyph-sized-and-shaped
# specks that pass every filter in page_signal._glyph_like_components
# despite carrying no real text at all (a texture-amplification failure
# mode page_signal.py's docstring already documents for CLAHE-preprocessed
# images; this shows the RAW image alone isn't always immune to it
# either). Below this threshold an implausibly high count still means
# "probably real, dense text, trust the ratio"; above it, the count
# itself is more likely texture noise than content, so the low-yield
# signal is not trusted at all rather than driving an unnecessary (and,
# for the Arabic-script direction, network-dependent) fallback pass on a
# page that has nothing to do with a script mismatch. Set with wide
# margin above the real max (2370) and well below the confirmed noise
# case (13832).
_LOW_YIELD_MAX_TRUSTED_INK_COMPONENTS = 5000


def _is_low_yield(total_chars: int, ink_component_count: Optional[int]) -> bool:
    """
    True if recognition returned suspiciously little text given how much
    glyph-shaped ink is actually visible on the raw page -- the signature
    of a script/recognition-model mismatch (see
    `estimate_text_ink_signal`'s docstring): RapidOCR drops low-scoring,
    out-of-dictionary detections before they ever reach the engine layer,
    so a page can end with a normal-looking (even high) confidence over
    the handful of detections that DID survive -- e.g. only a page
    number -- while nearly all of the page's actual text silently
    vanished. Confidence alone cannot see this; it never observes what
    got dropped.
    """
    if not ink_component_count or ink_component_count < _LOW_YIELD_MIN_INK_COMPONENTS:
        return False
    if ink_component_count > _LOW_YIELD_MAX_TRUSTED_INK_COMPONENTS:
        return False
    return total_chars <= max(
        _LOW_YIELD_MAX_CHARS_ABS, _LOW_YIELD_MAX_CHARS_RATIO * ink_component_count
    )


class RapidOCREngine(BaseOCREngine):
    """Adapter for RapidOCR ONNX engine."""

    def __init__(self):
        self._engine = None
        self._arabic_engine = None

    def _wants_rtl_script(self, languages: Optional[List[str]] = None) -> bool:
        # `languages`, when given, is a per-call override (e.g. a per-job
        # language list threaded down from JobConfig) that takes
        # precedence over the process-global `config.ocr_languages` --
        # deliberately NOT read from a mutated global, since a shared
        # engine instance can serve concurrent jobs with different
        # language requirements (see blast_ocr.core.router's
        # apply_auto_routing docstring for the cross-job leakage this
        # avoids).
        langs = languages if languages is not None else config.ocr_languages
        return any(lang in RTL_SCRIPT_LANGUAGES for lang in langs)

    def _warn_if_unsupported_language(self, languages: Optional[List[str]] = None) -> None:
        langs = languages if languages is not None else config.ocr_languages
        unsupported = [lang for lang in langs if lang not in _SUPPORTED_LANGUAGES]
        if unsupported:
            logger.warning(
                "OCR language(s) %s requested but not supported by the "
                "'rapidocr' engine's models -- text in that script will come "
                "back empty or garbage. Use ocr_engine='easyocr' for this "
                "language instead.",
                unsupported,
            )

    def _init_engine(self):
        if self._engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._engine = RapidOCR()
            except Exception as e:
                logger.error(f"Failed to initialize RapidOCR engine: {e}")
                raise RuntimeError(f"RapidOCR initialization failed: {e}") from e

    def _init_arabic_engine(self):
        if self._arabic_engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                rec_model_path, rec_keys_path = ensure_arabic_model()
                self._arabic_engine = RapidOCR(
                    rec_model_path=rec_model_path, rec_keys_path=rec_keys_path
                )
            except ArabicModelUnavailableError:
                raise
            except Exception as e:
                logger.error(f"Failed to initialize Arabic-script RapidOCR engine: {e}")
                raise RuntimeError(
                    f"Arabic-script RapidOCR initialization failed: {e}"
                ) from e

    def _active_engine(self, languages: Optional[List[str]] = None):
        self._warn_if_unsupported_language(languages)
        if self._wants_rtl_script(languages):
            self._init_arabic_engine()
            return self._arabic_engine
        self._init_engine()
        return self._engine

    def _fallback_engine(self, primary_is_rtl: bool) -> Tuple[Any, bool]:
        """
        Lazily initialize and return the OPPOSITE recognition model from
        the one `process_page` just used, for the low-yield script-
        mismatch retry. Raises ArabicModelUnavailableError (propagated to
        the caller, which handles it as a soft failure) if the Arabic
        model can't be reached and the primary pass used the default
        model.
        """
        if primary_is_rtl:
            self._init_engine()
            return self._engine, False
        self._init_arabic_engine()
        return self._arabic_engine, True

    @staticmethod
    def _recognize_pass(engine, img, is_rtl: bool) -> Dict[str, Any]:
        """Run one detection+recognition pass with the given RapidOCR
        instance and return its structured detections plus yield stats."""
        raw_output, _ = engine(img)

        raw_detections = []
        text_parts = []
        confidences = []
        char_counts = []
        formatted_details = []

        if raw_output:
            for item in raw_output:
                if not item or len(item) < 3:
                    continue
                bbox_points, text, conf = item[0], str(item[1]).strip(), float(item[2])
                if not text:
                    continue
                if is_rtl and contains_rtl_script(text):
                    # The Arabic-script recognition model emits each line in
                    # raw left-to-right pixel/visual order (a CTC decoding
                    # artifact of the underlying CRNN, not a logical reading
                    # order) -- reordering restores correct RTL reading
                    # order while leaving any embedded Latin/digit run (page
                    # numbers, footnote markers, or an English word/number
                    # embedded mid-line) in its own already-correct order.
                    text = reorder_rtl_visual_to_logical(text)

                raw_detections.append({
                    "text": text,
                    "confidence": conf,
                    "bbox": bbox_points,
                })
                text_parts.append(text)
                confidences.append(conf)
                char_counts.append(len(text))

                # Flat bbox points [x1,y1, x2,y1, x2,y2, x1,y2]
                flat_bbox = [int(c) for pt in bbox_points for c in pt] if isinstance(bbox_points, (list, tuple)) else []
                formatted_details.append({
                    "text": text,
                    "conf": conf,
                    "bbox": flat_bbox,
                })

        return {
            "raw_detections": raw_detections,
            "text_parts": text_parts,
            "confidences": confidences,
            "char_counts": char_counts,
            "formatted_details": formatted_details,
            "total_chars": sum(char_counts),
        }

    @property
    def engine_name(self) -> str:
        return "rapidocr"

    def metadata(self) -> Dict[str, Any]:
        # Derived from live config rather than a cached flag from the last
        # process_page() call, so a caller reading metadata() before the
        # first page (e.g. for job provenance at enqueue time) still sees
        # which model will actually be used.
        if self._wants_rtl_script():
            return {
                "engine": self.engine_name,
                "backend": "onnxruntime",
                "device": "cpu",
                "model_detection": "ch_PP-OCRv4_det",
                "model_recognition": "arabic_PP-OCRv5_rec",
            }
        return {
            "engine": self.engine_name,
            "backend": "onnxruntime",
            "device": "cpu",
            "model_detection": "ch_PP-OCRv4_det",
            "model_recognition": "ch_PP-OCRv4_rec",
        }

    def process_page(
        self,
        image_path: str,
        page_number: int,
        glyph_height: Optional[float] = None,
        languages: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        is_rtl = self._wants_rtl_script(languages)
        engine = self._active_engine(languages)

        start_time = time.monotonic()
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not load image at {image_path}")

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

        # Single connected-component pass yields both the glyph-height
        # estimate (for layout sizing) and the ink-coverage signal (for
        # script-mismatch detection below) -- see estimate_page_text_signal.
        page_signal = estimate_page_text_signal(gray)
        eff_glyph_height = glyph_height or (page_signal[0] if page_signal else None) or 24.0
        ink_component_count = page_signal[1] if page_signal else None

        # RapidOCR returns tuple (result, elapse); result shape:
        # [[bbox, text, score], ...]
        pass_result = self._recognize_pass(engine, img, is_rtl)

        script_fallback_applied = False
        script_fallback_error: Optional[str] = None

        if _is_low_yield(pass_result["total_chars"], ink_component_count):
            try:
                fallback_engine, fallback_is_rtl = self._fallback_engine(is_rtl)
                fallback_result = self._recognize_pass(fallback_engine, img, fallback_is_rtl)
                if fallback_result["total_chars"] > pass_result["total_chars"]:
                    logger.info(
                        "Page %d: primary recognition yielded only %d chars despite "
                        "~%d glyph-shaped components detected on the page -- retrying "
                        "with the %s recognition model recovered %d chars instead.",
                        page_number,
                        pass_result["total_chars"],
                        ink_component_count or 0,
                        "Arabic-script" if fallback_is_rtl else "default",
                        fallback_result["total_chars"],
                    )
                    pass_result = fallback_result
                    is_rtl = fallback_is_rtl
                    script_fallback_applied = True
            except ArabicModelUnavailableError as e:
                script_fallback_error = str(e)
                logger.warning(
                    "Page %d: possible script mismatch (%d glyph-shaped components "
                    "detected, only %d chars recognized) but the Arabic-script "
                    "fallback model is unavailable -- %s",
                    page_number, ink_component_count or 0, pass_result["total_chars"], e,
                )
            except Exception as e:
                script_fallback_error = str(e)
                logger.warning(
                    "Page %d: script-mismatch fallback attempt failed: %s", page_number, e
                )

        raw_detections = pass_result["raw_detections"]
        text_parts = pass_result["text_parts"]
        confidences = pass_result["confidences"]
        char_counts = pass_result["char_counts"]
        formatted_details = pass_result["formatted_details"]
        total_chars = pass_result["total_chars"]

        # Process layout
        layout_engine = LayoutEngine()
        layout_page = layout_engine.process_page_detections(
            raw_detections=raw_detections,
            page_num=page_number,
            width=w,
            height=h,
            glyph_height=eff_glyph_height,
        )

        extracted_text = layout_page.text if layout_page.text.strip() else " ".join(text_parts)

        if total_chars > 0:
            avg_confidence = sum(c * n for c, n in zip(confidences, char_counts)) / total_chars
        else:
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        elapsed = time.monotonic() - start_time

        result = {
            "page": page_number,
            "text": extracted_text,
            "confidence": avg_confidence,
            "bbox_count": len(raw_detections),
            "details": formatted_details,
            "page_model": layout_page.model_dump(),
            "processing_time": elapsed,
            "engine": self.engine_name,
        }
        if ink_component_count is not None:
            result["ink_component_count"] = ink_component_count
        if script_fallback_applied:
            result["script_fallback_applied"] = True
        if script_fallback_error:
            result["script_fallback_error"] = script_fallback_error
        return result
