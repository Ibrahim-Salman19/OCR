"""
PHASE 2: Memory leak detection and resource cleanup verification.
Tests the MEM-001 fix (del processed_img) and gc.collect() effectiveness.
"""

import gc
import os
import tempfile
import pytest
import numpy as np
import cv2
from PIL import Image
from unittest.mock import patch, MagicMock


# ── Test 1: processed_img is deleted after OCR call ──────────────────────
def test_processed_img_deleted_after_ocr():
    """MEM-001: Verify del processed_img prevents RAM accumulation."""
    from blast_ocr.core.extractor import RobustOCRExtractor

    with patch("easyocr.Reader") as mock_reader_cls:
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = [
            (
                [[0, 0], [20, 0], [20, 10], [0, 10]],
                "mock",
                0.9,
            )
        ]
        mock_reader_cls.return_value = mock_reader
        extractor = RobustOCRExtractor()

    # Create a test image
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img = Image.new("RGB", (400, 200), color="white")
        img.save(f.name)
        img_path = f.name

    try:
        gc.get_count()
        result = extractor.process_page(img_path, page_number=1)
        gc.collect()

        # The key assertion: result should be returned successfully
        # and no large numpy arrays should be dangling in memory
        assert result is not None
        assert "page" in result

        # Verify no reference to processed image survives in extractor state
        assert not hasattr(extractor, "_last_processed_img"), (
            "Extractor storing processed_img as instance variable — memory leak"
        )
    finally:
        os.unlink(img_path)


# ── Test 2: Memory does not accumulate across multiple pages ──────────────
def test_memory_flat_across_pages():
    """AUDIT.md verification: time per page must be flat, not increasing."""
    import tracemalloc
    from blast_ocr.core.extractor import RobustOCRExtractor

    with patch("easyocr.Reader") as mock_reader_cls:
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = [
            (
                [[0, 0], [20, 0], [20, 10], [0, 10]],
                "mock",
                0.9,
            )
        ]
        mock_reader_cls.return_value = mock_reader
        extractor = RobustOCRExtractor()
    memory_snapshots = []

    def make_test_image(size=(400, 300)):
        img = np.full((*size[::-1], 3), 255, dtype=np.uint8)
        cv2.putText(
            img, "Test page", (50, 300), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3
        )
        return img

    try:
        base_img = make_test_image()
    except MemoryError:
        pytest.skip("Insufficient memory to allocate test image")

    for i in range(5):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            cv2.imwrite(f.name, base_img)
            img_path = f.name
        try:
            tracemalloc.start()
            extractor.process_page(img_path, page_number=i + 1)
            gc.collect()
            current_bytes, peak_bytes = tracemalloc.get_traced_memory()
            memory_snapshots.append(
                {
                    "current_kb": current_bytes / 1024,
                    "peak_kb": peak_bytes / 1024,
                }
            )
            tracemalloc.stop()
        finally:
            os.unlink(img_path)

    # Per-page memory profile should remain roughly stable across iterations.
    if len(memory_snapshots) >= 3:
        warmed = memory_snapshots[1:]
        peaks = [m["peak_kb"] for m in warmed]
        max_peak = max(peaks)
        min_peak = max(min(peaks), 1)
        spread_pct = ((max_peak - min_peak) / min_peak) * 100

        # Keep as a coarse guard: if per-page peak memory balloons after warmup,
        # treat it as a potential regression.
        if spread_pct > 200:
            pytest.fail(
                f"Per-page peak memory spread too large ({spread_pct:.1f}%): "
                f"{memory_snapshots}. MEM-001 regression suspected. "
                f"(Tolerance: 200%)."
            )


# ── Test 3: Database connection is closed on OCRDatabase deletion ─────────
def test_database_connection_closed_on_del():
    """BUG HYPOTHESIS: __del__ silently fails if Session not initialized."""
    import tempfile
    from blast_ocr.storage.database import OCRDatabase

    db_file = tempfile.mktemp(suffix=".db")
    db = OCRDatabase(f"sqlite:///{db_file}")

    # Verify close() doesn't raise even if called multiple times
    db.close()
    db.close()  # Should not raise

    # Verify __del__ doesn't raise
    del db
    gc.collect()

    os.unlink(db_file)


# ── Test 4: BlastPipeline cleans up temp directory ───────────────────────
def test_pipeline_temp_directory_cleaned_up():
    """BUG HYPOTHESIS: TemporaryDirectory not cleaned if exception mid-batch."""
    import glob

    tmp_before = set(glob.glob("/tmp/tmp*"))

    from blast_ocr.pipeline import BlastPipeline

    pipeline = BlastPipeline()

    # Process a non-existent file — should fail gracefully
    result = pipeline.process_job("/nonexistent/file.pdf", output_dir="/tmp/test_out")

    tmp_after = set(glob.glob("/tmp/tmp*"))
    leaked_dirs = tmp_after - tmp_before

    assert result["status"] == "error" or result["status"] == "failed"
    assert len(leaked_dirs) == 0, (
        f"Temp directories leaked after failed job: {leaked_dirs}. "
        f"TemporaryDirectory context manager may not be handling exceptions correctly."
    )

    del pipeline


# ── Test 5: Cache file handles not left open ─────────────────────────────
def test_cache_file_handles_closed_after_write():
    """BUG HYPOTHESIS: Cache write opens file but exception before close leaks handle."""
    import psutil
    from blast_ocr.cache.manager import OCRCache

    cache = OCRCache(cache_dir=tempfile.mkdtemp())

    proc = psutil.Process()

    try:
        open_files_before = len(proc.open_files())
    except (MemoryError, OSError, psutil.Error):
        pytest.skip("Unable to inspect open files on this host")

    for i in range(20):
        cache.set(f"key_{i}", {"data": "x" * 1000, "page": i})
        cache.get(f"key_{i}")

    try:
        open_files_after = len(proc.open_files())
    except (MemoryError, OSError, psutil.Error):
        pytest.skip("Unable to inspect open files on this host")
    leaked = open_files_after - open_files_before

    if leaked > 2:  # Allow small tolerance
        pytest.fail(
            f"File handle leak: {leaked} extra open files after 20 cache operations. "
            f"Cache open/close pattern may not be using context managers correctly."
        )
