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


def _span(text, x, y, w=100, h=20):
    return Span(text=text, bbox=BoundingBox(xmin=x, ymin=y, xmax=x + w, ymax=y + h))


def test_borderless_table_detected_from_column_alignment():
    """GAP-07: a table with no drawn grid lines yields zero contours for
    the morphology pass, so it must be recovered from span geometry alone
    -- a repeated x-column alignment pattern across multiple rows.
    """
    spans = []
    for r in range(4):
        y = 50 + r * 40
        spans.append(_span(f"R{r}C0", 50, y))
        spans.append(_span(f"R{r}C1", 220, y))
        spans.append(_span(f"R{r}C2", 390, y))

    white_img = np.full((400, 600, 3), 255, dtype=np.uint8)
    tables = TableExtractor.extract_tables_from_image(white_img, spans)

    assert len(tables) == 1
    table = tables[0]
    assert table.num_rows == 4
    assert table.num_cols == 3
    assert table.grid[0] == ["R0C0", "R0C1", "R0C2"]
    assert table.grid[-1] == ["R3C0", "R3C1", "R3C2"]


def test_borderless_detection_ignores_two_column_prose_page():
    """GAP-07 false-positive guard: a normal two-column page of body text
    also produces consistent x-alignment (each column's left edge repeats
    down the page), but must never be reported as a table -- it only ever
    forms 2 x-bands, and the borderless detector requires >= 3 stable
    columns before calling anything a table.
    """
    spans = []
    for r in range(8):
        y = 50 + r * 30
        spans.append(_span(f"Left line {r} of running prose text", 50, y, w=150))
        spans.append(_span(f"Right line {r} of running prose text", 350, y, w=150))

    white_img = np.full((400, 700, 3), 255, dtype=np.uint8)
    tables = TableExtractor.extract_tables_from_image(white_img, spans)

    assert tables == []


def test_borderless_detection_requires_minimum_rows():
    """Only 2 aligned rows of a 3-column pattern must not qualify -- below
    the min_rows=3 stability threshold, this is as likely to be two
    unrelated aligned lines as a real table.
    """
    spans = []
    for r in range(2):
        y = 50 + r * 40
        spans.append(_span(f"R{r}C0", 50, y))
        spans.append(_span(f"R{r}C1", 220, y))
        spans.append(_span(f"R{r}C2", 390, y))

    tables = TableExtractor.extract_borderless_tables(spans)
    assert tables == []


def test_extract_tables_from_image_does_not_double_detect_bordered_table(table_image_and_spans):
    """The borderless fallback must not re-report a table the bordered
    morphology pass already found -- spans already claimed by a bordered
    table's bbox are excluded before the borderless pass runs.
    """
    img, spans = table_image_and_spans
    tables = TableExtractor.extract_tables_from_image(img, spans)
    assert len(tables) == 1
