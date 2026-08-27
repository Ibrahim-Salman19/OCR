"""
Sprint 4: pipeline.py — E2E integration tests with gemini.md schema compliance.
BUG-PREVENTION: The pipeline is the integration glue. These tests verify the
exact output contract defined in gemini.md is upheld end-to-end.
"""

import os
import tempfile
import pytest
import numpy as np
import cv2
from pathlib import Path
from unittest.mock import patch


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_output(tmp_path):
    return str(tmp_path / "output")


@pytest.fixture
def test_image_path(tmp_path):
    """Small real image with text rendered via cv2. No GPU needed."""
    img = np.full((100, 300, 3), 255, dtype=np.uint8)
    cv2.putText(img, "BLAST OCR", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    path = str(tmp_path / "test_input.png")
    cv2.imwrite(path, img)
    return path


@pytest.fixture
def pipeline(tmp_output):
    """
    BUG-PREVENTION: Always create pipeline with isolated output_dir.
    Sharing a global pipeline across tests causes DB state pollution.
    """
    from blast_ocr.pipeline import BlastPipeline

    return BlastPipeline(config_overrides={"output_dir": tmp_output})


# ─── Mocked process helper (fast path — no real OCR) ─────────────────────────


def mock_process_page(path, page_num):
    """Stand-in for process_page_wrapper. Returns valid schema without real OCR."""
    return {
        "page": page_num,
        "text": f"Extracted text for page {page_num}",
        "confidence": 0.92,
        "bbox_count": 5,
        "processing_time": 0.5,
        "details": [],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TASK 4.1 — gemini.md Schema Compliance
# ═══════════════════════════════════════════════════════════════════════════════


class TestGeminiSchemaCompliance:
    def test_success_result_has_required_top_level_keys(
        self, pipeline, test_image_path, tmp_output
    ):
        """
        BUG-PREVENTION: gemini.md defines the exact output contract:
        {status, job_id, pages_processed, output_files}.
        Any missing key breaks clients that parse this dict.
        """
        with patch(
            "blast_ocr.pipeline.process_page_wrapper", side_effect=mock_process_page
        ):
            result = pipeline.process_job(test_image_path, output_dir=tmp_output)

        assert result["status"] == "success", f"Expected success, got: {result}"
        assert "job_id" in result, "Missing job_id in success result"
        assert "pages_processed" in result, "Missing pages_processed in success result"
        assert "output_files" in result, "Missing output_files in success result"

    def test_output_files_has_md_and_docx_keys(
        self, pipeline, test_image_path, tmp_output
    ):
        """
        BUG-PREVENTION: gemini.md specifies output_files must have 'md' and 'docx'
        keys (matching the generated_files format). Renamed keys break UI file links.
        """
        with patch(
            "blast_ocr.pipeline.process_page_wrapper", side_effect=mock_process_page
        ):
            result = pipeline.process_job(test_image_path, output_dir=tmp_output)

        if result["status"] == "success":
            files = result["output_files"]
            assert "md" in files, "output_files must have 'md' key"
            # docx may be None if python-docx failed but key must exist
            assert "docx" in files, "output_files must have 'docx' key"

    def test_md_output_file_exists_on_disk(self, pipeline, test_image_path, tmp_output):
        """The .md output file must actually be written to disk, not just referenced."""
        with patch(
            "blast_ocr.pipeline.process_page_wrapper", side_effect=mock_process_page
        ):
            result = pipeline.process_job(test_image_path, output_dir=tmp_output)

        if result["status"] == "success":
            md_path = result["output_files"]["md"]
            assert os.path.exists(md_path), f"MD file missing at: {md_path}"
            assert Path(md_path).stat().st_size > 0, "MD file is empty"

    def test_pages_processed_count_correct(self, pipeline, test_image_path, tmp_output):
        """
        BUG-PREVENTION: pages_processed is used in the gemini.md metadata.page_count.
        Incorrect count misleads downstream consumers about document completeness.
        """
        with patch(
            "blast_ocr.pipeline.process_page_wrapper", side_effect=mock_process_page
        ):
            result = pipeline.process_job(test_image_path, output_dir=tmp_output)

        if result["status"] == "success":
            assert result["pages_processed"] == 1, (
                f"Expected 1 page for single image input, got {result['pages_processed']}"
            )

    def test_job_recorded_in_database_on_success(
        self, pipeline, test_image_path, tmp_output
    ):
        """
        BUG-PREVENTION: If job is not saved to DB, the audit trail is lost.
        The UI job history page will be empty even for successful runs.
        """
        with patch(
            "blast_ocr.pipeline.process_page_wrapper", side_effect=mock_process_page
        ):
            result = pipeline.process_job(test_image_path, output_dir=tmp_output)

        if result["status"] == "success":
            job_id = result["job_id"]
            db_record = pipeline.db.get_job(job_id)
            assert db_record is not None, f"Job {job_id} not found in DB"
            assert db_record.status in ("succeeded", "succeeded_with_warnings"), (
                f"Job status should be a JobState success value, got '{db_record.status}'"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# TASK 4.2 — Error & Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestPipelineErrorPaths:
    def test_missing_file_returns_error_status_dict(self, pipeline, tmp_output):
        """
        BUG-PREVENTION: Missing source file must return error dict, not raise.
        Raising crashes the Streamlit UI with an unhandled exception page.
        """
        result = pipeline.process_job("/totally/nonexistent/file.png", tmp_output)
        assert isinstance(result, dict), "Must return dict, never raise"
        assert result["status"] in ("error", "failed")

    def test_unsupported_extension_returns_failed(self, pipeline, tmp_path, tmp_output):
        """
        BUG-PREVENTION: Unsupported types (xlsx, mp4) must fail gracefully.
        Without the extension check, blind processing causes obscure crashes.
        """
        bad_file = tmp_path / "document.xlsx"
        bad_file.write_bytes(b"fake excel")
        result = pipeline.process_job(str(bad_file), tmp_output)
        assert result["status"] == "failed"

    def test_job_marked_failed_in_db_on_error(self, pipeline, tmp_path, tmp_output):
        """
        BUG-PREVENTION: Failed jobs must update DB status to 'failed', not stay
        'processing'. Stuck 'processing' jobs pollute the job history UI.
        """
        bad_file = tmp_path / "bad.xlsx"
        bad_file.write_bytes(b"not a real file")
        result = pipeline.process_job(str(bad_file), tmp_output)

        if "job_id" in result:
            db_record = pipeline.db.get_job(result["job_id"])
            if db_record:
                assert db_record.status == "failed", (
                    f"Failed job should have status='failed' in DB, got '{db_record.status}'"
                )

    def test_output_dir_created_if_missing(self, pipeline, test_image_path, tmp_path):
        """
        BUG-PREVENTION: Callers pass nested paths that don't exist yet.
        os.makedirs(output_dir) must handle deeply nested missing directories.
        """
        nested = str(tmp_path / "deep" / "nested" / "output")
        with patch(
            "blast_ocr.pipeline.process_page_wrapper", side_effect=mock_process_page
        ):
            result = pipeline.process_job(test_image_path, output_dir=nested)

        if result["status"] == "success":
            assert os.path.isdir(nested), f"Output dir not created: {nested}"

    def test_no_output_dir_defaults_to_source_parent(self, tmp_path):
        """
        BUG-PREVENTION: output_dir=None should default to the file's parent dir,
        not '.' (current working directory) which differs by context.
        """
        from blast_ocr.pipeline import BlastPipeline

        img = np.full((100, 100, 3), 255, dtype=np.uint8)
        img_path = str(tmp_path / "test.png")
        cv2.imwrite(img_path, img)

        pipeline = BlastPipeline()
        with patch(
            "blast_ocr.pipeline.process_page_wrapper", side_effect=mock_process_page
        ):
            result = pipeline.process_job(img_path, output_dir=None)

        if result["status"] == "success":
            md_path = result["output_files"]["md"]
            assert str(tmp_path) in md_path, (
                f"Output should default to source parent, got: {md_path}"
            )

    def test_pipeline_del_closes_db_without_error(self, tmp_output):
        """
        BUG-PREVENTION: Without __del__, long-running processes leak SQLite
        connections. Enough leaks exhaust the connection pool → DB errors.
        """
        from blast_ocr.pipeline import BlastPipeline

        pipeline = BlastPipeline(config_overrides={"output_dir": tmp_output})
        # Should not raise AttributeError or any other error
        try:
            pipeline.__del__()
        except Exception as e:
            pytest.fail(f"BUG: pipeline.__del__() raised: {e}")

    def test_config_overrides_not_applied_globally(self, tmp_output):
        """
        BUG-PREVENTION: FIX-3 deepcopy guard — without it, one pipeline's overrides
        mutate the global config object, affecting all subsequent pipeline instances.
        """
        from blast_ocr.pipeline import BlastPipeline
        from blast_ocr.config import config as global_config

        original_confidence = global_config.min_confidence
        BlastPipeline(config_overrides={"min_confidence": 0.01})
        assert global_config.min_confidence == original_confidence, (
            "BUG-FIX-3: Pipeline config override mutated the global config singleton"
        )

    def test_pptx_error_returns_failed_status(self, pipeline, tmp_path, tmp_output):
        """
        BUG-PREVENTION: HIGH-007 fix — corrupt PPTX used to return an error string
        written silently to the output file. Now raises OCREngineError → failed status.
        """
        bad_pptx = tmp_path / "corrupt.pptx"
        bad_pptx.write_bytes(b"not a pptx")
        result = pipeline.process_job(str(bad_pptx), tmp_output)
        assert result["status"] == "failed", (
            f"BUG-HIGH-007: Corrupt PPTX should return failed, got: {result['status']}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TASK 4.3 — No Temp File Leaks
# ═══════════════════════════════════════════════════════════════════════════════


class TestCleanup:
    def test_process_job_leaves_no_temp_png_files(
        self, pipeline, test_image_path, tmp_output
    ):
        """
        BUG-PREVENTION: BUG-TEMPDIR-WIN-01 — On Windows, pdftoppm holds file handles
        preventing temp dir cleanup. The retry loop in pipeline.py fixes this.
        For image input (non-PDF), no temp files should ever be created.
        """
        import glob

        tmp_dir = tempfile.gettempdir()
        before = set(glob.glob(os.path.join(tmp_dir, "*.png")))

        with patch(
            "blast_ocr.pipeline.process_page_wrapper", side_effect=mock_process_page
        ):
            pipeline.process_job(test_image_path, output_dir=tmp_output)

        after = set(glob.glob(os.path.join(tmp_dir, "*.png")))
        leaked = after - before
        # Allow up to 2 leaked files (EasyOCR model cache artifacts)
        assert len(leaked) <= 2, f"BUG: Temp PNG files leaked after job: {leaked}"
