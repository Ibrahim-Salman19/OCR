# 📚 B.L.A.S.T. OCR — Master Engineering & Documentation Index

**Status**: 🟢 Certified Production Knowledge Base  
**Maintainer**: [Ibrahim Salman](https://ibrahimsalman.vercel.app)  
**Canonical Directory**: `docs/`  

---

## 🏛️ Core Architecture & Engineering Specifications
- **[Architecture Deep Dive](ARCHITECTURE_DEEP_DIVE.md)**: 3-Layer A.N.T. design pattern, SIMD preprocessing, and tensor decoding.
- **[Benchmarks 2026](BENCHMARKS_2026.md)**: Reproducible 29.1 pps CPU throughput and 0.0002 MB/page streaming leak measurements.
- **[Deployment Guide](DEPLOYMENT_GUIDE.md)**: Production deployment via Docker, Kubernetes, and bare metal.
- **[Security Hardening](SECURITY_HARDENING.md)**: Sandboxing, path traversal jails, and 8-class PII redaction.
- **[Performance Tuning](PERFORMANCE_TUNING.md)**: ONNX Runtime thread affinity, aspect ratio bucketing, and SIMD acceleration.
- **[API Reference](API_REFERENCE.md)**: FastAPI endpoints, OpenAPI specs, SSE streaming, and Webhooks.
- **[AI Agent Integration Guide](AI_AGENT_INTEGRATION_GUIDE.md)**: Connecting LangChain, LlamaIndex, and MCP.
- **[Competitive Landscape](COMPETITIVE_LANDSCAPE.md)** & **[Competitive Research 2026](COMPETITIVE_RESEARCH_2026.md)**: Feature and latency bake-offs.
- **[Troubleshooting Guide](TROUBLESHOOTING.md)**: Diagnosing OCR anomalies, orientation errors, and queue lags.
- **[Document Processing Failure Taxonomy](DOCUMENT_PROCESSING_FAILURE_TAXONOMY.md)**: Error classifications and recovery strategies.
- **[Forensic Codebase Gap Analysis](FORENSIC_CODEBASE_GAP_ANALYSIS.md)**: System verification and test audits.
- **[Hardening Blueprint & Test Specs](HARDENING_BLUEPRINT_AND_TEST_SPECS.md)**: Chaos engineering and fuzz testing harness.
- **[Strategic Enhancement Plan](STRATEGIC_ENHANCEMENT_PLAN.md)**: Technical roadmap for enterprise scale.
- **[Evaluation Harness Guide](EVAL_HARNESS.md)**: Ground-truth corpus benchmarking and CER calculation.
- **[OCR Engine Evaluation 2026](OCR_ENGINE_EVALUATION_2026.md)**: Comparative bake-offs.
- **[OCR Engine Integration Map](OCR_ENGINE_INTEGRATION_MAP.md)**: Pluggable engine dispatch architecture.
- **[OCR Engine Transition Playbook](OCR_ENGINE_TRANSITION_PLAYBOOK.md)**: Migration strategies.
- **[Directory Submissions & Ecosystem](DIRECTORY_SUBMISSIONS_AND_ECOSYSTEM.md)**: Registries and distribution.
- **[GEO & SEO Optimization](GEO_AND_SEO_OPTIMIZATION.md)**: Generative Engine Optimization architecture.

---

## 📐 Architectural Decision Records (ADRs)
- **[ADR 0001: Stabilization Warning & Memory Policy](adr/0001-stabilization-warning-and-memory-policy.md)**
- **[ADR 0002: Eval Harness & Cache Key Fix](adr/0002-eval-harness-and-cache-key-fix.md)**
- **[ADR 0003: Phase 1 Preprocessing Fixes](adr/0003-phase1-preprocessing-fixes.md)**
- **[ADR 0004: Phase 2 Layout & Document Model](adr/0004-phase2-layout-and-document-model.md)**
- **[ADR 0005: Phase 3 Engine Bakeoff](adr/0005-phase3-engine-bakeoff.md)**
- **[ADR 0006: Phase 4 Book Intelligence](adr/0006-phase4-book-intelligence.md)**
- **[ADR 0007: Phase 5 Tier-0 Native Extraction](adr/0007-phase5-tier0-native-extraction.md)**
- **[ADR 0008: Phase 6 CRAFT Layer](adr/0008-phase6-craft-layer.md)**
- **[ADR 0009: Phase 1 v2 Wiring & Correctness](adr/0009-phase1-v2-wiring-and-correctness.md)**
- **[ADR 0010: Phase 2 Durable Queue & Alembic Fix](adr/0010-phase2-durable-queue-and-alembic-fix.md)**
- **[ADR 0011: Phase 3 Object Storage](adr/0011-phase3-object-storage.md)**
- **[ADR 0012: Phase 4 Observability](adr/0012-phase4-observability.md)**
- **[ADR 0013: Phase 5 CI/CD & Packaging](adr/0013-phase5-ci-cd-and-packaging.md)**

---

## 🔍 Developer SEO & Knowledge Hub (`docs/seo/`)
- **[High-Throughput PDF OCR in Python (29.1 pps)](seo/high-throughput-pdf-ocr-python.md)**
- **[Extract Tables from Scanned PDF in Python](seo/extract-tables-from-scanned-pdf-python.md)**
- **[How to Prevent Memory Leaks in Python Batch OCR](seo/pdf-ocr-memory-leak-prevention.md)**
- **[Setting Up Local MCP Server for Document OCR](seo/mcp-server-ocr-setup-guide.md)**
- **[Local OCR vs Cloud Vision Cost Comparison](seo/local-ocr-vs-cloud-vision-cost-comparison.md)**
- **[Searchable PDF Sandwich Generation Guide](seo/searchable-pdf-sandwich-generation.md)**
- **[Distributed OCR Worker Swarm with Redis](seo/distributed-ocr-worker-swarm-redis.md)**

---

## ⚔️ Competitor Comparisons & Alternatives (`docs/comparisons/`)
- **[Master Comparisons Index](comparisons/index.md)**
- **[B.L.A.S.T. vs Tesseract OCR](comparisons/blast-vs-tesseract.md)**
- **[B.L.A.S.T. vs EasyOCR](comparisons/blast-vs-easyocr.md)**
- **[B.L.A.S.T. vs AWS Textract](comparisons/blast-vs-aws-textract.md)**
- **[B.L.A.S.T. vs IBM Docling](comparisons/blast-vs-docling.md)**
- **[B.L.A.S.T. vs Marker 2](comparisons/blast-vs-marker.md)**
- **[Best Tesseract Alternative (2026 Guide)](comparisons/tesseract-alternative.md)**
- **[Best Self-Hosted AWS Textract Alternative](comparisons/aws-textract-alternative.md)**

---

## 🔄 Programmatic Document Format Conversions (`docs/conversions/`)
- **[Master Conversions Hub](conversions/index.md)**
- **[PDF to Markdown Converter](conversions/pdf-to-markdown.md)**
- **[Scanned PDF to DOCX Converter](conversions/scanned-pdf-to-docx.md)**
- **[PPTX to Markdown Converter](conversions/pptx-to-markdown.md)**
- **[Image to Searchable PDF Converter](conversions/image-to-searchable-pdf.md)**
- **[PDF to LaTeX Math Extractor](conversions/pdf-to-latex.md)**
- **[Scanned PDF to EPUB 3.0 Digitizer](conversions/pdf-to-epub.md)**

---

## 🤖 AI Agent & RAG Integrations (`docs/integrations/`)
- **[Master Integrations Hub](integrations/index.md)**
- **[LangChain RAG Integration Guide](integrations/langchain-rag.md)**
- **[LlamaIndex RAG Integration Guide](integrations/llamaindex-rag.md)**
- **[Cursor IDE MCP Setup Guide](integrations/cursor-mcp-setup.md)**
- **[Claude Desktop MCP Setup Guide](integrations/claude-desktop-mcp.md)**

---

## 📑 Technical Whitepapers & Research (`docs/whitepapers/`)
- **[Zero-Leak Streaming Memory Architecture Blueprint](whitepapers/enterprise-ocr-memory-architecture.md)**
- **[Evaluating Table Extraction with TEDS Benchmark](whitepapers/teds-table-extraction-benchmark.md)**
- **[Enterprise Cloud OCR Migration Playbook](whitepapers/cloud-to-local-migration-playbook.md)**

---

## 📈 Commercialization & GTM Playbooks (`docs/marketing/`)
- **[01. Marketing Plan (AARRR GTM)](marketing/01_MARKETING_PLAN_AARRR.md)**
- **[02. Marketing Council Review](marketing/02_MARKETING_COUNCIL_REVIEW.md)**
- **[03. Tactical Idea Bank (139 Tactics)](marketing/03_TACTICAL_IDEA_BANK.md)**
- **[04. Marketing Psychology & Mental Models](marketing/04_MARKETING_PSYCHOLOGY_AND_MENTAL_MODELS.md)**
- **[05. Marketing Loops & Automation](marketing/05_MARKETING_LOOPS_AND_AUTOMATION.md)**
- **[06. Competitor Profiles](marketing/06_COMPETITOR_PROFILES.md)**
- **[07. Competitor Comparisons & Battlecards](marketing/07_COMPETITOR_COMPARISONS_AND_BATTLECARDS.md)**
- **[08. Grand Slam Offer Design](marketing/08_GRAND_SLAM_OFFER_DESIGN.md)**
- **[09. Pricing & Packaging Strategy](marketing/09_PRICING_AND_PACKAGING_STRATEGY.md)**
- **[10. Sales Enablement Playbook](marketing/10_SALES_ENABLEMENT_PLAYBOOK.md)**
- **[11. RevOps & Pipeline Management](marketing/11_REVOPS_AND_PIPELINE_MANAGEMENT.md)**
- **[12. GEO & AEO Advanced Playbook](marketing/12_GEO_AEO_ADVANCED_PLAYBOOK.md)**
- **[13. Technical SEO Audit Report](marketing/13_TECHNICAL_SEO_AUDIT.md)**
- **[14. Site Architecture & Taxonomy](marketing/14_SITE_ARCHITECTURE_AND_TAXONOMY.md)**
- **[15. Programmatic SEO Spec](marketing/15_PROGRAMMATIC_SEO_SPEC.md)**
- **[16. Schema Markup Validation](marketing/16_SCHEMA_MARKUP_VALIDATION.md)**
- **[17. Homepage & Landing Page Copy](marketing/17_HOMEPAGE_AND_LANDING_PAGE_COPY.md)**
- **[18. Copy Editing Audit & Revision](marketing/18_COPY_EDITING_AUDIT_AND_REVISION.md)**
- **[19. CRO Audit & Roadmap](marketing/19_CRO_AUDIT_AND_EXPERIMENT_ROADMAP.md)**
- **[20. Developer Activation Flow](marketing/20_DEVELOPER_SIGNUP_AND_ACTIVATION_FLOW.md)**
- **[21. User Onboarding Experience](marketing/21_USER_ONBOARDING_EXPERIENCE.md)**
- **[22. Feature Gates & Upsell Modals](marketing/22_FEATURE_GATES_AND_UPSELL_MODALS.md)**
- **[23. Modals & Notification Banners](marketing/23_MODALS_AND_NOTIFICATION_BANNERS.md)**
- **[24. A/B Testing Program](marketing/24_AB_TESTING_PROGRAM.md)**
- **[25. Cold Outreach Playbook](marketing/25_COLD_OUTREACH_PLAYBOOK.md)**
- **[26. ICP Prospecting Guide](marketing/26_ICP_PROSPECTING_GUIDE.md)**
- **[27. Lifecycle Email Flows](marketing/27_LIFECYCLE_EMAIL_FLOWS.md)**
- **[28. SMS & Pipeline Notifications](marketing/28_SMS_AND_PIPELINE_NOTIFICATIONS.md)**
- **[29. Launch Execution Playbook](marketing/29_LAUNCH_EXECUTION_PLAYBOOK.md)**
- **[30. Community Marketing Strategy](marketing/30_COMMUNITY_MARKETING_STRATEGY.md)**
- **[31. Co-Marketing & Integration Partnerships](marketing/31_CO_MARKETING_AND_INTEGRATION_PARTNERSHIPS.md)**
- **[32. Creator & Influencer Partnerships](marketing/32_CREATOR_AND_INFLUENCER_PARTNERSHIPS.md)**
- **[33. Referral & Advocacy Program](marketing/33_REFERRAL_AND_ADVOCACY_PROGRAM.md)**
- **[34. Events & Conference Strategy](marketing/34_EVENTS_AND_CONFERENCE_STRATEGY.md)**
- **[35. PR & Media Pitch Deck](marketing/35_PR_AND_MEDIA_PITCH_DECK.md)**
- **[36. Content Strategy & Editorial Calendar](marketing/36_CONTENT_STRATEGY_AND_EDITORIAL_CALENDAR.md)**
- **[37. Lead Magnets & Whitepapers](marketing/37_LEAD_MAGNETS_AND_WHITEPAPERS.md)**
- **[38. Free Tools & Calculators Spec](marketing/38_FREE_TOOLS_AND_CALCULATORS_SPEC.md)**
- **[39. Social Media Content Calendar](marketing/39_SOCIAL_MEDIA_CONTENT_CALENDAR.md)**
- **[40. Video Scripts & Storyboards](marketing/40_VIDEO_SCRIPTS_AND_STORYBOARDS.md)**
- **[41. Creative & Visual Asset Specs](marketing/41_CREATIVE_AND_VISUAL_ASSET_SPECS.md)**
- **[42. Paid Advertising Blueprints](marketing/42_PAID_ADVERTISING_BLUEPRINTS.md)**
- **[43. App Store Optimization (ASO)](marketing/43_APP_STORE_OPTIMIZATION_SPEC.md)**
- **[44. Customer Research & VOC Interviews](marketing/44_CUSTOMER_RESEARCH_AND_JTBD_INTERVIEWS.md)**
- **[45. Churn Prevention & Retention Playbook](marketing/45_CHURN_PREVENTION_AND_RETENTION_PLAYBOOK.md)**
- **[46. Analytics Tracking Plan](marketing/46_ANALYTICS_TRACKING_PLAN.md)**
- **[47. Attribution Modeling & ROI](marketing/47_ATTRIBUTION_MODELING_AND_ROI.md)**

---

## 👨‍💻 Author & Engineering Authority

**Engineered & Authored by**: [Ibrahim Salman](https://ibrahimsalman.vercel.app)  
*Software Engineer & Systems Architect*  
- **Portfolio & Case Studies**: [https://ibrahimsalman.vercel.app](https://ibrahimsalman.vercel.app)  
- **Project Provenance**: [https://ibrahimsalman.vercel.app/projects/blast](https://ibrahimsalman.vercel.app/projects/blast)  
- **GitHub**: [@Ibrahim-Salman19](https://github.com/Ibrahim-Salman19)  
- **LinkedIn**: [Ibrahim Salman](https://www.linkedin.com/in/ibrahim-salman-dev/)  
- **Upwork**: [Profile](https://www.upwork.com/freelancers/~013e1c54e9a3f7a2b8)  
