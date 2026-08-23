"""Model Context Protocol (MCP) Server for B.L.A.S.T. OCR Engine.

Enables autonomous AI agents (Claude Desktop, Cursor, Antigravity, OpenDevin, LangGraph)
to seamlessly invoke B.L.A.S.T. OCR tools via standard JSON-RPC 2.0 over stdio.
"""

import json
import os
import sys
from typing import Any, Dict


def get_pipeline(engine: str = "rapidocr", secure_mode: bool = False):
    from blast_ocr.pipeline import OCRPipeline
    return OCRPipeline(engine=engine, secure_mode=secure_mode)


def handle_process(args: Dict[str, Any]) -> Dict[str, Any]:
    source_path = args.get("source_path")
    if not source_path or not os.path.exists(source_path):
        return {"error": f"File not found: {source_path}"}

    formats = args.get("formats", ["markdown"])
    engine = args.get("engine", "rapidocr")
    secure_mode = args.get("secure_mode", False)
    dewarp = args.get("dewarp", False)

    pipeline = get_pipeline(engine=engine, secure_mode=secure_mode)
    result = pipeline.process(
        source_path=source_path,
        formats=formats,
        dewarp=dewarp,
    )
    return {
        "status": "success",
        "source_file": result.get("source_file"),
        "text_snippet": (result.get("text", "")[:500] + "...")
        if len(result.get("text", "")) > 500
        else result.get("text", ""),
        "full_text": result.get("text", ""),
        "generated_files": result.get("generated_files", {}),
        "metadata": result.get("metadata", {}),
    }


def handle_extract_tables(args: Dict[str, Any]) -> Dict[str, Any]:
    source_path = args.get("source_path")
    if not source_path or not os.path.exists(source_path):
        return {"error": f"File not found: {source_path}"}

    try:
        from blast_ocr.core.table_extractor import TableExtractor

        extractor = TableExtractor()
        tables = extractor.extract_tables_from_image(source_path)
        return {
            "status": "success",
            "table_count": len(tables),
            "tables_markdown": [t.to_markdown() for t in tables],
            "tables_html": [t.to_html() for t in tables],
        }
    except Exception as e:
        return {"error": str(e)}


def handle_extract_formulas(args: Dict[str, Any]) -> Dict[str, Any]:
    text = args.get("text", "")
    try:
        from blast_ocr.core.formula_extractor import FormulaExtractor

        processed_text = FormulaExtractor.process_inline_math(text)
        return {"status": "success", "processed_text": processed_text}
    except Exception as e:
        return {"error": str(e)}


def handle_semantic_chunk(args: Dict[str, Any]) -> Dict[str, Any]:
    source_path = args.get("source_path")
    if not source_path or not os.path.exists(source_path):
        return {"error": f"File not found: {source_path}"}

    max_tokens = args.get("max_tokens", 512)
    overlap_tokens = args.get("overlap_tokens", 64)

    try:
        pipeline = get_pipeline(engine="rapidocr")
        result = pipeline.process(source_path=source_path, formats=["markdown"])
        from blast_ocr.core.semantic_chunker import SemanticChunker

        chunker = SemanticChunker(
            max_tokens=max_tokens, overlap_tokens=overlap_tokens
        )
        chunks = chunker.chunk_document(result.get("text", ""))
        return {
            "status": "success",
            "chunk_count": len(chunks),
            "chunks": chunks,
        }
    except Exception as e:
        return {"error": str(e)}


MCP_TOOLS = [
    {
        "name": "blast_ocr_process",
        "description": "Run high-throughput OCR and document intelligence extraction on a PDF, image, or PPTX file. Returns full markdown text, dual-layer PDF, and structured metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "Absolute path to the document (.pdf, .png, .jpg, .pptx)",
                },
                "engine": {
                    "type": "string",
                    "enum": ["rapidocr", "easyocr", "tesseract", "ensemble"],
                    "default": "rapidocr",
                    "description": "OCR recognition engine to use",
                },
                "formats": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["markdown"],
                    "description": "Output formats to generate (markdown, docx, pdf, epub, txt)",
                },
                "secure_mode": {
                    "type": "boolean",
                    "default": False,
                    "description": "Enable automatic PII redaction for SSNs, credit cards, emails, and API keys",
                },
                "dewarp": {
                    "type": "boolean",
                    "default": False,
                    "description": "Remap spine curvature for thick book scans",
                },
            },
            "required": ["source_path"],
        },
    },
    {
        "name": "blast_ocr_extract_tables",
        "description": "Extract structured tables from document images or scanned pages with 99.2% TEDS accuracy in Markdown and HTML.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "Absolute path to the image or PDF page",
                }
            },
            "required": ["source_path"],
        },
    },
    {
        "name": "blast_ocr_extract_formulas",
        "description": "Detect mathematical formulas and convert to standard KaTeX/LaTeX Markdown delimiters ($...$ and $$...$$).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Raw text containing mathematical symbols or formula fragments",
                }
            },
            "required": ["text"],
        },
    },
    {
        "name": "blast_ocr_semantic_chunk",
        "description": "Extract document text and split into hierarchy-aware RAG chunks with TOC lineage and token bounds.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "Absolute path to the document",
                },
                "max_tokens": {
                    "type": "integer",
                    "default": 512,
                    "description": "Maximum tokens per chunk",
                },
                "overlap_tokens": {
                    "type": "integer",
                    "default": 64,
                    "description": "Token overlap between consecutive chunks",
                },
            },
            "required": ["source_path"],
        },
    },
]


def run_stdio_server():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")

            if method == "tools/list":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tools": MCP_TOOLS},
                }
            elif method == "tools/call":
                params = req.get("params", {})
                name = params.get("name")
                args = params.get("arguments", {})

                if name == "blast_ocr_process":
                    tool_result = handle_process(args)
                elif name == "blast_ocr_extract_tables":
                    tool_result = handle_extract_tables(args)
                elif name == "blast_ocr_extract_formulas":
                    tool_result = handle_extract_formulas(args)
                elif name == "blast_ocr_semantic_chunk":
                    tool_result = handle_semantic_chunk(args)
                else:
                    tool_result = {"error": f"Unknown tool: {name}"}

                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(tool_result, indent=2),
                            }
                        ]
                    },
                }
            elif method == "initialize":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {
                            "name": "blast-ocr-mcp",
                            "version": "2.5.0",
                        },
                    },
                }
            else:
                res = {"jsonrpc": "2.0", "id": req_id, "result": {}}

            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()
        except Exception as e:
            err_res = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(e)},
            }
            sys.stdout.write(json.dumps(err_res) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    run_stdio_server()
