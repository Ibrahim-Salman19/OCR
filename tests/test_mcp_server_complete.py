"""
tests/test_mcp_server_complete.py

Unit test suite for Model Context Protocol (MCP) server.
Validates sandbox security, tool dispatch, JSON-RPC stdio protocol,
table/formula/chunking tool execution, and error serialization.
"""

import io
import json
import sys
from unittest.mock import patch, MagicMock
from PIL import Image

from blast_ocr.mcp_server import (
    _is_safe_mcp_path,
    get_pipeline,
    handle_process,
    handle_extract_tables,
    handle_extract_formulas,
    handle_semantic_chunk,
    run_stdio_server,
)


def test_is_safe_mcp_path(tmp_path):
    safe = str(tmp_path / "doc.pdf")
    assert _is_safe_mcp_path(safe) is True

    # Traversal / restricted roots
    assert _is_safe_mcp_path("/etc/passwd") is False
    assert _is_safe_mcp_path("/root/secret.key") is False


def test_get_pipeline():
    with patch("blast_ocr.pipeline.BlastPipeline") as mock_pipeline_cls:
        p = get_pipeline(engine="tesseract", secure_mode=True)
        assert p is not None
        mock_pipeline_cls.assert_called_once_with(
            config_overrides={"ocr_engine": "tesseract", "secure_mode": True}
        )


def test_handle_process_errors(tmp_path):
    # Missing path
    res1 = handle_process({})
    assert "error" in res1

    # Unsafe path
    with patch("blast_ocr.mcp_server._is_safe_mcp_path", return_value=False):
        with patch("os.path.exists", return_value=True):
            res2 = handle_process({"source_path": "/etc/shadow"})
            assert "Access denied" in res2["error"]


def test_handle_process_success(tmp_path):
    test_file = tmp_path / "sample.png"
    Image.new("RGB", (100, 100), color="white").save(str(test_file))

    mock_pipeline = MagicMock()
    mock_pipeline.process_job.return_value = {
        "status": "success",
        "source_file": "sample.png",
        "text": "Extracted text content for test " * 20,
        "generated_files": {"markdown": "/path/sample.md"},
        "metadata": {"page_count": 1},
    }

    with patch("blast_ocr.mcp_server.get_pipeline", return_value=mock_pipeline):
        res = handle_process({"source_path": str(test_file)})
        assert res["status"] == "success"
        assert "Extracted text" in res["text_snippet"]
        assert res["generated_files"]["markdown"] == "/path/sample.md"


def test_handle_extract_tables(tmp_path):
    # Error: nonexistent
    res_err = handle_extract_tables({"source_path": "missing.png"})
    assert "error" in res_err

    # Valid image
    img_file = tmp_path / "table.png"
    Image.new("RGB", (100, 100), color="white").save(str(img_file))

    mock_table = MagicMock()
    mock_table.to_markdown.return_value = "| A | B |\n|---|---|\n| 1 | 2 |"
    mock_table.to_html.return_value = "<table><tr><td>A</td></tr></table>"

    with patch("blast_ocr.core.table_extractor.TableExtractor") as mock_ext_cls:
        mock_ext = MagicMock()
        mock_ext.extract_tables.return_value = [mock_table]
        mock_ext_cls.return_value = mock_ext

        res = handle_extract_tables({"source_path": str(img_file)})
        assert res["status"] == "success"
        assert res["table_count"] == 1
        assert "| A | B |" in res["tables_markdown"][0]


def test_handle_extract_formulas():
    res = handle_extract_formulas({"text": "The energy is $E = mc^2$ in physics."})
    assert res["status"] == "success"
    assert "E = mc^2" in res["processed_text"]


def test_handle_semantic_chunk(tmp_path):
    res_err = handle_semantic_chunk({"source_path": "missing.txt"})
    assert "error" in res_err

    txt_file = tmp_path / "doc.txt"
    txt_file.write_text("Chapter 1. This is an introductory paragraph.")

    mock_chunk = MagicMock()
    mock_chunk.to_dict.return_value = {"text": "Chapter 1", "index": 0}

    mock_pipeline = MagicMock()
    mock_pipeline.process_job.return_value = {"text": "Chapter 1. This is introductory."}

    with patch("blast_ocr.mcp_server.get_pipeline", return_value=mock_pipeline):
        with patch("blast_ocr.core.semantic_chunker.SemanticChunker.chunk_text", return_value=[mock_chunk]):
            res = handle_semantic_chunk({"source_path": str(txt_file)})
            assert res["status"] == "success"
            assert res["chunk_count"] == 1


def test_run_stdio_server_flow():
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "blast_ocr_extract_formulas",
                "arguments": {"text": "$x + y = z$"},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "unknown_tool",
                "arguments": {},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 5, "method": "other_method"},
    ]

    input_data = "\n".join(json.dumps(r) for r in requests) + "\n\n"
    stdin_mock = io.StringIO(input_data)
    stdout_mock = io.StringIO()

    with patch.object(sys, "stdin", stdin_mock):
        with patch.object(sys, "stdout", stdout_mock):
            run_stdio_server()

    output_lines = [line for line in stdout_mock.getvalue().split("\n") if line.strip()]
    assert len(output_lines) == 5  # 5 requests with id (notification skipped)

    r1 = json.loads(output_lines[0])
    assert r1["id"] == 1
    assert r1["result"]["serverInfo"]["name"] == "blast-ocr-mcp"

    r2 = json.loads(output_lines[1])
    assert r2["id"] == 2
    assert "tools" in r2["result"]

    r3 = json.loads(output_lines[2])
    assert r3["id"] == 3
    assert "content" in r3["result"]

    r4 = json.loads(output_lines[3])
    assert r4["id"] == 4
    assert "Unknown tool" in r4["result"]["content"][0]["text"]
