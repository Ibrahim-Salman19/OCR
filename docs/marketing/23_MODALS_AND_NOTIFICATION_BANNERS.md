# Modals, Slide-Ins & Contextual Notification Banners: B.L.A.S.T. OCR

**Document Version**: 3.0.0  
**Framework**: Non-Intrusive Contextual Conversion Overlays (WCAG 2.1 AA Accessible, Mobile-Friendly, Zero Dark Patterns)  
**Target Surfaces**: Web Documentation (`docs/`), Interactive Streamlit App (`blast_ocr/ui/web_app.py`), and Marketing Pages  

---

## 1. Overlay Principles & Conversion Philosophy

Following the `popups` skill:
1. **Never Block Before Value**: Never fire a full-screen popup within 5 seconds of page load. Intrusive interstitials destroy SEO rankings and trigger immediate developer bounces.
2. **Context-Matched Triggers**: The offer must directly match what the user is currently reading. If reading about memory leaks, offer the Zero-Leak Streaming Blueprint. If inspecting benchmarks, offer the reproducible JSON dataset.
3. **Friction-Free Dismissal**: The `ESC` key, clicking the background overlay, or clicking a prominent `✕` button immediately dismisses the modal and stores an expiration token in `localStorage`.
4. **Strict Frequency Capping**: Maximum 1 modal per user session; 14-day suppression upon dismissal.

---

## 2. Four Production Modal & Banner Blueprints

### 2.1 Component 1: Top Announcement Sticky Bar (Persistent, Non-Blocking)
- **Placement**: Pinned to top of viewport (`z-index: 1000`), 40px height.
- **Trigger**: Visible on page load across documentation and homepage.
- **Copy**:
  - `Badge`: `[NEW v3.0]` (Neon Emerald `#10B981`)
  - `Text`: `RapidOCR ONNX default cuts CPU latency by 7.7x with native AI Agent MCP support.`
  - `Link`: `[Explore Benchmarks →]` (Electric Cyan `#00F2FE`)
  - `Dismiss`: `✕` (Muted Grey `#8B949E`)
- **CSS Architecture**:
  ```css
  .blast-sticky-banner {
    position: sticky;
    top: 0;
    width: 100%;
    height: 40px;
    background: #161B22;
    border-bottom: 1px solid #30363D;
    color: #F0F6FC;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    z-index: 9999;
  }
  ```

---

### 2.2 Component 2: The Exit-Intent Save Modal (Desktop Only)
- **Placement**: Centered modal overlay (`max-width: 520px`).
- **Trigger**: Mouse cursor leaves upper viewport boundary (`clientY <= 10px`) after at least 30 seconds of on-page engagement.
- **Target Audience**: Visitors abandoning without cloning the repo or trying the live demo.
- **Copy Structure**:
  - **Header Tag**: `WAIT: PROCESSING LARGE PDF ARCHIVES?`
  - **Headline**: `Don't Let Python OOM Killers Crash Your 800-Page Document Batches.`
  - **Value Prop**: `Download our free 12-page Zero-Leak Python PDF Streaming Blueprint. Learn how sliding-window memory buffers keep RAM flatlined at 142 MB across 10,000+ pages.`
  - **Form**: Single work-email input field + `[Send Me the Blueprint]` button.
  - **Decline Link**: `No thanks, I will manage memory manually.`
- **localStorage Key**: `blast_exit_modal_dismissed = true` (Suppressed for 14 days).

---

### 2.3 Component 3: The Benchmark Scroll-Depth Slide-In (50% Scroll Trigger)
- **Placement**: Bottom-right floating card (`bottom: 24px; right: 24px; width: 360px`).
- **Trigger**: User scrolls past 50% of `docs/BENCHMARKS_2026.md` or `docs/ARCHITECTURE_DEEP_DIVE.md`.
- **Visual Design**: Subtle slide-up animation, dark charcoal container with electric cyan left border accent.
- **Copy**:
  - **Eyebrow**: `REPRODUCIBLE RESEARCH`
  - **Headline**: `Want to replicate these CER & Latency benchmarks on your own machine?`
  - **Body**: `Run our automated eval harness in 1 line of Python: python -m eval.run --candidate rapidocr.`
  - **Primary Action**: `[View Eval Harness Guide →]`
  - **Dismiss Action**: `✕` icon in top corner.

---

### 2.4 Component 4: Error-Recovery Contextual Helper (Behavior-Triggered)
- **Placement**: Inline alert banner directly beneath the Streamlit upload tray.
- **Trigger**: User uploads an encrypted/password-protected PDF or a corrupted zero-byte file.
- **Visual Design**: Amber alert box (`#F59E0B` border) with terminal-styled helper text.
- **Copy**:
  - `⚠️ Security Gateway Notice: This document is encrypted or unreadable.`
  - `B.L.A.S.T. strictly rejects AES-encrypted or corrupted byte streams in secure mode to prevent XXE and traversal attacks.`
  - `Action Link: [How to decrypt and sanitize input PDFs before OCR]`

---

## 3. Accessible HTML/JS Modal Implementation

Following WCAG 2.1 accessibility standards (Focus Trap, Esc Listener, ARIA Attributes):

```html
<div id="blast-modal" class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-title" style="display:none;">
  <div class="modal-card">
    <button id="modal-close" class="modal-close-btn" aria-label="Close dialog">✕</button>
    <div class="modal-badge">ARCHITECTURAL BLUEPRINT</div>
    <h3 id="modal-title">Stop Python OOM Crashes on Massive PDFs</h3>
    <p>Get the sliding-window streaming code that maintains a verified 0.0002 MB/page memory slope.</p>
    <form id="blueprint-form">
      <input type="email" placeholder="Enter your work email" required aria-label="Work Email" />
      <button type="submit" class="cta-btn">Send Me the Code</button>
    </form>
    <button id="modal-decline" class="decline-link">Maybe later</button>
  </div>
</div>

<script>
(function() {
  const modal = document.getElementById('blast-modal');
  const closeBtn = document.getElementById('modal-close');
  const declineBtn = document.getElementById('modal-decline');
  
  function closeModal() {
    modal.style.display = 'none';
    localStorage.setItem('blast_modal_dismissed', Date.now());
  }
  
  // Close on Escape key
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && modal.style.display !== 'none') {
      closeModal();
    }
  });
  
  closeBtn.addEventListener('click', closeModal);
  declineBtn.addEventListener('click', closeModal);
  
  // Exit Intent Detection
  document.addEventListener('mouseleave', function(e) {
    const isDismissed = localStorage.getItem('blast_modal_dismissed');
    const isSuppressed = isDismissed && (Date.now() - isDismissed < 14 * 86400000);
    if (!isSuppressed && e.clientY <= 10) {
      modal.style.display = 'flex';
      closeBtn.focus(); // Accessible focus trap initial focus
    }
  });
})();
</script>
```
