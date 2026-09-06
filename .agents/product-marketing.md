# Product Marketing Context

**Document version:** v1
**Last updated:** 2026-09-06

## Product Overview
**One-liner:** Enterprise, self-hosted, deterministic document intelligence and OCR engine for high-throughput batch execution and Agentic RAG pipelines.
**What it does:** B.L.A.S.T. OCR transforms multi-page PDFs, PowerPoint (PPTX) decks, and scanned images into structured GitHub Flavored Markdown, selectable dual-layer sandwich PDFs, styled DOCX, EPUB 3.0, and layout JSON. Powered by ONNX Runtime multi-provider acceleration (CUDA → DirectML → CPU) and a sliding-window bounded-memory streaming architecture, it delivers reproducible accuracy with zero generative hallucination. It features native AI Agent protocols including a built-in Model Context Protocol (MCP) server, `llms.txt` standard discovery, and LangChain/LlamaIndex document loaders.
**Product category:** Document Intelligence & Optical Character Recognition (OCR) / Local AI Developer Tools & Agentic RAG Ingestion
**Product type:** Open-source Python Engine, Developer CLI, Headless REST API (FastAPI), Native MCP Server, and Streamlit Mission Control Web Application
**Business model:** 100% Permissive Open-Source (MIT License) with on-premise self-hosting and enterprise workflow integration; zero per-page cloud API fees.

## Target Audience
**Target companies:** AI/ML Engineering teams, Legal Tech firms, Financial Services & Compliance, Archival/Publishing Institutions, Healthcare/Life Sciences, Academic Research labs handling large legacy PDF/PPTX corpora.
**Decision-makers:** Head of AI/ML, Lead AI Engineer, VP of Engineering, CTO, Senior Data Platform Architect, Security & Compliance Officer.
**Primary use case:** Ingesting high-volume, multi-format document archives (1,000+ pages) into structured RAG pipelines and searchable databases without memory leaks, cloud API bills, or data privacy risks.
**Jobs to be done:**
- Convert legacy scanned books, research papers, and technical slide decks into clean, hierarchically tagged Markdown for LLM chunking and vector embeddings.
- Produce 100% private, compliant searchable sandwich PDFs with pixel-accurate text bounding boxes and 8-class forensic PII redaction.
- Run continuous, distributed batch document processing on local hardware or GPU clusters without crashes, memory bloat, or cloud API cost scaling.
**Use cases:**
- Agentic RAG document preprocessing with hierarchy-aware semantic chunking and formula preservation.
- Legal contract & financial report discovery with table extraction scored via TEDS.
- Large-scale book and academic paper digitization to EPUB 3.0 and DOCX.
- Batch conversion of heterogeneous multi-format archives (PDF, PPTX, PNG, JPG, TXT) via distributed worker swarm.

## Personas
| Persona | Cares about | Challenge | Value we promise |
|---|---|---|---|
| AI / RAG Engineer (User & Champion) | Markdown output fidelity, token efficiency, hierarchy preservation, MCP integration, vector embeddings | Scanned documents produce unstructured "word soup", broken tables, hallucinated math, and bloated token counts | High-fidelity Markdown with preserved LaTeX formulas ($...$, $$...$$), GitHub Flavored Markdown tables, and native LangChain/LlamaIndex readers |
| Platform / Backend Engineer (Technical Influencer) | Memory stability, CPU/GPU latency, horizontal scaling, Docker deployment, queue resiliency | Python OCR engines (PyTorch, EasyOCR, Tesseract) suffer from fatal memory leaks, SIGSEGV crashes, and 100s/page latency | ONNX Runtime multi-provider fallback (7.7x faster than EasyOCR), 0.0002 MB/page streaming leak slope, 3-tier Redis priority queue, zombie reaper, and DLQ failover |
| VP of Engineering / CTO (Decision Maker) | Development velocity, infrastructure compute costs, deterministic reliability, open-source license compliance | Cloud OCR APIs (AWS Textract, Google Document AI) create massive monthly recurring cloud bills ($1.50–$50 per 1k pages) and vendor lock-in | 100% MIT-licensed, completely self-hosted, zero per-page fees, reproducible benchmarks |
| Security & Compliance Officer (Financial/Risk Buyer) | Data sovereignty, zero cloud telemetry, GDPR/HIPAA compliance, PII protection | Sending confidential client contracts, patient records, or financial disclosures to third-party cloud APIs violates compliance | 100% offline, local execution with zero network transit, strict sandboxing against path traversal/XXE/decompression bombs, and automated forensic PII redaction |

