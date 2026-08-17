Title: Phase 4 Book Intelligence -- Header/Footer Stripping, Dehyphenation, Reflow, and EPUB Export Serializer
Status: accepted
Date: 2026-08-11

Context:
- Raw OCR output produces page-fragmented text containing running headers/footers (e.g. "The Ideology of Pakistan"), line-break hyphens (e.g. "implemen-\ntation"), and broken sentence flows.
- Phase 4 transforms structured `Document` and `Page` models (from Phase 2) into publication-ready book artifacts.

Decision:
- Built `BookProcessor` module (`blast_ocr/core/book_intelligence.py`):
  1. **Header & Footer Stripping (`strip_headers_footers`)**: Inspects top and bottom margins (default 8% page height), detects strings repeating across $\ge 2$ consecutive pages, and strips/marks them (`BlockType.HEADER` / `BlockType.FOOTER`).
  2. **Cross-Line Dehyphenation (`dehyphenate_text`)**: Regex-based word rejoining (`(\b[A-Za-z]+)-\s*\n\s*([a-z][A-Za-z]*\b)` -> `\1\2`), removing hyphenation artifacts across line boundaries.
  3. **Paragraph Reflow (`reflow_paragraphs`)**: Reconstructs unwrapped paragraphs within structural blocks while preserving double-newline block separation.
  4. **EPUB Serializer (`export_epub`)**: Generates structured XHTML/EPUB output files containing semantic page sections, formatted headers, and CSS styling.

Alternatives Considered:
- Option A: Heuristic string replacement on flat text.
  - Rejected: Lacks page bounding-box geometry context, risking accidental removal of real body text matching header titles.
- Option B: External NLP package (e.g. spaCy/NLTK) for dehyphenation.
  - Rejected: Unnecessary dependency footprint; targeted regex rules handle scanned book hyphenation patterns with zero overhead.

Consequences:
- Positive:
  - Cleaned book text stripped of noise headers/footers.
  - Paragraphs reflow naturally in exported formats.
  - Added native EPUB export support.

Verification:
- Created unit tests in `tests/test_book_intelligence.py` (4 passed).
