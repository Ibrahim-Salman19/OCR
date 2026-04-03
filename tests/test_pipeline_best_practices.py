from unittest.mock import MagicMock, patch

import numpy as np
import cv2


def _mock_db():
    db = MagicMock()
    db.create_job.return_value = 1
    db.update_job_status.return_value = None
    db.update_job_page_count.return_value = None
    db.save_result.return_value = None
    db.save_metric.return_value = None
    return db


def test_large_pdf_temporary_parallelism_is_restored():
    from blast_ocr.pipeline import BlastPipeline

    pipeline = BlastPipeline()
    pipeline.parallel_processor.max_workers = 3

    with patch("blast_ocr.pipeline.pdfinfo_from_path", return_value={"Pages": 501}):
        with patch("blast_ocr.pipeline.convert_from_path", return_value=[]):
            with patch.object(pipeline, "_process_image_batch", return_value=[]):
                pipeline.process_pdf("dummy.pdf")

    assert pipeline.parallel_processor.max_workers == 3


def test_secure_mode_redacts_directory_results(tmp_path):
    from blast_ocr.pipeline import BlastPipeline

    source_dir = tmp_path / "images"
    source_dir.mkdir()
    (source_dir / "a.png").write_bytes(b"placeholder")

    pipeline = BlastPipeline()
    pipeline.db = _mock_db()
    pipeline._config.secure_mode = True

    with patch.object(
        pipeline.parallel_processor,
        "process_batch_threaded",
        return_value=[
            {
                "page": 1,
                "text": "Contact me at alice@example.com",
                "confidence": 0.9,
                "processing_time": 0.1,
            }
        ],
    ):
        with patch(
            "blast_ocr.pipeline.save_output",
            return_value=(str(tmp_path / "o.md"), str(tmp_path / "o.docx")),
        ):
            result = pipeline.process_job(str(source_dir), output_dir=str(tmp_path))

    assert result["status"] == "success"
    saved_text = pipeline.db.save_result.call_args[0][2]
    assert "[REDACTED-EMAIL]" in saved_text
    assert "alice@example.com" not in saved_text


def test_secure_mode_redacts_single_image_route(tmp_path):
    from blast_ocr.pipeline import BlastPipeline

    img_path = tmp_path / "one.png"
    img = np.full((40, 40, 3), 255, dtype=np.uint8)
    cv2.imwrite(str(img_path), img)

    pipeline = BlastPipeline()
    pipeline.db = _mock_db()
    pipeline._config.secure_mode = True

    with patch(
        "blast_ocr.pipeline.process_page_wrapper",
        return_value={
            "page": 1,
            "text": "SSN 111-22-3333",
            "confidence": 0.95,
            "processing_time": 0.2,
        },
    ):
        with patch(
            "blast_ocr.pipeline.save_output",
            return_value=(str(tmp_path / "o.md"), str(tmp_path / "o.docx")),
        ):
            result = pipeline.process_job(str(img_path), output_dir=str(tmp_path))

    assert result["status"] == "success"
    saved_text = pipeline.db.save_result.call_args[0][2]
    assert "[REDACTED-SSN]" in saved_text
    assert "111-22-3333" not in saved_text


def test_secure_mode_redacts_pptx_route(tmp_path):
    from blast_ocr.pipeline import BlastPipeline

    pptx_path = tmp_path / "slides.pptx"
    pptx_path.write_bytes(b"placeholder")

    pipeline = BlastPipeline()
    pipeline.db = _mock_db()
    pipeline._config.secure_mode = True

    with patch(
        "blast_ocr.pipeline.extract_from_pptx",
        return_value="Card 4111 1111 1111 1111",
    ):
        with patch(
            "blast_ocr.pipeline.save_output",
            return_value=(str(tmp_path / "o.md"), str(tmp_path / "o.docx")),
        ):
            result = pipeline.process_job(str(pptx_path), output_dir=str(tmp_path))

    assert result["status"] == "success"
    saved_text = pipeline.db.save_result.call_args[0][2]
    assert "[REDACTED-CARD]" in saved_text
    assert "4111 1111 1111 1111" not in saved_text


def test_secure_mode_off_does_not_redact_single_image(tmp_path):
    from blast_ocr.pipeline import BlastPipeline

    img_path = tmp_path / "two.png"
    img = np.full((40, 40, 3), 255, dtype=np.uint8)
    cv2.imwrite(str(img_path), img)

    pipeline = BlastPipeline()
    pipeline.db = _mock_db()
    pipeline._config.secure_mode = False

    with patch(
        "blast_ocr.pipeline.process_page_wrapper",
        return_value={
            "page": 1,
            "text": "Reach me at bob@example.com",
            "confidence": 0.95,
            "processing_time": 0.2,
        },
    ):
        with patch(
            "blast_ocr.pipeline.save_output",
            return_value=(str(tmp_path / "o.md"), str(tmp_path / "o.docx")),
        ):
            result = pipeline.process_job(str(img_path), output_dir=str(tmp_path))

    assert result["status"] == "success"
    saved_text = pipeline.db.save_result.call_args[0][2]
    assert "bob@example.com" in saved_text
    assert "[REDACTED-EMAIL]" not in saved_text
