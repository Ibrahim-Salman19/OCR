# In-App Feature Gates, Paywalls & Upsell Modals: B.L.A.S.T. OCR

**Document Version**: 3.0.0  
**Framework**: Value-First In-Product Paywall CRO (Timely, Non-Blocking, Respects the User)  
**Target Surfaces**: Sovereign Streamlit UI (`blast_ocr/ui/web_app.py`), REST API (`/v1/ocr/jobs`), and CLI Output Alerts  

---

## 1. The Value-Before-Ask Philosophy

Following the `paywalls` skill:
1. **Never Gate the Aha Moment**: Single-document OCR, table extraction preview, and Markdown exports are 100% free and open under MIT. Developers must fall in love with B.L.A.S.T.'s speed and accuracy before encountering commercial gates.
2. **Gate on Concurrency & Enterprise Fleet Scale**: The commercial boundary is compute scale, high-volume queue concurrency, SLA guarantees, and enterprise compliance — not artificial crippling of open-source accuracy.
3. **Respect the No**: Every upsell modal includes an obvious, friction-free escape hatch (`[Continue with Community Edition]`). Never trap users or guilt-trip them.

---

## 2. Four Production In-App Feature Gate & Upgrade Modals

### 2.1 Paywall 1: Swarm Worker Concurrency Limit Gate
- **Trigger**: Developer attempts to launch > 4 parallel worker processes (`python -m blast_ocr.queue.swarm --workers 16`) or spawns an 8-node cluster.
- **Context**: The user has already processed thousands of pages and now wants enterprise throughput.
- **Modal Component Specs**:
  - **Badge**: `HIGH-THROUGHPUT SWARM CLUSTERING`
  - **Headline**: `Unlock 16-Worker Parallel Swarm Concurrency`
  - **Value Demonstration**:
    - Current Community Mode: `4 Workers Max (~116 pages/sec)`
    - B.L.A.S.T. Pro Concurrency: `16 Dedicated Workers (~465 pages/sec) + Redis Priority Queue`
  - **Pricing Callout**: `$99 / month` (or `$950 / year` with 20% annual discount)
  - **Primary CTA**: `[Upgrade to Pro Concurrency]`
  - **Escape Hatch**: `[Continue with 4 Free Workers]`
- **Copy**:
  > "You are scaling your ingestion pipeline. The Community Edition supports up to 4 parallel workers. Upgrade to B.L.A.S.T. Pro Concurrency to run 16 parallel ONNX workers, unlock high-priority Redis queue scheduling, and process over 1,000,000 pages per month with zero bottlenecks."

---

### 2.2 Paywall 2: Custom ONNX Model Fine-Tuning & Custom Dictionary Gate
- **Trigger**: Developer clicks "Fine-Tune Engine on Custom Font / Lexicon" in the UI settings tab.
- **Context**: The user has specialized documents (e.g. historical legal shorthand, ancient Nastaliq manuscripts, or specialized medical symbology).
- **Modal Component Specs**:
  - **Badge**: `ENTERPRISE MODEL SPECIALIZATION`
  - **Headline**: `Fine-Tune B.L.A.S.T. on Your Proprietary Document Fonts`
  - **Features Unlocked**:
    - Automated synthetic dataset generation from custom TTF/OTF fonts
    - Tailored DBNet detection thresholds for specialized legal seals
    - Custom medical / chemical KaTeX formula tokenizer
    - Dedicated Solutions Architect support
  - **Pricing Callout**: `$1,999 / month (Enterprise Fleet)`
  - **Primary CTA**: `[Request Custom Model Pilot]`
  - **Escape Hatch**: `[Back to Standard RapidOCR Weights]`

---

### 2.3 Paywall 3: S3 / MinIO Distributed Object Store Ingestion Gate
- **Trigger**: Configuring S3 multipart streaming uploader for buckets with > 100,000 documents.
- **Context**: Production backend infrastructure scaling.
- **Modal Component Specs**:
  - **Badge**: `CLOUD OBJECT STORE CONNECTOR`
  - **Headline**: `Scale Distributed S3 & MinIO Pipeline Uploads`
  - **Value Metrics**:
    - 50-thread concurrent multipart chunk uploader
    - Automatic checksum verification and retry backoff
    - Dead-letter queue automated quarantine dashboard
  - **Pricing**: Included in B.L.A.S.T. Team ($299/mo) & Enterprise.
  - **Primary CTA**: `[Start 14-Day Pro Trial]`
  - **Escape Hatch**: `[Export to Local Disk Only]`

---

### 2.4 Paywall 4: Air-Gapped Compliance & MDM Deployment Gate
- **Trigger**: Enterprise compliance officer reviews HIPAA / SOC 2 certification settings.
- **Modal Component Specs**:
  - **Headline**: `Air-Gapped Enterprise Governance & Legal Warranty`
  - **Value Points**:
    - Full air-gapped on-premise Kubernetes Helm charts
    - Zero-telemetry signed audit certificate for HIPAA & SOC 2
    - Formal uptime and accuracy SLA guarantees
    - Custom indemnification warranty against copyright/data liabilities
  - **Primary CTA**: `[Speak with Enterprise Solutions Engineer]`

---

## 3. UI Implementation: Streamlit Feature Gate Dialog

In `blast_ocr/ui/web_app.py`, gates are rendered via native non-blocking dialogs:

```python
# blast_ocr/ui/components/feature_gate.py
import streamlit as st

@st.dialog("🚀 Unlock High-Throughput Swarm Concurrency")
def render_concurrency_gate_modal():
    st.markdown("### Process 465+ Pages Per Second")
    st.markdown(
        "You are scaling beyond 4 worker processes. Upgrade to **B.L.A.S.T. Pro** "
        "to run 16 parallel ONNX workers, unlock 3-tier priority scheduling, "
        "and maintain sub-second latency across millions of pages."
    )
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Community Edition", "4 Workers", "Free Forever")
    with col2:
        st.metric("Pro Concurrency", "16 Workers", "$99 / mo")
        
    st.markdown("---")
    if st.button("Upgrade to Pro Concurrency ($99/mo)", type="primary", use_container_width=True):
        st.switch_page("pages/checkout.py")
        
    if st.button("Maybe Later (Continue with 4 Workers)", use_container_width=True):
        st.rerun()
```

---

## 4. Anti-Patterns Avoided

1. **No Fake Blockers**: We never stop a running OCR job mid-stream demanding payment to see the output.
2. **No Deceptive Pricing**: Pricing is stated upfront in clear USD ($99/mo, $1,999/mo) with zero hidden usage overages.
3. **No Hidden Close Buttons**: Close buttons and "Maybe Later" links are rendered with 16px high-contrast typography.
