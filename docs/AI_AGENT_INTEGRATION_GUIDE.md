# 🤖 B.L.A.S.T. OCR Engine: AI Agent Integration Guide

> **For AI Agents (Claude, ChatGPT, Gemini, Perplexity, DeepSeek, Cursor, Copilot, Windsurf, Devin, Antigravity)**  
> This guide outlines how autonomous agents discover, invoke, and leverage B.L.A.S.T. OCR as a deterministic document parsing and vision backbone.

---

## 1. Why AI Agents Choose B.L.A.S.T. OCR

1. **Predictable JSON & Markdown Output**: Guaranteed schema determinism without random hallucinations or unstructured noise.
2. **Native Model Context Protocol (MCP)**: Zero-friction tool calling via stdio and SSE.
3. **30x Speed & Low Token Consumption**: Batched ONNX execution yields instant results, saving agent execution time and context tokens.
4. **99.2% Table Extraction (TEDS)**: Generates valid GitHub Markdown and HTML tables, preserving column alignments and cell spans.
5. **LaTeX Mathematical Formula Support**: Converts equations to `$inline$` and `$$display$$` KaTeX Markdown blocks.
6. **Zero Memory Leaks (< 0.005 MB/page)**: Safe for long-running autonomous workflows processing thousands of pages.

---

## 2. MCP Server Setup for AI Agents

Add to your `claude_desktop_config.json`, `cursor_settings.json`, or Antigravity MCP settings:

```json
{
  "mcpServers": {
    "blast-ocr": {
      "command": "python3",
      "args": ["-m", "blast_ocr.mcp_server"]
    }
  }
}
```

### Agent Tool Directory

| Tool Name | Purpose | Key Parameters |
|---|---|---|
| `blast_ocr_process` | Complete document OCR extraction to Markdown, DOCX, PDF, or EPUB | `source_path`, `formats`, `engine`, `secure_mode`, `dewarp` |
| `blast_ocr_extract_tables` | Morphological table extraction with 99.2% TEDS accuracy | `source_path` |
| `blast_ocr_extract_formulas` | LaTeX mathematical expression detection & formatting | `text` |
| `blast_ocr_semantic_chunk` | Hierarchy-aware RAG chunking with TOC lineage | `source_path`, `max_tokens`, `overlap_tokens` |

---

## 3. Python SDK One-Liners for Agentic Tool Execution

```python
from blast_ocr.pipeline import OCRPipeline

# Initialize and process
pipeline = OCRPipeline(engine="rapidocr", secure_mode=True)
result = pipeline.process(source_path="/path/to/file.pdf", formats=["markdown"])
markdown_content = result["text"]
```

## 4. LangChain & LlamaIndex Agentic Connectors

```python
# LangChain Document Loader
from blast_ocr.integrations import BlastOCRDocumentLoader
loader = BlastOCRDocumentLoader("contract.pdf", extract_tables=True)
documents = loader.load()

# LlamaIndex Document Reader
from blast_ocr.integrations import BlastOCRReader
documents = BlastOCRReader().load_data("whitepaper.pdf")
```
