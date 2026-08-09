import os
import re
import sys
import logging
from pathlib import Path
from typing import Optional, Tuple, List
from pptx import Presentation as DefaultPresentation
from docx import Document as DefaultDocument

import defusedxml
defusedxml.defuse_stdlib()

from blast_ocr.core.exceptions import OCREngineError, OutputWriteError

logger = logging.getLogger(__name__)


def _get_presentation_cls():
    extractor_mod = sys.modules.get("blast_ocr.core.extractor")
    if extractor_mod and hasattr(extractor_mod, "Presentation"):
        return extractor_mod.Presentation
    return DefaultPresentation


def _get_document_cls():
    extractor_mod = sys.modules.get("blast_ocr.core.extractor")
    if extractor_mod and hasattr(extractor_mod, "Document"):
        return extractor_mod.Document
    return DefaultDocument


def sanitize_for_xml(text: Optional[str]) -> str:
    """Removes control characters that are invalid in XML / DOCX schemas."""
    if not text:
        return ""
    return re.sub(r"[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\u10000-\u10FFFF]", "", text)


def save_output(
    text: str, base_name: str, output_dir: str
) -> Tuple[str, Optional[str]]:
    """Saves to Markdown and DOCX."""
    os.makedirs(output_dir, exist_ok=True)

    # 1. Save Markdown
    md_path = os.path.join(output_dir, f"{base_name}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(text)

    # 2. Save DOCX
    docx_path = os.path.join(output_dir, f"{base_name}.docx")
    try:
        DocCls = _get_document_cls()
        doc = DocCls()
        doc.add_heading(base_name, 0)

        clean_text = sanitize_for_xml(text)

        for line in clean_text.split("\n"):
            line = line.strip()
            if line.startswith("## "):
                doc.add_heading(line.replace("## ", ""), level=2)
            elif line.startswith("---"):
                doc.add_page_break()
            else:
                if line:
                    doc.add_paragraph(line)
        doc.save(docx_path)
    except Exception as e:
        logger.error(f"DOCX generation failed: {e}")
        docx_path = None

    return md_path, docx_path


def extract_from_pptx(pptx_path: str) -> str:
    """Extracts text from slides, including notes and tables."""
    text_content = []
    try:
        PrsCls = _get_presentation_cls()
        prs = PrsCls(pptx_path)
        for i, slide in enumerate(prs.slides, start=1):
            slide_text = []
            slide_text.append(f"## Slide {i}")

            # 1. Shapes Text
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    slide_text.append(shape.text)

                # 2. Tables
                if hasattr(shape, "has_table") and shape.has_table:
                    for row in shape.table.rows:
                        row_text = " | ".join(
                            [cell.text_frame.text for cell in row.cells]
                        )
                        slide_text.append(f"| {row_text} |")

            # 3. Notes
            if (
                hasattr(slide, "has_notes_slide")
                and slide.has_notes_slide
                and slide.notes_slide.notes_text_frame
            ):
                notes = slide.notes_slide.notes_text_frame.text
                if notes:
                    slide_text.append(f"> **Notes:** {notes}")

            text_content.append("\n".join(slide_text))

        return "\n\n---\n\n".join(text_content)
    except Exception as e:
        logger.error(f"PPTX extraction failed: {e}")
        raise OCREngineError(f"PPTX extraction failed: {e}") from e
