from typing import Dict, Optional, Union
from pathlib import Path
import logging
import cv2
import numpy as np
import os
import sys
import threading
from pptx import Presentation  # noqa: F401 -- re-exported; tests monkeypatch this module path
from docx import Document  # noqa: F401 -- re-exported; tests monkeypatch this module path

# FIX(cloud): Redirect EasyOCR model cache to /tmp on Linux (Streamlit Cloud).
# On cloud, the home dir (/home/appuser) may not have a writable .EasyOCR dir.
# Setting this env var BEFORE importing easyocr tells it where to store models.
if sys.platform != "win32":
    _easyocr_model_dir = "/tmp/.EasyOCR/model"
    os.makedirs(_easyocr_model_dir, exist_ok=True)
    os.environ.setdefault("EASYOCR_MODULE_PATH", "/tmp/.EasyOCR")

import defusedxml

defusedxml.defuse_stdlib()

from blast_ocr.config import config
from blast_ocr.core.exceptions import (
    ImageLoadError,
    OCREngineError,
    PageExtractionError,
)
from blast_ocr.core.healing import healer
from blast_ocr.core.exporter import save_output, sanitize_for_xml, extract_from_pptx
from blast_ocr.core.page_signal import estimate_glyph_height

logger = logging.getLogger(__name__)

# FIX(phase2): HIGH-001 - Module-level global lock for EasyOCR thread safety.
# The architecture doc specifies a GLOBAL lock, but the original code created
# a per-instance lock (self.lock = threading.Lock() in __init__). This meant
# multiple RobustOCRExtractor instances would have separate locks, allowing
# race conditions. Now all instances share this single global lock.
_ocr_global_lock = threading.Lock()


def get_cache_namespace(engine_name: str = "easyocr") -> str:
    """Fingerprint of everything besides raw file bytes that can change what
    OCR produces for a given image: engine identity/version, GPU/quantization
    mode, languages, and the preprocessing knobs applied before pixels reach
    the engine. See FIX(F-07) in blast_ocr.cache.manager.OCRCache.get_cache_key
    -- cache entries are keyed on file content combined with this namespace so
    changing any of these can never silently serve a stale answer.
    """
    try:
        from importlib.metadata import version as _pkg_version

        pkg_map = {"easyocr": "easyocr", "rapidocr": "rapidocr_onnxruntime"}
        pkg_name = pkg_map.get(engine_name.lower(), engine_name.lower())
        engine_version = _pkg_version(pkg_name)
    except Exception:
        engine_version = "unknown"

    parts = [
        engine_name.lower(),
        engine_version,
        f"gpu={bool(config.ocr_gpu)}",
        f"quantize={not bool(config.ocr_gpu)}",
        f"langs={','.join(sorted(config.ocr_languages))}",
        f"denoise={config.denoise_level}",
        f"contrast={config.contrast_boost}",
        f"deskew={config.auto_deskew}",
    ]
    return "|".join(parts)


