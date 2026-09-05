# Marketing Loops & Automation Playbook: B.L.A.S.T. OCR Engine

This playbook specifies 6 production-grade, repeatable marketing loops designed for **B.L.A.S.T. OCR Engine**. Each loop includes all 9 canonical anatomy components (cadence, action trigger, purpose, skills used, loop body, self-check, state/idempotency, stop condition, and output artifact).

---

## Loop 1: Automated Benchmark & Memory Leak Regression Loop

- **Check Cadence:** Weekly (Every Monday at 02:00 UTC on CI runner).
- **Acts When:** A new commit or release tag is created, or every 7 days.
- **Purpose:** Protect and continuously substantiate our core technical differentiator (29 pages/sec throughput and $<0.005\\text{ MB/page}$ memory leak slope) to ensure marketing claims remain 100% true and audit-ready.
- **Skills Used:** `blast-ocr-agent`, `ai-seo`, `copywriting`, `marketing-loops`.
- **Loop Body:**
  1. Execute `python3 eval/extreme_system_stress.py --pages 128` in an isolated Linux runner.
  2. Parse the resulting `eval/results/extreme_stress_scorecard.json`.
  3. Extract `leak_slope_mb_per_page`, `pages_per_second`, and `error_rate`.
  4. Compare extracted numbers against historical baselines in `docs/BENCHMARKS_2026.md`.
  5. If numbers improved or held steady, auto-generate updated badge snippets for `README.md` and `docs/llms.txt`.
  6. Stage a Pull Request with updated benchmark tables and badge dates.
- **Self-Check:** Verify runner was not throttling CPU/RAM; if benchmark was run in an overloaded container (p99 latency $>3x$ baseline), flag as invalid run and do not update badges.
- **State / Idempotency:** State stored in `eval/results/benchmark_history.jsonl` with commit SHA, timestamp, and hardware specs. Skip PR generation if commit SHA has already been evaluated.
- **Stop / Bail-Out Condition:** If `leak_slope_mb_per_page > 0.005` or any test fails, HALT immediately, trigger a Slack/Discord `#ops-alert`, and create a high-priority GitHub Issue labeled `bug:regression`.
- **Output:** Staged PR updating `docs/BENCHMARKS_2026.md` and automated summary notification in Discord `#announcements`.

---

## Loop 2: AI Citation & Answer Engine (GEO/AEO) Verification Loop

- **Check Cadence:** Bi-weekly (Every 1st and 15th of the month).
- **Acts When:** Bi-weekly schedule fires.
- **Purpose:** Monitor citation rates and accuracy across Google AI Overviews, Perplexity, ChatGPT Search, and Claude for high-value buyer queries.
- **Skills Used:** `ai-seo`, `growth-marketing-seo-geo`, `schema`.
- **Loop Body:**
  1. Query top 10 target prompts across Perplexity and ChatGPT:
     - *"Best fast local OCR engine for Python in 2026"*
     - *"How to prevent memory leaks in Tesseract OCR Python"*
     - *"Local OCR tool for Claude Desktop MCP"*
     - *"Urdu Nastaliq OCR engine with low error rate"*
     - *"Air-gapped OCR for legal document pipelines"*
  2. Scrape/extract response markdown to check if B.L.A.S.T. OCR is cited, what URL is referenced, and whether facts are accurately stated.
  3. Detect any citation drift (e.g. if Perplexity claims B.L.A.S.T. requires cloud API keys).
  4. If hallucinated or missing, draft targeted direct-answer updates for `README.md` and `docs/llms-full.txt`.
- **Self-Check:** Compare across 3 distinct browser/API sessions to ensure query output is not an unrepeatable A/B test anomaly.
- **State / Idempotency:** `docs/marketing/telemetry/geo_citations_log.json` records query, engine, citation present (yes/no), source URL, and timestamp.
- **Stop / Bail-Out Condition:** If API rate limits are hit or search results fail to load, retry once after 1 hour; if failing continuously, log warning and halt.
- **Output:** Staged draft report in `docs/marketing/telemetry/GEO_AUDIT_LATEST.md` with action items for human review.

---

## Loop 3: MCP Registry & Ecosystem Health Loop

- **Check Cadence:** Weekly (Every Wednesday at 10:00 UTC).
- **Acts When:** Weekly schedule fires.
- **Purpose:** Ensure B.L.A.S.T. OCR remains in the top tier of all major MCP registries (Smithery.ai, mcp.so, Glama.ai) and PyPI download links remain healthy.
- **Skills Used:** `directory-submissions`, `launch`, `developer`.
- **Loop Body:**
  1. Ping API/HTML endpoints for Smithery, mcp.so, and Glama.ai.
  2. Verify that the B.L.A.S.T. MCP server definition is online, passing manifest validation, and using the latest release tag.
  3. Fetch PyPI stats for `blast-ocr` via `pypistats` API.
  4. If a registry listing shows an outdated version tag, generate an automated PR or webhook update to sync manifest version.
