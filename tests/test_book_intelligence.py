"""
Unit tests for Book Intelligence module (Phase 4).
"""

import os
from blast_ocr.core.document_model import (
    Document, Page, Block, Line, Span, BoundingBox, BlockType
)
from blast_ocr.core.book_intelligence import BookProcessor


def test_strip_headers_footers():
    # Construct a 2-page document with repeating header and footer
    bbox_header = BoundingBox(xmin=100, ymin=10, xmax=500, ymax=40)
    bbox_body = BoundingBox(xmin=100, ymin=150, xmax=500, ymax=800)
    bbox_footer = BoundingBox(xmin=100, ymin=950, xmax=500, ymax=980)

    p1 = Page(
        page_num=1, width=600, height=1000,
        blocks=[
            Block(block_type=BlockType.TEXT, lines=[Line(spans=[Span(text="The Ideology of Pakistan", bbox=bbox_header)], bbox=bbox_header)], bbox=bbox_header),
            Block(block_type=BlockType.TEXT, lines=[Line(spans=[Span(text="First page body paragraph text content.", bbox=bbox_body)], bbox=bbox_body)], bbox=bbox_body),
            Block(block_type=BlockType.TEXT, lines=[Line(spans=[Span(text="Page 1", bbox=bbox_footer)], bbox=bbox_footer)], bbox=bbox_footer),
        ]
    )

    p2 = Page(
        page_num=2, width=600, height=1000,
        blocks=[
            Block(block_type=BlockType.TEXT, lines=[Line(spans=[Span(text="The Ideology of Pakistan", bbox=bbox_header)], bbox=bbox_header)], bbox=bbox_header),
            Block(block_type=BlockType.TEXT, lines=[Line(spans=[Span(text="Second page body paragraph text content.", bbox=bbox_body)], bbox=bbox_body)], bbox=bbox_body),
            Block(block_type=BlockType.TEXT, lines=[Line(spans=[Span(text="Page 2", bbox=bbox_footer)], bbox=bbox_footer)], bbox=bbox_footer),
        ]
    )

    doc = Document(title="Test Book", pages=[p1, p2])
    cleaned_doc = BookProcessor.strip_headers_footers(doc)

    assert len(cleaned_doc.pages[0].blocks) == 1
    assert cleaned_doc.pages[0].blocks[0].lines[0].spans[0].text == "First page body paragraph text content."
    assert len(cleaned_doc.pages[1].blocks) == 1
    assert cleaned_doc.pages[1].blocks[0].lines[0].spans[0].text == "Second page body paragraph text content."


def test_dehyphenate_text():
    text = "The implemen-\ntation of the national protocol was successful."
    result = BookProcessor.dehyphenate_text(text)
    assert result == "The implementation of the national protocol was successful."


def test_reflow_paragraphs():
    bbox = BoundingBox(xmin=0, ymin=0, xmax=100, ymax=100)
    p = Page(
        page_num=1, width=200, height=200,
        blocks=[
            Block(
                block_type=BlockType.TEXT,
                lines=[
                    Line(spans=[Span(text="This is line one of the", bbox=bbox)], bbox=bbox),
                    Line(spans=[Span(text="first paragraph.", bbox=bbox)], bbox=bbox),
                ],
                bbox=bbox,
            )
        ]
    )
    doc = Document(pages=[p])
    reflowed = BookProcessor.reflow_paragraphs(doc)

    assert "This is line one of the first paragraph." in reflowed.pages[0].text


def test_export_epub(tmp_path):
    bbox = BoundingBox(xmin=0, ymin=0, xmax=100, ymax=100)
    p = Page(
        page_num=1, width=200, height=200,
        blocks=[Block(lines=[Line(spans=[Span(text="EPUB content test page.", bbox=bbox)], bbox=bbox)], bbox=bbox)]
    )
    doc = Document(title="EPUB Test", pages=[p])

    epub_file = str(tmp_path / "test.epub")
    output_file = BookProcessor.export_epub(doc, epub_file)

    assert os.path.exists(output_file)
    with open(output_file, "r", encoding="utf-8") as f:
        content = f.read()
        assert "EPUB Test" in content
        assert "EPUB content test page." in content
