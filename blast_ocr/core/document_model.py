"""
blast_ocr.core.document_model

Typed Document Model for B.L.A.S.T. OCR Protocol (Docling-inspired schema).
Represents OCR extraction geometry and semantics down to span level.
"""

from enum import Enum
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field


class BlockType(str, Enum):
    TITLE = "title"
    SECTION_HEADER = "section_header"
    HEADER = "header"
    FOOTER = "footer"
    TEXT = "text"
    COLUMN = "column"
    LIST_ITEM = "list_item"
    TABLE = "table"
    FORMULA = "formula"
    FOOTNOTE = "footnote"
    CAPTION = "caption"
    INDEX_ITEM = "index_item"
    UNKNOWN = "unknown"


class BoundingBox(BaseModel):
    """Normalized or pixel coordinates [xmin, ymin, xmax, ymax]."""
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @property
    def width(self) -> float:
        return max(0.0, self.xmax - self.xmin)

    @property
    def height(self) -> float:
        return max(0.0, self.ymax - self.ymin)

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.xmin + self.xmax) / 2.0, (self.ymin + self.ymax) / 2.0)

    def intersects(self, other: "BoundingBox") -> bool:
        return not (
            self.xmax < other.xmin or
            self.xmin > other.xmax or
            self.ymax < other.ymin or
            self.ymin > other.ymax
        )

    def union(self, other: "BoundingBox") -> "BoundingBox":
        return BoundingBox(
            xmin=min(self.xmin, other.xmin),
            ymin=min(self.ymin, other.ymin),
            xmax=max(self.xmax, other.xmax),
            ymax=max(self.ymax, other.ymax),
        )


class Span(BaseModel):
    """Atomic text detection span with source bounding box and OCR confidence."""
    text: str
    bbox: BoundingBox
    confidence: float = 1.0


class Line(BaseModel):
    """Horizontally aligned sequence of spans forming a line of text."""
    spans: List[Span] = Field(default_factory=list)
    bbox: BoundingBox
    reading_order_index: int = 0

    @property
    def text(self) -> str:
        return " ".join(s.text for s in self.spans if s.text.strip())

    @property
    def mean_confidence(self) -> float:
        if not self.spans:
            return 1.0
        total_chars = sum(len(s.text) for s in self.spans)
        if total_chars == 0:
            return sum(s.confidence for s in self.spans) / len(self.spans)
        return sum(s.confidence * len(s.text) for s in self.spans) / total_chars


class Block(BaseModel):
    """Cohesive structural layout region (paragraph, column segment, header)."""
    block_type: BlockType = BlockType.TEXT
    lines: List[Line] = Field(default_factory=list)
    bbox: BoundingBox
    reading_order_index: int = 0
    column_index: int = 0

    @property
    def text(self) -> str:
        return "\n".join(l.text for l in self.lines if l.text.strip())

    @property
    def mean_confidence(self) -> float:
        if not self.lines:
            return 1.0
        scores = [l.mean_confidence for l in self.lines]
        return sum(scores) / len(scores) if scores else 1.0

    @property
    def is_low_confidence(self) -> bool:
        return self.mean_confidence < 0.85


class Page(BaseModel):
    """Complete document page containing layout blocks."""
    page_num: int
    width: int
    height: int
    blocks: List[Block] = Field(default_factory=list)
    raw_text: Optional[str] = None

    @property
    def text(self) -> str:
        if self.blocks:
            sorted_blocks = sorted(self.blocks, key=lambda b: b.reading_order_index)
            txt = "\n\n".join(b.text for b in sorted_blocks if b.text.strip())
            if txt:
                return txt
        return self.raw_text or ""

    @property
    def mean_confidence(self) -> float:
        if not self.blocks:
            return 1.0
        scores = [b.mean_confidence for b in self.blocks]
        return sum(scores) / len(scores) if scores else 1.0

    def get_low_confidence_blocks(self, threshold: float = 0.85) -> List[Block]:
        return [b for b in self.blocks if b.mean_confidence < threshold]


class Document(BaseModel):
    """Multi-page structured document model."""
    title: str = "Ingested Document"
    pages: List[Page] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    @property
    def full_text(self) -> str:
        return "\n\n--- Page Break ---\n\n".join(p.text for p in self.pages)
