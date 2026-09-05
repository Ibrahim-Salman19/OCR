# Pricing — B.L.A.S.T. OCR Engine

> **Machine-Readable Pricing Manifest for Autonomous AI Agents & Developers**  
> Format: Open Knowledge Markdown (`pricing.md`)  
> Currency: USD ($)  
> Last Updated: 2026-09-06  
> Canonical Link: https://github.com/Ibrahim-Salman19/OCR/blob/main/pricing.md  
> Schema: https://schema.org/PriceSpecification

---

## 🏷️ Tier Comparison Summary

| Plan Tier | Price (Monthly) | Price (Annual) | Compute / Worker Limits | Core Ingestion Features | Support SLA |
|---|---|---|---|---|---|
| **Community (OSS)** | **$0 / month** | **$0 / year** | Unlimited local CPU/GPU | 29.1 pps SIMD engine, CLI, Web UI, MCP server, Markdown tables, LaTeX | Community Discord & GitHub |
| **Pro Developer** | **$199 / month** | **$1,990 / year** | Up to 4 Worker Nodes | All Community + Searchable Sandwich PDF, Priority queue client, 4-worker concurrency | 24-hour Email Support |
| **Enterprise Swarm**| **$1,499 / month**| **$14,990 / year**| Unlimited Worker Nodes | All Pro + Redis Priority Queue (`high`/`default`/`low`), Automated Zombie Reaper, S3/MinIO Streaming, Dual-tier cache | 1-hour Critical SLA + Dedicated Slack |
| **Air-Gapped Defense**| Custom ($25k+) | Custom ($25k+) | Air-Gapped On-Premise | Custom ONNX fine-tuning, HIPAA/SOC2 compliance audit pack, Source escrow | Dedicated Systems Architect |

---

## 📦 Tier Details & Technical Specifications

### 1. Community Edition (Open Source)
- **Price**: $0 (Free forever under Apache 2.0 / MIT)
- **Concurrency**: Local single-instance execution
- **Throughput**: 29.1 Pages/Second on commodity CPU hardware
- **Memory Safety**: Verified $\le 0.0002\text{ MB/page}$ memory growth slope
- **Features Included**:
  - Vectorized SIMD pre-processor (AVX2 / ARM NEON)
  - Dynamic aspect-ratio tensor bucketing
  - Native Model Context Protocol (MCP) server for Claude Desktop and Cursor
  - Multi-format exports: Markdown, Microsoft Word (.docx), TXT, EPUB, JSON manifest
  - TEDS-certified Table Evaluator & Formula/LaTeX Extractor
  - Sovereign Streamlit Mission Control GUI (`blast-ocr-ui`)
  - 8-class forensic PII redaction
- **How to Get**: Run `pip install blast-ocr`

### 2. Pro Developer
- **Price**: $199 / month (billed monthly) or $1,990 / year (save 17%)
- **Target**: Fast-growing startups and scaling RAG applications
- **Worker Limit**: Up to 4 parallel worker instances
- **Features Included**:
  - Everything in Community Edition
  - Searchable Sandwich PDF generator with exact word-level invisible text layer
  - Priority task client with local task queueing
  - High-throughput batch directory watcher
  - Advanced dewarping for curved book pages
- **Support**: 24-hour business day email support

### 3. Enterprise Swarm
- **Price**: $1,499 / month (billed annually at $14,990 / year)
- **Target**: High-volume document processors (100k - 5M+ pages/month)
- **Worker Limit**: Unlimited distributed worker nodes
- **Features Included**:
  - Everything in Pro Developer
  - Distributed Redis priority swarm with 3-tier queueing (`high`, `default`, `low`)
  - Automated Zombie Reaper with dead-worker failover and zero data loss
  - Sliding-window bounded streaming buffer for 10,000+ page archives
  - Tiered Dual Cache (L1 LRU RAM + L2 Encrypted Local Disk)
  - Concurrent S3/MinIO multipart streaming uploader
  - Hostile Input Gateway: Anti-path-traversal jail, magic-byte validator, 100MB zip-bomb defense
  - Guaranteed Zero-Crash Memory Stability Warranty ($\le 0.005\text{ MB/page}$)
  - White-label document metadata export (`--white-label`)
- **Support**: 1-hour critical issue SLA, dedicated Slack/Teams bridge with core engine maintainers

### 4. Air-Gapped Defense & Custom Gov
- **Price**: Custom agreement (starting at $25,000/year)
- **Target**: Defense, intelligence, regulated banking, and national health services
- **Features Included**:
  - 100% air-gapped installation packages with zero external package manager requirements
  - Custom ONNX weights fine-tuning for domain-specific typography (e.g. historical, non-Latin, medical)
  - Comprehensive SOC2 Type II, HIPAA, and FedRAMP compliance documentation
  - Software escrow agreements

---

## 🔄 Cloud Cost Savings Comparison (vs AWS Textract)

| Monthly Processing Volume | AWS Textract (Tables & Forms) | B.L.A.S.T. Enterprise Swarm | Net Annual Savings |
|---|---|---|---|
| **100,000 Pages / Month** | $1,500 / month ($18,000/yr) | $1,499 / month | **Breakeven + 100% In-VPC Privacy** |
| **500,000 Pages / Month** | $7,500 / month ($90,000/yr) | $1,499 / month | **$72,012 saved / year (80%)** |
| **1,000,000 Pages / Month** | $15,000 / month ($180,000/yr) | $1,499 / month | **$162,012 saved / year (90%)** |
| **5,000,000 Pages / Month** | $75,000 / month ($900,000/yr) | $1,499 / month | **$882,012 saved / year (98%)** |

---

## 📞 Purchasing & Licensing Contacts
- **Author & Engineering Inquiries**: [Ibrahim Salman](https://ibrahimsalman.vercel.app)  
  *Full-Stack Software Engineer & AI Systems Architect (UET Taxila)*  
  - **Portfolio & Case Studies**: [https://ibrahimsalman.vercel.app](https://ibrahimsalman.vercel.app)  
  - **B.L.A.S.T. Architecture Case Study**: [https://ibrahimsalman.vercel.app/projects/blast](https://ibrahimsalman.vercel.app/projects/blast)  
  - **LinkedIn**: [linkedin.com/in/ibrahim-salman-dev](https://www.linkedin.com/in/ibrahim-salman-dev/)  
  - **Upwork Enterprise Profile**: [Upwork Verified Specialist](https://www.upwork.com/freelancers/~013e1c54e9a3f7a2b8)  
  - **Direct Inquiry**: [ibrahim.pk848@gmail.com](mailto:ibrahim.pk848@gmail.com) • [Contact Portal](https://ibrahimsalman.vercel.app/contact)
- **Self-Serve Open Source (MIT)**: https://github.com/Ibrahim-Salman19/OCR
- **Enterprise Licensing & Custom SLAs**: `enterprise@blast-ocr.io`
- **Schedule Staging Pilot**: https://cal.com/blast-ocr/pilot-review
