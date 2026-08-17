"""Scoring primitives for the B.L.A.S.T. eval harness.

Three independent signals, deliberately kept separate rather than blended
into one score:

- CER / WER (jiwer): character/word-level fidelity of the recognized text.
- reading-order tau: whether recognized tokens come out in the same
  relative order as the gold tokens, independent of recognition errors.
  CER cannot see this at all -- a page with perfect per-word accuracy but
  scrambled order scores near-0 CER and is still unusable.
- fact checks (olmOCR-Bench style): machine-checkable pass/fail assertions
  that catch failures edit-distance rewards, such as hallucinated content
  on a blank page (low CER contribution, but wrong) or two paragraphs
  swapped wholesale (small edit distance, but wrong document).
"""

import difflib
import re
from dataclasses import dataclass
from typing import List, Optional

import jiwer
from scipy.stats import kendalltau

from eval.gold_loader import normalize_whitespace, tokenize

# jiwer's default transforms (Strip -> reduce-to-chars for CER;
# RemoveMultipleSpaces -> Strip -> reduce-to-words for WER) already do
# exactly the whitespace handling we want, and jiwer requires the final
# reduce-to-list-of-* step to be present in whatever transform is passed.
# We additionally normalize_whitespace() ourselves before handing strings
# to jiwer so callers see the same normalized text jiwer scores against.


def compute_cer(gold_text: str, hyp_text: str) -> float:
    """Character error rate. Case- and punctuation-sensitive by design:
    those ARE real OCR errors, not noise to normalize away."""
    gold_text = normalize_whitespace(gold_text)
    hyp_text = normalize_whitespace(hyp_text)
    if not gold_text:
        return 0.0 if not hyp_text else 1.0
    return jiwer.cer(gold_text, hyp_text)


def compute_wer(gold_text: str, hyp_text: str) -> float:
    gold_text = normalize_whitespace(gold_text)
    hyp_text = normalize_whitespace(hyp_text)
    if not gold_text:
        return 0.0 if not hyp_text else 1.0
    return jiwer.wer(gold_text, hyp_text)


