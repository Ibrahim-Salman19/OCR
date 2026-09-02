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
import threading
from pathlib import Path
from typing import Union

from PIL import Image

from blast_ocr.core.exceptions import DecompressionBombError

MAX_DECODE_PIXELS = 100_000_000  # 10,000 x 10,000

# Guards the save/mutate/restore of the process-global `Image.MAX_IMAGE_PIXELS`
# in `_open_header_only` below. `BatchPreprocessor.load_image` is called from
# worker threads (blast_ocr.core.parallel's ThreadPoolExecutor), so without
# this lock two concurrent header peeks can interleave their save/restore and
# leave PIL's own bomb guard permanently disarmed process-wide (thread A saves
# thread B's already-None value as "previous", then restores None instead of
# the real ceiling). The critical section is just the open() call itself
# (microseconds), so serializing it costs nothing next to the page decode
# that follows outside the lock.
_pil_ceiling_lock = threading.Lock()


def _open_header_only(source: Union[bytes, str, Path]):
    """Opens `source` for a header-only peek (no pixel decode) with PIL's
    own decompression-bomb guard suspended for the duration of the call.

    PIL raises its *own* `Image.DecompressionBombError` from `Image.open()`
    once a declared size exceeds 2x `Image.MAX_IMAGE_PIXELS` -- a second,
    independently-configured bomb check layered underneath this module's.
    Left enabled, it fires *before* this module's own ceiling comparison
    ever runs, and every caller here catches it with a blanket
    `except Exception` (treating "header unparseable" and "confirmed bomb"
    identically) -- so the largest, most obvious bombs (>2x the ceiling)
    silently no-op past the check instead of being rejected, while only
    moderately-oversized ones (limit..2x) actually get caught. This module's
    own pixel-count comparison below is the sole intended authority on the
    ceiling, so PIL's redundant guard is suspended here rather than raced.
    """
    with _pil_ceiling_lock:
        previous_ceiling = Image.MAX_IMAGE_PIXELS
        Image.MAX_IMAGE_PIXELS = None
        try:
            return (
                Image.open(io.BytesIO(source))
                if isinstance(source, (bytes, bytearray))
                else Image.open(source)
            )
        finally:
            Image.MAX_IMAGE_PIXELS = previous_ceiling


def enforce_pixel_ceiling(
    source: Union[bytes, str, Path], limit: int = MAX_DECODE_PIXELS
) -> None:
    """Raises DecompressionBombError if the image header declares more than
    `limit` pixels. No-ops if the header can't be parsed by PIL -- callers
    still reject payloads their own decoder can't read."""
    try:
        with _open_header_only(source) as probe:
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
        with _open_header_only(source) as probe:
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
        with _open_header_only(source) as probe:
            mode = probe.mode
    except Exception:
        return False
    return mode == "CMYK"
