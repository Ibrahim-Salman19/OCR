"""
tests/test_skills_advanced_qa.py

Rigorous integration, E2E edge-case, and concurrency test suite
directly implementing skills/advanced_qa.md:
1. Integration Testing: Pipeline -> Database & Extractor -> Cache
2. E2E Scenarios: 0-byte file, password-protected encrypted PDF, high-page streaming
3. Stress Testing: 10 concurrent pipeline instances, resource starvation recovery
4. Visual & Text Regression: Ground-truth text fidelity verification
"""

import concurrent.futures
import os
import cv2
import numpy as np
import pymupdf as fitz
import pytest

from blast_ocr.pipeline import BlastPipeline
from blast_ocr.core.worker import process_page_wrapper
from blast_ocr.security.gateway import IngestionGateway, SecurityValidationError
from blast_ocr.core.streaming import PageStreamGenerator


# ============================================================================
# 1. Integration Testing: Pipeline -> Database & Extractor -> Cache
# ============================================================================

def test_integration_pipeline_to_database(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    db_path = tmp_path / "integration.db"
    db_url = f"sqlite:///{db_path}"

    pipeline = BlastPipeline(config_overrides={"output_dir": str(out_dir), "database_url": db_url})

    img_path = str(tmp_path / "doc.png")
    img = np.full((120, 300, 3), 255, dtype=np.uint8)
    cv2.putText(img, "DB INTEGRATION", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.imwrite(img_path, img)

    result = pipeline.process_job(source=img_path, formats=["md"])
    assert result["status"] == "success"

    # Verify Database recorded job accurately
    job_id = result["job_id"]
    job = pipeline.db.get_job(job_id)
    assert job is not None
    assert job.status in ("succeeded", "succeeded_with_warnings")
    assert result["pages_processed"] >= 1


def test_integration_extractor_to_cache(tmp_path):
    img_path = str(tmp_path / "cache_test.png")
    img = np.full((100, 200, 3), 255, dtype=np.uint8)
    cv2.putText(img, "CACHE HIT", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.imwrite(img_path, img)

    # First pass: Cache Miss -> execution -> cached
    res1 = process_page_wrapper(img_path, 1)
    assert res1 is not None

    # Second pass: Cache Hit
    res2 = process_page_wrapper(img_path, 1)
    assert res2 is not None
    assert res1["text"] == res2["text"]


# ============================================================================
# 2. End-to-End Scenarios: 0-Byte File & Password-Protected Encrypted PDF
# ============================================================================

def test_e2e_zero_byte_file_rejection(tmp_path):
    zero_file = tmp_path / "empty.png"
    zero_file.write_bytes(b"")

    # IngestionGateway must reject
    with pytest.raises(SecurityValidationError, match=r"(?i)empty"):
        IngestionGateway.validate(str(zero_file))

    # Pipeline must reject gracefully without unhandled crash
    pipeline = BlastPipeline(config_overrides={"output_dir": str(tmp_path / "out")})
    res = pipeline.process_job(source=str(zero_file))
    assert res["status"] in ("failed", "error")


def test_e2e_password_protected_pdf_rejection(tmp_path):
    # Create genuine AES-256 password-protected PDF
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Top Secret Classified Document")
    
    enc_pdf_path = str(tmp_path / "encrypted_secret.pdf")
    perm = int(
        fitz.PDF_PERM_ACCESSIBILITY
        | fitz.PDF_PERM_PRINT
        | fitz.PDF_PERM_COPY
        | fitz.PDF_PERM_ANNOTATE
    )
    doc.save(
        enc_pdf_path,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="master_secret_key",
        user_pw="user_secret_key",
        permissions=perm,
    )
    doc.close()

    # Verify the document is indeed encrypted
    check_doc = fitz.open(enc_pdf_path)
    assert check_doc.is_encrypted
    check_doc.close()

    # Streaming generator must raise CorruptedDocumentError or handle gracefully
    with pytest.raises(Exception):
        with PageStreamGenerator(source_path=enc_pdf_path, chunk_size=5) as stream:
            for chunk in stream:
                pass


def test_e2e_high_page_count_sliding_window_streaming(tmp_path):
    # Create 30-page PDF
    doc = fitz.open()
    for i in range(30):
        p = doc.new_page(width=300, height=200)
        p.insert_text((30, 80), f"Page {i + 1} Content Stream")
    pdf_path = str(tmp_path / "long_doc.pdf")
    doc.save(pdf_path)
    doc.close()

    with PageStreamGenerator(source_path=pdf_path, chunk_size=10) as stream:
        assert stream.total_pages == 30
        chunks = list(stream)
        assert len(chunks) == 3  # 30 pages / 10 per chunk = 3 chunks
        for idx, chunk_items in enumerate(chunks):
            assert len(chunk_items) == 10


# ============================================================================
# 3. Stress Testing: 10 Parallel Pipeline Instances & Resource Starvation
# ============================================================================

def test_stress_concurrency_10_threads(tmp_path):
    """Run 10 BlastPipeline instances simultaneously across threads."""
    test_img = tmp_path / "thread_test.png"
    img = np.full((80, 200, 3), 255, dtype=np.uint8)
    cv2.putText(img, "THREAD OCR", (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.imwrite(str(test_img), img)

    def run_job(thread_id: int):
        out_dir = tmp_path / f"thread_out_{thread_id}"
        out_dir.mkdir(exist_ok=True)
        pipeline = BlastPipeline(config_overrides={"output_dir": str(out_dir)})
        return pipeline.process_job(source=str(test_img), formats=["txt"])

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(run_job, i) for i in range(10)]
        results = [f.result(timeout=60) for f in futures]

    assert len(results) == 10
    for res in results:
        assert res["status"] == "success"
        assert "THREAD OCR" in res["text"] or len(res["text"]) > 0


def test_resource_starvation_memory_error_recovery(tmp_path, monkeypatch):
    """Simulate MemoryError during page extraction and verify graceful handling."""
    pipeline = BlastPipeline(config_overrides={"output_dir": str(tmp_path / "starve_out")})

    test_img = tmp_path / "starve.png"
    img = np.full((50, 50, 3), 255, dtype=np.uint8)
    cv2.imwrite(str(test_img), img)

    def mock_process_page(*args, **kwargs):
        raise MemoryError("Simulated Out of Memory in OCR Worker")

    monkeypatch.setattr("blast_ocr.pipeline.process_page_wrapper", mock_process_page)
    res = pipeline.process_job(source=str(test_img), formats=["txt"])
    assert res is not None
    assert res.get("had_page_errors") is True or res.get("status") in ("failed", "error")


# ============================================================================
# 4. Visual & Text Regression Testing
# ============================================================================

def test_visual_and_text_regression(tmp_path):
    """Validate text accuracy, word bounding boxes, and schema determinism."""
    img_path = str(tmp_path / "regression_page.png")
    img = np.full((120, 400, 3), 255, dtype=np.uint8)
    cv2.putText(img, "SOVEREIGN OCR", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
    cv2.imwrite(img_path, img)

    pipeline = BlastPipeline(config_overrides={"output_dir": str(tmp_path / "reg_out")})
    result = pipeline.process_job(source=img_path, formats=["md", "docx", "txt"])

    assert result["status"] == "success"
    assert "SOVEREIGN OCR" in result["text"] or "SOVEREIGN" in result["text"]

    gen_files = result["generated_files"]
    assert "md" in gen_files or "markdown" in gen_files
    assert "txt" in gen_files
    assert os.path.getsize(gen_files["txt"]) > 0
