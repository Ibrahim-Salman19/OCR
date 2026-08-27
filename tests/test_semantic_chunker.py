"""
tests/test_semantic_chunker.py

Unit tests for TOC extraction, Footnote linking, and Semantic RAG chunking.
"""

from blast_ocr.core.document_model import Document, Page, Block, Line, Span, BoundingBox, BlockType
from blast_ocr.core.semantic_chunker import SemanticChunker


def test_toc_extraction():
    # Construct multi-page document with Chapters and Sections
    span_ch1 = Span(text="CHAPTER 1: Fundamental Principles", bbox=BoundingBox(xmin=0, ymin=0, xmax=200, ymax=30))
    block_ch1 = Block(lines=[Line(spans=[span_ch1], bbox=span_ch1.bbox)], bbox=span_ch1.bbox, block_type=BlockType.TITLE)

    span_sec1 = Span(text="1.1 Overview of Optics", bbox=BoundingBox(xmin=0, ymin=50, xmax=200, ymax=80))
    block_sec1 = Block(lines=[Line(spans=[span_sec1], bbox=span_sec1.bbox)], bbox=span_sec1.bbox, block_type=BlockType.SECTION_HEADER)

    page1 = Page(page_num=1, width=800, height=1000, blocks=[block_ch1, block_sec1])

    span_ch2 = Span(text="CHAPTER 2: Wave Mechanics", bbox=BoundingBox(xmin=0, ymin=0, xmax=200, ymax=30))
    block_ch2 = Block(lines=[Line(spans=[span_ch2], bbox=span_ch2.bbox)], bbox=span_ch2.bbox, block_type=BlockType.TITLE)
    page2 = Page(page_num=2, width=800, height=1000, blocks=[block_ch2])

    doc = Document(title="Physics Treatise", pages=[page1, page2])

    toc = SemanticChunker.extract_toc(doc)
    assert len(toc) == 2
    assert "CHAPTER 1" in toc[0].title
    assert len(toc[0].children) == 1
    assert "1.1" in toc[0].children[0].title
    assert "CHAPTER 2" in toc[1].title


def test_footnote_linking():
    body_span = Span(text="According to historical records [1], this occurred in 1842.", bbox=BoundingBox(xmin=0, ymin=100, xmax=500, ymax=130))
    body_block = Block(lines=[Line(spans=[body_span], bbox=body_span.bbox)], bbox=body_span.bbox)

    fn_span = Span(text="[1] Reference to Archive #492, London.", bbox=BoundingBox(xmin=0, ymin=900, xmax=400, ymax=930))
    fn_block = Block(lines=[Line(spans=[fn_span], bbox=fn_span.bbox)], bbox=fn_span.bbox)

    page = Page(page_num=1, width=800, height=1000, blocks=[body_block, fn_block])
    linked_page = SemanticChunker.link_footnotes(page)

    assert linked_page.blocks[1].block_type == BlockType.FOOTNOTE


def test_chunk_document():
    span1 = Span(text="CHAPTER 1: Introduction", bbox=BoundingBox(xmin=0, ymin=0, xmax=200, ymax=30))
    block1 = Block(lines=[Line(spans=[span1], bbox=span1.bbox)], bbox=span1.bbox, block_type=BlockType.TITLE)

    span2 = Span(text="This is a detailed paragraph discussing background history.", bbox=BoundingBox(xmin=0, ymin=50, xmax=500, ymax=80))
    block2 = Block(lines=[Line(spans=[span2], bbox=span2.bbox)], bbox=span2.bbox)

    page = Page(page_num=1, width=800, height=1000, blocks=[block1, block2])
    doc = Document(title="Sample Book", pages=[page])

    chunks = SemanticChunker.chunk_document(doc, max_chunk_tokens=50)
    assert len(chunks) >= 1
    chunk = chunks[0]
    assert "CHAPTER 1" in chunk.section_title or "Sample Book" in chunk.section_title
    assert chunk.page_start == 1
    assert chunk.token_estimate > 0
