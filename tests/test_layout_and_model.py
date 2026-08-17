"""
tests.test_layout_and_model

Unit tests for B.L.A.S.T. OCR Phase 2 Document Model and Layout Engine.
"""

import pytest
from blast_ocr.core.document_model import (
    Document, Page, Block, Line, Span, BoundingBox, BlockType
)
from blast_ocr.core.layout import LayoutEngine


class TestDocumentModel:
    def test_bounding_box_geometry(self):
        b1 = BoundingBox(xmin=10, ymin=10, xmax=100, ymax=50)
        b2 = BoundingBox(xmin=50, ymin=30, xmax=150, ymax=80)
        b3 = BoundingBox(xmin=200, ymin=200, xmax=300, ymax=300)

        assert b1.width == 90.0
        assert b1.height == 40.0
        assert b1.center == (55.0, 30.0)

        assert b1.intersects(b2) is True
        assert b1.intersects(b3) is False

        union_box = b1.union(b2)
        assert union_box.xmin == 10.0
        assert union_box.ymin == 10.0
        assert union_box.xmax == 150.0
        assert union_box.ymax == 80.0

    def test_span_line_block_hierarchy(self):
        b1 = BoundingBox(xmin=10, ymin=10, xmax=50, ymax=30)
        b2 = BoundingBox(xmin=60, ymin=10, xmax=100, ymax=30)

        s1 = Span(text="Hello", bbox=b1, confidence=0.9)
        s2 = Span(text="World", bbox=b2, confidence=0.7)

        line = Line(spans=[s1, s2], bbox=b1.union(b2))
        assert line.text == "Hello World"

        block = Block(block_type=BlockType.TEXT, lines=[line], bbox=line.bbox)
        assert block.text == "Hello World"

        page = Page(page_num=1, width=500, height=500, blocks=[block])
        assert page.text == "Hello World"

        doc = Document(title="Test", pages=[page])
        assert "Hello World" in doc.full_text


class TestLayoutEngine:
    def test_empty_detections(self):
        engine = LayoutEngine()
        page = engine.process_page_detections([], 1, 1000, 1000)
        assert page.page_num == 1
        assert page.blocks == []
        assert page.text == ""

    def test_single_column_reading_order(self):
        engine = LayoutEngine()
        detections = [
            {"text": "Line 2", "bbox": [10, 100, 200, 120], "confidence": 0.95},
            {"text": "Line 1", "bbox": [10, 50, 200, 70], "confidence": 0.98},
            {"text": "Line 3", "bbox": [10, 150, 200, 170], "confidence": 0.92},
        ]
        page = engine.process_page_detections(detections, 1, 1000, 1000)
        lines = [line.text for block in page.blocks for line in block.lines]
        assert lines == ["Line 1", "Line 2", "Line 3"]

    def test_two_column_index_segmentation(self):
        """Tests that two-column layouts (like p095) read left column top-to-bottom first."""
        engine = LayoutEngine()
        detections = [
            # Left column (x: 50..200)
            {"text": "Left Col Line 1", "bbox": [50, 50, 200, 70], "confidence": 0.99},
            {"text": "Left Col Line 2", "bbox": [50, 100, 200, 120], "confidence": 0.99},
            # Right column (x: 350..500)
            {"text": "Right Col Line 1", "bbox": [350, 50, 500, 70], "confidence": 0.99},
            {"text": "Right Col Line 2", "bbox": [350, 100, 500, 120], "confidence": 0.99},
        ]
        page = engine.process_page_detections(detections, 1, 1000, 1000)
        all_lines = [line.text for block in page.blocks for line in block.lines]

        # Natural reading order MUST read Left Column entirely before Right Column
        assert all_lines == [
            "Left Col Line 1",
            "Left Col Line 2",
            "Right Col Line 1",
            "Right Col Line 2",
        ]

    def test_dual_page_spread_split(self):
        """Tests dual-page spread splitting where width > 1.2 * height."""
        engine = LayoutEngine()
        detections = [
            # Left physical page
            {"text": "Left Page Top", "bbox": [100, 50, 400, 70], "confidence": 0.99},
            {"text": "Left Page Bottom", "bbox": [100, 500, 400, 520], "confidence": 0.99},
            # Right physical page
            {"text": "Right Page Top", "bbox": [1100, 50, 1400, 70], "confidence": 0.99},
            {"text": "Right Page Bottom", "bbox": [1100, 500, 1400, 520], "confidence": 0.99},
        ]
        # Landscape spread: width=1600, height=800
        page = engine.process_page_detections(detections, 1, 1600, 800)
        all_lines = [line.text for block in page.blocks for line in block.lines]

        assert all_lines == [
            "Left Page Top",
            "Left Page Bottom",
            "Right Page Top",
            "Right Page Bottom",
        ]
