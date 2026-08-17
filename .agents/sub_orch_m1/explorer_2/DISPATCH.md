## 2026-08-15T14:59:59Z
You are Explorer 2 for Milestone 1.
Your working directory for metadata: /mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m1/explorer_2
Scope document: /mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m1/SCOPE.md
Original request: /mnt/d/code/Projects/Python/OCR_Book/.agents/ORIGINAL_REQUEST.md

Task:
1. Research and design `blast_ocr/core/batch_preprocessor.py`:
   - Zero-disk PDF rasterization using PyMuPDF (fitz) directly to NumPy arrays via memory buffers without writing to disk.
   - High-speed SIMD / vectorized normalization and color conversion (RGB/BGR/Grayscale).
   - Aspect-ratio bucketer algorithm for text-line crops (e.g. bucketing crops into bins like 1:1, 2:1, 4:1, 8:1, 16:1 or dynamic clustering to minimize padding during batched recognition).
2. Research and design `blast_ocr/core/onnx_session.py`:
   - ONNX Runtime Execution Provider fallback cascade: `TensorrtExecutionProvider` -> `CUDAExecutionProvider` -> `DmlExecutionProvider` -> `CPUExecutionProvider`.
   - Graph optimization, memory pattern, thread configuration options.
   - Graceful fallback when GPU libraries are not installed or CUDA initialization fails.
3. Write your findings, technical blueprints, edge-case analysis, and sample interfaces to `/mnt/d/code/Projects/Python/OCR_Book/.agents/sub_orch_m1/explorer_2/handoff.md` and send a completion message with send_message to parent.
