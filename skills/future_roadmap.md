---
name: Future Roadmap
description: Strategic outlook for upgrading B.L.A.S.T. to Next-Gen OCR technologies (2026+).
---

# Future Roadmap: Next-Gen OCR

## 1. The Shift to VLMs (Vision-Language Models)
Traditional pipelines (`Detection -> Recognition`) are being replaced by End-to-End Transformers.

### Candidate: Surya OCR
- **Why**: 90+ languages, accurate table/layout analysis.
- **Tech**: Segformer + GNNs.
- **Pros**: Handles complex formatting better than EasyOCR.
- **Migration**: Drop-in replacement for layout analysis.

### Candidate: GOT-OCR 2.0
- **Why**: "General OCR Theory". Unified model for text, formulas, music, and charts.
- **Use Case**: Scientific papers, complex PDFs.
- **Cons**: High VRAM requirement (580M params).

## 2. Pipeline Evolution
- **Current**: `PDF -> Image -> EasyOCR`.
- **Future**: `PDF -> LayoutLM (Classification) -> Component OCR`.
  - Classify page zones (Text, Table, Image).
  - Route Tables to specific table-transformers.
  - Route Text to fast OCR.

## 3. Tooling Upgrades
- **Switch to `uv`**: Migrate CI/CD pipeline.
- **Switch to `Ruff`**: Enforce stricter rules (E, F, I, UP) to modernize syntax automatically.
