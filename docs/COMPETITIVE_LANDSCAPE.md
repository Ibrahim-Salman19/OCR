# B.L.A.S.T. OCR — Competitive Landscape (2025–2026)

Research conducted August 2026 across 30+ sources (open-source repositories, vendor
documentation, published benchmarks, and independent comparisons). Vendor-published claims are
marked "(vendor)"; independently-reproduced numbers are marked "(3rd-party)". Full source list
retained in session records; the summary and prioritized gap list below are what should drive
the roadmap.

## Executive summary

- **B.L.A.S.T.'s Tier-0 native-text-extraction bet is validated by the market, not a legacy
  shortcut.** Marker extracts the PDF text layer via `pdftext` before invoking any model;
  Gemini's API doesn't even charge tokens for natively-embedded PDF text; PyMuPDF's 2026
  position that VLMs are "solving the wrong problem" for born-digital PDFs is the extreme
  version of a pattern every serious pipeline now follows.
- **B.L.A.S.T.'s measured CER (~0.19) is in "poor" territory by general industry rules of thumb**
  (good ≈ 1–2%, poor ≈ >10%), roughly 3–6x worse than the ~0.03–0.07 normalized text-edit-distance
  top OmniDocBench systems post. This is the single most important number in this document —
  before trusting any other comparison, verify whether it reflects a genuinely hard/small gold
  corpus (14 pages) or a true quality gap.
- **Both of B.L.A.S.T.'s current OCR engines are explicitly described in 2026 guides as behind
  the frontier.** RapidOCR is called "the best lightweight choice" (praised for size, not
  accuracy); EasyOCR is described as having "fallen behind."
- **The field has converged on a tiered architecture**: native text → fast traditional OCR →
  confidence-gated VLM escalation → human review. B.L.A.S.T. has tiers 1–2 but no VLM escalation
  tier and no confidence signal to drive routing — the single biggest architectural gap versus
  the current state of the art.
- **B.L.A.S.T.'s "Book Intelligence" layer (header/footer stripping, dehyphenation, EPUB export)
  is a genuinely rare, defensible niche.** No major general-purpose player (Docling, Marker,
  Unstructured, MinerU) productizes "scanned book → clean EPUB." The closest analog is
  `pdf-craft` (6.1k★, MIT, DeepSeek-OCR-based) — small and young, proving the niche is real but
  not yet owned by anyone.
- **Sub-1B/sub-3B specialist VLMs now beat both classic pipelines and frontier chat models on
  document benchmarks** — e.g. PaddleOCR-VL-1.6 (0.9B) scores 96.34 on OmniDocBench v1.6 vs.
  GPT-4o's 85.80. "Small/CPU-friendly" and "accurate" are no longer mutually exclusive, which
  undercuts a purely CPU-only positioning as a differentiator on its own.
- **~15s/page CPU-only is slow in absolute terms** (a 300-page book ≈ 75 minutes) and should be
  benchmarked against PaddleOCR/PP-StructureV3's CPU-optimized path, the most relevant
  apples-to-apples comparator.
- **No table-structure metric (TEDS) anywhere in the eval harness** — every credible 2026
  benchmark treats tables as a first-class, separately-scored capability.
- **No confidence/uncertainty signal on the Document/Page/Block/Line/Span model** blocks the
  standard "route low-confidence output to human review" pattern every commercial competitor
  supports.
- **A durable job queue is no longer excusable by "we're OSS, not SaaS."** Docling itself ships
  `docling-serve` with Redis-queue orchestration and async polling — proof that even self-hosted
  OSS tools are expected to have a production deployment story. (This gap is now closed — see
  docs/adr/0010.)
- **Licensing clarity is a nearly-free differentiator.** Marker splits Apache-2.0 code from AI2
  OpenRAIL-M weights (revenue-capped); MinerU requires a commercial license above 100M MAU/$20M
  revenue. A clean MIT license across code (B.L.A.S.T. has this) is something to message clearly
  rather than assume is obvious.

## Comparison table

### Open-source / self-hostable pipelines

