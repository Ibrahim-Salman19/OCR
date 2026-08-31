"""
blast_ocr.security.image_sanitizer

Pre-decode header inspector guarding against decompression-bomb rasters.

PIL's Image.open() is lazy: it parses only the container header, not pixel
data. Peeking `.size` here rejects an oversized image before a single pixel
is decoded. This closes two gaps in the existing defenses:

1. `Image.MAX_IMAGE_PIXELS` only emits `DecompressionBombWarning` for images
   up to 2x its threshold and only raises past that -- a bomb sized between
   1x and 2x the configured ceiling silently decodes.
2. `cv2.imdecode`/`cv2.imread` (used on the hot ingestion path for uploaded
   files) enforce no pixel ceiling at all; a bomb passed through OpenCV is
   fully decoded into memory before any dimension can be inspected.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Union

from PIL import Image

from blast_ocr.core.exceptions import DecompressionBombError

MAX_DECODE_PIXELS = 100_000_000  # 10,000 x 10,000


def enforce_pixel_ceiling(
    source: Union[bytes, str, Path], limit: int = MAX_DECODE_PIXELS
) -> None:
    """Raises DecompressionBombError if the image header declares more than
    `limit` pixels. No-ops if the header can't be parsed by PIL -- callers
    still reject payloads their own decoder can't read."""
    try:
        opened = (
            Image.open(io.BytesIO(source))
            if isinstance(source, (bytes, bytearray))
            else Image.open(source)
        )
        with opened as probe:
            width, height = probe.size
    except Exception:
        return
    if width * height > limit:
        raise DecompressionBombError(width, height, limit)


def has_alpha_channel(source: Union[bytes, str, Path]) -> bool:
    """Peeks a raster's header (no pixel decode) to determine whether it
    declares a genuine transparency channel.

    Used to decide whether cv2 should decode with IMREAD_UNCHANGED (so a
    4th channel can be Porter-Duff composited as real alpha) or IMREAD_COLOR
    (OpenCV's own, already-correct colorspace conversion). Guessing purely
    from a decoded array's channel count is unsafe: a CMYK JPEG/TIFF also
    decodes to 4 channels under IMREAD_UNCHANGED, but that 4th channel is a
    K/ink plane, not transparency -- treating it as alpha corrupts color
    (e.g. a fully-inked, zero-K bright color would composite to white).
    Returns False (the safe, IMREAD_COLOR default) if the header can't be
    parsed by PIL.
    """
    try:
        opened = (
            Image.open(io.BytesIO(source))
            if isinstance(source, (bytes, bytearray))
            else Image.open(source)
        )
        with opened as probe:
            mode = probe.mode
            has_transparency_info = "transparency" in probe.info
    except Exception:
        return False
    return mode in ("RGBA", "LA") or (mode == "P" and has_transparency_info)


def is_cmyk(source: Union[bytes, str, Path]) -> bool:
    """Peeks a raster's header (no pixel decode) to determine whether it
    declares a CMYK color mode.

    Used to route CMYK rasters through a PIL decode + explicit color-space
    transform (blast_ocr.core.color_manager) instead of cv2's decode path,
    whose CMYK handling is undocumented and build/codec dependent -- most
    notably, whether an Adobe-produced CMYK JPEG's pre-inverted channels
    (APP14 marker) get undone before color conversion varies by libjpeg
    build. Returns False if the header can't be parsed by PIL.
    """
    try:
        opened = (
            Image.open(io.BytesIO(source))
            if isinstance(source, (bytes, bytearray))
            else Image.open(source)
        )
        with opened as probe:
            mode = probe.mode
    except Exception:
        return False
    return mode == "CMYK"
