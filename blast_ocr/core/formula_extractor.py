"""
blast_ocr.core.formula_extractor

Mathematical Formula & Equation Recognition for B.L.A.S.T. OCR Protocol.
Detects inline and display mathematical formulas, subscripts, superscripts,
Greek symbols, and converts them to standardized KaTeX / LaTeX Markdown blocks.
"""

import re
from dataclasses import dataclass

from blast_ocr.core.document_model import Block, BlockType, Span, Line


class _UnbalancedMathExpressionError(Exception):
    """Raised internally when OCR'd math text has unmatched delimiters
    (e.g. a dropped closing paren from a misread glyph). Never escapes
    FormulaExtractor -- callers get the original text back unchanged
    instead of a best-effort LaTeX string with unbalanced braces."""


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
        # "sqrt" is deliberately absent: it's handled exclusively by the
        # balanced-paren sqrt(...) -> \sqrt{...} scanner below. Leaving it
        # here would double-process it, since \bsqrt\b still matches the
        # "sqrt" substring inside an already-converted "\sqrt{" (a leading
        # backslash is a non-word character, so the word boundary doesn't
        # care that it's there), producing "\\sqrt{" instead of "\sqrt{".
        "sum": "\\sum", "int": "\\int", "prod": "\\prod",
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

    _SQRT_OPEN_PATTERN = re.compile(r"\bsqrt\s*\(")

    @classmethod
    def _convert_sqrt_balanced(cls, text: str) -> str:
        """
        Converts sqrt(...) -> \\sqrt{...} using explicit paren-depth tracking
        instead of a non-greedy regex, so nested parentheses inside the
        argument (e.g. "sqrt((a+b)/(c+d))") are matched to their true closing
        paren rather than the first ")" encountered. Nested sqrt(...) calls
        are converted recursively. Raises _UnbalancedMathExpressionError if a
        "sqrt(" is never closed, rather than emitting a truncated argument.
        """
        result = []
        i = 0
        n = len(text)
        while i < n:
            match = cls._SQRT_OPEN_PATTERN.match(text, i)
            if match:
                paren_idx = match.end() - 1
                depth = 1
                j = paren_idx + 1
                while j < n and depth > 0:
                    if text[j] == "(":
                        depth += 1
                    elif text[j] == ")":
                        depth -= 1
                    j += 1
                if depth != 0:
                    raise _UnbalancedMathExpressionError(
                        f"Unclosed sqrt( starting at offset {i}"
                    )
                inner = text[paren_idx + 1 : j - 1]
                result.append("\\sqrt{" + cls._convert_sqrt_balanced(inner) + "}")
                i = j
            else:
                result.append(text[i])
                i += 1
        return "".join(result)

    @staticmethod
    def _braces_balanced(text: str) -> bool:
        depth = 0
        for ch in text:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth < 0:
                    return False
        return depth == 0

    @classmethod
    def convert_to_latex(cls, text: str) -> str:
        """
        Converts pseudo-math or OCR ASCII text into clean LaTeX syntax.

        On any input whose delimiters can't be resolved (a dropped closing
        paren, or a brace-balance mismatch that would otherwise surface as
        broken LaTeX downstream), returns the original text unchanged rather
        than a best-effort but structurally invalid conversion -- honest raw
        text beats confidently wrong markup for OCR'd math.
        """
        stripped = text.strip()

        try:
            # 1. Convert square roots first (balanced-paren scan), so a
            # fraction living inside sqrt(...) -- e.g. "sqrt(a/b)" -- is
            # still visible to the fraction pass below once it's wrapped in
            # \sqrt{...}, instead of the naive regex ever seeing raw parens.
            latex = cls._convert_sqrt_balanced(stripped)
        except _UnbalancedMathExpressionError:
            return stripped
        except RecursionError:
            # Pathologically deep nested sqrt(sqrt(sqrt(...))) -- e.g. from
            # garbled OCR of a repeated glyph -- recurses one Python frame
            # per nesting level in _convert_sqrt_balanced. Past ~1000 levels
            # that exceeds the interpreter's recursion limit; treat it the
            # same as an unbalanced expression rather than crashing the page.
            return stripped

        # 2. Standardize fractions: a/b -> \frac{a}{b} when bounded
        latex = re.sub(r"([A-Za-z0-9_\^]+)\s*\/\s*([A-Za-z0-9_\^]+)", r"\\frac{\1}{\2}", latex)

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

        if not cls._braces_balanced(latex):
            return stripped

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
