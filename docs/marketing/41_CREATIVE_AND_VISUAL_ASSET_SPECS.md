# Creative & Visual Asset Design Specifications: B.L.A.S.T. OCR

**Document Version**: 3.0.0  
**Design Philosophy**: Anti-Slop Sovereign Engineering — Dark Mode, Monospace Accents, High-Density Empirical Data, Precision SVG Geometry  
**Target Formats**: OpenGraph (1200x630), Twitter/X Card (1200x675), LinkedIn Feed (1080x1080 & 1200x627), Google Display Network (300x250, 728x90, 160x600)  

---

## 1. Brand Identity & Design System Tokens

B.L.A.S.T. visually communicates sovereign computational precision, speed, and privacy. The design language rejects generic corporate stock illustrations in favor of high-contrast terminal environments, raw code snippets, and real benchmark graphs.

### 1.1 Color Palette & Tokens
| Token Name | Hex Code | Role & Usage | Visual Meaning |
|---|:---:|---|---|
| `--bg-canvas` | `#0E1117` | Root canvas & background | Sovereign deep space, terminal environment |
| `--bg-surface` | `#161B22` | Card containers, modal boxes, code blocks | Elevated glass/matte surface |
| `--border-subtle` | `#30363D` | 1px subtle borders, dividers | Structural grid discipline |
| `--accent-cyan` | `#00F2FE` | Primary CTA, hero headings, active highlights | High-speed ONNX vector execution |
| `--accent-emerald` | `#10B981` | Success states, benchmark winners, passing tests | Zero memory leak, production certified |
| `--accent-amber` | `#F59E0B` | Terminal warnings, command line flags, cautions | Developer execution, terminal parameters |
| `--accent-crimson` | `#EF4444` | Competitor crashes, OOM errors, high costs | Memory leaks, cloud invoice shock |
| `--text-primary` | `#F0F6FC` | Primary headlines, bold labels | Crisp readability against dark canvas |
| `--text-muted` | `#8B949E` | Secondary captions, metadata, author labels | Low cognitive load supporting info |

### 1.2 Typography System
- **Display & Headlines**: `Inter`, `SF Pro Display`, `-apple-system`, `sans-serif` (Weights: 700 Bold, 800 Extra-Bold). Letter-spacing: `-0.02em`.
- **Code, Data & Benchmarks**: `JetBrains Mono`, `Fira Code`, `SF Mono`, `monospace` (Weights: 500 Medium, 700 Bold). Letter-spacing: `-0.01em`.
- **Body Copy**: `Inter`, `sans-serif` (Weight: 400 Regular, 500 Medium). Line-height: `1.6`.

---

## 2. Five High-Converting Ad Creative Visual Formats

Following `references/static-ad-templates.md` in the `ad-creative` skill:

### Creative Format 1: The Terminal Proof Card (1080x1080 & 1200x630)
- **Concept**: Emulates an authentic macOS/Linux terminal window with red/yellow/green window buttons, dark charcoal background, and live execution text.
- **Top Bar**: `bash - 80x24 • B.L.A.S.T. OCR Pipeline Supervisor`
- **Command Line**:
  ```bash
  $ python run.py 1000_page_archive.pdf --formats md,pdf --engine rapidocr
  ```
- **Live Output Area**:
  ```
  [INFO] Initializing Vectorized ONNX Engine (CUDA -> DirectML -> CPU)
  [INFO] Bounded Streaming Buffer Active (window_size=10 pages)
  [PROGRESS] [████████████████████████████████] 1000/1000 (100%)
  [METRICS] Throughput: 29.1 pages/sec | Elapsed: 34.3s
  [MEMORY] Peak RAM: 142.1 MB | Growth Slope: 0.0002 MB/page (PASS)
  [OUTPUT] Generated GFM Markdown & Dual-Layer Searchable PDF
  ```
- **Overlay Badge (Bottom Right)**: Neon green pill badge: `✔ ZERO MEMORY LEAKS CERTIFIED`.
- **Primary Hook**: "Tired of OCR pipelines crashing at 3:00 AM? Run B.L.A.S.T."

---

### Creative Format 2: The Split-Screen Before / After (1200x630 & 1080x1080)
- **Concept**: Side-by-side contrast demonstrating document structure reconstruction.
- **Left Side (The Input / The Pain)**:
  - Header: `SCANNED FINANCIAL REPORT (Before)`
  - Visual: Angled scan of a real printed income statement with coffee stain, skew, and complex nested grid lines.
  - Callout text with red arrow: `❌ Conventional OCR output: "Revenue 2024 14200 Net Income 2400 (Word Soup)"`
- **Right Side (The Output / The Value)**:
  - Header: `B.L.A.S.T. MORPHOLOGICAL EXTRACTION (After)`
  - Visual: Pristine GitHub Flavored Markdown table rendered in VS Code with syntax highlighting and LaTeX equation below.
  - Callout text with green arrow: `✔ Clean GFM Markdown table + LaTeX math formulas ($...$)`
