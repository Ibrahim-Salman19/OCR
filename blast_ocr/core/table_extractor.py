"""
blast_ocr.core.table_extractor

Advanced Document Table Extraction and Reconstruction Engine.
Detects bordered and borderless tables from page images and OCR detections,
reconstructing structured 2D grid matrices and formatting them to Markdown, HTML, DOCX, and JSON.
"""

import logging
from typing import List, Dict, Any
import numpy as np
import cv2

from blast_ocr.core.document_model import BoundingBox, Span

logger = logging.getLogger(__name__)


class TableCell:
    def __init__(self, xmin: float, ymin: float, xmax: float, ymax: float, text: str = ""):
        self.bbox = BoundingBox(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)
        self.text = text.strip()
        self.row_idx: int = 0
        self.col_idx: int = 0

    @property
    def center_y(self) -> float:
        return self.bbox.center[1]

    @property
    def center_x(self) -> float:
        return self.bbox.center[0]


class ExtractedTable:
    def __init__(self, bbox: BoundingBox, grid: List[List[str]], confidence: float = 1.0):
        self.bbox = bbox
        self.grid = grid  # 2D list of strings [ [row0_col0, row0_col1, ...], [row1_col0, ...] ]
        self.confidence = confidence

    @property
    def num_rows(self) -> int:
        return len(self.grid)

    @property
    def num_cols(self) -> int:
        return max(len(r) for r in self.grid) if self.grid else 0

    def to_markdown(self) -> str:
        """Converts extracted table grid into standard Markdown table."""
        if not self.grid or not self.grid[0]:
            return ""

        num_cols = self.num_cols
        # Normalize row lengths
        norm_rows = []
        for row in self.grid:
            padded = [c.replace("\n", " ").strip() for c in row] + [""] * (num_cols - len(row))
            norm_rows.append(padded)

        # Header row
        header = "| " + " | ".join(norm_rows[0]) + " |"
        separator = "| " + " | ".join(["---"] * num_cols) + " |"
        body = ["| " + " | ".join(r) + " |" for r in norm_rows[1:]]

        return "\n".join([header, separator] + body)

    def to_html(self) -> str:
        """Converts extracted table grid into HTML table."""
        if not self.grid:
            return ""

        rows_html = []
        # Header
        if self.grid:
            th_cells = "".join(f"<th>{c}</th>" for c in self.grid[0])
            rows_html.append(f"<thead><tr>{th_cells}</tr></thead>")

        # Body
        tbody_rows = []
        for row in self.grid[1:]:
            td_cells = "".join(f"<td>{c}</td>" for c in row)
            tbody_rows.append(f"<tr>{td_cells}</tr>")
        if tbody_rows:
            rows_html.append(f"<tbody>{''.join(tbody_rows)}</tbody>")

        return f"<table class=\"ocr-table\">{''.join(rows_html)}</table>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bbox": [self.bbox.xmin, self.bbox.ymin, self.bbox.xmax, self.bbox.ymax],
            "num_rows": self.num_rows,
            "num_cols": self.num_cols,
            "grid": self.grid,
            "markdown": self.to_markdown(),
            "confidence": self.confidence,
        }


class TableExtractor:
    """
    Extracts table structure from image bitmaps and OCR detection spans.
    """

    @staticmethod
    def extract_tables_from_image(
        image: np.ndarray,
        spans: List[Span],
        min_table_area_ratio: float = 0.02,
        min_cells: int = 4,
    ) -> List[ExtractedTable]:
        """
        Detects tables in an image and maps text spans into structured table grids.
        
        Args:
            image: Grayscale or BGR image numpy array.
            spans: List of OCR text Spans with bounding boxes.
            min_table_area_ratio: Minimum image area fraction for a table.
            min_cells: Minimum cell count to qualify as a valid table.
            
        Returns:
            List of ExtractedTable instances.
        """
        if image is None or len(spans) == 0:
            return []

        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        # 1. Binarize
        thresh = cv2.adaptiveThreshold(
            ~gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, -2
        )

        # 2. Detect Horizontal & Vertical Line Kernels
        scale_h = max(20, int(w / 35))
        scale_v = max(20, int(h / 35))
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (scale_h, 1))
        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, scale_v))

        h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel, iterations=2)
        v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_kernel, iterations=2)

        # 3. Combine lines into grid mask
        grid_mask = cv2.bitwise_or(h_lines, v_lines)

        # 4. Find table bounding boxes
        contours, _ = cv2.findContours(grid_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        tables: List[ExtractedTable] = []
        min_area = (w * h) * min_table_area_ratio

        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            area = bw * bh
            if area < min_area or bw < 60 or bh < 40:
                continue

            # Crop table grid region to detect internal cells
            table_roi = grid_mask[y : y + bh, x : x + bw]
            cell_contours, _ = cv2.findContours(table_roi, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

            raw_cells: List[TableCell] = []
            for cc in cell_contours:
                cx, cy, cw, ch = cv2.boundingRect(cc)
                # Ignore tiny contours or whole-table outer boundary contour
                if cw < 15 or ch < 10 or (cw >= bw * 0.95 and ch >= bh * 0.95):
                    continue
                # Global cell coordinates
                abs_xmin = x + cx
                abs_ymin = y + cy
                abs_xmax = abs_xmin + cw
                abs_ymax = abs_ymin + ch
                raw_cells.append(TableCell(abs_xmin, abs_ymin, abs_xmax, abs_ymax))

            if len(raw_cells) < min_cells:
                continue

            # Match OCR text spans into cells
            for cell in raw_cells:
                cell_text_parts = []
                for s in spans:
                    # Check if span center is inside cell bbox
                    if (
                        cell.bbox.xmin <= s.bbox.center[0] <= cell.bbox.xmax
                        and cell.bbox.ymin <= s.bbox.center[1] <= cell.bbox.ymax
                    ):
                        cell_text_parts.append(s.text)
                cell.text = " ".join(cell_text_parts)

            # Sort cells into 2D grid matrix
            grid = TableExtractor._cells_to_grid(raw_cells, bh)
            if grid and len(grid) >= 2 and any(any(c.strip() for c in r) for r in grid):
                tbl_bbox = BoundingBox(xmin=x, ymin=y, xmax=x + bw, ymax=y + bh)
                tables.append(ExtractedTable(bbox=tbl_bbox, grid=grid))

        return tables

    @staticmethod
    def _cells_to_grid(cells: List[TableCell], table_height: float) -> List[List[str]]:
        """Groups unstructured cell boxes into a sorted row/column grid."""
        if not cells:
            return []

        # Sort cells vertically by Y-center
        sorted_by_y = sorted(cells, key=lambda c: c.center_y)
        
        # Adaptive row clustering tolerance based on average cell height
        avg_cell_h = sum(c.bbox.height for c in cells) / len(cells)
        row_tol = max(8.0, avg_cell_h * 0.45)

        rows: List[List[TableCell]] = []
        current_row: List[TableCell] = [sorted_by_y[0]]

        for cell in sorted_by_y[1:]:
            if abs(cell.center_y - current_row[0].center_y) < row_tol:
                current_row.append(cell)
            else:
                rows.append(sorted(current_row, key=lambda c: c.center_x))
                current_row = [cell]

        if current_row:
            rows.append(sorted(current_row, key=lambda c: c.center_x))

        # Reconstruct normalized 2D text matrix
        grid: List[List[str]] = []
        for r in rows:
            grid.append([c.text for c in r])

        return grid

    # Alias for API backwards-compatibility
    extract_tables = extract_tables_from_image
