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
            return self._gap_sweep_columns(spans, glyph_height)

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
                result.extend(self._gap_sweep_columns(bands[i], glyph_height))
            result.append([header])
        if bands[-1]:
            result.extend(self._gap_sweep_columns(bands[-1], glyph_height))

        return result

    def _gap_sweep_columns(self, spans: List[Span], glyph_height: float) -> List[List[Span]]:
        """
        Recursive XY-cut to identify vertical column gaps.
        A vertical gap must be wider than 2.0 * glyph_height (or ~40px) to form separate columns.
        """
        if len(spans) < 2:
            return [spans]

        # Sort spans by xmin
        sorted_by_x = sorted(spans, key=lambda s: s.bbox.xmin)

        # Search for vertical whitespace gap that splits spans into distinct horizontal columns
        # Sweep right through spans, tracking current maximum xmax
        splits = []
        current_max_x = sorted_by_x[0].bbox.xmax
        col_start = 0

        min_gap_width = max(35.0, 1.8 * glyph_height)

        for i in range(1, len(sorted_by_x)):
            span = sorted_by_x[i]
            gap = span.bbox.xmin - current_max_x

            if gap >= min_gap_width:
                # Valid vertical column gap found!
                splits.append(sorted_by_x[col_start:i])
                col_start = i

            current_max_x = max(current_max_x, span.bbox.xmax)

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

        # Sort spans within each line left-to-right
        for line in lines:
            line.spans.sort(key=lambda s: s.bbox.xmin)

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