- **Bottom Ribbon**: `100% Deterministic • 0% Generative Hallucination • Run Locally`

---

### Creative Format 3: The OOM Error Alert (1080x1080 Square)
- **Concept**: Plays on developer visceral pain — the dreaded out-of-memory crash.
- **Visual Center**: Red-bordered warning card styled like a terminal traceback:
  ```
  Traceback (most recent call last):
    File "pipeline.py", line 412, in process_batch
      output = torch_ocr_engine(page_tensors)
  torch.cuda.OutOfMemoryError: CUDA out of memory. Tried to allocate 2.40 GiB
  Process killed at page 842. Memory leak detected.
  ```
- **Contrasting Solution Banner**:
  - Electric blue badge: `NEVER AGAIN.`
  - Headline: "B.L.A.S.T. streams 1,000+ pages with a verified 0.0002 MB/page memory leak slope."
  - Metric callout: `142 MB Peak RAM Constant`.
- **CTA Button**: `pip install blast-ocr`

---

### Creative Format 4: The Cloud Invoice Shock (1200x630 Landscape)
- **Concept**: Highlights cloud OCR cost waste and lock-in.
- **Visual Left**: Cutout of a corporate cloud invoice:
  - `Cloud Document AI Extraction: $14,840.00`
  - Red stamp: `OVERPAYING`
- **Visual Right**: Clean laptop running B.L.A.S.T. OCR:
  - `B.L.A.S.T. OCR On-Premise: $0.00`
  - Green stamp: `100% FREE & OPEN SOURCE (MIT)`
- **Headline**: "Stop paying $0.05 per page to send confidential customer files to the cloud."
- **Subheadline**: "Run enterprise ONNX OCR locally on CPU & GPU with zero per-page fees."

---

### Creative Format 5: The Agentic RAG Blueprint (1200x630 & 16:9)
- **Concept**: Technical system architecture diagram illustrating LLM Agent tool execution.
- **Visual Flow**:
  - `Scanned Archive (.pdf, .pptx, .png)` →
  - `B.L.A.S.T. Core (RapidOCR ONNX + Table + Math)` →
  - `Native MCP Server (stdio / SSE)` →
  - `Claude Desktop / Cursor IDE / LangChain / LlamaIndex`
- **Key Callout Labels**:
  - `Hierarchy-Aware Chunks`
  - `Zero Generative Hallucination`
  - `Forensic PII Redacted`
- **Headline**: "The Missing Vision Layer for Local AI Agents."

---

## 3. Social OpenGraph (OG) 1200x630 Banner Specifications

The official repository OpenGraph banner (`og-image.png`) must render crisply across Slack, Discord, Twitter/X, and LinkedIn link previews:

- **Dimensions**: 1200 x 630 pixels (Aspect Ratio: 1.905:1).
- **Safe Zone**: 1100 x 550 pixels (keep all critical text 50px away from outer borders).
- **Background**: `#0E1117` with subtle SVG isometric grid lines in `#161B22`.
- **Top Left**: Logo mark — Electric Cyan Rocket (`#00F2FE`) + Monospace Brand Wordmark: `B.L.A.S.T. OCR`.
- **Center Headline (48px Inter Bold, White)**:
  `The Sovereign Document Intelligence Engine`
- **Center Subhead (24px Inter Regular, #8B949E)**:
  `Deterministic, High-Throughput ONNX OCR • Bounded Streaming Memory • Native MCP Agent`
- **Bottom Metric Triad**:
  - `29.1 pps CPU (7.7x vs EasyOCR)`
  - `0.0002 MB/page Leak Slope`
  - `0% Generative Hallucination`
- **Bottom Right**: GitHub Star Badge & MIT License mark.

---

## 4. Google Display Network (GDN) Responsive Specs

| Ad Size | Name | Primary Visual | Headline (30 ch) | Description (90 ch) |
|---|---|---|---|---|
| **300 x 250** | Medium Rectangle | Terminal window showing 29.1 pps metric | Private Offline OCR Engine | Extract tables & LaTeX math locally with zero cloud fees. 7.7x faster than EasyOCR. |
| **728 x 90** | Leaderboard | Logo + Split Before/After Table Preview | Fast, Private Document OCR | 100% offline ONNX OCR. Zero memory leaks on 1,000+ page archives. Try free live demo. |
| **160 x 600** | Wide Skyscraper | Vertical terminal log + 4 feature checkmarks | Stop Cloud OCR Bills | Run air-gapped document intelligence locally. Table extraction, math parsing, MCP native. |
| **320 x 50** | Mobile Leaderboard | Logo + Speed Badge | B.L.A.S.T. Local OCR | 100% private document OCR. 7.7x faster than EasyOCR. |
