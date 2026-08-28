## 2026-08-28T19:46:51Z

User Request:
You are an elite Document Intelligence & Security Researcher exploring Domain 1: "PDF Structure & Corruptions".
Your working directory is: /mnt/d/code/Projects/Python/OCR_Book/.agents/explorer_d1_pdf_1
Your parent orchestrator is: 0ae5094f-3648-476a-b95b-8fffc76efe1a

Read /mnt/d/code/Projects/Python/OCR_Book/.agents/ORIGINAL_REQUEST.md first.

Objective:
Conduct exhaustive global research across academic literature, CVE databases (NVD, GitHub Security Advisories), PDF specifications (ISO 32000-1, ISO 32000-2 / PDF 2.0), and production engines (PyMuPDF / MuPDF, Poppler, PDFium, Adobe PDF SDK, Ghostscript, Docling, Marker) regarding PDF structural anomalies, corruptions, and security vectors.

Catalog AT LEAST 12 distinct, deeply analyzed failure modes / edge cases for Domain 1, specifically covering:
1. Linearized (Fast Web View) stream faults & truncated hint tables (causing out-of-bounds reads or infinite loops).
2. Broken / corrupt XREF tables & hybrid-reference files (XREF table vs XREF stream mismatches).
3. Cyclic / recursive object references (e.g. Page Tree cycles, Indirect Object loops causing stack overflows / recursion limits).
4. PDF Polyglots (PDF+ZIP, PDF+HTML, PDF+PostScript, PDF+PNG hybrids) and parser differential evasion.
5. Dual-layer font encoding conflicts (ToUnicode CMap vs /Encoding differences, missing /Differences, Type3 font glyph-to-char desynchronization).
6. PDF 2.0 object streams (compressed object streams `/ObjStm` with cross-reference streams `/XRef`, UTF-8 metadata strings, unencrypted wrapper doc in AES-256).
7. JBIG2 decode bombs & arithmetic coder memory corruption (e.g., CVE-2021-30860 FORCEDENTRY segment table integer overflows, JBIG2 dictionary symbol reuse bugs).
8. Truncated or corrupt Trailer dictionaries (`/Size`, `/Root`, `/Prev` missing or pointing to invalid byte offsets).
9. Incremental update overwrites & shadow attacks (malicious layers hiding or modifying original content).
10. Encrypted PDF permission bypasses & empty password standard security handler (`/Standard`) authentication glitches.
11. Embedded stream length tampering (`/Length` mismatch with actual stream stream/endstream delimiters).
12. Malformed FlateDecode / LZW stream decompression bombs and dictionary resets.

For EACH failure mode / edge case, provide:
- Unique Taxonomy ID (e.g., TAX-PDF-01 to TAX-PDF-12+)
- Descriptive Name & Technical Classification
- Root Cause Analysis (PDF specification mechanics, byte-level anomalies)
- Real-World Production Engine Failure Examples (how PyMuPDF, Poppler, Tesseract, Docling, etc. fail or crash)
- CVE / Advisory References if applicable
- Detection & Reproduction Mechanics (how to trigger or generate the fault)
- Recommended Defensive Validation & Mitigation Strategy

Deliverable:
Write your comprehensive domain report to `/mnt/d/code/Projects/Python/OCR_Book/.agents/explorer_d1_pdf_1/domain_1_pdf_failures.md`.
Write your handoff report to `/mnt/d/code/Projects/Python/OCR_Book/.agents/explorer_d1_pdf_1/handoff.md`.
Update your `progress.md` throughout.
Send a completion message to your parent orchestrator with the full summary and artifact paths.
