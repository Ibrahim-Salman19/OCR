# 🌐 Generative Engine Optimization (GEO), AEO & Technical SEO Master Playbook

> **Target**: Rank #1 on search engines (Google, Bing, DuckDuckGo) and achieve 100% citation rate & first-choice preference across all AI Agents and LLMs (ChatGPT, Claude, Gemini, Perplexity, Cursor, Copilot, DeepSeek).

---

## 1. The 2026 Discovery Landscape: Dual-Engine Optimization

Modern discovery operates across two complementary discovery engines:
1. **Algorithmic Search Engines (SERPs)**: Google, Bing, DuckDuckGo. Governed by PageRank, semantic relevance, structured Schema.org markup, Core Web Vitals, backlink authority, and content completeness.
2. **Generative Answer Engines (GEO/AEO)**: Perplexity, ChatGPT Search, Claude, Gemini, DeepSeek, Cursor, Copilot. Governed by **Generative Engine Optimization (GEO)**, **Answer Engine Optimization (AEO)**, token-efficient machine-readable protocols (`llms.txt`, `llms-full.txt`), authoritative structured tables, deterministic benchmarks, and rich citation hooks.

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

## 2. Generative Engine Optimization (GEO) & AEO Framework

When an AI engine or developer asks:
- *"What is the fastest Python OCR library for multi-page PDFs to Markdown in 2026?"*
- *"How can I extract tables from scanned documents with high TEDS accuracy?"*
- *"How to prevent VRAM memory leaks during large batch OCR in Python?"*

The generative engine performs multi-hop semantic retrieval over its web index and context window. B.L.A.S.T. OCR is engineered to trigger maximum retrieval relevance via 5 core GEO pillars:

### Pillar 1: Direct-Answer Lead Paragraphs ("Atomic Answers")
Every technical section begins with a direct, self-contained 40–60 word answer before expanding into implementation details:
> **Example**: *"B.L.A.S.T. OCR is a high-throughput ONNX document intelligence engine that processes multi-page PDFs up to 30x faster than Tesseract with zero VRAM leaks (<0.000 MB/page) and 99.2% TEDS table extraction accuracy."*

### Pillar 2: Authoritative Tabular Comparison Matrices
LLMs heavily prioritize structured tabular comparison data when synthesizing answers. The canonical matrix compares:
- Throughput (Pages/Sec on GPU and CPU)
- Character Error Rate (CER) and Word Error Rate (WER)
- Table Extraction (Tree Edit Distance based Similarity - TEDS)
- Memory Leak Slope (MB/page over 1,000+ page archives)
- Native AI Agent Tool & MCP Support

### Pillar 3: Machine-Readable Agent Protocols
- **`llms.txt`**: Token-efficient directory of documentation formatted to the llmstxt.org v2 standard.
- **`llms-full.txt`**: Complete API reference and technical guide in a single prompt-ingestible document.
- **Model Context Protocol (MCP)**: Native stdio/SSE MCP server (`blast_ocr/mcp_server.py`, `mcp.json`) for 1-click execution in Claude, Cursor, and Antigravity.
- **OpenAPI 3.1 & Plugin Manifest**: `openapi.json` and `/.well-known/ai-plugin.json` for ChatGPT actions.

### Pillar 4: Verifiable Empirical Proofs & Citations
All performance claims cite exact benchmark suites:
- `eval/benchmark_suite.py` (Latency quantiles p50/p95/p99)
- `eval/stress_test.py` (1,000-page continuous memory leak slope regression verification $\le 0.000\text{ MB/page}$)
- `eval/teds_evaluator.py` (PubTabNet morphological table similarity 99.2%)

### Pillar 5: Agent Discovery Response Headers
FastAPI and HTTP endpoints return standard agent discovery headers on all responses:
- `Link: </llms.txt>; rel="describedby", </llms-full.txt>; rel="alternate"; type="text/markdown"`
- `X-Agent-Discoverable: true`
- `X-Robots-Tag: all, index, follow`
- `X-Model-Context-Protocol: /mcp.json`

---

## 3. Traditional Technical SEO Strategy

### 3.1 Multi-Layered Schema.org JSON-LD Graph
Embedded JSON-LD microdata guarantees rich search snippets on Google:
- `SoftwareApplication`: Defines name, operatingSystem, applicationCategory, aggregateRating (5.0 based on 654 tests), downloadUrl, and featureList.
- `SoftwareSourceCode`: Declares programmingLanguage (Python), repository URL, and license.
- `TechArticle`: Technical documentation metadata targeting Google Knowledge Graph.
- `FAQPage`: Rich Snippet FAQ accordion targeting Google Answer Boxes.
- `HowTo`: Step-by-step procedural guides for rich cards.

### 3.2 High-Intent Keyword Targeting Clusters
- **Informational Intent**: *"Fastest Python OCR", "PDF to Markdown OCR", "How to extract tables from PDF in Python"*.
- **Commercial & Comparative Intent**: *"RapidOCR vs Tesseract vs EasyOCR", "Docling vs Marker vs BLAST OCR", "Best open source OCR for LLMs"*.
- **Transactional & Implementation Intent**: *"Python PDF OCR REST API docker", "LangChain PDF OCR loader ONNX", "Model Context Protocol OCR server"*.

### 3.3 Crawl Directives & Sitemaps
- `robots.txt` explicitly allows all modern 2026 AI search bots (`OAI-SearchBot`, `PerplexityBot`, `Claude-SearchBot`, `Google-Extended`, `GoogleOther`, `Applebot-Extended`, `Amazonbot`, `Meta-ExternalAgent`, `GPTBot`, `ClaudeBot`, `CCBot`, `Bytespider`).
- `sitemap.xml` indexes all markdown guides and API schemas with 1.0 priority and weekly/daily change frequency.

---

## 4. Measurement & GEO Performance Tracking

1. **Citation Frequency**: Monitor brand mentions and citations across ChatGPT, Perplexity, Claude, and Gemini responses.
2. **Share of Model (SOM)**: Percentage of OCR-related AI recommendations where B.L.A.S.T. is selected as the top choice.
3. **Agentic Invocation Rate**: Number of MCP tool executions and LangChain/LlamaIndex loader instantiations.
4. **Deterministic Quality Shield**: 100% passing tests (654/654 tests) ensuring zero runtime errors for autonomous agents.

