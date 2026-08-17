"""
tests/test_searchable_pdf.py

Unit and integration tests for Searchable PDF (Sandwich PDF) Generator.
"""

import os
from pathlib import Path
import numpy as np
import cv2
import fitz
import pytest

from blast_ocr.core.searchable_pdf import SearchablePDFGenerator
from blast_ocr.core.document_model import Page, Block, Line, Span, BoundingBox


@pytest.fixture
def sample_image(tmp_path):
    img_path = str(tmp_path / "sample_scan.png")
    img = np.full((600, 800, 3), 255, dtype=np.uint8)
    cv2.putText(img, "Chapter 1: The Sovereign Architecture", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(img, "Deterministic OCR automation protocol.", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.imwrite(img_path, img)
    return img_path


def test_create_searchable_pdf_from_details(sample_image, tmp_path):
    out_pdf = str(tmp_path / "output_searchable.pdf")
    ocr_results = [{
        "details": [
            {"text": "Chapter 1: The Sovereign Architecture", "conf": 0.98, "bbox": [50, 75, 550, 115]},
            {"text": "Deterministic OCR automation protocol.", "conf": 0.95, "bbox": [50, 175, 600, 215]},
        ]
    }]

    res_path = SearchablePDFGenerator.create_from_page_images(
        page_images=[sample_image],
        page_ocr_results=ocr_results,
        output_pdf_path=out_pdf,
        title="Architecture Document",
    )

    assert os.path.exists(res_path)
    doc = fitz.open(res_path)
    assert len(doc) == 1
    page_text = doc[0].get_text()
    assert "Chapter 1: The Sovereign Architecture" in page_text
    assert "Deterministic OCR automation protocol." in page_text
    assert doc.metadata.get("title") == "Architecture Document"
    doc.close()


def test_create_searchable_pdf_from_page_model(sample_image, tmp_path):
    out_pdf = str(tmp_path / "output_model.pdf")
    span1 = Span(text="First Model Span", bbox=BoundingBox(xmin=50, ymin=50, xmax=300, ymax=90), confidence=0.99)
    line1 = Line(spans=[span1], bbox=span1.bbox)
    block1 = Block(lines=[line1], bbox=span1.bbox)
    page_model = Page(page_num=1, width=800, height=600, blocks=[block1])

    ocr_results = [{"page_model": page_model.model_dump()}]

    res_path = SearchablePDFGenerator.create_from_page_images(
        page_images=[sample_image],
        page_ocr_results=ocr_results,
        output_pdf_path=out_pdf,
        title="Page Model Doc",
    )

    assert os.path.exists(res_path)
    doc = fitz.open(res_path)
    assert "First Model Span" in doc[0].get_text()
    doc.close()


def test_create_multi_page_searchable_pdf(sample_image, tmp_path):
    out_pdf = str(tmp_path / "output_multipage.pdf")
    page1_data = {"details": [{"text": "Page 1 Content", "conf": 0.95, "bbox": [50, 50, 400, 90]}]}
    page2_data = {"details": [{"text": "Page 2 Content", "conf": 0.92, "bbox": [50, 50, 400, 90]}]}

    res_path = SearchablePDFGenerator.create_from_page_images(
        page_images=[sample_image, sample_image],
        page_ocr_results=[page1_data, page2_data],
        output_pdf_path=out_pdf,
        title="Multi-page Doc",
    )

    assert os.path.exists(res_path)
    doc = fitz.open(res_path)
    assert len(doc) == 2
    assert "Page 1 Content" in doc[0].get_text()
    assert "Page 2 Content" in doc[1].get_text()
    doc.close()


def test_reportlab_fallback(sample_image, tmp_path):
    out_pdf = str(tmp_path / "output_reportlab.pdf")
    ocr_results = [{
        "details": [
            {"text": "ReportLab Fallback Layer", "conf": 0.99, "bbox": [50, 75, 450, 115]}
        ]
    }]

    res_path = SearchablePDFGenerator._create_with_reportlab(
        page_images=[sample_image],
        page_ocr_results=ocr_results,
        output_pdf_path=out_pdf,
        title="ReportLab Test",
        author="ReportLab Engine",
    )

    assert os.path.exists(res_path)
    doc = fitz.open(res_path)
    assert len(doc) == 1
    assert "ReportLab Fallback Layer" in doc[0].get_text()
    doc.close()
