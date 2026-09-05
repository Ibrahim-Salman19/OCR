# Churn Prevention, Cancellation Flow & Retention Playbook: B.L.A.S.T. OCR

**Document Version**: 3.0.0  
**Framework**: 3-Tier Retention Architecture (Predictive Signal Detection, 3-Step Cancellation Flow, Involuntary Dunning Recovery)  
**Target Churn Rates**: Net Revenue Retention (NRR) >= 120%, Monthly Logo Churn <= 1.5%  

---

## 1. The Anatomy of Churn in Developer & Document AI Platforms

Churn in infrastructure and developer tools follows two distinct failure modes:
1. **Voluntary Churn (60%)**: Developer runs into an edge case (unsupported language, complex table geometry, OOM failure on a weird PDF) or finishes a temporary project migration.
2. **Involuntary Churn (40%)**: Expired credit cards, corporate spending card limits, or transient payment gateway network errors.

---

## 2. Predictive Churn Early Warning Signals (Health Telemetry)

Rather than waiting for a cancellation request, B.L.A.S.T. monitors customer usage telemetry to intervene while the customer is still salvageable:

| Telemetry Signal | Trigger Condition | Churn Risk | Automated Intervention Playbook |
|---|---|:---:|---|
| **Usage Drop-Off** | Processed pages drop by > 50% week-over-week for 2 consecutive weeks | High | Trigger automated check-in email from Customer Engineering: "Did your batch complete, or did you hit a processing bottleneck?" |
| **Repeated Processing Errors** | Error rate exceeds 5% of batch tasks (e.g. `CorruptedDocumentError` or unhandled layout exceptions) | Critical | Automated Slack/Webhook notification to On-Call Solutions Engineer to inspect log trace and offer a custom pre-processor filter within 4 hours. |
| **API Key Inactivity** | Zero REST API or CLI requests in 14 consecutive days after activation | Moderate | Send contextual email: "New RapidOCR ONNX model update: 18% lower CER on complex documents." |
| **Export Format Stagnation** | Customer only uses `txt` output, ignoring `markdown`, `pdf`, and `docx` | Low | Send interactive tutorial: "How to extract structured tables directly into Notion and Excel." |

---

## 3. The 3-Step In-App Cancellation Flow & Save Offers

When an enterprise customer or pro subscriber clicks "Cancel Subscription" in the dashboard, the cancellation flow must respect the user while intelligently presenting targeted alternatives:

```
[User Clicks "Cancel Plan"]
           │
           ▼
┌─────────────────────────────────────────┐
│ STEP 1: Reason Discovery Survey         │
│ (Single-select + optional text area)    │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ STEP 2: Conditional Save Offer          │
│ (Dynamically matched to stated reason)  │
└─────────────────────────────────────────┘
           │
     ┌─────┴────────────────┐
     ▼                      ▼
[Accepts Offer]       [Declines Offer]
     │                      │
     ▼                      ▼
Stay Active           ┌─────────────────────────────────────────┐
                      │ STEP 3: Graceful Exit & Data Preservation│
                      │ (Confirmation, grace period date, data) │
                      └─────────────────────────────────────────┘
```

### 3.1 Step 1: Exit Survey Reasons
1. `Completed my one-time document migration / project finished`
2. `Encountered formatting or accuracy issues with complex documents`
3. `Too expensive / cannot justify cost for current volume`
4. `Switching to another solution or cloud provider`
5. `Downsizing team / technical architecture changed`

---

### 3.2 Step 2: Dynamically Matched Save Offers

#### Scenario A: Reason is "Project Finished / Seasonal Need"
- **Save Offer**: **Account Pause for up to 90 Days**
- **Copy**:
  > "Need a break between batch runs? Instead of canceling and reconfiguring your API keys, worker swarm, and custom dictionary models, pause your subscription for up to 3 months.  
  >  
  > We will preserve your custom schemas, API credentials, and priority queue configurations with zero monthly charges. You can unpause anytime with one click."
- **Action Buttons**: `[Pause Account for 60 Days]` | `[Continue to Cancel]`

