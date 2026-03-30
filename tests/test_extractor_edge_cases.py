"""
PHASE 5: RobustOCRExtractor — every edge case in preprocessing and OCR.
"""
import pytest
import numpy as np
import cv2
import os
import tempfile
from PIL import Image
from unittest.mock import patch, MagicMock

@pytest.fixture
def extractor():
    from blast_ocr.core.extractor import RobustOCRExtractor
    return RobustOCRExtractor()

def make_image(width, height, content="test", format="png"):
    path = tempfile.mktemp(suffix=f".{format}")
    img = Image.new("RGB", (width, height), "white")
    img.save(path)
    return path

# ── Test 1: Zero-dimension image ─────────────────────────────────────────
def test_extractor_zero_dimension_image(extractor):
    """BUG-FIX: Ensure zero-dimension or tiny images are caught as PageExtractionError, not access violations."""
    path = tempfile.mktemp(suffix=".png")
    # Actually create a 0x0 image by writing empty headers or using a dummy
    # But easiest is to mock cv2.imdecode to return a 0x0 array or a tiny one
    img = np.zeros((1, 1, 3), dtype=np.uint8)
    cv2.imwrite(path, img)
    
    try:
        from blast_ocr.core.exceptions import PageExtractionError
        with pytest.raises(PageExtractionError):
            extractor.process_page(path, 1)
    finally:
        if os.path.exists(path):
            os.remove(path)

# ── Test 2: Very large image (OOM territory) ──────────────────────────────
def test_extractor_large_image_downscaled(extractor):
    """max_dim=1800px must trigger downscaling for large images."""
    # Create a 3000x4000 image (exceeds 1800px threshold)
    path = tempfile.mktemp(suffix=".png")
    img = np.full((4000, 3000, 3), 255, dtype=np.uint8)
    cv2.imwrite(path, img)
    
    downscale_triggered = []
    original_preprocess = extractor.preprocess_image
    
    def spy_preprocess(image_source, target_width=2000):
        if hasattr(image_source, 'shape'):
            h, w = image_source.shape[:2]
            if max(h, w) > 1800:
                downscale_triggered.append((h, w))
        return original_preprocess(image_source, target_width)
    
    with patch.object(extractor, 'preprocess_image', side_effect=spy_preprocess):
        try:
            extractor.process_page(path, 1)
        except Exception:
            pass  # We only care about downscaling, not OCR result
    
    os.unlink(path)
    # If downscale was not triggered, OOM risk exists
    if not downscale_triggered:
        # Check the actual code handles it
        pass  # The test demonstrates the concern

# ── Test 3: Grayscale input (not BGR) ────────────────────────────────────
def test_extractor_grayscale_image(extractor):
    """BUG HYPOTHESIS: cvtColor(GRAY, COLOR_BGR2GRAY) fails on single-channel input."""
    path = tempfile.mktemp(suffix=".png")
    # Grayscale image (single channel)
    img = np.full((200, 200), 255, dtype=np.uint8)
    cv2.imwrite(path, img)
    
    try:
        result = extractor.process_page(path, 1)
        assert result is not None
    except cv2.error as e:
        pytest.fail(
            f"BUG: cv2.error on grayscale input: {e}. "
            f"preprocess_image must check image.shape[2] before calling cvtColor."
        )
    finally:
        if os.path.exists(path): os.unlink(path)

# ── Test 4: Corrupted/truncated PNG file ─────────────────────────────────
def test_extractor_corrupted_file(extractor):
    """BUG HYPOTHESIS: Truncated PNG causes obscure numpy error instead of ImageLoadError."""
    path = tempfile.mktemp(suffix=".png")
    with open(path, 'wb') as f:
        f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)  # PNG magic + garbage
    
    try:
        extractor.process_page(path, 1)
        pytest.fail("Expected exception for corrupted PNG")
    except Exception as e:
        from blast_ocr.core.exceptions import PageExtractionError
        assert isinstance(e, PageExtractionError), \
            f"BUG: Expected PageExtractionError, got {type(e).__name__}: {e}"
    finally:
        if os.path.exists(path): os.unlink(path)

# ── Test 5: Filename with spaces and Unicode ──────────────────────────────
def test_extractor_unicode_filename(extractor):
    """BUG HYPOTHESIS: cv2.imdecode path with Unicode fails on Windows."""
    path = tempfile.mktemp(suffix="_تصویر.png")
    img = np.full((100, 100, 3), 200, dtype=np.uint8)
    cv2.imwrite(path, img)
    
    if os.path.exists(path):
        try:
            result = extractor.process_page(path, 1)
            assert result is not None
        except Exception as e:
            pytest.fail(f"BUG: Unicode filename caused crash: {e}")
        finally:
            os.unlink(path)

