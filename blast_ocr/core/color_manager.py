"""
blast_ocr.core.color_manager

CMYK-to-sRGB Color Space Transform.

cv2's CMYK decode path is undocumented and build/codec dependent (notably,
Adobe/Photoshop-produced CMYK JPEGs store channels pre-inverted per the
APP14 marker, and libjpeg-turbo builds disagree on whether to undo that
before color conversion). Decoding a CMYK raster through PIL instead, and
converting it explicitly here, gives one deterministic code path rather
than however OpenCV's build happens to behave.

Pillow's ImageCms (LittleCMS) binding can only synthesize sRGB/LAB/XYZ
profiles on the fly via `ImageCms.createProfile()` -- there is no generic,
synthesizable "CMYK" input profile, so the ICC transform is only available
when the source image itself embeds one (common in print-industry-produced
files, absent from most scanner/OCR output). When no embedded profile
exists, this falls back to the standard subtractive formula, which cannot
match a real press's gamut but is a correct, well-defined RGB rendering
that preserves relative luminance and contrast -- what OCR downstream
(binarization, glyph contrast) actually depends on.
"""

from __future__ import annotations

import io
import logging

import numpy as np
from PIL import Image, ImageCms

logger = logging.getLogger(__name__)


class ColorSpaceManager:
    """CMYK-to-sRGB color transform with ICC-aware and subtractive fallback paths."""

    @classmethod
    def convert_cmyk_to_srgb(cls, cmyk_img: Image.Image) -> Image.Image:
        """
        Converts a CMYK PIL image to RGB.

        Prefers a LittleCMS profile transform when the image carries an
        embedded ICC profile (`cmyk_img.info["icc_profile"]`); falls back to
        subtractive conversion otherwise. Non-CMYK input is returned
        converted to RGB unchanged (mirrors PIL's own `.convert("RGB")`).
        """
        if cmyk_img.mode != "CMYK":
            return cmyk_img.convert("RGB")

        icc_bytes = cmyk_img.info.get("icc_profile")
        if icc_bytes:
            try:
                srgb_profile = ImageCms.createProfile("sRGB")
                input_profile = ImageCms.getOpenProfile(io.BytesIO(icc_bytes))
                transform = ImageCms.buildTransform(
                    input_profile,
                    srgb_profile,
                    "CMYK",
                    "RGB",
                    renderingIntent=ImageCms.Intent.PERCEPTUAL,
                )
                return ImageCms.applyTransform(cmyk_img, transform)
            except Exception:
                logger.warning(
                    "Embedded CMYK ICC profile transform failed; "
                    "falling back to subtractive conversion.",
                    exc_info=True,
                )

        return cls._subtractive_cmyk_to_rgb(cmyk_img)

    @staticmethod
    def _subtractive_cmyk_to_rgb(cmyk_img: Image.Image) -> Image.Image:
        """
        Standard subtractive conversion:
            R = 255 * (1 - C) * (1 - K)
            G = 255 * (1 - M) * (1 - K)
            B = 255 * (1 - Y) * (1 - K)
        """
        cmyk_array = np.array(cmyk_img, dtype=np.float32) / 255.0
        c, m, y, k = (
            cmyk_array[:, :, 0],
            cmyk_array[:, :, 1],
            cmyk_array[:, :, 2],
            cmyk_array[:, :, 3],
        )

        r = 255.0 * (1.0 - c) * (1.0 - k)
        g = 255.0 * (1.0 - m) * (1.0 - k)
        b = 255.0 * (1.0 - y) * (1.0 - k)

        rgb_array = np.dstack((r, g, b))
        rgb_clipped = np.clip(rgb_array, 0, 255).astype(np.uint8)
        return Image.fromarray(rgb_clipped, mode="RGB")