| Tool | Accuracy signal | Speed signal | License | Key differentiator |
|---|---|---|---|---|
| **Docling** (IBM) | 50.3% olmOCR-bench (3rd-party) | ~2.1 pages/sec | MIT | Broadest format coverage, 64.7k★, has a production job-queue story |
| **Marker** (datalab-to) | 76.0% balanced / 83.5% born-digital olmOCR-bench (3rd-party) | 2.9–23.7 pages/sec (GPU) | Code Apache-2.0; weights AI2 OpenRAIL-M | Best speed/accuracy tradeoff among OSS pipelines in multiple 2026 head-to-heads |
| **MinerU** (OpenDataLab) | 72.7% olmOCR-bench; MinerU2.5-Pro tops OmniDocBench v1.6 base | Slower than Marker/page | Apache-derived, commercial license above 100M MAU/$20M rev | 77.5k★, best-in-class CJK layout/formula handling |
| **PaddleOCR / PP-StructureV3** | PaddleOCR-VL-1.6 (0.9B): 96.34 OmniDocBench v1.6, beats GPT-4o (85.80) | Engineered for CPU efficiency | Apache-2.0 | ~86k★; only credible CPU-first path that's also near-frontier accuracy |
| **RapidOCR** *(B.L.A.S.T. default)* | No independent CER leaderboard; called "usable" but behind VLMs in one video-OCR study | Recommended for lightweight/CPU deployment | Apache-2.0 | Best-regarded lightweight/CPU engine — positioned as lightweight, not accuracy-leading |
| **pdf-craft** | No independent leaderboard | GPU-accelerated, local | MIT | Closest direct competitor to Book Intelligence niche: scanned-book→EPUB with header/footer stripping + TOC; 6.1k★, small/young |
| **olmOCR** (Ai2) | 82.4±1.1 on its own bench; preferred over Marker/MinerU in pairwise eval | GPU required | Apache-2.0 | Its benchmark (olmOCR-bench) is a de facto standard others report against |

### Commercial / cloud APIs

| Tool | Accuracy signal | Pricing | Key differentiator |
|---|---|---|---|
| **AWS Textract** | 94.2% independent 100-doc test | $1.50/1K text → $50/1K forms | Best table structure extraction |
| **Google Document AI** | 95.8% independent 100-doc test | $0.65/1K → $30/1K, down to $0.0006/page at scale | Cheapest hyperscaler entry price |
| **Azure AI Document Intelligence** | "99%+" prebuilt (vendor) | $1.50/1K → $30/1K | Fast custom-model training (~30 min, 5 samples) |
| **Mistral OCR (v3→v4)** | OCR4: 93.07 OmniDocBench | $2/1K standard, $1/1K batch | Fastest-iterating product in this research; reshaping market price floor |
| **ABBYY** | 99.8% printed / ~95% handwriting (vendor) | ~$0.02–0.10/page enterprise | Legacy category leader, most exposed to VLM disruption |
| **LlamaParse** | Vendor's own ParseBench | $0.01875/page agentic tier | Cheaper than Textract at most tiers |

### Frontier VLMs (fastest-moving category)

| Tool | Accuracy signal | License |
|---|---|---|
| **Gemini 3 Flash/Pro** | #1 OCR Arena AND near-top OmniDocBench (90.1–90.33) — rare double leader | Proprietary |
| **GPT-5.2 / Claude Opus 4.6** | Top-4 OCR Arena, strong on printed media/handwriting | Proprietary |
| **Qwen3-VL** | OCRBench ~85–90%; DocVQA ~91–96% | Apache-2.0, open-weight |
| **Small specialist VLMs** (PaddleOCR-VL, GLM-OCR, dots.ocr, DeepSeek-OCR, MinerU2.5-Pro) | Several top OmniDocBench outright, beating GPT-4o | Mostly MIT/Apache — the cluster to study most closely |

## The VLM-vs-traditional-OCR debate

