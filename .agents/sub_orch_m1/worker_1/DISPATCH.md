## 2026-08-15T15:06:13Z

You are Worker 1 for Milestone 1: High-Throughput Batch Pipeline & GPU Acceleration.
Your working directory for metadata: /mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m1/worker_1
Scope document: /mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m1/SCOPE.md
Original request: /mnt/d/code/Projects/Python/OCR_Book/.agents/ORIGINAL_REQUEST.md
Explorer reports to read:
- Explorer 1 (Codebase Architecture): /mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m1/explorer_1/handoff.md
- Explorer 2 (Batch Preprocessor & ONNX Cascade): /mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m1/explorer_2/handoff.md
- Explorer 3 (Tensor Decoders & Batched RapidOCR): /mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m1/explorer_3/handoff.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Tasks:
1. Implement `blast_ocr/core/batch_preprocessor.py`:
   - `BatchPreprocessor` class with zero-disk PDF rasterization (`rasterize_pdf`), streaming chunk generator (`stream_rasterize_pdf`), image ingestion (`rasterize_image`), SIMD batch normalization (`normalize_images`), detection batch preparation (`prepare_detection_batch`), and aspect-ratio crop bucketer (`bucket_by_aspect_ratio`).
2. Implement `blast_ocr/core/onnx_session.py`:
   - `ONNXSessionManager`, `SessionConfig`, `ONNXSessionPool`, and `create_onnx_session` factory.
   - Provider cascade: `TensorrtExecutionProvider` -> `CUDAExecutionProvider` -> `DmlExecutionProvider` -> `CPUExecutionProvider` with robust try-except fallback, diagnostics logging, and SessionOptions configuration.
3. Implement `blast_ocr/core/tensor_decoder.py`:
   - `CTCDecoder`: Vectorized NumPy batch CTC greedy decoding with duplicate collapsing, blank token filtering, character vocab mapping, and confidence averaging.
   - `DBNetDecoder`: Vectorized and multi-threaded DBNet polygon extraction with analytical unclip distance calculation ($d = \frac{w \cdot h \cdot r}{2(w+h)}$), fast box scoring, and natural reading-order sorting.
4. Update `blast_ocr/core/engines/base.py`:
   - Update `BaseOCREngine` to include `process_batch` contract with a default loop fallback to `process_page` for single-page engines.
5. Implement `blast_ocr/core/engines/batched_rapidocr.py`:
   - `BatchedRapidOCREngine(BaseOCREngine)` implementing high-throughput dynamic batch OCR: batched detection -> polygon extraction -> crop extraction -> aspect-ratio bucketing -> batched recognition -> CTC decoding -> Docling-style `LayoutEngine` hierarchy integration (`PageResult` / `page_model`).
6. Update `blast_ocr/core/engines/__init__.py`:
   - Register `"batched_rapidocr"` in `_ENGINE_REGISTRY` and export `BatchedRapidOCREngine`.
7. Implement `tests/test_batched_engine.py`:
   - Comprehensive test suite covering:
     - Zero-disk PDF rasterization (in-memory synthetic multi-page PDFs)
     - Streaming PDF rasterization
     - SIMD image normalization & detection tensor preparation
     - Aspect-ratio bucketing (verifying padding reduction and index mapping)
     - ONNX session provider cascade & fallback simulation
     - CTC greedy decoder (testing duplicate characters, blank removal, empty predictions, confidence calculations)
     - DBNet polygon extractor & reading order sorting
     - BatchedRapidOCR full batch inference, multi-page batching, and schema parity with single-page engine
8. Verify everything:
   - Run `pytest tests/test_batched_engine.py -v`
   - Run `pytest tests/test_ocr_engines.py tests/test_pipeline.py -v`
   - Run full `pytest`
   - Ensure 100% tests pass with 0 regressions.

Write your final handoff report to `/mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m1/worker_1/handoff.md` and send a completion message back with send_message.