class RobustOCRExtractor:
    """
    Robust OCR text extraction engine with self-healing capabilities.
    """

    def __init__(self):
        """Initialize OCR engine with config settings"""
        self.reader = None
        # FIX(phase2): HIGH-001 - Use the module-level global lock instead of per-instance
        self.lock = _ocr_global_lock
        self._init_engine()

    @healer.retry_with_backoff
    def _init_engine(self):
        """Initialize EasyOCR with retry logic"""
        try:
            import easyocr

            download_flag = os.getenv("BLAST_OCR_EASYOCR_DOWNLOAD_ENABLED", "1")
            download_enabled = download_flag.strip().lower() not in {
                "0",
                "false",
                "no",
                "off",
            }
            model_storage_directory = os.getenv("BLAST_OCR_EASYOCR_MODEL_DIR")
            if not model_storage_directory and sys.platform != "win32":
                module_path = os.getenv("EASYOCR_MODULE_PATH", "/tmp/.EasyOCR")
                clean_module_path = module_path.rstrip("/\\")
                model_storage_directory = f"{clean_module_path}/model"

            logger.info(
                f"Initializing EasyOCR (GPU={config.ocr_gpu}, Langs={config.ocr_languages})"
            )
            self.reader = easyocr.Reader(
                config.ocr_languages,
                gpu=config.ocr_gpu,
                verbose=False,
                quantize=not bool(config.ocr_gpu),
                model_storage_directory=model_storage_directory,
                download_enabled=download_enabled,
            )
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {e}")
            raise OCREngineError(f"Engine init failed: {e}")

    def load_image(self, image_path: str) -> np.ndarray:
        """Load and validate image file"""
        if not Path(image_path).exists():
            raise ImageLoadError(f"File not found: {image_path}")

        try:
            # Load using CV2
            with open(image_path, "rb") as f:
                file_bytes = f.read()
            img = cv2.imdecode(
                np.frombuffer(file_bytes, dtype=np.uint8), cv2.IMREAD_COLOR
            )
            if img is None:
                raise ImageLoadError("cv2.imdecode returned None")

            # CRITICAL FIX: Validate dimensions to prevent C-level access violations
            # EasyOCR/OpenCV can crash on 0x0 or extremely small images on Windows
            if img.shape[0] < 2 or img.shape[1] < 2:
                raise ImageLoadError(
                    f"Image too small for OCR ({img.shape[1]}x{img.shape[0]})"
                )

            return img
        except Exception as e:
            if isinstance(e, ImageLoadError):
                raise
            raise ImageLoadError(f"Failed to load image: {e}") from e

    # FIX(phase1/F-02): Target glyph height, not a fixed output width.
    # 20-30px x-height is the documented sweet spot for CRNN-style text
    # recognizers; below ~20px accuracy measurably degrades. A fixed
    # target *width* conflates page physical size with scan DPI -- an A5
    # page and a folio need different scale factors to put the same-size
    # text at the same pixel height.
    #
    # FIX(phase1 follow-up): this used to *always* rescale to exactly
    # TARGET_GLYPH_HEIGHT_PX, which meant a page whose glyphs already
    # measured, say, 23px -- already inside the effective range -- still
    # got upscaled ~1.1x with interpolated pixels carrying no new
    # information, for no benefit. Measured directly against this
    # project's own gold corpus: full-corpus CER got *worse* (0.499 ->
    # 0.525) after that change, specifically on pages whose glyph height
    # was already adequate. The threshold framing below (only upscale
    # when below the floor) is what the underlying research actually
    # supports; always-hit-exact-target was an implementation
    # overcorrection past what the evidence justified. See
    # docs/adr/0003-phase1-preprocessing-fixes.md.
    MIN_ACCEPTABLE_GLYPH_HEIGHT_PX = 20.0
    TARGET_GLYPH_HEIGHT_PX = 26.0
    # Absolute backstop against pathological inputs (corrupt/huge scans),
    # not the primary quality control. Real book-page renders at 300 DPI
    # measured 2900-3300px on the long edge in this project's own gold
    # corpus; 4500px leaves headroom for higher-DPI or larger-format scans
    # without this cap being what determines normal-case output quality
    # the way the old fixed 1800px cap was.
    MAX_LONG_EDGE_PX = 4500

    @staticmethod
    def _estimate_glyph_height(gray: np.ndarray) -> Optional[float]:
        """Thin wrapper over blast_ocr.core.page_signal.estimate_glyph_height,
        kept on the class because existing call sites (this module's own
        preprocess_image, and the test suite) already address it as
        RobustOCRExtractor._estimate_glyph_height / self._estimate_....
        The restoration layer needs the same signal *before* CLAHE runs
        (see page_signal's docstring), so the actual implementation lives
        in a module neither extractor.py nor restoration.py has to import
        from the other to reach."""
        return estimate_glyph_height(gray)

    @staticmethod
    def _estimate_skew_angle(
        gray: np.ndarray,
        max_angle: float = 6.0,
        coarse_step: float = 1.0,
        fine_step: float = 0.1,
    ) -> float:
        """
        Projection-profile skew estimation: rotate the binarized page over
        a small angle range and pick the angle whose row-wise ink
        projection has maximum variance (sharpest text-line peaks = best
        alignment). Two-pass (coarse then fine) for speed.

        Replaces a prior minAreaRect-based estimate, which took the
        minimum bounding rectangle over every foreground pixel on the
        page -- dominated by whichever content (often margins/binding
        shadow, not text baselines) happened to define that rectangle,
        which is why that approach needed a hard >=10 degree "ignore, this
        is probably gibberish" escape hatch and still frequently hit it on
        genuinely flat pages. A projection-profile search directly
        measures what deskewing is meant to optimize -- text lines
        forming sharp horizontal bands -- so it doesn't need that escape
        hatch: a flat page simply scores best at angle 0.

        Runs on a downscaled copy (skew angle doesn't need full
        resolution) purely for speed.
        """
        h, w = gray.shape[:2]
        scale = min(1.0, 800.0 / max(h, w, 1))
        small = (
            cv2.resize(gray, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
            if scale < 1.0
            else gray
        )

        _, thresh = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        sh, sw = thresh.shape[:2]
        center = (sw // 2, sh // 2)

        def projection_variance(angle: float) -> float:
            if angle == 0.0:
                rotated = thresh
            else:
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(
                    thresh,
                    M,
                    (sw, sh),
                    flags=cv2.INTER_NEAREST,
                    borderMode=cv2.BORDER_CONSTANT,
                    borderValue=0,
                )
            row_sums = rotated.sum(axis=1)
            return float(np.var(row_sums))

        best_angle = 0.0
        best_score = projection_variance(0.0)

        angle = -max_angle
        while angle <= max_angle + 1e-9:
            if angle != 0.0:
                score = projection_variance(angle)
                if score > best_score:
                    best_score, best_angle = score, angle
            angle += coarse_step

        fine_lo, fine_hi = best_angle - coarse_step, best_angle + coarse_step
        angle = fine_lo
        while angle <= fine_hi + 1e-9:
            score = projection_variance(angle)
            if score > best_score:
                best_score, best_angle = score, angle
            angle += fine_step

        return best_angle

    def preprocess_image(
        self, image_source: Union[str, np.ndarray], target_width=2000
    ) -> np.ndarray:
        """
        Apply adaptive preprocessing to improve OCR accuracy.
        Accepts file path or numpy array. Returns numpy array.

        `target_width` is kept as a parameter for backward compatibility
        with existing callers, and is used only as the fallback scale
        target when glyph-height estimation has no usable signal (e.g. a
        blank page) -- it is no longer the primary resize control.
        """
        image = None
        try:
            if isinstance(image_source, str):
                # Use load_image for robust loading from path
                image = self.load_image(image_source)
            else:
                image = image_source

            # 1. Gray
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()

            # 2. Denoise (Conditional manual override -- see also the
            # automatic, noise-estimate-gated pass in
            # ForensicRestorer.restore(), which runs earlier in the
            # production pipeline. This knob stays available for a user
            # to explicitly ask for *more* denoising via the UI's Noise
            # Reduction slider on a scan that's still difficult after the
            # automatic pass.)
            # FIX(phase4): Use config value
            if config.denoise_level > 0:
                h_val = float(config.denoise_level)
                gray = cv2.fastNlMeansDenoising(
                    gray, None, h=h_val, templateWindowSize=7, searchWindowSize=21
                )

            # 3. Estimate text-line signal strength once, shared by both
            # deskew and resize below.
            # FIX(phase1 follow-up/F-09b): a page with no reliable
            # glyph-height signal (near-blank, or texture with no real text
            # -- e.g. a photographed cloth book cover) has no text lines to
            # measure a skew angle *from* either, and applying a
            # projection-profile deskew "correction" anyway was measured to
            # actively destroy the one real content region. On this
            # project's own photographed-cover gold page the estimator
            # confidently reported -7.0 degrees of skew from cloth-weave
            # texture alone; "correcting" that non-existent skew drove that
            # page's CER from 0.41 to 0.80 and accounted for nearly the
            # entire full-corpus regression this fix resolves (see
            # docs/adr/0003). Reuse the same signal the resize decision
            # already needs, computed once before either runs.
            glyph_height = self._estimate_glyph_height(gray)
            self._last_glyph_height = glyph_height

            # 4. Deskew -- only when there's real text-line signal to trust.
            # FIX(phase1/F-09): projection-profile search, replacing a
            # minAreaRect estimate that was dominated by non-text content
            # and needed a hard escape hatch for angles near 90 degrees on
            # otherwise-flat pages. See _estimate_skew_angle docstring.
            if config.auto_deskew and glyph_height:
                angle = self._estimate_skew_angle(gray)
                if 0.3 < abs(angle) < 10.0:
                    logger.info(f"Correcting deskew: {angle:.2f} degrees")
                    (h, w) = gray.shape
                    center = (w // 2, h // 2)
                    M = cv2.getRotationMatrix2D(center, angle, 1.0)
                    gray = cv2.warpAffine(
                        gray,
                        M,
                        (w, h),
                        flags=cv2.INTER_CUBIC,
                        borderMode=cv2.BORDER_REPLICATE,
                    )
                elif abs(angle) >= 10.0:
                    logger.warning(
                        f"Implausibly large skew estimate ({angle:.2f}°), ignoring."
                    )

            # 5. Resize -- target a glyph height the recognizer is trained
            # for, not a fixed output width.
            # FIX(phase1/F-02): the old logic capped the source image at
            # 1800px *before* this method ever saw it, then unconditionally
            # upscaled anything under 2000px wide back up with INTER_CUBIC --
            # a downscale-then-upscale round trip that discarded real
            # resolution and replaced it with interpolated pixels carrying
            # no new information. That early cap is gone (see process_page);
            # this is now the only resize decision, made with the full
            # source resolution available.
            h, w = gray.shape
            if glyph_height and glyph_height > 0:
                if glyph_height < self.MIN_ACCEPTABLE_GLYPH_HEIGHT_PX:
                    # Genuinely too small for reliable recognition -- scale
                    # up to the target. Below this floor is where the
                    # underlying research shows accuracy actually degrades.
                    scale = self.TARGET_GLYPH_HEIGHT_PX / glyph_height
                    # Don't let a noisy estimate produce an extreme factor.
                    scale = max(0.3, min(scale, 4.0))
                else:
                    # Already adequate -- leave it alone. Upscaling here
                    # would add interpolated pixels with no new
                    # information, not real detail.
                    scale = 1.0
            else:
                # No reliable glyph estimate (e.g. a blank/near-blank
                # page) -- fall back to scaling images toward target_width to
                # prevent OOM on oversized non-text pages while maintaining minimum width.
                scale = target_width / float(w) if w != target_width else 1.0

            # Safety backstop: never exceed MAX_LONG_EDGE_PX regardless of
            # what the glyph-height target requested.
            projected_long_edge = max(h, w) * scale
            if projected_long_edge > self.MAX_LONG_EDGE_PX:
                scale *= self.MAX_LONG_EDGE_PX / projected_long_edge

            if abs(scale - 1.0) > 0.02:  # skip a no-op resize
                new_w, new_h = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
                # OpenCV's own documented guidance: INTER_AREA for
                # shrinking, INTER_CUBIC for enlarging.
                interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
                gray = cv2.resize(gray, (new_w, new_h), interpolation=interp)

            # 6. Adaptive Threshold / Contrast Boost
            if config.contrast_boost != 1.0:
                # alpha = contrast (1.0-3.0), beta = brightness (0)
                gray = cv2.convertScaleAbs(gray, alpha=config.contrast_boost, beta=0)

            return gray

        except Exception as e:
            # BUG-FIX-01: Correctly use image_source/image and avoid re-loading failure
            # If load_image failed (image is None), then we must raise.
            if image is None:
                raise

            logger.warning(f"Preprocessing failed: {e}. Falling back to grayscale.")
            try:
                if len(image.shape) == 3:
                    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                return image.copy()
            except Exception as inner_e:
                logger.error(f"Fallback preprocessing failed: {inner_e}")
                # Ultimate fallback - return as-is
                return image

    @healer.retry_with_backoff
    def process_page(self, page_path: str, page_number: int) -> Dict:
        """Process single page with comprehensive error handling"""
        try:
            logger.debug(f"Processing page {page_number}: {page_path}")

            # 1. Load
            image = self.load_image(page_path)

            # --- MEMORY SAFETY BACKSTOP ---
            # FIX(phase1/F-02): this used to unconditionally cap every page
            # at 1800px *before* any quality decision was made, then
            # preprocess_image would upscale small results back toward
            # 2000px -- a downscale-then-upscale round trip that threw away
            # real resolution and replaced it with interpolated pixels.
            # That's gone: preprocess_image now makes the one resize
            # decision, targeting a glyph height the recognizer is trained
            # for using the full source resolution. This check is now only
            # a generous backstop against truly pathological inputs (a
            # corrupt or absurdly high-resolution file), using the same
            # MAX_LONG_EDGE_PX ceiling preprocess_image itself respects, so
            # it never fires on a normal book-page scan.
            if image is not None:
                height, width = image.shape[:2]
                max_dim = self.MAX_LONG_EDGE_PX
                if height > max_dim or width > max_dim:
                    logger.info(
                        f"Downscaling oversized image ({width}x{height}) to max {max_dim}px for stability"
                    )
                    scale = max_dim / max(height, width)
                    new_width = max(1, int(width * scale))
                    new_height = max(1, int(height * scale))
                    image = cv2.resize(
                        image, (new_width, new_height), interpolation=cv2.INTER_AREA
                    )

            # 2. Preprocess
            processed_img = self.preprocess_image(image)
            img_h, img_w = processed_img.shape[:2]

            # 3. OCR
            raw_results = None
            try:
                # detail=1 returns [bbox, text, conf]
                with self.lock:
                    try:
                        import torch

                        with torch.inference_mode():
                            raw_results = self.reader.readtext(processed_img, detail=1)
                    except (ImportError, OSError, NameError):
                        raw_results = self.reader.readtext(processed_img, detail=1)

            except Exception as e:
                raise OCREngineError(f"OCR processing failed: {e}")
            finally:
                # FIX(phase2-MEM-001): Explicit cleanup to prevent RAM accumulation
                # Run on both success and failure paths.
                if "processed_img" in locals():
                    del processed_img
                if "image" in locals():
                    del image

                # Force garbage collection to reclaim memory immediately
                import gc

                gc.collect()

                # PERF(phase2): Clear GPU memory after each page to prevent VRAM accumulation
                try:
                    import torch

                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except (ImportError, OSError, NameError):
                    pass

            # 4. Extract & Validate
            if not raw_results:
                logger.warning(f"Page {page_number}: No text detected")
                return {
                    "page": page_number,
                    "text": "",
                    "confidence": 0.0,
                    "bbox_count": 0,
                    "warning": "no_text_detected",
                }

            text_parts = [item[1] for item in raw_results]

            def _confidence_to_float(value) -> float:
                # BUG-VRAM-AUTOGRAD-01: Explicitly break autograd graph before storing.
                if hasattr(value, "detach"):
                    value = value.detach()
                if hasattr(value, "item"):
                    value = value.item()
                return float(value)

            # Phase 2 Layout Analysis: reconstruct reading order and block layout
            from blast_ocr.core.layout import LayoutEngine
            layout_engine = LayoutEngine()
            estimated_gh = getattr(self, "_last_glyph_height", None)
            layout_page = layout_engine.process_page_detections(
                raw_detections=[
                    {
                        "text": item[1],
                        "confidence": _confidence_to_float(item[2]),
                        "bbox": item[0],
                    }
                    for item in raw_results
                ],
                page_num=page_number,
                width=img_w,
                height=img_h,
                glyph_height=estimated_gh,
            )

            extracted_text = layout_page.text if layout_page.text.strip() else " ".join(text_parts)

            # FIX(phase1/F-08): character-count-weighted confidence, not a
            # plain per-box mean. An unweighted mean lets a handful of
            # low-confidence single-character specks (stray marks, noise)
            # drag a page of otherwise-clean prose below the reflexion
            # threshold and trigger a full second OCR pass for no real
            # quality reason; weighting by how much text each box actually
            # carries makes the aggregate track what's really on the page.
            confidences = [_confidence_to_float(item[2]) for item in raw_results]
            char_counts = [len(t) for t in text_parts]
            total_chars = sum(char_counts)
            if total_chars > 0:
                avg_confidence = (
                    sum(c * n for c, n in zip(confidences, char_counts)) / total_chars
                )
            else:
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            # Format details for UI: [{'text': t, 'conf': c, 'bbox': b}, ...]
            formatted_details = [
                {
                    "text": item[1],
                    "conf": _confidence_to_float(item[2]),
                    "bbox": [int(c) for point in item[0] for c in point],
                }
                for item in raw_results
            ]

            result = {
                "page": page_number,
                "text": extracted_text,
                "confidence": avg_confidence,
                "bbox_count": len(raw_results),
                "details": formatted_details,
                "page_model": layout_page.model_dump(),
            }

            # Quality check
            if avg_confidence < config.min_confidence:
                logger.warning(
                    f"Page {page_number} low confidence: {avg_confidence:.2f}"
                )
                result["warning"] = "low_confidence"

            return result

        except (ImageLoadError, OCREngineError) as e:
            logger.error(f"Page {page_number}: Fatal error - {e}")
            # Don't wrap if it's already a clean error, but adding context is good.
            raise PageExtractionError(page_number, e)
        except Exception as e:
            logger.error(f"Page {page_number}: Unexpected error - {e}")
            raise PageExtractionError(page_number, e)

# Re-exported utilities from blast_ocr.core.exporter for backward compatibility
__all__ = [
    "RobustOCRExtractor",
    "extract_from_pptx",
    "sanitize_for_xml",
    "save_output",
    "_ocr_global_lock",
    "get_cache_namespace",
]
