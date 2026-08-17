Title: Phase 2 Layout Analysis & Document Model -- Dual-Page Spread Splitting, Recursive XY-Cut Column Segmentation, Adaptive Line Clustering, and Docling-Inspired Pydantic Schema
Status: accepted
Date: 2026-08-11

Context:
- Baseline evaluation (Phase 0 and Phase 1) showed that reading-order corruption was the single largest source of CER/WER error in extracted text.
- EasyOCR detects bounding boxes in arbitrary detector-scan order. Previously (`blast_ocr/core/extractor.py:533`), extracted text was constructed via raw concatenation (`" ".join(text_parts)`), discarding geometric layout.
- `pipeline.py` contained a legacy helper `_regroup_text_by_layout()` using a fixed 15px row threshold with no column awareness, but it was dead code because `process_page` always returned a joined string.
- Every PDF page in `data/mybook.pdf` is a scanned dual-page spread (facing left and right physical pages in one image). Naive top-to-bottom grouping interleaves two independent sequential physical pages line-by-line or word-by-word.
- Detailed bounding box coordinates attached to `result["details"]` were never propagated or preserved downstream.

Decision:
- Built a typed, validated Document Model (`blast_ocr/core/document_model.py`) using Pydantic v2 (Docling-inspired schema):
  - `BoundingBox`: 2D rectangle `[xmin, ymin, xmax, ymax]` with width, height, center, intersection, and union operations.
  - `Span`: Atomic OCR detection unit carrying text, bounding box, and confidence.
  - `Line`: Horizontally-aligned collection of `Span` objects with reading order index and character-weighted mean confidence.
  - `Block`: Cohesive layout region (paragraph, title, column segment, index item) containing `Line` objects and column index.
  - `Page`: Structural page containing ordered `Block` instances and `text` property reconstructing full-page text in reading order.
  - `Document`: Multi-page document container with metadata and full-text rendering.
- Implemented `LayoutEngine` (`blast_ocr/core/layout.py`) with a 4-stage pipeline:
  1. **Dual-Page Spread Detection & Gutter Split (`_split_book_spread`)**: When image aspect ratio `width > 1.1 * height`, inspects central region (40%-60% page width) to locate vertical whitespace gutter gaps and split detections into Left Page and Right Page sub-regions before reading order evaluation.
  2. **Recursive XY-Cut Column Segmentation (`_segment_columns`)**: Sweeps bounding boxes horizontally within a page/region, splitting into separate columns whenever a vertical whitespace gap exceeds `max(35px, 1.8 * glyph_height)`.
  3. **Adaptive Line Clustering (`_cluster_lines`)**: Groups spans within a column into lines using a vertical proximity tolerance scaled to glyph height (`max(8px, 0.45 * glyph_height)`), sorting spans left-to-right and lines top-to-bottom.
  4. **Block Grouping (`_group_lines_into_blocks`)**: Merges consecutive lines within a column into structural blocks using inter-line gap thresholds (`max(25px, 2.2 * glyph_height)`).
- Integrated `LayoutEngine` directly into `RobustOCRExtractor.process_page`:
  - Passes raw detection geometry to `layout_engine.process_page_detections()`.
  - Sets `extracted_text = layout_page.text`.
  - Preserves full structured model in `result["page_model"] = layout_page.model_dump()`.
- Deleted legacy `_regroup_text_by_layout()` dead code from `pipeline.py`.

Alternatives Considered:
- Option A: Re-activate legacy `_regroup_text_by_layout()`.
  - Rejected: Fixed 15px pixel threshold cannot handle multi-resolution scans, has no column awareness, and fails completely on two-page spreads.
- Option B: Use external layout model (e.g., LayoutLMv3 or YOLOX-Layout).
  - Rejected: Requires heavy GPU dependencies or torch model weights that violate the CPU-only fast inference and lightweight package footprint constraints of B.L.A.S.T. OCR.
- Option C: Custom unvalidated dict layout tree.
  - Rejected: Pydantic v2 models provide runtime validation, clear type hints, easy JSON serialization (`model_dump()`), and seamless compatibility with downstream renderers/serializers.

Consequences:
- Positive:
  - CER slashed by 52.7% (0.4944 -> 0.2338).
  - WER slashed by 31.5% (0.7248 -> 0.4968).
  - Reading order tau increased from 0.6822 to 0.9641 (near-perfect ordering).
  - Fact-check pass rate increased from 29.8% (14/47) to 44.7% (21/47).
  - Bounding box geometry is preserved all the way through the result object (`page_model`).
- Negative:
  - Slight CPU overhead (<0.05s per page) for bounding box sorting and XY-cut calculations, completely negligible compared to OCR inference duration (~30s/page).

Verification:
- Added comprehensive unit test suite in `tests/test_layout_and_model.py` verifying document models, line clustering, column segmentation, and book spread splitting.
- Full 14-page gold corpus eval scorecard recorded in `eval/results/phase2_candidate.json`:
  - `mean_cer`: `0.2338` (vs baseline `0.4944`)
  - `mean_wer`: `0.4968` (vs baseline `0.7248`)
  - `mean_reading_order_tau`: `0.9641` (vs baseline `0.6822`)
  - `fact_pass_rate`: `44.7%` (21/47) (vs baseline `29.8%` (14/47))
- Promoted `phase2_candidate.json` to `eval/results/baseline.json`.
