"""
eval/teds_evaluator.py

Tree Edit Distance-based Similarity (TEDS) metric for Table Extraction & Structure Recognition.
Implements PubTabNet / ICDAR standard evaluation for:
- TEDS-Struct: Measures structural grid fidelity (rows, columns, cell spanning).
- TEDS-Content: Measures joint structural and textual accuracy.
"""

from typing import Dict, List, Optional, Union, Tuple
import re
import html
import xml.etree.ElementTree as ET


class TableNode:
    """Represents a node in the HTML table tree."""
    def __init__(self, tag: str, text: str = "", attributes: Optional[Dict[str, str]] = None):
        self.tag = tag.lower()
        self.text = text.strip()
        self.attributes = attributes or {}
        self.children: List['TableNode'] = []

    def add_child(self, child: 'TableNode'):
        self.children.append(child)

    def size(self) -> int:
        return 1 + sum(child.size() for child in self.children)

    def __repr__(self):
        return f"<{self.tag} text={self.text!r} attrs={self.attributes} children={len(self.children)}>"


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Standard Levenshtein string distance."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def _normalized_text_similarity(s1: str, s2: str) -> float:
    """Returns normalized similarity between 0.0 and 1.0."""
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    dist = _levenshtein_distance(s1, s2)
    return 1.0 - (dist / max_len)


def parse_html_table_to_tree(html_content: str) -> Optional[TableNode]:
    """Parses HTML table string into a TableNode tree."""
    if not html_content or "<table" not in html_content.lower():
        return None

    # Clean HTML snippet to well-formed XML
    clean = re.sub(r"<!--.*?-->", "", html_content, flags=re.DOTALL)
    # Extract table portion
    m = re.search(r"(<table.*?>.*?</table>)", clean, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    table_html = m.group(1)

    # Basic self-closing fix
    try:
        root_elem = ET.fromstring(table_html)
    except ET.ParseError:
        # Wrap or clean unclosed tags
        try:
            wrapped = f"<html>{table_html}</html>"
            root_elem = ET.fromstring(wrapped).find(".//table")
            if root_elem is None:
                return None
        except Exception:
            return None

    def _convert_elem(elem: ET.Element) -> TableNode:
        text = elem.text or ""
        attrs = {k.lower(): v for k, v in elem.attrib.items() if k.lower() in ("colspan", "rowspan")}
        node = TableNode(tag=elem.tag, text=text, attributes=attrs)
        for child in elem:
            node.add_child(_convert_elem(child))
            if child.tail and child.tail.strip():
                node.text += " " + child.tail.strip()
        return node

    return _convert_elem(root_elem)


def _tree_edit_distance(node1: Optional[TableNode], node2: Optional[TableNode], structure_only: bool = False) -> float:
    """
    Computes recursive tree edit distance between two TableNode hierarchies.
    """
    if node1 is None and node2 is None:
        return 0.0
    if node1 is None:
        return float(node2.size())
    if node2 is None:
        return float(node1.size())

    # Node matching cost
    tag_match = (node1.tag == node2.tag)
    attrs_match = (node1.attributes == node2.attributes)

    if not tag_match:
        node_cost = 1.0
    elif not attrs_match:
        node_cost = 0.5
    elif not structure_only:
        # Include text distance
        sim = _normalized_text_similarity(node1.text, node2.text)
        node_cost = 1.0 - sim
    else:
        node_cost = 0.0

    # Match children via sequence alignment DP
    children1 = node1.children
    children2 = node2.children
    m, n = len(children1), len(children2)

    dp = [[0.0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        dp[i][0] = dp[i - 1][0] + children1[i - 1].size()
    for j in range(1, n + 1):
        dp[0][j] = dp[0][j - 1] + children2[j - 1].size()

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost_match = _tree_edit_distance(children1[i - 1], children2[j - 1], structure_only=structure_only)
            cost_del = children1[i - 1].size()
            cost_ins = children2[j - 1].size()
            dp[i][j] = min(
                dp[i - 1][j - 1] + cost_match,
                dp[i - 1][j] + cost_del,
                dp[i][j - 1] + cost_ins,
            )

    return node_cost + dp[m][n]


class TEDSEvaluator:
    """Evaluates Table Extraction using Tree Edit Distance-based Similarity."""

    @staticmethod
    def evaluate(
        gold_html: str,
        hyp_html: str,
        structure_only: bool = False,
    ) -> float:
        """
        Computes TEDS score in range [0.0, 1.0].
        1.0 = Perfect match, 0.0 = Complete mismatch.
        """
        tree_gold = parse_html_table_to_tree(gold_html)
        tree_hyp = parse_html_table_to_tree(hyp_html)

        if tree_gold is None and tree_hyp is None:
            return 1.0
        if tree_gold is None or tree_hyp is None:
            return 0.0

        size_gold = tree_gold.size()
        size_hyp = tree_hyp.size()
        max_size = max(size_gold, size_hyp)

        if max_size == 0:
            return 1.0

        dist = _tree_edit_distance(tree_gold, tree_hyp, structure_only=structure_only)
        score = 1.0 - (dist / max_size)
        return max(0.0, min(1.0, score))

    @classmethod
    def evaluate_batch(
        cls,
        gold_tables: List[str],
        hyp_tables: List[str],
        structure_only: bool = False,
    ) -> Tuple[float, List[float]]:
        """Evaluates a batch of table pairs and returns (mean_score, list_of_scores)."""
        if not gold_tables:
            return 1.0, []

        scores = []
        for g, h in zip(gold_tables, hyp_tables):
            s = cls.evaluate(g, h, structure_only=structure_only)
            scores.append(s)

        mean_score = sum(scores) / len(scores) if scores else 0.0
        return mean_score, scores