Two paradigms: "OCR-1.0" (detector → recognizer → post-processor, errors compound across
stages — B.L.A.S.T.'s current tier) vs. "OCR-2.0" (a single vision-encoder+language-decoder
model). Benchmarks *disagree with each other*: on metric-based OmniDocBench, small specialist
VLMs beat both classical pipelines and GPT-4o; on human-preference-based OCR Arena, general
frontier chat models lead instead. There is no single "OCR accuracy in 2026" number — the right
comparator depends on whether structural/textual fidelity (closer to B.L.A.S.T.'s archival case)
or human-perceived usefulness matters more for the use case.

Economics have shifted too: Mistral OCR batch pricing ($1/1,000 pages) undercuts raw hyperscaler
OCR, and self-hosted small VLMs reportedly break even against Textract around 50–100K pages/month
— meaning "CPU-only, no GPU" is no longer the only path to low cost per page.

**The one place deterministic OCR still wins outright: hallucination risk.** Every production-VLM
source flags the same failure mode — a VLM can produce "plausible text that is absent from the
image," a fundamentally worse failure than a classical visually-similar misread. This matters
disproportionately for B.L.A.S.T.'s archival/book use case, which has far lower tolerance for
silent fabrication than a "chat with your PDF" use case. This is a legitimate reason to keep a
deterministic core — **but only if that core is actually accurate**, which loops back to the
CER-0.19 finding above. Slow + deterministic + inaccurate has no defensible position;
slow + deterministic + accurate has a genuinely strong one for this specific niche.

## Prioritized gaps (highest impact first)

1. **Diagnose and close the CER gap** (0.19 vs. "poor" threshold ~0.10) — determine whether it
   reflects the engine, a hard corpus, or a small-sample artifact. Gates the credibility of every
   other accuracy claim this project makes.
2. **Add a confidence-gated Tier-2 VLM escalation path** using an open-weight small specialist
   model (PaddleOCR-VL, dots.ocr, DeepSeek-OCR — all MIT/Apache-class, self-hostable). Aligns
   with the dominant 2026 architecture without forcing a cloud dependency.
3. **Add table extraction + TEDS scoring to the eval harness.** The largest specific methodology
   gap versus every referenced benchmark.
4. **Add per-span confidence scores to the Document/Page/Block/Line/Span model.** Unlocks
   human-review routing and gap #2's escalation logic simultaneously; RapidOCR/EasyOCR already
   emit per-detection confidence, so this is mostly data-model plumbing.
5. **Publish on OmniDocBench and/or olmOCR-bench directly; expand the gold corpus by an order of
   magnitude.** Both ship runnable harnesses already used by direct competitors — the fastest way
   to convert every quality claim from "trust us" to a checkable number on a shared test.
6. ~~Build a minimal async job queue.~~ **Done** — Redis + RQ durable queue shipped, see
   docs/adr/0010.
7. **Add bounded formula/equation extraction with CDM-style scoring** if academic/technical books
   are in scope.
8. **Verify non-Latin-script/RTL support explicitly** — the XY-cut/line-clustering layout logic
   has embedded LTR assumptions that may silently break on Arabic/Hebrew/vertical Japanese even
   if the OCR engine nominally supports the language.
9. **Benchmark the ~15s/page CPU figure against PaddleOCR/PP-StructureV3's CPU-optimized path** —
   the most relevant apples-to-apples comparator, not EasyOCR.
10. **Message the MIT license clearly** — nearly free; directly exploits real confusion around
    Marker's split licensing and MinerU's revenue cap.
11. **Add handwriting detection-and-flag (route to Tier-2) rather than a dedicated handwriting
    model.** Books commonly contain marginalia/inscriptions; flagging beats silently mis-OCRing.
12. **Make a deliberate scope decision on chart/figure understanding and state it explicitly** —
    lowest priority for the book niche specifically, but competitors increasingly treat it as
    standard.

## Methodology note

B.L.A.S.T.'s eval methodology is directionally well-aligned with industry practice: Kendall's
tau for reading order is an established academic technique, and "fact-check pass rate" is
conceptually close to Ai2's olmOCR-bench "unit test" philosophy (a deliberate move away from
edit-distance-only scoring, which doesn't correlate well with practical usefulness). The real gap
is scale — OmniDocBench uses 1,355+ pages, olmOCR-bench ~8,400 unit tests; a 14-page custom
corpus cannot credibly claim comparability without either much larger N or a run on the public
benchmarks themselves (gap #5 above).
