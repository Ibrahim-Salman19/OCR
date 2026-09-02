"""
blast_ocr.core.script_detection

Script-direction detection shared by the OCR engine layer (which needs it to
pick a recognition model and undo CTC-decode reversal) and the layout engine
(which needs it to order detections in correct reading order). Kept as a
dependency-free leaf module -- blast_ocr.core.layout must not import from
blast_ocr.core.engines.*, since blast_ocr.core.engines/__init__.py imports
engines that themselves import LayoutEngine, which would be a circular import.
"""

from __future__ import annotations

# Perso-Arabic script family: distinct languages, shared base script and
# character repertoire.
RTL_SCRIPT_LANGUAGES = {"ar", "ur", "fa", "ug"}

# Unicode blocks covering Arabic-script letters (Arabic, Arabic Supplement,
# Arabic Extended-A, Arabic Presentation Forms A/B -- the ranges that
# actually appear in Arabic/Persian/Urdu/Uyghur text, including the
# Urdu/Persian-specific letters PP-OCRv5's dictionary emits).
_ARABIC_SCRIPT_RANGES = (
    (0x0600, 0x06FF),
    (0x0750, 0x077F),
    (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF),
    (0xFE70, 0xFEFF),
)


def contains_rtl_script(text: str) -> bool:
    """True if `text` contains at least one Arabic-script codepoint.

    Used both to decide whether a detected text line needs the RTL
    left-to-right-output reversal fixup (a page shot through the
    Arabic-script recognition model can still contain pure-Latin/digit
    fragments -- page numbers, footnote markers -- that must NOT be
    reversed), and by the layout engine to decide whether a line's spans
    or a band's columns should be ordered right-to-left instead of
    left-to-right.
    """
    return any(
        any(lo <= ord(ch) <= hi for lo, hi in _ARABIC_SCRIPT_RANGES) for ch in text
    )
