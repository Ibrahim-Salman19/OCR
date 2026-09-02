"""
tests.test_layout_and_model

Unit tests for B.L.A.S.T. OCR Phase 2 Document Model and Layout Engine.
"""

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

    def test_spanning_header_does_not_collapse_two_columns(self):
        """GAP-04: a full-width title/banner sitting above a two-column body
        must not corrupt the column-gap sweep. Before the fix, the header's
        own xmax participated in the gutter search alongside the column
        spans, erasing the gap and merging both columns into reading order
        as if they were one.
        """
        engine = LayoutEngine()
        detections = [
            {"text": "Chapter Title Spanning The Full Page Width", "bbox": [20, 10, 980, 40], "confidence": 0.99},
            {"text": "Left Col Line 1", "bbox": [50, 100, 200, 120], "confidence": 0.99},
            {"text": "Left Col Line 2", "bbox": [50, 150, 200, 170], "confidence": 0.99},
            {"text": "Right Col Line 1", "bbox": [350, 100, 500, 120], "confidence": 0.99},
            {"text": "Right Col Line 2", "bbox": [350, 150, 500, 170], "confidence": 0.99},
        ]
        page = engine.process_page_detections(detections, 1, 1000, 1000)
        all_lines = [line.text for block in page.blocks for line in block.lines]

        assert all_lines == [
            "Chapter Title Spanning The Full Page Width",
            "Left Col Line 1",
            "Left Col Line 2",
            "Right Col Line 1",
            "Right Col Line 2",
        ]

    def test_segment_columns_is_a_permutation_of_input_spans(self):
        """GAP-04 invariant: column segmentation must never drop or duplicate
        a span, including a span straddling a spanning header's y position
        and two spans that are field-for-field identical (which a naive
        equality-based partition, e.g. `s not in already_placed`, would
        remove as if they were the same instance twice).
        """
        engine = LayoutEngine()
        header_bbox = BoundingBox(xmin=20, ymin=100, xmax=980, ymax=130)
        header = Span(text="Spanning Header", bbox=header_bbox, confidence=0.99)
        straddler_bbox = BoundingBox(xmin=50, ymin=90, xmax=200, ymax=140)
        straddler = Span(text="Straddles Header Y Range", bbox=straddler_bbox, confidence=0.99)
        dup_bbox = BoundingBox(xmin=50, ymin=200, xmax=200, ymax=220)
        dup_a = Span(text="Duplicate Text", bbox=dup_bbox, confidence=0.99)
        dup_b = Span(text="Duplicate Text", bbox=dup_bbox.model_copy(), confidence=0.99)

        spans = [header, straddler, dup_a, dup_b]
        columns = engine._segment_columns(spans, glyph_height=24.0, reference_width=1000.0)

        flattened = [s for col in columns for s in col]
        assert len(flattened) == len(spans)
        assert sorted(s.text for s in flattened) == sorted(s.text for s in spans)

    def test_rtl_line_orders_multiple_spans_right_to_left(self):
        """A single Arabic/Urdu-script line detected as two separate spans
        (common: OCR detects each word/cluster independently) must be
        concatenated in right-to-left reading order -- the visually
        rightmost span read first -- not left-to-right like a Latin line.

        Regression for a second-level instance of the original Urdu bug:
        rapidocr_engine.py already reverses each span's own characters for
        correct RTL glyph order, but that says nothing about the order
        multiple spans on the same line get joined in. Using `in` /
        substring assertions here would pass regardless of order, so this
        checks the exact position of each word instead.
        """
        engine = LayoutEngine()
        detections = [
            # Visually rightmost (higher x) -- must be read first in RTL.
            # Horizontal gap to the other span is kept below the column-gap
            # threshold so both stay on one line/column, not split into two.
            {"text": "کتاب", "bbox": [200, 50, 320, 80], "confidence": 0.99},
            # Visually leftmost (lower x) -- must be read second in RTL.
            {"text": "اردو", "bbox": [50, 50, 170, 80], "confidence": 0.99},
        ]
        page = engine.process_page_detections(detections, 1, 1000, 200)
        lines = [line.text for block in page.blocks for line in block.lines]
        assert lines == ["کتاب اردو"]

    def test_ltr_line_ordering_unchanged_by_rtl_fix(self):
        """Backward-compat guard: a pure-Latin line must still concatenate
        left-to-right exactly as before the RTL ordering fix."""
        engine = LayoutEngine()
        detections = [
            {"text": "World", "bbox": [200, 50, 320, 80], "confidence": 0.99},
            {"text": "Hello", "bbox": [50, 50, 170, 80], "confidence": 0.99},
        ]
        page = engine.process_page_detections(detections, 1, 1000, 200)
        lines = [line.text for block in page.blocks for line in block.lines]
        assert lines == ["Hello World"]

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
