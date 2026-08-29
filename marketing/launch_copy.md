# Launch Copy

Drafted, not posted. Every number below is one of the five verified figures in this repo — nothing else is safe to add without a new committed result file:

- 18% lower mean CER (0.2338 → 0.1916, RapidOCR vs. the prior EasyOCR default)
- 7.7x lower CPU per-page latency (117.8s → ~15.3s/page)
- 0.0002 MB/page growth slope over a 1,000-page streaming stress test
- 677 automated tests, 675 passing / 2 skipped
- 14-page gold corpus, 40.4% fact-pass rate (19/47)

Source for all five: `eval/results/rapidocr_candidate.json`, `docs/adr/0005-phase3-engine-bakeoff.md`, `eval/results/stress_report.json`. No GPU number and no TEDS/table-accuracy number exist yet — don't add one to this copy without a real result to cite (see `docs/BENCHMARKS_2026.md` §5).

The corpus is small and the CPU latency is slow in absolute terms (~15.3s/page is not fast). Both are said out loud below rather than omitted — this audience will open the JSON either way, and getting there first reads as confidence, not weakness.

## Fixed: the live demo used to contradict this copy

The landing page's first feature card used to read "GPU-Accelerated Inference — Batched ONNX tensor inference with dynamic sizing for sub-second page latency" — the exact claim this document otherwise avoids (verified number is ~15.3s/page, single-stream, CPU; no GPU run exists in `eval/results/`). By the time this was caught, the function holding it (`render_landing_page()` in `blast_ocr/ui/web_app.py`) was no longer mid-edit, so it's fixed directly: the card now reads "ONNX Multi-Provider Inference — Batched ONNX Runtime execution with CUDA, DirectML, and CPU provider fallback," a capability claim rather than a speed claim. `tests/test_agent_marketing_and_mcp.py` still passes. The two screenshots in `assets/` were re-captured after this fix, so they match what the page now says.

## Measuring which channel actually worked

The Streamlit demo links below carry a `utm_source` per channel (hackernews / producthunt / reddit) because that page is yours — Streamlit's own request logs (or any analytics you add to the app later) can attribute a visit to the tag. **Don't tag the GitHub repo links the same way** — GitHub doesn't surface query-string UTMs anywhere, so a tagged repo link measures nothing. For the repo, the real signal is already free: **Insights → Traffic → Referring sites** on the GitHub repo shows `news.ycombinator.com`, `reddit.com`, etc. by domain automatically, no tagging needed. Check it a few days after each post goes up.

---

## Platform rules, checked before writing the rest of this file

**Hacker News**: the guidelines now say explicitly that HN is for conversation between humans and ask posters not to submit AI-generated text. The Show HN draft below was written by an AI (me, this session). **Read it, then rewrite it in your own words before posting** — don't paste it verbatim. Use it as the structure and the fact-checked numbers, not the final prose. Separately, Show HN specifically requires something people can try or inspect without a signup/email gate — the live demo and the public repo both already satisfy that.

**r/LocalLLaMA**: the community runs an informal "1/10th" norm — self-promotional posts should be a small fraction of an account's overall activity, and posts are expected to lead with technical substance over promotional language. If the posting account is new or has little history of genuine participation in the sub, a first-ever post being a launch announcement risks reading as pure self-promotion regardless of content quality. Worth having some real comment history there first if there isn't any yet.

