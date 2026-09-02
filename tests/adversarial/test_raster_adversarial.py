"""
tests/adversarial/test_raster_adversarial.py

Adversarial suite for raster decompression-bomb and header-inspection
defenses (docs/HARDENING_BLUEPRINT_AND_TEST_SPECS.md §4.3.2, GAP-02/GAP-11).

Real entry points: `blast_ocr.security.image_sanitizer.enforce_pixel_ceiling`,
`has_alpha_channel`, `is_cmyk` (the blueprint's illustrative
`ImageSecuritySanitizer.inspect_and_sanitize` class does not exist here).

`tests/test_batched_engine.py` already has thorough end-to-end regression
coverage of `BatchPreprocessor.load_image` for GAP-02 (decompression bombs),
GAP-08 (16-bit TIFF saturation), GAP-11 (CMYK), and alpha compositing --
this file deliberately does not re-test those same paths. It instead targets
the header-inspector primitives directly, at the boundary values and
corrupt-input edges those existing tests don't exercise.
"""

import io
import struct
import zlib

import pytest

from blast_ocr.core.exceptions import DecompressionBombError
from blast_ocr.security.image_sanitizer import (
    MAX_DECODE_PIXELS,
    enforce_pixel_ceiling,
    has_alpha_channel,
    is_cmyk,
)


def _synthesize_png_header(width: int, height: int) -> bytes:
    """Builds a syntactically valid PNG whose IHDR declares `width` x
    `height` pixels, backed by a tiny, highly-repetitive (and therefore
    trivially zlib-compressible) IDAT payload -- exactly how a real
    decompression bomb is constructed: the container header is real, the
    actual compressed bytes are small, and the bomb is in the *implied*
    decoded size, not the file size on disk.
    """
    raw_scanline = b"\x00" + (b"\xff" * width * 3)
    compressed = zlib.compress(raw_scanline * 4, level=9)

    out = io.BytesIO()
    out.write(b"\x89PNG\r\n\x1a\n")
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    out.write(struct.pack(">I", len(ihdr_data)))
    out.write(b"IHDR")
    out.write(ihdr_data)
    out.write(struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data)))
    out.write(struct.pack(">I", len(compressed)))
    out.write(b"IDAT")
    out.write(compressed)
    out.write(struct.pack(">I", zlib.crc32(b"IDAT" + compressed)))
    out.write(struct.pack(">I", 0))
    out.write(b"IEND")
    out.write(struct.pack(">I", zlib.crc32(b"IEND")))
    return out.getvalue()


def test_decompression_bomb_rejected_before_pixel_decode():
    """TAX-IMG-02: a 20000x20000 (400 megapixel) declared image, backed by
    only a few hundred bytes on disk, must be rejected from its header alone
    -- proving the ceiling is enforced pre-decode, not by measuring a
    fully-materialized array afterward."""
    bomb_bytes = _synthesize_png_header(20_000, 20_000)
    assert len(bomb_bytes) < 2_000, "fixture sanity: bomb must stay tiny on disk"

    with pytest.raises(DecompressionBombError) as exc_info:
        enforce_pixel_ceiling(bomb_bytes)
    assert exc_info.value.width == 20_000
    assert exc_info.value.height == 20_000


def test_pixel_ceiling_boundary_exact_limit_passes():
    """Boundary value analysis: exactly MAX_DECODE_PIXELS must pass (the
    check is `> limit`, not `>= limit`) -- a header declaring precisely the
    ceiling is a legitimate large scan, not a bomb."""
    side = int(MAX_DECODE_PIXELS**0.5)  # side*side <= MAX_DECODE_PIXELS
    at_limit = _synthesize_png_header(side, side)

    enforce_pixel_ceiling(at_limit)  # must not raise


def test_pixel_ceiling_boundary_one_pixel_over_limit_rejected():
    side = int(MAX_DECODE_PIXELS**0.5)
    over_limit = _synthesize_png_header(side, side + 1)

    with pytest.raises(DecompressionBombError):
        enforce_pixel_ceiling(over_limit)


def test_enforce_pixel_ceiling_noops_on_unparseable_header():
    """Documented contract: a header PIL can't parse at all no-ops rather
    than raising, deferring to the caller's own decoder to reject the
    payload on its own terms."""
    garbage = b"\x00\x01\x02not-an-image\xff\xfe" * 4

    enforce_pixel_ceiling(garbage)  # must not raise


def test_has_alpha_channel_false_on_unparseable_header():
    """Documented contract: an unparseable header returns the safe
    IMREAD_COLOR default (False) rather than raising or crashing the
    decode-flag decision that depends on it."""
    garbage = b"\x00\x01\x02not-an-image\xff\xfe" * 4

    assert has_alpha_channel(garbage) is False


def test_is_cmyk_false_on_unparseable_header():
    garbage = b"\x00\x01\x02not-an-image\xff\xfe" * 4

    assert is_cmyk(garbage) is False


def test_is_cmyk_false_on_truncated_valid_signature():
    """A file that starts with a genuine PNG signature but is truncated
    before PIL can parse IHDR must fail safe (False), not raise past the
    caller into the decode-path decision."""
    truncated = b"\x89PNG\r\n\x1a\n" + b"\x00" * 4

    assert is_cmyk(truncated) is False
    assert has_alpha_channel(truncated) is False
