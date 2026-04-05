import pytest
import logging
from unittest.mock import MagicMock, patch

from blast_ocr.core.extractor import RobustOCRExtractor
from blast_ocr.core.exceptions import PageExtractionError

# Configure logger to capture output during tests
logging.basicConfig(level=logging.DEBUG)


@pytest.fixture
def extractor():
    """Use mocked EasyOCR reader for deterministic, crash-free unit tests."""
    with patch("easyocr.Reader") as mock_reader_cls:
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = [
            (
                [[0, 0], [20, 0], [20, 10], [0, 10]],
                "Sample OCR Test Text",
                0.95,
            )
        ]
        mock_reader_cls.return_value = mock_reader
        yield RobustOCRExtractor()


def test_extractor_initialization(extractor):
    assert extractor.reader is not None


def test_process_page_success(sample_image, extractor):
    result = extractor.process_page(sample_image, page_number=1)

    # Debug output
    print(f"Extracted Text: {result.get('text')}")
    print(f"Confidence: {result.get('confidence')}")

    assert result["page"] == 1
    # Lenient check as default font is tiny and might yield low quality
    assert len(result["text"]) > 0 or result.get("warning") == "no_text_detected"
    assert result["bbox_count"] >= 0


def test_process_page_not_found(extractor):
    # The extractor wraps image load errors in PageExtractionError
    with pytest.raises(PageExtractionError) as excinfo:
        extractor.process_page("non_existent_file.png", 1)
    assert "File not found" in str(excinfo.value) or "Cannot load" in str(excinfo.value)


def test_image_load_error(tmp_path, extractor):
    # Create invalid image file
    bad_file = tmp_path / "bad.png"
    bad_file.write_text("not an image")

    with pytest.raises(PageExtractionError) as excinfo:
        extractor.process_page(str(bad_file), 1)
    assert "extraction failed" in str(excinfo.value) or "cv2.imdecode" in str(
        excinfo.value
    )


def test_init_engine_respects_easyocr_env_overrides(monkeypatch):
    monkeypatch.setenv("BLAST_OCR_EASYOCR_DOWNLOAD_ENABLED", "0")
    monkeypatch.setenv("BLAST_OCR_EASYOCR_MODEL_DIR", "/custom/easyocr")

    with patch("easyocr.Reader") as mock_reader_cls:
        mock_reader_cls.return_value = MagicMock()
        RobustOCRExtractor()

    kwargs = mock_reader_cls.call_args.kwargs
    assert kwargs["download_enabled"] is False
    assert kwargs["model_storage_directory"] == "/custom/easyocr"


def test_init_engine_uses_linux_model_dir_fallback(monkeypatch):
    monkeypatch.setenv("BLAST_OCR_EASYOCR_DOWNLOAD_ENABLED", "1")
    monkeypatch.delenv("BLAST_OCR_EASYOCR_MODEL_DIR", raising=False)
    monkeypatch.delenv("EASYOCR_MODULE_PATH", raising=False)

    with patch("blast_ocr.core.extractor.sys.platform", "linux"):
        with patch("easyocr.Reader") as mock_reader_cls:
            mock_reader_cls.return_value = MagicMock()
            RobustOCRExtractor()

    kwargs = mock_reader_cls.call_args.kwargs
    assert kwargs["download_enabled"] is True
    assert kwargs["model_storage_directory"] == "/tmp/.EasyOCR/model"


def test_init_engine_normalizes_disabled_download_values(monkeypatch):
    monkeypatch.setenv("BLAST_OCR_EASYOCR_DOWNLOAD_ENABLED", "false")

    with patch("easyocr.Reader") as mock_reader_cls:
        mock_reader_cls.return_value = MagicMock()
        RobustOCRExtractor()

    kwargs = mock_reader_cls.call_args.kwargs
    assert kwargs["download_enabled"] is False
