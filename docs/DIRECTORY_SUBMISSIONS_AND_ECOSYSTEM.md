# 🌐 B.L.A.S.T. OCR — Directory Submissions & Ecosystem Distribution Dossier

> **Purpose**: Ready-to-deploy submission profiles, registry manifests, and directory copy for maximizing domain authority, dofollow backlinks, developer discoverability, and AI agent registry ingestion.
> **Last Updated**: 2026-09-06

---

## 📋 Core Metadata Dossier

| Field | Value |
|---|---|
| **Product Name** | B.L.A.S.T. OCR Engine |
| **Short Tagline (< 60 chars)** | Enterprise ONNX Document Intelligence & OCR Engine |
| **Primary URL** | `https://github.com/Ibrahim-Salman19/OCR` |
| **Live Demo URL** | `https://ocr-book.streamlit.app/` |
| **License** | MIT (100% Permissive Open-Source) |
| **Category** | Developer Tools / AI / OCR / RAG Ingestion |
| **Target Audience** | AI/ML Engineers, Python Developers, Legal/Financial Tech, Data Platform Engineers |
| **Pricing** | Free & Open-Source ($0 USD) |

---

## 📝 Standard Copy Variations

### 50-Character One-Liner
```text
Enterprise ONNX OCR & Document Intelligence Engine
```

### 150-Character Elevator Pitch
```text
B.L.A.S.T. OCR is a self-hosted ONNX document intelligence engine for PDFs and scans with bounded-memory streaming, table parsing, and native MCP support.
```

### 500-Character Directory Description
```text
B.L.A.S.T. OCR is a self-hosted, offline document intelligence and OCR engine for Python. Powered by ONNX Runtime execution (RapidOCR/PP-OCRv4 with CUDA → DirectML → CPU fallback), it converts multi-page PDFs, scanned images, and PPTX decks into structured Markdown, searchable sandwich PDFs, styled DOCX, EPUB 3.0, and layout JSON with zero generative hallucination. It features a bounded sliding-window streaming architecture (0.0002 MB/page leak slope) and native Model Context Protocol (MCP) server for AI agents.
```

---

## 🤖 1. Model Context Protocol (MCP) Registries

Target registries: [Smithery.ai](https://smithery.ai), [mcp.so](https://mcp.so), [Glama.ai](https://glama.ai), [Pulse MCP](https://pulsemcp.com).

### Registry Listing Payload
```json
{
  "name": "blast-ocr",
  "displayName": "B.L.A.S.T. OCR Engine",
  "description": "High-throughput local ONNX OCR, table extraction, and formula recognition with bounded-memory streaming for AI agents.",
  "homepage": "https://github.com/Ibrahim-Salman19/OCR",
  "repository": "https://github.com/Ibrahim-Salman19/OCR",
  "license": "MIT",
  "transport": "stdio",
  "command": "python3",
  "args": ["-m", "blast_ocr.mcp_server"],
  "tools": [
    {
      "name": "blast_ocr_process",
      "description": "Extract text, tables, and metadata from PDFs, images, and PPTX decks with multi-format export."
    },
    {
      "name": "blast_ocr_extract_tables",
      "description": "Morphological table structure detection and cell reconstruction into Markdown and HTML."
    },
    {
      "name": "blast_ocr_extract_formulas",
      "description": "Mathematical formula recognition converting inline and display equations to KaTeX Markdown."
    },
    {
      "name": "blast_ocr_semantic_chunk",
      "description": "Hierarchy-aware document chunking preserving headers, tables, and math for RAG vector search."
    }
  ],
  "categories": ["ocr", "document-processing", "rag", "productivity", "ai-tools"],
  "tags": ["ocr", "onnx", "pdf", "table-extraction", "mcp-server", "rag", "langchain", "llamaindex"]
}
```

---

## 🐙 2. GitHub Awesome Lists Submission Dossier

### Target Lists:
1. `awesome-mcp-servers` (`https://github.com/punkpeye/awesome-mcp-servers`)
2. `awesome-python` (`https://github.com/vinta/awesome-python`)
3. `awesome-rag` (`https://github.com/ai-boost/awesome-rag`)
4. `awesome-ocr` (`https://github.com/kba/awesome-ocr`)

### Proposed Markdown PR Blurb:
```markdown
- [B.L.A.S.T. OCR](https://github.com/Ibrahim-Salman19/OCR) - Enterprise self-hosted ONNX document intelligence engine for PDFs, PPTX, and scans with bounded-memory streaming (0.0002 MB/page leak slope), table extraction, dual-layer searchable PDF generation, and native Model Context Protocol (MCP) server for AI agents.
```

---

## 🚀 3. Product Hunt & AI Directory Listing Dossier

Target platforms: [Product Hunt](https://www.producthunt.com), [Futurepedia](https://www.futurepedia.io), [There's An AI For That](https://theresanaiforthat.com), [OpenTools](https://opentools.ai).

### Product Hunt Submission Fields:
- **Name**: B.L.A.S.T. OCR Engine
- **Tagline**: The self-hosted ONNX document intelligence engine for AI agents
- **Pricing**: Free / Open Source (MIT)
- **Primary Category**: Developer Tools
- **Secondary Category**: Artificial Intelligence / Productivity
- **Makers**: Ibrahim Salman (`https://github.com/Ibrahim-Salman19`)
- **First Comment / Maker Story**:
> "We built B.L.A.S.T. OCR to solve the three major headaches of document intelligence: slow CPU processing, fatal memory leaks on large multi-page PDF archives, and expensive cloud API bills.
> 
> By utilizing ONNX Runtime (RapidOCR/PP-OCRv4 with CUDA → DirectML → CPU fallback) and a bounded sliding-window streaming architecture, B.L.A.S.T. processes 1,000+ page archives with a measured memory leak slope of just 0.0002 MB/page — 7.7x faster than EasyOCR while cutting error rates by 18%.
> 
> Best of all, it includes a native Model Context Protocol (MCP) server so Claude, Cursor, and your autonomous agents can parse PDFs, extract tables, and preserve math formulas locally with zero setup. 100% private, 100% offline, and 100% MIT-licensed."

---

## 📦 4. PyPI Package Index Configuration

Target: `pip install blast-ocr`

### Keywords:
`ocr`, `onnx`, `document-intelligence`, `pdf-to-markdown`, `table-extraction`, `katex`, `formula-recognition`, `searchable-pdf`, `sandwich-pdf`, `mcp`, `model-context-protocol`, `rag`, `langchain`, `llamaindex`, `pp-ocr`, `rapidocr`

### Classifiers:
```text
Development Status :: 5 - Production/Stable
Intended Audience :: Developers
Intended Audience :: Science/Research
License :: OSI Approved :: MIT License
Programming Language :: Python :: 3.9
Programming Language :: Python :: 3.10
Programming Language :: Python :: 3.11
Programming Language :: Python :: 3.12
Programming Language :: Python :: 3.13
Topic :: Scientific/Engineering :: Image Recognition
Topic :: Text Processing :: General
```
