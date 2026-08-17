"""
blast_ocr.core.tier0_extractor

Tier-0 Native Text Extraction and Quality Router (Phase 3 of Execution Plan v2).
Uses pypdfium2 (Apache-2.0) to analyze and extract native text layers from born-digital PDFs,
scoring character count, printable ratio, replacement characters, whitespace sanity,
and duplicate text before deciding whether to pass native text or route to OCR.
"""

from typing import Tuple
import logging
import pypdfium2 as pdfium
from blast_ocr.core.models import NativeTextQuality, RouteDecision

logger = logging.getLogger(__name__)


class Tier0Extractor:
    """Quality classifier and native text extraction router for PDF documents."""

    MIN_TEXT_LENGTH: int = 50
    ALPHANUMERIC_RATIO_FLOOR: float = 0.65

    @classmethod
    def analyze_native_text_quality(cls, text: str) -> NativeTextQuality:
        """
        Evaluates extracted native text using multi-factor quality heuristics:
        character count, printable character ratio, unicode replacement character ratio,
        alphanumeric density, whitespace sanity, and duplication ratio.
        """
        clean_text = text.strip()
        char_len = len(clean_text)
        if char_len == 0:
            return NativeTextQuality(
                character_count=0,
                printable_ratio=0.0,
                unicode_replacement_ratio=0.0,
                alphanumeric_ratio=0.0,
                whitespace_sanity=0.0,
                duplicate_ratio=0.0,
                quality_score=0.0,
                decision=RouteDecision.OCR_REQUIRED,
            )

        printable_chars = sum(1 for c in clean_text if c.isprintable())
        printable_ratio = printable_chars / float(char_len)

        bad_unicode_chars = sum(1 for c in clean_text if c == '\ufffd' or 0xE000 <= ord(c) <= 0xF8FF)
        unicode_replacement_ratio = bad_unicode_chars / float(char_len)

        alphanumeric_chars = sum(1 for c in clean_text if c.isalnum() or c.isspace())
        alphanumeric_ratio = alphanumeric_chars / float(char_len)

        # Whitespace sanity: excessive space ratio indicates unmapped glyph kerning issues
        space_chars = sum(1 for c in clean_text if c.isspace())
        space_ratio = space_chars / float(char_len)
        whitespace_sanity = 1.0 - abs(space_ratio - 0.18) if space_ratio > 0.4 else 1.0

        # Duplicate ratio: check for repeated overlapping text layers
        lines = [line.strip() for line in clean_text.split('\n') if line.strip()]
        unique_lines = set(lines)
        duplicate_ratio = 1.0 - (len(unique_lines) / float(len(lines))) if lines else 0.0

        # Calculate composite quality score
        score = 0.98
        if char_len < cls.MIN_TEXT_LENGTH:
            score -= 0.7
        if printable_ratio < 0.90:
            score -= 0.3
        if unicode_replacement_ratio > 0.02:
            score -= 0.5
        if alphanumeric_ratio < cls.ALPHANUMERIC_RATIO_FLOOR:
            score -= 0.4
        if duplicate_ratio > 0.35:
            score -= 0.3
        score = max(0.0, min(1.0, score))

        if score >= 0.85:
            decision = RouteDecision.PASS_NATIVE
        elif score >= 0.50:
            decision = RouteDecision.HYBRID_REQUIRED
        else:
            decision = RouteDecision.OCR_REQUIRED

        return NativeTextQuality(
            character_count=char_len,
            printable_ratio=round(printable_ratio, 4),
            unicode_replacement_ratio=round(unicode_replacement_ratio, 4),
            alphanumeric_ratio=round(alphanumeric_ratio, 4),
            whitespace_sanity=round(whitespace_sanity, 4),
            duplicate_ratio=round(duplicate_ratio, 4),
            quality_score=round(score, 4),
            decision=decision,
        )

    @classmethod
    def evaluate_native_text_quality(cls, text: str) -> float:
        """Legacy quality evaluation helper returning scalar score 0.0-1.0."""
        return cls.analyze_native_text_quality(text).quality_score

    @classmethod
    def extract_native_page_text(cls, pdf_path: str, page_index: int) -> Tuple[str, float]:
        """
        Attempts native text extraction from a PDF page using pypdfium2.
        
        Args:
            pdf_path: Absolute path to PDF file.
            page_index: 0-indexed page integer.
            
        Returns:
            Tuple of (extracted_text: str, quality_score: float 0.0-1.0).
        """
        try:
            pdf = pdfium.PdfDocument(pdf_path)
            if page_index < 0 or page_index >= len(pdf):
                return "", 0.0

            page = pdf[page_index]
            textpage = page.get_textpage()
            text = textpage.get_text_range() or ""
            pdf.close()

            quality = cls.analyze_native_text_quality(text)
            return text.strip(), quality.quality_score

        except Exception as e:
            logger.debug(f"Tier-0 extraction failed for {pdf_path} p{page_index}: {e}")
            return "", 0.0
