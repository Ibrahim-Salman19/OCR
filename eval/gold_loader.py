"""Parses eval/gold/*.gold.txt files into structured gold records.

Gold file format: plain UTF-8 text, physical-page boundaries marked with a
line of the form ``[PAGE <label>]``, paragraphs separated by blank lines.
See eval/gold/manifest.json for why each page was selected.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

PAGE_MARKER_RE = re.compile(r"^\[PAGE\s+(.+?)\]\s*$")


@dataclass
class GoldPage:
    label: str
    paragraphs: List[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(self.paragraphs)


@dataclass
class GoldRecord:
    page_id: str
    path: Path
    physical_pages: List[GoldPage]

    @property
    def flat_text(self) -> str:
        """All physical pages concatenated in reading order, whitespace-normalized."""
        parts = [pp.text for pp in self.physical_pages]
        return normalize_whitespace(" ".join(parts))

    @property
    def tokens(self) -> List[str]:
        """Lowercased word tokens in gold reading order (for reading-order scoring)."""
        return tokenize(self.flat_text)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def parse_gold_file(path: Path) -> GoldRecord:
    raw = path.read_text(encoding="utf-8")
    physical_pages: List[GoldPage] = []
    current: Optional[GoldPage] = None
    para_lines: List[str] = []

    def flush_paragraph():
        if para_lines:
            text = " ".join(line.strip() for line in para_lines).strip()
            text = normalize_whitespace(text)
            if text and current is not None:
                current.paragraphs.append(text)
        para_lines.clear()

    for line in raw.splitlines():
        marker = PAGE_MARKER_RE.match(line)
        if marker:
            flush_paragraph()
            current = GoldPage(label=marker.group(1))
            physical_pages.append(current)
            continue
        if line.strip() == "":
            flush_paragraph()
            continue
        para_lines.append(line)
    flush_paragraph()

    page_id = path.stem.replace(".gold", "")
    return GoldRecord(page_id=page_id, path=path, physical_pages=physical_pages)


def load_all_gold(gold_dir: Path) -> List[GoldRecord]:
    records = [
        parse_gold_file(p) for p in sorted(gold_dir.glob("*.gold.txt"))
    ]
    return records
