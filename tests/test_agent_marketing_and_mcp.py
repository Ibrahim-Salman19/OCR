"""tests/test_agent_marketing_and_mcp.py

Unit and integration tests for:
- Model Context Protocol (MCP) server
- Marketing, SEO, and Agent Skills
- llms.txt & llms-full.txt compliance
- robots.txt & sitemap.xml validation
"""

import json
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
import pytest

from blast_ocr.mcp_server import (
    MCP_TOOLS,
    handle_extract_formulas,
    handle_extract_tables,
    handle_process,
    handle_semantic_chunk,
    run_stdio_server,
)

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_mcp_tools_schema_validity():
    assert len(MCP_TOOLS) >= 4
    tool_names = [t["name"] for t in MCP_TOOLS]
    assert "blast_ocr_process" in tool_names
    assert "blast_ocr_extract_tables" in tool_names
    assert "blast_ocr_extract_formulas" in tool_names
    assert "blast_ocr_semantic_chunk" in tool_names

    for tool in MCP_TOOLS:
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool
        assert tool["inputSchema"]["type"] == "object"
        assert "properties" in tool["inputSchema"]


def test_mcp_extract_formulas():
    res = handle_extract_formulas(
        {"text": "The energy equation is E = mc^2 and force is F = ma."}
    )
    assert res["status"] == "success"
    assert "processed_text" in res


def test_mcp_file_not_found_handling():
    res = handle_process({"source_path": "/nonexistent/path/doc.pdf"})
    assert "error" in res
    assert "not found" in res["error"]

    res_tab = handle_extract_tables({"source_path": "/nonexistent/path/doc.pdf"})
    assert "error" in res_tab

    res_chunk = handle_semantic_chunk(
        {"source_path": "/nonexistent/path/doc.pdf"}
    )
    assert "error" in res_chunk


def test_mcp_stdio_execution():
    import io
    from unittest.mock import patch

    input_payload = (
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        + "\n"
        + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        + "\n"
        + json.dumps({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "blast_ocr_extract_formulas",
                "arguments": {"text": "y = mx + b"},
            },
        })
        + "\n"
    )
    fake_stdin = io.StringIO(input_payload)
    fake_stdout = io.StringIO()

    with patch("sys.stdin", fake_stdin), patch("sys.stdout", fake_stdout):
        run_stdio_server()

    output_lines = [
        json.loads(line) for line in fake_stdout.getvalue().strip().split("\n") if line.strip()
    ]
    assert len(output_lines) == 3
    assert output_lines[0]["id"] == 1
    assert output_lines[0]["result"]["serverInfo"]["name"] == "blast-ocr-mcp"
    assert output_lines[1]["id"] == 2
    assert len(output_lines[1]["result"]["tools"]) >= 4
    assert output_lines[2]["id"] == 3
    assert "result" in output_lines[2]


def test_llms_txt_and_full_compliance():
    llms_txt = ROOT_DIR / "llms.txt"
    assert llms_txt.exists()
    content = llms_txt.read_text(encoding="utf-8")
    assert content.startswith("# B.L.A.S.T. OCR Engine")
    assert "Enterprise-grade" in content
    assert "Benchmark Comparison Matrix" in content
    assert "Quickstart" in content

    llms_full = ROOT_DIR / "llms-full.txt"
    assert llms_full.exists()
    full_content = llms_full.read_text(encoding="utf-8")
    assert "Complete Technical Specification" in full_content
    assert "Quantitative Performance Benchmarks" in full_content
    assert "Model Context Protocol (MCP) Server" in full_content


def test_robots_txt_and_sitemap_xml():
    robots = ROOT_DIR / "robots.txt"
    assert robots.exists()
    r_text = robots.read_text(encoding="utf-8")
    assert "User-agent: GPTBot" in r_text
    assert "User-agent: ClaudeBot" in r_text
    assert "User-agent: PerplexityBot" in r_text
    assert "Sitemap: https://blast-ocr.dev/sitemap.xml" in r_text

    sitemap = ROOT_DIR / "sitemap.xml"
    assert sitemap.exists()
    tree = ET.parse(str(sitemap))
    root = tree.getroot()
    assert "urlset" in root.tag
    urls = [
        elem.text
        for elem in root.findall(
            ".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
        )
    ]
    assert "https://blast-ocr.dev/" in urls
    assert "https://blast-ocr.dev/llms.txt" in urls
    assert "https://blast-ocr.dev/llms-full.txt" in urls


def test_marketing_skills_registry():
    skills_lock = ROOT_DIR / "skills-lock.json"
    assert skills_lock.exists()
    lock_data = json.loads(skills_lock.read_text(encoding="utf-8"))
    assert "growth-marketing-seo-geo" in lock_data["skills"]
    assert "blast-ocr-agent" in lock_data["skills"]
    assert "agentic-rag-connector" in lock_data["skills"]

    # Verify skill files exist and have YAML frontmatter
    skill_paths = [
        ROOT_DIR / ".agents/skills/growth-marketing-seo-geo/SKILL.md",
        ROOT_DIR / "skills/growth_marketing_seo.md",
        ROOT_DIR / ".agents/skills/blast-ocr-agent/SKILL.md",
        ROOT_DIR / "skills/blast_ocr_agent.md",
        ROOT_DIR / ".agents/skills/agentic-rag-connector/SKILL.md",
        ROOT_DIR / "skills/agentic_rag_connector.md",
    ]
    for sp in skill_paths:
        assert sp.exists(), f"Missing skill file: {sp}"
        text = sp.read_text(encoding="utf-8")
        assert text.startswith("---"), f"Skill {sp} missing YAML frontmatter"
        assert "name:" in text
        assert "description:" in text