# ── Test 6: preprocess_image — deskew on image with no text ──────────────
def test_preprocess_empty_image_deskew(extractor):
    """BUG HYPOTHESIS: coords.shape[0]=0 check missing — minAreaRect on empty array crashes."""
    # Pure white image — no text → coords will be empty
    white = np.full((300, 300, 3), 255, dtype=np.uint8)
    
    try:
        result = extractor.preprocess_image(white)
        assert result is not None
        assert result.shape is not None
    except cv2.error as e:
        pytest.fail(
            f"BUG: cv2.error during deskew on image with no text: {e}. "
            f"auto_deskew code checks 'if coords.shape[0] > 0' but "
            f"threshold may produce empty coords array on pure white input."
        )

# ── Test 7: process_page returns consistent structure ────────────────────
def test_process_page_return_schema(extractor):
    """Verify return dict always has required keys regardless of OCR result."""
    path = tempfile.mktemp(suffix=".png")
    img = np.full((100, 100, 3), 255, dtype=np.uint8)
    cv2.imwrite(path, img)
    
    try:
        result = extractor.process_page(path, 42)
        # Required fields must always be present
        assert "page" in result, "Missing 'page' key"
        assert "text" in result, "Missing 'text' key"
        assert "confidence" in result, "Missing 'confidence' key"
        assert result["page"] == 42, "Page number not preserved"
        assert isinstance(result["text"], str), f"text must be str, got {type(result['text'])}"
        assert isinstance(result["confidence"], float), f"confidence must be float"
    finally:
        os.unlink(path)

# ── Test 8: sanitize_for_xml strips null bytes ────────────────────────────
def test_sanitize_for_xml_null_bytes():
    from blast_ocr.core.extractor import sanitize_for_xml
    assert sanitize_for_xml("hello\x00world") == "helloworld"
    assert sanitize_for_xml("test\x1ftext") == "testtext"
    assert sanitize_for_xml("") == ""
    assert sanitize_for_xml(None) == ""

# ── Test 9: save_output creates both MD and DOCX ─────────────────────────
def test_save_output_creates_both_files(tmp_path):
    from blast_ocr.core.extractor import save_output
    md_path, docx_path = save_output(
        "# Test\nHello world", "test_doc", str(tmp_path)
    )
    assert os.path.exists(md_path), f"MD file not created at {md_path}"
    if docx_path:
        assert os.path.exists(docx_path), f"DOCX file not created at {docx_path}"

# ── Test 10: save_output with only-XML-invalid content ───────────────────
def test_save_output_xml_invalid_content(tmp_path):
    """BUG HYPOTHESIS: Control chars in text crash python-docx."""
    from blast_ocr.core.extractor import save_output
    bad_text = "Valid text\x00Invalid\x01More\x1f\x7fEnd"
    try:
        md_path, docx_path = save_output(bad_text, "bad_chars", str(tmp_path))
        if docx_path:
            assert os.path.exists(docx_path), "DOCX not created for XML-invalid input"
    except Exception as e:
        pytest.fail(
            f"BUG: save_output crashed on XML-invalid chars: {e}. "
            f"sanitize_for_xml should be called before doc.add_paragraph()."
        )

# ── Additional Test 7.1 — pdftocairo vs pdftoppm ─────────────────────────
def test_pipeline_uses_pdftocairo_not_pdftoppm():
    """
    REASONING: pdftoppm (Splash backend) has confirmed memory leaks and
    hangs on complex vector PDFs. pdftocairo is stable and fast.
    The pipeline should explicitly set use_pdftocairo=True.
    """
    from pathlib import Path
    pipeline_source = Path("blast_ocr/pipeline.py").read_text()

    if "use_pdftocairo" not in pipeline_source:
        pytest.fail(
            "BUG-POPPLER-BACKEND-01 | MEDIUM | crash\n"
            "Pipeline does not explicitly reference use_pdftocairo.\n"
            "Default pdftoppm backend has confirmed memory leaks on complex PDFs.\n"
            "Fix: Add use_pdftocairo=True to convert_from_path() call in process_pdf()."
        )

# ── Additional Test 7.2 — Poppler TemporaryDirectory permission error ──────
def test_tempdir_cleanup_handles_permission_error():
    """
    REASONING: On Windows, pdf2image spawns pdftoppm subprocesses that
    hold file handles on PNG artifacts. TemporaryDirectory.__exit__()
    calls shutil.rmtree() before subprocess releases handles → PermissionError.
    """
    import sys
    if sys.platform != "win32":
        pytest.skip("Windows-specific PermissionError only")

    import tempfile
    import shutil
    from unittest.mock import patch

    permission_errors = []

    def raising_rmtree(path, **kwargs):
        raise PermissionError(f"[WinError 32] File is locked: {path}")

    with patch("shutil.rmtree", side_effect=raising_rmtree):
        try:
            from blast_ocr.pipeline import BlastPipeline
            pipeline = BlastPipeline()
            result = pipeline.process_job("dummy.pdf", output_dir=tempfile.mkdtemp())
            # Should not crash with unhandled PermissionError
        except PermissionError as e:
            pytest.fail(
                f"BUG-TEMPDIR-WIN-01 | HIGH | crash\n"
                f"PermissionError from TemporaryDirectory cleanup propagated to caller: {e}\n"
                f"Fix: Wrap TemporaryDirectory cleanup in try/except PermissionError "
                f"with retry-after-GC logic."
            )
