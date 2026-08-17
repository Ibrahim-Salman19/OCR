# DISPATCH — survey_explorer_1

**Objective**: Survey the existing engine, inference pipeline, image pre-processing, and ONNX runtime integration.
**Key Focus**:
1. Map out current `blast_ocr/core`, `blast_ocr/engine`, and related modules.
2. Investigate RapidOCR / PP-OCRv4 ONNX integration, current execution flow, tensor decoding, and dynamic batching capabilities.
3. Identify how GPU acceleration (CUDA, TensorRT, DirectML, or CPU fallback) and vectorized batch pre-processing can be integrated to achieve sub-second single page latency and >= 5.0 pages/sec batch throughput.
4. Enumerate all required features, dependencies, and interface contracts for R1.
5. Write your comprehensive survey report to `/mnt/d/code/Projects/Python/OCR_Book/.agents/survey_explorer_1/report.md` and handoff to `/mnt/d/code/Projects/Python/OCR_Book/.agents/survey_explorer_1/handoff.md`.

## 2026-08-15T14:52:15Z
Task: Survey B.L.A.S.T. OCR codebase focusing on Engine & Inference Core (Requirement R1: High-Throughput Batch Pipeline & GPU Acceleration).
1. Map out existing `blast_ocr/core`, `blast_ocr/engine`, ONNX integration, RapidOCR usage, pipeline steps, and dependencies.
2. Determine technical design for vectorized batch pre-processing, batched ONNX tensor inference with dynamic batching and GPU/CUDA/TensorRT execution providers, multi-page parallel tensor decoding, and interfaces needed for sub-second latency and >= 5.0 pages/sec throughput.
3. Enumerate all required features, modules, files, constraints, and dependencies.
4. Output report.md and handoff.md.
