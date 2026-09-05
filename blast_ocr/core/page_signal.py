"""
Shared page-content signal estimation.

Used by both the restoration layer (`blast_ocr.core.restoration` -- to
decide whether contrast/denoise operations have real content to act on)
and the extractor's preprocessing stage (`blast_ocr.core.extractor` -- to
decide resize/deskew targets). Kept as an independent module so neither of
those has to import the other: restoration must be able to gate CLAHE
*before* the extractor ever sees the image, using the same signal the
extractor later uses to gate deskew.
"""

from typing import Optional, Tuple

import cv2
import numpy as np

# Below this many accepted glyph-shaped components, the connected-component
# signal isn't trusted for anything (height estimate OR ink-coverage
# comparison) -- shared by every function below so their "not enough
# signal" cutoffs stay in lockstep.
_MIN_TRUSTED_COMPONENTS = 20


def _glyph_like_components(gray: np.ndarray) -> Optional[np.ndarray]:
    """
    Connected-component analysis over the RAW (pre-enhancement) page,
    filtered down to components shaped like individual glyphs. Shared by
    `estimate_glyph_height` (needs the height distribution) and
    `estimate_text_ink_signal` (needs the count/area) so both stay
    consistent with a single filter definition instead of drifting apart.

    Returns the accepted rows of `cv2.connectedComponentsWithStats`'
    stats array (each row: [x, y, w, h, area]), or None when there isn't
    enough signal to trust the result (e.g. a blank/near-blank page, or a
    page with no real text at all).

    Deliberately run on the RAW page, before any contrast enhancement:
    CLAHE applied ahead of this check can amplify subtle background
    texture (e.g. a photographed cloth book cover) into thousands of
    small, glyph-sized-and-shaped connected components that pass every
    filter below despite carrying no real text -- see
    docs/adr/0003-phase1-preprocessing-fixes.md for the full incident.
    Measuring on the raw scan avoids that false signal entirely; on this
    project's own 14-page gold corpus, every genuine text page (even a
    near-blank one with only a marginalia annotation) produces a valid
    estimate on the raw image, while the one texture-only page (a
    photographed cover) correctly returns None.
    """
    try:
        _, thresh = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )
        num_labels, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
            thresh, connectivity=8
        )
        if num_labels <= 1:
            return None

        img_h, img_w = gray.shape[:2]
        accepted = []
        for i in range(1, num_labels):
            h = stats[i, cv2.CC_STAT_HEIGHT]
            w = stats[i, cv2.CC_STAT_WIDTH]
            area = stats[i, cv2.CC_STAT_AREA]
            # Filter to plausible single-glyph-sized blobs: reject
            # hairline specks, page-spanning blobs (rules, borders,
            # binding shadow), and extreme aspect ratios (underlines,
            # vertical rules) that aren't individual characters.
            if h < 4 or h > img_h * 0.06:
                continue
            if w > img_w * 0.5:
                continue
            if area < 6:
                continue
            if (w / max(h, 1)) > 8:
                continue
            accepted.append(stats[i])

        if len(accepted) < _MIN_TRUSTED_COMPONENTS:
            return None
        return np.array(accepted)
    except Exception:
        return None


def estimate_page_text_signal(gray: np.ndarray) -> Optional[Tuple[float, int, float]]:
    """
    Returns (median_glyph_height, component_count, total_area_px) in a
    single connected-component pass over the raw page -- for callers that
    need both `estimate_glyph_height`'s size measure and
    `estimate_text_ink_signal`'s coverage measure for the same page (e.g.
    the OCR engine layer, which uses the height to size the recognizer
    input and the coverage to detect a script/recognition mismatch) and
    would otherwise redundantly run the underlying CC analysis twice.
    Returns None under the same conditions as `estimate_glyph_height`.
    """
    rows = _glyph_like_components(gray)
    if rows is None:
        return None
    return (
        float(np.median(rows[:, cv2.CC_STAT_HEIGHT])),
        int(rows.shape[0]),
        float(np.sum(rows[:, cv2.CC_STAT_AREA])),
    )


def estimate_glyph_height(gray: np.ndarray) -> Optional[float]:
    """
    Estimate typical character height via connected-component analysis on
    the binarized page, used to pick a resize scale that lands glyphs in
    the recognizer's effective range, and to gate deskew/contrast
    operations that are only meaningful when there's real text present.

    Returns None when there isn't enough signal to trust the estimate --
    callers should fall back to a content-agnostic default in that case,
    not force a scale or geometric correction onto a page with nothing
    to measure. See `_glyph_like_components` for the filter and the "why
    raw page" rationale.
    """
    rows = _glyph_like_components(gray)
    if rows is None:
        return None
    return float(np.median(rows[:, cv2.CC_STAT_HEIGHT]))


def estimate_text_ink_signal(gray: np.ndarray) -> Optional[Tuple[int, float]]:
    """
    Returns (component_count, total_area_px) for glyph-shaped connected
    components on the raw page -- the same underlying signal
    `estimate_glyph_height` uses, exposed as a coverage measure instead
    of a size measure. Returns None under the same conditions as
    `estimate_glyph_height` (not enough connected-component signal to
    trust the estimate).

    Used by the OCR engine layer to detect a script/recognition-model
    mismatch: RapidOCR's own recognizer silently drops any detection
    whose score falls below its internal threshold *before* the engine
    ever sees it (an out-of-dictionary glyph -- e.g. Arabic-script text
    fed through a Latin/CJK-only model -- reliably scores low and gets
    dropped this way), so a page that superficially "recognized fine"
    can still be missing most of its actual content with no low-score
    detections around to signal it. Comparing what this function reports
    against what the engine actually returned catches that case: if the
    raw page clearly has substantial glyph-shaped ink but the engine's
    returned detections cover almost none of it, the active recognition
    model most likely can't decode this page's script, rather than the
    page being genuinely sparse -- a genuinely sparse/blank page also
    scores low on THIS signal (or returns None outright), so the two
    cases are distinguishable without depending on the OCR engine's
    internal score-filtering behavior at all.
    """
    rows = _glyph_like_components(gray)
    if rows is None:
        return None
    return int(rows.shape[0]), float(np.sum(rows[:, cv2.CC_STAT_AREA]))
