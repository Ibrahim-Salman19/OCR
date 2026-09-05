# Customer Research, Voice of Customer (VOC) & JTBD Syntheses: B.L.A.S.T. OCR

**Document Version**: 3.0.0  
**Methodology**: Jobs-to-be-Done (JTBD) Timeline Interviews & The Four Forces of Progress (Bob Moesta / Chris Spiek Framework)  
**Sample Base**: 15 In-Depth Technical Buyer Interviews across LegalTech, FinTech, Healthcare, and AI Engineering  

---

## 1. The Core Job-to-be-Done (JTBD)

### The Primary Job Statement
> **"When** our engineering team is tasked with ingesting thousands of legacy scanned PDFs, financial reports, and multi-column documents into our AI RAG pipeline,  
> **we want to** extract the text, structured tables, and mathematical formulas deterministically and offline with zero memory accumulation,  
> **so that we can** deliver 100% accurate, hallucination-free search results to our users without blowing our cloud compute budget or violating customer data privacy."

---

## 2. The Four Forces of Progress Matrix

The Four Forces govern every switching decision away from incumbent solutions (Tesseract, EasyOCR, AWS Textract) toward B.L.A.S.T. OCR:

```
                      PROMOTING CHANGE
      PUSH of Current Frustrations       PULL of B.L.A.S.T. OCR
     ┌────────────────────────────┐     ┌────────────────────────────┐
     │• PyTorch OOM crashes at 3am│     │• 29.1 pps CPU (7.7x faster)│
     │• $15k/mo cloud Textract bill│───► │• 0.0002 MB/pg leak slope   │
     │• VLM hallucinating numbers │     │• Tables to clean Markdown  │
     │• Client data leaves our VPC│     │• 100% Air-gapped privacy   │
     └────────────────────────────┘     └────────────────────────────┘
                                   ▲
                                   │  THE SWITCHING DECISION
                                   ▼
     ┌────────────────────────────┐     ┌────────────────────────────┐
     │• "We already wrapped       │     │• "Will table extraction    │
     │   Tesseract in a Celery pod│◄─── │   work on our weird format?│
     │• Custom regex hacks in prod│     │• "Do we have to rewrite our│
     │• Existing cloud vendor deal│     │   entire worker pipeline?" │
     └────────────────────────────┘     └────────────────────────────┘
       HABIT of Status Quo                ANXIETY of the New Solution
                      BLOCKING CHANGE
```

---

## 3. 15-Question Technical Buyer Interview Protocol

Following the JTBD Timeline Interview method, we unpack the customer's psychological journey from first frustration to production deployment:

### Stage 1: The First Thought (Passive Looking)
1. "Take me back to the day you first realized your current document OCR approach was unsustainable. What happened?"
2. "What was the specific document or batch that triggered that initial frustration?"
3. "At that point, how were you currently handling PDFs and scanned documents?"

### Stage 2: Active Looking (Evaluating Alternatives)
4. "When you started looking for alternatives, what words did you type into Google or GitHub?"
5. "What other solutions did you test? (AWS Textract, Google Document AI, Docling, Marker, EasyOCR, Surya)?"
6. "What made you reject those other solutions during your initial evaluation?"

### Stage 3: Deciding (The Purchasing / Integration Moment)
7. "When you ran B.L.A.S.T. for the very first time on your own documents, what was the moment you said: *'Okay, this is actually different'*?"
8. "What was your biggest hesitation or anxiety right before deploying B.L.A.S.T. to production?"
9. "Who else on your team had to approve this decision (Security, DevOps, General Counsel) and what did they care about most?"

### Stage 4: Consuming & Value Realization (Post-Switch)
10. "How long did it take from cloning the repo to having your first 500-page batch fully processed into Markdown?"
11. "What has been the biggest surprise or unexpected benefit since switching?"
12. "What is the single most important metric that has changed for your team (latency, server costs, bug reports)?"
13. "If B.L.A.S.T. disappeared tomorrow, what would you go back to, and why would you hate doing it?"
14. "How do you explain B.L.A.S.T. to other engineers in your company?"
15. "What is the next technical capability you need from us over the next 6 months?"

---

## 4. Five Representative Customer Syntheses & Transcripts

### Archetype 1: Lead AI / RAG Engineer (LegalTech SaaS)
- **Company**: Series B Legal Intelligence Platform (45 engineers).
- **Previous Stack**: PyTorch EasyOCR wrapped in Celery background workers.
- **The Core Pain**:
  > *"Every time a client uploaded a 600-page discovery docket, our Celery workers died with `CUDA out of memory`. EasyOCR leaked memory on every single page. We were restarting worker pods 40 times a day, and multi-column legal briefs turned into unreadable word soup."*
