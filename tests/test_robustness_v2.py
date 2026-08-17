"""
PHASE 9: Advanced Robustness, Security, and Hardware Resilience Tests.
These tests target the remediations from v2.0 forensic audit.
"""

import pytest
import os
import tempfile
import threading
import numpy as np
from unittest.mock import MagicMock, patch
from hypothesis import given, settings, strategies as st
from blast_ocr.pipeline import BlastPipeline
from blast_ocr.storage.database import OCRDatabase
from blast_ocr.core.extractor import RobustOCRExtractor


@pytest.fixture
def mocked_extractor():
    with patch("easyocr.Reader") as mock_reader_cls:
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = [
            (
                [[0, 0], [10, 0], [10, 10], [0, 10]],
                "mock",
                0.95,
            )
        ]
        mock_reader_cls.return_value = mock_reader
        yield RobustOCRExtractor()


# ── Test 1: SQL Injection Protection (Parameterized Queries) ───────────────
def test_db_sqli_protection():
    """Verify that malicious filenames do not trigger SQL injection."""
    db_file = tempfile.mktemp(suffix=".db")
    db = OCRDatabase(f"sqlite:///{db_file}")

    # Payload designed to break out of unparameterized strings
    malicious_name = "test'); DROP TABLE jobs; --.pdf"

    try:
        job_id = db.create_job(malicious_name, 1)
        # Check if table still exists
        job = db.get_job(job_id)
        assert job is not None
        assert job.filename == malicious_name
        assert job.status == "received"  # JobState.RECEIVED (see ADR 0009)
    finally:
        db.close()
        if os.path.exists(db_file):
            os.unlink(db_file)


# ── Test 2: Fuzzing — Corrupt/Binary Head-Garbage Files ────────────────────
@given(st.binary(min_size=10, max_size=1000))
@settings(max_examples=20, deadline=None)
def test_pipeline_fuzz_corrupt_headers(content):
    """Ensure the pipeline fails gracefully on garbage binary input."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(content)
        path = f.name

    try:
        pipeline = BlastPipeline()
        result = pipeline.process_job(path)
        # Status should be failed, but process must NOT crash or hang
        assert result["status"] == "failed"
        # Garbage bytes are now often rejected earlier, at the IngestionGateway
        # security boundary (magic-byte mismatch), rather than deeper inside PDF
        # extraction -- both are valid "failed gracefully with a reason" outcomes.
        error_text = result.get("error", "").lower()
        assert error_text, "Failure must carry a non-empty error message"
        assert any(
            phrase in error_text
            for phrase in ("extraction failed", "error", "magic bytes", "security validation")
        )
    finally:
        if os.path.exists(path):
            os.unlink(path)


# ── Test 3: Hardware Resilience — CUDA Out-Of-Memory Mock ──────────────────
def test_extractor_handles_cuda_oom_gracefully(mocked_extractor):
    """Verify that a GPU OOM error is caught and converted to OCREngineError."""
    extractor = mocked_extractor
    # Mock EasyOCR reader attribute
    extractor.reader = MagicMock()
    extractor.reader.readtext.side_effect = RuntimeError("CUDA out of memory")

    img = np.zeros((100, 100, 3), dtype=np.uint8)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        import cv2

        cv2.imwrite(f.name, img)
        path = f.name

    try:
        from blast_ocr.core.exceptions import OCREngineError, PageExtractionError

        # The extractor wraps core errors in PageExtractionError
        with pytest.raises((OCREngineError, PageExtractionError)):
            extractor.process_page(path, 1)
    finally:
        if os.path.exists(path):
            os.remove(path)


# ── Test 4: Resource Cleanup — Explicit GC Trigger Verification ───────────
@patch("gc.collect")
def test_extractor_triggers_gc_after_page(mock_gc, mocked_extractor):
    """Ensure gc.collect() is called during page processing (Low Priority BUG-MEM-GC-01)."""
    extractor = mocked_extractor
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        import cv2

        cv2.imwrite(f.name, img)
        path = f.name

    try:
        extractor.process_page(path, 1)
        # Verify GC was triggered at least once
        assert mock_gc.called, "gc.collect() was not called after page processing"
    finally:
        if os.path.exists(path):
            os.unlink(path)


# ── Test 5: Concurrency Stress — 20 simultaneous job objects ──────────────
def test_pipeline_high_concurrency_stress():
    """Stress test the pipeline orchestration with 20 parallel jobs."""
    pipeline = BlastPipeline()
    results = []

    def run_dummy_job(i):
        # Use an empty file which should fail gracefully
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"NOT A PDF")
            path = f.name
        try:
            res = pipeline.process_job(path)
            results.append(res)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    threads = [threading.Thread(target=run_dummy_job, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 20
    # All should be 'failed' because input isn't a PDF, but none should CRASH
    assert all(r["status"] == "failed" for r in results)
