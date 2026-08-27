"""
Sprint 7: Pipeline coverage tests.
Ensures pipeline.py PDF batching, fallback branches, and temp dir cleanup
are fully covered by targeted mocks.
"""

import os
import pytest
import numpy as np
from unittest.mock import patch, MagicMock


@pytest.fixture
def pipeline():
    from blast_ocr.pipeline import BlastPipeline

    return BlastPipeline()


def test_pipeline_del_exception(pipeline):
    """Covers pipeline.py lines 52-58."""
    # Replace db with something that raises on close
    mock_db = MagicMock()
    mock_db.close.side_effect = Exception("DB close failed")
    pipeline.db = mock_db

    # Manually trigger __del__
    pipeline.__del__()
    assert mock_db.close.called


def test_process_pdf_happy_path_and_pdfinfo_exceptions(pipeline):
    """Covers process_pdf branches, loop limits, and info fetching."""
    fake_batch_paths = [f"page_{i}.png" for i in range(10)]
    restored = np.full((20, 20), 255, dtype=np.uint8)

    # 1. pdfinfo_from_path succeeds
    with patch("blast_ocr.pipeline.pdfinfo_from_path", return_value={"Pages": 21}):
        with patch(
            "blast_ocr.pipeline.convert_from_path", return_value=fake_batch_paths
        ):
            with patch(
                "blast_ocr.pipeline.ForensicRestorer.restore", return_value=restored
            ):
                # Also mock parallel processor to avoid actual processing
                with patch.object(
                    pipeline.parallel_processor,
                    "process_batch_threaded",
                    return_value=[{"page": 1}],
                ):
                    # Also mock tempfile to avoid disk ops inside loop if we want, but letting it make tempdir is safe
                    res = pipeline.process_pdf(
                        "dummy.pdf", progress_callback=lambda c, t: None
                    )
                    assert len(res) == 3  # 3 batches (items: 1-10, 11-20, 21)


def test_process_pdf_info_fails_fallback(pipeline):
    """Covers line 77-78 and 126-128 (fallback when total_pages is None)."""
    restored = np.full((20, 20), 255, dtype=np.uint8)
    with patch(
        "blast_ocr.pipeline.pdfinfo_from_path", side_effect=Exception("No poppler")
    ):
        with patch(
            "blast_ocr.pipeline.convert_from_path",
            return_value=["page_1.png", "page_2.png"],
        ):
            with patch(
                "blast_ocr.pipeline.ForensicRestorer.restore", return_value=restored
            ):
                with patch.object(
                    pipeline.parallel_processor,
                    "process_batch_threaded",
                    return_value=[{"page": 1}, {"page": 2}],
                ):
                    res = pipeline.process_pdf("dummy.pdf")
                    assert len(res) == 2


def test_process_pdf_convert_fails_skips_batch(pipeline):
    """Covers batch render failure fallback returning structured error records."""
    with patch("blast_ocr.pipeline.pdfinfo_from_path", return_value={"Pages": 5}):
        with patch(
            "blast_ocr.pipeline.convert_from_path",
            side_effect=Exception("Render error"),
        ):
            res = pipeline.process_pdf("dummy.pdf")
            assert len(res) == 5
            assert all(r.get("status") == "error" for r in res)


def test_process_pdf_cleanup_permission_error(pipeline):
    """Covers lines 132-143 (cleanup Perm error retry exhaust)."""
    restored = np.full((20, 20), 255, dtype=np.uint8)
    with patch("blast_ocr.pipeline.pdfinfo_from_path", return_value={"Pages": 1}):
        with patch("blast_ocr.pipeline.convert_from_path", return_value=["page_1.png"]):
            with patch(
                "blast_ocr.pipeline.ForensicRestorer.restore", return_value=restored
            ):
                with patch.object(
                    pipeline.parallel_processor,
                    "process_batch_threaded",
                    return_value=[],
                ):
                    # Mock shutil.rmtree to always throw PermissionError


                    def mock_rmtree(path, *args, **kwargs):
                        raise PermissionError("Locked dir")

                    with patch("shutil.rmtree", side_effect=mock_rmtree):
                        with patch("time.sleep"):  # avoid actual sleeping for 5 seconds
                            pipeline.process_pdf("dummy.pdf")
                    # Ensure it cleans up after test normally by python GC if tempdir left over


def test_process_pdf_cleanup_generic_error(pipeline):
    """Covers lines 144-146 (cleanup generic Exception -> break)."""
    restored = np.full((20, 20), 255, dtype=np.uint8)
    with patch("blast_ocr.pipeline.pdfinfo_from_path", return_value={"Pages": 1}):
        with patch("blast_ocr.pipeline.convert_from_path", return_value=["page_1.png"]):
            with patch(
                "blast_ocr.pipeline.ForensicRestorer.restore", return_value=restored
            ):
                with patch.object(
                    pipeline.parallel_processor,
                    "process_batch_threaded",
                    return_value=[],
                ):
                    with patch("shutil.rmtree", side_effect=Exception("Hard error")):
                        pipeline.process_pdf("dummy.pdf")


def test_process_image_batch_remove_error(pipeline):
    """Covers line 169-170 (_process_image_batch OSError)."""
    import tempfile

    d = tempfile.mkdtemp()
    # Provide a real dummy page object with a real 'save' method
    from PIL import Image

    page = Image.new("RGB", (10, 10))

    with patch.object(
        pipeline.parallel_processor, "process_batch_threaded", return_value=[]
    ):
        with patch("os.remove", side_effect=OSError("Remove fails")):
            pipeline._process_image_batch([page], d, 1, None)

    # Cleanup actual created file
    try:
        os.remove(os.path.join(d, "page_0001.png"))
        os.rmdir(d)
    except Exception:
        pass


def test_missing_poppler_path(pipeline):
    """Covers poppler path check config blocks."""
    pipeline._config.poppler_path = None
    with patch("blast_ocr.pipeline.pdfinfo_from_path", side_effect=Exception("None")):
        with patch("blast_ocr.pipeline.convert_from_path", return_value=[]):
            pipeline.process_pdf("dummy.pdf")
            # Should run without crashing and use kwargs normally
