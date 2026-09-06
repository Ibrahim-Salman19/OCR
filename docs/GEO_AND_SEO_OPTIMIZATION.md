# 🌐 B.L.A.S.T. OCR — GEO, AEO & SEO Implementation Status

> Tracks the implementation of Search Engine Optimization (SEO), Generative Engine Optimization (GEO), and Answer Engine Optimization (AEO) across all B.L.A.S.T. OCR surfaces.
> **Last Verified & Certified:** September 2026 (Milestone 16+)

---

## 1. Canonical URLs & Surface Mapping

The project operates across three canonical live surfaces:
- **Source & Documentation**: `https://github.com/Ibrahim-Salman19/OCR` (Public Repository)
- **Static Marketing & Machine-Readable Surface**: `https://ibrahim-salman19.github.io/OCR/` (GitHub Pages, added 2026-09-06). This is a plain static `index.html` with real server-rendered `<head>` metadata and JSON-LD — no JavaScript required to read it — and, because Pages serves the whole repository root, it's also the first real HTTP endpoint for `robots.txt`, `sitemap.xml`, `llms.txt`, `llms-full.txt`, `mcp.json`, and `pricing.md`. Before this, none of those files were reachable at any URL the project actually claimed; they existed only as repo files or via `raw.githubusercontent.com`.
- **Live Demo & Operations Console**: `https://ocr-book.streamlit.app/` (Streamlit Community Cloud) — the interactive OCR pipeline. Linked from the Pages site; not the surface to point a crawler at for machine-readable content (see §5).

Every machine-readable file in this repo (`llms.txt`, `llms-full.txt`, `sitemap.xml`, `robots.txt`, `mcp.json`, `.well-known/ai-plugin.json`, `.agents/product-marketing.md`) is now reachable at `ibrahim-salman19.github.io/OCR/...` (real web root, static, no JS), and continues to also resolve at `raw.githubusercontent.com/Ibrahim-Salman19/OCR/main/...` for direct bot fetching and `github.com/Ibrahim-Salman19/OCR/blob/main/...` for human-facing documentation links.

---

## 2. Structured Data (Schema.org JSON-LD Graph)

A Schema.org `@graph` is maintained across three surfaces, but they carry different real-world
weight and it's worth being precise about which:

1. **GitHub README.md**: The JSON-LD is wrapped in an HTML comment (`<!-- {...} -->`), because
   GitHub's markdown sanitizer strips a literal `<script>` tag from any rendered README. That
   means this block is **inert for traditional structured-data parsers** — Google's Rich Results
   parser and any schema.org validator look for `<script type="application/ld+json">` elements in
   the rendered DOM, and an HTML comment is invisible to that scan. What it *is* good for: any
   LLM or agent that fetches the raw markdown (`raw.githubusercontent.com/.../README.md`) reads
   plain text, where comment syntax carries no special meaning — so the JSON is fully legible
   there. Treat this layer as a GEO/LLM-ingestion aid, not an SEO rich-result source.
2. **Streamlit Web UI (`blast_ocr/ui/web_app.py`)**: Verified with a real Playwright DOM check
   (not just a string-presence assertion) on 2026-09-06. Two facts, both confirmed empirically:
   - The raw, pre-JavaScript HTTP response is an 891-byte empty shell containing none of this
     content. Any crawler that doesn't execute JavaScript (GPTBot, ClaudeBot, PerplexityBot,
     CCBot, and social link-preview bots like Facebook/Twitter/LinkedIn/Slack) sees nothing here,
     full stop — this is a structural limitation of Streamlit Community Cloud, not a bug in this
     file, and it isn't fixable without a server-rendered surface in front of the SPA.
   - For crawlers that *do* execute JavaScript (Googlebot, Bingbot), `st.markdown(...,
     unsafe_allow_html=True)` only ever placed these tags inside the app body — never `<head>`.
     Google explicitly ignores a `rel="canonical"` link found outside `<head>`. This has now been
     fixed: `_inject_head_tags()` runs inside a Streamlit component iframe (which Streamlit grants
     same-origin access to the parent window) and relocates the canonical link, meta description,
     robots directive, and Open Graph/Twitter Card tags — including a newly added `og:image` — into
     the real `document.head`, confirmed by `tests/test_playwright_landing_and_nav.py::test_landing_page_seo_tags_land_in_real_head`,
     which asserts on the live rendered DOM rather than mocking the call. The JSON-LD `@graph`
     itself was left in the body, since Google's own documentation accepts JSON-LD in either
     `<head>` or `<body>`.
