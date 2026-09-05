# Analytics Tracking Plan & Measurement Architecture: B.L.A.S.T. OCR

**Document Version**: 3.0.0  
**Analytics Infrastructure**: PostHog (Product Analytics & Session Replay) + Google Analytics 4 (Acquisition)  
**Core Privacy Invariant**: 100% Zero-PII Ingestion Boundary — Never track document content, file names, or raw text  

---

## 1. Tracking Philosophy & Privacy Perimeter

B.L.A.S.T. is an air-gapped, privacy-centric document intelligence system. Our analytics tracking architecture strictly enforces:
1. **Zero Payload Logging**: Document contents, extracted strings, customer PII (names, SSNs, credit cards), and absolute filesystem paths are **never** captured in telemetry.
2. **Metadata-Only Telemetry**: We track operational performance metrics (page count, execution latency, memory growth slope, provider type, exit status) exclusively.
3. **Opt-Out by Default**: For local CLI and SDK executions, telemetry is completely disabled unless explicitly opted-in via `BLAST_OCR_TELEMETRY=1`.
4. **First-Party Routing**: When telemetry is enabled, events route to self-hosted PostHog or first-party reverse proxies to prevent third-party tracking cookies.

---

## 2. Core Conversion Funnels

We measure four mission-critical developer and commercial funnels:

```
Funnel 1: Developer Activation Funnel
Landing Page Visit ──► Docs Read (Quickstart) ──► SDK Install (`pip install`) ──► First Successful OCR (Time-to-Value < 45s)

Funnel 2: Power User Retention Funnel
First OCR ──► Batch Ingestion (> 50 pages) ──► Streaming Window Execution ──► Multi-Format Export (Markdown + PDF)

Funnel 3: AI Agent Integration Funnel
MCP Server Docs ──► `mcp.json` Configured ──► Tool Invocation (`blast_ocr_process`) ──► LangChain/LlamaIndex Connector

Funnel 4: Enterprise Pipeline Funnel
Cloud OCR Calculator ──► Enterprise Pitch Deck ──► RFP Form Submission ──► MQL Handoff to Sales Engineering
```

---

## 3. Exhaustive Event Tracking Matrix

| Event Name | Category | Trigger / User Action | Event Properties & Types | Sample Value |
|---|---|---|---|---|
| `page_viewed` | Navigation | User loads any documentation or UI surface | `path` (str), `referrer` (str), `utm_source` (str), `utm_campaign` (str) | `{path: "/docs/BENCHMARKS_2026.md", utm_source: "github"}` |
| `quickstart_code_copied` | Engagement | User clicks "Copy" button on SDK code block | `code_type` (str: `cli`, `sdk`, `docker`, `mcp`), `surface` (str) | `{code_type: "sdk", surface: "github_readme"}` |
| `demo_file_uploaded` | Activation | User drops a document into the Streamlit UI | `file_extension` (str: `pdf`, `png`, `pptx`), `file_size_kb` (int) | `{file_extension: "pdf", file_size_kb: 2450}` |
| `ocr_execution_started` | Core Engine | Document processing pipeline begins | `engine` (str), `provider` (str: `cuda`, `cpu`), `formats` (arr), `batch_size` (int) | `{engine: "rapidocr", provider: "CPU", batch_size: 16}` |
| `ocr_execution_completed`| Core Engine | Pipeline successfully exports results | `page_count` (int), `duration_sec` (float), `pages_per_sec` (float), `peak_ram_mb` (float) | `{page_count: 120, pages_per_sec: 29.1, peak_ram_mb: 142.1}` |
| `ocr_execution_failed` | Core Engine | Pipeline encounters a fatal error | `error_type` (str: `CorruptedDocument`, `OOM`), `page_failed` (int), `engine` (str) | `{error_type: "CorruptedDocumentError", page_failed: 4}` |
| `table_extracted` | Feature | TableExtractor successfully detects grid | `table_count` (int), `avg_rows` (int), `avg_cols` (int), `format` (str: `gfm`, `html`) | `{table_count: 3, avg_rows: 12, format: "gfm"}` |
| `formula_extracted` | Feature | LaTeX parser detects equations | `formula_count` (int), `has_display_math` (bool) | `{formula_count: 8, has_display_math: true}` |
| `pii_masked` | Security | Redaction filter masks sensitive strings | `masked_types` (arr: `ssn`, `email`, `credit_card`), `mask_count` (int) | `{masked_types: ["ssn", "email"], mask_count: 14}` |
| `mcp_tool_invoked` | AI Agent | Claude/Cursor calls an MCP stdio tool | `tool_name` (str), `agent_client` (str: `claude`, `cursor`, `antigravity`) | `{tool_name: "blast_ocr_process", agent_client: "cursor"}` |
| `calculator_completed` | Acquisition | User runs Cloud OCR vs Local Calculator | `monthly_pages` (int), `cloud_cost_est` (float), `local_savings` (float) | `{monthly_pages: 500000, local_savings: 14800.0}` |
| `sales_contact_submitted`| Commercial | Enterprise fills out RFP or sales form | `company_size` (str), `use_case` (str), `lead_score` (int) | `{company_size: "250-1000", use_case: "legal_rag", lead_score: 85}` |

