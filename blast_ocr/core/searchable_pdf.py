"""
blast_ocr.core.searchable_pdf

Searchable PDF (Sandwich PDF) Generator.
Creates dual-layer PDF documents with high-resolution scan background and
invisible, selectable, searchable OCR text overlay layers with exact bounding box alignment.
Supports PyMuPDF (fitz) with fallback to ReportLab.
"""

import os
import io
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import numpy as np
import cv2
from PIL import Image

logger = logging.getLogger(__name__)


class SearchablePDFGenerator:
    """
    Constructs high-fidelity Searchable PDFs ("Sandwich PDFs") containing
    original scanned images with an invisible, selectable text layer.
    """

    @staticmethod
    def create_from_page_images(
        page_images: List[Union[str, np.ndarray, Image.Image]],
        page_ocr_results: List[Dict[str, Any]],
        output_pdf_path: str,
        title: Optional[str] = None,
        author: Optional[str] = "BLAST OCR",
    ) -> str:
        """
        Builds a multi-page Searchable PDF from a list of page images and OCR detections.
        
        Args:
            page_images: List of filepaths, numpy arrays, or PIL Images.
            page_ocr_results: List of page OCR dictionaries (containing 'details' or 'page_model').
            output_pdf_path: Target destination path for the generated PDF.
            title: Optional document metadata title.
            author: Optional document metadata author.
            
        Returns:
            Absolute path string to the generated searchable PDF.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_pdf_path)), exist_ok=True)
        
        import importlib.util
        if importlib.util.find_spec("fitz") is not None:
            return SearchablePDFGenerator._create_with_fitz(
                page_images, page_ocr_results, output_pdf_path, title, author
            )
        else:
            logger.info("fitz not found, falling back to ReportLab for Searchable PDF generation.")
            return SearchablePDFGenerator._create_with_reportlab(
                page_images, page_ocr_results, output_pdf_path, title, author
            )

    @staticmethod
    def _create_with_fitz(
        page_images: List[Union[str, np.ndarray, Image.Image]],
        page_ocr_results: List[Dict[str, Any]],
        output_pdf_path: str,
        title: Optional[str],
        author: Optional[str],
    ) -> str:
        import fitz

        doc = fitz.open()

        for idx, (img_input, ocr_data) in enumerate(zip(page_images, page_ocr_results)):
            # Normalize image to bytes and get dimensions
            img_bytes, width, height = SearchablePDFGenerator._get_image_bytes_and_dims(img_input)
            
            # Create page with exact point dimensions matching image
            page = doc.new_page(width=float(width), height=float(height))
            page_rect = fitz.Rect(0, 0, float(width), float(height))
            
            # 1. Insert original scan image as background
            page.insert_image(page_rect, stream=img_bytes)

            # 2. Extract bounding boxes and text
            boxes = SearchablePDFGenerator._extract_text_boxes(ocr_data, width, height)

            # 3. Insert invisible text layer with precise baseline coordinates
            for box in boxes:
                text = box["text"].strip()
                if not text:
                    continue
                
                xmin, ymin, xmax, ymax = box["xmin"], box["ymin"], box["xmax"], box["ymax"]
                box_w = max(1.0, xmax - xmin)
                box_h = max(1.0, ymax - ymin)

                # Calculate font size to fit width and height smoothly
                font_w_unit = fitz.get_text_length(text, fontname="helv", fontsize=1.0)
                if font_w_unit > 0:
                    font_size = min(box_h * 0.80, (box_w / font_w_unit) * 1.05)
                else:
                    font_size = box_h * 0.80
                
                font_size = max(4.0, min(font_size, 96.0))
                
                # Baseline coordinate: near bottom of box
                baseline_y = float(ymax - (box_h * 0.15))
                point = fitz.Point(float(xmin), baseline_y)

                # render_mode=3 is invisible text (no stroke, no fill) in PDF specification
                try:
                    page.insert_text(
                        point,
                        text,
                        fontsize=font_size,
                        fontname="helv",
                        render_mode=3,
                    )
                except Exception as text_err:
                    logger.debug(f"Failed to insert invisible text span '{text}': {text_err}")

        # Set document metadata
        meta = doc.metadata or {}
        if title:
            meta["title"] = title
        if author:
            meta["author"] = author
        meta["creator"] = "B.L.A.S.T. Production OCR Engine"
        meta["producer"] = "PyMuPDF Searchable PDF Pipeline"
        doc.set_metadata(meta)

        doc.save(output_pdf_path, garbage=4, deflate=True)
        doc.close()
        return str(Path(output_pdf_path).resolve())

    @staticmethod
    def _create_with_reportlab(
        page_images: List[Union[str, np.ndarray, Image.Image]],
        page_ocr_results: List[Dict[str, Any]],
        output_pdf_path: str,
        title: Optional[str],
        author: Optional[str],
    ) -> str:
        from reportlab.pdfgen import canvas
        from reportlab.lib.colors import Color

        c = canvas.Canvas(output_pdf_path)
        if title:
            c.setTitle(title)
        if author:
            c.setAuthor(author)
        c.setCreator("B.L.A.S.T. Production OCR Engine")

        for img_input, ocr_data in zip(page_images, page_ocr_results):
            img_bytes, width, height = SearchablePDFGenerator._get_image_bytes_and_dims(img_input)
            c.setPageSize((width, height))

            # Draw image in background
            pil_img = Image.open(io.BytesIO(img_bytes))
            c.drawInlineImage(pil_img, 0, 0, width=width, height=height)

            # Draw invisible text overlay (alpha = 0)
            c.setFillColor(Color(0, 0, 0, alpha=0))
            boxes = SearchablePDFGenerator._extract_text_boxes(ocr_data, width, height)

            for box in boxes:
                text = box["text"].strip()
                if not text:
                    continue
                xmin, ymin, ymax = box["xmin"], box["ymin"], box["ymax"]
                box_h = max(1.0, ymax - ymin)
                font_size = max(4.0, min(box_h * 0.80, 96.0))
                c.setFont("Helvetica", font_size)
                
                # ReportLab Y-origin is bottom-left
                rl_y = height - ymax + (box_h * 0.15)
                c.drawString(xmin, rl_y, text)

            c.showPage()

        c.save()
        return str(Path(output_pdf_path).resolve())

    @staticmethod
    def _get_image_bytes_and_dims(img_input: Union[str, np.ndarray, Image.Image]) -> tuple:
        """Helper to extract JPEG/PNG bytes, width, and height."""
        if isinstance(img_input, (str, Path)):
            img_path = str(img_input)
            with open(img_path, "rb") as f:
                b = f.read()
            pil = Image.open(io.BytesIO(b))
            return b, pil.width, pil.height
        elif isinstance(img_input, Image.Image):
            buf = io.BytesIO()
            img_input.save(buf, format="PNG")
            b = buf.getvalue()
            return b, img_input.width, img_input.height
        elif isinstance(img_input, np.ndarray):
            h, w = img_input.shape[:2]
            success, enc = cv2.imencode(".png", img_input)
            if not success:
                raise ValueError("Failed to encode numpy image array to PNG")
            return enc.tobytes(), w, h
        else:
            raise TypeError(f"Unsupported image input type: {type(img_input)}")

    @staticmethod
    def _extract_text_boxes(ocr_data: Dict[str, Any], width: int, height: int) -> List[Dict[str, Any]]:
        """Parses various OCR result payload formats into normalized bounding boxes."""
        boxes = []
        
        # Format 1: page_model from DocumentModel
        page_model = ocr_data.get("page_model")
        if isinstance(page_model, dict) and "blocks" in page_model:
            for block in page_model.get("blocks", []):
                for line in block.get("lines", []):
                    # Check if line has spans
                    spans = line.get("spans", [])
                    if spans:
                        for span in spans:
                            text = span.get("text", "")
                            bbox = span.get("bbox", {})
                            if text and bbox:
                                boxes.append({
                                    "text": text,
                                    "xmin": float(bbox.get("xmin", 0)),
                                    "ymin": float(bbox.get("ymin", 0)),
                                    "xmax": float(bbox.get("xmax", width)),
                                    "ymax": float(bbox.get("ymax", height)),
                                })
                    else:
                        line_text = line.get("text", "")
                        bbox = line.get("bbox", {})
                        if line_text and bbox:
                            boxes.append({
                                "text": line_text,
                                "xmin": float(bbox.get("xmin", 0)),
                                "ymin": float(bbox.get("ymin", 0)),
                                "xmax": float(bbox.get("xmax", width)),
                                "ymax": float(bbox.get("ymax", height)),
                            })
            if boxes:
                return boxes

        # Format 2: details array [ {text, conf, bbox: [x1,y1, x2,y1, x2,y2, x1,y2] or [xmin,ymin,xmax,ymax]} ]
        details = ocr_data.get("details", [])
        if details:
            for item in details:
                text = item.get("text", "")
                raw_bbox = item.get("bbox", [])
                if not text or not raw_bbox:
                    continue
                if len(raw_bbox) == 4:
                    boxes.append({
                        "text": text,
                        "xmin": float(raw_bbox[0]),
                        "ymin": float(raw_bbox[1]),
                        "xmax": float(raw_bbox[2]),
                        "ymax": float(raw_bbox[3]),
                    })
                elif len(raw_bbox) == 8:
                    xs = [raw_bbox[0], raw_bbox[2], raw_bbox[4], raw_bbox[6]]
                    ys = [raw_bbox[1], raw_bbox[3], raw_bbox[5], raw_bbox[7]]
                    boxes.append({
                        "text": text,
                        "xmin": float(min(xs)),
                        "ymin": float(min(ys)),
                        "xmax": float(max(xs)),
                        "ymax": float(max(ys)),
                    })
            if boxes:
                return boxes

        # Format 3: Raw text fallback (spread evenly across page)
        raw_text = ocr_data.get("text", "")
        if raw_text:
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            if lines:
                line_height = height / max(1, len(lines) + 2)
                for i, line_text in enumerate(lines):
                    boxes.append({
                        "text": line_text,
                        "xmin": float(width * 0.05),
                        "ymin": float((i + 1) * line_height),
                        "xmax": float(width * 0.95),
                        "ymax": float((i + 2) * line_height),
                    })

        return boxes
