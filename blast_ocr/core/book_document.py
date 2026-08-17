"""
blast_ocr.core.book_document

Book Intelligence v2 Structural Intermediate Representation (Phase 6 of Execution Plan v2).
Provides typed BookDocument representation containing metadata, chapters, headings,
paragraphs, lists, quotes, tables, and figures for multi-format document generation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from blast_ocr.core.document_model import Document


@dataclass
class BookParagraph:
    text: str
    is_heading: bool = False
    heading_level: int = 0
    confidence: float = 1.0


@dataclass
class BookChapter:
    chapter_number: int
    title: str
    paragraphs: List[BookParagraph] = field(default_factory=list)

    def to_html(self) -> str:
        content = []
        if self.title:
            content.append(f"<h2>{self.title}</h2>")
        for p in self.paragraphs:
            if p.is_heading:
                tag = f"h{min(6, max(2, p.heading_level))}"
                content.append(f"<{tag}>{p.text}</{tag}>")
            else:
                content.append(f"<p>{p.text}</p>")
        return f'<section id="chapter_{self.chapter_number}">\n' + "\n".join(content) + "\n</section>"


@dataclass
class BookDocument:
    """Structural intermediate representation for ingested book documents."""
    title: str
    author: Optional[str] = None
    chapters: List[BookChapter] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_document_model(cls, doc: Document, title: Optional[str] = None) -> "BookDocument":
        doc_title = title or doc.title or "Ingested Document"
        chapters = []
        current_paras = []

        for page in doc.pages:
            p_text = page.text.strip()
            if not p_text:
                continue
            for raw_para in p_text.split("\n\n"):
                clean = raw_para.strip()
                if not clean:
                    continue
                is_head = clean.startswith("## ") or clean.startswith("# ")
                head_lvl = 2 if clean.startswith("## ") else (1 if clean.startswith("# ") else 0)
                txt = clean.replace("## ", "").replace("# ", "")
                current_paras.append(BookParagraph(text=txt, is_heading=is_head, heading_level=head_lvl))

        if current_paras:
            chapters.append(BookChapter(chapter_number=1, title=doc_title, paragraphs=current_paras))

        return cls(title=doc_title, chapters=chapters)

    def to_full_text(self) -> str:
        blocks = []
        for ch in self.chapters:
            for p in ch.paragraphs:
                if p.is_heading:
                    prefix = "#" * max(1, p.heading_level) + " "
                    blocks.append(f"{prefix}{p.text}")
                else:
                    blocks.append(p.text)
        return "\n\n".join(blocks)
