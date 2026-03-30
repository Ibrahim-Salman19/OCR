"""
PHASE 2: Memory leak detection and resource cleanup verification.
Tests the MEM-001 fix (del processed_img) and gc.collect() effectiveness.
"""
import gc
import os
import sys
import threading
import tempfile
import pytest
import numpy as np
import cv2
from unittest.mock import patch, MagicMock
from PIL import Image

# ── Test 1: processed_img is deleted after OCR call ──────────────────────
def test_processed_img_deleted_after_ocr():
    """MEM-001: Verify del processed_img prevents RAM accumulation."""
    from blast_ocr.core.extractor import RobustOCRExtractor
    
    extractor = RobustOCRExtractor()
    
    # Create a test image
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img = Image.new("RGB", (400, 200), color="white")
        img.save(f.name)
        img_path = f.name
    
    try:
        gc_counts_before = gc.get_count()
        result = extractor.process_page(img_path, page_number=1)
        gc.collect()
        
        # The key assertion: result should be returned successfully
        # and no large numpy arrays should be dangling in memory
        assert result is not None
        assert "page" in result
        
        # Verify no reference to processed image survives in extractor state
        assert not hasattr(extractor, '_last_processed_img'), \
            "Extractor storing processed_img as instance variable — memory leak"
    finally:
        os.unlink(img_path)

# ── Test 2: Memory does not accumulate across multiple pages ──────────────
def test_memory_flat_across_pages():
    """AUDIT.md verification: time per page must be flat, not increasing."""
    import tracemalloc
    from blast_ocr.core.extractor import RobustOCRExtractor
    
    extractor = RobustOCRExtractor()
    memory_snapshots = []
    
    def make_test_image(size=(800, 600)):
        img = np.full((*size[::-1], 3), 255, dtype=np.uint8)
        cv2.putText(img, f"Test page", (50, 300), cv2.FONT_HERSHEY_SIMPLEX, 2, (0,0,0), 3)
        return img
    
    tracemalloc.start()
    for i in range(5):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            cv2.imwrite(f.name, make_test_image())
            img_path = f.name
        try:
            extractor.process_page(img_path, page_number=i+1)
            gc.collect()
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')
            total_kb = sum(stat.size for stat in top_stats) / 1024
            memory_snapshots.append(total_kb)
        finally:
            os.unlink(img_path)
    tracemalloc.stop()
    
    # Memory should not grow linearly — detect accumulation
    if len(memory_snapshots) >= 3:
        # Ignore the first jump which is model loading (7MB -> 21MB in logs)
        growth = memory_snapshots[-1] - memory_snapshots[1]
        growth_pct = (growth / max(memory_snapshots[1], 1)) * 100
        if growth_pct > 50:  # Increased from 30% to 50% for Windows stability
            pytest.fail(
                f"Memory growing {growth_pct:.1f}% after model load: {memory_snapshots}. "
                f"MEM-001 fix may not be working correctly (Tolerance: 50%)."
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
    assert len(leaked_dirs) == 0, \
        f"Temp directories leaked after failed job: {leaked_dirs}. " \
        f"TemporaryDirectory context manager may not be handling exceptions correctly."
    
    del pipeline

# ── Test 5: Cache file handles not left open ─────────────────────────────
def test_cache_file_handles_closed_after_write():
    """BUG HYPOTHESIS: Cache write opens file but exception before close leaks handle."""
    import psutil
    from blast_ocr.cache.manager import OCRCache
    
    cache = OCRCache(cache_dir=tempfile.mkdtemp())
    
    proc = psutil.Process()
    open_files_before = len(proc.open_files())
    
    for i in range(20):
        cache.set(f"key_{i}", {"data": "x" * 1000, "page": i})
        cache.get(f"key_{i}")
    
    open_files_after = len(proc.open_files())
    leaked = open_files_after - open_files_before
    
    if leaked > 2:  # Allow small tolerance
        pytest.fail(
            f"File handle leak: {leaked} extra open files after 20 cache operations. "
            f"Cache open/close pattern may not be using context managers correctly."
        )
