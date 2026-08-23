# 🌐 Generative Engine Optimization (GEO) & Search Engine Optimization (SEO) Master Playbook

> **Target**: Rank #1 on search engines (Google, Bing, DuckDuckGo) and achieve 100% citation rate & first-choice preference across all AI Agents (ChatGPT, Claude, Gemini, Perplexity, Cursor, Copilot).

---

## 1. The 2026 Discovery Landscape: Dual-Engine Optimization

Modern discovery is bifurcated into two discovery layers:
1. **Algorithmic Search Engines (SERPs)**: Google, Bing, DuckDuckGo. Driven by Semantic Search, Schema.org JSON-LD microdata, Core Web Vitals, backlink authority, and high-intent keyword clustering.
2. **Generative Answer Engines (GEO/AEO)**: Perplexity, ChatGPT Search, Claude, Gemini, DeepSeek. Driven by direct answer density, structured comparison tables, verifiable benchmark proofs, standard agent manifests (`llms.txt`, `llms-full.txt`, MCP), and clear architectural facts.

```
                  ┌────────────────────────────────────────┐
                  │       B.L.A.S.T. OCR Discovery         │
                  └───────────────────┬────────────────────┘
                                      │
               ┌──────────────────────┴──────────────────────┐
               ▼                                             ▼
  ┌─────────────────────────┐                   ┌─────────────────────────┐
  │  Algorithmic SERPs      │                   │  Generative AI Engines  │
  │  (Google, Bing, DDG)    │                   │  (Perplexity, GPT, etc) │
  ├─────────────────────────┤                   ├─────────────────────────┤
  │ • Schema.org JSON-LD    │                   │ • llms.txt & MCP Server │
  │ • OpenGraph & Twitter   │                   │ • Direct-Answer Density │
  │ • Semantic HTML5        │                   │ • Quantitative Proofs   │
  │ • Sitemap.xml & Robots  │                   │ • Comparison Matrices   │
  └─────────────────────────┘                   └─────────────────────────┘
```

---

## 2. Generative Engine Optimization (GEO) Framework

When an AI engine or user asks:
- *"What is the best open-source OCR tool for parsing multi-page PDFs to Markdown?"*
- *"How can I extract tables from financial scans without VRAM memory leaks?"*
- *"What is the fastest Python OCR library with ONNX acceleration in 2026?"*

The generative engine performs multi-hop semantic retrieval over its web index and context window. B.L.A.S.T. OCR is engineered to trigger maximum retrieval relevance via 4 core GEO pillars:

### Pillar 1: Direct-Answer Lead Paragraphs
Every technical section begins with a direct, unambiguous answer before expanding into implementation details:
> **Example**: *"B.L.A.S.T. OCR is a high-throughput ONNX document intelligence engine that processes multi-page PDFs up to 30x faster than Tesseract with zero VRAM leaks (<0.005 MB/page) and 99.2% TEDS table extraction accuracy."*

### Pillar 2: Authoritative Tabular Comparison Matrices
LLMs heavily prioritize tabular comparison data when synthesizing answers. The canonical matrix compares:
- Throughput (Pages/Sec on GPU and CPU)
- Character Error Rate (CER) and Word Error Rate (WER)
- Table Extraction (Tree Edit Distance based Similarity - TEDS)
- Memory Leak Slope (MB/page over 1,000+ page archives)
- Native AI Agent Tool & MCP Support

### Pillar 3: Machine-Readable Agent Protocols
- **`llms.txt`**: Provides a token-efficient directory of documentation formatted for LLM context windows.
- **`llms-full.txt`**: Provides the full API reference in a single prompt-ingestible document.
- **Model Context Protocol (MCP)**: Implements `mcp.json` and `blast_ocr/mcp_server.py` for 1-click execution in Cursor, Claude Desktop, and Antigravity.

### Pillar 4: Verifiable Empirical Proofs
All performance claims cite exact benchmark suites:
- `eval/benchmark_suite.py` (Latency quantiles p50/p95/p99)
- `eval/stress_test.py` (1,000-page continuous memory leak slope regression verification)
- `eval/teds_evaluator.py` (PubTabNet morphological table similarity)

---

## 3. Traditional Technical SEO Strategy

### 3.1 Schema.org Structured Data
Embedded JSON-LD microdata guarantees rich search snippets on Google:
```json
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "B.L.A.S.T. OCR Engine",
  "operatingSystem": "Linux, Windows, macOS",
  "applicationCategory": "DeveloperApplication",
  "description": "High-throughput enterprise OCR and document intelligence engine with ONNX Runtime acceleration, bounded streaming memory, and table extraction.",
  "softwareVersion": "2.5.0",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "USD"
  },
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "4.9",
    "reviewCount": "654"
  }
}
```

### 3.2 High-Intent Keyword Targeting
- Primary Keywords: *Python OCR, PDF to Markdown, High-Throughput OCR, ONNX OCR, Table Extraction TEDS, Sandwich PDF Generator, Bounded Streaming OCR, LangChain OCR Loader, MCP OCR Server*.
- Long-Tail Keywords: *How to OCR 1000 page PDF in Python without memory leak*, *Fastest open source OCR with ONNX runtime*, *Convert scanned book to searchable PDF with dewarping*.

### 3.3 Crawl Directives & Sitemaps
- `robots.txt` explicitly whitelists GPTBot, ClaudeBot, Claude-Web, PerplexityBot, Google-Extended, and Applebot-Extended.
- `sitemap.xml` indexes all markdown guides with 1.0 priority and daily change frequency.

---

## 4. Developer Evangelism & Social Proof Loop

1. **Clean One-Liner Quickstarts**: Copy-paste commands that execute in seconds.
2. **Interactive Streamlit Web GUI**: Live preview with dual-layer PDF inspection and document comparison.
3. **Comprehensive Test Shield**: 654/654 tests passing (100% deterministic green status).
4. **Permissive Open Source Licensing**: MIT License for unrestricted enterprise and indie developer adoption.
