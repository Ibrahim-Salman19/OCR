"""
tests/test_table_extractor.py

Unit tests for TableExtractor module.
"""

import numpy as np
import cv2
import pytest

from blast_ocr.core.table_extractor import TableExtractor
from blast_ocr.core.document_model import Span, BoundingBox


@pytest.fixture
def table_image_and_spans():
    # 2 rows, 3 columns table
    img = np.full((350, 550, 3), 255, dtype=np.uint8)
    cv2.rectangle(img, (50, 50), (500, 300), (0, 0, 0), 2)
    cv2.line(img, (50, 175), (500, 175), (0, 0, 0), 2)
    cv2.line(img, (200, 50), (200, 300), (0, 0, 0), 2)
    cv2.line(img, (350, 50), (350, 300), (0, 0, 0), 2)

    spans = [
        Span(text="Header 1", bbox=BoundingBox(xmin=60, ymin=70, xmax=180, ymax=120)),
        Span(text="Header 2", bbox=BoundingBox(xmin=210, ymin=70, xmax=330, ymax=120)),
        Span(text="Header 3", bbox=BoundingBox(xmin=360, ymin=70, xmax=480, ymax=120)),
        Span(text="Data A", bbox=BoundingBox(xmin=60, ymin=190, xmax=180, ymax=240)),
        Span(text="Data B", bbox=BoundingBox(xmin=210, ymin=190, xmax=330, ymax=240)),
        Span(text="Data C", bbox=BoundingBox(xmin=360, ymin=190, xmax=480, ymax=240)),
    ]
    return img, spans


def test_extract_tables_success(table_image_and_spans):
    img, spans = table_image_and_spans
    tables = TableExtractor.extract_tables_from_image(img, spans)

    assert len(tables) == 1
    table = tables[0]
    assert table.num_rows == 2
    assert table.num_cols == 3

    md = table.to_markdown()
    assert "| Header 1 | Header 2 | Header 3 |" in md
    assert "| Data A | Data B | Data C |" in md

    html = table.to_html()
    assert "<table" in html
    assert "<th>Header 1</th>" in html
    assert "<td>Data A</td>" in html

    d = table.to_dict()
    assert d["num_rows"] == 2
    assert d["num_cols"] == 3


def test_extract_tables_empty():
    img = np.full((100, 100, 3), 255, dtype=np.uint8)
    tables = TableExtractor.extract_tables_from_image(img, [])
    assert tables == []


def test_extract_tables_none_image():
    tables = TableExtractor.extract_tables_from_image(None, [])
    assert tables == []