---

## 4. UTM Campaign Naming Conventions

All outbound campaigns, social links, newsletters, and partner directories must follow strict UTM syntax:

```
utm_source   = Platform / Channel (e.g. "github", "twitter", "linkedin", "reddit", "producthunt", "newsletter")
utm_medium   = Placement Type (e.g. "readme", "social_thread", "cpc_search", "abm_ad", "tla_sponsor", "directory")
utm_campaign = Campaign Name (e.g. "v3_launch", "cloud_cost_alternatives", "rag_developer_outreach")
utm_content  = Creative / Ad Variant (e.g. "terminal_proof_card", "split_table_before_after", "cta_demo")
```

### Example Canonical URLs:
- `https://github.com/Ibrahim-Salman19/OCR?utm_source=twitter&utm_medium=social_thread&utm_campaign=engine_bakeoff&utm_content=rapidocr_cer`
- `https://ocr-book.streamlit.app/?utm_source=linkedin&utm_medium=tla_sponsor&utm_campaign=v3_launch&utm_content=founder_post`

---

## 5. Implementation Architecture & Code Snippets

### 5.1 Python Server-Side Tracking (PostHog)
For opt-in self-hosted server metrics without frontend cookies:

```python
import os
import posthog

POSTHOG_API_KEY = os.getenv("BLAST_OCR_POSTHOG_KEY")
TELEMETRY_ENABLED = os.getenv("BLAST_OCR_TELEMETRY", "0") == "1"

if TELEMETRY_ENABLED and POSTHOG_API_KEY:
    posthog.api_key = POSTHOG_API_KEY
    posthog.host = "https://telemetry.blast-ocr.dev"

def track_ocr_completed(session_id: str, page_count: int, duration_sec: float, peak_ram_mb: float):
    if not TELEMETRY_ENABLED:
        return
    posthog.capture(
        distinct_id=session_id,
        event="ocr_execution_completed",
        properties={
            "page_count": page_count,
            "duration_seconds": round(duration_sec, 2),
            "pages_per_second": round(page_count / max(duration_sec, 0.001), 2),
            "peak_ram_mb": round(peak_ram_mb, 1),
            "engine": "rapidocr_onnx",
        }
    )
```

### 5.2 Frontend Streamlit Event Tracking (Zero-Cookie Safe GA4 Hook)
```javascript
// Embedded safe analytics payload for Streamlit web app
function trackDemoEvent(eventName, properties) {
  if (window.gtag) {
    window.gtag(event, eventName, {
      event_category: DemoUI,
      ...properties,
      anonymize_ip: true,
      allow_google_signals: false
    });
  }
}
```
