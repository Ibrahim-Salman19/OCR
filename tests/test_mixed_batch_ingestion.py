"""
tests/test_mixed_batch_ingestion.py

Exhaustive tests for mixed-batch document ingestion:
1. Native extraction of .txt and .md documents.
2. Fault isolation in mixed batches (PDF + TXT + MD + invalid .exe).
3. Security boundary checks (spoofed extensions, binary null bytes).
4. Directory scanning with mixed file types.
5. Streamlit UI multi-file partial batch resilience.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

from blast_ocr.pipeline import BlastPipeline
from blast_ocr.security.gateway import IngestionGateway, SecurityValidationError
import blast_ocr.ui.web_app as web_app
from tests.test_ui_mock import MockSessionState


@pytest.fixture
def clean_workdir(tmp_path):
    out_dir = tmp_path / "output_dir"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def test_txt_and_md_native_extraction(clean_workdir, tmp_path):
    """Verify that .txt and .md files are extracted and generate all output formats."""
    txt_file = tmp_path / "sample_notes.txt"
    txt_file.write_text("This is an important plain text document.\nWith multiple lines of content.", encoding="utf-8")

    md_file = tmp_path / "sample_guide.md"
    md_file.write_text("# Guide\n\n## Section 1\nThis is a markdown document.\n\n| Col A | Col B |\n|---|---|\n| 1 | 2 |", encoding="utf-8")

    pipeline = BlastPipeline()
    try:
        # Process TXT
        txt_res = pipeline.process_job(source_path=str(txt_file), output_dir=str(clean_workdir / "txt_out"))
        assert txt_res["status"] == "success"
        assert "This is an important plain text" in txt_res["text"]
        assert os.path.exists(txt_res["generated_files"]["md"])
        assert os.path.exists(txt_res["generated_files"]["docx"])
        assert os.path.exists(txt_res["generated_files"]["txt"])

        # Process MD
        md_res = pipeline.process_job(source_path=str(md_file), output_dir=str(clean_workdir / "md_out"))
        assert md_res["status"] == "success"
        assert "This is a markdown document" in md_res["text"]
        assert os.path.exists(md_res["generated_files"]["md"])
        assert os.path.exists(md_res["generated_files"]["docx"])
    finally:
        pipeline.close()


def test_security_gateway_blocks_unauthorized_and_spoofed(tmp_path):
    """Verify gateway catches unsupported extensions, spoofed binaries, and binary text files."""
    # 1. Disallowed extension
    exe_file = tmp_path / "app.exe"
    exe_file.write_bytes(b"MZ\x90\x00\x03\x00\x00\x00")
    with pytest.raises(SecurityValidationError, match="not in allowed security whitelist"):
        IngestionGateway.validate(exe_file)

    # 2. Spoofed PDF (exe renamed to pdf)
    spoofed_pdf = tmp_path / "spoofed.pdf"
    spoofed_pdf.write_bytes(b"NOT_A_REAL_PDF_HEADER_12345")
    with pytest.raises(SecurityValidationError, match="magic bytes do not match"):
        IngestionGateway.validate(spoofed_pdf)

    # 3. Spoofed TXT containing binary null bytes
    binary_txt = tmp_path / "binary_payload.txt"
    binary_txt.write_bytes(b"ELF\x00\x01\x02\x03\x00\x00payload")
    with pytest.raises(SecurityValidationError, match="binary null bytes"):
        IngestionGateway.validate(binary_txt)


def test_directory_ingestion_filters_non_images(clean_workdir, tmp_path):
    """Verify directory processing collects only images and ignores .txt/.md/.py safely."""
    import cv2
    import numpy as np

    img_dir = tmp_path / "mixed_folder"
    img_dir.mkdir()

    # Create 2 valid dummy images
    dummy_img = np.ones((50, 200, 3), dtype=np.uint8) * 255
    cv2.putText(dummy_img, "TEST", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.imwrite(str(img_dir / "page_01.png"), dummy_img)
    cv2.imwrite(str(img_dir / "page_02.jpg"), dummy_img)

    # Add non-image files in the same folder
    (img_dir / "readme.md").write_text("# Readme", encoding="utf-8")
    (img_dir / "notes.txt").write_text("Some text", encoding="utf-8")
    (img_dir / "script.py").write_text("print(1)", encoding="utf-8")

    pipeline = BlastPipeline()
    try:
        res = pipeline.process_job(source_path=str(img_dir), output_dir=str(clean_workdir / "dir_out"))
        assert res["status"] == "success"
        assert res["pages_processed"] == 2  # Only the 2 images were processed
    finally:
        pipeline.close()


def test_ui_mixed_batch_upload_resilience(tmp_path):
    """Verify Streamlit UI processes valid files and isolates invalid ones in a mixed batch."""
    valid_pdf = MagicMock()
    valid_pdf.name = "document1.pdf"
    valid_pdf.size = 1024
    valid_pdf.getbuffer.return_value = b"%PDF-1.4 valid dummy pdf content"

    valid_txt = MagicMock()
    valid_txt.name = "document2.txt"
    valid_txt.size = 512
    valid_txt.getbuffer.return_value = b"Plain text content for second document"

    invalid_exe = MagicMock()
    invalid_exe.name = "bad_payload.exe"
    invalid_exe.size = 2048
    invalid_exe.getbuffer.return_value = b"MZ12345"

    mock_pipeline = MagicMock()
    mock_pipeline.process_job.side_effect = [
        {"status": "success", "pages_processed": 1, "generated_files": {"md": "/tmp/out1.md"}},
        {"status": "success", "pages_processed": 1, "generated_files": {"md": "/tmp/out2.md"}},
    ]

    mock_db = MagicMock()
    mock_state = MockSessionState(
        {"session_id": "test-uuid", "output_dir": str(tmp_path / "ui_out"), "current_results": None}
    )

    with patch("streamlit.file_uploader", return_value=[valid_pdf, invalid_exe, valid_txt]):
        with patch("streamlit.button", return_value=True):
            with patch("streamlit.session_state", mock_state):
                web_app.handle_file_upload(mock_pipeline, mock_db)

                # Verify summaries contain all 3 files
                summary = mock_state.current_results["summary"]
                assert len(summary) == 3

                # Valid PDF and TXT succeeded
                assert summary[0]["FILE"] == "document1.pdf"
                assert summary[0]["STATUS"] == "SUCCESS"

                # Invalid EXE was caught and marked FAILED without crashing the batch
                assert summary[1]["FILE"] == "bad_payload.exe"
                assert summary[1]["STATUS"] == "FAILED"
                assert "UNAUTHORIZED EXTENSION" in summary[1]["ERROR"]

                assert summary[2]["FILE"] == "document2.txt"
                assert summary[2]["STATUS"] == "SUCCESS"