#### Scenario B: Reason is "Accuracy or Document Formatting Issues"
- **Save Offer**: **Complimentary 1-on-1 Engineering Support & Custom Pre-Processor**
- **Copy**:
  > "Document OCR can be tricky with degraded scans and non-standard tables.  
  >  
  > Let our Core Engine engineers look at your edge-case documents under a strict NDA. We will configure custom CLAHE pre-processing, aspect-ratio bucketing, or fine-tune layout thresholds specifically for your document corpus."
- **Action Buttons**: `[Book 30-Min Engineering Call]` | `[Continue to Cancel]`

#### Scenario C: Reason is "Too Expensive / Cost Concerns"
- **Save Offer**: **Concurrency Downgrade or 50% Off for 2 Months**
- **Copy**:
  > "We understand budget constraints. If you don't need full 16-worker concurrency right now, switch to our Starter Concurrency tier at $99/mo, or take 50% off your current plan for the next two billing cycles while you scale."
- **Action Buttons**: `[Apply 50% Discount for 2 Months]` | `[Downgrade Plan]` | `[Continue to Cancel]`

---

### 3.3 Step 3: Graceful Exit & Offboarding
If the user still declines all save offers:
- Confirm cancellation immediately with zero dark patterns.
- Display exact end-of-billing-cycle date: "Your access remains active through October 31, 2026."
- Guarantee data preservation: "Your configurations, API keys, and local models remain saved for 180 days should you choose to reactivate."
- Provide one-click reactivate button.

---

## 4. Involuntary Churn & Dunning Playbook (Payment Recovery)

Failed payments account for up to 40% of SaaS churn. B.L.A.S.T. implements an automated 14-day smart retry and multi-channel dunning cadence via Stripe / webhook automations:

| Day | Action & Channel | Mechanism | Message / Notification Copy |
|:---:|:---|:---|:---|
| **-7** | Pre-Dunning Email | Automated Stripe card expiry check | *Subject: Your payment card on file for B.L.A.S.T. OCR expires this month.* Friendly reminder to update card before billing renewal to prevent worker swarm interruptions. |
| **Day 0** | Soft Retry + In-App Toast | Smart gateway retry algorithm | *In-App Toast*: "Payment processing failed. We will automatically retry tomorrow. Update card details here." |
| **Day 3** | 2nd Retry + Email 1 | Gateway retry + transactional email | *Subject: Action Required: Update payment method for B.L.A.S.T. OCR.* Clear link to Stripe customer billing portal with 1-click update. No login wall. |
| **Day 7** | 3rd Retry + Email 2 + SMS | Gateway retry + SMS alert to billing contact | *Email & SMS*: "Warning: Your B.L.A.S.T. OCR worker swarm will be paused in 7 days due to unpaid balance. Update billing now to maintain production throughput." |
| **Day 14**| Final Attempt + Account Suspension | Grace period expiration | Worker queue transitions to read-only mode. Jobs paused in Redis priority queue. Email: "Your subscription is paused. Reactivate anytime to resume pending document batches." |

---

## 5. Post-Cancellation Win-Back Cadence

For churned customers who completed cancellation:

### Day 7: The Gentle Feedback Check-In
- **Subject**: *Quick question about your B.L.A.S.T. OCR experience*
- **Copy**: Short, personal note from the Lead Engineer asking 1 single question: "What was the single biggest feature missing from B.L.A.S.T. that would have made you stay?" Zero sales pressure.

### Day 30: Major Technical Milestone Announcement
- **Subject**: *Update: B.L.A.S.T. v3.0 released with 7.7x faster ONNX engine*
- **Copy**: Highlight recent technical improvements directly addressing common churn reasons (e.g. enhanced table extraction, KaTeX math parsing, native MCP integration). Include reproducible benchmark graphs.

### Day 60: The "Come Back" Re-Activation Incentive
- **Subject**: *Re-activate your B.L.A.S.T. OCR cluster with 2 months free*
- **Copy**: Targeted offer for inactive accounts: "Re-activate your subscription on an annual plan and get 2 months free + complimentary migration assistance."
