"""
tests/test_formula_extractor.py

Unit tests for Mathematical Formula Recognition & KaTeX conversion.
"""

import pytest
from blast_ocr.core.formula_extractor import FormulaExtractor
from blast_ocr.core.document_model import Block, Line, Span, BoundingBox, BlockType


def test_is_math_block():
    assert FormulaExtractor.is_math_block("E = mc^2")
    assert FormulaExtractor.is_math_block("f(x) = sin(x) + cos(x)")
    assert FormulaExtractor.is_math_block("alpha + beta = gamma / 2")
    assert not FormulaExtractor.is_math_block("This is a regular sentence describing a book chapter.")


def test_convert_to_latex():
    raw = "alpha / beta"
    latex = FormulaExtractor.convert_to_latex(raw)
    assert r"\frac{\alpha}{\beta}" in latex or (r"\alpha" in latex and r"\beta" in latex)

    raw_sqrt = "sqrt(x^2 + y^2)"
    latex_sqrt = FormulaExtractor.convert_to_latex(raw_sqrt)
    assert r"\sqrt{x^2 + y^2}" in latex_sqrt or r"\sqrt" in latex_sqrt


def test_process_block():
    span = Span(text="f(x) = a*x^2 + b*x + c", bbox=BoundingBox(xmin=0, ymin=0, xmax=100, ymax=20))
    line = Line(spans=[span], bbox=span.bbox)
    block = Block(lines=[line], bbox=span.bbox)

    processed = FormulaExtractor.process_block(block)
    assert processed.block_type == BlockType.FORMULA
    assert "$$" in processed.text
