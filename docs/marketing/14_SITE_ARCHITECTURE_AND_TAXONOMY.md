# 🗺️ Site Architecture, URL Taxonomy & Internal Linking Graph

**Status**: 🟢 Production-Grade Masterclass  
**Framework**: Hub-and-Spoke Information Architecture & PageRank Equity Distribution  
**Applicable Skills**: `site-architecture`, `growth-marketing-seo-geo`, `seo-audit`, `programmatic-seo`  
**Total Indexed Surfaces**: 89 Validated Endpoints across Docs, ADRs, Playbooks, and API

---

## 🏛️ 1. Complete Site Topology & Visual Hierarchy

The B.L.A.S.T. digital ecosystem is structured to provide an immediate 3-click maximum path to any document, benchmark proof, or code snippet:

```
                                      ┌─────────────────────────────────────────┐
                                      │            TIER 0: ROOT HUB             │
                                      │    https://github.com/Ibrahim-Salman19/OCR │
                                      │  (README.md, Hero, Quickstart, Video)   │
                                      └────────────────────┬────────────────────┘
                                                           │
         ┌────────────────────────────────┬────────────────┴────────────────┬────────────────────────────────┐
         ▼                                ▼                                 ▼                                ▼
┌──────────────────┐            ┌──────────────────┐              ┌──────────────────┐             ┌──────────────────┐
│  TIER 1: ENGINE  │            │  TIER 1: SYSTEM  │              │  TIER 1: AGENTIC │             │ TIER 1: BUSINESS │
│  & BENCHMARKS    │            │   RELIABILITY    │              │    INTELLIGENCE  │             │   & SOVEREIGNTY  │
└────────┬─────────┘            └────────┬─────────┘              └────────┬─────────┘             └────────┬─────────┘
         │                               │                                 │                                │
         ├─ docs/BENCHMARKS_2026.md      ├─ docs/STRATEGIC_PLAN.md         ├─ .agents/skills/               ├─ docs/marketing/
         ├─ eval/benchmark_suite.py      ├─ docs/adr/                      │  ├─ blast-ocr-agent            │  ├─ 08_GRAND_SLAM...
         ├─ eval/stress_test.py          │  ├─ ADR-001 Streaming          │  └─ agentic-rag-connector      │  ├─ 09_PRICING...
         └─ docs/seo/high-throughput...  │  ├─ ADR-002 Dual Cache          ├─ blast_ocr/mcp_server.py       │  ├─ 10_SALES_ENAB...
                                         │  └─ ADR-003 Swarm Queues        ├─ docs/seo/mcp-server-ocr...    └─ docs/seo/cost...
                                         └─ docs/seo/pdf-memory-leak...    └─ docs/seo/extract-tables...
```

---

## 🏷️ 2. URL Taxonomy & Slug Formatting Standards

Every URL and document path adheres to strict architectural naming conventions:

1. **Protocol & Hostname**: Canonical URL prefix `https://github.com/Ibrahim-Salman19/OCR/blob/main/` or local REST API `http://localhost:8000/v1/`.
2. **Kebab-Case Lowercase Slugs**: All public URLs and SEO documents use lowercase letters and hyphens (e.g., `high-throughput-pdf-ocr-python.md`). No underscores or uppercase characters in web slugs.
3. **Zero Trailing Slashes**: Enforced at the router level (`/docs/benchmarks` not `/docs/benchmarks/`).
4. **Logical Hierarchical Nesting**:
   - `/docs/`: Foundational architectural documentation and benchmarks.
   - `/docs/adr/`: Architecture Decision Records (immutable RFC records).
   - `/docs/marketing/`: GTM, commercialization, and revenue operations playbooks.
   - `/docs/seo/`: Programmatic and high-intent developer answer-first hubs.
   - `/v1/`: Versioned REST API and OpenAPI interactive documentation (`/v1/docs`).

---

## 🧭 3. Persona-Driven User Flows (IA Navigation Paths)

