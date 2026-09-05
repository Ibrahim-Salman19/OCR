# Enterprise SMS & Operational Pipeline Notifications: B.L.A.S.T. OCR

**Document Version**: 3.0.0  
**Channel Profile**: Latency-Sensitive Enterprise Swarm Alerts & Mission-Critical Pipeline Notifications  
**Compliance Standards**: TCPA (US), A2P 10DLC (The Campaign Registry), CTIA Guidelines, GDPR / CASL  

---

## 1. SMS Channel Strategy: Operational Urgency vs. Email Nurture

Following the `sms` skill:
- **SMS is NOT for Newsletters**: SMS earns the right to interrupt because it achieves a 98% open rate within 3 minutes. Blasting promotional content burns phone numbers and spikes opt-out rates.
- **Where SMS Wins**: High-severity operational alerts, queue disaster failovers, batch ingestion completions for massive jobs (10,000+ pages), and urgent billing/dunning alerts.
- **Where Email Wins**: Technical whitepapers, onboarding documentation, changelogs, and weekly performance summaries.

---

## 2. Regulatory Compliance & Carrier Guardrails (Read First)

A single TCPA class-action settlement can run $5M to $40M. B.L.A.S.T. enforces strict compliance:

### 2.1 The 6 Non-Negotiable TCPA & 10DLC Rules
1. **Explicit Written Consent**: Phone numbers are collected only with an unchecked, explicit opt-in checkbox stating: *"I agree to receive urgent operational pipeline alerts from B.L.A.S.T. OCR. Message frequency varies. Msg & data rates may apply."*
2. **A2P 10DLC Campaign Registration**: Long-code phone numbers are registered under the *Account Notification / System Alert* campaign category with The Campaign Registry (TCR).
3. **Mandatory Sender ID**: Every single text begins with inline brand identification: `From B.L.A.S.T. OCR:` or `[BLAST-ALERT]:`.
4. **Instant STOP Handling**: Responding `STOP`, `UNSUBSCRIBE`, `CANCEL`, `END`, or `QUIT` automatically revokes consent and halts all outbound messages within 10 seconds.
5. **Instant HELP Handling**: Responding `HELP` immediately returns brand identity, support contact email, and unsubscribe instructions.
6. **Strict Quiet Hours**: Marketing or non-critical notifications are blocked before 9:00 AM and after 8:00 PM in the recipient's local time zone. Only P1 infrastructure outage alerts bypass quiet hours if explicitly opted-in.

---

## 3. Character Budget & Encoding Discipline (GSM-7 vs. UCS-2)

SMS is billed per 140-byte segment:
- **GSM-7 Characters**: Up to **160 characters** = 1 segment. Standard Latin characters, numbers, and basic punctuation.
- **UCS-2 Encoding (Emojis & Accents)**: Adding a single emoji (e.g. 🚨 or 🚀) drops the segment limit from 160 characters to **70 characters**, immediately doubling or tripling carrier costs.
- **Engineering Rule**: B.L.A.S.T. operational alerts use pure **GSM-7 alphanumeric characters** with ASCII brackets (e.g. `[ALERT]`, `[OK]`, `[WARN]`) to guarantee single-segment transmission.

---

## 4. Five Production Operational SMS Message Templates

### Template 1: P1 Swarm Worker Failure / Zombie Alert (Severity: High)
- **Character Count**: 154 characters (1 GSM-7 Segment)
- **Trigger**: Automated Zombie Reaper detects dead worker node or memory starvation.
- **Message Copy**:
  ```
  From BLAST OCR: [P1 ALERT] Worker node #4 (10.0.4.12) became unresponsive during batch #8421. Auto-failover initiated. Check logs: blast.dev/ops/8421
  ```

---

### Template 2: Dead-Letter Queue (DLQ) Threshold Breach (Severity: High)
- **Character Count**: 158 characters (1 GSM-7 Segment)
- **Trigger**: More than 50 poison pill documents quarantine in the DLQ within 10 minutes.
- **Message Copy**:
  ```
  From BLAST OCR: [WARN] DLQ threshold breached: 52 poisoned files quarantined in Redis queue. Inspection required. Reply STOP to opt out. blast.dev/dlq
  ```

---

### Template 3: Large Batch Ingestion Complete (Severity: Low / Informational)
- **Character Count**: 148 characters (1 GSM-7 Segment)
- **Trigger**: Batch job with > 5,000 pages finishes processing and multi-format export.
- **Message Copy**:
  ```
  From BLAST OCR: Batch #9021 complete! 12,450 pages processed in 7.1 min (29.2 pps). 0 memory leaks. Markdown & PDF ready: blast.dev/jobs/9021. Stop=optout
  ```

---

### Template 4: Security Hostile Input Gateway Alert (Severity: Medium)
- **Character Count**: 159 characters (1 GSM-7 Segment)
- **Trigger**: Hostile input gateway rejects a decompression bomb or spoofed magic byte file.
- **Message Copy**:
  ```
  From BLAST OCR: [SEC-WARN] Malicious payload rejected: 121MP decompression bomb detected from IP 192.168.1.45. File blocked. Logs: blast.dev/sec/trace
  ```

---

### Template 5: Mandatory Compliance HELP & STOP Responses
- **HELP Response (128 characters)**:
  ```
  BLAST OCR Alerts: For support email support@blast-ocr.dev or visit blast.dev/help. Msg&data rates apply. Reply STOP to cancel.
  ```
- **STOP Confirmation (92 characters)**:
  ```
  You have successfully unsubscribed from BLAST OCR alerts. You will receive no more messages.
  ```

---

## 5. Implementation Code: Twilio Python Alert Dispatcher

```python
# blast_ocr/notifications/sms_dispatcher.py
import os
from twilio.rest import Client

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID else None

def send_operational_alert(to_phone: str, message: str) -> bool:
    """Dispatches a compliant, single-segment operational alert."""
    if not client or not to_phone:
        return False
    
    # Enforce mandatory sender ID if omitted
    if not message.startswith("From BLAST OCR:"):
        message = f"From BLAST OCR: {message}"
        
    try:
        msg = client.messages.create(
            body=message,
            from_=TWILIO_FROM_NUMBER,
            to=to_phone,
            status_callback="https://api.blast-ocr.dev/v1/telemetry/sms-callback"
        )
        return msg.status in ["queued", "sent"]
    except Exception as e:
        # Fall back to logging; never crash the core OCR pipeline on alert failures
        print(f"[SMS ALERT FAILURE] {e}")
        return False
```
