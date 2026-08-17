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

from typing import Optional

import cv2
import numpy as np


def estimate_glyph_height(gray: np.ndarray) -> Optional[float]:
    """
    Estimate typical character height via connected-component analysis on
    the binarized page, used to pick a resize scale that lands glyphs in
    the recognizer's effective range, and to gate deskew/contrast
    operations that are only meaningful when there's real text present.

    Returns None when there isn't enough signal to trust the estimate
    (e.g. a blank/near-blank page, or a page with no real text at all --
    callers should fall back to a content-agnostic default in that case,
    not force a scale or geometric correction onto a page with nothing
    to measure.

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
        heights = []
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
            heights.append(h)

        if len(heights) < 20:  # not enough signal to trust the estimate
            return None
        return float(np.median(heights))
    except Exception:
        return None