**Product Hunt**: confirmed three hard requirements the draft below didn't originally account for —
1. The maker account must be **at least one week old** before it can launch a product — check this now, since it affects timing, not just copy.
2. Company accounts aren't allowed; it has to launch under a personal maker account.
3. **A gallery needs a minimum of two images** (a 240×240 square thumbnail plus at least one more), each under 3MB. There were none until this pass — `marketing/assets/landing_desktop.png` and `landing_mobile.png` (real screenshots of the live app, captured this session, Streamlit's own "Deploy" chrome bar cropped off) can serve as a starting gallery once the sub-second/GPU line above is fixed on the live page.
4. Best launch time is 12:01 AM Pacific, for whichever day gets chosen.

Field lengths below are all confirmed within PH's actual limits: product name 21/40 chars, tagline 54/60 chars, and — since PH's help docs give the *listing* description its own separate 500-char cap, distinct from the longer text allowed on the product's own page — a 420-char short description for the listing plus a longer full description for the page body.

---

## Show HN

**Title:**
`Show HN: B.L.A.S.T. – self-hosted OCR with a native MCP server for AI agents`

**Body:**

B.L.A.S.T. is a self-hosted OCR / document-intelligence pipeline (PDF, PPTX, scanned images → Markdown, DOCX, EPUB, dual-layer searchable PDF, structured JSON). MIT licensed, runs fully offline, no cloud calls.

The part I actually wanted to exist and couldn't find elsewhere: it ships a native MCP server, so Claude Desktop, Cursor, or any MCP-speaking agent can call `blast_ocr_process`, `blast_ocr_extract_tables`, `blast_ocr_extract_formulas`, and `blast_ocr_semantic_chunk` directly, plus LangChain and LlamaIndex document loaders for RAG pipelines.

On the OCR side, I run RapidOCR (ONNX) as the default engine after replacing an EasyOCR baseline — documented as a real bake-off, not a marketing table: on a 14-page gold corpus, mean CER went from 0.2338 to 0.1916 (18% lower) and per-page CPU latency from ~117.8s to ~15.3s (7.7x faster). Raw JSON and methodology: `eval/results/rapidocr_candidate.json`, ADR 0005.

Saying the quiet part: 15.3s/page is slow in absolute terms — this is a CPU bake-off between two engines, not a speed record. The corpus is 14 pages (I'd like it bigger). Fact-pass rate on hand-authored fact checks is 40.4%. No GPU throughput and no table-extraction (TEDS) accuracy number exist yet — I'm not going to make one up, they're listed as open gaps in `docs/BENCHMARKS_2026.md` instead of quietly omitted.

677 automated tests, 675 passing / 2 skipped, if that's a signal you care about.

Repo: https://github.com/Ibrahim-Salman19/OCR
Live demo (Streamlit, may need a moment to wake up): https://ocr-book.streamlit.app/?utm_source=hackernews&utm_medium=show_hn&utm_campaign=launch

Feedback, and especially "this benchmark methodology is wrong because X," welcome.

---

## Product Hunt

**Name** (21/40 chars):
`B.L.A.S.T. OCR Engine`

**Tagline** (54/60 chars):
`Self-hosted OCR with a native MCP server for AI agents`

**Short description** (for the listing card — 420/500 chars, PH's actual field limit):
`Self-hosted OCR/document-intelligence pipeline: PDFs, PPTX, and scanned images to Markdown, DOCX, EPUB, or searchable PDF. Fully offline, MIT licensed. Ships a native MCP server (Claude, Cursor) plus LangChain/LlamaIndex loaders, table extraction, LaTeX math, and PII redaction. The default engine (EasyOCR to RapidOCR) was swapped after a documented bake-off: 18% lower CER, 7.7x lower CPU latency. 677 automated tests.`

**Full description** (for the product page body, longer form is fine here):

B.L.A.S.T. turns PDFs, PPTX decks, and scanned images into Markdown, DOCX, EPUB, dual-layer searchable PDF, or structured JSON — entirely offline, MIT licensed, no API keys or cloud calls.

What makes it different from the usual OCR wrapper: a native Model Context Protocol (MCP) server, so Claude Desktop, Cursor, and other MCP agents can call it directly, plus LangChain and LlamaIndex loaders for RAG. It also does table extraction to Markdown/HTML, LaTeX math recognition, and forensic PII redaction (SSNs, cards, emails, API keys, IPs, IBANs) — useful if you're feeding sensitive documents into an agent pipeline and don't want them touching a third-party API in the first place.

Under the hood: RapidOCR on ONNX Runtime, swapped in after a documented bake-off against the previous EasyOCR default — 18% lower character error rate, 7.7x lower CPU latency, numbers and methodology committed in the repo, not just asserted. 677 automated tests.

Early-stage project (small benchmark corpus so far, actively growing it) — looking for people who'll actually try it against their own documents and tell me where it breaks.

Repo: https://github.com/Ibrahim-Salman19/OCR
Try it: https://ocr-book.streamlit.app/?utm_source=producthunt&utm_medium=launch&utm_campaign=launch

---

## Reddit — r/LocalLLaMA

**Title:**
`Self-hosted OCR engine with a native MCP server (offline, MIT) — real before/after numbers, not marketing copy`

**Body:**

Posting here because this sub tends to actually read the benchmark JSON instead of the headline, and I'd rather get that scrutiny before a bigger launch than after.

What it is: B.L.A.S.T., a self-hosted OCR/document-intelligence pipeline — PDF/PPTX/scanned images → Markdown, DOCX, EPUB, dual-layer searchable PDF, or structured JSON for RAG ingestion. Fully offline, MIT licensed. Ships a native MCP server (`blast_ocr_process`, `blast_ocr_extract_tables`, `blast_ocr_extract_formulas`, `blast_ocr_semantic_chunk`) plus LangChain/LlamaIndex loaders, so it's meant to sit directly in an agent or RAG pipeline rather than be a standalone OCR CLI you pipe output from.

The numbers, with sources, since I know this crowd checks:
- Swapped the default engine from EasyOCR to RapidOCR (ONNX Runtime) after an actual bake-off on a 14-page gold corpus: mean CER 0.2338 → 0.1916 (18% lower), per-page CPU latency ~117.8s → ~15.3s (7.7x faster). Raw result: `eval/results/rapidocr_candidate.json`, writeup in `docs/adr/0005-phase3-engine-bakeoff.md`.
- 1,000-page streaming memory test: 0.0002 MB/page growth slope, so it doesn't balloon RAM on long documents.
- 677 automated tests, 675 passing / 2 skipped.

What I'm *not* claiming: no GPU throughput number (only tested CPU so far), no table-extraction accuracy score yet (the TEDS evaluator exists and is unit-tested, but I haven't run it end-to-end on a real table corpus), and I haven't benchmarked it against Docling, Marker, or Surya on the same corpus — that's an open item, not a hidden one (tracked in `docs/BENCHMARKS_2026.md`). 15.3s/page is also just slow in absolute terms; if you need real-time, this isn't it yet.

Repo: https://github.com/Ibrahim-Salman19/OCR — happy to take corrections on the eval methodology, that's exactly the kind of feedback I'm short on as a solo project.
Live demo: https://ocr-book.streamlit.app/?utm_source=reddit&utm_medium=localllama&utm_campaign=launch

---

## First 72 Hours

The launch lives or dies on the first hour of comment response, not on the post copy — a solo dev who's asleep when the thread takes off loses most of the traffic window. Plan around that, not around writing more copy.

**Posting order** — stagger, don't dump all three in one sitting:
- Day 1, morning in US Eastern time (HN's most active window): post Show HN. Stay reachable for the next 3-4 hours minimum to answer every comment quickly — velocity of response in the first hour matters more than post quality at that point.
- Day 1 or 2: Product Hunt (best posted right at midnight PT, since PH's daily ranking window starts then).
- Day 2 or 3, *not* the same day as HN: r/LocalLLaMA. Spacing these out means a slow day on one channel doesn't read as "the launch flopped" and gives you bandwidth to actually answer comments on each instead of splitting attention three ways at once.

**Be reachable.** Block the posting day — no meetings, phone nearby. If a critical bug gets reported in a comment, fix and reply with a commit reference same-day if at all possible; visible responsiveness is worth more here than the fix being perfect.

**Pre-drafted replies to the questions that will come up** — write these once, in your own words, before posting, so you're not composing a defensive answer live under pressure:

1. *"15.3s/page is really slow, why would I use this?"* — Own it, don't argue: "Fair — that's single-stream CPU inference on ONNX, no batching enabled in this benchmark. The point right now isn't raw speed, it's that it runs fully offline with a native MCP server so it drops into an agent pipeline with no cloud call. Batching and GPU numbers are an open item, not benchmarked yet."
2. *"Why hasn't this been run against Docling/Marker/Surya?"* — "Wanted to ship numbers I'd actually measured rather than none. Marker alone pulls in torch + transformers + surya-ocr — multi-GB — and I'd rather do that comparison properly on a bigger box than rush a number I can't stand behind. Tracked as an open gap in docs/BENCHMARKS_2026.md, not hidden. Contributions welcome if you've got the RAM to spare."
3. *"14 pages is a tiny corpus — how do you know this generalizes?"* — "Agreed, it's small — I know that's a real limitation, not a strength I'm claiming. It's a real scanned book with mixed layout (headers, footers, index, chapter breaks), not synthetic text, so it's at least a realistic 14 pages. Growing the corpus is the top priority before I'd trust bigger claims myself."
4. *"Why self-host instead of just calling AWS Textract / Google Document AI?"* — "Mainly: no per-page cloud cost, no document leaving your machine (built-in PII redaction if you do send output onward), and it's meant to be called directly by an agent via MCP rather than glued together with a cloud SDK."

---

## Personal-network outreach email

There's no mailing list — this is a one-off email to actual people you know (past colleagues, other devs, people who'd genuinely find this useful), not the start of a newsletter program. Don't build recurring-send infrastructure on top of this; it's a single message, sent once, to a short hand-picked list.

**Subject:** Built a self-hosted OCR engine with an MCP server — would value your eyes on it

**Body:**

Hi [name],

I've been building B.L.A.S.T., a self-hosted OCR/document-intelligence pipeline (PDF/PPTX/scanned images → Markdown, DOCX, EPUB, searchable PDF), and just pushed it public: https://github.com/Ibrahim-Salman19/OCR

The part I think you'd find interesting: it ships a native MCP server, so it plugs straight into Claude Desktop, Cursor, or any agent workflow — plus LangChain/LlamaIndex loaders for RAG. Fully offline, MIT licensed.

I documented a real engine swap (EasyOCR → RapidOCR) with actual before/after numbers instead of marketing claims — 18% lower error rate, 7.7x lower latency, all in `eval/results/` if you want to check my methodology rather than take my word for it.

It's early — small benchmark corpus, a few known gaps I've written down rather than hidden (see `docs/BENCHMARKS_2026.md`) — so I'd genuinely value you trying it against a real document of yours and telling me where it breaks, more than a star or a share. Live demo if you don't want to install anything: https://ocr-book.streamlit.app/?utm_source=personal&utm_medium=email&utm_campaign=launch

Thanks for reading this far either way.

[your name]
