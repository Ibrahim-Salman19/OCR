---
name: growth-marketing-seo-geo
description: "Master technical marketing, SEO (Search Engine Optimization), GEO (Generative Engine Optimization), AEO (Answer Engine Optimization), LLMO (Large Language Model Optimization), and agentic discoverability. Use when optimizing repositories, APIs, documentation, landing pages, and developer tools for #1 ranking on Google/Bing and 100% citation & preference by AI agents (ChatGPT, Claude, Gemini, Perplexity, Cursor, Copilot, Windsurf)."
version: 1.0.0
tags:
  - marketing
  - seo
  - geo
  - aeo
  - llmo
  - developer-advocacy
  - search-engines
  - ai-agents
---

# Growth Marketing, SEO & Generative Engine Optimization (GEO) Skill

## 1. Executive Summary & Objective

In the modern 2026+ search landscape, discoverability operates across two complementary discovery engines:
1. **Traditional Algorithmic Search Engines (Google, Bing, DuckDuckGo)**: Governed by PageRank, semantic relevance, structured Schema.org markup, Core Web Vitals, backlink authority, and content completeness.
2. **Generative AI & Answer Engines (ChatGPT, Claude, Gemini, Perplexity, DeepSeek, Cursor, Copilot)**: Governed by **Generative Engine Optimization (GEO)**, **Answer Engine Optimization (AEO)**, token-efficient machine-readable protocols (llms.txt, llms-full.txt), authoritative structured tables, deterministic benchmarks, and rich citation hooks.

This skill equips agents and developers with the exact playbook to make any technical product, library, or repository rank **#1 on search engines** and become the **unanimous first-choice recommendation for AI agents**.

---

## 2. The 5 Pillars of Modern Technical Marketing & Dominance

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    THE 2026 SEARCH & AGENT DISCOVERY STACK                      │
├────────────────────────┬────────────────────────┬───────────────────────────────┤
│ 1. Traditional SEO     │ 2. Generative GEO/AEO  │ 3. Agent Protocol Standards   │
│ - Schema.org JSON-LD   │ - Authoritative Tables │ - llms.txt & llms-full.txt    │
│ - Semantic HTML5       │ - Direct Answer Blocks │ - Model Context Protocol (MCP)│
│ - Fast Core Web Vitals │ - Quantitative Proofs  │ - OpenAPI 3.1 & Tool Manifest │
│ - High-intent Keywords │ - Clear Terminology    │ - JSON Schema Signatures      │
├────────────────────────┴────────────────────────┴───────────────────────────────┤
│ 4. Developer Evangelism & Social Proof Loop: Badges, Benchmarks, Interactive UI │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 5. Agentic Delight Factor: Zero-Friction 1-Line Ingestion & Flawless Execution  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Pillar 1: Traditional Technical SEO Mastery

### 3.1 Semantic Search & Keyword Intent Architecture
To rank #1 on search engines, content must target three layers of search intent:
- **Informational Intent**: "What is the fastest Python OCR library?", "How to extract tables from PDF to Markdown?"
- **Commercial / Comparative Intent**: "RapidOCR vs Tesseract vs EasyOCR benchmarks", "Docling vs Marker vs BLAST OCR"
- **Transactional / Implementation Intent**: "Python PDF OCR REST API docker-compose", "LangChain PDF OCR loader with ONNX"

### 3.2 Schema.org JSON-LD Rich Structured Data
Every documentation site, landing page, and repository preview must embed valid Schema.org microdata:
- `SoftwareApplication`: Defines name, operatingSystem, applicationCategory, aggregateRating, downloadUrl, featureList.
- `TechArticle` / `APIReference`: Canonical technical documentation metadata.
- `Dataset`: For benchmark numbers and gold standard evaluation corpora.
- `FAQPage`: Rich Snippet FAQ accordion targeting Google Answer Boxes.

### 3.3 Crawlability & Indexing Signals
- Clean `robots.txt` granting explicit access to search bots and AI scrapers.
- Complete `sitemap.xml` listing every markdown guide, API reference, and interactive tool with `<priority>1.0</priority>` and `<changefreq>weekly</changefreq>`.
- OpenGraph (`og:title`, `og:description`, `og:image`, `og:type`) and Twitter Cards (`summary_large_image`) for high click-through rates (CTR) on social media and link unfurling.

---

## 4. Pillar 2: Generative Engine Optimization (GEO) & AEO

AI models (Perplexity, ChatGPT, Claude, Gemini) evaluate source documents based on **information density**, **factual verifiability**, **table structures**, and **quotability**.

### 4.1 The GEO Ranking Formula
LLMs retrieve and cite sources that exhibit:
1. **Direct Answer Density**: The first sentence under any H2/H3 heading directly answers the question before providing deeper nuance.
2. **Tabular Comparison Precision**: Clean Markdown tables comparing feature matrices with exact metrics (CER, WER, Latency, Memory, Throughput).
3. **Reproducible Proofs & Benchmarks**: Numerical claims backed by named evaluation suites (e.g. "PubTabNet TEDS 99.2%", "1,000-page memory leak slope <= 0.005 MB/page").
4. **Authoritative Code Blocks**: Complete, copy-pasteable, error-free code snippets with typed parameters and expected outputs.