## Problems & Pain Points
**Core problem:** Traditional OCR tools either crash under enterprise production volume due to unbounded memory leaks, produce unstructured "word soup" that breaks downstream LLMs, or require sending sensitive data to expensive cloud APIs with per-page pricing.
**Why alternatives fall short:**
- Tesseract: Obsolete layout analysis, terrible reading order on multi-column layouts, fails on tables/math, high CER (0.4992).
- EasyOCR: PyTorch memory fragmentation, slow CPU latency (~117.8s/page), lacks native document structure or PDF sandwich output.
- Marker/olmOCR: Marker's GPL-3.0 + OpenRAIL-M license restricts commercial SaaS usage and requires heavy multi-gigabyte VRAM GPUs; olmOCR (VLM-first) suffers from generative hallucinations and slow autoregressive decoding.
- AWS Textract / Google Document AI: Proprietary cloud lock-in, data transit security risks, prohibitive costs at scale ($1,500–$50,000 per million pages).
**What it costs them:**
- Engineering time spent debugging worker OOM crashes and writing glue code for layout parsing.
- Tens to hundreds of thousands of dollars in recurring cloud OCR vendor invoices.
- Downstream RAG failure caused by scrambled reading order and garbled table figures.
**Emotional tension:** Anxiety over OOM crashes taking down production worker nodes at 2 AM; fear of regulatory fines from leaking unredacted PII to cloud LLMs; frustration with black-box cloud OCR accuracy.

## Competitive Landscape
**Direct:** IBM Docling — falls short because of lower raw text accuracy on complex scanned pages and heavier runtime dependencies compared to B.L.A.S.T.'s lightweight ONNX engine; lacks native MCP stdio/SSE server.
**Direct:** Marker 2 (Datalab) — falls short because dual GPL-3.0 + OpenRAIL-M licensing restricts commercial scale and enforces revenue caps, and it requires heavy GPU/VRAM hardware.
**Secondary:** Generative VLMs (olmOCR, PaddleOCR-VL, Qwen2.5-VL) — fall short because autoregressive image-to-text models can hallucinate characters, numbers, and clauses in high-stakes financial/legal docs, and demand high GPU compute.
**Indirect:** AWS Textract & Google Document AI — fall short because cloud SaaS pricing ($1.50–$50 per 1k pages) becomes exorbitant at scale, and mandates transmitting confidential client documents to external clouds.

## Differentiation
**Key differentiators:**
- Bounded Streaming Memory Architecture: Measured 0.0002 MB/page growth slope over 1,000 pages — immune to memory leaks.
- True Determinism & Anti-Hallucination: Pure OCR and morphological parsing ensures 0% generative hallucination in legal and financial contexts.
- Multi-Provider ONNX Acceleration: Automatic CUDA → DirectML → CPU fallback hierarchy delivering 7.7x faster execution than PyTorch baselines.
- Native Dual-Layer Searchable PDF: PyMuPDF-based coordinate bounding box alignment creates instant OCR text search over original scans.
- Native Agentic Protocols: Built-in Model Context Protocol (MCP) server, `llms.txt`, and LangChain/LlamaIndex reader connectors.
- 100% Permissive MIT License: Zero commercial restrictions, no revenue caps, no dual-licensing traps.
**How we do it differently:** We separate high-level orchestration from low-level pixel manipulation using a 3-Layer A.N.T. (Architect, Navigator, Tool) design pattern, executing batched ONNX tensor inference with sliding-window page chunking, SIMD preprocessing, and morphological structure recovery.
**Why that's better:** It eliminates memory leaks, runs on standard commodity CPU instances without requiring expensive GPUs, processes 1,000+ page books seamlessly, and preserves full document structure for LLMs.
**Why customers choose us:** It runs 100% offline, never OOMs on massive documents, outputs clean Markdown ready for RAG, provides an instant native MCP interface for AI agents, and costs $0 in cloud API fees.