def reading_order_tau(
    gold_tokens: List[str], hyp_text: str, chunk_size: int = 12
) -> Optional[float]:
    """Kendall's tau over the positions of matched gold *chunks* in the
    hypothesis.

    A naive approach -- align individual gold and hypothesis tokens via
    difflib (LCS-style) and correlate their positions -- does not work:
    a longest-common-subsequence alignment is *monotonic by construction*
    (that's what makes it a subsequence), so matched-token positions
    increase together even when the hypothesis is fully scrambled, as long
    as enough common words (e.g. "the", "and") exist to string a
    monotonic alignment together. Verified empirically: a word-by-word
    interleaving of two independent sentences still scored tau ~= 1.0
    under that approach.

    Instead we chunk the gold tokens into runs of `chunk_size` words and,
    for each chunk, look for the longest *contiguous* matching run of
    that chunk anywhere in the hypothesis token stream. A chunk only
    contributes a position if most of it (at least half, floor 3 tokens)
    matches contiguously -- individual OCR substitution errors inside a
    chunk don't break this, but genuine reordering (e.g. two columns
    interleaved line-by-line, or two facing pages merged row-by-row) does,
    because no long contiguous run of the original chunk survives
    interleaving. tau is then the rank correlation between chunk index
    (gold order) and matched position (hypothesis order): 1.0 = correct
    order, ~0 = scrambled, -1.0 = fully reversed.

    Returns None when fewer than 2 chunks get a confident match (not
    enough signal to compute a correlation).
    """
    hyp_tokens = tokenize(hyp_text)
    if len(gold_tokens) < 2 or not hyp_tokens:
        return None

    chunks = [
        gold_tokens[i : i + chunk_size] for i in range(0, len(gold_tokens), chunk_size)
    ]
    if len(chunks) > 1 and len(chunks[-1]) < max(2, chunk_size // 2):
        chunks = chunks[:-1]  # trailing remainder too short to match reliably

    sm = difflib.SequenceMatcher(None, autojunk=False)
    sm.set_seq1(hyp_tokens)

    gold_order: List[int] = []
    hyp_positions: List[int] = []
    for i, chunk in enumerate(chunks):
        sm.set_seq2(chunk)
        match = sm.find_longest_match(0, len(hyp_tokens), 0, len(chunk))
        required = max(3, len(chunk) // 2)
        if match.size >= required:
            gold_order.append(i)
            hyp_positions.append(match.a)

    if len(gold_order) < 2:
        return None

    tau, _p_value = kendalltau(gold_order, hyp_positions)
    if tau != tau:  # NaN guard (constant input -- e.g. only 2 chunks, both at rank 0)
        return None
    return float(tau)


def _normalize_for_search(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@dataclass
class FactCheckResult:
    check_type: str
    description: str
    passed: bool
    detail: str = ""


def run_fact_checks(checks: List[dict], hyp_text: str) -> List[FactCheckResult]:
    """Evaluate a list of fact-check dicts (as loaded from *.facts.yaml)
    against the pipeline's hypothesis text for one page. Matching is
    case-insensitive and whitespace-normalized -- these checks test
    presence/order/absence of content, not exact formatting."""
    norm_hyp = _normalize_for_search(hyp_text)
    results: List[FactCheckResult] = []

    for check in checks:
        ctype = check["type"]

        if ctype == "contains":
            needle = _normalize_for_search(check["text"])
            passed = needle in norm_hyp
            results.append(
                FactCheckResult(
                    ctype,
                    f'contains "{check["text"]}"',
                    passed,
                    "" if passed else "not found in output",
                )
            )

        elif ctype == "absent":
            needle = _normalize_for_search(check["text"])
            max_occ = check.get("max_occurrences", 0)
            count = norm_hyp.count(needle) if needle else 0
            passed = count <= max_occ
            results.append(
                FactCheckResult(
                    ctype,
                    f'absent "{check["text"]}" (max {max_occ})',
                    passed,
                    f"found {count} occurrences" if not passed else "",
                )
            )

        elif ctype == "ordered_before":
            first = _normalize_for_search(check["first"])
            second = _normalize_for_search(check["second"])
            idx_first = norm_hyp.find(first)
            idx_second = norm_hyp.find(second)
            if idx_first == -1 or idx_second == -1:
                missing = []
                if idx_first == -1:
                    missing.append(f'"{check["first"]}"')
                if idx_second == -1:
                    missing.append(f'"{check["second"]}"')
                results.append(
                    FactCheckResult(
                        ctype,
                        f'"{check["first"]}" ordered_before "{check["second"]}"',
                        False,
                        f"not found: {', '.join(missing)}",
                    )
                )
            else:
                passed = idx_first < idx_second
                results.append(
                    FactCheckResult(
                        ctype,
                        f'"{check["first"]}" ordered_before "{check["second"]}"',
                        passed,
                        "" if passed else "found in reverse order",
                    )
                )

        elif ctype == "table_cell":
            # Validates presence of row/cell content in extracted table text
            row_text = check.get("row_text", "")
            cell_text = check.get("cell_text", "")
            passed = (cell_text.lower() in norm_hyp) and (not row_text or row_text.lower() in norm_hyp)
            results.append(
                FactCheckResult(
                    ctype,
                    f'Cell "{cell_text}" in table',
                    passed,
                    "" if passed else f'cell "{cell_text}" missing in extracted table',
                )
            )

        else:
            raise ValueError(f"Unknown fact check type: {ctype!r}")

    return results


def compute_teds(gold_html: str, hyp_html: str, structure_only: bool = False) -> float:
    """Tree Edit Distance-based Similarity for Table Extraction."""
    from eval.teds_evaluator import TEDSEvaluator
    return TEDSEvaluator.evaluate(gold_html, hyp_html, structure_only=structure_only)
