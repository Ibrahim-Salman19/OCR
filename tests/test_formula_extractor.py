"""
tests/test_formula_extractor.py

Unit tests for Mathematical Formula Recognition & KaTeX conversion.
"""

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


def test_convert_to_latex_nested_parens_in_sqrt():
    """GAP-12: the original non-greedy `sqrt\\((.*?)\\)` regex matched up to
    the FIRST ")" it saw, so a nested-paren argument like sqrt((a+b)/(c+d))
    produced an unbalanced result ("\\sqrt{(a+b}/(c+d))"). The balanced-paren
    scanner must find the true matching close paren instead.
    """
    latex = FormulaExtractor.convert_to_latex("sqrt((a+b)/(c+d))")
    assert latex == r"\sqrt{(a+b)/(c+d)}"
    assert latex.count("{") == latex.count("}")


def test_convert_to_latex_nested_sqrt():
    latex = FormulaExtractor.convert_to_latex("sqrt(sqrt(x))")
    assert latex == r"\sqrt{\sqrt{x}}"


def test_convert_to_latex_unbalanced_sqrt_returns_original_text():
    """GAP-12: a dropped closing paren (a plausible OCR misread) must return
    the original text unchanged rather than emitting broken LaTeX with an
    unresolved "\\sqrt{" and no matching "}".
    """
    raw = "sqrt(unbalanced expression"
    assert FormulaExtractor.convert_to_latex(raw) == raw


def test_convert_to_latex_never_emits_unbalanced_braces():
    """Invariant: for any input, convert_to_latex's output has balanced {}."""
    cases = [
        "sqrt((a+b)/(c+d))",
        "sqrt(unbalanced",
        "sqrt(sqrt(x))",
        "alpha / beta",
        "sqrt(x^2 + y^2)",
        "))))((((",
        "",
    ]
    for case in cases:
        latex = FormulaExtractor.convert_to_latex(case)
        assert latex.count("{") == latex.count("}"), f"Unbalanced braces for input {case!r}: {latex!r}"


def test_process_block():
    span = Span(text="f(x) = a*x^2 + b*x + c", bbox=BoundingBox(xmin=0, ymin=0, xmax=100, ymax=20))
    line = Line(spans=[span], bbox=span.bbox)
    block = Block(lines=[line], bbox=span.bbox)

    processed = FormulaExtractor.process_block(block)
    assert processed.block_type == BlockType.FORMULA
    assert "$$" in processed.text