### Flow A: The Skeptical Systems Engineer (Focus: Speed & Memory Proof)
```
Step 1: Arrives on GitHub README via Reddit or Hacker News.
Step 2: Scans Hero Bar: "29.1 Pages/Second | 0.0002 MB/Page Memory Slope".
Step 3: Clicks [BENCHMARKS_2026.md](docs/BENCHMARKS_2026.md) to inspect raw hardware specifications.
Step 4: Copies reproducible CLI command: `python -m blast_ocr.core.benchmark --quick`.
Step 5: Verifies execution on local machine in under 30 seconds.
```

### Flow B: The AI Platform Lead (Focus: RAG Tables & MCP Integration)
```
Step 1: Discovers B.L.A.S.T. via Claude Desktop or MCP server registry.
Step 2: Reads [docs/seo/mcp-server-ocr-setup-guide.md](docs/seo/mcp-server-ocr-setup-guide.md).
Step 3: Pastes `blast_ocr.mcp_server` JSON into `claude_desktop_config.json`.
Step 4: Prompts Claude to parse a complex balance sheet PDF.
Step 5: Observes perfect Markdown table structure and zero hallucination.
```

### Flow C: The Enterprise CTO / InfoSec Director (Focus: Compliance & Air-Gap)
```
Step 1: Receives Sales One-Pager or cold email outreach.
Step 2: Visits [docs/marketing/10_SALES_ENABLEMENT_PLAYBOOK.md](docs/marketing/10_SALES_ENABLEMENT_PLAYBOOK.md).
Step 3: Reviews 20-Point Enterprise Security RFP Bank (Zero VPC egress, SOC2/HIPAA alignment).
Step 4: Schedules 14-Day Staging Pilot Sprint via calendar link.
```

---

## 🕸️ 4. Hub-and-Spoke Topic Clusters & Link Equity Graph

To maximize PageRank distribution and Generative Engine citation authority, the site organizes content into 4 self-reinforcing topic clusters:

```
+---------------------------------------------------------------------------------------------+
| TOPIC CLUSTER 1: INFERENCE SPEED & RUNTIME ARCHITECTURE (HUB: docs/BENCHMARKS_2026.md)      |
+---------------------------------------------------------------------------------------------+
| Inbound Spokes:                                                                             |
| - docs/seo/high-throughput-pdf-ocr-python.md (Links to Hub within first 100 words)          |
| - docs/marketing/07_COMPETITOR_COMPARISONS_AND_BATTLECARDS.md (Cites empirical CER numbers) |
| - README.md (Primary hero anchor link)                                                      |
| Outbound Spokes:                                                                            |
| - Hub links to ADR-001 (Streaming), ADR-003 (Swarm), and Python SIMD preprocessor code     |
+---------------------------------------------------------------------------------------------+
| TOPIC CLUSTER 2: ZERO-LEAK SYSTEMS RELIABILITY (HUB: docs/STRATEGIC_ENHANCEMENT_PLAN.md)   |
+---------------------------------------------------------------------------------------------+
| Inbound Spokes:                                                                             |
| - docs/seo/pdf-ocr-memory-leak-prevention.md                                               |
| - docs/marketing/45_CHURN_PREVENTION_AND_RETENTION_PLAYBOOK.md                              |
| - eval/stress_test.py (Direct citation in script docstrings)                               |
| Outbound Spokes:                                                                            |
| - Hub links to sliding-window buffer, zombie reaper failover, and Redis heartbeat client    |
+---------------------------------------------------------------------------------------------+
| TOPIC CLUSTER 3: AGENTIC AI, TABLES & MCP (HUB: docs/seo/mcp-server-ocr-setup-guide.md)    |
+---------------------------------------------------------------------------------------------+
| Inbound Spokes:                                                                             |
| - docs/seo/extract-tables-from-scanned-pdf-python.md                                        |
| - docs/marketing/31_CO_MARKETING_AND_INTEGRATION_PARTNERSHIPS.md                            |
| Outbound Spokes:                                                                            |
| - Hub links to LangChain connector, LlamaIndex node parser, and TEDS table evaluation suite |
+---------------------------------------------------------------------------------------------+
| TOPIC CLUSTER 4: AIR-GAPPED ENTERPRISE SOVEREIGNTY (HUB: docs/marketing/10_SALES...)       |
+---------------------------------------------------------------------------------------------+
| Inbound Spokes:                                                                             |
| - docs/seo/local-ocr-vs-cloud-vision-cost-comparison.md                                     |
| - docs/marketing/08_GRAND_SLAM_OFFER_DESIGN.md                                              |
| - docs/marketing/09_PRICING_AND_PACKAGING_STRATEGY.md                                       |
| Outbound Spokes:                                                                            |
| - Hub links to security sandboxing jail, magic byte validator, and Docker Compose swarm     |
+---------------------------------------------------------------------------------------------+
```

