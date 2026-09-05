# Revenue Operations (RevOps) & Pipeline Management: B.L.A.S.T. OCR

**Document Version**: 3.0.0  
**Core Systems**: Canonical CRM (HubSpot / Salesforce), Redis Priority Queue Telemetry, Stripe Billing  
**Primary RevOps Mission**: Connect Marketing, Sales Engineering, and Customer Success into an aligned, automated revenue engine with < 5 minute speed-to-lead.  

---

## 1. Unified Lead Lifecycle Framework

Every prospective customer progresses through 7 deterministic lifecycle stages with strict ownership, entry criteria, and exit requirements:

| Lifecycle Stage | Stage Definition | Entry Criteria | Exit Criteria | Primary Owner | SLA / Cadence |
|---|---|---|---|---|---|
| **1. Subscriber** | Anonymous reader engaged with technical content | Opts into newsletter, GitHub release watch, or RSS feed | Provides corporate domain or downloads whitepaper | Marketing | Automated weekly digest |
| **2. Lead** | Known developer contact with identified corporate email | Submits email via SDK calculator, live demo, or whitepaper download | Passes explicit ICP firmographic fit filters | Marketing Ops | Auto-enriched via Clearbit / Apollo in 60s |
| **3. MQL** | Marketing Qualified Lead exhibiting high fit + buying intent | Reaches >= 65 points on 100-point scoring model | Sales Engineer accepts or rejects with reason code | Inbound SDR / Solutions Eng | **< 4 Business Hours** response SLA |
| **4. SQL** | Sales Qualified Lead with confirmed technical use case | Discovery call confirms budget, timeline, and document volume | Solution evaluation demo scheduled | Account Executive (AE) | Completed within **48 hours** |
| **5. Opportunity** | Active commercial pilot or formal contract evaluation | Security questionnaire submitted, pricing proposal delivered | Closed-Won (Signed Contract) or Closed-Lost (Loss Reason Logged) | AE + Solutions Architect | Multi-week enterprise deal cycle |
| **6. Customer** | Paying client running production worker clusters | Contract signed, Stripe billing active, worker keys issued | Expands nodes, renews contract, or churns | Customer Success / Tech Account Mgr | Weekly onboarding check-ins (first 30d) |
| **7. Evangelist** | Power user promoting B.L.A.S.T. in the community | High NPS (9-10), authored case study, active Discord MVP | Ongoing participation in advisory board | Developer Relations & CS | Quarterly roadmap preview briefings |

---

## 2. The 100-Point Predictive Lead Scoring Model

Leads are scored dynamically across three dimensions: **Explicit Fit**, **Implicit Intent**, and **Negative Disqualification**.

### 2.1 Explicit Fit Scoring (Max 40 Points)
- **Company Industry**:
  - LegalTech, Financial Services, Healthcare AI (+15 pts)
  - Enterprise Software, Data Platforms, Insurance (+10 pts)
  - E-Commerce, Consumer Services (+5 pts)
  - Personal Blogs, Generic Freelance (0 pts)
- **Company Size**:
  - 500 – 5,000 employees (+15 pts)
  - 50 – 499 employees (+10 pts)
  - 1 – 49 employees (+5 pts)
- **Job Title & Seniority**:
  - Head of AI, VP Engineering, CTO, Chief Compliance Officer (+10 pts)
  - Principal / Lead RAG Engineer, Architect (+8 pts)
  - Junior Developer, Student (+0 pts)

---

### 2.2 Implicit Behavioral Intent Scoring (Max 60 Points)
- **High-Intent Actions**:
  - Requested Enterprise Demo or RFP Call (+30 pts)
  - Ran Cloud OCR vs Local ROI Calculator with > 100,000 pages (+25 pts)
  - Downloaded Enterprise Architectural Decision Record Whitepaper (+15 pts)
  - Visited Pricing Page >= 3 times in 7 days (+15 pts)
  - Tested Streamlit Live Demo with a 50+ page document (+10 pts)
  - Copied Python SDK Quickstart code block (+5 pts)
  - Read `docs/BENCHMARKS_2026.md` (+5 pts)

---

### 2.3 Negative Disqualification Scoring (Deductions)
- Competitor domain email (e.g. `@abbyy.com`, `@aws.amazon.com`, `@google.com`) (-100 pts → Auto-Disqualify)
- Personal / Free webmail domains (e.g. `@gmail.com`, `@yahoo.com`, `@hotmail.com`) (-25 pts)
- Job seeker / Student keywords detected in title ("Student", "Intern", "Seeking Opportunities") (-50 pts)
- Inactive for > 60 days with zero touchpoints (-20 pts)
- Email bounced or flagged as invalid via Truelist / ZeroBounce (-100 pts)

### Scoring Threshold:
- **Score >= 65 Points**: Automatically promoted to **MQL** → Alerts routed to Solutions Engineering.
- **Score 35 – 64 Points**: Nurture Track → 5-stage automated engineering lifecycle sequence.
- **Score < 35 Points**: Low Priority / Self-Serve Open Source Community.

---

## 3. Lead Routing Decision Tree & Speed-to-Lead SLAs

Research confirms that contacting inbound enterprise leads within **5 minutes** produces a 21x higher qualification rate than waiting 30 minutes.

### 3.1 Routing Decision Tree:
```
Inbound Lead Identified
           │
           ▼
[Lead Score >= 65 AND Valid Corporate Domain?]
     ├── NO ──► Route to Self-Serve Open-Source Nurture
     └── YES ──► Check Account Size:
                  ├── Employees > 500 ──► Route to Senior Enterprise AE + Solutions Architect
                  ├── Employees 50 - 499 ──► Round-Robin to Mid-Market AE
                  └── Fallback ──► Head of Growth / Founder Alert
```

### 3.2 Strict Handoff SLAs:
1. **Initial Outreach**: Inbound MQL notification sent to assigned AE via Slack + CRM. First personal touch within **4 business hours** (Target: < 15 minutes).
2. **Accept / Reject SLA**: AE must update CRM status to `Accepted (SQL)` or `Rejected (Recycle)` within **48 hours**.
3. **Rejection Reason Code Required**: If rejected, AE must select a valid reason (`Budget < $10k`, `No active project`, `Timing > 6 months`, `Competitor locked`).

---

## 4. Pipeline Stage Management & Stage Hygiene

To maintain accurate revenue forecasting, deals cannot advance without meeting explicit exit criteria:

| Deal Stage | Required Stage Fields | Stale Alert Threshold |
|---|---|:---:|
| **Stage 1: Qualified Discovery** | Confirmed monthly page volume, current OCR stack, primary pain point | 14 days |
| **Stage 2: Technical Evaluation** | Benchmark test run on customer sample PDFs, accuracy threshold agreed | 21 days |
| **Stage 3: Security & Architecture Review** | Air-gapped deployment verified, NDA executed, legal review started | 14 days |
| **Stage 4: Commercial Proposal** | Concurrency tier selected, SLA terms specified, billing terms agreed | 10 days |
| **Stage 5: Negotiation & Legal** | Master Services Agreement (MSA) in redlines, order form sent | 14 days |
| **Stage 6: Closed-Won** | Signed contract uploaded, Stripe customer ID linked, welcome call booked | N/A |
| **Stage 7: Closed-Lost** | Formal loss reason logged, competitor chosen (if any), re-engagement date set | N/A |

### Stale Deal Automation:
If a deal remains in any stage for **2x the average stage duration**, an automated Slack alert triggers to the VP of Sales, and the deal is flagged for pipeline review. No silent push dates are permitted.
