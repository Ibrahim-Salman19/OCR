# Interactive Free Tools & Engineering-as-Marketing Calculators: B.L.A.S.T. OCR

**Document Version**: 3.0.0  
**Strategy**: Engineering-as-Marketing (High-Utility, Lead-Generating Interactive Calculators & Simulators)  
**Hosted Endpoints**: Integrated into Sovereign Streamlit UI (`blast_ocr/ui/web_app.py`) & Standalone Web Tools  

---

## 1. Engineering-as-Marketing Philosophy

Following the `free-tools` skill:
1. **Utility Precedes Conversion**: Free interactive tools attract high-intent engineering decision-makers who are actively researching budget, infrastructure limits, and accuracy tradeoffs.
2. **Instant Gratification with Real Math**: Provide un-gated, real-time calculations. Only gate advanced export reports (e.g. customized executive PDF ROI briefing).
3. **Embeddability**: Provide embeddable iframe / React widgets that partner blogs and AI directories can host, driving high-domain-authority backlinks.

---

## 2. Tool 1: Cloud OCR Cost vs. Local Self-Hosted ROI Calculator

- **Live URL**: `https://ocr-book.streamlit.app/#cloud-calculator` / `tools/calculator/`
- **Target Keywords**: "aws textract cost calculator", "ocr cost estimator", "cloud ocr vs local cost"
- **Primary Value**: Calculates exact monthly and 3-year savings by migrating from AWS Textract / Google Document AI to B.L.A.S.T. self-hosted ONNX.

### 2.1 Input Controls (Interactive Sliders)
1. **Monthly Document Volume (Pages)**: Slider `1,000` to `5,000,000` (Default: `100,000` pages/month).
2. **Document Complexity Profile**:
   - `Plain Text Only` (Standard OCR pricing)
   - `Tables & Financial Spreadsheets` (Textract Tables: $0.015/page)
   - `Forms & Key-Value Pairs` (Textract Forms: $0.050/page)
   - `Mixed Enterprise Archive` (Blended: $0.030/page)
3. **Current Cloud Provider**:
   - AWS Textract (Text: $0.0015/pg, Tables: $0.015/pg, Forms: $0.050/pg)
   - Google Cloud Document AI (General: $0.0015/pg, Form Parser: $0.065/pg)
   - Azure AI Document Intelligence (Prebuilt: $0.010/pg, Custom: $0.050/pg)
4. **Current Hardware Available**:
   - Existing On-Premise CPU Nodes ($0 additional hardware cost)
   - Cloud VM Instance (e.g. AWS `c6i.2xlarge` @ $245/month)

### 2.2 Mathematical Engine & Formulas
$$	ext{Monthly Cloud Cost} = 	ext{Pages} 	imes \left( \%_{	ext{text}} 	imes P_{	ext{text}} + \%_{	ext{tables}} 	imes P_{	ext{tables}} + \%_{	ext{forms}} 	imes P_{	ext{forms}} ight)$$
$$	ext{Monthly Self-Hosted Cost} = 	ext{Hardware VM Cost} + 	ext{Maintenance Allowance}$$
$$	ext{Annual Net Savings} = (	ext{Monthly Cloud Cost} - 	ext{Monthly Self-Hosted Cost}) 	imes 12$$
$$	ext{ROI \%} = rac{	ext{Annual Net Savings}}{	ext{Annual Self-Hosted Cost}} 	imes 100$$

### 2.3 Output Dashboard Metrics (Real-Time Display)
- **Current Monthly Cloud Spend**: `$3,000.00`
- **B.L.A.S.T. Self-Hosted Monthly Cost**: `$245.00` (1x 8-core CPU node)
- **Annual Net Savings**: **`$33,060.00 / year`** (91.8% Reduction)
- **3-Year Projected Savings**: **`$99,180.00`**
- **Payback Period**: **`0.09 months (Immediate)`**
- **Lead Capture CTA**: `[Download Executive PDF Cost Briefing for CFO]`

---

## 3. Tool 2: Document Memory Leak Slope & Crash Risk Estimator

