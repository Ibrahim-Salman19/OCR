Title: Phase 5 Tier-0 Native-Text Extraction & Confidence-Gated Routing -- pypdfium2 Integration & Plausibility Scoring
Status: accepted
Date: 2026-08-11

Context:
- For born-digital PDFs or documents with existing high-quality embedded text layers, running full OCR (image rendering + ONNX inference) wastes CPU cycles.
- Licensing constraint: PyMuPDF is AGPL-3.0 and incompatible with B.L.A.S.T. OCR's MIT license. `pypdfium2` is Apache-2.0 and approved for use.

Decision:
- Built `Tier0Extractor` (`blast_ocr/core/tier0_extractor.py`):
  - Uses `pypdfium2` (`pdfium.PdfDocument`) to extract embedded PDF text layers natively.
  - Evaluates text quality and plausibility via `evaluate_native_text_quality()`: checks character length ($\ge 50$ chars), alphanumeric/space ratio ($\ge 0.65$), and detects unmapped unicode/private-use area glyph corruption.
  - Scores confidence (0.98 for clean born-digital text; $< 0.4$ for corrupted font maps or empty pages).
- Routing logic bypasses full OCR when native confidence exceeds floor ($0.85$), passing through to the structured document model instantly.

Consequences:
- Positive:
  - Instant extraction (<0.01s per page) for born-digital PDFs.
  - Zero CER/WER regression on scanned books (`data/mybook.pdf` has no native text layer, so it safely routes to full OCR).
  - Apache-2.0 compliant implementation.

Verification:
- Added unit tests in `tests/test_tier0_extractor.py` (passed).
