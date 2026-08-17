"""
tests/test_execution_plan_v2_p0.py

Comprehensive unit tests verifying P0 requirements from Execution Plan v2:
- JobConfig immutability & validation
- IngestionGateway security boundary
- JobStateMachine & JobFingerprint
- BookDocument structural IR
- RunManifest auditable schema v1
"""

import pytest
import tempfile
import os
from pathlib import Path

from blast_ocr.core.models import JobConfig, JobState, RouteDecision
from blast_ocr.security.gateway import IngestionGateway, SecurityValidationError
from blast_ocr.core.job_state import JobStateMachine, JobFingerprint
from blast_ocr.core.book_document import BookDocument, BookParagraph, BookChapter
from blast_ocr.core.manifest import RunManifest, ManifestOutputArtifact
from blast_ocr.core.document_model import Document, Page


def test_job_config_immutability_and_filtering():
    cfg = JobConfig.from_dict({
        "ocr_engine": "rapidocr",
        "enable_tier0_routing": True,
        "UNKNOWN_EXTRA_KEY": 12345,
    })
    assert cfg.ocr_engine == "rapidocr"
    assert cfg.enable_tier0_routing is True
    assert not hasattr(cfg, "UNKNOWN_EXTRA_KEY")

    with pytest.raises(AttributeError):
        cfg.ocr_engine = "easyocr"


def test_ingestion_gateway_validation(tmp_path):
    # Test non-existent file
    with pytest.raises(SecurityValidationError):
        IngestionGateway.validate_and_ingest("non_existent.pdf", str(tmp_path / "uploads"))

    # Test disallow extension
    bad_file = tmp_path / "test.exe"
    bad_file.write_bytes(b"MZ12345")
    with pytest.raises(SecurityValidationError):
        IngestionGateway.validate_and_ingest(str(bad_file), str(tmp_path / "uploads"))

    # Test valid PNG ingestion with magic bytes
    png_file = tmp_path / "test.png"
    png_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    payload = IngestionGateway.validate_and_ingest(str(png_file), str(tmp_path / "uploads"))

    assert payload.original_filename == "test.png"
    assert payload.extension == ".png"
    assert payload.safe_filepath.exists()
    assert payload.safe_filepath.name != "test.png"  # UUID generated


def test_job_state_machine_and_fingerprint():
    assert JobStateMachine.can_transition(JobState.RECEIVED, JobState.VALIDATING)
    assert JobStateMachine.can_transition(JobState.PROCESSING, JobState.POST_PROCESSING)
    assert not JobStateMachine.can_transition(JobState.SUCCEEDED, JobState.PROCESSING)

    with pytest.raises(ValueError):
        JobStateMachine.validate_transition(JobState.SUCCEEDED, JobState.PROCESSING)

    cfg = JobConfig()
    fp1 = JobFingerprint.compute("hash123", cfg)
    fp2 = JobFingerprint.compute("hash123", cfg)
    assert fp1 == fp2
    assert len(fp1) == 64  # SHA256 hex length


def test_book_document_structural_representation():
    page1 = Page(page_num=1, raw_text="## Chapter 1\n\nThis is paragraph one.\n\nThis is paragraph two.", width=800, height=1000)
    doc = Document(title="Test Book", pages=[page1])

    book_doc = BookDocument.from_document_model(doc, title="Test Book")
    assert book_doc.title == "Test Book"
    assert len(book_doc.chapters) == 1

    full_txt = book_doc.to_full_text()
    assert "## Chapter 1" in full_txt
    assert "This is paragraph one." in full_txt

    html = book_doc.chapters[0].to_html()
    assert "<section id=\"chapter_1\">" in html
    assert "<h2>Chapter 1</h2>" in html


def test_run_manifest_schema(tmp_path):
    manifest = RunManifest(
        job_id=42,
        input_filename="test_book.pdf",
        input_sha256="abc123sha",
        input_size_bytes=102400,
        input_page_count=10,
        ocr_engine="rapidocr",
        outputs=[
            ManifestOutputArtifact(
                artifact_type="md",
                filepath=str(tmp_path / "test_book.md"),
                sha256_hash="mdsha123",
                size_bytes=5120,
            )
        ],
    )

    out_json_path = tmp_path / "manifest.json"
    manifest.save(str(out_json_path))

    assert out_json_path.exists()

    data = manifest.to_dict()
    assert data["schema_version"] == "1.0"
    assert data["job_id"] == 42
    assert data["input"]["filename"] == "test_book.pdf"
    assert data["ocr"]["engine"] == "rapidocr"
    assert len(data["outputs"]) == 1
    assert data["outputs"][0]["type"] == "md"
