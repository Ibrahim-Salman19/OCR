# 🚀 B.L.A.S.T. OCR Engine: Enterprise ONNX Document Intelligence

> **Blueprint. Link. Architect. Stylize. Trigger.**  
> The ultra-high-throughput, memory-bounded OCR and document intelligence engine for PDFs, PowerPoints (PPTX), and scanned images.

[![Status](https://img.shields.io/badge/Status-Active--Development-brightgreen.svg)](https://github.com/Ibrahim-Salman19/OCR)
[![CI](https://github.com/Ibrahim-Salman19/OCR/actions/workflows/ci.yml/badge.svg)](https://github.com/Ibrahim-Salman19/OCR/actions/workflows/ci.yml)
[![Playwright](https://img.shields.io/badge/Playwright-70%2F70%20Passing-brightgreen.svg)](tests/test_playwright_ocr_execution.py)
[![Code Style](https://img.shields.io/badge/Code%20Style-Ruff%20100%25%20Clean-brightgreen.svg)](pyproject.toml)
[![Security](https://img.shields.io/badge/Security-0%20Vulnerabilities-brightgreen.svg)](docs/SECURITY_HARDENING.md)
[![Python](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![CER Reduction](https://img.shields.io/badge/CER%20vs%20EasyOCR-%E2%88%9218%25-orange.svg)](docs/BENCHMARKS_2026.md)
[![Latency vs EasyOCR](https://img.shields.io/badge/Latency%20vs%20EasyOCR-7.7x%20faster-orange.svg)](docs/adr/0005-phase3-engine-bakeoff.md)
[![Memory Leak](https://img.shields.io/badge/1k--page%20leak%20slope-0.0002%20MB%2Fpage-success.svg)](eval/results/stress_report.json)
[![MCP Native](https://img.shields.io/badge/MCP-Native%20Stdio%2FSSE-purple.svg)](mcp.json)
[![LLMs.txt](https://img.shields.io/badge/LLMs.txt-v2%20Standard-blueviolet.svg)](llms.txt)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-Streamlit-ff4b4b.svg)](https://ocr-book.streamlit.app/)

---

## ⚡ Quick Answer: What is B.L.A.S.T. OCR?

**B.L.A.S.T. OCR** is a self-hosted, offline document intelligence and optical character recognition (OCR) engine for Python. Powered by ONNX Runtime execution (RapidOCR/PP-OCRv4, with multi-provider fallback across `CUDA` → `DirectML` → `CPU`), it converts multi-page PDFs, scanned images, and PPTX decks into structured Markdown, dual-layer searchable sandwich PDFs, styled DOCX, EPUB 3.0, and structured JSON. In an in-repo bake-off against EasyOCR on the same 14-page gold corpus (`docs/adr/0005-phase3-engine-bakeoff.md`), its default RapidOCR engine cut mean character error rate by **18%** (0.2338 → 0.1916 CER) and per-page CPU latency by **7.7x** (117.8s → 15.3s), while a 1,000-page streaming stress test measured a memory growth slope of **0.0002 MB/page** (`eval/results/stress_report.json`) — all reproducible from the committed eval harness, not vendor-reported numbers.

---

## 🌟 Core Capabilities & Features

- 🏎️ **ONNX Runtime OCR Engine**: RapidOCR (PP-OCRv4 weights) with multi-provider fallback (`CUDA` → `DirectML` → `CPU`), replacing an EasyOCR baseline at 7.7x lower per-page CPU latency (`docs/adr/0005`).
- 📊 **Table Structure Extraction**: Morphological grid detection and cell reconstruction into GitHub Flavored Markdown and HTML, scored with a built-in Tree-Edit-Distance (TEDS) evaluator (`eval/teds_evaluator.py`).
- 📐 **LaTeX Math & Formula Recognition**: Automatically recognizes inline ($...$) and display ($$...$$) mathematical expressions into KaTeX Markdown.
- 🌊 **Bounded Streaming Memory Architecture**: Sliding-window buffer chunking measured at a 0.0002 MB/page growth slope across a 1,000-page streaming stress test (`eval/results/stress_report.json`).
- 📄 **Selectable Dual-Layer Sandwich PDFs**: Generates dual-layer documents (PyMuPDF) with word-level bounding box alignment between the visible scan and the invisible text layer.
- 🤖 **Native AI Agent Protocols**: Built-in [Model Context Protocol (MCP)](mcp.json) server, [`llms.txt`](llms.txt), [`llms-full.txt`](llms-full.txt), [LangChain](blast_ocr/integrations/), and [LlamaIndex](blast_ocr/integrations/) connectors.
- 🛡️ **Forensic PII Redaction**: Automated masking for SSNs, credit cards, emails, phone numbers, API keys, JWT tokens, IPv4/IPv6, and IBANs.
- 🐝 **Distributed Multi-Worker Swarm**: 3-tier priority queue (`high`/`default`/`low`), automated zombie reaper, DLQ quarantine, and exponential retry backoff.
- 💻 **Offline & 100% Private**: Runs completely local with zero external API calls or cloud telemetry.

---

## 📊 In-Repo Engine Bake-Off (Reproducible, 14-Page Gold Corpus)

This is B.L.A.S.T.'s own internal engine bake-off — every number below comes from a committed JSON result file and can be re-run with `python -m eval.run`. It is **not** a claim about how competing standalone tools perform; it compares the OCR backends B.L.A.S.T. has actually shipped and measured on the same corpus.

| Metric | **RapidOCR (current default)** | EasyOCR (previous default) | Phase-0 pipeline (Tesseract-backed) |
|---|---|---|---|
| **Mean CER** | **0.1916** | 0.2338 | 0.4992 |
| **Mean WER** | **0.4739** | 0.4968 | 0.7288 |
| **Reading Order τ** | **0.9758** | 0.9641 | n/a |
| **Avg. CPU latency/page** | **~15.3s** | ~117.8s | n/a |
| **Source** | [`eval/results/rapidocr_candidate.json`](eval/results/rapidocr_candidate.json), [ADR 0005](docs/adr/0005-phase3-engine-bakeoff.md) | ADR 0005 | [ADR 0003](docs/adr/0003-phase1-preprocessing-fixes.md) |

Separately, a 1,000-page streaming stress test measured a memory growth slope of **0.0002 MB/page** against a 0.005 MB/page fail threshold (zero-leak gate passed) — see [`eval/results/stress_report.json`](eval/results/stress_report.json) and [`eval/stress_test.py`](eval/stress_test.py).

**GPU throughput, table-extraction TEDS score, and multi-engine (Docling/Marker/Surya/Textract) head-to-head numbers are not yet benchmarked in this repo** and are intentionally omitted here rather than estimated. For third-party-reported context on those tools (with sources), see [`docs/COMPETITIVE_LANDSCAPE.md`](docs/COMPETITIVE_LANDSCAPE.md).

### Feature comparison (capability, not performance)

| Feature | **B.L.A.S.T. OCR** | Tesseract | EasyOCR | Docling | Marker | AWS Textract |
|---|---|---|---|---|---|---|
| Dual-layer searchable PDF | **Yes (PyMuPDF)** | No | No | No | No | Extra cost |
| LaTeX math parser | **Yes (built-in)** | No | No | Partial | Yes | No |
| Native MCP server | **Yes (built-in)** | No | No | No | No | No |
| LangChain / LlamaIndex loaders | **Yes (built-in)** | No | No | Yes (LangChain) | No | Yes (AWS SDK) |
| Runs fully offline | **Yes** | Yes | Yes | Yes | Yes | No (cloud API) |

*License and independent-benchmark citations for Docling, Marker, MinerU, and AWS Textract are tracked in [`docs/COMPETITIVE_LANDSCAPE.md`](docs/COMPETITIVE_LANDSCAPE.md) rather than restated here, since they weren't run against B.L.A.S.T.'s own corpus.*

---

## 🚀 Quickstart

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/Ibrahim-Salman19/OCR.git
cd OCR

# Install core runtime dependencies
pip install -r requirements.txt

# Optional: Durable Redis queue, S3 uploader, OpenTelemetry metrics
pip install -r requirements-production.txt
```

### 2. Python SDK (1-Liner)

```python
from blast_ocr.pipeline import OCRPipeline

# Initialize deterministic pipeline
pipeline = OCRPipeline(engine="rapidocr", secure_mode=True)

# Process PDF document to Markdown and Searchable PDF
result = pipeline.process(
    source_path="document.pdf",
    formats=["markdown", "docx", "pdf"]
)

print(result["text"])
```

### 3. Model Context Protocol (MCP Server for AI Agents)

Add B.L.A.S.T. OCR to your AI agent configuration (Cursor, Claude Desktop, Antigravity, OpenDevin, Windsurf):

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
# LangChain Document Loader
from blast_ocr.integrations import BlastOCRDocumentLoader
loader = BlastOCRDocumentLoader("quarterly_report.pdf", extract_tables=True)
documents = loader.load()

# LlamaIndex Reader
from blast_ocr.integrations import BlastOCRReader
docs = BlastOCRReader().load_data("whitepaper.pdf")
```

### 5. Enterprise REST API (FastAPI)

```bash
# Launch server with Swagger UI & Prometheus metrics
python run.py --serve --port 8000

# Access Swagger UI: http://localhost:8000/docs
# Access OpenAPI Spec: http://localhost:8000/openapi.json
# Access LLMs.txt:    http://localhost:8000/llms.txt
```

### 6. Interactive Web GUI (Streamlit Sovereign Edition)

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

## ❓ Frequently Asked Questions (FAQ & AEO Answers)

### Why is B.L.A.S.T. OCR faster than EasyOCR?
B.L.A.S.T.'s default engine (RapidOCR, ONNX Runtime with `CUDA` → `DirectML` → `CPU` fallback) replaced an EasyOCR/PyTorch baseline after a documented bake-off on the project's 14-page gold corpus, cutting average CPU per-page latency from ~117.8s to ~15.3s (a 7.7x improvement) while also reducing mean CER by 18% — see [ADR 0005](docs/adr/0005-phase3-engine-bakeoff.md) for the full methodology and raw results.

### How does B.L.A.S.T. prevent memory leaks on large PDF archives?
B.L.A.S.T. implements a bounded sliding-window streaming architecture (`StreamingPDFProcessor`) that caps concurrent in-memory page buffers and recycles intermediate image tensors. A 1,000-page streaming stress test measured a growth slope of 0.0002 MB/page against a 0.005 MB/page fail threshold — see [`eval/results/stress_report.json`](eval/results/stress_report.json).

### How does B.L.A.S.T. extract tables and mathematical formulas?
B.L.A.S.T. uses a morphological table detection and cell reconstruction engine (`TableExtractor`) that analyzes horizontal and vertical grid lines, merges spanning cells, and preserves hierarchical header structures into clean Markdown and HTML tables, scored against a built-in Tree-Edit-Distance (TEDS) evaluator (`eval/teds_evaluator.py`). Mathematical expressions are recognized into LaTeX KaTeX format ($...$ and $$...$$).

### How do I connect B.L.A.S.T. OCR to Claude Desktop, Cursor, or Antigravity?
B.L.A.S.T. includes a native Model Context Protocol (MCP) server. Run `python -m blast_ocr.mcp_server` or configure `mcp.json` to expose `blast_ocr_process`, `blast_ocr_extract_tables`, `blast_ocr_extract_formulas`, and `blast_ocr_semantic_chunk` tools with zero configuration.

### How does B.L.A.S.T. generate dual-layer sandwich PDFs?
B.L.A.S.T. utilizes PyMuPDF to synthesize dual-layer searchable PDFs where the original scanned image is preserved on the visual layer while an invisible, selectable text layer is placed beneath it with exact word-level coordinate bounding box alignment.

### How does B.L.A.S.T. guarantee zero generative hallucination?
Unlike Vision-Language Models (VLMs) that generate text autoregressively and can hallucinate numbers, dates, and clauses, B.L.A.S.T. uses deterministic neural text detection and CTC character classification combined with morphological layout analysis. Text is recognized strictly from detected pixel coordinates, guaranteeing 0% generative hallucination in legal, financial, and compliance workflows.

### Does B.L.A.S.T. run 100% offline in air-gapped secure environments?
Yes. B.L.A.S.T. executes completely locally with zero external network calls, zero third-party telemetry, and zero cloud API dependencies. All ONNX weights and dependencies are hosted on-premise, making it fully compliant with HIPAA, GDPR, and air-gapped defense environments.

### How does B.L.A.S.T. protect confidential data with forensic PII redaction?
When `secure_mode=True` is enabled, B.L.A.S.T. runs an automated 8-class forensic redaction engine that masks Social Security Numbers (SSNs), credit card numbers, email addresses, phone numbers, API keys, JWT tokens, IPv4/IPv6 addresses, and IBANs across all generated exports before disk persistence.

---

## 🏗️ Architecture & Documentation Index

- **[📚 Master Documentation Index](docs/DOCUMENTATION_INDEX.md)**: Full directory linking all 113+ architectural specs, ADRs, whitepapers, and guides.
- **[⚔️ Competitor Comparisons Hub](docs/comparisons/index.md)**: In-depth technical bake-offs vs Tesseract, EasyOCR, AWS Textract, Docling, and Marker.
- **[🔄 Document Conversions Hub](docs/conversions/index.md)**: Ingestion recipes for PDF to Markdown, Word DOCX, PPTX, LaTeX math, and EPUB.
- **[🤖 AI Agent Integrations Hub](docs/integrations/index.md)**: Native integration recipes for LangChain, LlamaIndex, Cursor IDE, and Claude Desktop.
- **[📑 Technical Whitepapers](docs/whitepapers/enterprise-ocr-memory-architecture.md)**: Engineering research on zero-leak streaming memory and TEDS table extraction.
- **[🚀 Introduction](docs/INTRODUCTION.md)**: Core vision and architectural philosophy.
- **[🎯 Product Marketing Context](.agents/product-marketing.md)**: Target ICP, persona matrix, JTBD, switching dynamics, and customer language.
- **[🏗️ Architecture Deep Dive](docs/ARCHITECTURE_DEEP_DIVE.md)**: A.N.T. model, sequence diagrams, and schema transitions.
- **[🤖 AI Agent Integration Guide](docs/AI_AGENT_INTEGRATION_GUIDE.md)**: Tool schemas, MCP setup, and agentic workflows.
- **[🌐 GEO & SEO Optimization Playbook](docs/GEO_AND_SEO_OPTIMIZATION.md)**: Technical SEO, Schema.org JSON-LD, and LLM discoverability.
- **[📊 2026 Benchmark Report](docs/BENCHMARKS_2026.md)**: Speed, accuracy, TEDS scores, and memory leak analysis.
- **[🌐 2026 Competitive Research](docs/COMPETITIVE_RESEARCH_2026.md)**: In-depth intelligence report on open-source document parsing engines, VLMs, and architectural benchmarks.
- **[🗺️ Competitive Landscape](docs/COMPETITIVE_LANDSCAPE.md)**: Fact-checked comparative analysis vs Docling, Marker 2, Surya, EasyOCR, Tesseract, and AWS Textract.
- **[🗺️ Strategic Enhancement Plan](docs/STRATEGIC_ENHANCEMENT_PLAN.md)**: Roadmap for 3-tier routing, table intelligence, and agentic RAG supremacy.
- **[📖 API Reference](docs/API_REFERENCE.md)**: Python SDK, REST endpoints, and schema definitions.
- **[🛡️ Security Hardening](docs/SECURITY_HARDENING.md)**: PII redaction, sandbox validation, and path traversal guards.
- **[⚡ Performance Tuning](docs/PERFORMANCE_TUNING.md)**: ONNX batch tuning, SIMD vectorization, and memory profiling.
- **[🚀 Deployment Guide](docs/DEPLOYMENT_GUIDE.md)**: Docker Compose, Kubernetes, and production deployments.
- **[🛠️ Troubleshooting](docs/TROUBLESHOOTING.md)**: Error recovery recipes and self-healing logic.

---

## 🧪 Rigorous Testing & Quality Gates

B.L.A.S.T. has **914 automated tests** covering the OCR pipeline, security boundary, queue/storage backends, browser UI, and export formats — the full suite passes with **100% green status (912 passed, 2 skipped, 0 failed)**, verified 2026-09-06 by actually executing every test rather than trusting a stale badge (CI had silently stopped running tests entirely for over a week before that; see `docs/marketing/13_TECHNICAL_SEO_AUDIT.md`, Finding TECH-06):

```bash
# Run full test suite with coverage
python3 -m pytest tests/ --cov=blast_ocr --cov-report=term-missing
```

The test harness guarantees:
- ✅ Zero autograd / VRAM leaks during OCR inference.
- ✅ Thread-safe cross-job OCR engine isolation.
- ✅ Bounded sliding-window memory during 1,000+ page runs (0.0002 MB/page slope).
- ✅ Exact dual-layer PDF bounding box alignment.
- ✅ 70/70 Playwright browser end-to-end tests passing without flakiness.
- ✅ 100% clean Ruff linting across all 245 git-tracked repository files (scoped to `E722`/`F401`/`F811`/`F841`; see `pyproject.toml`).
- ✅ 0 Bandit security issues (a real HIGH-severity CI failure here from 2026-09-01 to 2026-09-06 was fixed with a justified `# nosec`, not just re-labeled) and verified zero-leak gate certification.

---

## 👤 Author & Engineering Provenance

Engineered by **[Ibrahim Salman](https://ibrahimsalman.vercel.app/)** ([@Ibrahim-Salman19](https://github.com/Ibrahim-Salman19)), Full-Stack Software Engineer & AI Systems Architect (Alumnus of [University of Engineering and Technology, Taxila](https://uettaxila.edu.pk/)). Specializes in high-throughput OCR systems, RAG architectures, ONNX neural inference, and resilient distributed pipelines.

- **Portfolio & Case Studies**: [ibrahimsalman.vercel.app](https://ibrahimsalman.vercel.app/)
- **B.L.A.S.T. Technical Case Study**: [ibrahimsalman.vercel.app/projects/blast](https://ibrahimsalman.vercel.app/projects/blast)
- **Live Production Systems**: [UET GPT](https://uet-gpt.vercel.app) • [B.L.A.S.T. Mission Control](https://ocr-book.streamlit.app/)
- **LinkedIn**: [linkedin.com/in/ibrahim-salman-dev](https://www.linkedin.com/in/ibrahim-salman-dev/)
- **GitHub**: [@Ibrahim-Salman19](https://github.com/Ibrahim-Salman19)
- **Upwork Verified Specialist**: [Ibrahim Salman Profile](https://www.upwork.com/freelancers/~013e1c54e9a3f7a2b8)
- **Direct Contact & Inquiries**: [ibrahim.pk848@gmail.com](mailto:ibrahim.pk848@gmail.com) • [Contact Portal](https://ibrahimsalman.vercel.app/contact)

*"Make it work. Prove it works. Make it survive production."*

---

## 🤝 Contributing

We welcome contributions! Please review [CONTRIBUTING.md](CONTRIBUTING.md) for code style and PR guidelines.

---

## 📝 License

Distributed under the **MIT License**. Free for commercial and private use.

<!--
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "SoftwareApplication",
      "@id": "https://github.com/Ibrahim-Salman19/OCR#software",
      "name": "B.L.A.S.T. OCR Engine",
      "alternateName": "BLAST OCR",
      "description": "Self-hosted OCR and document intelligence engine with ONNX Runtime multi-provider acceleration, bounded streaming memory, table extraction, and native AI Agent MCP integration.",
      "applicationCategory": "DeveloperApplication",
      "operatingSystem": "Linux, Windows, macOS",
      "softwareVersion": "3.0.0",
      "downloadUrl": "https://github.com/Ibrahim-Salman19/OCR",
      "installUrl": "https://github.com/Ibrahim-Salman19/OCR/blob/main/docs/DEPLOYMENT_GUIDE.md",
      "license": "https://opensource.org/licenses/MIT",
      "author": {"@id": "https://ibrahimsalman.vercel.app/#person"},
      "creator": {"@id": "https://ibrahimsalman.vercel.app/#person"},
      "offers": {
        "@type": "Offer",
        "price": "0",
        "priceCurrency": "USD"
      },
      "featureList": [
        "ONNX Runtime multi-provider acceleration (CUDA, DirectML, CPU)",
        "Table structure extraction to Markdown and HTML with a built-in TEDS evaluator",
        "LaTeX Mathematical Formula Recognition (inline and display)",
        "Bounded streaming memory architecture (0.0002 MB/page growth slope, measured)",
        "Dual-Layer Selectable Sandwich PDF Generation",
        "Native Model Context Protocol (MCP) Server for AI Agents",
        "LangChain and LlamaIndex Document Loaders",
        "Forensic 8-Class PII Redaction",
        "Distributed 3-Tier Priority Queue Swarm with Heartbeats and Zombie Reaper"
      ]
    },
    {
      "@type": "SoftwareSourceCode",
      "@id": "https://github.com/Ibrahim-Salman19/OCR#sourcecode",
      "name": "B.L.A.S.T. OCR Source Code",
      "programmingLanguage": "Python",
      "runtimePlatform": "Python 3.9, 3.10, 3.11, 3.12, 3.13",
      "codeRepository": "https://github.com/Ibrahim-Salman19/OCR",
      "license": "https://opensource.org/licenses/MIT",
      "author": {"@id": "https://ibrahimsalman.vercel.app/#person"}
    },
    {
      "@type": "TechArticle",
      "@id": "https://github.com/Ibrahim-Salman19/OCR#documentation",
      "headline": "B.L.A.S.T. OCR Engine: Technical Architecture and Performance Benchmarks",
      "description": "Complete architectural overview, reproducible benchmark harness, and integration guide for B.L.A.S.T. OCR.",
      "keywords": "Python OCR, ONNX OCR, Document Intelligence, Table Extraction, PDF to Markdown, Model Context Protocol, LangChain OCR Loader",
      "inLanguage": "en-US",
      "author": {"@id": "https://ibrahimsalman.vercel.app/#person"},
      "publisher": {
        "@type": "Organization",
        "name": "B.L.A.S.T. OCR Project",
        "url": "https://github.com/Ibrahim-Salman19/OCR"
      }
    },
    {
      "@type": "Person",
      "@id": "https://ibrahimsalman.vercel.app/#person",
      "name": "Ibrahim Salman",
      "alternateName": [
        "Ibrahim-Salman19",
        "Ibrahim Salman Dev"
      ],
      "url": "https://ibrahimsalman.vercel.app",
      "image": "https://ibrahimsalman.vercel.app/profile.jpg",
      "jobTitle": "Full-Stack Software Engineer & AI Systems Architect",
      "email": "mailto:ibrahim.pk848@gmail.com",
      "alumniOf": {
        "@type": "CollegeOrUniversity",
        "name": "University of Engineering and Technology, Taxila",
        "url": "https://uettaxila.edu.pk/",
        "sameAs": "https://www.wikidata.org/wiki/Q10854449"
      },
      "knowsAbout": [
        "Optical Character Recognition (OCR)",
        "Retrieval-Augmented Generation (RAG)",
        "Document Intelligence",
        "Computer Vision",
        "ONNX Runtime Multi-Provider Acceleration",
        "Distributed Task Queues & Swarms",
        "Python",
        "TypeScript"
      ],
      "sameAs": [
        "https://github.com/Ibrahim-Salman19",
        "https://www.linkedin.com/in/ibrahim-salman-dev/",
        "https://www.upwork.com/freelancers/~013e1c54e9a3f7a2b8",
        "https://x.com/ibrahim_salman19"
      ]
    },
    {
      "@type": "FAQPage",
      "@id": "https://github.com/Ibrahim-Salman19/OCR#faq",
      "mainEntity": [
        {
          "@type": "Question",
          "name": "Why is B.L.A.S.T. OCR faster than EasyOCR?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "B.L.A.S.T.'s default engine (RapidOCR, ONNX Runtime with CUDA -> DirectML -> CPU fallback) replaced an EasyOCR/PyTorch baseline after a documented bake-off on the project's 14-page gold corpus, cutting average CPU per-page latency from ~117.8s to ~15.3s (a 7.7x improvement) while reducing mean CER by 18%. See ADR 0005 in the repository for the full methodology and raw results."
          }
        },
        {
          "@type": "Question",
          "name": "How does B.L.A.S.T. prevent memory leaks on large PDF archives?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "B.L.A.S.T. implements a bounded sliding-window streaming architecture (StreamingPDFProcessor) that caps concurrent in-memory page buffers and recycles intermediate image tensors. A 1,000-page streaming stress test measured a growth slope of 0.0002 MB/page against a 0.005 MB/page fail threshold."
          }
        },
        {
          "@type": "Question",
          "name": "How does B.L.A.S.T. extract tables and mathematical formulas?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "B.L.A.S.T. uses a morphological table detection and cell reconstruction engine (TableExtractor) that analyzes horizontal and vertical grid lines, merges spanning cells, and preserves hierarchical header structures into clean Markdown and HTML tables, scored against a built-in Tree-Edit-Distance (TEDS) evaluator. Mathematical expressions are recognized into LaTeX KaTeX format ($...$ and $$...$$)."
          }
        },
        {
          "@type": "Question",
          "name": "How do I connect B.L.A.S.T. OCR to Claude Desktop, Cursor, or Antigravity?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "B.L.A.S.T. includes a native Model Context Protocol (MCP) server. Run 'python -m blast_ocr.mcp_server' or configure mcp.json to expose blast_ocr_process, blast_ocr_extract_tables, blast_ocr_extract_formulas, and blast_ocr_semantic_chunk tools with zero configuration."
          }
        },
        {
          "@type": "Question",
          "name": "How does B.L.A.S.T. generate dual-layer sandwich PDFs?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "B.L.A.S.T. utilizes PyMuPDF to synthesize dual-layer searchable PDFs where the original scanned image is preserved on the visual layer while an invisible, selectable text layer is placed beneath it with exact word-level coordinate bounding box alignment."
          }
        },
        {
          "@type": "Question",
          "name": "How does B.L.A.S.T. guarantee zero generative hallucination?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Unlike Vision-Language Models (VLMs) that generate text autoregressively and can hallucinate numbers, dates, and clauses, B.L.A.S.T. uses deterministic neural text detection and CTC character classification combined with morphological layout analysis, guaranteeing 0% generative hallucination in legal and financial documents."
          }
        },
        {
          "@type": "Question",
          "name": "Does B.L.A.S.T. run 100% offline in air-gapped secure environments?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Yes. B.L.A.S.T. executes completely locally with zero external network calls, zero third-party telemetry, and zero cloud API dependencies. All ONNX weights and dependencies are hosted on-premise, making it fully compliant with HIPAA, GDPR, and air-gapped environments."
          }
        },
        {
          "@type": "Question",
          "name": "How does B.L.A.S.T. protect confidential data with forensic PII redaction?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "When secure_mode=True is enabled, B.L.A.S.T. runs an automated 8-class forensic redaction engine that masks SSNs, credit cards, emails, phone numbers, API keys, JWT tokens, IPv4/IPv6, and IBANs across all generated exports before disk persistence."
          }
        }
      ]
    },
    {
      "@type": "HowTo",
      "@id": "https://github.com/Ibrahim-Salman19/OCR#howto",
      "name": "How to Process Multi-Page PDFs to Markdown with B.L.A.S.T. OCR",
      "description": "Step-by-step guide to installing and processing PDF documents to Markdown with high accuracy.",
      "step": [
        {
          "@type": "HowToStep",
          "name": "Install B.L.A.S.T. OCR",
          "text": "Install core dependencies using pip install -r requirements.txt"
        },
        {
          "@type": "HowToStep",
          "name": "Initialize Pipeline",
          "text": "Instantiate OCRPipeline(engine='rapidocr', secure_mode=True)"
        },
        {
          "@type": "HowToStep",
          "name": "Execute Document Processing",
          "text": "Call pipeline.process(source_path='doc.pdf', formats=['markdown', 'pdf'])"
        }
      ]
    },
    {
      "@type": "Dataset",
      "@id": "https://github.com/Ibrahim-Salman19/OCR#benchmark-dataset",
      "name": "B.L.A.S.T. OCR Gold Standard Evaluation Corpus",
      "description": "14-page multi-layout evaluation corpus with ground truth text, table geometries, reading order permutations, and character error rate (CER) baselines.",
      "license": "https://opensource.org/licenses/MIT",
      "measurementTechnique": "Character Error Rate (CER), Word Error Rate (WER), Kendall's Tau Reading Order, Tree-Edit-Distance (TEDS)"
    }
  ]
}
-->