- **Live URL**: `https://ocr-book.streamlit.app/#memory-simulator` / `tools/memory-simulator/`
- **Target Keywords**: "python ocr memory leak", "pytorch celery oom killer", "pdf processing crash estimator"
- **Primary Value**: Simulates memory accumulation curves for standard PyTorch/Tesseract pipelines vs. B.L.A.S.T. bounded streaming.

### 3.1 Input Parameters
1. **Archive Size (Pages)**: Slider `50` to `20,000` pages.
2. **Current OCR Engine**:
   - `PyTorch EasyOCR` (Measured leak slope: ~0.045 MB/page)
   - `Unbounded PyMuPDF / Tesseract` (Measured leak slope: ~0.025 MB/page)
   - `B.L.A.S.T. Bounded Streaming` (Measured leak slope: **0.0002 MB/page**)
3. **Worker Server RAM**: `2 GB`, `4 GB`, `8 GB`, `16 GB`, `32 GB`.
4. **Concurrent Worker Processes**: `1`, `2`, `4`, `8`, `16`.

### 3.2 Simulation Engine & Mathematical Modeling
$$	ext{Projected Peak RAM}(N) = 	ext{RAM}_{	ext{baseline}} + (N 	imes 	ext{Slope}_{	ext{engine}} 	imes 	ext{Workers})$$
$$	ext{Crash Probability} = egin{cases} 0\% & 	ext{if } 	ext{Peak RAM} < 0.85 	imes 	ext{Server RAM} \ 75\% & 	ext{if } 0.85 	imes 	ext{Server RAM} \le 	ext{Peak RAM} < 	ext{Server RAM} \ 100\% & 	ext{if } 	ext{Peak RAM} \ge 	ext{Server RAM} 	ext{ (OOM Kill)} \end{cases}$$

### 3.3 Output Visualization (Interactive Chart & Alert)
- **Chart**: Two dynamic line curves (Standard PyTorch ramping steeply into the red OOM threshold at page 640 vs B.L.A.S.T. flatline at 142 MB through 20,000 pages).
- **Failure Prediction Callout**:
  - `⚠️ CRITICAL: Standard PyTorch pipeline will trigger Linux OOM Killer on Page 642 of your 5,000-page archive.`
  - `✔ B.L.A.S.T. Streaming will process all 5,000 pages safely with a peak RAM of 145 MB.`
- **CTA Button**: `[View the 1,000-Page Verified Stress Report]`

---

## 4. Tool 3: TEDS Table Extraction Benchmark & Markdown Playground

- **Live URL**: `https://ocr-book.streamlit.app/#table-playground`
- **Primary Value**: Allows developers to paste or upload an image of a complex table, inspect the morphological grid lines in real-time, and copy clean GFM Markdown.

### 4.1 Features & Interactive UI
1. **Image Dropzone**: Drop any scanned financial table, invoice, or research data sheet (.png, .jpg, .pdf).
2. **Morphological Grid Inspector**: Interactive SVG overlay showing detected horizontal and vertical grid lines, bounding boxes, and cell confidence scores.
3. **Output Tabs**:
   - `GitHub Flavored Markdown (.md)`: Formatted table with copy-to-clipboard button.
   - `HTML Code (<table>)`: Semantic HTML table with `<thead>` and `<tbody>`.
   - `CSV Export`: Clean spreadsheet format.
   - `TEDS Metric Scorer`: If ground truth is provided, calculates Tree-Edit-Distance-score in real-time.

---

## 5. Embeddable JavaScript Widget Code

Partners, technical bloggers, and documentation sites can embed the Cloud OCR Cost Calculator directly using this snippet:

```html
<!-- B.L.A.S.T. Cloud OCR Savings Calculator Widget -->
<div id="blast-ocr-calculator-widget" data-theme="dark" data-default-pages="100000"></div>
<script src="https://blast-ocr.dev/widgets/calculator.js" async></script>
```

The widget delivers immediate utility to the host's readers while generating a clean, canonical attribution link: `Powered by B.L.A.S.T. OCR (MIT Licensed)`.
