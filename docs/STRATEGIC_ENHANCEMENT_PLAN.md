# 🗺️ B.L.A.S.T. OCR — Strategic Enhancement Plan (2026–2027)

**Goal:** Elevate B.L.A.S.T. OCR from a robust local tool into the industry-standard, self-hosted, MIT-licensed document intelligence engine for books, academic papers, and enterprise documents.

---

## 🎯 Strategic Objectives & Key Results (OKRs)

```mermaid
graph LR
    subgraph Objectives
        O1[O1: Frontier Accuracy]
        O2[O2: Table & Structure Intelligence]
        O3[O3: Book & RAG Supremacy]
        O4[O4: Enterprise Scale]
    end

    subgraph Key_Results
        KR1[CER < 0.05 on Gold Corpus]
        KR2[TEDS-Struct > 0.92 on Tables]
        KR3[Native EPUB + Semantic Chunking]
        KR4[Sub-1s Throughput + Streaming API]
    end

    O1 --> KR1
    O2 --> KR2
    O3 --> KR3
    O4 --> KR4
```

---

## 🏛️ The 5 Enhancement Vectors

### 🔷 Vector 1: 3-Tier Intelligent Routing & Confidence Gating
- **Problem**: Traditional OCR engines (RapidOCR/EasyOCR) struggle on degraded scans and handwritten marginalia; brute-force VLMs are too slow/heavy for standard pages and risk hallucination.
- **Solution**: A deterministic 3-tier cascade that dynamically selects the optimal compute path:
  1. **Tier-0 (Vector Pass)**: `pypdfium2` native extraction for born-digital PDFs ($\sim 0.001\text{s/page}$, 0 compute cost).
  2. **Tier-1 (Deterministic ONNX Pass)**: RapidOCR / PP-OCRv4 ONNX with CLAHE and XY-Cut ($\sim 0.5\text{s–1.5s/page}$).
  3. **Tier-2 (Specialist VLM Escalation)**: Triggered when span confidence falls below threshold ($C < 0.85$) or severe spatial overlap occurs. Invokes a quantized local specialist model (PaddleOCR-VL 0.9B or DeepSeek-OCR ONNX) strictly on the degraded region.

```mermaid
flowchart TD
    Page[Input Page] --> CheckDigital{Born Digital?}
    CheckDigital -->|Yes| T0[Tier-0: Native Vector Extraction]
    CheckDigital -->|No| T1[Tier-1: RapidOCR ONNX Fast Pass]
    
    T0 --> QualityCheck{Confidence >= 0.85?}
    QualityCheck -->|Yes| Success[Standard Output]
    QualityCheck -->|No| T1
    
    T1 --> ConfCheck{Page Confidence >= 0.85?}
    ConfCheck -->|Yes| Success
    ConfCheck -->|No| T2[Tier-2: Targeted VLM Crop Escalation]
    T2 --> Merge[Merge Transcriptions] --> Success
```

---

### 🔷 Vector 2: Advanced Table Intelligence & TEDS Evaluation Harness
- **Problem**: Tabular data in financial reports, books, and scientific papers contains merged cells (`colspan`/`rowspan`) and borderless layouts that morphological filters can fragment.
- **Solution**:
  - **ONNX Table Structure Recognition (TSR)**: Integrate a lightweight SLANet / Table-Transformer ONNX model to predict OTSL table tokens and precise cell spans.
  - **TEDS Metric in Eval Harness**: Add `eval/teds_evaluator.py` computing **Tree Edit Distance-based Similarity** ($TEDS_{\text{struct}}$ and $TEDS_{\text{content}}$) on standard table benchmarks (PubTabNet subset).

---

### 🔷 Vector 3: Semantic Book Intelligence & RAG Chunking
- **Problem**: Large Language Models (LLMs) and RAG applications require hierarchical chunking respecting semantic boundaries (chapters, subheadings, tables) rather than naive token-length slicing.
- **Solution**:
  - **Hierarchical Table of Contents (TOC) Extraction**: Detect frontmatter, preface, chapter numbers, and Roman numeral pagination to build a nested JSON document tree.
  - **Footnote & Citation Linking**: Match in-text superscript markers `[^1]` with footer text blocks and compile bidirectional anchor links.
  - **Structure-Aware Semantic Chunker**: Export pre-chunked outputs with metadata (`section_title`, `page_span`, `block_type`, `bbox`) directly compatible with LangChain, LlamaIndex, and vector databases.

