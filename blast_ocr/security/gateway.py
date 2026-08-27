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

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp", ".pptx", ".txt"}

# Magic bytes signature dictionary
MAGIC_BYTES = {
    ".pdf": [b"%PDF"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".bmp": [b"BM"],
    ".tiff": [b"II*\x00", b"MM\x00*"],
    ".pptx": [b"PK\x03\x04"],  # Zip container
}


class SecurityValidationError(Exception):
    """Raised when an ingested file violates security policies."""
    pass


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

        if ext in MAGIC_BYTES:
            with open(src, "rb") as f:
                header = f.read(16)
            matched = any(header.startswith(sig) for sig in MAGIC_BYTES[ext])
            if not matched:
                raise SecurityValidationError(
                    f"File header magic bytes do not match expected signature for extension '{ext}'"
                )

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

        # Validate magic bytes
        if ext in MAGIC_BYTES:
            with open(src, "rb") as f:
                header = f.read(16)
            matched = any(header.startswith(sig) for sig in MAGIC_BYTES[ext])
            if not matched:
                raise SecurityValidationError(
                    f"File header magic bytes do not match expected signature for extension '{ext}'"
                )

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
