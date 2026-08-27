"""
blast_ocr.core.semantic_chunker

Semantic Book Intelligence, Hierarchical TOC Extraction, Footnote Linking,
and Structure-Aware RAG Chunking for B.L.A.S.T. OCR Protocol.
"""

import re
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from blast_ocr.core.document_model import Document, Page, Block, BlockType


@dataclass
class TOCItem:
    title: str
    level: int  # 1 for Part/Chapter, 2 for Section, 3 for Subsection
    page_num: int
    children: List['TOCItem'] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "level": self.level,
            "page_num": self.page_num,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class SemanticChunk:
    chunk_id: str
    content: str
    section_title: str
    heading_path: List[str]
    page_start: int
    page_end: int
    block_types: List[str]
    token_estimate: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "section_title": self.section_title,
            "heading_path": self.heading_path,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "block_types": self.block_types,
            "token_estimate": self.token_estimate,
            "metadata": self.metadata,
        }


class SemanticChunker:
    """
    Analyzes document layout structure, extracts hierarchical Table of Contents (TOC),
    links footnotes, and generates semantically coherent chunks for LLM RAG applications.
    """

    CHAPTER_HEADING_REGEX = re.compile(
        r"^(CHAPTER|PART|BOOK|SECTION|MODULE|ACT|UNIT)\s+([0-9IVXLCDM]+|[A-Z]+)\b[:\.\s]*(.*)",
        re.IGNORECASE
    )

    SECTION_HEADING_REGEX = re.compile(
        r"^([0-9]+\.[0-9]+(\.[0-9]+)*)\s+(.*)"
    )

    FOOTNOTE_MARKER_REGEX = re.compile(r"\[\^?([0-9]+|\*|\†)\]")

    @classmethod
    def extract_toc(cls, doc: Document) -> List[TOCItem]:
        """
        Extracts hierarchical Table of Contents from document pages.
        """
        toc_roots: List[TOCItem] = []
        current_h1: Optional[TOCItem] = None

        for page in doc.pages:
            for block in page.blocks:
                text = block.text.strip()
                if not text:
                    continue

                lines = text.split("\n")
                first_line = lines[0].strip()

                # 1. Check Numbered Section Level (H2)
                sec_match = cls.SECTION_HEADING_REGEX.match(first_line)
                if sec_match or (block.block_type == BlockType.SECTION_HEADER and len(first_line) < 80):
                    item = TOCItem(title=first_line, level=2, page_num=page.page_num)
                    if current_h1:
                        current_h1.children.append(item)
                    else:
                        toc_roots.append(item)
                    continue

                # 2. Check Chapter / Part / Title Level (H1)
                ch_match = cls.CHAPTER_HEADING_REGEX.match(first_line)
                if ch_match or (block.block_type == BlockType.TITLE and len(first_line) < 80):
                    title = first_line
                    item = TOCItem(title=title, level=1, page_num=page.page_num)
                    toc_roots.append(item)
                    current_h1 = item
                    continue

        return toc_roots

    @classmethod
    def link_footnotes(cls, page: Page) -> Page:
        """
        Identifies footnote blocks at page bottom and links with body text superscript markers.
        """
        if not page.blocks or len(page.blocks) < 2:
            return page

        page_height = page.height or 1000
        bottom_threshold = page_height * 0.85

        for block in page.blocks:
            # Check if block is in bottom 15% of page and starts with footnote indicator
            if block.bbox.ymin >= bottom_threshold or block.bbox.ymax >= bottom_threshold:
                txt = block.text.strip()
                if re.match(r"^(\*|\†|\[\^?[0-9]+\]|[0-9]+\.|\([0-9]+\))\s+", txt):
                    block.block_type = BlockType.FOOTNOTE

        return page

    @classmethod
    def chunk_document(
        cls,
        doc: Document,
        max_chunk_tokens: int = 512,
        overlap_tokens: int = 64,
    ) -> List[SemanticChunk]:
        """
        Generates structure-aware semantic chunks respecting headings, paragraphs, and tables.
        """
        chunks: List[SemanticChunk] = []
        current_heading_path = [doc.title or "Document"]
        current_section = doc.title or "General"

        current_blocks: List[Block] = []
        current_text_segments: List[str] = []
        current_types: List[str] = []
        chunk_page_start = doc.pages[0].page_num if doc.pages else 1
        chunk_page_end = chunk_page_start

        def _approx_tokens(text: str) -> int:
            return max(1, len(text.split()) * 4 // 3)

        def _flush_chunk():
            nonlocal current_blocks, current_text_segments, current_types
            if not current_text_segments:
                return

            chunk_text = "\n\n".join(current_text_segments).strip()
            if not chunk_text:
                return

            tok_count = _approx_tokens(chunk_text)
            c = SemanticChunk(
                chunk_id=str(uuid.uuid4())[:8],
                content=chunk_text,
                section_title=current_section,
                heading_path=list(current_heading_path),
                page_start=chunk_page_start,
                page_end=chunk_page_end,
                block_types=list(set(current_types)),
                token_estimate=tok_count,
                metadata={
                    "doc_title": doc.title,
                    "section": current_section,
                    "pages": f"{chunk_page_start}-{chunk_page_end}",
                },
            )
            chunks.append(c)
            current_blocks = []
            current_text_segments = []
            current_types = []

        for page in doc.pages:
            # First pass: link footnotes
            page = cls.link_footnotes(page)

            for block in page.blocks:
                b_text = block.text.strip()
                if not b_text:
                    continue

                b_type_str = block.block_type.value if hasattr(block.block_type, "value") else str(block.block_type)

                # Check if block is a major heading (boundary event)
                is_h1 = bool(cls.CHAPTER_HEADING_REGEX.match(b_text)) or (block.block_type == BlockType.TITLE)
                is_h2 = bool(cls.SECTION_HEADING_REGEX.match(b_text)) or (block.block_type == BlockType.SECTION_HEADER)

                if is_h1 or is_h2:
                    # Flush existing chunk before heading
                    _flush_chunk()
                    chunk_page_start = page.page_num
                    chunk_page_end = page.page_num

                    if is_h1:
                        current_heading_path = [doc.title, b_text]
                        current_section = b_text
                    else:
                        if len(current_heading_path) > 1:
                            current_heading_path = current_heading_path[:2] + [b_text]
                        else:
                            current_heading_path.append(b_text)
                        current_section = b_text

                    current_text_segments.append(f"### {b_text}")
                    current_types.append(b_type_str)
                    continue

                # Add block to current accumulator
                current_text_segments.append(b_text)
                current_types.append(b_type_str)
                chunk_page_end = page.page_num

                # Check if size exceeds token target
                accum_text = "\n\n".join(current_text_segments)
                if _approx_tokens(accum_text) >= max_chunk_tokens:
                    _flush_chunk()
                    chunk_page_start = page.page_num

        _flush_chunk()
        return chunks

    @classmethod
    def chunk_text(
        cls,
        text: str,
        title: str = "Document",
        max_chunk_tokens: int = 512,
        overlap_tokens: int = 64,
    ) -> List[SemanticChunk]:
        """Convenience method to chunk raw text using semantic paragraph segmentation."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return []

        blocks = []
        for p in paragraphs:
            b_type = BlockType.TITLE if (len(p) < 60 and not p.endswith(".")) else BlockType.PARAGRAPH
            blocks.append(Block(text=p, block_type=b_type, bbox=[0, 0, 100, 100], confidence=1.0))

        page = Page(page_num=1, width=1000, height=1000, blocks=blocks)
        doc = Document(title=title, pages=[page])
        return cls.chunk_document(doc, max_chunk_tokens=max_chunk_tokens, overlap_tokens=overlap_tokens)