---

### 🔷 Vector 4: Mathematical Formula & Equation Recognition
- **Problem**: Equations in academic books and technical slides are rendered as garbled ASCII characters by standard OCR engines.
- **Solution**:
  - **Formula Region Detection**: Detect inline ($...$) and block ($$...$$) mathematical expressions during layout analysis.
  - **UniMERNet / LaTeX Parser**: Transcribe mathematical glyphs into standardized KaTeX/LaTeX formatting.

---

### 🔷 Vector 5: Enterprise Scale, Streaming API & Framework SDKs
- **Problem**: Production web apps need real-time feedback; enterprise developers need standard Python SDK loaders.
- **Solution**:
  - **Server-Sent Events (SSE) & WebSocket Streaming**: Real-time page-by-page progress and live bounding-box streaming on `GET /v1/ocr/jobs/{id}/stream`.
  - **Official Ecosystem Loaders**:
    - `blast_ocr.integrations.langchain.BlastOCRDocumentLoader`
    - `blast_ocr.integrations.llamaindex.BlastOCRReader`
  - **Batch Distributed Worker Swarm**: Multi-worker Redis queue with automated worker heartbeat and graceful auto-scaling.

---

## 📅 Phased Implementation Roadmap

```mermaid
gantt
    title B.L.A.S.T. Production Roadmap (2026-2027)
    dateFormat  YYYY-MM-DD
    section Phase 1: Quality & TEDS
    TEDS Evaluation Harness        :p1_1, 2026-09-01, 14d
    Gold Corpus 10x Expansion      :p1_2, after p1_1, 14d
    CER / WER Calibration          :p1_3, after p1_2, 10d
    
    section Phase 2: Table & Formula
    ONNX Table Structure Model     :p2_1, 2026-10-01, 21d
    LaTeX Math Detector            :p2_2, after p2_1, 14d
    Table DOCX/HTML Precision      :p2_3, after p2_2, 10d
    
    section Phase 3: Hybrid VLM Tier
    Confidence Routing Framework   :p3_1, 2026-11-15, 14d
    PaddleOCR-VL / dots.ocr ONNX   :p3_2, after p3_1, 21d
    Anti-Hallucination Gate        :p3_3, after p3_2, 10d
    
    section Phase 4: Book & RAG
    Hierarchical TOC Detection     :p4_1, 2027-01-05, 14d
    Footnote & Anchor Linking      :p4_2, after p4_1, 10d
    Semantic RAG Chunker           :p4_3, after p4_2, 14d
    
    section Phase 5: Enterprise SDK
    SSE Streaming WebSockets       :p5_1, 2027-02-15, 14d
    LangChain & LlamaIndex Loaders :p5_2, after p5_1, 10d
    Distributed Swarm Cluster      :p5_3, after p5_2, 14d
```

### Milestone Deliverables

| Phase | Core Milestone | Target Deliverable | Benchmark Gate |
| :--- | :--- | :--- | :--- |
| **Phase 1** | **Benchmarking & TEDS** | `eval/teds_evaluator.py`, 100-Page Gold Corpus | CER $\le 0.10$, TEDS baseline established |
| **Phase 2** | **Table & Formula Engine** | ONNX Table Structure parser, LaTeX math converter | TEDS-Struct $\ge 0.90$, Formula BLEU $\ge 0.85$ |
| **Phase 3** | **Hybrid 3-Tier Routing** | Confidence-gated Tier-2 local VLM integration | Mean CER $\le 0.05$, Tau $\ge 0.98$ |
| **Phase 4** | **Book & RAG Intelligence** | Hierarchical TOC, Footnote anchors, Semantic Chunker | 100% Valid EPUB 3.0, Zero broken links |
| **Phase 5** | **Enterprise Connectors** | LangChain / LlamaIndex SDKs, Streaming REST API | < 50ms SSE latency, 100% OpenAPI coverage |

---

## 🛡️ Architectural Non-Negotiables & Guarantees
1. **100% Permissive MIT Licensing**: Zero closed-source or revenue-capped dependencies.
2. **Local & Air-Gapped Capable**: Pure local execution without mandatory internet calls or third-party telemetry.
3. **Deterministic Core Integrity**: Hallucination-free text extraction for archival, legal, and financial compliance.
4. **Backward Compatibility**: Full compatibility across `JobConfig`, `ExportBundle`, and standard input/output schemas.
