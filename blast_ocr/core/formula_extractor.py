"""
blast_ocr.core.formula_extractor

Mathematical Formula & Equation Recognition for B.L.A.S.T. OCR Protocol.
Detects inline and display mathematical formulas, subscripts, superscripts,
Greek symbols, and converts them to standardized KaTeX / LaTeX Markdown blocks.
"""

import re
from dataclasses import dataclass

from blast_ocr.core.document_model import Block, BlockType, Span, Line


@dataclass
class FormulaMatch:
    raw_text: str
    latex_text: str
    is_display_block: bool
    confidence: float


class FormulaExtractor:
    """
    Detects and normalizes mathematical equations and scientific notation.
    """

    GREEK_SYMBOLS = {
        "alpha": "\\alpha", "beta": "\\beta", "gamma": "\\gamma", "delta": "\\delta",
        "epsilon": "\\epsilon", "theta": "\\theta", "lambda": "\\lambda", "mu": "\\mu",
        "pi": "\\pi", "sigma": "\\sigma", "omega": "\\omega", "Delta": "\\Delta",
        "Sigma": "\\Sigma", "Omega": "\\Omega", "Phi": "\\Phi", "Psi": "\\Psi",
    }

    MATH_OPERATORS = {
        "sum": "\\sum", "int": "\\int", "prod": "\\prod", "sqrt": "\\sqrt",
        "+-": "\\pm", "<=": "\\le", ">=": "\\ge", "!=": "\\neq",
        "approx": "\\approx", "infty": "\\infty", "->": "\\rightarrow",
        "<->": "\\leftrightarrow", "times": "\\times", "div": "\\div",
    }

    # Regex heuristic indicators for mathematical equations
    MATH_INDICATOR_PATTERN = re.compile(
        r"(\b(sin|cos|tan|log|ln|exp|det|lim)\b|"
        r"[\^_\+\-\*\/=\<\>\±\∫\∑\∏\√\∞\α\β\γ\δ\θ\λ\μ\π\σ\ω]|\b[a-zA-Z]\s*=\s*[\d\w\+\-\*\/])"
    )

    DISPLAY_EQ_PATTERN = re.compile(r"^\s*(\([0-9]+(\.[0-9]+)*\)|\[[0-9]+\])?\s*([a-zA-Z0-9_\^\+\-\*\/\(\)\=\s]{4,})\s*(\([0-9]+(\.[0-9]+)*\))?\s*$")

    @classmethod
    def is_math_block(cls, text: str) -> bool:
        """Determines if a block of text is primarily a mathematical formula."""
        stripped = text.strip()
        if not stripped:
            return False

        # Check explicit math indicators
        matches = cls.MATH_INDICATOR_PATTERN.findall(stripped)
        if len(matches) >= 3 and len(stripped.split()) <= 15:
            return True

        # Check equation pattern like E = mc^2 or f(x) = ...
        if re.search(r"^[A-Za-z]\s*\([A-Za-z0-9,\s]+\)\s*=", stripped):
            return True
        if re.search(r"^[A-Za-z0-9_]+\s*=\s*[-+]?[0-9A-Za-z_]+", stripped) and any(c in stripped for c in "+-*/^"):
            return True

        return False

    @classmethod
    def convert_to_latex(cls, text: str) -> str:
        """
        Converts pseudo-math or OCR ASCII text into clean LaTeX syntax.
        """
        latex = text.strip()

        # 1. Standardize fractions: a/b -> \frac{a}{b} when bounded
        latex = re.sub(r"([A-Za-z0-9_\^]+)\s*\/\s*([A-Za-z0-9_\^]+)", r"\\frac{\1}{\2}", latex)

        # 2. Convert square roots: sqrt(x) -> \sqrt{x}
        latex = re.sub(r"sqrt\s*\((.*?)\)", r"\\sqrt{\1}", latex)

        # 3. Standardize Greek names
        for g_name, g_latex in cls.GREEK_SYMBOLS.items():
            latex = re.sub(rf"\b{g_name}\b", lambda m, rep=g_latex: rep, latex)

        # 4. Standardize operators
        for op_name, op_latex in cls.MATH_OPERATORS.items():
            if op_name.isalpha():
                latex = re.sub(rf"\b{op_name}\b", lambda m, rep=op_latex: rep, latex)
            else:
                latex = latex.replace(op_name, op_latex)

        # 5. Handle superscripts: x^2 -> x^{2}, x^n -> x^{n}
        latex = re.sub(r"\^([A-Za-z0-9]{2,})", r"^{\1}", latex)
        # 6. Handle subscripts: x_1 -> x_{1}, x_max -> x_{max}
        latex = re.sub(r"_([A-Za-z0-9]{2,})", r"_{\1}", latex)

        return latex

    @classmethod
    def process_block(cls, block: Block) -> Block:
        """
        Inspects block and classifies as BlockType.FORMULA if math is detected,
        formatting text as KaTeX math block $$...$$.
        """
        raw_text = block.text
        if cls.is_math_block(raw_text):
            latex_expr = cls.convert_to_latex(raw_text)
            block.block_type = BlockType.FORMULA
            # Replace line spans with formatted latex
            formatted_text = f"$$\n{latex_expr}\n$$"
            new_span = Span(text=formatted_text, bbox=block.bbox, confidence=0.95)
            new_line = Line(spans=[new_span], bbox=block.bbox)
            block.lines = [new_line]

        return block

    @classmethod
    def process_inline_math(cls, text: str) -> str:
        """
        Detects inline formulas like $a^2 + b^2 = c^2$ and wraps in single dollar signs.
        """
        # Look for patterns like x = y + z or alpha = 0.05 within text
        def _replace_inline(match):
            eq = match.group(0)
            return f"${cls.convert_to_latex(eq)}$"

        pattern = r"\b[a-zA-Z]\s*=\s*[a-zA-Z0-9_\+\-\*\/\^]+\b"
        return re.sub(pattern, _replace_inline, text)
