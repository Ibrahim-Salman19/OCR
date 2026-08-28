## 2026-08-28T19:46:51Z

You are an elite Document Layout & Multi-Modal Structure Researcher exploring Domain 4: "Layout & Multi-Modal Structure".
Your working directory is: /mnt/d/code/Projects/Python/OCR_Book/.agents/explorer_d4_layout_1
Your parent orchestrator is: 0ae5094f-3648-476a-b95b-8fffc76efe1a

Read /mnt/d/code/Projects/Python/OCR_Book/.agents/ORIGINAL_REQUEST.md first.

Objective:
Conduct exhaustive global research across layout analysis literature (PubLayNet, TableBank, DocBank, ICDAR competitions), multimodal document AI models (LayoutLMv3, Nougat, Donut, Marker, Docling, Surya, Unstructured), and spatial document geometry regarding layout segmentation, reading order, table parsing, and multi-modal structure reconstruction failures.

Catalog AT LEAST 12 distinct, deeply analyzed failure modes / edge cases for Domain 4, specifically covering:
1. Multi-column overlapping bounding boxes & reading order topological sort failures (XY-Cut collapse, spanning headers causing column interleaving / text splicing).
2. Borderless nested tables & implicit gridlines (whitespace-only cell delimiters, cells spanning multiple visual rows/columns without demarcation, financial report misalignment).
3. Multi-page merged tables & spanning row splits (table header repetition, footers embedded inside data rows, multi-page cell continuation).
4. Mixed rotation within a single page (e.g. 90° rotated sidebar or table alongside 0° main text, upside-down 180° stamps, skew angles).
5. Inline complex mathematical formulas with nested sub/superscripts, matrices, fractions, and square roots interfering with line segmentation and OCR character bounding boxes.
6. Figure-caption spatial association failures (captions merged into body text or associated with the wrong figure/table).
7. Marginalia, running headers, running footers, and page numbers falsely injected into body text paragraphs.
8. Drop caps & decorative initial characters split from the parent word or misclassified as standalone figures.
9. Form fields & key-value pair misalignment (checkboxes, dotted underline leaders, multi-line key-value boxes).
10. Right-to-left layout reading order inversion (Hebrew/Arabic multi-column documents reading right-to-left columns vs left-to-right western parsers).
11. Text wrap around irregular non-rectangular polygonal images/shapes breaking rectangular bounding box assumptions.
12. Hierarchical section heading level misclassification (all caps body text detected as H1, font size variations across styles breaking markdown TOC generation).

For EACH failure mode / edge case, provide:
- Unique Taxonomy ID (e.g., TAX-LAY-01 to TAX-LAY-12+)
- Descriptive Name & Technical Classification
- Root Cause Analysis (spatial geometry algorithms, heuristic vs model-based segmentation limitations)
- Real-World Production Engine Failure Examples (how Marker, Docling, Unstructured, PDF-Extract-Kit, PyMuPDF fail)
- Evaluation Metrics Affected (TEDS score degradation, BLEU/ROUGE drop, Reading Order Edit Distance)
- Detection & Reproduction Mechanics
- Recommended Defensive Validation & Mitigation Strategy

Deliverable:
Write your comprehensive domain report to `/mnt/d/code/Projects/Python/OCR_Book/.agents/explorer_d4_layout_1/domain_4_layout_failures.md`.
Write your handoff report to `/mnt/d/code/Projects/Python/OCR_Book/.agents/explorer_d4_layout_1/handoff.md`.
Update your `progress.md` throughout.
Send a completion message to your parent orchestrator with the full summary and artifact paths.
