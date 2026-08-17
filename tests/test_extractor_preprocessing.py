"""
Phase 1: RobustOCRExtractor preprocessing -- glyph-height-targeted resize
and projection-profile deskew, replacing the fixed-1800px-cap round trip
and minAreaRect deskew estimate (see docs/adr/ for the full rationale).
"""

import cv2
import numpy as np
import pytest

from blast_ocr.core.extractor import RobustOCRExtractor


def _synthetic_text_page(
    width=1200, height=1600, n_lines=25, glyph_height=18, angle=0.0
):
    """A page of text-like rectangles (stand-ins for glyphs) at a known
    height, optionally rotated by a known angle -- lets tests assert
    against ground truth the way a real scanned page never allows."""
    img = np.full((height, width), 255, dtype=np.uint8)
    margin = 80
    line_gap = (height - 2 * margin) // n_lines
    for i in range(n_lines):
        y = margin + i * line_gap
        x = margin
        while x < width - margin - 40:
            glyph_w = np.random.randint(8, 20)
            cv2.rectangle(
                img, (x, y), (x + glyph_w, y + glyph_height), 0, thickness=-1
            )
            x += glyph_w + np.random.randint(4, 10)

    if angle != 0.0:
        center = (width // 2, height // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        img = cv2.warpAffine(
            img, M, (width, height), flags=cv2.INTER_LINEAR, borderValue=255
        )
    return img


@pytest.fixture
def extractor():
    from unittest.mock import patch, MagicMock

    with patch("easyocr.Reader") as mock_reader_cls:
        mock_reader_cls.return_value = MagicMock()
        yield RobustOCRExtractor()


class TestEstimateGlyphHeight:
    def test_blank_page_returns_none(self, extractor):
        blank = np.full((800, 600), 255, dtype=np.uint8)
        assert extractor._estimate_glyph_height(blank) is None

    def test_estimates_known_glyph_height_reasonably(self, extractor):
        page = _synthetic_text_page(glyph_height=18)
        estimate = extractor._estimate_glyph_height(page)
        assert estimate is not None
        # Synthetic rectangles aren't real glyphs (no ascenders/descenders,
        # no anti-aliasing), so we check the estimate is in a sane
        # neighborhood of the true height rather than exact.
        assert 10 <= estimate <= 30, f"Expected roughly 18px, got {estimate}"

    def test_sparse_marks_do_not_produce_an_estimate(self, extractor):
        """A handful of stray marks (not a real text page) shouldn't be
        enough signal to justify a scaling decision."""
        img = np.full((800, 600), 255, dtype=np.uint8)
        for i in range(5):
            cv2.rectangle(img, (50 + i * 20, 50), (60 + i * 20, 65), 0, -1)
        assert extractor._estimate_glyph_height(img) is None


class TestEstimateSkewAngle:
    def test_unrotated_page_scores_near_zero(self, extractor):
        page = _synthetic_text_page(angle=0.0)
        angle = extractor._estimate_skew_angle(page)
        assert abs(angle) < 0.5, f"Expected ~0 degrees, got {angle}"

    def test_blank_page_does_not_crash(self, extractor):
        blank = np.full((400, 400), 255, dtype=np.uint8)
        angle = extractor._estimate_skew_angle(blank)
        assert isinstance(angle, float)

    @pytest.mark.parametrize("true_angle", [-3.0, 2.0, 4.5])
    def test_recovers_known_injected_rotation(self, extractor, true_angle):
        page = _synthetic_text_page(angle=true_angle)
        estimated = extractor._estimate_skew_angle(page)
        # The correction angle should be the negative of the injected
        # rotation (rotate back by -true_angle to undo it), matching the
        # sign convention already used by the minAreaRect estimate this
        # replaces (preprocess_image applies `angle` directly as the
        # correction, i.e. estimated ~= -true_angle undoes a +true_angle
        # rotation applied via getRotationMatrix2D with positive=CCW).
        assert abs(estimated - (-true_angle)) < 0.6, (
            f"Injected {true_angle}, expected correction ~{-true_angle}, "
            f"got {estimated}"
        )