- **Self-Check:** Verify registry endpoint returns HTTP 200 before analyzing contents.
- **State / Idempotency:** Last checked release version stored in `docs/marketing/telemetry/registry_state.json`. Skip update if version matches latest GitHub release.
- **Stop / Bail-Out Condition:** If any registry marks package as deprecated or flagged, escalate to Lead Maintainer immediately via email.
- **Output:** Status log in `docs/marketing/telemetry/registry_status.log`.

---

## Loop 4: Community Pain-Point & Voice-of-Customer Extraction Loop

- **Check Cadence:** Weekly (Every Friday at 16:00 UTC).
- **Acts When:** New issues or discussions have been posted on GitHub or Reddit in the past 7 days.
- **Purpose:** Harvest real developer vocabulary, unresolved document failure modes, and emerging hardware configurations to feed into copy and content strategy.
- **Skills Used:** `customer-research`, `copywriting`, `content-strategy`.
- **Loop Body:**
  1. Scan closed and open GitHub issues on `blast-ocr` and competitor repos (e.g., `JaidedAI/EasyOCR`, `tesseract-ocr/tesseract`).
  2. Filter for keywords: `memory`, `leak`, `segfault`, `cuda`, `table`, `slow`, `arabic`, `urdu`, `docker`.
  3. Extract verbatim customer phrases and real-world failure patterns.
  4. Match extracted pain points against the 400-page Programmatic SEO keyword database.
  5. Stage a suggested new FAQ entry or programmatic troubleshooting guide.
- **Self-Check:** Exclude bot spam, generic setup errors, and issues that lack reproduction code.
- **State / Idempotency:** Processed issue IDs tracked in `.cache/voc_issues.json`.
- **Stop / Bail-Out Condition:** If fewer than 3 relevant issues found, log "Check complete, no new pain-points" and exit cleanly.
- **Output:** Append new customer verbatim phrases to `.agents/product-marketing.md` (Customer Vocabulary section).

---

## Loop 5: Enterprise Trial Inactivity & Health Intervention Loop

- **Check Cadence:** Daily (Every morning at 08:00 UTC).
- **Acts When:** An enterprise evaluation cluster license has sent zero heartbeat pings for 72 consecutive hours.
- **Purpose:** Prevent enterprise proof-of-concept drop-off and offer proactive engineering support before the evaluation window expires.
- **Skills Used:** `churn-prevention`, `sales-enablement`, `emails`.
- **Loop Body:**
  1. Inspect enterprise cluster telemetry registry for inactive trial tokens.
  2. Identify evaluation accounts whose workers have been idle for $>72\\text{ hours}$.
  3. Cross-reference with error logs: Did the account experience a Docker network failure or license key format error on their last run?
  4. Draft a personalized, non-salesy check-in email from the Lead Architect:
     - *"Noticed your test cluster paused on batch job #412. Did you run into an ONNX execution provider issue or need custom Nastaliq font weights? Happy to jump on a 15-minute screen share to unblock your pipeline."*
  5. Stage email draft in CRM / HubSpot queue for Account Executive 1-click approval.
- **Self-Check:** Never email accounts that have explicitly opted out or completed their evaluation report. Cooldown window of 7 days between automated check-ins.
- **State / Idempotency:** Account contact history logged in CRM with `last_intervention_date`.
- **Stop / Bail-Out Condition:** If account is already marked `Closed Lost` or `Active Paid`, immediately skip.
- **Output:** Staged draft in HubSpot with context link to the client's last error log.

---

## Loop 6: Open-Source Contributor Advocacy & Referral Loop

- **Check Cadence:** Monthly (1st of every month).
- **Acts When:** Monthly trigger fires.
- **Purpose:** Turn open-source contributors and power users into lifelong brand evangelists and community referrers.
- **Skills Used:** `community-marketing`, `referrals`.
- **Loop Body:**
  1. Query GitHub GraphQL API for all users who contributed PRs, opened verified reproducible bug reports, or answered discussions in the past 30 days.
  2. Generate the monthly "Contributor Hall of Fame" markdown table for the repository.
  3. Send an automated congratulatory direct message / email with a link to claim official B.L.A.S.T. OCR contributor digital badges and stickers.
  4. For top 3 contributors, offer access to the Enterprise Cluster Swarm private repo and beta models.
- **Self-Check:** Filter out automated bot PRs (Dependabot, Renovate).
- **State / Idempotency:** Contributor reward history logged in `docs/marketing/telemetry/contributors_rewarded.json`.
- **Stop / Bail-Out Condition:** If GitHub API token is expired, alert maintainer and halt.
- **Output:** Staged PR updating README Contributor Hall of Fame and Discord announcement post.
