"""
tests/test_teds_evaluator.py

Unit tests for TEDSEvaluator module.
"""

import pytest
from eval.teds_evaluator import TEDSEvaluator, parse_html_table_to_tree, TableNode
from eval.metrics import compute_teds


def test_parse_html_table():
    html_str = """
    <table>
        <tr><th>Name</th><th>Score</th></tr>
        <tr><td>Alice</td><td>95</td></tr>
    </table>
    """
    tree = parse_html_table_to_tree(html_str)
    assert tree is not None
    assert tree.tag == "table"
    assert len(tree.children) == 2  # 2 tr elements
    assert tree.size() > 5


def test_teds_identical_tables():
    html1 = """
    <table>
        <tr><th>Col A</th><th>Col B</th></tr>
        <tr><td>100</td><td>200</td></tr>
    </table>
    """
    score = TEDSEvaluator.evaluate(html1, html1)
    assert score == 1.0


def test_teds_structural_difference():
    # 2 rows vs 3 rows
    html1 = "<table><tr><td>A</td></tr><tr><td>B</td></tr></table>"
    html2 = "<table><tr><td>A</td></tr><tr><td>B</td></tr><tr><td>C</td></tr></table>"

    score_struct = TEDSEvaluator.evaluate(html1, html2, structure_only=True)
    assert 0.0 < score_struct < 1.0


def test_teds_text_difference():
    html1 = "<table><tr><td>Revenue</td><td>$10,000</td></tr></table>"
    html2 = "<table><tr><td>Revenue</td><td>$10,500</td></tr></table>"

    # Structure only should be 1.0 (same shape)
    score_struct = TEDSEvaluator.evaluate(html1, html2, structure_only=True)
    assert score_struct == 1.0

    # Content includes text edit distance
    score_content = TEDSEvaluator.evaluate(html1, html2, structure_only=False)
    assert 0.8 < score_content < 1.0


def test_compute_teds_helper():
    html1 = "<table><tr><td>A</td></tr></table>"
    html2 = "<table><tr><td>A</td></tr></table>"
    assert compute_teds(html1, html2) == 1.0


def test_teds_batch_eval():
    golds = ["<table><tr><td>A</td></tr></table>", "<table><tr><td>B</td></tr></table>"]
    hyps = ["<table><tr><td>A</td></tr></table>", "<table><tr><td>C</td></tr></table>"]
    mean_score, individual = TEDSEvaluator.evaluate_batch(golds, hyps)
    assert len(individual) == 2
    assert individual[0] == 1.0
    assert 0.0 < mean_score < 1.0