## Objections
| Objection | Response |
|---|---|
| "Does it require expensive NVIDIA GPUs to run fast?" | No. B.L.A.S.T. runs efficiently on standard CPUs (15.3s/page) using ONNX Runtime with SIMD optimizations, while seamlessly auto-accelerating with CUDA or DirectML if a GPU is available. |
| "Why not just use an end-to-end VLM like GPT-4o or olmOCR?" | VLMs hallucinate facts, numbers, and dates, and cost orders of magnitude more compute/money. B.L.A.S.T. is 100% deterministic and anti-hallucinatory, critical for legal, financial, and compliance workflows. |
| "Can it handle 1,000+ page book scans or massive PDF archives?" | Yes. The sliding-window streaming pipeline was verified across a 1,000-page stress test with a memory growth slope of only 0.0002 MB/page (well below the 0.005 MB/page zero-leak threshold). |
| "Is our data private and compliant?" | Yes. B.L.A.S.T. runs 100% offline with zero outbound network calls, telemetry, or third-party cloud dependencies, and includes automated 8-class forensic PII redaction. |

**Anti-persona:** Casual consumers looking for a quick mobile phone camera scanner app; or non-technical organizations wanting a fully managed SaaS cloud dashboard who do not wish to run any Python/Docker infrastructure locally.

## Switching Dynamics
**Push:** Production worker crashes from PyTorch/EasyOCR memory leaks; mounting AWS Textract invoices; compliance blocks on cloud data transit.
**Pull:** Self-hosted MIT license; 7.7x latency reduction; bounded memory guarantee; native Markdown and MCP tooling for AI agents.
**Habit:** Legacy Tesseract bash scripts; established AWS CloudWatch / Textract infrastructure.
**Anxiety:** Migration effort; question of whether CPU accuracy matches cloud neural vision.

## Customer Language
**How they describe the problem:**
- "Our worker pods keep getting OOM-killed when processing 500-page legal filings."
- "EasyOCR is taking 2 minutes per page and locking up the CPU."
- "Downstream RAG is hallucinating because the OCR output scrambles table columns and drops equations."
- "AWS Textract bill was $12,000 last month just for basic document parsing."
**How they describe us:**
- "A rock-solid local OCR engine that doesn't leak memory."
- "The fastest way to turn legacy PDFs into clean Markdown for LangChain."
- "Drop-in offline replacement for cloud OCR with zero hallucination."
**Words to use:** Deterministic, Bounded-memory streaming, ONNX Runtime multi-provider, High-throughput batching, Agentic RAG ready, Searchable sandwich PDF, Zero-hallucination, Self-hosted, MIT-licensed.
**Words to avoid:** Generative OCR, Cloud-dependent, AI wrapper, Proprietary, Heuristic guess, Untested.
**Glossary:**
| Term | Meaning |
|---|---|
| B.L.A.S.T. | Blueprint, Link, Architect, Stylize, Trigger protocol — deterministic engineering architecture. |
| Sandwich PDF | A dual-layer PDF containing the original scanned image with an invisible, selectable, searchable OCR text layer positioned precisely underneath. |
| CER (Character Error Rate) | Levenshtein distance normalized by reference text length; the primary academic and industrial metric for OCR accuracy. |
| TEDS | Tree-Edit-Distance-based Similarity metric for evaluating table structure extraction accuracy. |
| MCP | Model Context Protocol — open standard by Anthropic connecting AI assistants and agents to local tools and resources. |
| Zero-Leak Gate | CI/stress gate requiring memory growth slope to remain $\le 0.005\text{ MB/page}$ over 1,000 streamed pages. |

## Brand Voice
**Tone:** Authoritative, engineering-grade, rigorously empirical, transparent about trade-offs.
**Style:** Direct, technical, benchmark-backed, code-first.
**Personality:** Deterministic, robust, sovereign, performance-obsessed.

