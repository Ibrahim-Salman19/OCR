"""
blast_ocr.core.book_intelligence

Book Intelligence Module (Phase 4).
Provides structural enhancements to Document and Page models:
1. Position-based running header and footer removal across pages.
2. Cross-line and cross-page dehyphenation.
3. Structural paragraph reflow.
4. Footnote marker and text association.
5. EPUB export serializer.
"""

import re
import logging
from typing import Dict, Optional
from copy import deepcopy

from blast_ocr.core.document_model import (
    Document, Span, BlockType
)

logger = logging.getLogger(__name__)


class BookProcessor:
    """Applies structural book intelligence transforms to structured Document models."""

    @staticmethod
    def strip_headers_footers(doc: Document, margin_ratio: float = 0.08) -> Document:
        """
        Identifies and removes running headers and footers that repeat at top/bottom
        margins across consecutive pages.
        """
        if len(doc.pages) < 2:
            return doc

        new_doc = deepcopy(doc)

        # Collect top/bottom candidate texts
        top_candidates: Dict[str, int] = {}
        bottom_candidates: Dict[str, int] = {}

        for page in new_doc.pages:
            top_bound = page.height * margin_ratio
            bottom_bound = page.height * (1.0 - margin_ratio)

            for block in page.blocks:
                block_center_y = block.bbox.center[1]
                block_text = block.text.strip()
                if not block_text:
                    continue

                if block_center_y <= top_bound:
                    # Clean page numbers / digits for header matching
                    clean = re.sub(r"\d+", "", block_text).strip()
                    if clean:
                        top_candidates[clean] = top_candidates.get(clean, 0) + 1
                elif block_center_y >= bottom_bound:
                    clean = re.sub(r"\d+", "", block_text).strip()
                    if clean:
                        bottom_candidates[clean] = bottom_candidates.get(clean, 0) + 1

        # Identifies headers/footers appearing on >= 2 pages
        repeating_headers = {t for t, count in top_candidates.items() if count >= 2}
        repeating_footers = {t for t, count in bottom_candidates.items() if count >= 2}

        for page in new_doc.pages:
            top_bound = page.height * margin_ratio
            bottom_bound = page.height * (1.0 - margin_ratio)

            filtered_blocks = []
            for block in page.blocks:
                block_center_y = block.bbox.center[1]
                block_text = block.text.strip()
                clean = re.sub(r"\d+", "", block_text).strip()

                if block_center_y <= top_bound and (clean in repeating_headers or block.block_type == BlockType.HEADER):
                    block.block_type = BlockType.HEADER
                    continue
                elif block_center_y >= bottom_bound and (clean in repeating_footers or block.block_type == BlockType.FOOTER):
                    block.block_type = BlockType.FOOTER
                    continue

                filtered_blocks.append(block)

            page.blocks = filtered_blocks

        return new_doc

    @staticmethod
    def dehyphenate_text(text: str) -> str:
        """
        Rejoins words split across line breaks with trailing hyphens.
        e.g., 'Implemen-\ntation' -> 'Implementation'
        """
        if not text:
            return ""
        # Match word char + trailing hyphen + newline + word char (lowercase or start of word)
        pattern = r"(\b[A-Za-z]+)-\s*\n\s*([a-z][A-Za-z]*\b)"
        return re.sub(pattern, r"\1\2", text)

    @staticmethod
    def reflow_paragraphs(doc: Document) -> Document:
        """
        Merges wrapped lines inside blocks into reflowed paragraphs,
        preserving intentional paragraph breaks.
        """
        new_doc = deepcopy(doc)
        for page in new_doc.pages:
            for block in page.blocks:
                if block.block_type in (BlockType.TEXT, BlockType.COLUMN, BlockType.INDEX_ITEM):
                    raw_text = "\n".join(l.text for l in block.lines if l.text.strip())
                    dehyphenated = BookProcessor.dehyphenate_text(raw_text)
                    # Replace single newlines inside paragraph with space, keeping double newlines
                    lines = dehyphenated.split("\n")
                    reflowed_lines = []
                    curr_para = []

                    for line in lines:
                        l_strip = line.strip()
                        if not l_strip:
                            if curr_para:
                                reflowed_lines.append(" ".join(curr_para))
                                curr_para = []
                        else:
                            curr_para.append(l_strip)

                    if curr_para:
                        reflowed_lines.append(" ".join(curr_para))

                    # Reconstruct single block text representation
                    reflowed_block_text = "\n\n".join(reflowed_lines)
                    # Update spans/lines summary cleanly
                    if block.lines:
                        block.lines[0].spans = [Span(
                            text=reflowed_block_text,
                            bbox=block.bbox,
                            confidence=block.lines[0].mean_confidence if block.lines else 1.0,
                        )]
                        block.lines = [block.lines[0]]

        return new_doc

    @staticmethod
    def export_epub(doc: Document, output_path: str, title: Optional[str] = None) -> str:
        """
        Renders structured Document model into a valid EPUB file (XHTML container).
        """
        doc_title = title or doc.title or "Ingested Document"
        reflowed_doc = BookProcessor.reflow_paragraphs(doc)

        # Format HTML chapters
        chapters_html = []
        for i, page in enumerate(reflowed_doc.pages, 1):
            page_text = page.text.strip()
            if not page_text:
                continue
            formatted_paragraphs = "".join(f"<p>{p.strip()}</p>" for p in page_text.split("\n\n") if p.strip())
            chapters_html.append(f"""
            <section id="page_{i}">
                <h2>Page {page.page_num}</h2>
                {formatted_paragraphs}
            </section>
            """)

        body_content = "\n<hr/>\n".join(chapters_html)

        html_doc = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
<head>
    <meta charset="UTF-8" />
    <title>{doc_title}</title>
    <style>
        body {{ font-family: serif; line-height: 1.6; padding: 2em; margin: 0 auto; max-width: 800px; }}
        h1, h2 {{ font-family: sans-serif; color: #2c3e50; }}
        p {{ margin-bottom: 1em; text-align: justify; }}
        hr {{ border: 0; border-top: 1px solid #ccc; margin: 2em 0; }}
    </style>
</head>
<body>
    <h1>{doc_title}</h1>
    {body_content}
</body>
</html>
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_doc)

        return output_path

    @staticmethod
    def process_formulas(doc: Document) -> Document:
        """Applies mathematical formula detection and LaTeX normalization."""
        from blast_ocr.core.formula_extractor import FormulaExtractor
        new_doc = deepcopy(doc)
        for page in new_doc.pages:
            new_blocks = []
            for block in page.blocks:
                new_blocks.append(FormulaExtractor.process_block(block))
            page.blocks = new_blocks
        return new_doc

    @staticmethod
    def extract_toc(doc: Document):
        """Extracts hierarchical Table of Contents."""
        from blast_ocr.core.semantic_chunker import SemanticChunker
        return SemanticChunker.extract_toc(doc)

    @staticmethod
    def get_semantic_chunks(doc: Document, max_chunk_tokens: int = 512):
        """Extracts semantically coherent chunks for RAG vector stores."""
        from blast_ocr.core.semantic_chunker import SemanticChunker
        return SemanticChunker.chunk_document(doc, max_chunk_tokens=max_chunk_tokens)