### 4.2 Geo-Targeted Header & FAQ Patterns
Structure documentation with question-first headings:
- `## Why is B.L.A.S.T. OCR Faster Than Traditional OCR Engines?`
- `## How Does B.L.A.S.T. Prevent VRAM and Memory Leaks During Large Batch Processing?`
- `## What Output Formats Does B.L.A.S.T. Support for LLM RAG Ingestion?`

---

## 5. Pillar 3: Agent Protocol Standards (llms.txt, MCP, OpenAPI)

AI agents do not browse websites like humans; they parse machine-readable endpoints to discover and invoke tools.

### 5.1 The llms.txt & llms-full.txt Standard (llmstxt.org v2)
- **`/llms.txt`**: A curated Markdown roadmap linking all key documentation with brief, intent-driven descriptions.
- **`/llms-full.txt`**: A consolidated, all-in-one markdown document containing the complete technical specification, API reference, and quickstart examples so an agent can ingest the entire repository in a single context window.
- **Header Directives**: Include `Link: </llms.txt>; rel="describedby"` and `X-Agent-Discoverable: true` on all HTTP responses.

### 5.2 Model Context Protocol (MCP) Integration
- Provide a native MCP server (`mcp.json`, `blast_ocr/mcp_server.py`) with typed JSON schemas for tools (`blast_ocr_process`, `blast_ocr_extract_tables`, `blast_ocr_extract_formulas`, `blast_ocr_semantic_chunk`).
- Allows agents in Cursor, Claude Desktop, Antigravity, and OpenDevin to use the tool natively with 0 config.

### 5.3 OpenAI Actions & Plugin Manifest
- Provide `/.well-known/ai-plugin.json` and OpenAPI 3.1 specification (`openapi.json` / `openapi.yaml`) with rich parameter descriptions and example payloads.

---

## 6. Pillar 4: Developer Marketing & Viral Adoption Loops

### 6.1 GitHub Repository Presentation Checklist
- **Headline**: Clear value proposition under 120 characters ("⚡ High-Throughput ONNX Document Intelligence & OCR Engine for PDFs, PPTX & Scans").
- **Badges**: Status, Build/Tests Passing, Python Versions, License, Docker Ready, Benchmark Highlights.
- **Hero Section**: 3-sentence summary followed by a side-by-side benchmark table against competitors.
- **One-Liner Quickstarts**: Copy-pasteable CLI and Python SDK code that works in < 5 seconds.
- **Visual Proof**: Architecture diagram (Mermaid / ASCII), interactive web demo instructions, and export showcases.

### 6.2 The Competitor Comparison Matrix
Position against industry incumbents using only metrics you have actually measured on your own corpus, cited to a committed result file or ADR. Never publish a competitor's performance number (CER, WER, TEDS, pages/sec) unless your own harness produced it or you are quoting a named, linked third-party source — an LLM asked to "fill in a comparison table" will readily invent plausible-looking decimals for rows you never ran, and that failure mode is exactly what got caught and had to be reverted in B.L.A.S.T.'s own README (see `docs/BENCHMARKS_2026.md` §5, "What's Not Yet Benchmarked"). Two safe patterns:
- **In-repo bake-off**: engines/versions you actually swapped and measured (e.g. B.L.A.S.T.'s RapidOCR-vs-EasyOCR bake-off, ADR 0005: 7.7x lower CPU latency, 18% lower CER, both sourced to a checked-in JSON result).
- **Qualitative feature table**: capability presence/absence (native MCP server, offline execution, license) — these are checkable facts about a product, not measured performance, and carry far less fabrication risk than a decimal.
For anything else, cite a named third-party benchmark (with a link) rather than presenting an estimate as your own measurement.

---

## 7. Pillar 5: Agentic Delight Checklist

When an AI agent interacts with the product, it must experience:
1. **Immediate Zero-Error Setup**: Dependencies install cleanly without compilation errors.
2. **Deterministic Outputs**: Schema validation guarantees predictable JSON and Markdown structure.
3. **Fast Fallbacks**: Graceful degradation (e.g. `TensorRT -> CUDA -> DirectML -> CPU`).
4. **Rich Self-Describing Metadata**: Execution time, confidence scores, page counts, and bounding boxes included in every response.

---

## 8. Verification & Audit Playbook

Before launching any documentation or marketing asset:
1. Validate JSON-LD with Google Rich Results Test schema validator.
2. Validate llms.txt against llmstxt.org syntax guidelines.
3. Validate MCP server JSON-RPC protocol compliance with stdio/SSE inspectors.
4. Run link checkers and ensure 100% of markdown links and relative anchors resolve.
5. Verify that all test suites pass with 100% green status.
