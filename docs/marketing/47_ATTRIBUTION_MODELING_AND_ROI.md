# Marketing Attribution Modeling & Unit Economics (LTV:CAC): B.L.A.S.T. OCR

**Document Version**: 3.0.0  
**Attribution Methodology**: W-Shaped Multi-Touch Attribution for B2B & Developer Infrastructure  
**Core Financial Metrics**: Blended CAC, Paid CAC, Payback Period, Net Revenue Retention (NRR), LTV:CAC Ratio  

---

## 1. Why Single-Touch Attribution Fails for Developer Infrastructure

Developer and enterprise infrastructure software journeys are non-linear, multi-stakeholder, and multi-session:
- An AI engineer discovers B.L.A.S.T. through an open-source GitHub release or technical Reddit post (**First Touch**).
- They benchmark the ONNX engine locally and test the Streamlit demo (**Lead Creation Touch**).
- They share the benchmark numbers with their Engineering Director during a sprint planning meeting.
- The Engineering Director downloads the whitepaper and attends a technical webinar (**Nurture Touch**).
- The VP of Engineering requests an enterprise pilot call via Google Search (**Opportunity Creation Touch**).
- The legal team requires an air-gapped security audit before signing a $24,000 annual contract (**Closed-Won Touch**).

If we used **First-Touch Attribution**, Google Search and the sales deck get 0% credit. If we used **Last-Touch Attribution**, the open-source GitHub repo, benchmarks, and Reddit posts get 0% credit and get defunded.

---

## 2. The W-Shaped Multi-Touch Attribution Model

B.L.A.S.T. implements the **W-Shaped Attribution Model**, weighting the three key transition milestones while distributing remaining credit to intermediate nurture touchpoints:

```
First Touch (Discovery)           Lead Creation Touch           Opportunity Creation
        [40%]                           [20%]                         [40%]
          │                               │                             │
          ▼                               ▼                             ▼
   GitHub / Blog ──► Docs / Benchmark ──► Demo / SDK ──► Whitepaper ──► Enterprise RFP
                           ▲                                ▲
                           │                                │
                       [Nurture]                        [Nurture]
                     (Split ~10%)                     (Split ~10%)
```

### Milestone Weights:
1. **First Touch (30% Credit)**: First anonymous site visit, GitHub star, or documentation page load. (Measures brand discovery).
2. **Lead Creation Touch (30% Credit)**: The session where the user clones the repo, installs the pip package, or creates an account.
3. **Opportunity Creation Touch (30% Credit)**: The moment an enterprise trial, demo request, or RFP form is submitted.
4. **Middle Touchpoints (10% Shared Credit)**: Webinar views, changelog reads, Discord questions, and email opens occurring between the major milestones.

---

## 3. Unit Economics & ROI Formulas

### 3.1 Blended Customer Acquisition Cost (CAC)
Measures total sales and marketing expenditure divided by total new acquired customers (organic + paid):

$$	ext{Blended CAC} = rac{	ext{Total Marketing Spend} + 	ext{Total Sales & SDR Spend} + 	ext{Tooling Costs}}{	ext{Total New Customers}}$$

- **Target Blended CAC (Self-Serve Pro)**: **$85.00**
- **Target Blended CAC (Enterprise Fleet)**: **$3,200.00**

### 3.2 Paid CAC
Isolates paid advertising spend against customers acquired directly through paid media clicks:

$$	ext{Paid CAC} = rac{	ext{Google Ads Spend} + 	ext{LinkedIn Ads Spend} + 	ext{Ad Creative Agency/Tool Fees}}{	ext{Paid Attributed Customers}}$$

- **Target Paid CAC**: **< $140.00** (Self-Serve Pro), **< $4,500.00** (Enterprise Fleet)

---

### 3.3 Customer Lifetime Value (LTV) Calculation
For recurring concurrency subscriptions:

$$	ext{LTV} = rac{	ext{Average Revenue Per Account (ARPA)} 	imes 	ext{Gross Margin \%}}{	ext{Monthly Churn Rate}}$$

#### Example Parameters:
- **Enterprise Fleet**: ARPA = $2,000/mo ($24,000/yr), Gross Margin = 85% (software license / self-hosted infrastructure), Monthly Churn = 1.0% (Annualized Churn ~11.4%).
$$	ext{LTV} = rac{\$2,000 	imes 0.85}{0.01} = \mathbf{\$170,000.00}$$

---

### 3.4 LTV:CAC Ratio Benchmarks

$$	ext{LTV:CAC Ratio} = rac{\$170,000}{\$3,200} = \mathbf{53.1:1} \quad (	ext{Enterprise})$$
$$	ext{LTV:CAC Ratio} = rac{\$1,020}{\$120} = \mathbf{8.5:1} \quad (	ext{Pro Self-Serve})$$

- **< 1:1**: Losing money rapidly (unsustainable).
- **1:1 to 2.5:1**: Underperforming, marketing spend inefficient.
- **3:1 to 5:1**: **Healthy SaaS target zone**.
- **> 5:1**: Highly efficient engine — under-investing in acquisition; opportunity to aggressively scale paid ads and content.

---

### 3.5 CAC Payback Period (Months to Cash Breakeven)

$$	ext{Payback Period (Months)} = rac{	ext{CAC}}{	ext{ARPA} 	imes 	ext{Gross Margin \%}}$$

- **Self-Serve Pro Tier** ($99/mo, $85 CAC):
  $$	ext{Payback} = rac{\$85}{\$99 	imes 0.90} = \mathbf{0.95 	ext{ months}} \quad (	ext{Instant Payback})$$
- **Enterprise Fleet** ($2,000/mo, $3,200 CAC):
  $$	ext{Payback} = rac{\$3,200}{\$2,000 	imes 0.85} = \mathbf{1.88 	ext{ months}} \quad (	ext{Target} < 12 	ext{ months})$$

---

## 4. Channel Attribution Matrix & Spend Allocation

| Marketing Channel | Attribution Role | Primary W-Weight | Cost Profile | Target Payback | 2026 Budget Share |
|---|---|:---:|---|:---:|:---:|
| **GitHub Organic & Open-Source** | First Touch (Discovery) | 35% | Low (Engineering labor) | Immediate | 30% |
| **Technical Content & Programmatic SEO** | Lead Creation (Evaluation) | 25% | Low (Creation cost) | < 3 months | 20% |
| **Google Search Ads (High-Intent)** | Opportunity Creation | 20% | High ($4.00 CPC) | < 6 months | 25% |
| **LinkedIn ABM (Enterprise Decision Makers)**| Opportunity Creation & Nurture | 10% | High ($8.50 CPC) | < 9 months | 15% |
| **Co-Marketing & Vector DB Integrations** | First Touch & Nurture | 10% | Medium (Partner time) | < 4 months | 10% |

---

## 5. Attribution Review Cadence & Reporting

1. **Weekly Acquisition Sync (30 min)**: Review channel-by-channel top-of-funnel conversion rates, cost per click, and git clone / pip install volume.
2. **Monthly Cohort Reconciliation (60 min)**: Match closed-won enterprise contracts back to original first-touch referrers using W-shaped CRM weights. Adjust Google and LinkedIn ad budgets based on CAC payback.
3. **Quarterly LTV & NRR Recalibration**: Update cohort retention curves, churn rate inputs, and expansion revenue to ensure LTV:CAC remains in the 5:1 to 8:1 range.
