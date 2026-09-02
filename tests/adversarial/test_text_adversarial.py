"""
tests/adversarial/test_text_adversarial.py

Adversarial suite for Trojan Source BiDi/null-byte injection (GAP-03) and
Private Use Area font-corruption fallback (GAP-09)
(docs/HARDENING_BLUEPRINT_AND_TEST_SPECS.md §4.3.3).

Real entry points: `blast_ocr.security.gateway._scan_text_sample` (the
raw-upload boundary scanner for .txt/.md files) and
`blast_ocr.core.exporter.sanitize_for_xml` (the extracted-content
sanitizer). There is no `blast_ocr.core.text_sanitizer.TextSanitizer` in
this codebase -- the blueprint's illustrative class of that name does not
exist, and its BiDi-stripping and NFKC-normalization behavior is not
implemented anywhere in the pipeline. This file tests the real functions
that do exist, and documents the resulting scope boundary rather than
inventing coverage for logic that was never built.
"""

import pytest

from blast_ocr.core.exporter import sanitize_for_xml
from blast_ocr.core.models import RouteDecision
from blast_ocr.core.tier0_extractor import Tier0Extractor
from blast_ocr.security.gateway import SecurityValidationError, _scan_text_sample


def test_raw_upload_bidi_trojan_source_override_rejected():
    """TAX-TXT-02: a raw .txt/.md upload containing a BiDi RLO/PDF pair
    (CVE-2021-42574-class Trojan Source) is rejected at the ingestion
    boundary before it ever reaches the pipeline."""
    hostile = "access_level = ‮admin‬user".encode("utf-8")

    with pytest.raises(SecurityValidationError, match="BiDi"):
        _scan_text_sample(hostile, ".txt")


def test_raw_upload_null_byte_rejected():
    """TAX-TXT-12: a raw text upload containing a binary null byte is
    rejected rather than passed through to downstream text processing that
    could abort on serialization."""
    hostile = b"header\x00value"

    with pytest.raises(SecurityValidationError, match="null bytes"):
        _scan_text_sample(hostile, ".md")


def test_raw_upload_clean_text_passes():
    clean = "Chapter 1: Introduction\n\nThis is ordinary prose.".encode("utf-8")

    _scan_text_sample(clean, ".txt")  # must not raise


def test_sanitize_for_xml_strips_null_and_c0_control_bytes():
    dirty = "invoice\x00number\x07\x1B\x0Cvalue"
    clean = sanitize_for_xml(dirty)

    assert "\x00" not in clean
    assert "\x07" not in clean
    assert clean == "invoicenumbervalue"


def test_sanitize_for_xml_does_not_strip_bidi_overrides_from_extracted_content():
    """Documents a real scope boundary: GAP-03's Trojan Source defense only
    covers the raw-upload boundary (_scan_text_sample above), not BiDi
    override characters embedded in a PDF's digital text layer or in OCR'd
    text that reaches `sanitize_for_xml` on the output path. This is
    deliberately locked in as a passing regression test (documenting actual
    behavior) rather than a proposed fix -- stripping BiDi marks
    unconditionally from extracted content risks corrupting legitimate
    Arabic/Hebrew RTL text that relies on the same codepoint range, and
    that policy tradeoff is out of scope for the Tier 4 adversarial harness
    itself.
    """
    hostile = "access_level = ‮admin‬user"

    result = sanitize_for_xml(hostile)

    assert "‮" in result, (
        "sanitize_for_xml no longer passes through BiDi overrides -- if this "
        "assertion now fails because BiDi stripping was added to the output "
        "path, update this test to lock in the new (safer) behavior instead "
        "of treating this as a regression."
    )


def test_pua_font_corruption_boundary_below_threshold_passes_native():
    """GAP-09 boundary value: unicode_replacement_ratio == 0.02 (the
    Tier0Extractor threshold check is a strict `> 0.02`) must still route
    PASS_NATIVE -- the penalty must not fire one boundary value early."""
    filler = "the quick brown fox jumps over lazy dog and reads printed books today "
    total = 500
    pua_count = 10  # exactly 0.02 of 500
    base = (filler * ((total // len(filler)) + 1))[: total - pua_count]
    text = base + (chr(0xE010) * pua_count)

    quality = Tier0Extractor.analyze_native_text_quality(text)

    assert quality.unicode_replacement_ratio == 0.02
    assert quality.decision == RouteDecision.PASS_NATIVE


def test_pua_font_corruption_boundary_above_threshold_falls_back_to_ocr():
    """GAP-09 boundary value: one PUA character past the 0.02 ratio
    threshold must flip the routing decision away from PASS_NATIVE."""
    filler = "the quick brown fox jumps over lazy dog and reads printed books today "
    total = 500
    pua_count = 11  # just over 0.02 of 500
    base = (filler * ((total // len(filler)) + 1))[: total - pua_count]
    text = base + (chr(0xE010) * pua_count)

    quality = Tier0Extractor.analyze_native_text_quality(text)

    assert quality.unicode_replacement_ratio > 0.02
    assert quality.decision != RouteDecision.PASS_NATIVE
