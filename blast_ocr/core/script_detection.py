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

from typing import Optional

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


def _is_rtl_char(ch: str) -> bool:
    return any(lo <= ord(ch) <= hi for lo, hi in _ARABIC_SCRIPT_RANGES)


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
    return any(_is_rtl_char(ch) for ch in text)


def reorder_rtl_visual_to_logical(text: str) -> str:
    """
    Convert one line of Arabic-script-model output from the CTC
    recognizer's raw left-to-right visual (pixel) order into correct
    logical reading order.

    A blind whole-string reversal (`text[::-1]`) is only correct when the
    entire line is Arabic-script. It breaks the common case of a mixed
    line -- e.g. an Urdu sentence containing an embedded English word or a
    number, which is routine in real Urdu textbooks. The recognizer scans
    strictly left-to-right in pixel space:

    - For an RTL (Arabic-script) run, that produces the *reverse* of
      logical order, because within an RTL word the first logical letter
      sits at the right edge of that word's pixel span -- scanning
      left-to-right hits the last logical letter first.
    - For an LTR run (Latin letters, digits, punctuation), that already
      produces correct logical order, since such glyphs are drawn on the
      page left-to-right in the same order they're read.

    Recovering logical order therefore needs two independent operations:
    mirror the left-to-right sequence of *runs* (each run keeps its own
    extracted characters), and additionally reverse the *internal*
    character order only within each RTL run, leaving LTR runs
    (including embedded digits, e.g. a date or page number) untouched
    internally. For a line that is entirely one script, this reduces
    exactly to the old `text[::-1]` behavior.
    """
    if not text:
        return text

    runs: list[tuple[bool, str]] = []
    current_class: Optional[bool] = None
    current_chars: list[str] = []
    for ch in text:
        cls = _is_rtl_char(ch)
        if cls != current_class and current_chars:
            runs.append((bool(current_class), "".join(current_chars)))
            current_chars = []
        current_class = cls
        current_chars.append(ch)
    if current_chars:
        runs.append((bool(current_class), "".join(current_chars)))

    reordered = [
        (run_text[::-1] if is_rtl else run_text) for is_rtl, run_text in reversed(runs)
    ]
    return "".join(reordered)
