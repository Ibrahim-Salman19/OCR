"""Model Context Protocol (MCP) Server for B.L.A.S.T. OCR Engine.

Enables autonomous AI agents (Claude Desktop, Cursor, Antigravity, OpenDevin, LangGraph)
to seamlessly invoke B.L.A.S.T. OCR tools via standard JSON-RPC 2.0 over stdio.
"""

import json
import os
import sys
from typing import Any, Dict


def _is_safe_mcp_path(target_path: str) -> bool:
    """Sandbox verification for MCP file access."""
    try:
        from blast_ocr.api.routes import _is_safe_path
        return _is_safe_path(target_path)
    except Exception:
        # Fallback to basic traversal check
        resolved = os.path.abspath(os.path.realpath(target_path))
        forbidden = ("/etc", "/root", "/boot", "/sys", "/proc", "/dev", "/usr", "/home", "/var")
        return not any(resolved == f or resolved.startswith(f + os.sep) for f in forbidden)


def get_pipeline(engine: str = "rapidocr", secure_mode: bool = False):
    from blast_ocr.pipeline import BlastPipeline
    config_overrides = {"ocr_engine": engine, "secure_mode": secure_mode}
    return BlastPipeline(config_overrides=config_overrides)


def handle_process(args: Dict[str, Any]) -> Dict[str, Any]:
    source_path = args.get("source_path")
    if not source_path or not os.path.exists(source_path):
        return {"error": f"File not found: {source_path}"}
    if not _is_safe_mcp_path(source_path):
        return {"error": f"Access denied: path '{source_path}' is outside allowed directories."}

    formats = args.get("formats", ["markdown"])
    engine = args.get("engine", "rapidocr")
    secure_mode = args.get("secure_mode", False)
    dewarp = args.get("dewarp", False)

    pipeline = get_pipeline(engine=engine, secure_mode=secure_mode)
    try:
        result = pipeline.process_job(
            source=source_path,
            formats=formats,
            enable_dewarp=dewarp,
        )
        return {
            "status": "success",
            "source_file": result.get("source_file", os.path.basename(source_path)),
            "text_snippet": (result.get("text", "")[:500] + "...")
            if len(result.get("text", "")) > 500
            else result.get("text", ""),
            "full_text": result.get("text", ""),
            "generated_files": result.get("generated_files", {}),
            "metadata": result.get("metadata", {}),
        }
    except Exception as e:
        return {"error": f"Processing failed: {e}"}
    finally:
        pipeline.close()


def handle_extract_tables(args: Dict[str, Any]) -> Dict[str, Any]:
    source_path = args.get("source_path")
    if not source_path or not os.path.exists(source_path):
        return {"error": f"File not found: {source_path}"}
    if not _is_safe_mcp_path(source_path):
        return {"error": f"Access denied: path '{source_path}' is outside allowed directories."}

    try:
        import cv2
        from blast_ocr.core.table_extractor import TableExtractor

        img = cv2.imread(source_path)
        if img is None:
            return {"error": f"Could not decode image from '{source_path}'"}

        extractor = TableExtractor()
        tables = extractor.extract_tables(img, spans=[])
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
    if not _is_safe_mcp_path(source_path):
        return {"error": f"Access denied: path '{source_path}' is outside allowed directories."}

    max_tokens = args.get("max_tokens", 512)
    overlap_tokens = args.get("overlap_tokens", 64)

    pipeline = get_pipeline(engine="rapidocr")
    try:
        result = pipeline.process_job(source=source_path, formats=["markdown"])
        from blast_ocr.core.semantic_chunker import SemanticChunker

        chunks = SemanticChunker.chunk_text(
            text=result.get("text", ""),
            title=os.path.basename(source_path),
            max_chunk_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
        )
        return {
            "status": "success",
            "chunk_count": len(chunks),
            "chunks": [c.to_dict() for c in chunks],
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        pipeline.close()


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

            # Handle notifications (requests without id): execute without returning a response
            is_notification = req_id is None

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
            elif method in ("notifications/initialized", "notifications/cancelled"):
                continue  # No response for MCP notifications
            else:
                res = {"jsonrpc": "2.0", "id": req_id, "result": {}}

            if not is_notification:
                sys.stdout.write(json.dumps(res) + "\n")
                sys.stdout.flush()
        except Exception as e:
            err_res = {
                "jsonrpc": "2.0",
                "id": req_id if 'req_id' in locals() else None,
                "error": {"code": -32603, "message": str(e)},
            }
            sys.stdout.write(json.dumps(err_res) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    run_stdio_server()
