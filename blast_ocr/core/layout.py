"""
blast_ocr.core.layout

Advanced Layout Engine for B.L.A.S.T. OCR Protocol.
Implements adaptive line clustering and Recursive XY-Cut column segmentation
to construct structured Reading Order and Document Models from raw OCR detections.
"""

from typing import List, Dict, Any, Optional
import numpy as np

from blast_ocr.core.document_model import (
    Page, Block, Line, Span, BoundingBox, BlockType
)
from blast_ocr.core.script_detection import contains_rtl_script


class LayoutEngine:
    """
    Reconstructs document layout, column segmentation, and reading order
    from unstructured 2D bounding box detections.
    """

    # A span at least this wide relative to the physical page is treated as a
    # full-width spanning element (title, running header, banner) rather than
    # column-body text. Anchored to the physical page width, not the bounding
    # extent of the spans being segmented -- anchoring to the latter is
    # self-referential and false-positives on a narrow single-column page,
    # where the body text's own tight bounding box makes ordinary lines look
    # "spanning" relative to it.
    SPANNING_HEADER_WIDTH_RATIO: float = 0.82

    def __init__(self, default_glyph_height: float = 24.0):
        self.default_glyph_height = default_glyph_height

    def process_page_detections(
        self,
        raw_detections: List[Dict[str, Any]],
        page_num: int,
        width: int,
        height: int,
        glyph_height: Optional[float] = None,
    ) -> Page:
        """
        Main entry point: converts raw OCR detection dicts into a structured Page model.
        
        raw_detections elements:
          - 'text': str
          - 'bbox': [[x1,y1], [x2,y1], [x2,y2], [x1,y2]] or [xmin, ymin, xmax, ymax]
          - 'confidence': float
        """
        if not raw_detections:
            return Page(page_num=page_num, width=width, height=height, blocks=[])

        # 1. Convert raw detection dicts into Span objects
        spans = self._convert_to_spans(raw_detections)
        if not spans:
            return Page(page_num=page_num, width=width, height=height, blocks=[])

        eff_glyph_height = glyph_height if (glyph_height and glyph_height > 0) else self.default_glyph_height

        # 2. Check for dual-page book spread split (central vertical gutter)
        sub_page_spans_list = self._split_book_spread(spans, width, height, eff_glyph_height)

        # Each physical page a spread splits into occupies roughly half the
        # combined spread width; anchoring the spanning-header ratio to that
        # (rather than the un-split full width) keeps the "full-width header"
        # definition meaningful per physical page after the split.
        page_ref_width = float(width) if len(sub_page_spans_list) <= 1 else float(width) / 2.0

        all_blocks: List[Block] = []
        global_reading_index = 0

        for sub_spans in sub_page_spans_list:
            if not sub_spans:
                continue

            # 3. Column / Block Segmentation (Recursive XY-Cut on sub-page spans)
            columns = self._segment_columns(sub_spans, eff_glyph_height, page_ref_width)

            for col_idx, col_spans in enumerate(columns):
                if not col_spans:
                    continue

                # 4. Adaptive Line Clustering within column
                lines = self._cluster_lines(col_spans, eff_glyph_height)

                # 5. Group lines into cohesive blocks
                blocks = self._group_lines_into_blocks(lines, col_idx, eff_glyph_height)

                for block in blocks:
                    block.reading_order_index = global_reading_index
                    global_reading_index += 1
                    all_blocks.append(block)

        return Page(page_num=page_num, width=width, height=height, blocks=all_blocks)

    def _convert_to_spans(self, raw_detections: List[Dict[str, Any]]) -> List[Span]:
        spans: List[Span] = []
        for d in raw_detections:
            text = str(d.get("text", "")).strip()
            if not text:
                continue
            bbox_raw = d.get("bbox")
            conf = float(d.get("confidence", 1.0))

            if not bbox_raw:
                continue

            # Handle 4-point polygon [[x1,y1], [x2,y1], ...] or 4-element box [xmin, ymin, xmax, ymax]
            if isinstance(bbox_raw, (list, tuple)):
                if len(bbox_raw) == 4 and isinstance(bbox_raw[0], (int, float)):
                    xmin, ymin, xmax, ymax = map(float, bbox_raw)
                elif len(bbox_raw) == 4 and isinstance(bbox_raw[0], (list, tuple)):
                    pts = np.array(bbox_raw, dtype=np.float32)
                    xmin, ymin = float(pts[:, 0].min()), float(pts[:, 1].min())
                    xmax, ymax = float(pts[:, 0].max()), float(pts[:, 1].max())
                else:
                    continue
            else:
                continue

            # Skip 0-width or 0-height phantom boxes
            if xmax <= xmin or ymax <= ymin:
                continue

            bbox = BoundingBox(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)
            spans.append(Span(text=text, bbox=bbox, confidence=conf))

        return spans

    def _split_book_spread(
        self, spans: List[Span], page_width: int, page_height: int, glyph_height: float
    ) -> List[List[Span]]:
        """
        If width > 1.2 * height (dual page spread), search for central gutter gap
        and split spans into Left Page and Right Page to preserve physical page order.
        """
        if page_width <= 1.1 * page_height or not spans:
            return [spans]

        mid_min = 0.40 * page_width
        mid_max = 0.60 * page_width

        # Find spans crossing the candidate gutter zone
        mid_spans = [s for s in spans if s.bbox.xmin < mid_max and s.bbox.xmax > mid_min]

        # Calculate a vertical histogram in the mid zone to find the widest empty gap
        # If very few spans cross mid zone, split cleanly at the center gap or page_width / 2
        split_x = page_width / 2.0

        if mid_spans:
            # Find best gap between xmin and xmax of mid spans
            mid_spans_sorted = sorted(mid_spans, key=lambda s: s.bbox.xmin)
            max_gap = 0.0
            best_split = split_x
            for i in range(len(mid_spans_sorted) - 1):
                gap = mid_spans_sorted[i+1].bbox.xmin - mid_spans_sorted[i].bbox.xmax
                if gap > max_gap:
                    max_gap = gap
                    best_split = (mid_spans_sorted[i+1].bbox.xmin + mid_spans_sorted[i].bbox.xmax) / 2.0

            if max_gap > 1.5 * glyph_height:
                split_x = best_split

        left_spans = [s for s in spans if s.bbox.center[0] < split_x]
        right_spans = [s for s in spans if s.bbox.center[0] >= split_x]

        if not left_spans:
            return [right_spans]
        if not right_spans:
            return [left_spans]

        return [left_spans, right_spans]

    def _segment_columns(
        self, spans: List[Span], glyph_height: float, reference_width: float
    ) -> List[List[Span]]:
        """
        Isolates full-width spanning elements (titles, running headers/banners)
        from column-body text before column-gap detection, then recursively
        XY-cuts each resulting y-band independently.

        Without this, a spanning span's own xmax/xmin participate in the
        vertical-gutter gap sweep below alongside genuine column text; a
        header that stretches across where the gutter would otherwise be
        erases the gap entirely and collapses a real two-column page into one
        column (TAX-LAY-01).
        """
        if len(spans) < 2:
            return [spans]

        spanning = sorted(
            (
                s
                for s in spans
                if reference_width > 0
                and s.bbox.width >= self.SPANNING_HEADER_WIDTH_RATIO * reference_width
            ),
            key=lambda s: s.bbox.center[1],
        )
        if not spanning:
            return self._merge_narrow_trailing_columns(
                self._gap_sweep_columns(spans, glyph_height), glyph_height
            )

        # Identity-based partition (not equality/`in`) so two spans with
        # identical text and geometry are never conflated: each span is
        # assigned to exactly one bucket, so total span count across all
        # returned columns always equals len(spans).
        spanning_ids = {id(s) for s in spanning}
        candidates = [s for s in spans if id(s) not in spanning_ids]

        header_centers = [h.bbox.center[1] for h in spanning]
        bands: List[List[Span]] = [[] for _ in range(len(spanning) + 1)]
        for s in candidates:
            cy = s.bbox.center[1]
            band_idx = 0
            for i, header_cy in enumerate(header_centers):
                if cy >= header_cy:
                    band_idx = i + 1
            bands[band_idx].append(s)

        result: List[List[Span]] = []
        for i, header in enumerate(spanning):
            if bands[i]:
                result.extend(
                    self._merge_narrow_trailing_columns(
                        self._gap_sweep_columns(bands[i], glyph_height), glyph_height
                    )
                )
            result.append([header])
        if bands[-1]:
            result.extend(
                self._merge_narrow_trailing_columns(
                    self._gap_sweep_columns(bands[-1], glyph_height), glyph_height
                )
            )

        return result

    @staticmethod
    def _merge_narrow_trailing_columns(
        columns: List[List[Span]], glyph_height: float
    ) -> List[List[Span]]:
        """
        Merges a column back into its left neighbor when every span in it
        is narrow -- the signature of right-aligned trailing labels (page
        numbers, roman numerals) following dot-leader-style entries in a
        table of contents, rather than a genuine second column of
        comparable content.

        Without this, `_gap_sweep_columns` correctly finds the gap
        between a TOC's title text and its right-aligned page-number
        column (title text can be very wide; page numbers cannot, so the
        gap between them is real and often large) but then reading order
        processes each detected column fully before moving to the next
        -- so every title gets read first, followed by every page
        number, rather than each title's own number appearing right
        after it. Confirmed on this project's own gold corpus
        (eval/pages/p008.png, a table of contents): merging the numbers
        back into the title column lets `_cluster_lines`'s existing
        Y-proximity + left-to-right-within-line logic place each number
        at the end of its own title's line, exactly where it belongs.

        Distinguished from a genuine second column (e.g. an index's two
        columns of name+citation entries, both containing full
        words/phrases of varying width) by width alone: a real second
        column has at least some entries as wide as ordinary text; a
        trailing label column does not, because every entry in it is a
        short number or numeral.
        """
        if len(columns) < 2:
            return columns

        narrow_threshold = 4.0 * glyph_height
        merged = [list(c) for c in columns]

        idx = len(merged) - 1
        while idx > 0:
            candidate = merged[idx]
            neighbor = merged[idx - 1]
            if (
                candidate
                and neighbor
                and all(s.bbox.width < narrow_threshold for s in candidate)
                and any(s.bbox.width >= narrow_threshold for s in neighbor)
            ):
                merged[idx - 1] = neighbor + candidate
                del merged[idx]
            idx -= 1

        return merged

    def _gap_sweep_columns(self, spans: List[Span], glyph_height: float) -> List[List[Span]]:
        """
        XY-cut to identify vertical column gaps.
        A vertical gap must be wider than ~1.8 * glyph_height (or ~35px)
        to form separate columns.

        Tries `_sweep_with_tolerance` at tolerance=0 first -- the original
        strict algorithm (a running max(xmax); any span whose xmin clears
        it by min_gap_width starts a new column) -- and only escalates to
        a higher tolerance if that finds no split at all. This makes the
        escalation strictly additive: it can only find columns the strict
        sweep missed, never change a case the strict sweep already
        handled, so pages/tests already relying on exact strict-sweep
        behavior are unaffected.

        Escalating matters because the strict sweep requires ABSOLUTE
        zero overlap: a single outlier span crossing the corridor
        anywhere merges the whole gap away, even when every other row
        shows a clear gap there. That's a real failure mode, not a
        hypothetical one: confirmed on this project's own gold corpus
        (eval/pages/p095.png, a genuine two-column index -- explicitly
        flagged in eval/gold/manifest.json as "the one real intra-page
        multi-column case in this book"). Most index entries are short,
        but one entry wraps across six continuation lines whose xmax
        reaches to ~2157px while the facing column's nearest entry starts
        at ~2175px -- an 18px gap on those rows, against a ~150-400px gap
        on every other row -- and that alone was enough to collapse the
        whole-page sweep to zero splits. The two columns then got read as
        a single block in raw top-to-bottom (y-sorted) order, interleaving
        unrelated left/right index entries line-by-line and corrupting
        the page (measured CER 0.57, the worst of this project's 14-page
        English gold corpus).

        An escalated split (tolerance > 0) is only accepted if it's
        reasonably BALANCED -- see `_is_balanced_split`. Without that
        check, escalating tolerance also introduced a real regression on
        a different page (eval/pages/p094.png, footnote-style numbered
        citations: "1. Quaid-i-Azam Speaks. p. 129."): the leading
        citation number is a narrow span, but unlike an index's dense,
        row-for-row-paired number column, here it's a SPARSE marker that
        only appears at the start of some entries, with continuation
        lines carrying no number at all. Measured concretely: escalating
        found a "column split" of sizes [59, 1] and [62, 1] -- a single
        outlier span peeled off as its own "column" -- versus p095/p096's
        genuine splits of [31, 32] and [5, 3]. Requiring both sides of an
        escalated split to be reasonably sized rejects the former while
        keeping the latter.
        """
        if len(spans) < 2:
            return [spans]

        min_gap_width = max(35.0, 1.8 * glyph_height)
        sorted_by_x = sorted(spans, key=lambda s: s.bbox.xmin)

        max_tolerance = max(2, round(0.2 * len(sorted_by_x)))
        for tolerance in range(0, max_tolerance + 1):
            splits = self._sweep_with_tolerance(sorted_by_x, min_gap_width, tolerance)
            if len(splits) > 1 and (tolerance == 0 or self._is_balanced_split(splits)):
                return splits

        return [spans]

    @staticmethod
    def _is_balanced_split(splits: List[List[Span]]) -> bool:
        """
        True if every resulting column group is large enough to
        plausibly be a genuine column rather than a single outlier span
        incidentally clearing the tolerance-relaxed boundary. Calibrated
        against this project's own gold corpus (see `_gap_sweep_columns`'s
        docstring): rejects [59, 1]/[62, 1] (a lone outlier, ~1.6% of
        the total) with wide margin below accepting [31, 32] (48%) and
        [5, 3] (37.5%), both genuine two-column pages.
        """
        total = sum(len(c) for c in splits)
        smallest = min(len(c) for c in splits)
        return smallest >= 2 and smallest >= 0.15 * total

    @staticmethod
    def _sweep_with_tolerance(
        sorted_by_x: List[Span], min_gap_width: float, tolerance: int
    ) -> List[List[Span]]:
        """
        Running-boundary gap sweep (spans already sorted by xmin) where
        the boundary is the xmax after excluding the `tolerance` largest
        xmax values seen so far in the current column -- i.e. up to
        `tolerance` outlier spans may extend arbitrarily far right
        without single-handedly blocking a gap the rest of the column
        shows clearly. tolerance=0 has no spans to exclude and is exactly
        the original strict running-max sweep.

        Maintained via a bounded min-heap of the (tolerance + 1) largest
        xmax values seen in the current column: once full, its smallest
        element is the boundary (the largest value that is NOT one of the
        `tolerance` excluded outliers).
        """
        import heapq

        splits: List[List[Span]] = []
        col_start = 0
        heap: List[float] = []

        for i, span in enumerate(sorted_by_x):
            if i > col_start:
                boundary = heap[0] if len(heap) > tolerance else max(heap)
                if span.bbox.xmin - boundary >= min_gap_width:
                    splits.append(sorted_by_x[col_start:i])
                    col_start = i
                    heap = []

            heapq.heappush(heap, span.bbox.xmax)
            if len(heap) > tolerance + 1:
                heapq.heappop(heap)

        splits.append(sorted_by_x[col_start:])
        return splits

    def _cluster_lines(self, spans: List[Span], glyph_height: float) -> List[Line]:
        """
        Groups spans into horizontal lines using adaptive vertical tolerance.
        """
        if not spans:
            return []

        # Sort spans primarily by top (ymin), secondarily by xmin
        sorted_spans = sorted(spans, key=lambda s: (s.bbox.ymin, s.bbox.xmin))

        lines: List[Line] = []
        vert_tolerance = max(8.0, 0.45 * glyph_height)

        for span in sorted_spans:
            # Try to place span in an existing line
            matched_line = None
            for line in lines:
                # Calculate vertical overlap or proximity
                line_center_y = line.bbox.center[1]
                span_center_y = span.bbox.center[1]

                if abs(span_center_y - line_center_y) <= vert_tolerance:
                    matched_line = line
                    break

            if matched_line:
                matched_line.spans.append(span)
                matched_line.bbox = matched_line.bbox.union(span.bbox)
            else:
                lines.append(Line(spans=[span], bbox=span.bbox))

        # Sort spans within each line left-to-right -- except an RTL-script
        # line (Arabic/Urdu/Persian/Uyghur), which reads right-to-left: the
        # per-character reversal in rapidocr_engine.py only fixes each
        # detection's own text, it says nothing about the order multiple
        # detections on the same line get concatenated in. Without this, two
        # Urdu words on one line still come out in the wrong order relative
        # to each other, even though each word individually reads correctly.
        for line in lines:
            is_rtl_line = any(contains_rtl_script(s.text) for s in line.spans)
            line.spans.sort(key=lambda s: s.bbox.xmin, reverse=is_rtl_line)

        # Sort lines top-to-bottom
        lines.sort(key=lambda l: l.bbox.ymin)

        return lines

    def _group_lines_into_blocks(
        self, lines: List[Line], col_idx: int, glyph_height: float
    ) -> List[Block]:
        """
        Groups consecutive lines into cohesive Block objects.
        """
        if not lines:
            return []

        blocks: List[Block] = []
        current_block_lines: List[Line] = [lines[0]]
        block_gap_threshold = max(25.0, 2.2 * glyph_height)

        for i in range(1, len(lines)):
            prev_line = current_block_lines[-1]
            curr_line = lines[i]

            line_gap = curr_line.bbox.ymin - prev_line.bbox.ymax

            if line_gap > block_gap_threshold:
                # Start new block
                block_bbox = current_block_lines[0].bbox
                for l in current_block_lines[1:]:
                    block_bbox = block_bbox.union(l.bbox)

                blocks.append(Block(
                    block_type=BlockType.TEXT,
                    lines=current_block_lines,
                    bbox=block_bbox,
                    column_index=col_idx,
                ))
                current_block_lines = [curr_line]
            else:
                current_block_lines.append(curr_line)

        if current_block_lines:
            block_bbox = current_block_lines[0].bbox
            for l in current_block_lines[1:]:
                block_bbox = block_bbox.union(l.bbox)

            blocks.append(Block(
                block_type=BlockType.TEXT,
                lines=current_block_lines,
                bbox=block_bbox,
                column_index=col_idx,
            ))

        return blocks