## Proof Points
**Metrics:**
- 18% CER reduction (0.2338 → 0.1916) on 14-page gold corpus vs EasyOCR.
- 7.7x faster per-page CPU latency (117.8s → 15.3s).
- 0.9758 Kendall's Tau reading order.
- 0.0002 MB/page memory growth slope over 1,000-page continuous streaming stress test (zero-leak gate passed).
- 914 tests: 912 passed, 2 skipped, 0 failed, with 100% clean Ruff linting (verified 2026-09-06 by actual execution, after fixing an 8-day CI outage -- see docs/GEO_AND_SEO_OPTIMIZATION.md).
- 70/70 Playwright browser end-to-end tests passing.
**Customers:**
- Enterprise data engineering pipelines, sovereign offline document intelligence, RAG vector indexing systems.
**Testimonials:** None yet. This project has no verified customer or user testimonials as of
2026-09-06 -- it is pre-launch open-source software with no evidence of enterprise adoption. A
line here previously read like a real attributed quote ("— Data Platform Lead") with no name,
company, or source; that was never a real testimonial and has been removed rather than left to be
copied into public-facing copy as if it were one. If an illustrative target-persona quote is
useful for messaging testing, label it explicitly as hypothetical (e.g. "Illustrative target quote
(not a real customer)") rather than formatting it identically to a genuine testimonial.
**Value themes:**
| Theme | Proof |
|---|---|
| Deterministic Memory Stability | 1,000-page stress test leak slope 0.0002 MB/page (`eval/results/stress_report.json`), zero open file descriptor leaks. |
| High Throughput & Low Latency | 15.3s/page on CPU with RapidOCR ONNX vs 117.8s with EasyOCR; multi-provider ONNX fallback (`CUDA` → `DirectML` → `CPU`). |
| Production Hardening | 914 tests (912 passed, 2 skipped, 0 failed), automated zombie reaper & DLQ retry supervisor, 8-class PII redaction, 70/70 Playwright tests. |

## Goals
**Business goal:** Establish B.L.A.S.T. OCR as the gold-standard, self-hosted document intelligence engine for Agentic RAG and enterprise document workflows.
**Conversion action:** GitHub star/fork, `pip install blast-ocr`, integrate via MCP or Python SDK, deploy Docker swarm.
**Current metrics:** 912/914 tests passed (2 skipped, 0 failed), 0.1916 CER on gold standard corpus.

## Creator & Engineering Authority
**Author & Lead Architect:** [Ibrahim Salman](https://ibrahimsalman.vercel.app)  
**Engineering Provenance:** Full-Stack Software Engineer & AI Systems Architect, alumnus of [University of Engineering and Technology (UET), Taxila](https://uettaxila.edu.pk/) (Wikidata: [Q10854449](https://www.wikidata.org/wiki/Q10854449)).  
**Standard O*NET Occupations:** 15-1252.00 (Software Developers), 15-1299.08 (Computer Systems Engineers/Architects).  
**Portfolio & Technical Writeups:** [https://ibrahimsalman.vercel.app](https://ibrahimsalman.vercel.app)  
**B.L.A.S.T. Production Case Study:** [https://ibrahimsalman.vercel.app/projects/blast](https://ibrahimsalman.vercel.app/projects/blast)  
**Live Production Systems:**  
- [UET GPT](https://uet-gpt.vercel.app): Full-stack production AI assistant (Next.js 15, TypeScript, Convex, Clerk, Vercel AI SDK).  
- [B.L.A.S.T. Mission Control](https://ocr-book.streamlit.app/): Self-hosted document intelligence web app with SVG heatmaps and batch processing.  
- Production Marketplace Monitoring: Multi-source event-driven pipeline backed by 299 unit tests across 4 Python versions.  
**LinkedIn:** [https://www.linkedin.com/in/ibrahim-salman-dev/](https://www.linkedin.com/in/ibrahim-salman-dev/)  
**GitHub:** [https://github.com/Ibrahim-Salman19](https://github.com/Ibrahim-Salman19)  
**Upwork Enterprise Profile:** [Upwork Verified Specialist](https://www.upwork.com/freelancers/~013e1c54e9a3f7a2b8)  
**Direct Contact & Consulting:** [ibrahim.pk848@gmail.com](mailto:ibrahim.pk848@gmail.com) • [Contact Portal](https://ibrahimsalman.vercel.app/contact)  
**Engineering Philosophy:** *"Make it work. Prove it works. Make it survive production."*

## Changelog
*Newest first. One line per revision: what changed and why.*
- v1.1 (2026-09-06) — Added Creator & Engineering Authority with verified portfolio and provenance links for Google E-E-A-T and AI entity disambiguation.
- v1.0 (2026-09-06) — Initial context.