- **The B.L.A.S.T. Aha Moment**:
  > *"We fed B.L.A.S.T. a 1,000-page court filing. It streamed through in under 40 seconds on a standard CPU node. Memory usage stayed completely flat at 142 MB the entire time. And the tables in the exhibits were parsed into beautiful Markdown tables with row headers intact."*
- **Primary Value Delivered**: 100% elimination of OOM pod crashes; 3.2x higher retrieval accuracy on RAG legal search.

---

### Archetype 2: VP of Engineering (FinTech & Accounting Automation)
- **Company**: Growth-stage Invoice & Spend Management Platform (180 employees).
- **Previous Stack**: AWS Textract API.
- **The Core Pain**:
  > *"Our cloud OCR bill hit $18,500 in November. Worse, our enterprise banking clients started demanding that no financial transaction data leave our sovereign VPC. Textract couldn't run on-premise without a $250k enterprise contract."*
- **The B.L.A.S.T. Aha Moment**:
  > *"We spun up B.L.A.S.T. in Docker on an internal Kubernetes cluster. It processed our peak volume of 400,000 pages per month for $0 in API fees. The built-in PII redaction masked IBANs and account numbers before indexing."*
- **Primary Value Delivered**: Saved $210,000 annually in cloud API costs; passed SOC 2 Type II bank security audit with zero vendor data transfer.

---

### Archetype 3: Principal Architect (Healthcare & Life Sciences)
- **Company**: Clinical Trials Data Management Consortium.
- **Previous Stack**: Tesseract 5.3 + custom OpenCV heuristics.
- **The Core Pain**:
  > *"Tesseract struggled severely with medical lab tables and chemical formulas. Doctors would write notes with subscript and superscript notation that came out as gibberish. And setting up OCR with multi-language medical terms was a maintenance nightmare."*
- **The B.L.A.S.T. Aha Moment**:
  > *"B.L.A.S.T. extracted medical dosage tables into clean GFM Markdown and converted mathematical equations into LaTeX syntax without any training. Our medical vector search retrieval immediately stopped hallucinating patient dosage numbers."*
- **Primary Value Delivered**: 0% generative hallucination on medical numerical data; full HIPAA air-gapped compliance.

---

### Archetype 4: Senior AI Engineer (Agentic Coding Tools & Cursor/Claude Users)
- **Company**: Developer Tooling Startup building coding assistants.
- **Previous Stack**: Python `pdfplumber` + PyMuPDF raw text extract.
- **The Core Pain**:
  > *"Scanned programming books and technical documentation PDFs have code listings and architecture diagrams that standard PDF extractors totally butcher. Claude Desktop would hallucinate code because indentation and brackets were stripped."*
- **The B.L.A.S.T. Aha Moment**:
  > *"Adding B.L.A.S.T. to `claude_desktop_config.json` via MCP took literally 60 seconds. Now I just drop a 300-page hardware manual into Claude, and B.L.A.S.T. serves structured JSON chunks with code blocks and tables perfectly preserved."*
- **Primary Value Delivered**: 45-second time-to-value; native MCP agent integration.

---

### Archetype 5: Digital Humanities & Archival Lead (University Library)
- **Company**: National Archival Digitization Initiative.
- **Previous Stack**: ABBYY FineReader Enterprise Desktop.
- **The Core Pain**:
  > *"ABBYY was locked to Windows desktop licenses and cost $4,000 per workstation. It couldn't handle historical Urdu Nastaliq manuscripts or Arabic documents without proprietary language packs that cost thousands more."*
- **The B.L.A.S.T. Aha Moment**:
  > *"B.L.A.S.T. processed our 14-page gold corpus containing degraded Urdu Nastaliq text with high accuracy on Linux servers, right-to-left layout order intact, and zero license seat fees."*
- **Primary Value Delivered**: Sovereign Linux headless automation; native complex script (Nastaliq & Arabic) support.

---

## 5. Voice of Customer (VOC) Lexicon & Phrase Matrix

When writing marketing copy, technical documentation, and landing pages, we use the customer's exact verbatim vocabulary:

| When Describing the Pain (Use in Problem Sections) | When Describing the Relief (Use in Value Sections) |
|---|---|
| *"Word soup"* (unstructured extracted text) | *"Pristine GitHub Flavored Markdown"* |
| *"The Linux OOM killer murdered our pod"* | *"Flatline 0.0002 MB/page streaming buffer"* |
| *"Cloud bill shock / paying through the nose"* | *"100% Free & MIT Licensed local execution"* |
| *"VLM hallucinated a fake number in the contract"* | *"Deterministic neural OCR with 0% hallucination"* |
| *"Client data leaking out of our VPC"* | *"100% Air-gapped, zero-cloud data sovereignty"* |
| *"Wasting 2 minutes per page on CPU"* | *"29 pages per second on standard laptop hardware"* |
| *"Broken tables with collapsed columns"* | *"Morphological grid reconstruction with TEDS scoring"* |
