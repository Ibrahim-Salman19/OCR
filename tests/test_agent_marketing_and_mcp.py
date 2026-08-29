"""tests/test_agent_marketing_and_mcp.py

Unit and integration tests for:
- Model Context Protocol (MCP) server
- Marketing, SEO, and Agent Skills
- llms.txt & llms-full.txt compliance
- robots.txt & sitemap.xml validation
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

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
    assert "self-hosted" in content.lower()
    assert "benchmark" in content.lower()
    assert "quickstart" in content.lower() or "core documentation" in content.lower()

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
    assert "User-agent: Claude-SearchBot" in r_text
    assert "User-agent: PerplexityBot" in r_text
    assert "User-agent: OAI-SearchBot" in r_text
    assert "User-agent: GoogleOther" in r_text
    assert (
        "Sitemap: https://raw.githubusercontent.com/Ibrahim-Salman19/OCR/main/sitemap.xml"
        in r_text
    )

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
    assert "https://github.com/Ibrahim-Salman19/OCR" in urls
    assert "https://ocr-book.streamlit.app/" in urls
    assert "https://raw.githubusercontent.com/Ibrahim-Salman19/OCR/main/llms.txt" in urls
    assert "https://raw.githubusercontent.com/Ibrahim-Salman19/OCR/main/llms-full.txt" in urls
    assert "https://raw.githubusercontent.com/Ibrahim-Salman19/OCR/main/mcp.json" in urls
    assert (
        "https://github.com/Ibrahim-Salman19/OCR/blob/main/docs/BENCHMARKS_2026.md"
        in urls
    )


def test_fastapi_agent_discovery_headers_and_endpoints():
    from fastapi.testclient import TestClient
    from blast_ocr.api.app import app

    client = TestClient(app)

    # Test root endpoint
    root_resp = client.get("/")
    assert root_resp.status_code == 200
    root_json = root_resp.json()
    assert root_json["name"] == "B.L.A.S.T. OCR Engine"
    assert "llms_roadmap" in root_json
    assert "mcp_manifest" in root_json
    assert "schema_jsonld" in root_json

    # Test discovery headers
    assert root_resp.headers["X-Agent-Discoverable"] == "true"
    assert "Link" in root_resp.headers
    assert "/llms.txt" in root_resp.headers["Link"]
    assert root_resp.headers["X-Robots-Tag"] == "all, index, follow"
    assert root_resp.headers["X-Model-Context-Protocol"] == "/mcp.json"

    # Test discovery endpoints
    mcp_resp = client.get("/mcp.json")
    assert mcp_resp.status_code == 200
    assert "mcpServers" in mcp_resp.json()

    well_known_mcp = client.get("/.well-known/mcp.json")
    assert well_known_mcp.status_code == 200
    assert "mcpServers" in well_known_mcp.json()

    plugin_resp = client.get("/.well-known/ai-plugin.json")
    assert plugin_resp.status_code == 200
    assert "name_for_model" in plugin_resp.json()

    schema_resp = client.get("/v1/schema.json")
    assert schema_resp.status_code == 200
    schema_data = schema_resp.json()
    assert schema_data["@context"] == "https://schema.org"
    assert "@graph" in schema_data
    types = [item["@type"] for item in schema_data["@graph"]]
    assert "SoftwareApplication" in types
    assert "SoftwareSourceCode" in types
    assert "TechArticle" in types
    assert "FAQPage" in types
    assert "HowTo" in types

    software_entry = next(
        item for item in schema_data["@graph"] if item["@type"] == "SoftwareApplication"
    )
    assert "aggregateRating" not in software_entry, (
        "aggregateRating must not be fabricated review markup -- "
        "see docs/GEO_AND_SEO_OPTIMIZATION.md section 2"
    )


def test_readme_schema_org_jsonld():
    readme_path = ROOT_DIR / "README.md"
    assert readme_path.exists()
    readme_text = readme_path.read_text(encoding="utf-8")
    assert "schema.org" in readme_text
    assert "SoftwareApplication" in readme_text
    assert "FAQPage" in readme_text

    # Extract JSON-LD from HTML comment
    start = readme_text.find("<!--\n{")
    end = readme_text.find("\n-->", start)
    assert start != -1 and end != -1
    json_str = readme_text[start + 5:end].strip()
    data = json.loads(json_str)
    assert data["@context"] == "https://schema.org"
    assert "@graph" in data

    software_entry = next(
        item for item in data["@graph"] if item["@type"] == "SoftwareApplication"
    )
    assert "aggregateRating" not in software_entry, (
        "aggregateRating must not be fabricated review markup -- "
        "see docs/GEO_AND_SEO_OPTIMIZATION.md section 2"
    )


def test_streamlit_ui_seo_tags():
    ui_path = ROOT_DIR / "blast_ocr/ui/web_app.py"
    assert ui_path.exists()
    ui_text = ui_path.read_text(encoding="utf-8")
    assert "_SEO_META_TAGS" in ui_text
    assert "B.L.A.S.T. OCR Engine" in ui_text
    assert "schema.org" in ui_text
    assert 'rel="describedby"' in ui_text


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

