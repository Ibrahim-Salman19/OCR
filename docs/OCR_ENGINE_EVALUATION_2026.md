# OCR Engine Evaluation (April 2026)

This document captures a web-backed, code-aware evaluation of OCR engine options for B.L.A.S.T. with a CPU-only deployment target.

## Scope and Decision Context

- Primary objective: maximize runtime reliability for production OCR.
- Constraint: no GPU available (CPU-only operation required).
- Constraint: do not break current pipeline/output contracts.
- Constraint: Streamlit Community Cloud deployment behavior must remain stable.

## Snapshot Date

- Evaluation date: 2026-04-06.

## Sources Used

- EasyOCR package metadata: `https://pypi.org/project/easyocr/`
- PaddleOCR package metadata: `https://pypi.org/project/paddleocr/`
- RapidOCR package metadata: `https://pypi.org/project/rapidocr-onnxruntime/`
- Tesseract package metadata: `https://pypi.org/project/tesserocr/`
- EasyOCR releases: `https://github.com/JaidedAI/EasyOCR/releases`
- PaddleOCR releases: `https://github.com/PaddlePaddle/PaddleOCR/releases`
- Tesseract releases: `https://github.com/tesseract-ocr/tesseract/releases`
- PaddleOCR pipeline docs: `https://paddlepaddle.github.io/PaddleOCR/latest/en/version3.x/pipeline_usage/OCR.html`
- PaddleOCR high-performance inference docs: `https://paddlepaddle.github.io/PaddleOCR/latest/en/version3.x/deployment/high_performance_inference.html`
- PaddleOCR ONNX docs: `https://paddlepaddle.github.io/PaddleOCR/latest/en/version3.x/deployment/obtaining_onnx_models.html`
- EasyOCR docs: `https://www.jaided.ai/easyocr/documentation/`
- PaddleOCR 3.0 report: `https://arxiv.org/abs/2507.05595`
- PP-OCRv5 report: `https://arxiv.org/abs/2603.24373`

## Current Project Constraints (Code Reality)

B.L.A.S.T. is currently EasyOCR-first and tightly integrated at these points:

- `blast_ocr/core/extractor.py` initializes `easyocr.Reader(...)` and calls `readtext(..., detail=1)`.
- `blast_ocr/core/worker.py` and `blast_ocr/pipeline.py` expect current extractor return shape.
- `blast_ocr/ui/web_app.py` includes EasyOCR bootstrap detection and cloud startup safeguards.
- Existing tests mock/assert EasyOCR-specific behavior (for example `tests/test_extractor.py`, `tests/conftest.py`).

This means a direct engine swap is high-risk without an adapter layer.

## High-Level Findings

### EasyOCR

- Latest release: `1.7.2` (2024-09-24).
- CPU mode is supported (`gpu=False`) and works with current code path.
- Stable and simple integration in this repo today.
- Slower recent release cadence versus newer OCR stacks.

### PaddleOCR

- Latest release: `3.4.0` (2026-01-29).
- Very active ecosystem and strong momentum around PP-OCRv5.
- Official docs describe CPU operation, inference threading controls, and high-performance backends.
- Important migration caveat: PaddleOCR `3.x` has interface differences from older generations and introduces a new output model.

### RapidOCR

- Lightweight CPU path with ONNX Runtime.
- Current PyPI metadata indicates `requires_python <3.13`, which is a compatibility risk for newer runtimes.

### Tesseract

- Mature and actively maintained engine.
- Strong for clean printed text but generally weaker than modern deep OCR on noisy/complex layouts without extra tuning.

## Comparison Summary (CPU-Only, April 2026)

| Engine | Freshness | CPU Suitability | Integration Risk in This Repo | Strategic Fit |
| --- | --- | --- | --- | --- |
| EasyOCR | Medium | Good | Low (already integrated) | Medium |
| PaddleOCR 3.x | High | Very Good | High without adapter | High |
| RapidOCR | Medium | Good | Medium-High (new contract + Python cap) | Medium |
| Tesseract | High | Good (for clean docs) | Medium | Medium |

## Recommendation

1. Keep EasyOCR as the production default immediately (lowest breakage risk).
2. Migrate to a multi-backend architecture with feature flags.
3. Introduce PaddleOCR as an optional backend first, then promote after shadow/canary validation.

This balances reliability today with stronger long-term engine quality.

## Non-Negotiable Safety Requirements

- No direct in-place replacement of `easyocr.Reader` calls.
- Preserve current extractor output contract consumed by pipeline/UI.
- Maintain instant rollback capability through environment variables.
- Require benchmark and quality gates before default-engine cutover.

## Related Documents

- Transition runbook: `docs/OCR_ENGINE_TRANSITION_PLAYBOOK.md`
- Deployment controls: `docs/DEPLOYMENT_GUIDE.md`
- API contracts: `docs/API_REFERENCE.md`
