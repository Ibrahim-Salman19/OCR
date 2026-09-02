"""
tests/adversarial/test_layout_adversarial.py

Adversarial suite for layout/multi-modal structure defenses
(docs/HARDENING_BLUEPRINT_AND_TEST_SPECS.md §4.3.4): spanning-header
reading-order collapse (GAP-04), borderless table extraction dropout
(GAP-07), and nested-formula parsing safety (GAP-12).

Real entry points: `blast_ocr.core.layout.LayoutEngine`,
`blast_ocr.core.table_extractor.TableExtractor`,
`blast_ocr.core.formula_extractor.FormulaExtractor` (the blueprint's
illustrative `core.layout_sorter.XYCutPlusPlusSorter` does not exist here).

`tests/test_layout_and_model.py`, `tests/test_table_extractor.py`, and
`tests/test_formula_extractor.py` already carry direct regression coverage
for each GAP fix individually -- this file targets combinations and extreme
inputs those unit suites don't exercise: two independent spanning headers on
one page, a flood of duplicate/overlapping table-candidate detections, and
pathologically deep nested formula input.
"""

from blast_ocr.core.formula_extractor import FormulaExtractor
from blast_ocr.core.layout import LayoutEngine
from blast_ocr.core.document_model import BoundingBox, Span
from blast_ocr.core.table_extractor import TableExtractor


def test_two_independent_spanning_headers_each_mask_their_own_column_band():
    """GAP-04 generalization: `_segment_columns` already builds one Y-band
    per spanning header, but no existing test exercises more than a single
    header. A page with a running title banner AND a mid-page section
    divider banner, each sitting above its own two-column body, must keep
    both column bands independently ordered rather than only the first
    header's band being handled correctly.
    """
    engine = LayoutEngine()
    detections = [
        {"text": "Book Title Running Header", "bbox": [20, 10, 980, 40], "confidence": 0.99},
        {"text": "Section A Left", "bbox": [50, 100, 200, 120], "confidence": 0.99},
        {"text": "Section A Right", "bbox": [350, 100, 500, 120], "confidence": 0.99},
        {"text": "Section B Divider Banner", "bbox": [20, 300, 980, 330], "confidence": 0.99},
        {"text": "Section B Left", "bbox": [50, 400, 200, 420], "confidence": 0.99},
        {"text": "Section B Right", "bbox": [350, 400, 500, 420], "confidence": 0.99},
    ]

    page = engine.process_page_detections(detections, page_num=1, width=1000, height=1000)
    all_lines = [line.text for block in page.blocks for line in block.lines]

    assert all_lines == [
        "Book Title Running Header",
        "Section A Left",
        "Section A Right",
        "Section B Divider Banner",
        "Section B Left",
        "Section B Right",
    ]


def test_layout_engine_never_drops_or_duplicates_spans_under_dense_multi_header_input():
    """Property-style invariant (extends the existing single-header
    permutation test): across three spanning headers interleaved with
    column text, every input span must appear in exactly one output line,
    with no drops and no duplication regardless of how many header bands
    are involved.
    """
    engine = LayoutEngine()
    detections = []
    for i in range(3):
        y_base = i * 300
        detections.append(
            {"text": f"Header {i}", "bbox": [20, y_base + 10, 980, y_base + 40], "confidence": 0.99}
        )
        detections.append(
            {"text": f"Left {i}", "bbox": [50, y_base + 100, 200, y_base + 120], "confidence": 0.99}
        )
        detections.append(
            {"text": f"Right {i}", "bbox": [350, y_base + 100, 500, y_base + 120], "confidence": 0.99}
        )

    page = engine.process_page_detections(detections, page_num=1, width=1000, height=1000)
    all_texts = sorted(line.text for block in page.blocks for line in block.lines)

    assert all_texts == sorted(d["text"] for d in detections)


def test_borderless_table_detector_does_not_hang_or_crash_on_flood_of_duplicate_spans():
    """Adversarial volume test: OCR ensembles / tiled detection passes can
    emit hundreds of duplicate or near-duplicate detections at identical
    coordinates (a common failure mode, not a contrived one). The
    borderless detector's row/column-band clustering must stay fast and
    must not fabricate a table out of degenerate, all-identical geometry.
    """
    spans = [
        Span(text="dup", bbox=BoundingBox(xmin=10, ymin=10, xmax=50, ymax=30))
        for _ in range(500)
    ]

    tables = TableExtractor.extract_borderless_tables(spans)

    assert tables == []


def test_formula_extractor_never_crashes_on_pathologically_deep_nested_sqrt():
    """GAP-12 regression: `_convert_sqrt_balanced` recurses one Python stack
    frame per nesting level. Garbled OCR of a repeated glyph (e.g. a scan
    artifact producing `sqrt(sqrt(sqrt(...)))` thousands of levels deep) must
    not crash page processing with an uncaught RecursionError -- it should
    fall back to the original raw text, exactly like the existing
    unbalanced-parens safety net.
    """
    pathological = "sqrt(" * 2000 + "x" + ")" * 2000

    result = FormulaExtractor.convert_to_latex(pathological)

    assert result == pathological.strip()


def test_formula_extractor_still_converts_moderate_nested_sqrt_correctly():
    """Companion to the pathological-depth test above: confirms the
    RecursionError safety net only engages past the interpreter's recursion
    limit, and ordinary moderate nesting still converts as expected."""
    moderate = "sqrt(sqrt(sqrt(x)))"

    result = FormulaExtractor.convert_to_latex(moderate)

    assert result == "\\sqrt{\\sqrt{\\sqrt{x}}}"
