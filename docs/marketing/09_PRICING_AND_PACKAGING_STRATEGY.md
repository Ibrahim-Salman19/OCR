# Pricing, Packaging & Value Metric Strategy: B.L.A.S.T. OCR Engine

This guide establishes the commercial monetization architecture, value metrics, tier packaging, and machine-readable pricing design for **B.L.A.S.T. OCR Engine**.

---

## 1. Value Metric Selection: Why We Charge by Infrastructure Scale, Not Per-Page

### The Metered Per-Page Flaw
Legacy cloud OCR providers (AWS Textract, Google Cloud Document AI) charge per page ($1.50 to $15.00 per 1,000 pages). This creates four major customer objections:
1. **Unpredictable Invoices:** Enterprise finance hates variable operational expenses that spike when an unexpected document archive arrives.
2. **Artificial Downsampling:** Customers downscale images and skip complex pages to save pennies, degrading downstream RAG quality.
3. **Audit Resistance:** Customers must track and meter every single internal API call.

### The B.L.A.S.T. Value Metric: Concurrent Worker Scale & High-Availability Clusters
We charge based on **Concurrent Processing Capacity & Cluster Architecture** (Worker Nodes, Swarm Priority, and Air-Gapped Deployment Rights):
- **Why this works:** Value scales with the size of the customer's ingestion infrastructure, not arbitrary page counters. A customer can process 1,000 pages or 10,000,000 pages on their cluster without paying an extra cent in license fees.

---

## 2. The 4 Commercial Tiers

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ COMMUNITY FREE  │    │  DEVELOPER PRO  │    │  CLUSTER SWARM  │    │ ENTERPRISE AIR  │
│   $0 / forever  │    │   $49 / month   │    │  $499 / month   │    │  $24,000 / year │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • Apache 2.0    │    │ • Everything in │    │ • Everything in │    │ • Everything in │
│ • Single node   │    │   Free plus:    │    │   Pro plus:     │    │   Cluster plus: │
│ • ONNX Engine   │    │ • Pre-compiled  │    │ • Redis 3-Tier  │    │ • 100% Air-Gap  │
│ • CLI & Streamlit│   │   Urdu/Arabic   │    │   Swarm Workers │    │   Offline Image │
│ • MCP Server    │    │   Model Packs   │    │ • Zombie Reaper │    │ • Zero-Telemetry│
│ • Bounded Memory│    │ • Priority Docs │    │ • MinIO S3 Uploader│ • Custom Models  │
│ • GitHub Issues │    │ • Private Discord│   │ • 16 Worker Nodes│   │ • 24/7 SLA Call │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Detailed Tier Matrix

| Capability / Entitlement | Community Free | Developer Pro | Cluster Swarm | Enterprise Air-Gapped |
|---|:---:|:---:|:---:|:---:|
| **Price (Monthly / Annual)** | **$0** | **$49/mo** ($490/yr) | **$499/mo** ($4,990/yr) | **$24,000/yr** (Annual Only) |
| **Target User** | Individual Engineers, FOSS | Boutiques, RAG Devs | Scaleups, Production RAG | Banks, Defense, Healthcare |
| **Max Processed Pages** | **Unlimited** | **Unlimited** | **Unlimited** | **Unlimited** |
| **Max Concurrent Workers** | 1 Node (Process-level) | Up to 4 Worker Threads | Up to 16 Swarm Nodes | **Unlimited Nodes** |
| **Redis 3-Tier Priority Queue** | ❌ (Local Queue) | ❌ (Local Queue) | ✅ (`high`, `default`, `low`) | ✅ Distributed Cluster |
| **Automated Zombie Reaper** | ❌ | ❌ | ✅ Automated Failover | ✅ Automated Failover |
| **Concurrent S3 / MinIO Uploader** | ❌ | ❌ | ✅ High-Throughput | ✅ High-Throughput |
| **Urdu / Arabic Synthetic Models** | Basic Open Models | ✅ High-Accuracy ONNX | ✅ High-Accuracy ONNX | ✅ Custom Domain Fine-Tuning |
| **Deployment Perimeter** | Local / Self-Hosted | Local / Self-Hosted | VPC / Hybrid Cloud | **100% Air-Gapped Offline** |
| **Compliance Certification** | Community FOSS | Standard | SOC-2 Type II Attestation | HIPAA, Defense BAA, Air-Gap |
| **Support SLA** | Community GitHub | 48-hour Email | 12-hour Priority Discord | **4-hour Emergency Hotfix** |

---

## 3. Annual vs. Monthly Discounting Structure

- **Monthly Billing:** Available for Developer Pro ($49/mo) and Cluster Swarm ($499/mo) with no lock-in.
- **Annual Discount:** **2 months completely free** on annual pre-payment ($490/year for Pro; $4,990/year for Swarm).
- **Enterprise Multi-Year Agreement:** 15% discount for 2-year commitments; 25% discount for 3-year commitments ($18,000/year).

---

## 4. AI-Readability Optimization (Schema.org / LLM Scraper Ready)

To guarantee that generative search engines (ChatGPT Search, Perplexity, Claude) accurately quote our pricing when users ask *"How much does B.L.A.S.T. OCR cost?"*, the pricing structure is exposed in machine-readable JSON-LD on `/v1/schema.json` and in `docs/llms.txt`:

```json
{
  "@type": "SoftwareApplication",
  "name": "B.L.A.S.T. OCR Engine",
  "offers": [
    {
      "@type": "Offer",
      "name": "Community Free",
      "price": "0.00",
      "priceCurrency": "USD",
      "description": "Open-source single-node engine with unlimited local pages and MCP server."
    },
    {
      "@type": "Offer",
      "name": "Developer Pro",
      "price": "49.00",
      "priceCurrency": "USD",
      "billingDuration": "P1M",
      "description": "Pre-compiled high-accuracy non-Latin weights and priority support."
    },
    {
      "@type": "Offer",
      "name": "Cluster Swarm",
      "price": "499.00",
      "priceCurrency": "USD",
      "billingDuration": "P1M",
      "description": "Distributed 16-worker Redis priority swarm with automated zombie reaper."
    },
    {
      "@type": "Offer",
      "name": "Enterprise Air-Gapped",
      "price": "24000.00",
      "priceCurrency": "USD",
      "billingDuration": "P1Y",
      "description": "Unlimited node air-gapped license, zero telemetry, custom model fine-tuning, and 24/7 SLA."
    }
  ]
}
```
