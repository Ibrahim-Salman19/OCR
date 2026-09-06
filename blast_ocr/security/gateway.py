"""
blast_ocr.security.gateway

Hostile Document Security Gateway & Ingestion Boundary (Phase 4 of Execution Plan v2).
Protects OCR execution pipeline against untrusted file uploads by enforcing:
1. Extension allowlisting (.pdf, .png, .jpg, .jpeg, .pptx, .bmp, .tiff)
2. Magic byte / MIME type validation (preventing extension spoofing)
3. File size ceilings (200MB max per file)
4. Internal safe UUID filename generation (preventing path traversal attacks)
5. Structure sanity checks.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Union
import os
import uuid
import logging

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".tiff",
    ".tif",
    ".webp",
    ".pptx",
    ".txt",
    ".md",
    ".markdown",
}

# Magic bytes signature dictionary
MAGIC_BYTES = {
    ".pdf": [b"%PDF"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".bmp": [b"BM"],
    ".tiff": [b"II*\x00", b"MM\x00*"],
    ".tif": [b"II*\x00", b"MM\x00*"],
    ".webp": [b"RIFF"],
    ".pptx": [b"PK\x03\x04"],  # Zip container
}


# Unicode BiDi override/embedding control characters (Trojan Source, CVE-2021-42574
# class attacks): these can reorder how text visually renders without changing its
# logical byte order, hiding malicious content from a human reviewer.
# bandit's B613 (trojansource) plugin flags any source file containing these
# characters, on the reasonable assumption they're hidden there to fool a
# reviewer. Here they're the opposite: a literal, commented, single-line
# detection list -- the thing `_scan_text_sample` below uses to *reject*
# uploads containing them. Suppressing is correct; hiding the characters
# (e.g. via \uXXXX escapes) would just move the false positive to whichever
# call site re-derives the same set.
BIDI_OVERRIDE_CHARS = frozenset(
    "‪‫‬‭‮⁦⁧⁨⁩"  # nosec B613
)

# PDF readers (per ISO 32000) tolerate the "%PDF-" marker anywhere within the
# first 1024 bytes of a file, not just at offset 0. That tolerance is what
# makes PDF/X polyglots possible: a payload whose byte 0 satisfies some other
# format's magic-byte check (e.g. a PNG or ZIP header) while a spec-compliant
# PDF reader still finds "%PDF-" later in the same stream and treats the
# whole file as an executable PDF (embedded JavaScript, /Launch actions,
# etc). Scanning this same window for every upload, regardless of its
# declared extension, closes that bypass.
PDF_POLYGLOT_SIGNATURE = b"%PDF-"
PDF_POLYGLOT_SCAN_WINDOW = 1024

# Cross-format polyglot detection (a non-.pdf file embedding a PDF signature)
# is restricted to formats with a fixed-layout binary header, where a
# literal "%PDF-" this early in the file is genuinely anomalous. ZIP-based
# containers (.pptx) and text formats can legitimately contain that 5-byte
# ASCII sequence in an entry name or file path within the same window
# without being a polyglot payload, so they're excluded to avoid rejecting
# legitimate uploads.
RASTER_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}


class SecurityValidationError(Exception):
    """Raised when an ingested file violates security policies."""
    pass


def _check_pdf_polyglot(sample: bytes, ext: str) -> None:
    """Rejects PDF magic-header offset evasion and cross-format PDF polyglots.

    A `.pdf` upload must present its header at byte 0 -- an offset match means
    the true PDF signature is hiding behind attacker-controlled leading bytes.
    Any non-`.pdf` upload that contains a PDF signature within the same
    reader-tolerated window is a polyglot payload smuggled under a different
    declared extension.
    """
    offset = sample.find(PDF_POLYGLOT_SIGNATURE)
    if offset == -1:
        return
    if ext == ".pdf":
        if offset != 0:
            raise SecurityValidationError(
                f"PDF magic header found at offset {offset} instead of 0 "
                "(polyglot / evasion vector)"
            )
        return
    if ext in RASTER_IMAGE_EXTENSIONS:
        raise SecurityValidationError(
            f"File declared as '{ext}' contains an embedded PDF signature at byte "
            f"{offset} (polyglot payload)"
        )


def _scan_text_sample(sample: bytes, ext: str) -> None:
    """Rejects a raw text upload containing null bytes or Unicode BiDi override characters.

    This only inspects the leading sample read at the ingestion boundary (consistent
    with the existing header check below); it is a fast reject for hostile uploads,
    not a substitute for full-document text sanitization applied to extracted content.
    """
    if b"\x00" in sample:
        raise SecurityValidationError(
            f"File header contains binary null bytes, rejecting invalid text document '{ext}'"
        )
    decoded = sample.decode("utf-8", errors="ignore")
    if any(ch in BIDI_OVERRIDE_CHARS for ch in decoded):
        raise SecurityValidationError(
            f"File contains Unicode BiDi override control characters, rejecting potentially hostile text document '{ext}'"
        )


@dataclass(frozen=True)
class IngestionPayload:
    original_filename: str
    safe_filepath: Path
    extension: str
    size_bytes: int
    file_hash_sha256: str


class IngestionGateway:
    """Security boundary for validating and sanitizing uploaded documents."""

    MAX_FILE_SIZE_BYTES: int = 200 * 1024 * 1024  # 200MB limit

    @classmethod
    def validate(cls, source_path: Union[str, Path]) -> None:
        """Validates source file extension, existence, size, and magic bytes."""
        src = Path(source_path)
        if not src.exists():
            raise SecurityValidationError(f"Source file does not exist: {source_path}")

        ext = src.suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise SecurityValidationError(
                f"File extension '{ext}' is not in allowed security whitelist: {sorted(ALLOWED_EXTENSIONS)}"
            )

        file_size = src.stat().st_size
        if file_size == 0:
            raise SecurityValidationError("File is empty (0 bytes)")

        if file_size > cls.MAX_FILE_SIZE_BYTES:
            raise SecurityValidationError(
                f"File size {file_size} bytes exceeds maximum ceiling of {cls.MAX_FILE_SIZE_BYTES} bytes"
            )

        with open(src, "rb") as f:
            sample = f.read(PDF_POLYGLOT_SCAN_WINDOW)
        _check_pdf_polyglot(sample, ext)

        if ext in MAGIC_BYTES:
            matched = any(sample.startswith(sig) for sig in MAGIC_BYTES[ext])
            if not matched:
                raise SecurityValidationError(
                    f"File header magic bytes do not match expected signature for extension '{ext}'"
                )
        elif ext in {".txt", ".md", ".markdown"}:
            _scan_text_sample(sample, ext)

    @classmethod
    def validate_and_ingest(
        cls, source_path: str, upload_dir: str
    ) -> IngestionPayload:
        """
        Validates source file security policy, generates internal UUID filename,
        copies file into upload_dir, and returns an IngestionPayload.
        """
        src = Path(source_path)
        if not src.exists():
            raise SecurityValidationError(f"Source file does not exist: {source_path}")

        ext = src.suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise SecurityValidationError(
                f"File extension '{ext}' is not in allowed security whitelist: {sorted(ALLOWED_EXTENSIONS)}"
            )

        file_size = src.stat().st_size
        if file_size > cls.MAX_FILE_SIZE_BYTES:
            raise SecurityValidationError(
                f"File size {file_size} bytes exceeds maximum ceiling of {cls.MAX_FILE_SIZE_BYTES} bytes"
            )

        # Validate magic bytes and PDF polyglot evasion
        with open(src, "rb") as f:
            sample = f.read(PDF_POLYGLOT_SCAN_WINDOW)
        _check_pdf_polyglot(sample, ext)

        if ext in MAGIC_BYTES:
            matched = any(sample.startswith(sig) for sig in MAGIC_BYTES[ext])
            if not matched:
                raise SecurityValidationError(
                    f"File header magic bytes do not match expected signature for extension '{ext}'"
                )
        elif ext in {".txt", ".md", ".markdown"}:
            _scan_text_sample(sample, ext)

        # Compute SHA256 file fingerprint
        import hashlib
        hasher = hashlib.sha256()
        with open(src, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        sha256_hash = hasher.hexdigest()

        # Generate internal UUID filename to isolate user-controlled filenames
        safe_filename = f"{uuid.uuid4().hex}{ext}"
        os.makedirs(upload_dir, exist_ok=True)
        safe_path = Path(upload_dir) / safe_filename

        import shutil
        shutil.copy2(src, safe_path)

        logger.info(
            f"Ingested '{src.name}' -> '{safe_path.name}' (SHA256: {sha256_hash[:12]}..., Size: {file_size} bytes)"
        )

        return IngestionPayload(
            original_filename=src.name,
            safe_filepath=safe_path,
            extension=ext,
            size_bytes=file_size,
            file_hash_sha256=sha256_hash,
        )