3. **Enterprise REST API (`blast_ocr/api/app.py`)**: Served at `/v1/schema.json` with standard
   `application/ld+json` serialization — functionally correct, but only reachable once this API is
   deployed to a public domain; per `.well-known/ai-plugin.json`, it currently is not.

### Implemented Schema Entities:
- `SoftwareApplication`: Defines name, alternateName, description, operatingSystem, applicationCategory, downloadUrl, installUrl, license, free price offer ($0 USD), and complete 9-point feature list.
- `SoftwareSourceCode`: Declares Python 3.9–3.13 runtime platform, code repository, and MIT license.
- `TechArticle`: Documents architectural overview, reproducible benchmarks, and integration guides with targeted technical keywords.
- `FAQPage`: Q&A targeting the top 8 high-volume user and AI assistant queries (speed, memory leaks, table extraction, MCP setup, sandwich PDFs, anti-hallucination, air-gapped security, PII redaction). As of 2026-09-06 all three surfaces (README.md, Streamlit UI, FastAPI `/v1/schema.json`) carry the same 8 questions — previously the README had 8 while the two live/API surfaces only had 5, a real drift now closed. Note: Google restricted FAQ *rich results* to well-known government/health sites in August 2023, so this project won't get the SERP accordion — the value here is GEO/AI-answer-engine extraction (Perplexity, Bing Copilot, ChatGPT Search), not a Google rich snippet. See `docs/marketing/16_SCHEMA_MARKUP_VALIDATION.md` §3.
- `HowTo`: Structured 3-step guide for PDF-to-Markdown document processing. Note: Google discontinued HowTo rich results entirely in August 2023; same GEO-only caveat as `FAQPage`.
- `Organization`: An inline `publisher` object nested inside `TechArticle` — not a standalone top-level entity with its own `@id`, so nothing elsewhere can reference it directly.
- `Dataset`: Describes the 14-page Gold Standard Evaluation Corpus with ground truth text, table geometries, reading order, and CER baselines. Present in the FastAPI `/v1/schema.json` graph and, as of 2026-09-06, the Streamlit UI graph (previously missing there — the two live graphs had drifted out of sync).

---

## 3. Generative Engine Optimization (GEO) & AEO Implementation

AI models (Perplexity, ChatGPT, Claude, Gemini, Copilot) prioritize content that exhibits high direct-answer density, verified statistics, clean tabular comparisons, and quotable definitions.

### Key Enhancements:
1. **Self-Contained 40–60 Word Direct Answer Blocks**: Every major H2 and H3 section begins with a direct, comprehensive answer before presenting nuance or code.
2. **Query Fan-Out Coverage**: Content directly targets the semantic query fan-out cluster:
   - *"What is B.L.A.S.T. OCR?"*
   - *"Why is B.L.A.S.T. faster than EasyOCR?"*
   - *"How does B.L.A.S.T. prevent memory leaks on massive PDFs?"*
   - *"How does B.L.A.S.T. extract tables and formulas for RAG?"*
   - *"How do I connect B.L.A.S.T. to Claude Desktop or Cursor via MCP?"*
   - *"How does B.L.A.S.T. guarantee zero generative hallucination?"*
   - *"Does B.L.A.S.T. run offline without cloud telemetry?"*
3. **Head-to-Head Competitor Matrices**: Comprehensive tabular comparisons against IBM Docling, Marker 2, Surya, EasyOCR, Tesseract, and AWS Textract covering compute profiles, licensing (MIT vs GPL/OpenRAIL-M), and memory architectures.
4. **Product Marketing Alignment**: Seamlessly integrated with `.agents/product-marketing.md` to ensure consistent ICP definitions, persona value propositions, and customer vocabulary.

---

## 4. Machine-Readable Agent Protocols

