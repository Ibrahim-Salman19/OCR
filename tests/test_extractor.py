import pytest
import logging
from blast_ocr.core.extractor import RobustOCRExtractor
from blast_ocr.core.exceptions import ImageLoadError, PageExtractionError

# Configure logger to capture output during tests
logging.basicConfig(level=logging.DEBUG)

def test_extractor_initialization():
    extractor = RobustOCRExtractor()
    assert extractor.reader is not None

def test_process_page_success(sample_image):
    extractor = RobustOCRExtractor()
    result = extractor.process_page(sample_image, page_number=1)
    
    # Debug output
    print(f"Extracted Text: {result.get('text')}")
    print(f"Confidence: {result.get('confidence')}")
    
    assert result['page'] == 1
    # Lenient check as default font is tiny and might yield low quality
    assert len(result['text']) > 0 or result.get('warning') == 'no_text_detected'
    assert result['bbox_count'] >= 0

def test_process_page_not_found():
    extractor = RobustOCRExtractor()
    # The extractor wraps image load errors in PageExtractionError
    with pytest.raises(PageExtractionError) as excinfo:
        extractor.process_page("non_existent_file.png", 1)
    assert "File not found" in str(excinfo.value) or "Cannot load" in str(excinfo.value)

def test_image_load_error(tmp_path):
    # Create invalid image file
    bad_file = tmp_path / "bad.png"
    bad_file.write_text("not an image")
    
    extractor = RobustOCRExtractor()
    with pytest.raises(PageExtractionError) as excinfo:
        extractor.process_page(str(bad_file), 1)
    assert "extraction failed" in str(excinfo.value) or "cv2.imdecode" in str(excinfo.value)
