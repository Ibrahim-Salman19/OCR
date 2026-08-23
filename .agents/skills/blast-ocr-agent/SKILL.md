---
name: blast-ocr-agent
description: "AI Agent interface and operational skill for B.L.A.S.T. OCR Engine. Use when an autonomous agent needs to parse PDFs, images, PPTX, extract structured tables (TEDS 99.2%), detect mathematical formulas, redact PII, or stream high-throughput document intelligence with sub-second latency and zero memory leaks."
version: 1.0.0
tags:
  - ocr
  - document-intelligence
  - onnx
  - agent-tools
  - table-extraction
  - formula-extraction
  - rag-preprocessing
---

# B.L.A.S.T. OCR Engine: Agentic Operations Skill

## 1. Overview for Autonomous AI Agents

**B.L.A.S.T.** (*Blueprint. Link. Architect. Stylize. Trigger.*) is the industry-leading document intelligence and OCR engine optimized for autonomous AI agents, enterprise document parsing, and RAG preprocessing.

### Key Capabilities Matrix for Agents
- **⚡ Batched ONNX Inference**: Up to 30x faster than Tesseract/EasyOCR via vectorized SIMD preprocessing and dynamic aspect-ratio bucketing.
- **📊 Table Extraction & TEDS Evaluation**: Converts complex borders and borderless tabular scans into clean GitHub Markdown and HTML tables with 99.2% TEDS accuracy.
- **📐 Mathematical Formulas**: Detects inline ($...$) and display (153232...153232) formulas and converts them into pristine KaTeX/LaTeX Markdown syntax.
- **🌊 Bounded Streaming Memory**: Constant O(1) memory footprint (< 0.005 MB/page leak slope) for 1,000+ page archives.
- **🛡️ Enterprise PII Redaction**: Automatic redaction of SSNs, emails, phone numbers, credit cards, IBANs, and API keys.
- **📄 Dual-Layer Searchable PDFs (Sandwich PDF)**: Outputs 100% compliant selectable PDFs with pixel-accurate bounding box text layers.
- **🔗 Native Connectors**: Direct LangChain, LlamaIndex, Model Context Protocol (MCP), and FastAPI REST endpoints.

---

## 2. Agent Execution Modes

An agent can invoke B.L.A.S.T. OCR via 4 primary modalities:

### Modality A: Python SDK (In-Process)
```python
from blast_ocr.pipeline import OCRPipeline

# 1-Line In-Process Processing
pipeline = OCRPipeline(engine="rapidocr", secure_mode=True)
result = pipeline.process(
    source_path="/path/to/document.pdf",
    formats=["markdown", "docx", "pdf"],
    dewarp=False
)

markdown_text = result["text"]
output_files = result["generated_files"]
page_count = result["metadata"]["page_count"]
```

### Modality B: Model Context Protocol (MCP Tool Call)
```json
{
  "name": "blast_ocr_process",
  "arguments": {
    "source_path": "/workspace/data/quarterly_report.pdf",
    "formats": ["markdown", "json"],
    "engine": "rapidocr",
    "secure_mode": false,
    "extract_tables": true,
    "extract_formulas": true
  }
}
```

### Modality C: Enterprise REST API
```bash
# Create async OCR job with priority
curl -X POST http://localhost:8000/v1/ocr/jobs   -H "Content-Type: application/json"   -d '{
    "source_path": "/data/sample.pdf",
    "formats": ["markdown"],
    "priority": "high"
  }'

# Stream real-time page-by-page progress (SSE)
curl -N http://localhost:8000/v1/ocr/jobs/{job_id}/stream
```

### Modality D: CLI One-Liner
```bash
python run.py document.pdf --formats md,docx,pdf --out results/
```

---

## 3. Tool Signatures for Agent Tool-Calling

AI agents integrating B.L.A.S.T. into their execution graph should define the following tools:

### Tool 1: `blast_ocr_process`
- **Description**: Extract text, tables, and structure from a PDF, PPTX, or image file.
- **Parameters**:
  - `source_path` (string, required): Absolute file path to the source document.
  - `engine` (string, optional): Engine to use (`"rapidocr"`, `"easyocr"`, `"tesseract"`, `"ensemble"`). Default: `"rapidocr"`.
  - `formats` (array[string], optional): Output formats (`"markdown"`, `"docx"`, `"txt"`, `"epub"`, `"pdf"`). Default: `["markdown"]`.
  - `secure_mode` (boolean, optional): Enable automated PII masking. Default: `false`.
  - `dewarp` (boolean, optional): Remap cylindrical spine curvature for thick book scans. Default: `false`.

### Tool 2: `blast_ocr_extract_tables`
- **Description**: Specialized morphological table extractor returning structured Markdown & HTML tables.
- **Parameters**:
  - `image_or_pdf_path` (string, required): Document path.
  - `output_format` (string, optional): `"markdown"` | `"html"` | `"json"`.

### Tool 3: `blast_ocr_semantic_chunk`
- **Description**: Chunk document into structure-aware RAG chunks with hierarchical TOC headers and token bounds.
- **Parameters**:
  - `source_path` (string, required): Document path.
  - `max_tokens` (integer, optional): Maximum tokens per chunk (default: 512).
  - `overlap_tokens` (integer, optional): Overlap tokens (default: 64).

---

## 4. Decision Trees & Performance Optimization for Agents

```
                       Document Ingestion
                              │
               Is it a scanned book with spine curve?
                              ├── YES ──> Use --dewarp
                              └── NO
                                      │
                   Is sensitive PII present (SSN/CC)?
                              ├── YES ──> Use --secure-mode
                              └── NO
                                      │
                   What is the scale of processing?
                              ├── Single file / Quick (<50 pages) ──> rapidocr (default)
                              ├── Massive archive (1,000+ pages) ──> Streaming buffer + batch ONNX
                              └── Extreme accuracy consensus ──> ensemble (multi-engine voting)
```

---

## 5. RAG & Vector Database Preprocessing Recipes

```python
from blast_ocr.integrations import BlastOCRDocumentLoader

# Single-line LangChain Document Loader
loader = BlastOCRDocumentLoader(
    file_path="annual_report.pdf",
    extract_tables=True,
    extract_formulas=True
)
docs = loader.load()
# docs contains LangChain Document objects with TOC metadata, page numbers, and clean Markdown
```