class TestPreprocessImageResize:
    def test_small_image_is_upscaled(self, extractor):
        page = _synthetic_text_page(width=300, height=400, glyph_height=8)
        result = extractor.preprocess_image(page)
        assert max(result.shape) > max(page.shape)

    def test_oversized_image_respects_safety_ceiling(self, extractor):
        huge = _synthetic_text_page(width=6000, height=8000, glyph_height=60)
        result = extractor.preprocess_image(huge)
        assert max(result.shape) <= RobustOCRExtractor.MAX_LONG_EDGE_PX + 1

    def test_too_small_glyph_height_is_upscaled_toward_target(self, extractor):
        """Below MIN_ACCEPTABLE_GLYPH_HEIGHT_PX, scale up toward the target."""
        page = _synthetic_text_page(width=2400, height=3200, glyph_height=10)
        result = extractor.preprocess_image(page)
        new_estimate = extractor._estimate_glyph_height(result)
        assert new_estimate is not None
        # Allow a generous band: synthetic-rectangle estimation plus resize
        # interpolation both add noise around the exact target.
        assert 15 <= new_estimate <= 40, (
            f"Expected resized glyph height near "
            f"{RobustOCRExtractor.TARGET_GLYPH_HEIGHT_PX}px, got {new_estimate}"
        )

    def test_adequate_glyph_height_is_not_rescaled(self, extractor):
        """FIX(phase1 follow-up): a page whose glyph height is already
        >= MIN_ACCEPTABLE_GLYPH_HEIGHT_PX must NOT be rescaled -- doing so
        unconditionally (always retargeting to exactly TARGET_GLYPH_HEIGHT_PX)
        was measured to make full-corpus CER worse, not better, because it
        upscaled already-adequate pages with interpolated pixels carrying
        no new information. See docs/adr/0003-phase1-preprocessing-fixes.md."""
        page = _synthetic_text_page(width=2400, height=3200, glyph_height=60)
        result = extractor.preprocess_image(page)
        assert result.shape == page.shape, (
            f"Page already had adequate glyph height (60px, well above the "
            f"{RobustOCRExtractor.MIN_ACCEPTABLE_GLYPH_HEIGHT_PX}px floor) "
            f"and should not have been resized; got shape {result.shape} "
            f"from input {page.shape}"
        )

    def test_does_not_crash_on_blank_page(self, extractor):
        blank = np.full((500, 500), 255, dtype=np.uint8)
        result = extractor.preprocess_image(blank)
        assert result is not None
        assert result.size > 0


class TestPreprocessImageDeskewGating:
    """FIX(phase1 follow-up/F-09b): _estimate_skew_angle has no way to know
    whether it's looking at real text lines or texture, so preprocess_image
    must not trust its output on a page with no reliable glyph-height
    signal. This exact gap let a -7.0 degree estimate on a photographed
    cloth book cover (no body text, just weave texture) get applied as a
    "correction", driving that gold page's CER from 0.41 to 0.80 and
    accounting for nearly the entire full-corpus regression this fix
    resolves. See docs/adr/0003-phase1-preprocessing-fixes.md."""

    def test_no_glyph_signal_skips_deskew_even_with_large_angle_estimate(
        self, extractor
    ):
        from unittest.mock import patch

        page = np.full((900, 700), 255, dtype=np.uint8)
        with patch.object(
            RobustOCRExtractor, "_estimate_glyph_height", return_value=None
        ), patch.object(
            RobustOCRExtractor, "_estimate_skew_angle", return_value=5.0
        ) as mock_angle:
            extractor.preprocess_image(page)
            # No trustworthy text-line signal -> don't even ask for an
            # angle estimate, let alone apply one.
            mock_angle.assert_not_called()

    def test_glyph_signal_present_allows_deskew_to_apply(self, extractor):
        """Complements the test above: real text-line signal must still
        get a real correction -- the new gate suppresses deskew only for
        signal-free pages, it doesn't silently disable deskew altogether."""
        page = _synthetic_text_page(angle=4.0)
        result = extractor.preprocess_image(page)
        residual = extractor._estimate_skew_angle(result)
        assert abs(residual) < 2.0, (
            f"Expected deskew to reduce residual skew well below the "
            f"injected 4.0 degrees, got {residual}"
        )
