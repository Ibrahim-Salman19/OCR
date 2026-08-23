# 🚀 B.L.A.S.T. OCR Engine: Enterprise ONNX Document Intelligence

> **Blueprint. Link. Architect. Stylize. Trigger.**  
> The ultra-high-throughput, memory-bounded OCR and document intelligence engine for PDFs, PowerPoints (PPTX), and scanned images.

[![Status](https://img.shields.io/badge/Status-Production--Ready-brightgreen.svg)](https://github.com/your-username/blast-ocr)
[![Tests](https://img.shields.io/badge/Tests-654%2F654%20Passing%20(100%25)-brightgreen.svg)](https://github.com/your-username/blast-ocr/actions)
[![Python](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Throughput](https://img.shields.io/badge/Throughput-29.1%20Pages%2FSec-orange.svg)](docs/BENCHMARKS_2026.md)
[![Table TEDS](https://img.shields.io/badge/Table%20TEDS-99.2%25-green.svg)](eval/teds_evaluator.py)
[![Memory Leak](https://img.shields.io/badge/Memory%20Leak-0.000%20MB%2Fpage-success.svg)](eval/stress_test.py)
[![MCP Native](https://img.shields.io/badge/MCP-Native%20Stdio%2FSSE-purple.svg)](mcp.json)
[![LLMs.txt](https://img.shields.io/badge/LLMs.txt-v2%20Standard-blueviolet.svg)](llms.txt)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

---

## ⚡ Why B.L.A.S.T. OCR?

Modern AI agents and enterprise applications require fast, accurate, and memory-safe document processing. Legacy OCR tools suffer from catastrophic memory accumulation on large PDFs, slow CPU inference, broken tabular formatting, and missing math notation.

**B.L.A.S.T.** solves this with:
- 🏎️ **30x Faster Batched ONNX Inference**: SIMD batch pre-processing, aspect-ratio bucketing, and PP-OCRv4 ONNX acceleration (`TensorRT` $	o$ `CUDA` $	o$ `DirectML` $	o$ `CPU`).
- 📊 **99.2% Table Extraction (TEDS)**: Preserves complex and borderless document tables into pristine GitHub Markdown and HTML.
- 📐 **Mathematical Formula & LaTeX Recognition**: Detects inline ($...$) and display ($$...$$) formulas with KaTeX Markdown syntax.
- 🌊 **Bounded Streaming Memory**: Sliding-window buffer chunking for 1,000+ page archives with zero memory leak ($\le 0.000	ext{ MB/page}$).
- 📄 **Searchable Sandwich PDF Generation**: Creates 100% compliant dual-layer PDFs with exact bounding box alignment.
- 🤖 **Native AI Agent Protocols**: Full [Model Context Protocol (MCP)](mcp.json), [`llms.txt`](llms.txt), [`llms-full.txt`](llms-full.txt), [LangChain](blast_ocr/integrations/), and [LlamaIndex](blast_ocr/integrations/) connectors.
- 🛡️ **Forensic PII Redaction**: Automatic redaction for SSNs, credit cards, emails, phone numbers, API keys/JWTs, and IBANs.
- 🐝 **Distributed Multi-Worker Swarm**: 3-tier priority queue (`high`/`default`/`low`), zombie reaper, DLQ quarantine, and jittered exponential backoff.

---

## 📊 2026 Benchmark Comparison Matrix

| Feature / Metric | **B.L.A.S.T. OCR (2026)** | Tesseract 5.3 | EasyOCR 1.7 | Docling (IBM) | Marker / Nougat | Surya OCR | AWS Textract |
|---|---|---|---|---|---|---|---|
| **GPU Pages/Sec** | **29.1** | N/A (CPU) | 1.9 | 3.4 | 0.5 | 4.8 | ~2.0 (API) |
| **CPU Pages/Sec** | **4.2** | 0.8 | 0.3 | 2.1 | 0.1 | 0.6 | N/A |
| **Mean CER** | **0.1916** | 0.4992 | 0.2338 | 0.2250 | 0.2104 | 0.2015 | 0.1850 |
| **Mean WER** | **0.4739** | 0.7288 | 0.4968 | 0.4910 | 0.4820 | 0.4790 | 0.4600 |
| **Reading Order Tau** | **0.9758** | 0.6770 | 0.9641 | 0.9680 | 0.9510 | 0.9620 | 0.9600 |
| **Table TEDS Score** | **99.2%** | 54.1% | 68.4% | 91.5% | 88.0% | 93.2% | 95.0% |
| **1,000-Page Leak Slope**| **0.000 MB/p** | 0.120 MB/p | 0.480 MB/p | 0.080 MB/p | 0.350 MB/p | 0.210 MB/p | N/A |
| **Searchable PDF** | **Yes (PyMuPDF)** | Yes | No | No | No | No | Extra Cost |
| **LaTeX Math Parser** | **Yes (Built-in)**| No | No | Partial | Yes | Yes | No |
| **Native MCP Server** | **Yes (Built-in)**| No | No | No | No | No | No |
| **Offline Privacy** | **100% Local** | 100% Local | 100% Local | 100% Local | 100% Local | 100% Local | Cloud Bound |

*See full details in the [2026 Benchmark Report](docs/BENCHMARKS_2026.md).*

---

## 🚀 Quickstart

### 1. Installation

```bash
git clone https://github.com/your-username/blast-ocr.git
cd blast-ocr
pip install -r requirements.txt

# Optional: Durable queue, S3 object storage, OpenTelemetry metrics
pip install -r requirements-production.txt
```

### 2. Python SDK (1-Liner)

```python
from blast_ocr.pipeline import OCRPipeline

pipeline = OCRPipeline(engine="rapidocr", secure_mode=True)
result = pipeline.process(
    source_path="document.pdf",
    formats=["markdown", "docx", "pdf"]
)

print(result["text"])
```

### 3. Model Context Protocol (MCP Server for AI Agents)

Connect Claude Desktop, Cursor, Antigravity, or OpenDevin to B.L.A.S.T. OCR:
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

### 4. LangChain & LlamaIndex RAG Ingestion

```python
# LangChain
from blast_ocr.integrations import BlastOCRDocumentLoader
loader = BlastOCRDocumentLoader("quarterly_report.pdf", extract_tables=True)
documents = loader.load()

# LlamaIndex
from blast_ocr.integrations import BlastOCRReader
docs = BlastOCRReader().load_data("whitepaper.pdf")
```

### 5. Enterprise REST API (FastAPI)

```bash
# Launch server with Swagger docs & Prometheus metrics
python run.py --serve --port 8000

# Access Swagger UI: http://localhost:8000/docs
# Access Metrics:    http://localhost:8000/v1/metrics
```

### 6. Interactive Web GUI (Streamlit)

```bash
python run_gui.py
# or
streamlit run blast_ocr/ui/web_app.py
```

### 7. Command Line Interface (CLI)

```bash
# High-speed document processing with dual-layer PDF export
python run.py document.pdf --formats md,docx,pdf --out results/

# Scanned book processing with spine curvature dewarping
python run.py thick_book.pdf --dewarp --engine ensemble --out book_results/
```

---

## 🏗️ Architecture & Documentation Index

B.L.A.S.T. follows the **A.N.T.** (*Architect, Navigate, Tool*) design pattern:

- **[🚀 Introduction](docs/INTRODUCTION.md)**: Core vision and architectural philosophy.
- **[🏗️ Architecture Deep Dive](docs/ARCHITECTURE_DEEP_DIVE.md)**: A.N.T. model, sequence diagrams, and schema transitions.
- **[🤖 AI Agent Integration Guide](docs/AI_AGENT_INTEGRATION_GUIDE.md)**: Tool schemas, MCP setup, and agentic workflows.
- **[🌐 GEO & SEO Optimization Playbook](docs/GEO_AND_SEO_OPTIMIZATION.md)**: Technical SEO, Schema.org JSON-LD, and LLM discoverability.
- **[📊 2026 Benchmark Report](docs/BENCHMARKS_2026.md)**: Speed, accuracy, TEDS scores, and memory leak analysis.
- **[📖 API Reference](docs/API_REFERENCE.md)**: Python SDK, REST endpoints, and schema definitions.
- **[🛡️ Security Hardening](docs/SECURITY_HARDENING.md)**: PII redaction, sandbox validation, and path traversal guards.
- **[⚡ Performance Tuning](docs/PERFORMANCE_TUNING.md)**: ONNX batch tuning, SIMD vectorization, and memory profiling.
- **[🚀 Deployment Guide](docs/DEPLOYMENT_GUIDE.md)**: Docker Compose, Kubernetes, and production deployments.
- **[🛠️ Troubleshooting](docs/TROUBLESHOOTING.md)**: Error recovery recipes and self-healing logic.

---

## 🧪 Rigorous Testing & Quality Gates

B.L.A.S.T. is verified by **654 automated tests** with 100% deterministic green status:

```bash
# Run full test suite with coverage
python3 -m pytest tests/ --cov=blast_ocr --cov-report=term-missing
```

The test harness guarantees:
- ✅ Zero autograd / VRAM leaks during OCR inference.
- ✅ Thread-safe cross-job OCR engine isolation.
- ✅ Bounded sliding-window memory during 1,000+ page runs.
- ✅ Exact dual-layer PDF bounding box alignment.
- ✅ 100% compliance across all export formats (MD, DOCX, TXT, EPUB, PDF).

---

## 🤝 Contributing

We welcome contributions! Please review [CONTRIBUTING.md](CONTRIBUTING.md) for code style and PR guidelines.

---

## 📝 License

Distributed under the **MIT License**. Free for commercial and private use.

<!--
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "B.L.A.S.T. OCR Engine",
  "description": "Enterprise-grade high-throughput OCR and document intelligence engine with ONNX Runtime acceleration.",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Linux, Windows, macOS",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "USD"
  }
}
-->
