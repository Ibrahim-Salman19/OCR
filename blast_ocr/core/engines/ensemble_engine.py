"""
blast_ocr.core.engines.ensemble_engine

Consensus Ensemble OCR Engine Adapter.
Combines fast primary extraction (RapidOCR) with secondary validation
(EasyOCR), cross-checking every page rather than gating on either engine's
own self-reported confidence -- see the note in process_page for why that
gate was removed.
"""

from typing import Dict, Any, List, Optional
import difflib
import time
import logging

from blast_ocr.core.engines.base import BaseOCREngine
from blast_ocr.core.engines.rapidocr_engine import RapidOCREngine
from blast_ocr.core.engines.easyocr_engine import EasyOCREngine

logger = logging.getLogger(__name__)

# Below this normalized text-similarity ratio between the two engines'
# outputs, the page is flagged as a disagreement (see process_page). Set
# wide/conservative (only substantial disagreement trips it) because this
# constant is NOT empirically calibrated the way the RapidOCR script-
# mismatch ink-ratio threshold was (blast_ocr.core.engines.rapidocr_engine
# ._LOW_YIELD_MAX_CHARS_RATIO, calibrated against real measured pages):
# calibrating this one the same way would require running EasyOCR against
# this project's real gold-corpus page images, which are large
# (2916x2334) and OOM-killed a from-scratch EasyOCR model load in this
# project's own dev sandbox (~7.6GB RAM). Treat this as a coarse,
# conservative signal -- worth tightening once real cross-engine
# measurements are available -- not a precisely-tuned one.
DISAGREEMENT_SIMILARITY_THRESHOLD = 0.5


class ConsensusEnsembleEngine(BaseOCREngine):
    """Ensemble OCR engine providing multi-engine consensus and voting."""

    def __init__(self, high_confidence_threshold: float = 0.85):
        # Retained for API/metadata compatibility; no longer used to gate
        # whether the secondary engine runs (see process_page).
        self.high_confidence_threshold = high_confidence_threshold
        self._primary = RapidOCREngine()
        self._secondary = None

    @property
    def engine_name(self) -> str:
        return "ensemble"

    def metadata(self) -> Dict[str, Any]:
        return {
            "engine": self.engine_name,
            "primary": self._primary.engine_name,
            "secondary": "easyocr",
            "confidence_threshold": self.high_confidence_threshold,
        }

    def process_page(
        self,
        image_path: str,
        page_number: int,
        glyph_height: Optional[float] = None,
        languages: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        start_time = time.monotonic()

        # 1. Run primary fast engine
        primary_res = self._primary.process_page(
            image_path, page_number, glyph_height, languages=languages
        )
        primary_conf = primary_res.get("confidence", 0.0)
        # A suspected-but-unresolved script mismatch (RapidOCREngine's own
        # ink-coverage fallback tried and failed, e.g. offline) can still
        # carry a normal-looking confidence -- the reported bug's exact
        # shape, only a page number recognized at high confidence while
        # the rest of the page's text silently vanished.
        suspected_mismatch = bool(primary_res.get("script_fallback_error"))

        # 2. ALWAYS cross-check against the secondary engine -- this used
        # to be gated on `primary_conf < high_confidence_threshold`, which
        # sounds reasonable but is empirically broken: measured against
        # this project's own 14-page English gold corpus (eval/run.py,
        # 2026-09-03), RapidOCR's char-weighted confidence sat in a narrow
        # 0.91-0.96 band on EVERY page regardless of actual accuracy --
        # including pages that scored 46-67% CER (i.e. mostly wrong). A
        # hard structural page (a photographed cover, an index page, a
        # near-blank page with a hand-drawn annotation) confidently
        # recognizes the small amount of text it DOES attempt while
        # missing most of the page's real content, and a per-character
        # confidence score has no way to see what it never attempted --
        # the same blind spot _is_low_yield's ink-coverage signal targets
        # for the *script*-mismatch case specifically, but confidence
        # itself is simply not a general reliability signal, and gating
        # the one mechanism meant to catch that (a second, independently
        # architected and trained engine) on that same unreliable signal
        # meant it essentially never fired on exactly the pages that
        # needed it. Always cross-checking costs real latency (EasyOCR is
        # markedly slower than RapidOCR), which is the accepted tradeoff
        # for selecting this engine specifically.
        logger.info(
            f"Page {page_number}: cross-checking primary result "
            f"(confidence={primary_conf:.2f}"
            f"{', suspected script mismatch' if suspected_mismatch else ''}) "
            "against secondary engine (EasyOCR)."
        )
        if self._secondary is None:
            self._secondary = EasyOCREngine()

        try:
            sec_res = self._secondary.process_page(image_path, page_number, glyph_height)
            sec_conf = sec_res.get("confidence", 0.0)
            primary_text = str(primary_res.get("text", "") or "")
            sec_text = str(sec_res.get("text", "") or "")

            # A suspected mismatch on the primary side makes its confidence
            # score unreliable as a comparison basis -- prefer the
            # secondary result as long as it actually produced something,
            # rather than risk re-picking the very result whose
            # credibility is already in question. If the secondary also
            # came back empty, fall through to the normal
            # higher-confidence-wins comparison instead of discarding a
            # non-empty primary result for nothing.
            secondary_has_content = bool(sec_text.strip())
            if (suspected_mismatch and secondary_has_content) or sec_conf > primary_conf:
                chosen = sec_res
                chosen["engine"] = f"{self.engine_name} (easyocr_selected, conf={sec_conf:.2f})"
            else:
                chosen = primary_res
                chosen["engine"] = f"{self.engine_name} (rapidocr_selected, conf={primary_conf:.2f})"
            chosen["processing_time"] = time.monotonic() - start_time

            # Surface disagreement regardless of which side was chosen --
            # "no silent low quality": two independently-architected
            # engines substantially disagreeing on the same page means at
            # least one of them is wrong, which is worth flagging even
            # when the CHOSEN result's own confidence looks normal.
            if primary_text.strip() or sec_text.strip():
                similarity = difflib.SequenceMatcher(None, primary_text, sec_text).ratio()
                if similarity < DISAGREEMENT_SIMILARITY_THRESHOLD:
                    chosen["engine_disagreement"] = True
                    chosen["engine_agreement_ratio"] = round(similarity, 3)
                    logger.warning(
                        f"Page {page_number}: primary and secondary engines disagree "
                        f"substantially (text similarity={similarity:.2f}) -- result may "
                        "be unreliable despite a normal-looking confidence score."
                    )

            return chosen

        except Exception as sec_err:
            logger.warning(f"Ensemble secondary engine failed: {sec_err}, using primary result.")
            primary_res["engine"] = f"{self.engine_name} (primary_fallback)"
            return primary_res