---

## 📋 5. Page-Level Metadata & Schema.org Specification Matrix

| Page URI / Slug | Title Tag (< 60 chars) | Meta Description (< 155 chars) | Primary H1 | Target Schema.org Type |
|---|---|---|---|---|
| `/` (Root README) | B.L.A.S.T. OCR: Air-Gapped 29.1 pps Python Engine | High-throughput local OCR engine in Python. 29.1 pps on CPU, zero memory leaks, native MCP server, and structured Markdown table export. | B.L.A.S.T. Deterministic OCR Engine | `SoftwareApplication` |
| `/docs/BENCHMARKS_2026.md` | B.L.A.S.T. Benchmarks: 29.1 pps & Zero Memory Leaks | Verified 2026 empirical benchmarks: 29.1 pages/sec on CPU, 0.0002 MB/page memory slope, and 0.1916 CER on 128-page stress corpus. | Empirical Benchmark Scorecard 2026 | `Dataset`, `TechArticle` |
| `/docs/seo/high-throughput...` | High-Throughput PDF OCR in Python (29 Pages/Sec) | Learn how to achieve 29 pages/sec PDF OCR on CPU using vectorized SIMD preprocessing and dynamic aspect-ratio bucketing. | High-Throughput PDF OCR in Python | `HowTo`, `TechArticle` |
| `/docs/seo/mcp-server-ocr...` | Setup Document OCR MCP Server for Claude & Cursor | Connect B.L.A.S.T. OCR to Claude Desktop and Cursor using Model Context Protocol. Extract tables and formulas deterministically. | Document OCR MCP Server Setup Guide | `HowTo`, `TechArticle` |
| `/docs/seo/pdf-memory-leak...`| Prevent Memory Leaks in Python Batch OCR Pipelines | Eliminate out-of-memory container crashes in Python OCR. Sliding-window memory streaming and zero-leak engineering. | Preventing Memory Leaks in Batch OCR | `HowTo`, `TechArticle` |
| `/docs/marketing/09_PRICING...`| B.L.A.S.T. Enterprise Pricing & Deployment Licensing | Transparent enterprise pricing: Free Open Source Core, $199/mo Pro, $1,499/mo Unlimited Swarm with zero-crash SLA. | Enterprise Pricing & Packaging | `Product`, `Offer` |

---

## 🚫 6. Error Routing, Redirects & Canonicalization Rules

1. **Self-Referential Canonicals**: Every documentation page defines an explicit canonical URL in its metadata header to prevent duplicate content penalties across forks and mirrors.
2. **Permanent 301 Redirect Map**:
   - Deprecated `/benchmark` $\rightarrow$ `/docs/BENCHMARKS_2026.md`
   - Deprecated `/roadmap` $\rightarrow$ `/docs/STRATEGIC_ENHANCEMENT_PLAN.md`
   - Deprecated `/api-docs` $\rightarrow$ `/v1/docs`
3. **Structured 404 Experience**:
   - When a requested endpoint is not found, the server renders a helpful navigation hub linking directly to the Quickstart CLI command, Verified Benchmarks, and MCP Server setup guide.