1. **`llms.txt` (llmstxt.org v2 Standard)**: Curated Markdown roadmap linking core guides with intent-driven summaries.
2. **`llms-full.txt` (Open Knowledge Format / Unified Spec)**: Single-prompt full context specification containing complete Python SDK, CLI, MCP Server, REST API, LangChain, and LlamaIndex recipes.
3. **`mcp.json` & `blast_ocr/mcp_server.py`**: Native Model Context Protocol (MCP) server exposing `blast_ocr_process`, `blast_ocr_extract_tables`, `blast_ocr_extract_formulas`, and `blast_ocr_semantic_chunk`.
4. **`.well-known/ai-plugin.json`**: OpenAPI action manifest for ChatGPT and OpenAI custom GPTs.
5. **Discovery Headers**: FastAPI automatically emits `X-Agent-Discoverable: true`, `X-Robots-Tag: all, index, follow`, `X-Model-Context-Protocol: /mcp.json`, and `Link: </llms.txt>; rel="describedby"`.

---

## 5. Crawlability & Indexation Infrastructure

- **`robots.txt`**: Unconditionally welcomes 18 distinct AI search and agent crawlers (`OAI-SearchBot`, `GPTBot`, `ChatGPT-User`, `PerplexityBot`, `Claude-SearchBot`, `ClaudeBot`, `Claude-Web`, `Anthropic-AI`, `Google-Extended`, `GoogleOther`, `Applebot-Extended`, `Amazonbot`, `Meta-ExternalAgent`, `MistralBot`, `Cohere-ai`, `Diffbot`, `CCBot`, `Bytespider`, `DuckAssistBot`).
- **`sitemap.xml`**: 126 `<loc>` entries (verified by parsing with `xml.etree.ElementTree` on 2026-09-06; 5 of them the new GitHub Pages surface, 116 of the remaining 121 are `github.com/.../blob/main/...` URLs — confirmed against the live `github.com/robots.txt` on 2026-09-06 that `/blob/` paths are not disallowed for the general crawler group), spanning all core surfaces, machine-readable protocol files, technical documentation guides, and Architectural Decision Records (ADRs).
- **Streamlit SPA crawlability — mitigated, not fully open**: `https://ocr-book.streamlit.app/` is a client-rendered single-page app — its raw HTTP response (891 bytes, verified 2026-09-06) contains no meta tags, no schema, and none of the content described in §2 until the JS bundle executes. Search/AI crawlers that don't run JavaScript (GPTBot, ClaudeBot, PerplexityBot, CCBot, Bytespider, and social unfurl bots) still see nothing on this specific surface, regardless of what `web_app.py` injects — that's a Streamlit Community Cloud hosting constraint, not something fixable from application code. As of 2026-09-06 this no longer matters as much as it did: `https://ibrahim-salman19.github.io/OCR/` (§1) is a genuine static page those same crawlers can read in full, and is the URL `robots.txt`'s `Sitemap:` directive and this project's outbound links now point to first.
- **Auditing methodology note**: `curl`/`web_fetch` against the Streamlit surface cannot detect JS-injected content at all — it will either falsely report "no schema found" (content is there, just not in the raw response) or, if someone assumes the JS-rendered DOM matches what a non-JS crawler sees, falsely conclude the schema/meta tags are working for every crawler type. Any future audit of this surface needs an actual JS-rendering check (Google's Rich Results Test, or a Playwright DOM query as used in `tests/test_playwright_landing_and_nav.py::test_landing_page_seo_tags_land_in_real_head`) — this is how the `<head>`-placement bug in §2 was found and confirmed fixed, after two prior audit passes (`docs/marketing/13_TECHNICAL_SEO_AUDIT.md`, this file's earlier versions) missed it by inspecting only the source text of `web_app.py`.

---

## 6. Empirical Proof Discipline & Testing Gates

All published metrics are strictly grounded in reproducible in-repo eval runs:
- **Test Suite Status**: Certified 737 passing tests (735 passed, 2 skipped, 0 failed).
- **Playwright Suite**: 71/71 passing browser end-to-end automation tests.
- **Evaluation Scenarios**: 24/24 evaluation scenarios verified in `eval/run_playwright_suite.py`.
- **Code Quality**: 100% clean Ruff linting (`ruff check .` with 0 errors across 187 repository files).
- **Security Audit**: 0 Bandit security vulnerabilities.
- **CER Reduction**: 0.1916 CER on 14-page gold corpus (18% CER reduction vs EasyOCR 0.2338).
- **Latency Advantage**: 15.3s/page on CPU vs 117.8s with EasyOCR (7.7x faster).
- **Zero-Leak Memory Gate**: 0.0002 MB/page growth slope over 1,000 continuous streamed pages ($\le 0.005\text{ MB/page}$ threshold).
