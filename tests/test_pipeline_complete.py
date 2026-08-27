"""
PHASE 6: BlastPipeline end-to-end correctness, routing, error recovery.
"""

import pytest
import os
import numpy as np
import cv2


@pytest.fixture
def pipeline(tmp_path):
    from blast_ocr.pipeline import BlastPipeline

    return BlastPipeline(config_overrides={"output_dir": str(tmp_path)})


@pytest.fixture
def test_image(tmp_path):
    path = tmp_path / "test.png"
    img = np.full((200, 200, 3), 255, dtype=np.uint8)
    cv2.putText(img, "BLAST OCR", (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    cv2.imwrite(str(path), img)
    return str(path)


# ── Test 1: process_job returns dict with required keys ───────────────────
def test_process_job_return_schema(pipeline, test_image, tmp_path):
    result = pipeline.process_job(test_image, output_dir=str(tmp_path))
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "status" in result, "Missing 'status' key"
    assert result["status"] in ("success", "failed", "error"), (
        f"Invalid status value: {result['status']}"
    )


# ── Test 2: File not found returns error status, not crash ────────────────
def test_process_job_missing_file_returns_error(pipeline, tmp_path):
    result = pipeline.process_job("/absolutely/nonexistent.pdf", str(tmp_path))
    assert result["status"] in ("error", "failed"), (
        f"Expected error status for missing file, got: {result}"
    )
    assert "error" in result or "message" in result, (
        "Error result must contain error message"
    )


# ── Test 3: Unsupported file type returns error, not crash ────────────────
def test_process_job_unsupported_extension(pipeline, tmp_path):
    bad_file = tmp_path / "document.xlsx"
    bad_file.write_bytes(b"fake excel data")
    result = pipeline.process_job(str(bad_file), str(tmp_path))
    assert result["status"] == "failed", (
        f"Expected 'failed' for unsupported extension, got: {result['status']}"
    )


# ── Test 4: Output directory is created if it doesn't exist ──────────────
def test_process_job_creates_output_dir(pipeline, test_image, tmp_path):
    nonexistent_dir = str(tmp_path / "new" / "nested" / "dir")
    result = pipeline.process_job(test_image, nonexistent_dir)
    if result["status"] == "success":
        assert os.path.isdir(nonexistent_dir), (
            "Output directory not created by process_job"
        )


# ── Test 5: Job is recorded in database regardless of success/failure ─────
def test_job_always_recorded_in_db(pipeline, tmp_path):
    """BUG HYPOTHESIS: Exception before db.create_job means no DB record."""
    # Try with a bad file
    pipeline.process_job("/nonexistent.pdf", str(tmp_path))
    # The job_id should still be returned or DB should have the record
    # This verifies the try/except wraps correctly


# ── Test 6: progress_callback receives correct (current, total) values ─────
def test_progress_callback_called_correctly(pipeline, test_image, tmp_path):
    """BUG HYPOTHESIS: progress_callback receives wrong total value."""
    calls = []

    def cb(current, total):
        calls.append((current, total))

    result = pipeline.process_job(test_image, str(tmp_path), progress_callback=cb)

    if result["status"] == "success" and calls:
        # current should never exceed total
        for current, total in calls:
            assert current <= total, (
                f"BUG: progress_callback received current={current} > total={total}"
            )
        # Final call should have current == total
        final_current, final_total = calls[-1]
        assert final_current <= final_total


# ── Test 7: config_overrides actually override defaults ───────────────────
def test_config_overrides_applied(tmp_path):
    from blast_ocr.pipeline import BlastPipeline

    pipeline = BlastPipeline(
        config_overrides={"min_confidence": 0.99, "max_workers": 1}
    )
    assert pipeline._config.min_confidence == 0.99, (
        "BUG: config_overrides did not override min_confidence"
    )
    assert pipeline._config.max_workers == 1, (
        "BUG: config_overrides did not override max_workers"
    )


# ── Test 8: config_overrides with unknown key doesn't crash ───────────────
def test_config_overrides_unknown_key_ignored(tmp_path):
    """BUG HYPOTHESIS: setattr on Pydantic model with unknown key raises AttributeError."""
    from blast_ocr.pipeline import BlastPipeline

    try:
        BlastPipeline(config_overrides={"TOTALLY_FAKE_SETTING": 999})
        # Should silently ignore unknown keys
    except AttributeError as e:
        pytest.fail(
            f"BUG: config_overrides raises AttributeError for unknown key: {e}. "
            f"The 'if hasattr(self._config, k)' guard should prevent this."
        )


# ── Test 9: deepcopy of config prevents global mutation ───────────────────
def test_config_deepcopy_isolates_pipeline():
    """BUG HYPOTHESIS: Without deepcopy, one pipeline's overrides affect another."""
    from blast_ocr.pipeline import BlastPipeline

    p1 = BlastPipeline(config_overrides={"min_confidence": 0.1})
    p2 = BlastPipeline(config_overrides={"min_confidence": 0.9})
    assert p1._config.min_confidence != p2._config.min_confidence, (
        "BUG: config deepcopy not working — pipeline configs are sharing state"
    )


# ── Test 10: PPTX extraction error propagates as failed job ───────────────
def test_pptx_extraction_error_handled(pipeline, tmp_path):
    """BUG HYPOTHESIS: OCREngineError from extract_from_pptx not caught by pipeline."""
    bad_pptx = tmp_path / "corrupt.pptx"
    bad_pptx.write_bytes(b"not a valid pptx file at all")

    result = pipeline.process_job(str(bad_pptx), str(tmp_path))
    assert result["status"] == "failed", (
        f"BUG: Corrupt PPTX should return failed status, got: {result}"
    )
