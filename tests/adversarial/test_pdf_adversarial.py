"""
tests/adversarial/test_pdf_adversarial.py

Adversarial suite for the PDF/document ingestion boundary
(docs/HARDENING_BLUEPRINT_AND_TEST_SPECS.md §4.3.1, GAP-01).

Real entry point: `blast_ocr.security.gateway.IngestionGateway.validate`
(the blueprint's illustrative `security.pdf_validator.PDFPreflightValidator`
does not exist in this codebase).
"""

import pytest

from blast_ocr.security.gateway import IngestionGateway, SecurityValidationError


def _write(tmp_path, name: str, content: bytes):
    path = tmp_path / name
    path.write_bytes(content)
    return path


def test_pdf_polyglot_header_offset_rejected(tmp_path):
    """TAX-PDF-04: a '%PDF-' signature hiding behind attacker-controlled
    leading bytes (offset != 0) must be rejected, not silently accepted
    because *some* valid header exists later in the file."""
    polyglot = b"MZ\x90\x00\x03\x00\x00\x00" + b"%PDF-1.7\n1 0 obj<<>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
    path = _write(tmp_path, "evasion.pdf", polyglot)

    with pytest.raises(SecurityValidationError, match="offset"):
        IngestionGateway.validate(path)


def test_pdf_signature_smuggled_in_raster_extension_rejected(tmp_path):
    """A '.png'-declared upload that actually embeds a PDF signature within
    the reader-tolerated scan window is a polyglot payload smuggled under a
    different extension -- must be rejected even though its own extension's
    magic-byte check would otherwise fail first for an unrelated reason."""
    smuggled = b"\x89PNG\r\n\x1a\n" + b"junk" + b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF"
    path = _write(tmp_path, "smuggled.png", smuggled)

    with pytest.raises(SecurityValidationError, match="polyglot"):
        IngestionGateway.validate(path)


def test_valid_pdf_at_offset_zero_passes(tmp_path):
    valid_pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF"
    )
    path = _write(tmp_path, "clean.pdf", valid_pdf)

    IngestionGateway.validate(path)  # must not raise


def test_disallowed_extension_rejected(tmp_path):
    path = _write(tmp_path, "payload.exe", b"MZ\x90\x00")

    with pytest.raises(SecurityValidationError, match="whitelist"):
        IngestionGateway.validate(path)


def test_empty_file_rejected(tmp_path):
    path = _write(tmp_path, "empty.pdf", b"")

    with pytest.raises(SecurityValidationError, match="empty"):
        IngestionGateway.validate(path)


def test_nonexistent_file_rejected(tmp_path):
    missing = tmp_path / "does_not_exist.pdf"

    with pytest.raises(SecurityValidationError, match="does not exist"):
        IngestionGateway.validate(missing)


def test_oversized_file_rejected(tmp_path, monkeypatch):
    """The real 200MB ceiling is expensive to materialize in a unit test;
    lowering MAX_FILE_SIZE_BYTES exercises the exact same comparison against
    a small, fast fixture instead of skipping the boundary entirely."""
    monkeypatch.setattr(IngestionGateway, "MAX_FILE_SIZE_BYTES", 16)
    valid_pdf = b"%PDF-1.4\n" + b"x" * 32 + b"\n%%EOF"
    path = _write(tmp_path, "toobig.pdf", valid_pdf)

    with pytest.raises(SecurityValidationError, match="exceeds maximum"):
        IngestionGateway.validate(path)


def test_mismatched_magic_bytes_for_declared_extension_rejected(tmp_path):
    """A '.png' extension whose content is neither a genuine PNG header nor
    a PDF polyglot (e.g. a plain text file renamed) must fail the magic-byte
    signature check rather than being ingested on extension trust alone."""
    path = _write(tmp_path, "fake.png", b"this is not a png file at all")

    with pytest.raises(SecurityValidationError, match="magic bytes"):
        IngestionGateway.validate(path)
